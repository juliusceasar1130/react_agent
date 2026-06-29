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

def test_message_feedback_schema_and_model():
    """测试反馈相关的 Pydantic 校验和 SQLAlchemy 模型字段定义"""
    from backend.app.schemas import MessageResponse, MessageFeedbackRequest
    from backend.app.models import ChatMessage

    # 1. 验证 MessageFeedbackRequest 能够正确实例化
    req = MessageFeedbackRequest(feedback="collected")
    assert req.feedback == "collected"

    # 2. 验证 MessageResponse 支持 feedback 属性且默认值为 "none"
    res = MessageResponse(
        id="msg-1",
        role="assistant",
        content="hello",
        session_id="sess-1",
        feedback="collected",
        refined_payload='{"rewritten_query": "q"}',
        created_at=datetime.now() if "datetime" in globals() else MagicMock()
    )
    assert res.feedback == "collected"
    assert res.refined_payload == '{"rewritten_query": "q"}'

    # 3. 验证 SQLAlchemy ChatMessage 模型具备 feedback 字段定义
    msg = ChatMessage(role="assistant", content="hello", session_id="sess-1")
    assert hasattr(msg, "feedback")
    assert hasattr(msg, "refined_payload")

@patch("backend.app.crud.get_message")
def test_update_message_feedback_crud(mock_get_message):
    """测试 crud.update_message_feedback 方法"""
    from backend.app.crud import update_message_feedback
    
    mock_msg = MagicMock()
    mock_msg.feedback = "none"
    mock_get_message.return_value = mock_msg
    
    mock_db = MagicMock()
    result = update_message_feedback(mock_db, "msg-123", "like")
    
    assert result.feedback == "like"
    mock_get_message.assert_called_once_with(mock_db, "msg-123")
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(mock_msg)


@patch("backend.app.crud.get_message")
def test_update_message_refined_payload_crud(mock_get_message):
    """测试 crud.update_message_refined_payload 方法"""
    from backend.app.crud import update_message_refined_payload
    
    mock_msg = MagicMock()
    mock_msg.refined_payload = None
    mock_get_message.return_value = mock_msg
    
    mock_db = MagicMock()
    result = update_message_refined_payload(mock_db, "msg-123", '{"rewritten_query": "q"}')
    
    assert result.refined_payload == '{"rewritten_query": "q"}'
    mock_get_message.assert_called_once_with(mock_db, "msg-123")
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(mock_msg)

from datetime import datetime

@patch("backend.app.api.process_collected_message_async")
@patch("backend.app.api.crud.update_message_feedback")
def test_post_message_feedback_endpoint(mock_update_message_feedback, mock_bg_task):
    """测试 POST /api/chat/messages/{id}/feedback 接口"""
    mock_msg = MagicMock()
    mock_msg.id = "msg-123"
    mock_msg.role = "assistant"
    mock_msg.content = "hello"
    mock_msg.session_id = "sess-1"
    mock_msg.feedback = "collected"
    mock_msg.refined_payload = None
    mock_msg.tool_calls = None
    mock_msg.tool_results = None
    mock_msg.created_at = datetime.now()
    mock_update_message_feedback.return_value = mock_msg

    client = TestClient(app)
    response = client.post(
        "/api/chat/messages/msg-123/feedback",
        json={"feedback": "collected"}
    )
    assert response.status_code == 200
    assert response.json()["feedback"] == "collected"
    mock_update_message_feedback.assert_called_once()
    mock_bg_task.assert_called_once_with(message_id="msg-123")


