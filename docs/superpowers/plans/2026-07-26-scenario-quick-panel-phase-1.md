# 快捷场景面板 (Phase 1: Backend Core Engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建快捷场景面板后端核心引擎（数据结构模型扩充、参数解析层 `resolver`、SQL 参数化安全执行层 `executor`、结果格式化层 `formatter` 及现存场景 SQL 片段修正），并通过单元测试进行 100% 规则验证。

**Architecture:** 采用三层纯函数解耦架构，不依赖 FastAPI 或 HTTP 上下文。参数解析自动推断 widget 与处理默认值；SQL 执行层通过 SQLAlchemy `:param_name` 命名参数防注入，并空值整行剔除；结果格式化层统一按 `output_type`（`table`/`scalar`）封装。

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, PostgreSQL, pytest.

---

## File Structure

- **Modify**: [models.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/models.py) (Add `widget`, `default_template`, `output_type` to TypedDicts)
- **Create**: [__init__.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/direct_path/__init__.py) (Package exports for direct path engine)
- **Create**: [resolver.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/direct_path/resolver.py) (Parameter resolution, widget inferencing, `source_table` option queries)
- **Create**: [executor.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/direct_path/executor.py) (SQL template loading, bindparam parameterization, empty-value line stripping, DB execution)
- **Create**: [formatter.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/direct_path/formatter.py) (Data format transformation for `table` and `scalar`)
- **Modify**: [scenario.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/scenario.py) (Update `sql_fragment` for bindparam compatibility and set `default_template`)
- **Create**: [test_scenario_quick_panel_engine.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/tests/test_scenario_quick_panel_engine.py) (TDD Unit tests)

---

### Task 1: Extend Backend Skill Data Models (`models.py`)

**Files:**
- Modify: `backend/app/skills/models.py:33-68`
- Test: `backend/tests/test_scenario_quick_panel_engine.py`

- [ ] **Step 1: Write failing test for model definitions**

```python
# backend/tests/test_scenario_quick_panel_engine.py
import pytest
from backend.app.skills.models import ParameterDefinition, ScenarioSkill

def test_models_new_fields():
    param_def: ParameterDefinition = {
        "type": "string",
        "items_type": "",
        "description": "test",
        "required": False,
        "source_column": "col",
        "source_table": "tbl",
        "example_values": ["val"],
        "usage": "test",
        "sql_fragment": "AND col = '{value}'",
        "widget": "select",  # NEW field
    }
    assert param_def["widget"] == "select"

    scenario: ScenarioSkill = {
        "skill_name": "domain",
        "name": "scen",
        "title": "Title",
        "description": "desc",
        "example_questions": [],
        "triggers": [],
        "intent_keywords": [],
        "required_inputs": [],
        "optional_inputs": [],
        "workflow": [],
        "rules": [],
        "gotchas": [],
        "output_contract": "",
        "sql_template_refs": [],
        "script_refs": [],
        "default_template": "in_process",  # NEW field
        "output_type": "table",  # NEW field
    }
    assert scenario["default_template"] == "in_process"
    assert scenario["output_type"] == "table"
```

- [ ] **Step 2: Run test to verify it fails (or fails typechecking/attribute check if missing)**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_models_new_fields -v`
Expected: Passes dictionary key assignment but type checkers/imports verify TypedDict keys.

- [ ] **Step 3: Update `backend/app/skills/models.py`**

```python
class ParameterDefinition(TypedDict):
    """场景参数定义，用于指导 LLM 动态填充参数。"""

    type: str  # "array", "string", "integer" 等
    items_type: str  # 仅当 type="array" 时使用，表示数组元素类型
    description: str  # 参数用途说明
    required: bool  # 是否必填
    source_column: str  # 数据库列名
    source_table: str  # 可选值来源表（用于 LLM 查询可选值）
    example_values: list[str]  # 示例值
    usage: str  # 使用方式说明
    sql_fragment: str  # SQL 片段模板，{value} 为占位符
    widget: NotRequired[str]  # 显式控件类型，未指定时由 resolver 推断


