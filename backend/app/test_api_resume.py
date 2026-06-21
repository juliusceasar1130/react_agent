import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import MagicMock, patch
from backend.app.api import router

app = FastAPI()
app.include_router(router)

def test_resume_endpoint_not_found():
    client = TestClient(app)
    # 发送空 JSON，由于参数不符合 ResumeChatRequest，应该返回 422
    response = client.post("/api/chat/resume", json={})
    assert response.status_code == 422

@patch("backend.app.api.crud.get_session")
@patch("backend.app.api.crud.create_message")
@patch("backend.app.api.get_agent_service")
def test_resume_endpoint_success(mock_get_agent_service, mock_create_message, mock_get_session):
    # Mock get_session 返回非空
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    
    # Mock create_message 避免外键约束报错
    mock_msg = MagicMock()
    mock_msg.id = "test-msg-id"
    mock_msg.content = "hello world"
    mock_msg.created_at = MagicMock()
    mock_msg.created_at.isoformat.return_value = "2026-06-19T21:40:00"
    mock_create_message.return_value = mock_msg
    
    # Mock get_agent_service
    mock_service = MagicMock()
    async def mock_process_stream_resume(*args, **kwargs):
        yield {"type": "token", "text": "hello"}
        yield {"type": "token", "text": " world"}
        yield {"type": "final", "content": "hello world"}
        
    mock_service.process_stream_resume = mock_process_stream_resume
    mock_get_agent_service.return_value = mock_service
    
    client = TestClient(app)
    response = client.post(
        "/api/chat/resume",
        json={"session_id": "test-session-id", "answers": {"q1": "a1"}}
    )
    
    assert response.status_code == 200
    
    # 验证流式响应内容
    lines = response.text.splitlines()
    # 过滤掉空行，检查 SSE 数据
    data_lines = [line for line in lines if line.strip()]
    
    import json
    parsed_events = []
    for line in data_lines:
        if line.startswith("data: "):
            data_str = line[len("data: "):]
            if data_str == "[DONE]":
                parsed_events.append("[DONE]")
            else:
                parsed_events.append(json.loads(data_str))
                
    assert parsed_events[-1] == "[DONE]"
    
    # 检查 token 事件
    token_events = [e for e in parsed_events if isinstance(e, dict) and e.get("type") == "token"]
    assert len(token_events) == 2
    assert token_events[0]["text"] == "hello"
    assert token_events[1]["text"] == " world"
    
    # 检查 final 事件
    final_events = [e for e in parsed_events if isinstance(e, dict) and e.get("type") == "final"]
    assert len(final_events) == 1
    assert final_events[0]["content"] == "hello world"
    assert final_events[0]["message_id"] == "test-msg-id"
    assert final_events[0]["created_at"] == "2026-06-19T21:40:00"
