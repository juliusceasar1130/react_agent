# backend/app/crud.py
import re
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .models import ChatSession, ChatMessage
from .schemas import SessionCreate, SessionUpdate, MessageCreate


DEFAULT_SESSION_TITLE = "新对话"
LEGACY_PLACEHOLDER_TITLES = {"新会话"}
SESSION_TITLE_MAX_LENGTH = 30


def _is_placeholder_session_title(title: Optional[str]) -> bool:
    normalized_title = (title or "").strip()
    return not normalized_title or normalized_title in {
        DEFAULT_SESSION_TITLE,
        *LEGACY_PLACEHOLDER_TITLES,
    }


def _build_session_title_from_message(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if not normalized:
        return DEFAULT_SESSION_TITLE

    if len(normalized) <= SESSION_TITLE_MAX_LENGTH:
        return normalized

    return f"{normalized[:SESSION_TITLE_MAX_LENGTH - 3].rstrip()}..."


# ==================== Session CRUD ====================


def create_session(db: Session, session: SessionCreate) -> ChatSession:
    """创建新会话"""
    # 设置默认标题
    title = session.title if session.title else DEFAULT_SESSION_TITLE
    db_session = ChatSession(title=title)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    # 返回会话
    return db_session


def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
    """根据ID获取会话"""
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_sessions(db: Session) -> List[ChatSession]:
    """获取所有会话"""
    return db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()


def update_session(
    db: Session, session_id: str, session_update: SessionUpdate
) -> Optional[ChatSession]:
    """更新会话（只更新提供的非 None 字段）"""
    db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if db_session:
        # 过滤 None 值，只更新提供的字段
        update_data = session_update.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            setattr(db_session, field, value)
        db_session.updated_at = datetime.now()
        db.commit()
        db.refresh(db_session)
    return db_session


def delete_session(db: Session, session_id: str) -> bool:
    """删除会话（级联删除关联的消息）"""
    db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if db_session:
        db.delete(db_session)
        db.commit()
        return True
    return False


# ==================== Message CRUD ====================


def create_message(db: Session, message: MessageCreate) -> ChatMessage:
    """创建新消息"""
    # 复用 get_session 检查会话是否存在
    db_session = get_session(db, message.session_id)
    if not db_session:
        raise ValueError(f"会话 {message.session_id} 不存在")

    # 创建消息
    db_message = ChatMessage(
        role=message.role,
        content=message.content,
        session_id=message.session_id,
        tool_calls=message.tool_calls,
        tool_results=message.tool_results,
        subagents=message.subagents,
    )
    db.add(db_message)

    if message.role == "user" and _is_placeholder_session_title(db_session.title):
        existing_user_message = (
            db.query(ChatMessage.id)
            .filter(
                ChatMessage.session_id == message.session_id,
                ChatMessage.role == "user",
            )
            .first()
        )
        if existing_user_message is None:
            db_session.title = _build_session_title_from_message(message.content)

    # 更新会话的 updated_at 时间
    db_session.updated_at = datetime.now()
    db.commit()
    db.refresh(db_message)

    return db_message


def get_message(db: Session, message_id: str) -> Optional[ChatMessage]:
    """根据ID获取消息"""
    return db.query(ChatMessage).filter(ChatMessage.id == message_id).first()


def update_message_feedback(db: Session, message_id: str, feedback: str) -> Optional[ChatMessage]:
    """更新指定消息的反馈状态"""
    db_message = get_message(db, message_id)
    if db_message:
        db_message.feedback = feedback
        db.commit()
        db.refresh(db_message)
    return db_message


def update_message_refined_payload(db: Session, message_id: str, payload: str) -> Optional[ChatMessage]:
    """更新指定消息的提纯草稿数据"""
    db_message = get_message(db, message_id)
    if db_message:
        db_message.refined_payload = payload
        db.commit()
        db.refresh(db_message)
    return db_message


def get_messages_by_session(db: Session, session_id: str) -> List[ChatMessage]:
    """获取指定会话的所有消息"""
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def delete_message(db: Session, message_id: str) -> bool:
    """删除消息"""
    db_message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if db_message:
        db.delete(db_message)
        db.commit()
        return True
    return False


def delete_messages_by_session(db: Session, session_id: str) -> int:
    """删除指定会话的所有消息"""
    deleted_count = (
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    )
    db.commit()
    return deleted_count


def get_collected_messages(db: Session) -> List[ChatMessage]:
    """获取所有标记为 collected 待审核状态的消息，按创建时间倒序"""
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.feedback == "collected")
        .order_by(ChatMessage.created_at.desc())
        .all()
    )
