import pytest
from backend.app.schemas import (
    StreamToolCallPayload,
    TokenStreamEvent,
    ReasoningStreamEvent,
    ToolCallStreamEvent,
    ToolResultStreamEvent,
)
from backend.app.services.chat_service import SQLAgentService


def test_subagent_schemas_serialization():
    # 验证 TokenStreamEvent
    token_evt = TokenStreamEvent(
        type="token",
        text="SELECT * FROM users",
        subagent_id="call_123",
        subagent_name="sql_domain_agent",
    )
    dumped = token_evt.model_dump()
    assert dumped["subagent_id"] == "call_123"
    assert dumped["subagent_name"] == "sql_domain_agent"

    # 验证 ReasoningStreamEvent
    reasoning_evt = ReasoningStreamEvent(
        type="reasoning",
        text="Analyzing schema...",
        subagent_id="call_123",
        subagent_name="sql_domain_agent",
    )
    assert reasoning_evt.subagent_id == "call_123"

    # 验证 StreamToolCallPayload
    tool_payload = StreamToolCallPayload(
        id="tool_456",
        name="sql_db_query",
        args={"query": "SELECT 1"},
        status="completed",
        subagent_id="call_123",
        subagent_name="sql_domain_agent",
    )
    assert tool_payload.subagent_id == "call_123"

    # 验证 ToolCallStreamEvent
    call_evt = ToolCallStreamEvent(
        type="tool_call",
        id="tool_456",
        name="sql_db_query",
        args_text="{\"query\": \"SELECT 1\"}",
        status="started",
        subagent_id="call_123",
        subagent_name="sql_domain_agent",
    )
    assert call_evt.subagent_id == "call_123"

    # 验证 ToolResultStreamEvent
    result_evt = ToolResultStreamEvent(
        type="tool_result",
        id="tool_456",
        content="[{\"count\": 1}]",
        subagent_id="call_123",
        subagent_name="sql_domain_agent",
    )
    assert result_evt.subagent_id == "call_123"


def test_serialize_tool_calls_keeps_subagent_metadata():
    """打标后的工具聚合序列化：子智能体内部工具保留 subagent 元数据，主 Agent 工具（task 委派）不带。"""
    tool_calls = {
        "call_main_1": {
            "id": "call_main_1",
            "name": "task",
            "args": {"description": "do sql", "subagent_type": "sql_domain_agent"},
            "args_text": '{"description": "do sql", "subagent_type": "sql_domain_agent"}',
            "status": "completed",
        },
        "call_sub_1": {
            "id": "call_sub_1",
            "name": "sql_db_query",
            "args": {"query": "SELECT 1"},
            "args_text": '{"query": "SELECT 1"}',
            "status": "completed",
            "subagent_id": "call_main_1",
            "subagent_name": "sql_domain_agent",
        },
    }
    serialized = SQLAgentService._serialize_tool_calls(tool_calls, final=True)
    by_id = {item["id"]: item for item in serialized}
    assert "subagent_id" not in by_id["call_main_1"]
    assert by_id["call_sub_1"]["subagent_id"] == "call_main_1"
    assert by_id["call_sub_1"]["subagent_name"] == "sql_domain_agent"


def test_status_signature_distinguishes_subagent():
    """状态签名纳入 subagent 维度，避免主子同文案状态互相去重。"""
    base = {"stage": "thinking", "text": "正在分析问题", "source": "agent"}
    main_sig = SQLAgentService._status_signature({**base})
    sub_sig = SQLAgentService._status_signature({**base, "subagent_id": "call_1"})
    assert main_sig != sub_sig
    # 同一 subagent 的同文案状态签名应稳定相等（可去重）
    assert SQLAgentService._status_signature({**base, "subagent_id": "call_1"}) == sub_sig
