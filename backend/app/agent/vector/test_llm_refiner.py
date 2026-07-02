import pytest
from unittest.mock import patch, MagicMock
from backend.app.agent.vector.llm_refiner import refine_sql_case_with_llm, RefinedSQLCase

@patch("backend.app.agent.vector.llm_refiner._create_llm")
def test_refine_sql_case_with_llm_success(mock_get_llm):
    """测试 LLM 成功解析意图并对 SQL 中的车身号/日期脱敏"""
    mock_llm_instance = MagicMock()
    mock_structured_llm = MagicMock()
    
    # 模拟 with_structured_output 返回结构化模型
    mock_llm_instance.with_structured_output.return_value = mock_structured_llm
    
    # 模拟 invoke 返回合法的结构化输出字典
    mock_structured_llm.invoke.return_value = {
        "raw": MagicMock(),
        "parsed": RefinedSQLCase(
            rewritten_query="查询昨天二号线的出车数",
            desensitized_sql="SELECT count(*) FROM paint_vehicle WHERE line_id = 2 AND production_date = {{日期}}"
        ),
        "parsing_error": None
    }
    
    mock_get_llm.return_value = mock_llm_instance
    
    query = "查2号线的出车数 [澄清提问: 我们想和您确认哪天？ -> 澄清回答: 昨天]"
    sql = "SELECT count(*) FROM paint_vehicle WHERE line_id = 2 AND production_date = '2026-06-28'"
    
    res_query, res_sql = refine_sql_case_with_llm(query, sql)
    
    assert res_query == "查询昨天二号线的出车数"
    assert "{{日期}}" in res_sql
    assert "2026-06-28" not in res_sql


@patch("backend.app.agent.vector.llm_refiner._create_llm")
def test_refine_sql_case_with_llm_parsing_error(mock_get_llm):
    """测试 LLM 返回的结果校验失败时，能够安全降级回退到原始数据"""
    mock_llm_instance = MagicMock()
    mock_structured_llm = MagicMock()
    
    mock_llm_instance.with_structured_output.return_value = mock_structured_llm
    
    # 模拟返回包含 parsing_error 的输出字典
    mock_structured_llm.invoke.return_value = {
        "raw": MagicMock(),
        "parsed": None,
        "parsing_error": ValueError("Schema validation failed")
    }
    mock_get_llm.return_value = mock_llm_instance
    
    query = "查2号线的出车数"
    sql = "SELECT 1"
    
    res_query, res_sql = refine_sql_case_with_llm(query, sql)
    
    assert res_query == "查2号线的出车数"
    assert res_sql == "SELECT 1"


@patch("backend.app.agent.vector.llm_refiner._create_llm")
def test_refine_sql_case_with_llm_fallback(mock_get_llm):
    """测试 LLM 提炼连接报错时，能够安全降级回退到原始数据"""
    mock_llm_instance = MagicMock()
    mock_structured_llm = MagicMock()
    
    mock_llm_instance.with_structured_output.return_value = mock_structured_llm
    mock_structured_llm.invoke.side_effect = Exception("LLM connection error")
    mock_get_llm.return_value = mock_llm_instance
    
    query = "查2号线的出车数"
    sql = "SELECT 1"
    
    res_query, res_sql = refine_sql_case_with_llm(query, sql)
    
    assert res_query == "查2号线的出车数"
    assert res_sql == "SELECT 1"


@patch("backend.app.agent.vector.llm_refiner._create_llm")
def test_refine_multi_sql_case_success(mock_get_llm):
    """测试 LLM 能够成功提取和脱敏多步拼接的 SQL 模板，并保持步骤结构"""
    mock_llm_instance = MagicMock()
    mock_structured_llm = MagicMock()

    mock_llm_instance.with_structured_output.return_value = mock_structured_llm

    mock_structured_llm.invoke.return_value = {
        "raw": MagicMock(),
        "parsed": RefinedSQLCase(
            rewritten_query="查询昨天流挂缺陷车辆的配置",
            desensitized_sql="-- Step 1\nSELECT id FROM position WHERE name = {{产线名称}};\n\n-- Step 2\nSELECT config FROM process WHERE position_id = {{Step1.id}}"
        ),
        "parsing_error": None
    }
    mock_get_llm.return_value = mock_llm_instance

    raw_query = "查昨天缺陷车的配置"
    raw_sql = "-- Step 1\nSELECT id FROM position WHERE name = 'paint_shop';\n\n-- Step 2\nSELECT config FROM process WHERE position_id = 42"

    res_query, res_sql = refine_sql_case_with_llm(raw_query, raw_sql)

    assert "Step 1" in res_sql
    assert "Step 2" in res_sql
    assert "{{产线名称}}" in res_sql
    assert "{{Step1.id}}" in res_sql
