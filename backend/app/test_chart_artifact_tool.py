import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.config import settings
from backend.app.agent.tools.chart_artifact_tool import (
    BuildChartArtifactInput,
    create_chart_artifact_tool,
)
from backend.app.chart_artifacts import get_chart_record


@pytest.fixture()
def chart_tool_tmp_dir(monkeypatch):
    tmp_path = Path.cwd() / f".tmp_chart_tool_{uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    monkeypatch.setattr(settings, "chart_artifact_dir", str(tmp_path))
    monkeypatch.setattr(settings, "chart_artifact_ttl_hours", 24)
    monkeypatch.setattr(settings, "chart_artifact_max_points", 100)
    try:
        yield tmp_path
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_chart_tool_requires_loaded_skill(chart_tool_tmp_dir: Path) -> None:
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": []})

    result = tool.func(
        query="SELECT 1 AS x, 2 AS y",
        required_skill="paint_shop_defect_analysis",
        chart_type="line",
        title="demo",
        description="demo",
        x_field="x",
        series=[{"name": "y", "field": "y", "y_axis": "left"}],
        runtime=runtime,
    )

    assert "请先使用 load_skill" in result


def test_chart_tool_uses_structured_args_schema(chart_tool_tmp_dir: Path) -> None:
    tool = create_chart_artifact_tool("sqlite:///")

    assert tool.args_schema is BuildChartArtifactInput


def test_chart_tool_returns_chart_ref(chart_tool_tmp_dir: Path) -> None:
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": ["paint_shop_defect_analysis"]})

    result = tool.func(
        query="SELECT '2026-04-01' AS stat_date, 2 AS detection_count",
        required_skill="paint_shop_defect_analysis",
        chart_type="auto",
        title="demo",
        description="demo",
        x_field="stat_date",
        series=[{"name": "检测次数", "field": "detection_count", "y_axis": "left"}],
        runtime=runtime,
    )

    payload = json.loads(result)
    assert payload["kind"] == "chart_artifact_ref"
    assert payload["chart_id"].startswith("cht_")
    assert payload["point_count"] == 1
    assert payload["chart_type"] in {"line", "bar"}


def test_chart_tool_invoke_works_without_runtime_injection(chart_tool_tmp_dir: Path) -> None:
    tool = create_chart_artifact_tool("sqlite:///")

    result = tool.invoke(
        {
            "query": "SELECT '2026-04-01' AS stat_date, 2 AS detection_count, 5 AS total_defects",
            "required_skill": "paint_shop_defect_analysis",
            "chart_type": "auto",
            "title": "demo",
            "description": "demo",
            "x_field": "stat_date",
            "series": [
                {"name": "检测次数", "field": "detection_count", "color": "#1f77b4"},
                {"name": "缺陷总数", "field": "total_defects", "color": "#ff7f0e"},
            ],
        }
    )

    payload = json.loads(result)
    assert payload["kind"] == "chart_artifact_ref"


def test_chart_tool_accepts_injected_runtime_argument(chart_tool_tmp_dir: Path) -> None:
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": ["paint_shop_defect_analysis"]})

    result = tool.invoke(
        {
            "name": "build_chart_artifact",
            "id": "abc",
            "type": "tool_call",
            "args": {
                "query": "SELECT '2026-04-01' AS stat_date, 2 AS detection_count, 5 AS total_defects",
                "required_skill": "paint_shop_defect_analysis",
                "chart_type": "line",
                "title": "demo",
                "description": "demo",
                "x_field": "stat_date",
                "series": [
                    {"name": "检测次数", "field": "detection_count", "color": "#1f77b4"},
                    {"name": "缺陷总数", "field": "total_defects", "color": "#ff7f0e"},
                ],
                "runtime": runtime,
            },
        }
    )

    assert json.loads(result.content)["kind"] == "chart_artifact_ref"