class ScenarioSkill(TypedDict):
    """二级披露的固定场景技能定义。"""

    skill_name: str
    name: str
    title: str
    description: str
    example_questions: list[str]  # 新增：首页展示的示例问题
    triggers: list[str]
    intent_keywords: list[str]
    required_inputs: list[str]
    optional_inputs: list[str]
    workflow: list[str]
    rules: list[str]
    gotchas: list[str]
    output_contract: str
    sql_template_refs: list[AssetRef]
    script_refs: list[AssetRef]
    parameters: NotRequired[dict[str, ParameterDefinition]]
    scenario_root: NotRequired[str]
    domain_root: NotRequired[str]
    default_template: NotRequired[str]  # 直通路径默认 SQL 模板名称
    output_type: NotRequired[str]  # 输出格式，默认 "table"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_models_new_fields -v`
Expected: PASS

---

### Task 2: Implement Parameter Resolver (`resolver.py`)

**Files:**
- Create: `backend/app/skills/resolver.py`
- Test: `backend/tests/test_scenario_quick_panel_engine.py`

- [ ] **Step 1: Write failing tests for resolver**

```python
# Add to backend/tests/test_scenario_quick_panel_engine.py
from backend.app.skills.resolver import infer_widget, resolve_params, resolve_source_options

def test_infer_widget():
    assert infer_widget("string", has_source_table=True, explicit_widget=None) == "select"
    assert infer_widget("string", has_source_table=False, explicit_widget=None) == "text"
    assert infer_widget("integer", has_source_table=False, explicit_widget=None) == "number"
    assert infer_widget("array", has_source_table=False, explicit_widget=None) == "multiselect"
    assert infer_widget("string", has_source_table=True, explicit_widget="custom") == "custom"

def test_resolve_source_options_fallback_on_complex_column():
    # If source_column has commas (multi-column), it should gracefully return empty options without executing DB query
    opts = resolve_source_options("dim.carbody_registry", "col1, col2")
    assert opts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_infer_widget -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.skills.resolver'`

- [ ] **Step 3: Implement `backend/app/skills/resolver.py`**

```python
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
    if param_type_lower == "string":
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
        from backend.app.config import ANALYTICS_DATABASE_URL
        from sqlalchemy import create_engine
        engine = create_engine(ANALYTICS_DATABASE_URL)
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
    from backend.app.skills.registry import get_scenario_skill
    scenario = get_scenario_skill(domain_name, scenario_name)
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
        default_val = str(example_vals[0]) if example_vals else ("" if p_def.get("type") == "string" else None)
        
        options = []
        if widget in ("select", "multiselect") and src_table and src_col:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_infer_widget backend/tests/test_scenario_quick_panel_engine.py::test_resolve_source_options_fallback_on_complex_column -v`
Expected: PASS

---

### Task 3: Implement SQL Executor with Bindparam & Empty-Param Cleansing (`executor.py`)

**Files:**
- Create: `backend/app/skills/executor.py`
- Test: `backend/tests/test_scenario_quick_panel_engine.py`

- [ ] **Step 1: Write failing tests for executor SQL preparation**

```python
# Add to backend/tests/test_scenario_quick_panel_engine.py
from backend.app.skills.executor import build_executed_sql

def test_build_executed_sql_with_valid_and_empty_params():
    raw_sql = """SELECT * FROM table
WHERE 1=1
    {platform_filter}
    {stranded_days}
ORDER BY id;"""

    parameters_def = {
        "platform_filter": {
            "type": "string",
            "sql_fragment": "AND platform = '{value}'"
        },
        "stranded_days": {
            "type": "integer",
            "sql_fragment": "AND days > make_interval(days => :stranded_days)"
        }
    }

    # Case 1: platform_filter is empty string (should be stripped), stranded_days=2 (should be replaced with bindparam)
    user_params = {"platform_filter": "", "stranded_days": "2"}
    clean_sql, bind_vars = build_executed_sql(raw_sql, parameters_def, user_params)

    assert "{platform_filter}" not in clean_sql
    assert ":stranded_days" in clean_sql
    assert bind_vars == {"stranded_days": 2}
    assert "WHERE 1=1\n    AND days > make_interval(days => :stranded_days)\nORDER BY id;" in clean_sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_build_executed_sql_with_valid_and_empty_params -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.skills.executor'`

