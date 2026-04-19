from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from backend.app.services import SQLAgentService


class _StubAgent:
    async def astream(self, *_args, **_kwargs):
        yield (
            "updates",
            {
                "model": {
                    "messages": [AIMessage(content="answer")],
                }
            },
        )


class _StubAgentWithWarning:
    async def astream(self, *_args, **_kwargs):
        yield (
            "custom",
            {
                "type": "status",
                "stage": "thinking",
                "text": "当前上下文已接近安全阈值，建议新建对话",
                "source": "context_warning",
                "detail": {
                    "estimated_input_tokens": 320,
                    "warn_tokens": 200,
                    "context_window": 500,
                    "output_reserve": 4000,
                    "safety_buffer": 100,
                    "message_count": 5,
                    "tool_count": 2,
                    "recommended_action": "start_new_session",
                    "source": "context_warning",
                },
            },
        )
        yield (
            "updates",
            {
                "model": {
                    "context_warning": {
                        "estimated_input_tokens": 320,
                        "warn_tokens": 200,
                        "context_window": 500,
                        "output_reserve": 4000,
                        "safety_buffer": 100,
                        "message_count": 5,
                        "tool_count": 2,
                        "recommended_action": "start_new_session",
                        "source": "context_warning",
                    },
                    "messages": [AIMessage(content="answer")],
                }
            },
        )


@pytest.mark.asyncio
async def test_process_stream_emits_final_event_without_context_warning() -> None:
    service = SQLAgentService(
        SimpleNamespace(
            agent=_StubAgent(),
            checkpointer=None,
            conn_pool=None,
        )
    )

    events = [event async for event in service.process_stream("hello", "s1")]

    assert not any(event["type"] == "error" for event in events)
    assert events[-1]["type"] == "final"
    assert events[-1]["content"] == "answer"


@pytest.mark.asyncio
async def test_process_stream_passthrough_custom_context_warning_status() -> None:
    service = SQLAgentService(
        SimpleNamespace(
            agent=_StubAgentWithWarning(),
            checkpointer=None,
            conn_pool=None,
        )
    )

    events = [event async for event in service.process_stream("hello", "s1")]

    warning_events = [
        event
        for event in events
        if event["type"] == "status" and event.get("source") == "context_warning"
    ]
    assert len(warning_events) == 1
    assert warning_events[0]["detail"]["estimated_input_tokens"] == 320
    assert events[-1]["type"] == "final"
    assert events[-1]["context_warning"]["estimated_input_tokens"] == 320
