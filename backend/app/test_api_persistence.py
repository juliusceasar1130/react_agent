import pytest
import json
import asyncio
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import MagicMock, patch
from backend.app.api import router

app = FastAPI()
app.include_router(router)

@patch("backend.app.api.crud.get_session")
@patch("backend.app.api.crud.create_message")
@patch("backend.app.api.get_agent_service")
def test_stream_interrupt_saves_clarification(mock_get_agent_service, mock_create_message, mock_get_session):
    """测试当流式响应遇到中断时，正确将澄清提问保存为 assistant 消息"""
    # 模拟会话存在
    mock_get_session.return_value = MagicMock()
    
    # 模拟消息返回对象
    mock_msg = MagicMock()
    mock_msg.id = "clarify-msg-id"
    mock_msg.created_at = MagicMock()
    mock_msg.created_at.isoformat.return_value = "2026-06-28T12:00:00"
    mock_create_message.return_value = mock_msg

    # 模拟 Agent Stream 产生 interrupt 事件
    mock_service = MagicMock()
    async def mock_process_stream(*args, **kwargs):
        yield {
            "type": "tool_call",
            "id": "tool_load_skill",
            "name": "load_skill",
            "args_text": '{"skill": "paint_shop_defect_analysis"}',
            "status": "completed"
        }
        yield {
            "type": "tool_result",
            "id": "tool_load_skill",
            "content": "skill loaded successfully"
        }
        yield {
            "type": "interrupt",
            "questions": [
                {
                    "question": "确认产线？",
                    "header": "参数确认",
                    "multiSelect": False,
                    "options": [
                        {"label": "一产线", "description": ""},
                        {"label": "二产线", "description": ""}
                    ]
                }
            ],
            "session_id": "test-sess-1"
        }
    mock_service.process_stream = mock_process_stream
    mock_get_agent_service.return_value = mock_service

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"message": "出了多少车？", "session_id": "test-sess-1", "stream": True}
    )
    assert response.status_code == 200
    
    # 校验是否保存了澄清消息到数据库
    # 期望在 crud.create_message 中传入 MessageCreate，其 role="assistant" 且含有 tool_calls
    called_args = [args[0][1] for args in mock_create_message.call_args_list]
    # 校验是否有 assistant 消息创建
    assistant_creates = [c for c in called_args if c.role == "assistant"]
    assert len(assistant_creates) == 1
    assert "AskUserQuestion" in assistant_creates[0].tool_calls
    assert "load_skill" in assistant_creates[0].tool_calls
    assert "tool_load_skill" in assistant_creates[0].tool_results
    assert "skill loaded successfully" in assistant_creates[0].tool_results
    assert "确认产线？" in assistant_creates[0].content

@patch("backend.app.api.crud.get_messages_by_session")
@patch("backend.app.api.crud.get_session")
@patch("backend.app.api.crud.create_message")
@patch("backend.app.api.get_agent_service")
def test_resume_saves_user_answers(mock_get_agent_service, mock_create_message, mock_get_session, mock_get_messages_by_session):
    """测试恢复挂起流时，正确将用户的回答保存为 user 消息"""
    mock_get_session.return_value = MagicMock()
    
    # 模拟历史澄清消息，以便提取 AskUserQuestion 的 tool_call_id
    mock_prev_msg = MagicMock()
    mock_prev_msg.role = "assistant"
    mock_prev_msg.tool_calls = json.dumps([{"id": "ask_user_call_1", "name": "AskUserQuestion"}])
    mock_get_messages_by_session.return_value = [mock_prev_msg]
    
    mock_msg = MagicMock()
    mock_msg.id = "resume-msg-id"
    mock_msg.content = "最终结果"
    mock_msg.created_at = MagicMock()
    mock_msg.created_at.isoformat.return_value = "2026-06-28T12:05:00"
    mock_create_message.return_value = mock_msg

    mock_service = MagicMock()
    async def mock_process_stream_resume(*args, **kwargs):
        yield {"type": "final", "content": "最终结果"}
    mock_service.process_stream_resume = mock_process_stream_resume
    mock_get_agent_service.return_value = mock_service

    client = TestClient(app)
    response = client.post(
        "/api/chat/resume",
        json={"session_id": "test-sess-1", "answers": {"q1": "a1"}}
    )
    assert response.status_code == 200

    # 检查所有的消息保存调用
    called_args = [args[0][1] for args in mock_create_message.call_args_list]
    user_creates = [c for c in called_args if c.role == "user"]
    
    # 必须保存了用户的回答消息
    assert len(user_creates) == 1
    assert "q1: a1" in user_creates[0].content
    # 必须以 AskUserQuestion 的 tool_call_id 作为键名序列化保存
    assert "ask_user_call_1" in user_creates[0].tool_results
    assert "q1" in user_creates[0].tool_results