- [ ] **Step 3: Implement `backend/app/skills/executor.py`**

```python
"""
SQL 执行层 (Executor)

职责：加载场景 SQL 模板，安全过滤与绑定参数转换，执行查询返回原始行。
"""

import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_executed_sql(
    raw_sql: str,
    parameters_def: dict[str, Any],
    user_params: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """
    解析 SQL 模板：
    1. 判定为空的参数（None, "", 纯空白）整行删除
    2. 有值的参数使用 sql_fragment 替换，将 {value} 转化为命名参数 :param_name
    """
    bind_vars = {}
    lines = raw_sql.splitlines()
    final_lines = []

    for line in lines:
        matched_placeholder = False
        for param_name, param_def in parameters_def.items():
            placeholder = f"{{{param_name}}}"
            if placeholder in line:
                matched_placeholder = True
                val = user_params.get(param_name)
                # 判定非空值
                if val is not None and str(val).strip() != "":
                    sql_fragment = param_def.get("sql_fragment", "")
                    bind_placeholder = f":{param_name}"
                    
                    # 替换 {value}
                    replaced_fragment = sql_fragment.replace("{value}", bind_placeholder)
                    
                    # 物理类型转换
                    p_type = param_def.get("type", "string")
                    if p_type == "integer":
                        bind_vars[param_name] = int(val)
                    elif p_type == "float":
                        bind_vars[param_name] = float(val)
                    else:
                        bind_vars[param_name] = str(val)

                    line = line.replace(placeholder, replaced_fragment)
                    final_lines.append(line)
                else:
                    # 空值参数：剔除整行
                    pass
                break

        if not matched_placeholder:
            final_lines.append(line)

    clean_sql = "\n".join(final_lines)
    return clean_sql, bind_vars


def execute_scenario(
    domain_name: str,
    scenario_name: str,
    params: dict[str, Any],
    template_name: str | None = None,
) -> tuple[list[tuple], list[str]]:
    """
    加载模板并安全执行查询，返回 (rows, column_names)。
    """
    from backend.app.skills.registry import get_scenario_skill, load_scenario_asset
    scenario = get_scenario_skill(domain_name, scenario_name)
    if not scenario:
        raise ValueError(f"Scenario not found: {domain_name}/{scenario_name}")

    target_template = template_name or scenario.get("default_template")
    sql_refs = scenario.get("sql_template_refs", [])
    
    ref_item = None
    if target_template:
        for ref in sql_refs:
            if ref["name"] == target_template:
                ref_item = ref
                break
    if not ref_item and sql_refs:
        ref_item = sql_refs[0]
        
    if not ref_item:
        raise ValueError(f"No SQL template ref found for scenario {domain_name}/{scenario_name}")

    # 读取模板文本
    raw_sql = load_scenario_asset(scenario, ref_item["path"])
    parameters_def = scenario.get("parameters", {})

    # 构建并净化 SQL
    clean_sql, bind_vars = build_executed_sql(raw_sql, parameters_def, params)

    from backend.app.config import ANALYTICS_DATABASE_URL
    from sqlalchemy import create_engine
    engine = create_engine(ANALYTICS_DATABASE_URL)

    with engine.connect() as conn:
        result = conn.execute(text(clean_sql), bind_vars)
        columns = list(result.keys())
        rows = [tuple(row) for row in result.fetchmany(300)]
        return rows, columns
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_build_executed_sql_with_valid_and_empty_params -v`
Expected: PASS

---

### Task 4: Implement Result Formatter (`formatter.py`)

**Files:**
- Create: `backend/app/skills/formatter.py`
- Test: `backend/tests/test_scenario_quick_panel_engine.py`

