from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import DateTime
from sqlalchemy import func
import uuid


def generate_uuid():
    return str(uuid.uuid4())


Base = declarative_base()


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String(36), primary_key=True, index=True, default=generate_uuid)
    title = Column(String(255), nullable=False, default="新会话")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # 定义一对多的关系
    messages = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, index=True, default=generate_uuid)
    session_id = Column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        String(50), nullable=False
    )  # e.g., 'user' or 'assistant' 'system' ''tool'
    content = Column(String, nullable=False)
    tool_calls = Column(Text, nullable=True)  # 改为Text类型
    tool_results = Column(Text, nullable=True)  # 改为Text类型
    created_at = Column(DateTime, nullable=False, default=func.now())

    session = relationship("ChatSession", back_populates="messages")
