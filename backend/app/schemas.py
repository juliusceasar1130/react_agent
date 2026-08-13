# backend/app/schemas.py
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from typing import Annotated, Any, Dict, Literal, Optional, List, Union
from datetime import datetime
from backend.app.agent.tools.ask_user_question import QuestionItem


# 消息基类
class MessageBase(BaseModel):
    role: str  # user, assistant, system, tool
    content: str
    session_id: str
    tool_calls: Optional[str] = None  # JSON字符串
    tool_results: Optional[str] = None  # JSON字符串
    feedback: str = "none"
    refined_payload: Optional[str] = None  # LLM 预提纯后的 json 字符串

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


class ReasoningStreamEvent(BaseModel):
    type: Literal["reasoning"] = "reasoning"
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


class RAGContextPayload(BaseModel):
    title: str
    domain: str
    aliases: List[str]
    content: str


class RAGContextStreamEvent(BaseModel):
    type: Literal["rag_context"]
    rag_context: List[RAGContextPayload]


class LexiconTablePayload(BaseModel):
    table_name: str
    ddl: str


class LexiconValuePayload(BaseModel):
    table_name: str
    column_name: str
    exact_value: str


class LexiconRowPayload(BaseModel):
    table_name: str
    primary_key_column: str
    primary_key_val: str
    row_content: str


class LexiconContextPayload(BaseModel):
    tables: List[LexiconTablePayload] = []
    values: List[LexiconValuePayload] = []
    rows: List[LexiconRowPayload] = []


class LexiconContextStreamEvent(BaseModel):
    type: Literal["lexicon_context"]
    lexicon_context: LexiconContextPayload


class ToolArtifactStreamEvent(BaseModel):
    type: Literal["tool_artifact"]
    artifact: Dict[str, Any]


class SubagentChangeStreamEvent(BaseModel):
    type: Literal["subagent_change"] = "subagent_change"
    active_subagent: str
    display_name: str


class PlanUpdateStreamEvent(BaseModel):
    type: Literal["plan_update"] = "plan_update"
    plan: Dict[str, Any]


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


class InterruptStreamEvent(BaseModel):
    type: Literal["interrupt"]
    questions: List[QuestionItem]
    session_id: str


ChatStreamEvent = Annotated[
    Union[
        TokenStreamEvent,
        ReasoningStreamEvent,
        StatusStreamEvent,
        ToolCallStreamEvent,
        ToolResultStreamEvent,
        FinalStreamEvent,
        ErrorStreamEvent,
        InterruptStreamEvent,
        RAGContextStreamEvent,
        LexiconContextStreamEvent,
        ToolArtifactStreamEvent,
        SubagentChangeStreamEvent,
        PlanUpdateStreamEvent,
    ],
    Field(discriminator="type"),
]

_chat_stream_event_adapter = TypeAdapter(ChatStreamEvent)


def serialize_chat_stream_event(event: Any) -> Dict[str, Any]:
    """校验并序列化项目统一的结构化流式事件。"""
    validated_event = _chat_stream_event_adapter.validate_python(event)
    return validated_event.model_dump(mode="json", exclude_none=True)


class MessageFeedbackRequest(BaseModel):
    """客户端提交赞/踩/收藏状态的请求体"""
    feedback: str  # none, like, dislike, collected, approved


class MessageApproveRequest(BaseModel):
    """管理员审批并入库黄金案例的请求体"""
    custom_query: Optional[str] = None
    custom_sql: Optional[str] = None


# ==================== 快捷场景面板 (Scenario Quick Panel) Schemas ====================

class ScenarioItem(BaseModel):
    name: str
    title: str
    description: str
    direct_path_enabled: Optional[bool] = True


class ScenarioSummary(BaseModel):
    domain: str
    domain_title: str
    scenarios: List[ScenarioItem]

    model_config = ConfigDict(from_attributes=True)


class ParameterOptionSchema(BaseModel):
    value: str
    label: str


class ParameterDefSchema(BaseModel):
    type: str
    widget: str
    description: str
    required: bool = False
    default: Optional[Union[str, int, float]] = None
    options: List[ParameterOptionSchema] = []


class TemplateInfoSchema(BaseModel):
    name: str
    label: str


class ScenarioParamsResponse(BaseModel):
    name: str
    title: str
    output_type: str = "table"
    templates: Optional[List[TemplateInfoSchema]] = None
    default_template: Optional[str] = None
    parameters: Dict[str, ParameterDefSchema]

    model_config = ConfigDict(from_attributes=True)


class ScenarioExecuteRequest(BaseModel):
    params: Dict[str, Any] = {}
    template_name: Optional[str] = None
    page: Optional[int] = 1
    page_size: Optional[int] = 50


class ScenarioExecuteResponse(BaseModel):
    type: str  # "table" or "scalar"
    columns: Optional[List[str]] = None
    rows: Optional[List[List[Any]]] = None
    row_count: Optional[int] = None
    total_count: Optional[int] = None
    page: Optional[int] = 1
    page_size: Optional[int] = 50
    total_pages: Optional[int] = 1
    is_truncated: Optional[bool] = False
    value: Optional[Union[str, int, float]] = None
    label: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

