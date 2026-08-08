"""
参数解析层 (Resolver)

职责：获取场景元数据、推断 widget 控件、填入默认值、及查询 source_table 可选选项。
"""

import logging
import time
from typing import Any
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 简单内存缓存：key -> (timestamp, options_list)
_OPTIONS_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}
CACHE_TTL_SECONDS = 60.0


def infer_widget(param_type: str, has_source_table: bool, explicit_widget: str | None = None) -> str:
    """推断前端 Widget 类型。"""
    if explicit_widget:
        return explicit_widget
    
    param_type_lower = (param_type or "").lower()
    if param_type_lower in ("date", "datetime"):
        return "date"
    elif param_type_lower in ("daterange", "date_range"):
        return "daterange"
    elif param_type_lower == "string":
        return "select" if has_source_table else "text"
    elif param_type_lower in ("integer", "number", "float"):
        return "number"
    elif param_type_lower == "array":
        return "multiselect"
    return "text"


def resolve_source_options(source_table: str, source_column: str) -> list[dict[str, str]]:
    """
    查询 source_table 中 source_column 的去重值。
    - 针对多列/复杂表达式降级为 []
    - 安全切分 Schema 与 Table
    - 带有 60s 内存缓存
    """
    if not source_table or not source_column:
        return []
    
    # 复杂表达式/多列不查库
    if "," in source_column or "(" in source_column:
        return []
    
    cache_key = f"{source_table}:{source_column}"
    now = time.time()
    if cache_key in _OPTIONS_CACHE:
        ts, cached_opts = _OPTIONS_CACHE[cache_key]
        if now - ts < CACHE_TTL_SECONDS:
            return cached_opts

    # 安全切分 Schema 与 Table
    parts = source_table.split(".")
    if len(parts) == 2:
        schema_part, table_part = parts[0].strip('"'), parts[1].strip('"')
        formatted_table = f'"{schema_part}"."{table_part}"'
    else:
        table_part = source_table.strip('"')
        formatted_table = f'"{table_part}"'
    
    formatted_column = source_column.strip('"')
    sql = f'SELECT DISTINCT "{formatted_column}" AS val FROM {formatted_table} WHERE "{formatted_column}" IS NOT NULL LIMIT 200'

    try:
        from backend.app.config import settings
        from sqlalchemy import create_engine
        engine = create_engine(settings.analytics_database_url)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            options = [{"value": str(row[0]), "label": str(row[0])} for row in result if row[0] is not None]
            _OPTIONS_CACHE[cache_key] = (now, options)
            return options
    except Exception as e:
        logger.warning("Query source_options failed for %s.%s: %s", source_table, source_column, e)
        return []


def resolve_params(domain_name: str, scenario_name: str, template_name: str | None = None) -> dict[str, Any]:
    """
    解析场景技能定义，返回参数定义、默认值与模板元数据。
    """
    from backend.app.skills.registry import get_scenario_by_name
    scenario = get_scenario_by_name(domain_name, scenario_name)
    if not scenario:
        raise ValueError(f"Scenario not found: {domain_name}/{scenario_name}")

    templates_info = []
    for ref in scenario.get("sql_template_refs", []):
        templates_info.append({"name": ref["name"], "label": ref.get("description", ref["name"])})

    default_template = template_name or scenario.get("default_template") or (templates_info[0]["name"] if templates_info else None)

    raw_params = scenario.get("parameters", {})
    resolved_params = {}

    for p_name, p_def in raw_params.items():
        src_table = p_def.get("source_table", "")
        src_col = p_def.get("source_column", "")
        widget = infer_widget(p_def.get("type", "string"), has_source_table=bool(src_table), explicit_widget=p_def.get("widget"))
        
        # 默认值推断
        example_vals = p_def.get("example_values", [])
        explicit_default = p_def.get("default")
        default_val = explicit_default if explicit_default is not None else (str(example_vals[0]) if example_vals else ("" if p_def.get("type") == "string" else None))
        
        options = []
        explicit_options = p_def.get("options")
        if explicit_options:
            options = explicit_options
        elif widget in ("select", "multiselect") and src_table and src_col:
            fetched_opts = resolve_source_options(src_table, src_col)
            options = [{"value": "", "label": "不限"}] + fetched_opts if widget == "select" else fetched_opts
        elif example_vals:
            options = [{"value": str(v), "label": str(v)} for v in example_vals]
            if widget == "select":
                options = [{"value": "", "label": "不限"}] + options

        resolved_params[p_name] = {
            "type": p_def.get("type", "string"),
            "widget": widget,
            "description": p_def.get("description", ""),
            "required": p_def.get("required", False),
            "default": default_val,
            "options": options,
        }

    return {
        "name": scenario["name"],
        "title": scenario.get("title", scenario["name"]),
        "output_type": scenario.get("output_type", "table"),
        "templates": templates_info,
        "default_template": default_template,
        "parameters": resolved_params,
    }
