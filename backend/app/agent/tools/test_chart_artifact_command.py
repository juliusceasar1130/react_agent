import pytest
from unittest.mock import MagicMock
from langgraph.types import Command

def test_build_chart_artifact_mvp_returns():
    from backend.app.agent.tools.chart_artifact_tool import create_chart_artifact_tool

    engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    # 模拟 row 映射
    mock_row = {"detection_date": "2026-01", "defect_count": 10}
    mock_conn.execute.return_value.mappings.return_value.all.return_value = [
        mock_row
    ]
    engine.connect.return_value = mock_conn

    tool = create_chart_artifact_tool(engine)
    result = tool.invoke({
        "query": "SELECT detection_date, defect_count FROM t",
        "required_skill": "test_skill",
        "chart_type": "line",
        "title": "缺陷趋势",
        "description": "",
        "x_field": "detection_date",
        "series": [{"name": "缺陷数", "field": "defect_count"}],
    })

    # 验证返回结构为 Command
    assert isinstance(result, Command)
    assert "messages" in result.update
    assert "tool_artifact" in result.update

    # 验证流式 Payload 字段
    artifact = result.update["tool_artifact"]
    assert artifact["kind"] == "chart_spec"
    assert artifact["title"] == "缺陷趋势"
    assert "rows" in artifact

    # 验证历史回溯用 ToolMessage 格式 (必须包含旧版寻址所需的引用 JSON)
    msg = result.update["messages"][0]
    import json
    parsed_ref = json.loads(msg.content)
    assert parsed_ref["kind"] == "chart_artifact_ref"
    assert "chart_id" in parsed_ref
