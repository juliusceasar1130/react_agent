# backend/app/api.py
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Any, List

logger = logging.getLogger(__name__)

from .database import get_db
from .crud import (
    # Session CRUD
    create_session,
    get_session,
    get_sessions,
    update_session,
    delete_session,
    # Message CRUD
    create_message,
    get_message,
    get_messages_by_session,
    delete_message,
    delete_messages_by_session,
)
from .schemas import (
    # Session Schemas
    ChatRequest,
    ChatResponse,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    # Message Schemas
    MessageCreate,
    MessageResponse,
)
from . import crud

from .services import get_agent_service  # FastAPI 兼容层，内部复用 Agent V2 核心服务

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _encode_sse(event: Any) -> str:
    """编码 SSE data 行。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ==================== Session API ====================


@router.post(
    "/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED
)
def create_session_endpoint(session: SessionCreate, db: Session = Depends(get_db)):
    """创建新会话"""
    db_session = create_session(db, session)
    # 添加消息数量 - 2025-01-01
    return {
        "id": db_session.id,
        "title": db_session.title,
        "created_at": db_session.created_at,
        "updated_at": db_session.updated_at,
        "message_count": 0,
        "messages": []
    }


@router.get("/sessions", response_model=List[SessionResponse])
def get_sessions_endpoint(db: Session = Depends(get_db)):
    """获取所有会话"""
    sessions = get_sessions(db)
    # 添加消息数量 - 2025-01-01
    result = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": len(session.messages),
            "messages": []
        }
        result.append(session_dict)
    return result


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """根据ID获取会话"""
    db_session = get_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    # 添加消息数量 - 2025-01-01
    return {
        "id": db_session.id,
        "title": db_session.title,
        "created_at": db_session.created_at,
        "updated_at": db_session.updated_at,
        "message_count": len(db_session.messages),
        "messages": []
    }


@router.put("/sessions/{session_id}", response_model=SessionResponse)
def update_session_endpoint(
    session_id: str, session_update: SessionUpdate, db: Session = Depends(get_db)
):
    """更新会话"""
    db_session = update_session(db, session_id, session_update)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    # 添加消息数量 - 2025-01-01
    return {
        "id": db_session.id,
        "title": db_session.title,
        "created_at": db_session.created_at,
        "updated_at": db_session.updated_at,
        "message_count": len(db_session.messages),
        "messages": []
    }


@router.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """删除会话（级联删除关联的消息）"""
    success = delete_session(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return {"message": f"会话 {session_id} 已删除"}


# ==================== Message API ====================


@router.post(
    "/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
def create_message_endpoint(message: MessageCreate, db: Session = Depends(get_db)):
    """创建新消息"""
    try:
        db_message = create_message(db, message)
        return db_message
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/messages/{message_id}", response_model=MessageResponse)
def get_message_endpoint(message_id: str, db: Session = Depends(get_db)):
    """根据ID获取消息"""
    db_message = get_message(db, message_id)
    if not db_message:
        raise HTTPException(status_code=404, detail=f"消息 {message_id} 不存在")
    return db_message


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_messages_by_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """获取指定会话的所有消息"""
    # 检查会话是否存在
    db_session = get_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")

    messages = get_messages_by_session(db, session_id)
    return messages


@router.delete("/messages/{message_id}")
def delete_message_endpoint(message_id: str, db: Session = Depends(get_db)):
    """删除消息"""
    success = delete_message(db, message_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"消息 {message_id} 不存在")
    return {"message": f"消息 {message_id} 已删除"}


# ====================== 消息处理 ======================


@router.post("/message", response_model=ChatResponse)
async def send_message(chat_request: ChatRequest, db: Session = Depends(get_db)):
    """发送消息（非流式）

    修改时间: 2025-01-03
    修改内容: 使用 PostgresSaver 自动管理历史，删除手动历史加载逻辑
    """
    logger.info("api.py - send_message - 用户发送非流式消息")
    logger.info(f"ChatRequest: {chat_request}")

    if chat_request.stream:
        raise HTTPException(
            status_code=400, detail="Use /stream endpoint for streaming"
        )

    session_id = chat_request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id不能为空")

    # ✅ 删除手动历史加载逻辑（PostgresSaver 自动管理）

    # 保存用户消息
    logger.info("保存用户消息到数据库")
    user_message = crud.create_message(
        db,
        MessageCreate(session_id=session_id, role="user", content=chat_request.message),
    )

    # ✅ 构建 config（thread_id 对应 session_id）
    config = {"configurable": {"thread_id": str(session_id)}}
    agent_service = get_agent_service()

    # 使用Agent处理消息
    logger.info("调用Agent处理消息（PostgresSaver 自动管理历史）")
    agent_response = await agent_service.process_message(
        chat_request.message,
        session_id,
        config
    )

    # 保存Assistant消息
    logger.info("保存Assistant消息到数据库")
    assistant_message = crud.create_message(
        db,
        MessageCreate(
            session_id=session_id,
            role="assistant",
            content=agent_response["content"],
            tool_calls=agent_response["tool_calls"],
            tool_results=agent_response["tool_results"],
        ),
    )
    logger.info("Assistant消息保存完成")
    return ChatResponse(
        session_id=session_id, message=assistant_message, is_complete=True
    )


@router.post("/stream")
async def stream_message_post(chat_request: ChatRequest, db: Session = Depends(get_db)):
    """流式发送消息（POST方法）- 真正的流式处理

    修改时间: 2026-03-27 17:30 Asia/Shanghai
    修改内容:
    - 升级为结构化流式事件透传协议
    - 在 final/error 路径统一处理 assistant 消息落库
    - 保留 [DONE] 作为传输层结束标记，但不再作为业务成功判断依据
    """
    logger.info("Received streaming chat request via POST")
    logger.info(f"ChatRequest: {chat_request}")

    if not chat_request.message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    session_id = chat_request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id不能为空")

    # 检查会话是否存在
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 保存用户消息
    user_message = crud.create_message(
        db,
        MessageCreate(session_id=session_id, role="user", content=chat_request.message),
    )
    agent_service = get_agent_service()

    # ✅ 删除手动历史加载逻辑（PostgresSaver 自动管理）

    async def generate():
        logger.info("Starting real stream generation")
        logger.info(f"消息: {chat_request.message}")
        logger.info(f"会话ID: {session_id}")

        try:
            # ✅ 构建 config（thread_id 对应 session_id）
            config = {"configurable": {"thread_id": str(session_id)}}

            full_content = ""
            tool_calls_map: dict[str, dict[str, Any]] = {}
            tool_results_data: dict[str, Any] = {}
            assistant_persisted = False

            logger.info("开始调用agent_service.process_stream...")

            async for event in agent_service.process_stream(
                chat_request.message,
                session_id,
                config
            ):
                event_type = event.get("type")

                if event_type == "token":
                    token_text = event.get("text", "")
                    if token_text:
                        full_content += token_text

                elif event_type == "tool_call":
                    tool_id = event.get("id")
                    if tool_id:
                        tool_calls_map[tool_id] = {
                            "id": tool_id,
                            "name": event.get("name", ""),
                            "args_text": event.get("args_text", ""),
                            "status": event.get("status", "streaming"),
                        }

                elif event_type == "tool_result":
                    tool_id = event.get("id")
                    if tool_id and event.get("content") is not None:
                        tool_results_data[tool_id] = event.get("content")

                elif event_type == "final":
                    final_content = event.get("content") or full_content
                    if final_content:
                        full_content = final_content

                    final_tool_calls = event.get("tool_calls") or list(tool_calls_map.values()) or None
                    final_tool_results = event.get("tool_results") or tool_results_data or None
                    logger.info(
                        "收到最终事件，tool_calls=%d, tool_results=%d",
                        len(final_tool_calls or []),
                        len(final_tool_results or {}),
                    )

                    assistant_message = crud.create_message(
                        db,
                        MessageCreate(
                            session_id=session_id,
                            role="assistant",
                            content=full_content or "回答完成，但未生成可展示的文本内容。",
                            tool_calls=(
                                json.dumps(final_tool_calls, ensure_ascii=False)
                                if final_tool_calls
                                else None
                            ),
                            tool_results=(
                                json.dumps(final_tool_results, ensure_ascii=False)
                                if final_tool_results
                                else None
                            ),
                        ),
                    )
                    assistant_persisted = True
                    logger.info("Assistant消息保存成功，ID: %s", assistant_message.id)

                    final_event = {
                        **event,
                        "content": assistant_message.content,
                        "tool_calls": final_tool_calls,
                        "tool_results": final_tool_results,
                        "message_id": assistant_message.id,
                        "created_at": assistant_message.created_at.isoformat(),
                    }
                    yield _encode_sse(final_event)
                    continue

                elif event_type == "error":
                    error_message = event.get("message") or "流式处理失败"
                    if not assistant_persisted:
                        assistant_message = crud.create_message(
                            db,
                            MessageCreate(
                                session_id=session_id,
                                role="assistant",
                                content=error_message,
                            ),
                        )
                        assistant_persisted = True
                        event = {
                            **event,
                            "message_id": assistant_message.id,
                            "created_at": assistant_message.created_at.isoformat(),
                        }

                yield _encode_sse(event)

        except Exception as e:
            logger.error(f"流式处理异常: {e}", exc_info=True)
            assistant_message = crud.create_message(
                db,
                MessageCreate(
                    session_id=session_id,
                    role="assistant",
                    content=f"错误: {str(e)}",
                ),
            )
            error_data = {
                "type": "error",
                "message": f"错误: {str(e)}",
                "retryable": False,
                "message_id": assistant_message.id,
                "created_at": assistant_message.created_at.isoformat(),
            }
            yield _encode_sse(error_data)
        finally:
            # 确保发送结束标记
            yield "data: [DONE]\n\n"
            logger.info("流式响应结束")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
