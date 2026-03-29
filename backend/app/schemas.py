# backend/app/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, Optional, List
from datetime import datetime


# 消息基类
class MessageBase(BaseModel):
    role: str  # user, assistant, system, tool
    content: str
    session_id: str
    tool_calls: Optional[str] = None  # JSON字符串
    tool_results: Optional[str] = None  # JSON字符串

    # 允许从 ORM 实例（SQLAlchemy 模型）创建 Pydantic 模型
    model_config = ConfigDict(from_attributes=True)


# 消息创建请求
class MessageCreate(MessageBase):
    pass


# 消息响应
class MessageResponse(MessageBase):
    id: str
    created_at: datetime


class SessionBase(BaseModel):
    title: Optional[str] = "新对话"
    # 允许从 ORM 实例创建
    model_config = ConfigDict(from_attributes=True)


# 会话创建请求
class SessionCreate(SessionBase):
    pass


# 会话更新请求
class SessionUpdate(BaseModel):
    pass


# 会话响应
class SessionResponse(SessionBase):
    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0  # 消息总数 - 2025-01-01
    messages: List[MessageResponse] = []


# 聊天请求
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: Optional[bool] = False


# 聊天响应
class ChatResponse(BaseModel):
    session_id: str
    message: MessageResponse
    is_complete: bool = True


# 流式响应事件
class ChatStreamEvent(BaseModel):
    type: str
    text: Optional[str] = None
    node: Optional[str] = None
    stage: Optional[str] = None
    message: Optional[str] = None
    retryable: Optional[bool] = None
    content: Optional[str] = None
    source: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    args_text: Optional[str] = None
    status: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[Dict[str, Any]] = None
    message_id: Optional[str] = None
    created_at: Optional[datetime] = None
