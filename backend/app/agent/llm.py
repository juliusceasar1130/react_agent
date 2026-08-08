# backend/app/agent/llm.py
"""
LLM 工厂与适配器模块

封装 LangChain 模型工厂 `_create_llm` 以及定制的 `QwenChatDeepSeek` 协议增强适配器，
解耦底层通信协议与上层 SQL Agent 逻辑。

修改时间: 2026-07-31 22:37 Asia/Shanghai
主要修改内容:
- 从 service.py 提取独立的 LLM 模块 llm.py
- 提供 QwenChatDeepSeek 兼容类 (支持 reasoning / reasoning_content 拦截与传输)
- 提供 _create_llm 模型工厂函数
"""

import logging
from typing import Any

from langchain_core.messages import AIMessageChunk
from langchain_deepseek import ChatDeepSeek

from backend.app.config import settings

logger = logging.getLogger(__name__)


class ReasoningAwareChatDeepSeek(ChatDeepSeek):
    """同时兼容 vLLM 返回的 reasoning 字段与 reasoning_content 字段的 ChatDeepSeek 增强类 (同步/异步/流式)"""

    def _create_chat_result(self, response: Any, generation_info: dict | None = None) -> Any:
        rtn = super()._create_chat_result(response, generation_info)
        choices = getattr(response, "choices", None)
        if choices:
            msg = choices[0].message
            reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None)
            if not reasoning and hasattr(msg, "model_extra") and isinstance(msg.model_extra, dict):
                reasoning = msg.model_extra.get("reasoning") or msg.model_extra.get("reasoning_content")
            if reasoning and rtn.generations:
                rtn.generations[0].message.additional_kwargs["reasoning_content"] = reasoning
        return rtn

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: Any,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> Any:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if not generation_chunk:
            return generation_chunk

        choices = getattr(chunk, "choices", None) or (chunk.get("choices") if isinstance(chunk, dict) else None)
        if choices:
            top = choices[0]
            delta = getattr(top, "delta", None) or (top.get("delta") if isinstance(top, dict) else None)
            if delta:
                reasoning = (
                    getattr(delta, "reasoning", None)
                    or getattr(delta, "reasoning_content", None)
                    or (delta.get("reasoning") if isinstance(delta, dict) else None)
                    or (delta.get("reasoning_content") if isinstance(delta, dict) else None)
                )
                if not reasoning and hasattr(delta, "model_extra") and isinstance(delta.model_extra, dict):
                    reasoning = delta.model_extra.get("reasoning") or delta.model_extra.get("reasoning_content")

                if reasoning and isinstance(generation_chunk.message, AIMessageChunk):
                    generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning

        return generation_chunk


# 向后兼容别名
QwenChatDeepSeek = ReasoningAwareChatDeepSeek


def _create_llm(use_ollama: bool = False) -> Any:
    """
    创建 LLM 实例。

    Args:
        use_ollama: 是否使用 Ollama 本地模型，默认使用 DeepSeek/Qwen

    Returns:
        BaseChatModel 实例
    """
    if use_ollama:
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.agent_temperature,
            num_ctx=settings.ollama_num_ctx,
            keep_alive=settings.ollama_keep_alive,
        )

    # 1. 组装标准参数
    kwargs: dict[str, Any] = {
        "model": settings.deepseek_model,
        "temperature": settings.agent_temperature,
        "api_key": settings.deepseek_api_key or "EMPTY",
        "api_base": settings.deepseek_base_url,
        "max_tokens": settings.agent_max_tokens,
        "request_timeout": settings.llm_timeout,
        "max_retries": settings.llm_max_retries,
    }

    # top_p 和 presence_penalty 属于 OpenAI 官方一级标准参数，直接在顶层参数传递以防触发 UserWarning
    if settings.llm_top_p is not None:
        kwargs["top_p"] = settings.llm_top_p
    if settings.llm_presence_penalty is not None:
        kwargs["presence_penalty"] = settings.llm_presence_penalty

    # 2. 动态检测并将 vLLM 特有的非标准采样参数安全包裹在 extra_body 中透传，规避 OpenAI SDK 的参数强拦截
    extra_body: dict[str, Any] = {}
    if settings.llm_top_k is not None:
        extra_body["top_k"] = settings.llm_top_k
    if settings.llm_repetition_penalty is not None:
        extra_body["repetition_penalty"] = settings.llm_repetition_penalty
    if settings.llm_min_p is not None:
        extra_body["min_p"] = settings.llm_min_p
    if settings.llm_enable_thinking is not None:
        extra_body["chat_template_kwargs"] = {
            "enable_thinking": settings.llm_enable_thinking
        }

    if extra_body:
        kwargs["extra_body"] = extra_body

    logger.info(
        "Initializing ReasoningAwareChatDeepSeek with arguments: %s",
        {k: v for k, v in kwargs.items() if k != "api_key"},
    )
    return ReasoningAwareChatDeepSeek(**kwargs)
