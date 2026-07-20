import pytest
from unittest.mock import MagicMock
import os
from langgraph.types import Command
from langchain_core.tools import ToolException

def test_export_to_csv_command_returns():
    from backend.app.agent.tools.csv_export_tool import create_csv_export_tool

    engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    # 模拟查询列和行
    mock_conn.execute.return_value.keys.return_value = ["id", "val"]
    mock_conn.execute.return_value.fetchall.return_value = [
        (1, "a"),
        (2, "b"),
    ]
    engine.connect.return_value = mock_conn

    runtime = MagicMock()
    runtime.state = {"skills_loaded": ["test_skill"]}

    # 临时注入配置
    os.environ["SQL_EXPORT_MAX_ROWS"] = "100"

    tool = create_csv_export_tool(engine)
    # 直接调用 tool.func 以绕过 Pydantic input model 校验，完美运行单元测试
    result = tool.func(
        query="SELECT id, val FROM t",
        required_skill="test_skill",
        runtime=runtime
    )

    # 验证返回结构为 Command
    assert isinstance(result, Command)
    assert "messages" in result.update
    assert "tool_artifact" in result.update

    # 验证侧信道元数据字段
    artifact = result.update["tool_artifact"]
    assert artifact["kind"] == "file_export"
    assert artifact["row_count"] == 2
    assert artifact["col_count"] == 2
    assert artifact["columns"] == ["id", "val"]
    assert "file_id" in artifact

    # 验证历史持久化内容格式
    msg = result.update["messages"][0]
    import json
    parsed_ref = json.loads(msg.content)
    assert parsed_ref["kind"] == "file_export"
    assert parsed_ref["file_id"] == artifact["file_id"]

def test_export_to_csv_oom_limit():
    from backend.app.agent.tools.csv_export_tool import create_csv_export_tool
    from backend.app.config import settings

    engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    # 模拟超限数据集
    mock_conn.execute.return_value.keys.return_value = ["id"]
    mock_conn.execute.return_value.fetchall.return_value = [(i,) for i in range(10)]
    engine.connect.return_value = mock_conn

    runtime = MagicMock()
    runtime.state = {"skills_loaded": ["test_skill"]}

    # 动态修改单例属性以触发安全限制
    old_max = settings.sql_export_max_rows
    settings.sql_export_max_rows = 5

    try:
        tool = create_csv_export_tool(engine)
        # 在原生 func 模式下运行，抛出的 ToolException 不会被 langchain 拦截，因此可直接 raises 断言
        with pytest.raises(ToolException) as excinfo:
            tool.func(
                query="SELECT id FROM t",
                required_skill="test_skill",
                runtime=runtime
            )
        assert "超过系统安全上限" in str(excinfo.value)
    finally:
        # 还原配置，防止干扰后续其他用例
        settings.sql_export_max_rows = old_max
