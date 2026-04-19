"""上下文窗口告警中间件。"""

from __future__ import annotations

import logging
from typing import Any, Callable

from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import BaseMessage
from langgraph.types import Command

from backend.app.agent.state import CustomState
from backend.app.agent.utils import emit_stream_status

logger = logging.getLogger(__name__)


class ContextWarningMiddleware(AgentMiddleware[CustomState]):
    """在最终 ModelRequest 上估算输入 token，并在接近阈值时发出告警。"""

    state_schema = CustomState

    def __init__(
        self,
        estimator: Any,
        enabled: bool = True,
        context_window: int = 0,
        warn_tokens: int = 0,
        output_reserve: int = 0,
        safety_buffer: int = 0,
    ) -> None:
        self.estimator = estimator
        self.enabled = enabled
        self.context_window = context_window
        self.warn_tokens = warn_tokens
        self.output_reserve = output_reserve
        self.safety_buffer = safety_buffer

    @staticmethod
    def _message_payload(message: BaseMessage | dict[str, Any]) -> dict[str, Any]:
        """将消息转换为可稳定序列化的估算载体。"""
        if isinstance(message, dict):
            return message

        payload: dict[str, Any] = {}
        message_type = getattr(message, "type", None) or getattr(message, "role", None)
        if message_type is not None:
            payload["type"] = message_type

        content = getattr(message, "content", None)
        if content is not None:
            payload["content"] = content

        name = getattr(message, "name", None)
        if name is not None:
            payload["name"] = name

        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id is not None:
            payload["tool_call_id"] = tool_call_id

        return payload

    def _estimate_input_tokens(self, request: ModelRequest) -> int:
        """估算 system_message / messages / tools 的输入 token 总和。"""
        total_tokens = 0

        if request.system_message is not None:
            total_tokens += self.estimator.count_json_like_tokens(
                self._message_payload(request.system_message)
            )

        total_tokens += self.estimator.count_json_like_tokens(
            [self._message_payload(message) for message in request.messages]
        )

        total_tokens += self.estimator.count_json_like_tokens(request.tools or [])
        return total_tokens + self.safety_buffer

    def _build_warning_payload(self, request: ModelRequest) -> tuple[dict[str, Any] | None, int | None]:
        """在达到阈值时生成统一 warning payload。"""
        if not self.enabled:
            return None, None

        estimated_input_tokens = self._estimate_input_tokens(request)
        if estimated_input_tokens < self.warn_tokens:
            return None, estimated_input_tokens

        return (
            {
                "estimated_input_tokens": estimated_input_tokens,
                "warn_tokens": self.warn_tokens,
                "context_window": self.context_window,
                "output_reserve": self.output_reserve,
                "safety_buffer": self.safety_buffer,
                "message_count": len(request.messages),
                "tool_count": len(request.tools or []),
                "recommended_action": "start_new_session",
                "source": "context_warning",
            },
            estimated_input_tokens,
        )

    def _emit_observability(self, request: ModelRequest, warning_payload: dict[str, Any] | None, estimated_input_tokens: int | None) -> None:
        """输出固定格式的观测日志，并在触发时发出流式状态事件。"""
        triggered = warning_payload is not None
        logger.info(
            "context warning check: enabled=%s estimated_input_tokens=%s warn_tokens=%s context_window=%s safety_buffer=%s triggered=%s message_count=%s tool_count=%s",
            self.enabled,
            estimated_input_tokens,
            self.warn_tokens,
            self.context_window,
            self.safety_buffer,
            triggered,
            len(request.messages),
            len(request.tools or []),
        )

        if warning_payload is not None:
            emit_stream_status(
                "当前上下文已接近安全阈值，建议新建对话",
                stage="thinking",
                source="context_warning",
                detail=warning_payload,
            )

    def _prepare_warning(self, request: ModelRequest) -> tuple[dict[str, Any] | None, int | None]:
        """在当前请求上执行上下文估算，并在触发时发出 custom status。"""
        warning_payload, estimated_input_tokens = self._build_warning_payload(request)
        self._emit_observability(request, warning_payload, estimated_input_tokens)
        return warning_payload, estimated_input_tokens

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ExtendedModelResponse:
        warning_payload, _ = self._prepare_warning(request)
        response = handler(request)
        return ExtendedModelResponse(
            model_response=response,
            command=Command(update={"context_warning": warning_payload}),
        )

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ExtendedModelResponse:
        warning_payload, _ = self._prepare_warning(request)
        response = await handler(request)
        return ExtendedModelResponse(
            model_response=response,
            command=Command(update={"context_warning": warning_payload}),
        )
