import pytest
from unittest.mock import patch, MagicMock
from backend.app.agent.vector.llm_refiner import refine_sql_case_with_llm

@patch("backend.app.agent.vector.llm_refiner._create_llm")
def test_refine_sql_case_with_llm_success(mock_get_llm):
    """测试 LLM 成功解析意图并对 SQL 中的车身号/日期脱敏"""
    mock_llm_instance = MagicMock()
    # 模拟大模型返回符合 JSON 协议的字符串
    mock_llm_instance.invoke.return_value = MagicMock(content="""
    {
        "rewritten_query": "查询昨天二号线的出车数",
        "desensitized_sql": "SELECT count(*) FROM paint_vehicle WHERE line_id = 2 AND production_date = <日期>"
    }
    """)
    mock_get_llm.return_value = mock_llm_instance
    
    query = "查2号线的出车数 [澄清提问: 我们想和您确认哪天？ -> 澄清回答: 昨天]"
    sql = "SELECT count(*) FROM paint_vehicle WHERE line_id = 2 AND production_date = '2026-06-28'"
    
    res_query, res_sql = refine_sql_case_with_llm(query, sql)
    
    assert res_query == "查询昨天二号线的出车数"
    assert "<日期>" in res_sql
    assert "2026-06-28" not in res_sql


@patch("backend.app.agent.vector.llm_refiner._create_llm")
def test_refine_sql_case_with_llm_fallback(mock_get_llm):
    """测试 LLM 提炼报错时，能够安全降级回退到原始数据"""
    mock_llm_instance = MagicMock()
    mock_llm_instance.invoke.side_effect = Exception("LLM connection error")
    mock_get_llm.return_value = mock_llm_instance
    
    query = "查2号线的出车数"
    sql = "SELECT 1"
    
    res_query, res_sql = refine_sql_case_with_llm(query, sql)
    
    assert res_query == "查2号线的出车数"
    assert res_sql == "SELECT 1"