def test_chart_tool_rejects_excess_points(chart_tool_tmp_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "chart_artifact_max_points", 1)
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": ["paint_shop_defect_analysis"]})

    result = tool.func(
        query="SELECT 1 AS x, 2 AS y UNION ALL SELECT 2 AS x, 3 AS y",
        required_skill="paint_shop_defect_analysis",
        chart_type="line",
        title="demo",
        description="demo",
        x_field="x",
        series=[{"name": "y", "field": "y", "y_axis": "left"}],
        runtime=runtime,
    )

    assert "图表点数超过上限" in result


def test_chart_tool_rejects_non_numeric_series_field(chart_tool_tmp_dir: Path) -> None:
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": ["paint_shop_defect_analysis"]})

    result = tool.func(
        query="SELECT '2026-04-01' AS stat_date, 'A7' AS defect_type_name, 2 AS detection_count",
        required_skill="paint_shop_defect_analysis",
        chart_type="line",
        title="demo",
        description="demo",
        x_field="stat_date",
        series=[{"name": "车型", "field": "defect_type_name", "y_axis": "left"}],
        runtime=runtime,
    )

    assert "必须引用数值列" in result


def test_chart_tool_rejects_unsupported_series_keys(chart_tool_tmp_dir: Path) -> None:
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": ["paint_shop_defect_analysis"]})

    result = tool.func(
        query="SELECT '2026-04-01' AS stat_date, 2 AS detection_count",
        required_skill="paint_shop_defect_analysis",
        chart_type="line",
        title="demo",
        description="demo",
        x_field="stat_date",
        series=[
            {
                "name": "检测次数",
                "field": "detection_count",
                "y_axis": "left",
                "metric": "detection_count",
            }
        ],
        runtime=runtime,
    )

    assert "图表系列参数不合法" in result


def test_chart_tool_infers_category_split_from_series_name(
    chart_tool_tmp_dir: Path,
) -> None:
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": ["paint_shop_defect_analysis"]})

    result = tool.func(
        query=(
            "SELECT '2026-04-01' AS stat_date, 'A7' AS defect_type_name, 2 AS detection_count "
            "UNION ALL "
            "SELECT '2026-04-01' AS stat_date, 'TiguanL' AS defect_type_name, 8 AS detection_count"
        ),
        required_skill="paint_shop_defect_analysis",
        chart_type="line",
        title="demo",
        description="demo",
        x_field="stat_date",
        series=[
            {"name": "A7 - 检测次数", "field": "detection_count", "y_axis": "left"},
            {"name": "TiguanL - 检测次数", "field": "detection_count", "y_axis": "left"},
        ],
        runtime=runtime,
    )

    payload = json.loads(result)
    chart_payload = get_chart_record(payload["chart_id"])
    inferred_pairs = {
        (item["name"], item.get("category_field"), item.get("category_value"))
        for item in chart_payload["series"]
    }

    assert ("A7 - 检测次数", "defect_type_name", "A7") in inferred_pairs
    assert ("TiguanL - 检测次数", "defect_type_name", "TiguanL") in inferred_pairs


def test_structured_chart_input_requires_category_pair() -> None:
    with pytest.raises(ValidationError):
        BuildChartArtifactInput.model_validate(
            {
                "query": "SELECT 1 AS x, 2 AS y",
                "required_skill": "paint_shop_defect_analysis",
                "chart_type": "line",
                "title": "demo",
                "description": "demo",
                "x_field": "x",
                "series": [
                    {
                        "name": "A7 - 检测次数",
                        "field": "y",
                        "category_field": "defect_type_name",
                    }
                ],
            }
        )


def test_structured_chart_input_rejects_unknown_top_level_field() -> None:
    with pytest.raises(ValidationError):
        BuildChartArtifactInput.model_validate(
            {
                "query": "SELECT 1 AS x, 2 AS y",
                "required_skill": "paint_shop_defect_analysis",
                "chart_type": "line",
                "title": "demo",
                "description": "demo",
                "x_field": "x",
                "series": [{"name": "检测次数", "field": "y"}],
                "unexpected": "boom",
            }
        )
