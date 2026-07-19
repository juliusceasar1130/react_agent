import pytest
from unittest.mock import MagicMock
from langchain_core.tools import ToolException
from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException
from backend.app.agent.tools.csv_export_tool import create_csv_export_tool
from backend.app.agent.tools.chart_artifact_tool import create_chart_artifact_tool
from backend.app.config import settings

# 1. 模拟数据字典
MOCK_TABLE_INFO = {
    "fct.fct_vehicle_position_current": """
        CREATE TABLE fct.fct_vehicle_position_current (
            vehicle_id VARCHAR PRIMARY KEY,
            station_id VARCHAR,
            defect_count INTEGER
        );
    """,
    "dim.dim_station": """
        CREATE TABLE dim.dim_station (
            station_id VARCHAR PRIMARY KEY,
            station_name VARCHAR
        );
    """
}

# 2. 直接对 validate_readonly_query 执行单元测试
def test_validate_readonly_query_dml_block(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    # 测试常规 DML 写操作拦截
    with pytest.raises(SQLLintException) as exc_info:
        validate_readonly_query("UPDATE fct.fct_vehicle_position_current SET defect_count = 0;", MOCK_TABLE_INFO)
    assert "DML" in str(exc_info.value) or "只读查询" in str(exc_info.value)

def test_validate_readonly_query_truncate_bypass_prevention(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    # 测试 AST 漏洞加固：拦截 TRUNCATE
    with pytest.raises(SQLLintException) as exc_info:
        validate_readonly_query("TRUNCATE TABLE fct.fct_vehicle_position_current;", MOCK_TABLE_INFO)
    assert "只读查询" in str(exc_info.value)

def test_validate_readonly_query_grant_bypass_prevention(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    # 测试 AST 漏洞加固：拦截 GRANT
    with pytest.raises(SQLLintException) as exc_info:
        validate_readonly_query("GRANT ALL PRIVILEGES ON TABLE fct.fct_vehicle_position_current TO admin;", MOCK_TABLE_INFO)
    assert "只读查询" in str(exc_info.value)

def test_validate_readonly_query_multi_statement(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    # 测试多语句拼接拦截
    with pytest.raises(SQLLintException) as exc_info:
        validate_readonly_query("SELECT 1; SELECT 2;", MOCK_TABLE_INFO)
    assert "多条" in str(exc_info.value) or "堆叠查询" in str(exc_info.value)

def test_validate_readonly_query_alias_prefix_linter(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    # 测试 Linter 规则拦截：JOIN 时缺少表前缀别名
    with pytest.raises(SQLLintException) as exc_info:
        validate_readonly_query(
            "SELECT vehicle_id FROM fct.fct_vehicle_position_current v JOIN dim.dim_station s ON v.station_id = s.station_id;", 
            MOCK_TABLE_INFO
        )
    assert "别名前缀" in str(exc_info.value)

def test_validate_readonly_query_valid_sql(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    # 测试合法 SQL 顺利通过
    try:
        validate_readonly_query(
            "SELECT v.vehicle_id, s.station_name FROM fct.fct_vehicle_position_current v JOIN dim.dim_station s ON v.station_id = s.station_id;", 
            MOCK_TABLE_INFO
        )
    except SQLLintException:
        pytest.fail("Valid SQL should not raise SQLLintException")


# 3. 对两个导出/画图工具的统一异常契约进行单元测试
def test_csv_export_tool_linter_integration(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    mock_engine = MagicMock()
    csv_tool = create_csv_export_tool(mock_engine, MOCK_TABLE_INFO)
    monkeypatch.setattr(csv_tool, "args_schema", None)  # 避开 Pydantic 类型强校验
    
    # 模拟 ToolRuntime 状态
    mock_runtime = MagicMock()
    mock_runtime.state.get.return_value = ["paint_shop"]

    # 测试 DML 规则被拦截并返回错误字符串（由于 handle_tool_error=True，ToolException 会被捕获并作为字符串返回）
    res_dml = csv_tool.invoke({
        "query": "UPDATE fct.fct_vehicle_position_current SET defect_count = 0;", 
        "required_skill": "paint_shop",
        "runtime": mock_runtime
    })
    assert "只读查询" in res_dml or "DML" in res_dml or "SEC-001" in res_dml

    # 测试 Linter 别名规则拦截
    res_alias = csv_tool.invoke({
        "query": "SELECT vehicle_id FROM fct.fct_vehicle_position_current v JOIN dim.dim_station s ON v.station_id = s.station_id;", 
        "required_skill": "paint_shop",
        "runtime": mock_runtime
    })
    assert "别名前缀" in res_alias or "STR-002" in res_alias

def test_chart_artifact_tool_linter_integration(monkeypatch):
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "")
    
    mock_engine = MagicMock()
    chart_tool = create_chart_artifact_tool(mock_engine, MOCK_TABLE_INFO)
    monkeypatch.setattr(chart_tool, "args_schema", None)  # 避开 Pydantic 类型强校验
    
    mock_runtime = MagicMock()
    mock_runtime.state.get.return_value = ["paint_shop"]
    
    series_input = [{"name": "缺陷数", "field": "defect_count", "y_axis": "left"}]

    # 测试 TRUNCATE 被拦截并返回错误字符串
    res_truncate = chart_tool.invoke({
        "query": "TRUNCATE TABLE fct.fct_vehicle_position_current;", 
        "required_skill": "paint_shop",
        "chart_type": "bar",
        "title": "缺陷图",
        "description": "测试",
        "x_field": "vehicle_id",
        "series": series_input,
        "runtime": mock_runtime
    })
    assert "只读查询" in res_truncate or "SEC-001" in res_truncate

    # 测试 Linter 别名规则拦截并返回错误字符串
    res_alias = chart_tool.invoke({
        "query": "SELECT vehicle_id FROM fct.fct_vehicle_position_current v JOIN dim.dim_station s ON v.station_id = s.station_id;", 
        "required_skill": "paint_shop",
        "chart_type": "bar",
        "title": "缺陷图",
        "description": "测试",
        "x_field": "v.vehicle_id",
        "series": series_input,
        "runtime": mock_runtime
    })
    assert "别名前缀" in res_alias or "STR-002" in res_alias
