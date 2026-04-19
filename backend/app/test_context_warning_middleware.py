from __future__ import annotations

from unittest.mock import MagicMock

from langchain.agents.middleware import (
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command

from backend.app.agent.middleware.context_warning_middleware import (
    ContextWarningMiddleware,
)


class FakeEstimator:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def count_json_like_tokens(self, value: object) -> int:
        self.calls.append(value)
        return self._count(value)

    def _count(self, value: object) -> int:
        if isinstance(value, str):
            if value == "SYS":
                return 40
            if value == "MSG":
                return 50
            if value == "TOOL":
                return 20
            return 0

        if isinstance(value, dict):
            return sum(self._count(item) for item in value.values())

        if isinstance(value, list):
            return sum(self._count(item) for item in value)

        return 0


def _make_request(
    *,
    system_message: SystemMessage | None,
    messages: list[object],
    tools: list[object] | None = None,
) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        system_message=system_message,
        tools=tools or [],
        state={"messages": []},
    )


def test_enabled_false_skips_warning_and_estimator_calls() -> None:
    estimator = FakeEstimator()
    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=False,
        context_window=1000,
        warn_tokens=800,
        output_reserve=200,
        safety_buffer=100,
    )
    request = _make_request(
        system_message=SystemMessage(content="SYS"),
        messages=[HumanMessage(content="MSG")],
        tools=[{"name": "TOOL"}],
    )

    response = middleware.wrap_model_call(request, lambda modified: ModelResponse(result=[]))

    assert isinstance(response, ExtendedModelResponse)
    assert isinstance(response.command, Command)
    assert response.command.update == {"context_warning": None}
    assert estimator.calls == []


def test_warning_payload_is_generated_when_threshold_is_reached() -> None:
    estimator = FakeEstimator()
    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=True,
        context_window=1000,
        warn_tokens=100,
        output_reserve=200,
        safety_buffer=100,
    )
    request = _make_request(
        system_message=SystemMessage(content="SYS"),
        messages=[HumanMessage(content="MSG")],
        tools=[{"name": "TOOL"}],
    )
    response = middleware.wrap_model_call(request, lambda modified: ModelResponse(result=[]))

    assert isinstance(response, ExtendedModelResponse)
    assert isinstance(response.command, Command)
    warning = response.command.update["context_warning"]
    assert warning is not None
    assert warning["estimated_input_tokens"] == 210
    assert warning["warn_tokens"] == 100
    assert warning["context_window"] == 1000
    assert warning["output_reserve"] == 200
    assert warning["safety_buffer"] == 100
    assert warning["message_count"] == 1
    assert warning["tool_count"] == 1
    assert warning["recommended_action"] == "start_new_session"
    assert warning["source"] == "context_warning"


def test_warning_payload_is_not_generated_below_threshold() -> None:
    estimator = FakeEstimator()
    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=True,
        context_window=1000,
        warn_tokens=200,
        output_reserve=200,
        safety_buffer=100,
    )
    request = _make_request(
        system_message=SystemMessage(content="SYS"),
        messages=[HumanMessage(content="MSG")],
        tools=[],
    )

    warning = middleware._build_warning_payload(request)

    assert warning == (None, 190)


def test_wrap_model_call_clears_warning_when_threshold_not_reached() -> None:
    estimator = FakeEstimator()
    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=True,
        context_window=1000,
        warn_tokens=200,
        output_reserve=200,
        safety_buffer=100,
    )
    request = _make_request(
        system_message=SystemMessage(content="SYS"),
        messages=[HumanMessage(content="MSG")],
        tools=[],
    )

    response = middleware.wrap_model_call(request, lambda modified: ModelResponse(result=[]))

    assert isinstance(response, ExtendedModelResponse)
    assert isinstance(response.command, Command)
    assert response.command.update == {"context_warning": None}


def test_warning_payload_handles_missing_system_message() -> None:
    estimator = FakeEstimator()
    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=True,
        context_window=1000,
        warn_tokens=120,
        output_reserve=200,
        safety_buffer=100,
    )
    request = _make_request(
        system_message=None,
        messages=[HumanMessage(content="MSG")],
        tools=[],
    )

    warning = middleware._build_warning_payload(request)

    assert warning[0] is not None
    assert warning[0]["estimated_input_tokens"] == 150
    assert warning[0]["message_count"] == 1
    assert warning[0]["tool_count"] == 0


def test_warning_emits_stream_status_and_logs_when_triggered(monkeypatch, caplog) -> None:
    estimator = FakeEstimator()
    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=True,
        context_window=500,
        warn_tokens=100,
        output_reserve=200,
        safety_buffer=100,
    )
    request = _make_request(
        system_message=SystemMessage(content="SYS"),
        messages=[HumanMessage(content="MSG")],
        tools=[{"name": "TOOL"}],
    )
    emitted_events: list[dict] = []
    monkeypatch.setattr(
        "backend.app.agent.middleware.context_warning_middleware.emit_stream_status",
        lambda text, *, stage, source=None, detail=None: emitted_events.append(
            {
                "text": text,
                "stage": stage,
                "source": source,
                "detail": detail,
            }
        ),
    )

    with caplog.at_level("INFO"):
        middleware.wrap_model_call(request, lambda modified: ModelResponse(result=[]))

    assert emitted_events
    assert emitted_events[0]["source"] == "context_warning"
    assert emitted_events[0]["detail"]["estimated_input_tokens"] == 210
    assert any("context warning check:" in record.message for record in caplog.records)
