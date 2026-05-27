# backend/app/schemas.py
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from typing import Annotated, Any, Dict, Literal, Optional, List, Union
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
    enable_thinking: Optional[bool] = None  # 新增：支持客户端动态控制思考模式


class ContextWarningPayload(BaseModel):
    estimated_input_tokens: int
    warn_tokens: int
    context_window: int
    output_reserve: int
    safety_buffer: int
    message_count: int
    tool_count: int
    recommended_action: Literal["start_new_session"]
    source: Literal["context_warning"]


# 聊天响应
class ChatResponse(BaseModel):
    session_id: str
    message: MessageResponse
    is_complete: bool = True
    context_warning: Optional[ContextWarningPayload] = None


class ChartArtifactRef(BaseModel):
    kind: Literal["chart_artifact_ref"]
    chart_id: str
    chart_type: Literal["line", "bar"]
    title: str
    point_count: int
    created_at: datetime
    expires_at: datetime
    message: Optional[str] = None


class ChartSeriesDefinition(BaseModel):
    name: str
    field: str
    y_axis: Literal["left", "right"] = "left"
    category_field: Optional[str] = None
    category_value: Optional[str] = None
    color: Optional[str] = None


class ChartArtifactResponse(BaseModel):
    kind: Literal["chart_spec"]
    chart_id: str
    chart_type: Literal["line", "bar"]
    title: str
    description: Optional[str] = None
    x_field: str
    series: List[ChartSeriesDefinition]
    rows: List[Dict[str, Any]]
    created_at: datetime
    expires_at: datetime


StreamStage = Literal["thinking", "retrieving", "querying", "writing"]
StreamToolCallStatus = Literal["started", "streaming", "completed"]


class StreamToolCallPayload(BaseModel):
    id: str
    name: str
    args: Any = Field(default_factory=dict)
    args_text: str = ""
    status: StreamToolCallStatus


class TokenStreamEvent(BaseModel):
    type: Literal["token"]
    text: str
    node: Optional[str] = None


class StatusStreamEvent(BaseModel):
    type: Literal["status"]
    stage: StreamStage
    text: str
    source: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None


class ToolCallStreamEvent(BaseModel):
    type: Literal["tool_call"]
    id: str
    name: str
    args_text: str = ""
    status: StreamToolCallStatus


class ToolResultStreamEvent(BaseModel):
    type: Literal["tool_result"]
    id: str
    content: str


class FinalStreamEvent(BaseModel):
    type: Literal["final"]
    content: str
    tool_calls: Optional[List[StreamToolCallPayload]] = None
    tool_results: Optional[Dict[str, str]] = None
    context_warning: Optional[ContextWarningPayload] = None
    message_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ErrorStreamEvent(BaseModel):
    type: Literal["error"]
    message: str
    retryable: Optional[bool] = None
    message_id: Optional[str] = None
    created_at: Optional[datetime] = None


ChatStreamEvent = Annotated[
    Union[
        TokenStreamEvent,
        StatusStreamEvent,
        ToolCallStreamEvent,
        ToolResultStreamEvent,
        FinalStreamEvent,
        ErrorStreamEvent,
    ],
    Field(discriminator="type"),
]

_chat_stream_event_adapter = TypeAdapter(ChatStreamEvent)


def serialize_chat_stream_event(event: Any) -> Dict[str, Any]:
    """校验并序列化项目统一的结构化流式事件。"""
    validated_event = _chat_stream_event_adapter.validate_python(event)
    return validated_event.model_dump(mode="json", exclude_none=True)