@patch("backend.app.api.crud.get_session")
@patch("backend.app.api.crud.create_message")
@patch("backend.app.api.get_agent_service")
def test_stream_disconnect_saves_partial_content(mock_get_agent_service, mock_create_message, mock_get_session):
    """测试当流式链接中途断开时，正确将部分生成内容与已调工具保存"""
    mock_get_session.return_value = MagicMock()
    
    mock_msg = MagicMock()
    mock_msg.id = "partial-msg-id"
    mock_msg.content = "SELECT * FROM"
    mock_msg.tool_calls = json.dumps([{"id": "tool_0", "name": "sql_db_query"}])
    mock_msg.created_at = MagicMock()
    mock_msg.created_at.isoformat.return_value = "2026-06-28T12:00:00"
    mock_create_message.return_value = mock_msg

    # 模拟流式生成：产生一个 token 和工具调用后模拟断开
    mock_service = MagicMock()
    async def mock_process_stream(*args, **kwargs):
        yield {"type": "token", "text": "SELECT * FROM"}
        yield {"type": "tool_call", "id": "tool_0", "name": "sql_db_query", "args_text": "SELECT 1", "status": "started"}
        await asyncio.sleep(1.0)
        
    mock_service.process_stream = mock_process_stream
    mock_get_agent_service.return_value = mock_service

    # 通过 mock request.is_disconnected() 为 True 来模拟客户端断开
    with patch("backend.app.api.Request.is_disconnected", return_value=True):
        client = TestClient(app)
        response = client.post(
            "/api/chat/stream",
            json={"message": "查询数据", "session_id": "test-sess-1", "stream": True}
        )
    
    # 校验是否保存了部分回答消息
    called_args = [args[0][1] for args in mock_create_message.call_args_list]
    assistant_creates = [c for c in called_args if c.role == "assistant"]
    assert len(assistant_creates) == 1
    assert assistant_creates[0].content == "SELECT * FROM"
    assert "sql_db_query" in assistant_creates[0].tool_calls

@patch("backend.app.api.crud.get_session")
@patch("backend.app.api.crud.create_message")
@patch("backend.app.api.get_agent_service")
def test_non_stream_exception_saves_error_message(mock_get_agent_service, mock_create_message, mock_get_session):
    """测试非流式请求发生报错时，将 Error 消息正确写入数据库"""
    mock_get_session.return_value = MagicMock()
    
    mock_msg = MagicMock()
    mock_msg.id = "error-msg-id"
    mock_msg.content = "错误: Database Timeout"
    mock_msg.created_at = MagicMock()
    mock_msg.created_at.isoformat.return_value = "2026-06-28T12:10:00"
    mock_create_message.return_value = mock_msg
    
    # 模拟 agent_service 报错
    mock_service = MagicMock()
    mock_service.process_message.side_effect = Exception("Database Timeout")
    mock_get_agent_service.return_value = mock_service
    
    client = TestClient(app)
    response = client.post(
        "/api/chat/message",
        json={"message": "查询数据", "session_id": "test-sess-1"}
    )
    assert response.status_code == 500
    
    # 校验是否保存了报错消息
    called_args = [args[0][1] for args in mock_create_message.call_args_list]
    error_creates = [c for c in called_args if c.role == "assistant" and "错误: Database Timeout" in c.content]
    assert len(error_creates) == 1
