import asyncio
import shutil
from types import SimpleNamespace
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import router, send_message
from backend.app.chart_artifacts import create_chart_record
from backend.app.config import settings
from backend.app.schemas import ChatRequest, ChatResponse


@pytest.fixture()
def chart_api_tmp_dir(monkeypatch):
    tmp_path = Path.cwd() / f".tmp_chart_api_{uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    monkeypatch.setattr(settings, "chart_artifact_dir", str(tmp_path))
    monkeypatch.setattr(settings, "chart_artifact_ttl_hours", 24)
    try:
        yield tmp_path
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def chart_record(chart_api_tmp_dir: Path):
    return create_chart_record(
        payload={
            "kind": "chart_spec",
            "chart_type": "line",
            "title": "demo",
            "description": "demo",
            "x_field": "stat_date",
            "series": [{"name": "count", "field": "detection_count", "y_axis": "left"}],
            "rows": [{"stat_date": "2026-04-01", "detection_count": 1}],
        }
    )


def test_get_chart_endpoint_returns_chart_payload(
    client: TestClient,
    chart_record: dict,
) -> None:
    response = client.get(f"/api/chat/charts/{chart_record['chart_id']}")
    assert response.status_code == 200
    assert response.json()["kind"] == "chart_spec"
    assert response.json()["chart_id"] == chart_record["chart_id"]


def test_chat_response_accepts_context_warning() -> None:
    payload = ChatResponse.model_validate(
        {
            "session_id": "s1",
            "message": {
                "id": "m1",
                "role": "assistant",
                "content": "ok",
                "session_id": "s1",
                "created_at": "2026-04-19T00:00:00",
            },
            "is_complete": True,
            "context_warning": {
                "estimated_input_tokens": 12001,
                "warn_tokens": 12000,
                "context_window": 16384,
                "output_reserve": 2000,
                "safety_buffer": 512,
                "message_count": 8,
                "tool_count": 2,
                "recommended_action": "start_new_session",
                "source": "context_warning",
            },
        }
    )
    assert payload.context_warning is not None


def test_send_message_returns_context_warning(monkeypatch) -> None:
    user_message = SimpleNamespace(
        id="user-1",
        role="user",
        content="hello",
        session_id="s1",
        created_at="2026-04-19T00:00:00",
        tool_calls=None,
        tool_results=None,
    )
    assistant_message = SimpleNamespace(
        id="assistant-1",
        role="assistant",
        content="ok",
        session_id="s1",
        created_at="2026-04-19T00:00:01",
        tool_calls=None,
        tool_results=None,
    )
    created_messages = iter([user_message, assistant_message])
    context_warning = {
        "estimated_input_tokens": 12001,
        "warn_tokens": 12000,
        "context_window": 16384,
        "output_reserve": 2000,
        "safety_buffer": 512,
        "message_count": 8,
        "tool_count": 2,
        "recommended_action": "start_new_session",
        "source": "context_warning",
    }

    async def _process_message(*_args, **_kwargs):
        return {
            "content": "ok",
            "tool_calls": None,
            "tool_results": None,
            "context_warning": context_warning,
        }

    monkeypatch.setattr("backend.app.api.crud.create_message", lambda *_args, **_kwargs: next(created_messages))
    monkeypatch.setattr(
        "backend.app.api.get_agent_service",
        lambda: SimpleNamespace(process_message=_process_message),
    )

    payload = ChatRequest(message="hello", session_id="s1", stream=False)
    response = asyncio.run(send_message(payload, db=object()))

    assert response.context_warning is not None
    assert response.context_warning.estimated_input_tokens == 12001
