import pytest
from unittest.mock import MagicMock
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from backend.app.agent.tools.sql_tools import create_wrapped_query_tool

def test_sql_db_query_command_success(monkeypatch):
    """测试 sql_db_query 成功查询时，返回 Command 侧信道且内容无损有界。"""
    # 1. 模拟原始查询工具
    mock_db = MagicMock()
    mock_db.run_no_throw.return_value = [{"id": 1, "name": "test_1"}, {"id": 2, "name": "test_2"}]
    # 模拟 cursor.description 行为
    mock_cursor = MagicMock()
    mock_cursor.description = [("id",), ("name",)]
    
    mock_original_tool = MagicMock()
    mock_original_tool.db = mock_db
    
    # 2. 模拟 ToolRuntime 状态
    mock_runtime = MagicMock()
    mock_runtime.state = {
        "skills_loaded": ["test_skill"]
    }
    mock_runtime.tool_call_id = "call_success"
    
    from backend.app.config import settings
    monkeypatch.setattr(settings, "sql_linter_enabled", False)
    
    # 3. 创建包装后的工具
    wrapped_tool = create_wrapped_query_tool(
        original_query_tool=mock_original_tool,
        custom_table_info={}
    )
    # 避开 Pydantic 强校验（如果有的话）
    if hasattr(wrapped_tool, "args_schema"):
        wrapped_tool.args_schema = None
        
    # 4. 调用工具
    result = wrapped_tool.invoke({
        "query": "SELECT id, name FROM test_table",
        "required_skill": "test_skill",
        "runtime": mock_runtime
    })
    
    # 5. 断言返回 Command
    assert isinstance(result, Command)
    assert "messages" in result.update
    assert "tool_artifact" in result.update
    
    # 验证 messages
    tool_msgs = result.update["messages"]
    assert len(tool_msgs) == 1
    assert isinstance(tool_msgs[0], ToolMessage)
    # content 应为包含查询时刻的字符串，并且 JSON 部分是合法的 JSON 列表
    content_str = tool_msgs[0].content
    assert "[数据真实查询时刻:" in content_str
    
    import re
    import json
    clean_json = re.sub(r"^\[数据真实查询时刻: [^\]]+\]\n", "", content_str.strip())
    preview_data = json.loads(clean_json)
    assert len(preview_data) == 2
    assert preview_data[0]["id"] == 1
    
    # 验证 tool_artifact
    artifact = result.update["tool_artifact"]
    assert artifact["kind"] == "query_result"
    assert artifact["columns"] == ["id", "name"]
    assert artifact["rows"] == [{"id": 1, "name": "test_1"}, {"id": 2, "name": "test_2"}]
    assert artifact["row_count"] == 2
    assert artifact["truncated"] is False
    assert "query_time" in artifact
    assert isinstance(artifact["source_tables"], list)


