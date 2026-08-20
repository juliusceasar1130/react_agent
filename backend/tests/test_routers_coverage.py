# backend/tests/test_routers_coverage.py
"""
自动化测试套件：覆盖 routers/ 各子模块核心端点与 SSE 流式契约
包含：skills, sessions, admin, artifacts, _analytics, chat (message, stream, resume, _encode_sse)
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.app.routers import router, scenarios_router
from backend.app.schemas import (
    TokenStreamEvent,
    SubagentChangeStreamEvent,
    FinalStreamEvent,
    ReasoningStreamEvent,
)
from backend.app.routers.chat import _encode_sse

# 创建用于测试的独立 FastAPI app
app = FastAPI()
app.include_router(router)
app.include_router(scenarios_router)

client = TestClient(app)


def test_encode_sse_helper():
    """测试 SSE 编码函数正确输出 data: {JSON}\n\n 格式"""
    event = TokenStreamEvent(type="token", text="你好")
    encoded = _encode_sse(event)
    assert encoded.startswith("data: ")
    assert encoded.endswith("\n\n")
    assert '"text":"你好"' in encoded or '"text": "你好"' in encoded
    assert '"type":"token"' in encoded or '"type": "token"' in encoded


def test_encode_sse_subagent_change():
    """测试 subagent_change 事件编码"""
    event = SubagentChangeStreamEvent(
        type="subagent_change",
        active_subagent="sql_domain_agent",
        display_name="SQL智能体"
    )
    encoded = _encode_sse(event)
    assert "sql_domain_agent" in encoded
    assert "subagent_change" in encoded


def test_skills_router_get():
    """测试 GET /api/chat/skills 路由"""
    mock_domain_skills = {
        "painting": {
            "name": "painting",
            "title": "涂装领域",
            "description": "涂装车间生产数据",
        }
    }
    with patch("backend.app.routers.skills.get_domain_skills", return_value=mock_domain_skills), \
         patch("backend.app.routers.skills.list_scenarios_by_skill", return_value=[]):
        resp = client.get("/api/chat/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "painting"


def test_skills_router_reload():
    """测试 POST /api/chat/skills/reload 路由"""
    with patch("backend.app.routers.skills.reload_skills", return_value=True):
        resp = client.post("/api/chat/skills/reload")
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"]


def test_sessions_router_crud():
    """测试 /api/chat/sessions CRUD 端点"""
    now = datetime.now(timezone.utc)
    mock_session = MagicMock()
    mock_session.id = "test-session-uuid-1234"
    mock_session.title = "测试会话"
    mock_session.created_at = now
    mock_session.updated_at = now
    mock_session.messages = []

    with patch("backend.app.routers.sessions.get_sessions", return_value=[mock_session]), \
         patch("backend.app.routers.sessions.get_session", return_value=mock_session), \
         patch("backend.app.routers.sessions.create_session", return_value=mock_session), \
         patch("backend.app.routers.sessions.update_session", return_value=mock_session), \
         patch("backend.app.routers.sessions.delete_session", return_value=True), \
         patch("backend.app.database.get_db"):

        # 1. List sessions
        r1 = client.get("/api/chat/sessions")
        assert r1.status_code == 200

        # 2. Create session (201 Created)
        r2 = client.post("/api/chat/sessions", json={"title": "新会话"})
        assert r2.status_code == 201

        # 3. Get single session
        r3 = client.get("/api/chat/sessions/test-session-uuid-1234")
        assert r3.status_code == 200

        # 4. Update session
        r4 = client.put("/api/chat/sessions/test-session-uuid-1234", json={})
        assert r4.status_code == 200

        # 5. Delete session
        r5 = client.delete("/api/chat/sessions/test-session-uuid-1234")
        assert r5.status_code == 200


def test_messages_feedback_endpoint():
    """测试 POST /api/chat/messages/{message_id}/feedback 端点"""
    now = datetime.now(timezone.utc)
    mock_msg = MagicMock()
    mock_msg.id = "msg-123"
    mock_msg.session_id = "sess-123"
    mock_msg.role = "assistant"
    mock_msg.content = "回答内容"
    mock_msg.feedback = "like"
    mock_msg.tool_calls = None
    mock_msg.tool_results = None
    mock_msg.tool_artifacts = None
    mock_msg.subagents = None
    mock_msg.refined_payload = None
    mock_msg.created_at = now

    with patch("backend.app.routers.sessions.crud.update_message_feedback", return_value=mock_msg), \
         patch("backend.app.database.get_db"):
        resp = client.post(
            "/api/chat/messages/msg-123/feedback",
            json={"feedback": "like"}
        )
        assert resp.status_code == 200


def test_admin_router_endpoints():
    """测试 /api/chat/admin/messages/* 路由"""
    with patch("backend.app.routers.admin.crud.get_collected_messages", return_value=[]), \
         patch("backend.app.database.get_db"):
        # 1. Pending messages
        r1 = client.get("/api/chat/admin/messages/pending")
        assert r1.status_code == 200

    # 2. Approve message 404 test
    with patch("backend.app.routers.admin.crud.get_message", return_value=None), \
         patch("backend.app.database.get_db"):
        r2 = client.post(
            "/api/chat/admin/messages/msg-123/approve",
            json={"custom_query": "查询车", "custom_sql": "SELECT 1"}
        )
        assert r2.status_code == 404


def test_artifacts_router_endpoints():
    """测试 /api/chat/artifacts/*、/api/chat/files/* 和 /api/chat/charts/* 端点"""
    with patch("backend.app.routers.artifacts.get_artifact_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.get_artifact.side_effect = FileNotFoundError("not found")
        mock_get_store.return_value = mock_store

        r1 = client.get("/api/chat/charts/non-existent-chart")
        assert r1.status_code == 404

        r2 = client.get("/api/chat/files/non-existent-file")
        assert r2.status_code == 404

    # 测试 /api/chat/artifacts/{artifact_id} 返回元数据并成功剥离 stored_path (H2)
    mock_record = MagicMock()
    mock_record.payload = {
        "kind": "chart_spec",
        "chart_id": "cht_123",
        "artifact_id": "cht_123",
        "title": "测试图表",
        "stored_path": "/sensitive/server/path/cht_123.json",
    }
    with patch("backend.app.routers.artifacts.get_artifact_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.get_artifact.return_value = mock_record
        mock_get_store.return_value = mock_store

        resp = client.get("/api/chat/artifacts/cht_123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "测试图表"
        assert "stored_path" not in data  # 验证 H2 脱敏成功


def test_analytics_dimensions_endpoint():
    """测试 GET /api/chat/dimensions/{table_name} 端点"""
    mock_settings = MagicMock()
    mock_settings.dimension_tables = ["ods_process_area"]
    with patch("backend.app.routers._analytics.settings", mock_settings):
        with patch("backend.app.routers._analytics._get_analytics_engine", return_value=None):
            resp = client.get("/api/chat/dimensions/ods_process_area")
            assert resp.status_code == 503
            assert "Analytics database is not configured" in resp.json()["detail"]


def test_chat_stream_endpoint_flow():
    """测试 POST /api/chat/stream 的流式 SSE 建立"""
    mock_session = MagicMock()
    mock_session.id = "sess-123"

    mock_msg = MagicMock()
    mock_msg.id = "msg-123"
    mock_msg.session_id = "sess-123"
    mock_msg.created_at = datetime.now(timezone.utc)
    mock_msg.content = "结果"

    async def mock_stream_loop(*args, **kwargs):
        yield {"type": "token", "text": "正在"}
        yield {"type": "final", "content": "完成"}

    with patch("backend.app.routers.chat.crud.get_session", return_value=mock_session), \
         patch("backend.app.routers.chat.crud.create_message", return_value=mock_msg), \
         patch("backend.app.routers.chat.get_agent_service") as mock_get_svc, \
         patch("backend.app.database.get_db"):
        mock_svc = MagicMock()
        mock_svc.is_ready = True
        mock_svc.process_stream = mock_stream_loop
        mock_get_svc.return_value = mock_svc

        resp = client.post(
            "/api/chat/stream",
            json={"message": "查询在制车", "session_id": "sess-123", "stream": True}
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


def test_chat_resume_endpoint():
    """测试 POST /api/chat/resume 路由"""
    mock_session = MagicMock()
    mock_session.id = "sess-123"

    mock_msg = MagicMock()
    mock_msg.id = "msg-123"
    mock_msg.created_at = datetime.now(timezone.utc)
    mock_msg.content = "澄清"
    mock_msg.role = "user"
    mock_msg.tool_calls = None

    async def mock_resume_loop(*args, **kwargs):
        yield {"type": "token", "text": "继续"}
        yield {"type": "final", "content": "恢复完成"}

    with patch("backend.app.routers.chat.crud.get_session", return_value=mock_session), \
         patch("backend.app.routers.chat.crud.get_messages_by_session", return_value=[mock_msg]), \
         patch("backend.app.routers.chat.crud.create_message", return_value=mock_msg), \
         patch("backend.app.routers.chat.get_agent_service") as mock_get_svc, \
         patch("backend.app.database.get_db"):
        mock_svc = MagicMock()
        mock_svc.is_ready = True
        mock_svc.process_stream_resume = mock_resume_loop
        mock_get_svc.return_value = mock_svc

        resp = client.post(
            "/api/chat/resume",
            json={"session_id": "sess-123", "answers": {"area": "二区"}}
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


def test_chat_stream_endpoint_with_tool_artifact_and_interrupt():
    """测试 POST /api/chat/stream 在收到 tool_artifact 及 interrupt 时的作用域与持久化"""
    mock_session = MagicMock()
    mock_session.id = "sess-123"

    mock_msg = MagicMock()
    mock_msg.id = "msg-123"
    mock_msg.session_id = "sess-123"
    mock_msg.created_at = datetime.now(timezone.utc)
    mock_msg.content = "结果"

    async def mock_stream_loop(*args, **kwargs):
        yield {
            "type": "tool_artifact",
            "artifact": {"kind": "chart_spec", "chart_id": "chart_1", "tool_call_id": "call_1"},
            "tool_call_id": "call_1",
            "subagent_id": "sub_1",
            "subagent_name": "data_agent"
        }
        yield {
            "type": "interrupt",
            "session_id": "sess-123",
            "questions": [{"question": "请确认查询范围？", "options": None}]
        }

    with patch("backend.app.routers.chat.crud.get_session", return_value=mock_session), \
         patch("backend.app.routers.chat.crud.create_message", return_value=mock_msg) as mock_create_msg, \
         patch("backend.app.routers.chat.get_agent_service") as mock_get_svc, \
         patch("backend.app.database.get_db"):
        mock_svc = MagicMock()
        mock_svc.is_ready = True
        mock_svc.process_stream = mock_stream_loop
        mock_get_svc.return_value = mock_svc

        resp = client.post(
            "/api/chat/stream",
            json={"message": "查询", "session_id": "sess-123", "stream": True}
        )
        assert resp.status_code == 200
        # 验证 create_message 被正确调用，且传入了包含工件的 tool_artifacts
        assert mock_create_msg.call_count >= 2
        last_call_args = mock_create_msg.call_args[0][1]
        assert last_call_args.tool_artifacts is not None
        assert "chart_1" in last_call_args.tool_artifacts