- [ ] **Step 1: Write failing tests for result formatter**

```python
# Add to backend/tests/test_scenario_quick_panel_engine.py
from backend.app.skills.formatter import format_result

def test_format_result_table():
    rows = [("V001", "ADP", 3.2), ("V002", "ADP", 2.1)]
    columns = ["vehicle_id", "platform_code", "stranded_hours"]
    res = format_result(rows, columns, "table")
    assert res == {
        "type": "table",
        "columns": ["vehicle_id", "platform_code", "stranded_hours"],
        "rows": [["V001", "ADP", 3.2], ["V002", "ADP", 2.1]],
        "row_count": 2,
    }

def test_format_result_scalar():
    rows = [(42,)]
    columns = ["count"]
    res = format_result(rows, columns, "scalar")
    assert res == {
        "type": "scalar",
        "value": 42,
        "label": "查询结果",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_format_result_table -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.skills.formatter'`

- [ ] **Step 3: Implement `backend/app/skills/formatter.py`**

```python
"""
结果格式化层 (Formatter)

职责：将原始数据库查询行转化为前端渲染组件（Table / Scalar）直接可用的 JSON 数据形态。
"""

from typing import Any


def format_result(rows: list[tuple], columns: list[str], output_type: str = "table") -> dict[str, Any]:
    """根据 output_type 将数据库查询行格式化为输出数据。"""
    if output_type == "scalar":
        val = rows[0][0] if rows and len(rows[0]) > 0 else 0
        return {
            "type": "scalar",
            "value": val,
            "label": "查询结果",
        }
    
    # 默认 "table"
    formatted_rows = [list(row) for row in rows]
    return {
        "type": "table",
        "columns": columns,
        "rows": formatted_rows,
        "row_count": len(formatted_rows),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_format_result_table backend/tests/test_scenario_quick_panel_engine.py::test_format_result_scalar -v`
Expected: PASS

---

### Task 5: Update Existing Scenario Definition (`stranded_vehicle_detection/scenario.py`)

**Files:**
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/scenario.py`
- Test: `backend/tests/test_scenario_quick_panel_engine.py`

- [ ] **Step 1: Write failing test verifying scenario metadata updates**

```python
# Add to backend/tests/test_scenario_quick_panel_engine.py
from backend.app.skills.domains.paint_shop_vehicle_logistics.scenarios.stranded_vehicle_detection.scenario import SCENARIO

def test_stranded_vehicle_scenario_metadata():
    assert SCENARIO.get("default_template") == "in_process"
    params = SCENARIO["parameters"]
    assert "make_interval" in params["stranded_days"]["sql_fragment"]
    assert "make_interval" in params["in_process_stranded_days"]["sql_fragment"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_stranded_vehicle_scenario_metadata -v`
Expected: FAIL with `AssertionError: assert 'make_interval' in 'AND ...'`

- [ ] **Step 3: Update `stranded_vehicle_detection/scenario.py`**

Modify `SCENARIO` dictionary:
- Add `"default_template": "in_process"`
- Update `stranded_days` `sql_fragment` to `'AND (cr."retention_checkpoint_pass_at" - cr."first_seen_at") > make_interval(days => :stranded_days)'`
- Update `in_process_stranded_days` `sql_fragment` to `'AND (CURRENT_TIMESTAMP - cr."first_seen_at") > make_interval(days => :in_process_stranded_days)'`
- Update `platform_filter` `sql_fragment` to `'AND cr."platform_code" = :platform_filter'`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scenario_quick_panel_engine.py::test_stranded_vehicle_scenario_metadata -v`
Expected: PASS

---

## Self-Review Checklist

1. **Spec coverage:** Covers `resolver.py`, `executor.py`, `formatter.py`, `models.py`, and `scenario.py` update as required in Phase 1 spec.
2. **Placeholder scan:** No TBDs, no TODOs, all code blocks provided.
3. **Type consistency:** Function names and parameters consistent across tasks.