def test_sql_db_query_command_truncated(monkeypatch):
    """测试当查询结果超限截断时，Command.messages 包含 WARNING，而 tool_artifact.rows 有界且 truncated=True。"""
    # 模拟 50 行数据
    large_result = [{"id": i, "name": f"name_{i}"} for i in range(50)]
    mock_db = MagicMock()
    mock_db.run_no_throw.return_value = large_result
    
    mock_original_tool = MagicMock()
    mock_original_tool.db = mock_db
    
    mock_runtime = MagicMock()
    mock_runtime.state = {
        "skills_loaded": ["test_skill"]
    }
    mock_runtime.tool_call_id = "call_truncated"
    
    # 我们将 settings 里的限制 mock 为：硬限 10 行，预览 3 行
    from backend.app.config import settings
    monkeypatch.setattr(settings, "sql_result_hard_limit", 10)
    monkeypatch.setattr(settings, "sql_result_preview_rows", 3)
    monkeypatch.setattr(settings, "sql_linter_enabled", False)
    
    wrapped_tool = create_wrapped_query_tool(
        original_query_tool=mock_original_tool,
        custom_table_info={}
    )
    if hasattr(wrapped_tool, "args_schema"):
        wrapped_tool.args_schema = None
    
    result = wrapped_tool.invoke({
        "query": "SELECT id, name FROM test_table",
        "required_skill": "test_skill",
        "runtime": mock_runtime
    })
    
    assert isinstance(result, Command)
    artifact = result.update["tool_artifact"]
    
    # 侧信道 rows 应当是有界限的（只传输前 settings.sql_result_hard_limit = 10 行，防 SSE OOM）
    assert len(artifact["rows"]) == 10
    assert artifact["row_count"] == 50
    assert artifact["truncated"] is True
    
    # 大模型观察的预览消息只含 settings.sql_result_preview_rows = 3 行
    tool_msg = result.update["messages"][0]
    assert "⚠️ SYSTEM WARNING:" in tool_msg.content
    assert "数据预览 (前 3 行):" in tool_msg.content
    
    import re
    import json
    preview_segment = tool_msg.content.split("数据预览 (前 3 行):\n")[-1]
    preview_data = json.loads(preview_segment)
    assert len(preview_data) == 3
    assert preview_data[0]["id"] == 0


def test_sql_db_query_empty_result(monkeypatch):
    """测试空结果时 columns 能正常 fallback 提取，而不会发生越界 IndexError。"""
    mock_db = MagicMock()
    mock_db.run_no_throw.return_value = []
    
    mock_original_tool = MagicMock()
    mock_original_tool.db = mock_db
    
    mock_runtime = MagicMock()
    mock_runtime.state = {
        "skills_loaded": ["test_skill"]
    }
    mock_runtime.tool_call_id = "call_empty"
    
    from backend.app.config import settings
    monkeypatch.setattr(settings, "sql_linter_enabled", False)
    
    wrapped_tool = create_wrapped_query_tool(
        original_query_tool=mock_original_tool,
        custom_table_info={}
    )
    if hasattr(wrapped_tool, "args_schema"):
        wrapped_tool.args_schema = None
        
    result = wrapped_tool.invoke({
        "query": "SELECT * FROM empty_table",
        "required_skill": "test_skill",
        "runtime": mock_runtime
    })
    
    assert isinstance(result, Command)
    artifact = result.update["tool_artifact"]
    assert artifact["rows"] == []
    assert artifact["columns"] == []
    assert artifact["row_count"] == 0
    assert artifact["truncated"] is False


def test_sql_db_query_serialized_string_result(monkeypatch):
    """测试当 original_query_tool 返回格式化列表字符串时，能正确反序列化并保存数据。"""
    mock_db = MagicMock()
    # 模拟返回一个代表 list[dict] 的单引号 Python 字符串
    mock_db.run_no_throw.return_value = "[{'id': 99, 'val': 'hello'}]"
    
    mock_original_tool = MagicMock()
    mock_original_tool.db = mock_db
    
    mock_runtime = MagicMock()
    mock_runtime.state = {
        "skills_loaded": ["test_skill"]
    }
    mock_runtime.tool_call_id = "call_serialized"
    
    from backend.app.config import settings
    monkeypatch.setattr(settings, "sql_linter_enabled", False)
    
    wrapped_tool = create_wrapped_query_tool(
        original_query_tool=mock_original_tool,
        custom_table_info={}
    )
    if hasattr(wrapped_tool, "args_schema"):
        wrapped_tool.args_schema = None
        
    result = wrapped_tool.invoke({
        "query": "SELECT id, val FROM test_table",
        "required_skill": "test_skill",
        "runtime": mock_runtime
    })
    
    assert isinstance(result, Command)
    artifact = result.update["tool_artifact"]
    # 验证确实被成功解析并填充了 rows 列表
    assert artifact["rows"] == [{"id": 99, "val": "hello"}]
    assert artifact["columns"] == ["id", "val"]
    assert artifact["row_count"] == 1
    assert artifact["truncated"] is False