def test_approve_message_endpoint():
    """测试管理员批准消息接口，直接读取草稿/微调数据同步落库"""
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    from backend.app.main import app
    import json
    
    # Mock 数据库查询返回带有 refined_payload 的 collected 状态消息
    mock_msg = MagicMock()
    mock_msg.id = "msg-collected-1"
    mock_msg.feedback = "collected"
    mock_msg.refined_payload = json.dumps({
        "rewritten_query": "默认提炼的问题",
        "desensitized_sql": "SELECT * FROM users",
        "domain": "general"
    })
    
    # Mock crud 中的 get_message 与 update_message_feedback
    with patch("backend.app.api.crud.get_message", return_value=mock_msg), \
         patch("backend.app.api.crud.update_message_feedback") as mock_update_feedback, \
         patch("backend.app.agent.vector.factory.add_document_to_store") as mock_add_doc:
         
        client = TestClient(app)
        response = client.post(
            "/api/chat/admin/messages/msg-collected-1/approve",
            json={"custom_query": "改写的问题", "custom_sql": "SELECT 1"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_update_feedback.assert_called_once()
        _, kwargs = mock_update_feedback.call_args
        assert kwargs["message_id"] == "msg-collected-1"
        assert kwargs["feedback"] == "approved"
        
        # 验证写入向量库的是管理员微调订正后的最终版本
        mock_add_doc.assert_called_once_with(
            text="改写的问题",
            metadata={
                "type": "sql_example",
                "sql": "SELECT 1",
                "domain": "general"
            }
        )


@patch("backend.app.crud.update_message_refined_payload")
@patch("backend.app.agent.vector.llm_refiner.refine_sql_case_with_llm")
def test_process_collected_message_async_integration(mock_refine, mock_update_payload):
    """测试异步提取、提纯并将草稿保存到数据库的流程"""
    from backend.app.api import process_collected_message_async
    from unittest.mock import MagicMock, patch
    import json
    
    # Mock 数据库查询返回目标消息
    m_target = MagicMock()
    m_target.id = "m_target"
    m_target.session_id = "sess-1"
    m_target.tool_calls = json.dumps([
        {"id": "sql-1", "name": "sql_db_query", "args": {"query": "SELECT * FROM users"}}
    ])
    m_target.tool_results = json.dumps({"sql-1": "[{'id': 1}]"})
    
    m_user = MagicMock()
    m_user.id = "m_user"
    m_user.role = "user"
    m_user.content = "查用户"
    
    # Mock 数据库拉取会话历史
    mock_history = [m_user, m_target]
    
    # Mock LLM 返回
    mock_refine.return_value = ("提炼的问题", "SELECT * FROM users")
    
    with patch("backend.app.api.crud.get_message", return_value=m_target), \
         patch("backend.app.agent.vector.rule_extractor.get_messages_by_session", return_value=mock_history), \
         patch("backend.app.api.crud.update_message_feedback") as mock_update_feedback:
         
         process_collected_message_async("m_target")
         
         # 断言 LLM 提炼被调用
         mock_refine.assert_called_once_with("查用户", "SELECT * FROM users")
         # 断言更新草稿被调用，且不调用 add_document_to_store
         mock_update_payload.assert_called_once()
         
         # 检查草稿的 json 内容
         args, kwargs = mock_update_payload.call_args
         payload_str = kwargs.get("payload") or args[2]
         payload_data = json.loads(payload_str)
         assert payload_data["rewritten_query"] == "提炼的问题"
         assert payload_data["desensitized_sql"] == "SELECT * FROM users"
         assert payload_data["domain"] == "general"
         
         # 断言没有发生状态退回
         mock_update_feedback.assert_not_called()


@patch("backend.app.api.crud.get_collected_messages")
def test_get_pending_messages_endpoint(mock_get_collected):
    """测试 GET /api/chat/admin/messages/pending 接口"""
    from datetime import datetime
    mock_msg = MagicMock()
    mock_msg.id = "msg-collected-1"
    mock_msg.role = "assistant"
    mock_msg.content = "hello"
    mock_msg.session_id = "sess-1"
    mock_msg.feedback = "collected"
    mock_msg.refined_payload = '{"rewritten_query": "q", "desensitized_sql": "s"}'
    mock_msg.tool_calls = None
    mock_msg.tool_results = None
    mock_msg.created_at = datetime.now()

    mock_get_collected.return_value = [mock_msg]

    client = TestClient(app)
    response = client.get("/api/chat/admin/messages/pending")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["feedback"] == "collected"
    assert response.json()[0]["refined_payload"] == '{"rewritten_query": "q", "desensitized_sql": "s"}'
