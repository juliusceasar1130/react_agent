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


def test_infer_widget():
    from backend.app.skills.direct_path import infer_widget
    assert infer_widget("string", has_source_table=True, explicit_widget=None) == "select"
    assert infer_widget("string", has_source_table=False, explicit_widget=None) == "text"
    assert infer_widget("integer", has_source_table=False, explicit_widget=None) == "number"
    assert infer_widget("array", has_source_table=False, explicit_widget=None) == "multiselect"
    assert infer_widget("string", has_source_table=True, explicit_widget="custom") == "custom"


def test_resolve_source_options_fallback_on_complex_column():
    from backend.app.skills.direct_path import resolve_source_options
    opts = resolve_source_options("dim.carbody_registry", "col1, col2")
    assert opts == []


def test_build_executed_sql_with_valid_and_empty_params():
    from backend.app.skills.direct_path import build_executed_sql
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

    user_params = {"platform_filter": "", "stranded_days": "2"}
    clean_sql, bind_vars = build_executed_sql(raw_sql, parameters_def, user_params)

    assert "{platform_filter}" not in clean_sql
    assert ":stranded_days" in clean_sql
    assert bind_vars == {"stranded_days": 2}
    assert "WHERE 1=1\n    AND days > make_interval(days => :stranded_days)\nORDER BY id;" in clean_sql


def test_format_result_table():
    from backend.app.skills.direct_path import format_result
    rows = [("V001", "ADP", 3.2), ("V002", "ADP", 2.1)]
    columns = ["vehicle_id", "platform_code", "stranded_hours"]
    res = format_result(rows, columns, "table")
    assert res == {
        "type": "table",
        "columns": ["vehicle_id", "platform_code", "stranded_hours"],
        "rows": [["V001", "ADP", 3.2], ["V002", "ADP", 2.1]],
        "row_count": 2,
        "total_count": 2,
        "page": 1,
        "page_size": 50,
        "total_pages": 1,
        "is_truncated": False,
    }


def test_format_result_scalar():
    from backend.app.skills.direct_path import format_result
    rows = [(42,)]
    columns = ["count"]
    res = format_result(rows, columns, "scalar")
    assert res == {
        "type": "scalar",
        "value": 42,
        "label": "查询结果",
    }


def test_stranded_vehicle_scenario_metadata():
    from backend.app.skills.domains.paint_shop_vehicle_logistics.scenarios.stranded_vehicle_detection.scenario import SCENARIO
    assert SCENARIO.get("default_template") == "in_process"
    params = SCENARIO["parameters"]
    assert "make_interval" in params["stranded_days"]["sql_fragment"]
    assert "make_interval" in params["in_process_stranded_days"]["sql_fragment"]
    assert "vehicle_type_filter" in params
    assert params["vehicle_type_filter"]["widget"] == "select"
    assert params["vehicle_type_filter"]["example_values"][0] == "product_vehicle"
    assert "vehicle_type_filter" in SCENARIO["optional_inputs"]


