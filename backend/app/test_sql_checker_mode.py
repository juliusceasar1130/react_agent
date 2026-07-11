import pytest
from unittest.mock import MagicMock, patch
from backend.app.agent.tools.sql_tools import create_wrapped_query_tool

def test_sql_checker_mode_fast():
    """测试在 fast 模式下，直接跳过大模型 checker 校验"""
    mock_query_tool = MagicMock()
    mock_query_tool.db.run_no_throw.return_value = "query results"
    mock_checker_tool = MagicMock()
    
    # 模拟 settings.sql_checker_mode 为 "fast"
    with patch("backend.app.agent.tools.sql_tools.settings") as mock_settings:
        mock_settings.sql_checker_mode = "fast"
        mock_settings.sql_linter_enabled = False # 屏蔽 linter
        mock_settings.sql_result_hard_limit = 1000
        mock_settings.dimension_result_hard_limit = 1000
        mock_settings.sql_result_preview_rows = 5
        
        wrapped_tool = create_wrapped_query_tool(mock_query_tool, mock_checker_tool)
        
        mock_runtime = MagicMock()
        mock_runtime.state = {"skills_loaded": ["test_skill"]}
        
        # 运行 sql_db_query
        result = wrapped_tool.func("SELECT 1", "test_skill", runtime=mock_runtime)
        
        # 断言 1: checker 的 invoke 绝没有被调用
        mock_checker_tool.invoke.assert_not_called()
        # 断言 2: 查询工具被调用了
        mock_query_tool.db.run_no_throw.assert_called_once_with("SELECT 1", include_columns=True)
        assert "query results" in result

def test_sql_checker_mode_safety():
    """测试在 safety 模式下，大模型 checker 被同步调用"""
    mock_query_tool = MagicMock()
    mock_query_tool.db.run_no_throw.return_value = "query results"
    mock_checker_tool = MagicMock()
    mock_checker_tool.invoke.return_value = "SQL Safe"
    
    # 模拟 settings.sql_checker_mode 为 "safety"
    with patch("backend.app.agent.tools.sql_tools.settings") as mock_settings:
        mock_settings.sql_checker_mode = "safety"
        mock_settings.sql_linter_enabled = False # 屏蔽 linter
        mock_settings.sql_result_hard_limit = 1000
        mock_settings.dimension_result_hard_limit = 1000
        mock_settings.sql_result_preview_rows = 5
        
        wrapped_tool = create_wrapped_query_tool(mock_query_tool, mock_checker_tool)
        
        mock_runtime = MagicMock()
        mock_runtime.state = {"skills_loaded": ["test_skill"]}
        
        # 运行 sql_db_query
        result = wrapped_tool.func("SELECT 1", "test_skill", runtime=mock_runtime)
        
        # 断言 1: checker 的 invoke 被调用了
        mock_checker_tool.invoke.assert_called_once_with({"query": "SELECT 1"})
