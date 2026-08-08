# backend/tests/agent/test_sse_reasoning_events.py
import pytest
from pydantic import TypeAdapter
from backend.app.schemas import ReasoningStreamEvent, ChatStreamEvent

def test_reasoning_stream_event_schema():
    event = ReasoningStreamEvent(text="正在分析SQL...", node="agent")
    assert event.type == "reasoning"
    assert event.text == "正在分析SQL..."
    assert event.node == "agent"

def test_chat_stream_event_union_discriminates_reasoning():
    adapter = TypeAdapter(ChatStreamEvent)
    data = {"type": "reasoning", "text": "正在推理...", "node": "agent"}
    parsed = adapter.validate_python(data)
    assert isinstance(parsed, ReasoningStreamEvent)
    assert parsed.text == "正在推理..."


def test_extract_reasoning_content_from_message_chunk():
    from langchain_core.messages import AIMessageChunk
    chunk = AIMessageChunk(content="", additional_kwargs={"reasoning_content": "思考：发现表ods.process_areas"})
    reasoning_text = chunk.additional_kwargs.get("reasoning_content")
    assert reasoning_text == "思考：发现表ods.process_areas"
