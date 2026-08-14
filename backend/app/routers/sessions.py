import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app import crud
from backend.app.crud import (
    create_session,
    get_session,
    get_sessions,
    update_session,
    delete_session,
    create_message,
    get_message,
    get_messages_by_session,
    delete_message,
)
from backend.app.schemas import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    MessageCreate,
    MessageResponse,
    MessageFeedbackRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED
)
def create_session_endpoint(session: SessionCreate, db: Session = Depends(get_db)):
    """创建新会话"""
    db_session = create_session(db, session)
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


@router.post("/messages/{message_id}/feedback", response_model=MessageResponse)
def update_message_feedback_endpoint(
    message_id: str,
    feedback_request: MessageFeedbackRequest,
    bg_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """更新消息的用户反馈状态"""
    db_message = crud.update_message_feedback(db, message_id, feedback_request.feedback)
    if not db_message:
        raise HTTPException(status_code=404, detail=f"消息 {message_id} 不存在")
        
    if feedback_request.feedback == "collected":
        from backend.app.routers.admin import process_collected_message_async
        bg_tasks.add_task(process_collected_message_async, message_id=message_id)
        
    return db_message
