# backend/app/agent/middleware/rag_prompt_injector_middleware.py
"""
轻量级 RAG 提示词注入中间件 (RagPromptInjectorMiddleware)。

主要职责:
- 专门为主 Agent (或轻量级 Agent) 设计。
- 读取 state["lexicon_context"]["formatted_text"]，无痕注入发给 LLM 的 SystemMessage <runtime_context> 动态区。
- 不运行任何 SQL 工具消息折叠与极限删除算法，执行毫秒级开销。
"""

import datetime
import logging
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from langchain_core.runnables.config import ensure_config

from backend.app.agent.config.profile_loader import get_sampling_profile, apply_profile_to_model_settings
from backend.app.agent.context import RequestContext
from backend.app.agent.state import CustomState

logger = logging.getLogger(__name__)


class RagPromptInjectorMiddleware(AgentMiddleware[CustomState, RequestContext]):
    """轻量级 RAG 提示词注入中间件。"""

    state_schema = CustomState
    context_schema = RequestContext

    def _inject_thinking_config(self, request: ModelRequest) -> None:
        """从当前协程的运行时上下文(ContextVar)中，打捞客户端传入的思考模式，并动态覆写网络发包参数"""
        try:
            runnable_config = ensure_config()
            configurable = runnable_config.get("configurable") or {}
            client_enable_thinking = configurable.get("enable_thinking")
            client_thinking_level = configurable.get("thinking_level")

            if client_enable_thinking is not None:
                if request.model_settings is None:
                    request.model_settings = {}

                # 加载采样参数组合并覆写 model_settings
                profile = get_sampling_profile(client_enable_thinking, client_thinking_level)
                apply_profile_to_model_settings(request.model_settings, profile)

                logger.info(
                    "⚡ RagPromptInjectorMiddleware: 已注入采样参数组合 (mode=%s)",
                    "thinking" if client_enable_thinking else "fast",
                )
        except Exception as e:
            logger.warning("⚡ RagPromptInjectorMiddleware: 动态注入采样参数组合失败: %s", e)

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """从 request.runtime.context 或 request.state 中提取结构化 RAG 文本并动态编译入 SystemMessage。"""
        self._inject_thinking_config(request)

        runtime = getattr(request, "runtime", None)
        lexicon_ctx = (
            getattr(runtime, "context", {}).get("lexicon_context")
            if runtime and getattr(runtime, "context", None) and isinstance(runtime.context, dict)
            else None
        )
        if not lexicon_ctx and hasattr(request, "context") and isinstance(request.context, dict):
            lexicon_ctx = request.context.get("lexicon_context")
        if not lexicon_ctx:
            lexicon_ctx = request.state.get("lexicon_context") if request.state else {}

        if not lexicon_ctx or not isinstance(lexicon_ctx, dict):
            return request

        rag_text = lexicon_ctx.get("formatted_text", "")
        if not rag_text or not isinstance(rag_text, str) or not rag_text.strip():
            return request

        # 获取基础系统消息内容
        base_sys_text = ""
        if request.system_message:
            base_sys_text = (
                request.system_message.content
                if isinstance(request.system_message.content, str)
                else str(request.system_message.content)
            )

        # 组装静态区
        system_rules_xml = f"<system_rules>\n{base_sys_text.strip()}\n</system_rules>"

        # 组装动态区与日期锚点
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"[系统提示: {date_str}]"

        dynamic_parts = [rag_text.strip(), date_prompt]
        runtime_context_content = "\n\n".join(dynamic_parts).strip()
        runtime_context_xml = f"<runtime_context>\n{runtime_context_content}\n</runtime_context>"

        compiled_content = f"{system_rules_xml}\n\n{runtime_context_xml}"
        new_system_message = SystemMessage(content=compiled_content)

        logger.info("⚡ RagPromptInjectorMiddleware: 已将 RAG 背景知识注入主 Agent System Message。")
        return request.override(system_message=new_system_message)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """同步模型调用拦截。"""
        modified_request = self._modify_request(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Any],
    ) -> ModelResponse:
        """异步模型调用拦截。"""
        modified_request = self._modify_request(request)
        return await handler(modified_request)
