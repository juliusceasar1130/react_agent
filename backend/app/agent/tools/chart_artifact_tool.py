"""图表 artifact 工具。"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from langchain.tools import ToolRuntime, tool as langchain_tool
from langchain_core.tools import ToolException
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException
from backend.app.agent.utils import emit_stream_status
from backend.app.chart_artifacts import create_chart_record
from backend.app.config import settings

logger = logging.getLogger(__name__)


class ChartSeriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Series display name. For category comparison charts, include a recognizable "
            "category value in the name such as A7 or TiguanL."
        )
    )
    field: str = Field(
        description=(
            "Numeric metric field from the SQL result, for example detection_count or "
            "avg_defect_per_detection. Do not use dimension/category fields here."
        )
    )
    y_axis: Literal["left", "right"] = Field(
        default="left",
        description="Which y-axis this series uses: left or right.",
    )
    category_field: str | None = Field(
        default=None,
        description=(
            "Optional category/dimension field used to split one numeric metric into "
            "multiple series, for example defect_type_name."
        ),
    )
    category_value: str | None = Field(
        default=None,
        description=(
            "Optional category value matching category_field, for example A7 or TiguanL."
        ),
    )
    color: str | None = Field(
        default=None,
        description="Optional hex color for this series, for example #1f77b4.",
    )

    @model_validator(mode="after")
    def _validate_category_pair(self) -> "ChartSeriesInput":
        if bool(self.category_field) != bool(self.category_value):
            raise ValueError("category_field 和 category_value 必须同时提供。")
        return self


class BuildChartArtifactInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    query: str = Field(
        description="Read-only SELECT query used to fetch chart data."
    )
    required_skill: str = Field(
        description="The loaded business skill required for this chart query."
    )
    chart_type: Literal["line", "bar", "auto"] = Field(
        description="Chart type. Use auto when the tool should infer line or bar."
    )
    title: str = Field(description="Chart title shown to the user.")
    description: str = Field(
        default="",
        description="Short chart description shown under the title.",
    )
    x_field: str = Field(
        description="Field from SQL result used as the x-axis, usually a date or category."
    )
    series: list[ChartSeriesInput] = Field(
        description=(
            "Series definitions. Use field for numeric columns only. For multi-category "
            "comparisons on the same metric, provide category_field/category_value."
        ),
        min_length=1,
    )

    @model_validator(mode="after")
    def _validate_extra_fields(self) -> "BuildChartArtifactInput":
        extra_fields = set((self.model_extra or {}).keys())
        unsupported = sorted(extra_fields - {"runtime"})
        if unsupported:
            joined = "、".join(unsupported)
            raise ValueError(f"不支持的图表工具参数: {joined}")
        return self


_SERIES_INPUT_ADAPTER = TypeAdapter(list[ChartSeriesInput])


def _looks_like_temporal_field(field_name: str, values: list[Any]) -> bool:
    lowered = field_name.lower()
    if any(token in lowered for token in ("date", "time", "day", "month", "year")):
        return True

    for value in values:
        if value is None:
            continue
        if isinstance(value, (date, datetime)):
            return True
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                datetime.fromisoformat(normalized)
                return True
            except ValueError:
                continue
    return False


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _is_numeric_value(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _format_validation_error(prefix: str, exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    location = " -> ".join(str(part) for part in first_error.get("loc", []))
    message = first_error.get("msg", "参数不合法")
    if location:
        return f"Error: {prefix} - {location}: {message}"
    return f"Error: {prefix} - {message}"


def _infer_category_series(
    *,
    rows: list[dict[str, Any]],
    x_field: str,
    series: list[dict[str, Any]],
) -> None:
    duplicate_fields = {
        field for field, count in Counter(item["field"] for item in series).items() if count > 1
    }
    if not duplicate_fields or not rows:
        return

    series_fields = {item["field"] for item in series}
    candidate_columns: list[tuple[str, list[str]]] = []
    for column in rows[0].keys():
        if column == x_field or column in series_fields:
            continue

        values = [row.get(column) for row in rows if row.get(column) is not None]
        if not values or all(_is_numeric_value(value) for value in values):
            continue

        unique_values = list(dict.fromkeys(str(value) for value in values))
        if len(unique_values) < 2:
            continue

        candidate_columns.append((column, unique_values))

    if not candidate_columns:
        return

    unresolved_names: list[str] = []
    for item in series:
        if item["field"] not in duplicate_fields:
            continue
        if item.get("category_field") and item.get("category_value") is not None:
            continue

        matched_pairs: list[tuple[str, str]] = []
        for column, values in candidate_columns:
            matched_values = [value for value in values if value in item["name"]]
            matched_pairs.extend((column, value) for value in matched_values)

        if len(matched_pairs) == 1:
            item["category_field"], item["category_value"] = matched_pairs[0]
        else:
            unresolved_names.append(item["name"])

    if unresolved_names:
        joined_names = "、".join(unresolved_names)
        raise ValueError(
            "同一数值字段被拆成多个图表系列（多系列对比）时，必须为每条系列显式提供 "
            f"category_field 和 category_value 组合。未指定分类的系列: {joined_names}"
        )


def _resolve_chart_type(chart_type: str, x_field: str, rows: list[dict[str, Any]]) -> str:
    if chart_type in {"line", "bar"}:
        return chart_type

    x_values = [row.get(x_field) for row in rows]
    return "line" if _looks_like_temporal_field(x_field, x_values) else "bar"


def _validate_numeric_series_fields(
    rows: list[dict[str, Any]],
    series: list[dict[str, Any]],
) -> None:
    for item in series:
        values = [row.get(item["field"]) for row in rows if row.get(item["field"]) is not None]
        if not values or not all(_is_numeric_value(value) for value in values):
            raise ValueError(
                f"图表序列字段 '{item['field']}' 必须引用数值列，不能使用车型、缺陷类型等分类字段。"
            )


def create_chart_artifact_tool(
    engine: Engine,
    custom_table_info: dict = None,
) -> Any:
    """创建图表 artifact 工具。"""

    @langchain_tool(args_schema=BuildChartArtifactInput)
    def build_chart_artifact(
        query: str,
        required_skill: str,
        chart_type: str,
        title: str,
        description: str,
        x_field: str,
        series: list[ChartSeriesInput],
        runtime: ToolRuntime | None = None,
    ) -> str:
        """
        Execute a SQL query, create a chart artifact, and return a lightweight chart reference.

        IMPORTANT: Use this tool only after the user explicitly asks for a chart.
        The tool returns a lightweight chart reference for the LLM, while the full chart payload
        is stored server-side for the frontend to fetch by chart_id.

        When multiple series reuse the same numeric field for category comparison,
        do not only duplicate the field name. You must explicitly provide category_field and
        category_value for each series so the tool can accurately split the data.
        """
        if runtime is not None:
            skills_loaded = runtime.state.get("skills_loaded", [])
            if required_skill not in skills_loaded:
                raise ToolException(
                    f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再生成图表。\n"
                    f"当前已加载的技能: {skills_loaded or '无'}。"
                )
        else:
            logger.debug(
                "build_chart_artifact 未注入 ToolRuntime，跳过 skills_loaded 校验。required_skill=%s",
                required_skill,
            )

        if not series:
            raise ToolException("Error: 生成图表至少需要一个序列字段。")

        try:
            emit_stream_status(
                "正在执行 SQL 合规检查",
                stage="querying",
                source="build_chart_artifact",
            )
            validate_readonly_query(query, custom_table_info)

            emit_stream_status(
                "正在准备图表数据",
                stage="querying",
                source="build_chart_artifact",
            )

            with engine.connect() as conn:
                result = conn.execute(text(query))
                rows = [
                    {key: _normalize_value(value) for key, value in dict(row).items()}
                    for row in result.mappings().all()
                ]

            if not rows:
                return "Error: 查询结果为空，无法生成图表。"

            if len(rows) > settings.chart_artifact_max_points:
                return (
                    "Error: 图表点数超过上限，当前结果不适合直接绘图。"
                    "请先聚合、缩小时间范围，或继续使用 export_to_csv。"
                )

            columns = set(rows[0].keys())
            if x_field not in columns:
                return f"Error: x_field '{x_field}' 不存在于查询结果中。"

            try:
                validated_series = _SERIES_INPUT_ADAPTER.validate_python(series)
            except ValidationError as exc:
                return _format_validation_error("图表系列参数不合法", exc)

            normalized_series: list[dict[str, Any]] = []
            for item in validated_series:
                field = item.field.strip()
                if field not in columns:
                    return f"Error: 图表序列字段 '{field}' 不存在于查询结果中。"

                category_field = item.category_field.strip() if item.category_field else None
                category_value = item.category_value.strip() if item.category_value else None
                if category_field and category_field not in columns:
                    return f"Error: 分类字段 '{category_field}' 不存在于查询结果中。"

                normalized_series.append(
                    {
                        "name": item.name.strip() or field,
                        "field": field,
                        "y_axis": item.y_axis,
                        "category_field": category_field,
                        "category_value": category_value,
                        "color": item.color.strip() if item.color else None,
                    }
                )

            try:
                _validate_numeric_series_fields(rows, normalized_series)
                _infer_category_series(
                    rows=rows,
                    x_field=x_field,
                    series=normalized_series,
                )
            except ValueError as exc:
                return f"Error: {exc}"

            resolved_chart_type = _resolve_chart_type(chart_type, x_field, rows)
            payload = {
                "kind": "chart_spec",
                "chart_type": resolved_chart_type,
                "title": title,
                "description": description,
                "x_field": x_field,
                "series": normalized_series,
                "rows": rows,
            }
            chart_ref = create_chart_record(payload=payload)

            emit_stream_status(
                "图表 artifact 已生成",
                stage="writing",
                source="build_chart_artifact",
            )
            return json.dumps(chart_ref, ensure_ascii=False)
        except SQLLintException as exc:
            logger.warning(f"build_chart_artifact 校验未通过拦截: {exc}")
            raise ToolException(str(exc))
        except Exception as exc:
            logger.error("图表 artifact 生成失败: %s", exc)
            raise ToolException(f"Error: 图表生成失败 - {exc}")

    build_chart_artifact.handle_tool_error = True
    return build_chart_artifact
