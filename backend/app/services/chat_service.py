# backend/app/services/chat_service.py
"""
FastAPI 兼容 Agent 服务适配层。

修改时间: 2026-03-31 10:45 Asia/Shanghai
主要修改内容:
- 本地 FastAPI 改为异步生命周期管理，不再在模块导入时立即初始化 Agent
- 切回 ainvoke / astream，并继续保留结构化流式事件协议
- 新增 initialize/get/shutdown 三段式单例管理，便于 startup/shutdown 中显式控制资源
- 修正流式最终答案聚合逻辑，避免将多节点 token 误落库为最终回答
- 修正 tool_call_chunk 聚合键，统一按 chunk index 归并工具调用
- 非流式错误改为向上抛出，由 API 层返回标准错误响应
- 新增 LangSmith tracing metadata / tags，便于按会话、模型与运行模式过滤 trace
- 2026-03-31 21:52 Asia/Shanghai: 新增 Agent 执行任务取消收敛，尽量把断连取消继续向下传到图执行与模型调用
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any, AsyncIterator, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from backend.app.agent.service import SQLAgentService as CoreSQLAgentService
from backend.app.config import settings

logger = logging.getLogger(__name__)


class SQLAgentService:
    """供 FastAPI 调用的 SQL Agent 兼容服务层。"""

    def __init__(self, core: CoreSQLAgentService) -> None:
        self.core = core
        self.agent = self.core.agent
        self.checkpointer = self.core.checkpointer
        self.conn_pool = self.core.conn_pool

    @classmethod
    async def create(cls, use_ollama: bool = False) -> "SQLAgentService":
        """异步创建 FastAPI 本地运行的兼容服务层。"""
        core = await CoreSQLAgentService.create_local_async(
            use_ollama=use_ollama,
        )
        return cls(core)

    async def aclose(self) -> None:
        """关闭底层异步资源。"""
        if self.core is not None:
            await self.core.aclose()
        self.agent = None
        self.checkpointer = None
        self.conn_pool = None
        self.core = None

    def _resolve_llm_provider(self) -> str:
        """根据当前服务配置解析追踪用的 provider 名称。"""
        if getattr(self.core, "_use_ollama", False):
            return "ollama"

        base_url = (settings.deepseek_base_url or "").lower()
        if "deepseek.com" in base_url:
            return "deepseek"
        if "openai" in base_url:
            return "openai"
        return "custom"

    def _resolve_llm_model_name(self) -> str:
        """获取当前服务使用的模型名称。"""
        if getattr(self.core, "_use_ollama", False):
            return settings.ollama_model or "unknown"
        return settings.deepseek_model or "unknown"

    @staticmethod
    def _merge_unique_items(*items: list[str]) -> list[str]:
        """按顺序合并字符串列表并去重。"""
        merged: list[str] = []
        seen: set[str] = set()

        for group in items:
            for item in group:
                normalized = str(item).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)

        return merged

    def _build_trace_metadata(
        self,
        session_id: str,
        request_mode: str,
        existing_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """构造 LangSmith trace metadata。"""
        llm_provider = self._resolve_llm_provider()
        llm_model_name = self._resolve_llm_model_name()
        metadata = {
            "session_id": str(session_id),
            "thread_id": str(session_id),
            "request_mode": request_mode,
            "app_component": "fastapi_chat_api",
            "runtime_mode": "fastapi_local",
            "rag_backend": settings.rag_backend,
            "ls_provider": llm_provider,
            "ls_model_name": llm_model_name,
            "ls_temperature": settings.agent_temperature,
            "ls_max_tokens": settings.agent_max_tokens,
        }

        if existing_metadata:
            metadata.update(existing_metadata)
            if (
                "business_domain" not in metadata
                and existing_metadata.get("domain") is not None
            ):
                metadata["business_domain"] = existing_metadata["domain"]

        return metadata

    def _build_trace_tags(
        self,
        request_mode: str,
        existing_tags: Optional[list[Any]] = None,
    ) -> list[str]:
        """构造 LangSmith trace tags。"""
        llm_provider = self._resolve_llm_provider()
        llm_model_name = self._resolve_llm_model_name()
        default_tags = [
            "chat-api",
            "sql-agent",
            f"mode:{request_mode}",
            "runtime:fastapi_local",
            f"rag:{settings.rag_backend}",
            f"provider:{llm_provider}",
            f"model:{llm_model_name}",
            f"env:{'debug' if settings.debug else 'prod'}",
        ]

        normalized_existing = [str(item) for item in (existing_tags or [])]
        return self._merge_unique_items(default_tags, normalized_existing)

    def _build_config(
        self,
        session_id: str,
        config: Optional[dict],
        *,
        request_mode: str,
    ) -> dict:
        """构造并补全 LangGraph / LangSmith 配置。"""
        resolved_config = dict(config or {})
        configurable = dict(resolved_config.get("configurable") or {})
        metadata = dict(resolved_config.get("metadata") or {})
        tags = resolved_config.get("tags") or []

        configurable["thread_id"] = str(session_id)
        resolved_config["configurable"] = configurable
        resolved_config["metadata"] = self._build_trace_metadata(
            session_id,
            request_mode,
            metadata,
        )
        resolved_config["tags"] = self._build_trace_tags(
            request_mode,
            tags if isinstance(tags, list) else [tags],
        )
        resolved_config.setdefault(
            "run_name",
            "SQLAgentChatStream" if request_mode == "stream" else "SQLAgentChatInvoke",
        )
        return resolved_config

    @staticmethod
    def _iter_content_blocks(message: Any) -> list[dict]:
        """统一读取 content_blocks / content 中的结构化块。"""
        content_blocks = getattr(message, "content_blocks", None)
        if isinstance(content_blocks, list):
            return [block for block in content_blocks if isinstance(block, dict)]

        content = getattr(message, "content", None)
        if isinstance(content, list):
            return [block for block in content if isinstance(block, dict)]
        return []

    @classmethod
    def _extract_text_segments(cls, message: Any) -> list[str]:
        """提取文本片段，兼容字符串内容与 text content blocks。"""
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return [content] if content else []

        text_parts = []
        for block in cls._iter_content_blocks(message):
            if block.get("type") == "text" and block.get("text"):
                text_parts.append(block["text"])
        return text_parts

    @classmethod
    def _extract_message_content(cls, message: Any) -> str:
        """提取消息完整文本内容。"""
        return "".join(cls._extract_text_segments(message))

    @staticmethod
    def _normalize_tool_args(args: Any) -> Any:
        """规范化工具参数，兼容 dict / 其他对象。"""
        if isinstance(args, dict):
            return dict(args)
        return args or {}

    @staticmethod
    def _safe_load_json(text: str) -> Any:
        """尽力将字符串解析为 JSON。"""
        if not text:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    def _upsert_tool_call(
        self,
        tool_calls: dict[str, dict[str, Any]],
        *,
        tool_call_id: str,
        actual_id: str = "",
        name: str = "",
        args: Any = None,
        args_text_delta: str = "",
        subagent_id: Optional[str] = None,
        subagent_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """更新工具调用聚合信息。"""
        existing = tool_calls.get(
            tool_call_id,
            {
                "id": tool_call_id,
                "actual_id": "",
                "name": "",
                "args": {},
                "args_text": "",
            },
        )

        if actual_id:
            existing["actual_id"] = actual_id
        if name:
            existing["name"] = name
        if args is not None:
            existing["args"] = self._normalize_tool_args(args)
        if args_text_delta:
            existing["args_text"] = f"{existing.get('args_text', '')}{args_text_delta}"
            parsed = self._safe_load_json(existing["args_text"])
            if parsed is not None:
                existing["args"] = parsed
        if subagent_id is not None:
            existing["subagent_id"] = subagent_id
        if subagent_name is not None:
            existing["subagent_name"] = subagent_name

        tool_calls[tool_call_id] = existing
        return existing

    @staticmethod
    def _find_tool_call_key_by_actual_id(
        tool_calls: dict[str, dict[str, Any]],
        actual_id: str,
    ) -> Optional[str]:
        """根据 LangChain 原始 tool_call_id 查找内部聚合键。"""
        if not actual_id:
            return None

        for key, item in tool_calls.items():
            if item.get("actual_id") == actual_id or item.get("id") == actual_id:
                return key
        return None

    def _collect_tool_calls_from_message(
        self,
        message: Any,
        tool_calls: dict[str, dict[str, Any]],
        subagent_id: Optional[str] = None,
        subagent_name: Optional[str] = None,
    ) -> None:
        """从 AIMessage / 完整消息中提取工具调用。"""
        raw_tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in raw_tool_calls:
            try:
                actual_id = tool_call["id"] if tool_call.get("id") else ""
                tool_name = tool_call["name"] if tool_call.get("name") else ""
                if not actual_id or not tool_name:
                    continue

                tool_call_id = (
                    self._find_tool_call_key_by_actual_id(tool_calls, actual_id)
                    or actual_id
                )
                self._upsert_tool_call(
                    tool_calls,
                    tool_call_id=tool_call_id,
                    actual_id=actual_id,
                    name=tool_name,
                    args=tool_call.get("args"),
                    subagent_id=subagent_id,
                    subagent_name=subagent_name,
                )
            except (KeyError, TypeError, AttributeError) as exc:
                logger.warning("提取工具调用信息失败: %s", exc)

    def _collect_tool_call_chunk_events(
        self,
        message: Any,
        tool_calls: dict[str, dict[str, Any]],
        subagent_id: Optional[str] = None,
        subagent_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """从流式消息块中提取 tool_call_chunk 事件。"""
        events: list[dict[str, Any]] = []
        for block in self._iter_content_blocks(message):
            if block.get("type") != "tool_call_chunk":
                continue

            block_index = block.get("index", 0)
            actual_id = block.get("id") or ""
            message_id = getattr(message, "id", None) or ""

            tool_call_id = ""
            if actual_id:
                tool_call_id = actual_id
            else:
                for key, item in tool_calls.items():
                    if item.get("message_id") == message_id and item.get("block_index") == block_index:
                        tool_call_id = key
                        break
                
                if not tool_call_id:
                    tool_call_id = f"tool_{message_id}_{block_index}" if message_id else f"tool_call_chunk_{len(tool_calls)}"

            is_new = tool_call_id not in tool_calls
            tool_info = self._upsert_tool_call(
                tool_calls,
                tool_call_id=tool_call_id,
                actual_id=actual_id or tool_call_id,
                name=block.get("name") or "",
                args_text_delta=block.get("args") or "",
                subagent_id=subagent_id,
                subagent_name=subagent_name,
            )
            
            tool_info["message_id"] = message_id
            tool_info["block_index"] = block_index

            if not tool_info.get("name") and not tool_info.get("args_text"):
                continue

            event_dict: dict[str, Any] = {
                "type": "tool_call",
                "id": tool_info["id"],
                "name": tool_info.get("name") or f"tool_call_{block_index}",
                "args_text": tool_info.get("args_text") or "",
                "status": "started" if is_new else "streaming",
            }
            resolved_subagent_id = subagent_id or tool_info.get("subagent_id")
            resolved_subagent_name = subagent_name or tool_info.get("subagent_name")
            if resolved_subagent_id:
                event_dict["subagent_id"] = resolved_subagent_id
            if resolved_subagent_name:
                event_dict["subagent_name"] = resolved_subagent_name

            events.append(event_dict)

        return events

    def _collect_tool_result_event(
        self,
        message: Any,
        tool_calls: dict[str, dict[str, Any]],
        tool_results: dict[str, str],
        subagent_id: Optional[str] = None,
        subagent_name: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """从 ToolMessage 中提取工具结果事件。"""
        if not isinstance(message, ToolMessage):
            return None

        content = self._extract_message_content(message)
        if not message.tool_call_id or not content:
            return None

        tool_call_id = (
            self._find_tool_call_key_by_actual_id(tool_calls, message.tool_call_id)
            or message.tool_call_id
        )

        previous = tool_results.get(tool_call_id)
        tool_results[tool_call_id] = content

        if previous == content:
            return None

        event_dict: dict[str, Any] = {
            "type": "tool_result",
            "id": tool_call_id,
            "content": content,
        }
        matched_call_id = subagent_id or tool_calls.get(tool_call_id, {}).get("subagent_id")
        matched_sub_name = subagent_name or tool_calls.get(tool_call_id, {}).get("subagent_name")
        if matched_call_id:
            event_dict["subagent_id"] = matched_call_id
        if matched_sub_name:
            event_dict["subagent_name"] = matched_sub_name

        return event_dict

    @staticmethod
    def _serialize_tool_calls(
        tool_calls: dict[str, dict[str, Any]],
        *,
        final: bool = False,
    ) -> list[dict[str, Any]]:
        """将工具调用聚合结果序列化为列表。"""
        serialized = []
        for item in tool_calls.values():
            call_entry: dict[str, Any] = {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "args": item.get("args", {}) or {},
                "args_text": item.get("args_text", "") or "",
                "status": "completed" if final else (item.get("status") or "streaming"),
            }
            if item.get("subagent_id"):
                call_entry["subagent_id"] = item["subagent_id"]
            if item.get("subagent_name"):
                call_entry["subagent_name"] = item["subagent_name"]
            serialized.append(call_entry)
        return serialized

    def _extract_tool_data_from_result(self, result: dict) -> tuple[str, list, dict]:
        """从 invoke 结果中提取最终文本、工具调用和工具结果。"""
        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None
        content = self._extract_message_content(last_message)

        tool_calls_map: dict[str, dict[str, Any]] = {}
        tool_results: dict[str, str] = {}
        intermediate_steps = result.get("intermediate_steps", [])
        logger.info("中间步骤数量: %d", len(intermediate_steps))

        for step in intermediate_steps:
            if len(step) < 2:
                continue

            action = step[0]
            observation = step[1]
            tool_name = getattr(action, "tool", "")
            tool_input = getattr(action, "tool_input", {})
            tool_id = f"tool_{len(tool_calls_map)}"

            if tool_name:
                self._upsert_tool_call(
                    tool_calls_map,
                    tool_call_id=tool_id,
                    name=tool_name,
                    args=tool_input,
                )

            if observation:
                tool_results[tool_id] = str(observation)

        logger.info("处理消息列表，共 %d 条消息", len(messages))

        if not intermediate_steps:
            for message in messages:
                if isinstance(message, AIMessage):
                    self._collect_tool_calls_from_message(message, tool_calls_map)
                tool_result_event = self._collect_tool_result_event(
                    message,
                    tool_calls_map,
                    tool_results,
                )
                if tool_result_event:
                    tool_results[tool_result_event["id"]] = tool_result_event["content"]

        tool_calls = self._serialize_tool_calls(tool_calls_map, final=True)
        logger.info(
            "提取完成：tool_calls=%d 个, tool_results=%d 个",
            len(tool_calls),
            len(tool_results),
        )
        return content, tool_calls, tool_results

    @staticmethod
    def _build_status_event(
        node_name: str,
        *,
        has_tool_results: bool,
        has_tokens: bool,
    ) -> Optional[dict[str, Any]]:
        """将 LangGraph 节点名映射为状态事件。"""
        node_lower = (node_name or "").lower()
        if not node_lower or node_lower == "__interrupt__":
            return None

        if "rag" in node_lower or "retriev" in node_lower or "skill" in node_lower:
            return {
                "type": "status",
                "stage": "retrieving",
                "text": "正在检索业务上下文",
                "source": node_name,
            }

        if "tool" in node_lower:
            return {
                "type": "status",
                "stage": "querying",
                "text": "正在调用工具",
                "source": node_name,
            }

        if "model" in node_lower:
            if has_tool_results or has_tokens:
                return {
                    "type": "status",
                    "stage": "writing",
                    "text": "正在整理答案",
                    "source": node_name,
                }
            return {
                "type": "status",
                "stage": "thinking",
                "text": "正在分析问题",
                "source": node_name,
            }

        return {
            "type": "status",
            "stage": "thinking",
            "text": f"正在执行节点：{node_name}",
            "source": node_name,
        }

    @staticmethod
    def _normalize_custom_event(data: Any) -> Optional[dict[str, Any]]:
        """规范化 custom stream 事件。"""
        if isinstance(data, dict):
            if data.get("type") in {
                "token",
                "status",
                "tool_call",
                "tool_result",
                "final",
                "error",
                "subagent_change",
                "plan_update",
            }:
                return data
            return None

        if isinstance(data, str) and data.strip():
            return {
                "type": "status",
                "stage": "thinking",
                "text": data.strip(),
            }

        return None

    @staticmethod
    def _unpack_stream_chunk(chunk: Any) -> tuple[Optional[str], Any]:
        """兼容 LangGraph sync/async streaming 的不同返回形状。"""
        if isinstance(chunk, dict):
            return chunk.get("type"), chunk.get("data")

        if isinstance(chunk, (tuple, list)):
            if len(chunk) == 2 and isinstance(chunk[0], str):
                return chunk[0], chunk[1]

            if (
                len(chunk) == 3
                and isinstance(chunk[1], str)
            ):
                return chunk[1], chunk[2]

        return None, chunk

    @staticmethod
    def _status_signature(event: dict[str, Any]) -> tuple[str, str, str, str]:
        """构建状态事件签名，用于去重。"""
        return (
            event.get("stage", ""),
            event.get("text", ""),
            event.get("source", ""),
            str(event.get("subagent_id") or ""),
        )

    async def process_message(
        self, message: str, session_id: str, config: dict = None
    ) -> Dict[str, Any]:
        """处理用户消息（非流式）。"""
        resolved_config = self._build_config(
            session_id,
            config,
            request_mode="invoke",
        )
        invoke_task = asyncio.create_task(
            self.agent.ainvoke(
                {"messages": [HumanMessage(content=message)]},
                config=resolved_config,
            )
        )
        try:
            result = await invoke_task
        except asyncio.CancelledError:
            logger.info("非流式 Agent 调用被取消: session_id=%s", session_id)
            invoke_task.cancel()
            with suppress(asyncio.CancelledError):
                await invoke_task
            raise

        content, tool_calls, tool_results = self._extract_tool_data_from_result(
            result
        )
        context_warning = result.get("context_warning")
        return {
            "content": content,
            "tool_calls": json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            "tool_results": json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
            "context_warning": context_warning,
        }

    async def process_stream(
        self, message: str, session_id: str, config: dict = None
    ) -> AsyncIterator[dict[str, Any]]:
        """流式处理用户消息，输出结构化事件。"""
        resolved_config = self._build_config(
            session_id,
            config,
            request_mode="stream",
        )
        logger.info("开始流式处理，消息: %s...", message[:100])
        input_data = {
            "messages": [HumanMessage(content=message)],
            "rag_context": [],
            "rag_query": "",
        }
        async for event in self._stream_execution_loop(session_id, resolved_config, input_data):
            yield event

    async def process_stream_resume(
        self, session_id: str, answers: dict[str, Any], config: dict = None
    ) -> AsyncIterator[dict[str, Any]]:
        """从挂起状态恢复流式消息执行。"""
        resolved_config = self._build_config(
            session_id,
            config,
            request_mode="stream",
        )
        logger.info("开始流式恢复处理，session_id: %s, 答复: %s", session_id, answers)
        input_data = Command(resume=answers)
        async for event in self._stream_execution_loop(session_id, resolved_config, input_data):
            yield event

    async def _stream_execution_loop(
        self, session_id: str, resolved_config: dict, input_data: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """核心流式执行循环。"""
        has_stream_tokens = False
        accumulated_tool_calls: dict[str, dict[str, Any]] = {}
        accumulated_tool_results: dict[str, str] = {}
        context_warning: Optional[dict[str, Any]] = None
        latest_ai_content = ""
        last_status_signature: Optional[tuple[str, str, str]] = None
        event_queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()
        stream_done = object()
        source_iter: Optional[Any] = None
        producer_task: Optional[asyncio.Task[None]] = None

        async def _emit(event: dict[str, Any]) -> None:
            await event_queue.put(event)

        async def _produce_events() -> None:
            nonlocal has_stream_tokens
            nonlocal latest_ai_content
            nonlocal last_status_signature
            nonlocal source_iter
            nonlocal context_warning
            try:
                user_query = None
                if isinstance(input_data, dict) and "messages" in input_data:
                    last_msg = input_data["messages"][-1]
                    user_query = getattr(last_msg, "content", "")
                    if isinstance(user_query, str):
                        user_query = user_query.strip()

                initial_status = {
                    "type": "status",
                    "stage": "thinking",
                    "text": "正在分析问题",
                    "source": "agent",
                }
                await _emit(initial_status)
                last_status_signature = self._status_signature(initial_status)

                source_iter = self.agent.astream(
                    input_data,
                    config=resolved_config,
                    stream_mode=["messages", "updates", "custom"],
                    subgraphs=True,
                    version="v2",
                )

                has_sent_rag = False
                has_sent_lexicon = False
                current_subagent = None
                active_task_targets: dict[str, str] = {}
                warned_unregistered_tools: set[str] = set()
                # 按 task call_id 聚合子智能体会话（reasoning/content），final 时随事件落库
                accumulated_subagents: dict[str, dict[str, Any]] = {}

                async for chunk in source_iter:
                    if chunk is None:
                        continue

                    if isinstance(chunk, dict):
                        ns = chunk.get("ns", ())
                        chunk_type = chunk.get("type")
                        data = chunk.get("data")

                        if chunk_type == "messages" and isinstance(data, tuple) and len(data) == 2:
                            msg_chunk, _ = data
                            if hasattr(msg_chunk, "tool_calls") and msg_chunk.tool_calls:
                                for tc in msg_chunk.tool_calls:
                                    if isinstance(tc, dict):
                                        tc_name = tc.get("name", "")
                                        tc_id = tc.get("id")
                                        tc_args = tc.get("args") or {}
                                        if tc_name == "task" and tc_id:
                                            target_subagent = (
                                                tc_args.get("subagent")
                                                or tc_args.get("subagent_type")
                                                or "sql_domain_agent"
                                            )
                                            active_task_targets[tc_id] = target_subagent

                        matched_subagent = None
                        matched_call_id = None
                        if ns:
                            for segment in ns:
                                if isinstance(segment, str):
                                    if segment.startswith("tools:"):
                                        call_id = segment.split("tools:", 1)[1]
                                        matched_call_id = call_id
                                        # 未知 call_id 不打标（宁可回落 main，也不静默归属 sql_domain_agent）
                                        matched_subagent = active_task_targets.get(call_id)
                                        if matched_subagent is None:
                                            if call_id not in warned_unregistered_tools:
                                                warned_unregistered_tools.add(call_id)
                                                logger.warning(
                                                    "ns 含未登记的 tools:%s，不归属子智能体（active_task_targets=%s）",
                                                    call_id,
                                                    sorted(active_task_targets.keys()),
                                                )
                                        break
                                    elif "sql_domain_agent" in segment:
                                        # ns 中出现子智能体名（CompiledSubAgent run_name 可能注入）时的兜底：
                                        # 只标记归属、不猜测 call_id，避免并行委派时错配会话
                                        matched_subagent = "sql_domain_agent"
                                        break

                        new_subagent = matched_subagent if matched_subagent else "main"
                        if new_subagent != current_subagent:
                            current_subagent = new_subagent
                            # 子智能体识别与显示名目前仅覆盖 sql_domain_agent；
                            # 新增子智能体时需同步扩展 active_task_targets 来源、本映射与前端 title 映射
                            display_name = (
                                "SQL数据助手" if current_subagent == "sql_domain_agent" else "通用助手"
                            )
                            await _emit({
                                "type": "subagent_change",
                                "active_subagent": current_subagent,
                                "display_name": display_name,
                            })

                    if not has_sent_rag:
                        try:
                            state = await self.agent.aget_state(resolved_config)
                            rag_context_list = state.values.get("rag_context", []) if state else []
                            rag_query = state.values.get("rag_query", "") if state else ""
                            if isinstance(rag_query, str):
                                rag_query = rag_query.strip()

                            if rag_context_list and (user_query is None or rag_query == user_query):
                                rag_context_payload = [
                                    {
                                        "title": doc.metadata.get("term") or doc.metadata.get("title") or "未命名术语",
                                        "domain": doc.metadata.get("domain", "通用"),
                                        "aliases": doc.metadata.get("aliases", []),
                                        "content": doc.page_content,
                                    }
                                    for doc in rag_context_list
                                ]
                                await _emit({
                                    "type": "rag_context",
                                    "rag_context": rag_context_payload
                                })
                                has_sent_rag = True
                        except Exception as e:
                            logger.warning("流式执行中提前提取并发送 RAG 状态失败: %s", e)
                            has_sent_rag = True

                    if not has_sent_lexicon:
                        try:
                            state = await self.agent.aget_state(resolved_config)
                            lexicon_context_val = state.values.get("lexicon_context", {}) if state else {}
                            rag_query = state.values.get("rag_query", "") if state else ""
                            if isinstance(rag_query, str):
                                rag_query = rag_query.strip()

                            if lexicon_context_val and "detail" in lexicon_context_val and (user_query is None or rag_query == user_query):
                                await _emit({
                                    "type": "lexicon_context",
                                    "lexicon_context": lexicon_context_val["detail"]
                                })
                                has_sent_lexicon = True
                        except Exception as e:
                            logger.warning("流式执行中提前提取并发送 Lexicon 状态失败: %s", e)
                            has_sent_lexicon = True

                    chunk_type, chunk_data = self._unpack_stream_chunk(chunk)
                    if chunk_type is None:
                        logger.debug("无法识别的流式块结构: %r", chunk)
                        continue

                    if chunk_type == "messages":
                        if (
                            not isinstance(chunk_data, (tuple, list))
                            or len(chunk_data) != 2
                        ):
                            continue

                        message_chunk, metadata = chunk_data
                        node_name = (
                            metadata.get("langgraph_node")
                            if isinstance(metadata, dict)
                            else None
                        )

                        if isinstance(message_chunk, AIMessage):
                            reasoning_text = message_chunk.additional_kwargs.get("reasoning_content")
                            if reasoning_text:
                                reasoning_dict: dict[str, Any] = {
                                    "type": "reasoning",
                                    "text": reasoning_text,
                                    "node": node_name,
                                }
                                if matched_call_id:
                                    reasoning_dict["subagent_id"] = matched_call_id
                                    reasoning_dict["subagent_name"] = matched_subagent
                                    sub_state = accumulated_subagents.setdefault(
                                        matched_call_id,
                                        {"name": matched_subagent, "reasoning": "", "content": "", "_reasoning_len": 0},
                                    )
                                    # reasoning_content 可能以完整消息重复出现，按长度增量去重
                                    if len(reasoning_text) > sub_state["_reasoning_len"]:
                                        sub_state["reasoning"] += reasoning_text[sub_state["_reasoning_len"]:]
                                        sub_state["_reasoning_len"] = len(reasoning_text)
                                await _emit(reasoning_dict)

                            for text_segment in self._extract_text_segments(message_chunk):
                                if not text_segment:
                                    continue
                                has_stream_tokens = True
                                token_dict: dict[str, Any] = {
                                    "type": "token",
                                    "text": text_segment,
                                    "node": node_name,
                                }
                                if matched_call_id:
                                    token_dict["subagent_id"] = matched_call_id
                                    token_dict["subagent_name"] = matched_subagent
                                    sub_state = accumulated_subagents.setdefault(
                                        matched_call_id,
                                        {"name": matched_subagent, "reasoning": "", "content": "", "_reasoning_len": 0},
                                    )
                                    sub_state["content"] += text_segment
                                await _emit(token_dict)

                        for event in self._collect_tool_call_chunk_events(
                            message_chunk,
                            accumulated_tool_calls,
                            subagent_id=matched_call_id,
                            subagent_name=matched_subagent,
                        ):
                            await _emit(event)

                        tool_result_event = self._collect_tool_result_event(
                            message_chunk,
                            accumulated_tool_calls,
                            accumulated_tool_results,
                            subagent_id=matched_call_id,
                            subagent_name=matched_subagent,
                        )
                        if tool_result_event:
                            await _emit(tool_result_event)

                    elif chunk_type == "updates" and isinstance(chunk_data, dict):
                        for node_name, state_update in chunk_data.items():
                            status_event = self._build_status_event(
                                node_name,
                                has_tool_results=bool(accumulated_tool_results),
                                has_tokens=has_stream_tokens,
                            )
                            if status_event:
                                if matched_call_id:
                                    status_event["subagent_id"] = matched_call_id
                                    status_event["subagent_name"] = matched_subagent
                                status_signature = self._status_signature(status_event)
                                if status_signature != last_status_signature:
                                    await _emit(status_event)
                                    last_status_signature = status_signature

                            if not isinstance(state_update, dict):
                                continue

                            if "tool_artifact" in state_update:
                                artifact_val = state_update.get("tool_artifact")
                                if artifact_val:
                                    await _emit({
                                        "type": "tool_artifact",
                                        "artifact": artifact_val
                                    })

                            if "context_warning" in state_update:
                                warning_payload = state_update.get("context_warning")
                                normalized_warning = (
                                    warning_payload
                                    if isinstance(warning_payload, dict)
                                    else None
                                )
                                if normalized_warning != context_warning:
                                    context_warning = normalized_warning
                                    if normalized_warning is not None:
                                        warning_event = {
                                            "type": "status",
                                            "stage": "thinking",
                                            "text": "当前上下文已接近安全阈值，建议新建对话",
                                            "source": "context_warning",
                                            "detail": normalized_warning,
                                        }
                                        status_signature = self._status_signature(warning_event)
                                        if status_signature != last_status_signature:
                                            await _emit(warning_event)
                                            last_status_signature = status_signature

                            updated_messages = state_update.get("messages", [])
                            last_message = (
                                updated_messages[-1] if updated_messages else None
                            )
                            if last_message is None:
                                continue

                            if isinstance(last_message, AIMessage):
                                self._collect_tool_calls_from_message(
                                    last_message,
                                    accumulated_tool_calls,
                                    subagent_id=matched_call_id,
                                    subagent_name=matched_subagent,
                                )
                                if not getattr(last_message, "tool_calls", None):
                                    latest_ai_content = self._extract_message_content(
                                        last_message
                                    )

                            tool_result_event = self._collect_tool_result_event(
                                last_message,
                                accumulated_tool_calls,
                                accumulated_tool_results,
                                subagent_id=matched_call_id,
                                subagent_name=matched_subagent,
                            )
                            if tool_result_event:
                                await _emit(tool_result_event)

                    elif chunk_type == "custom":
                        custom_event = self._normalize_custom_event(chunk_data)
                        if not custom_event:
                            continue

                        if (
                            custom_event.get("type") == "status"
                            and custom_event.get("source") == "context_warning"
                            and isinstance(custom_event.get("detail"), dict)
                        ):
                            context_warning = custom_event["detail"]

                        if custom_event.get("type") == "status":
                            status_signature = self._status_signature(custom_event)
                            if status_signature == last_status_signature:
                                continue
                            last_status_signature = status_signature

                        await _emit(custom_event)

                state = await self.agent.aget_state(resolved_config)
                state_next = state.next if state else []
                state_tasks = state.tasks if state else []
                logger.info("[interrupt_check] aget_state 返回: next=%s, tasks=%d, session_id=%s",
                            list(state_next) if state_next else "[]", len(state_tasks), session_id)
                if state_next and any("tools" in n or "AskUserQuestion" in n for n in state_next):
                    if state_tasks and state_tasks[0].interrupts:
                        interrupt_val = state_tasks[0].interrupts[0].value
                        logger.info("[interrupt_check] 检测到 interrupt: type=%s, value=%s, session_id=%s",
                                    type(interrupt_val).__name__, str(interrupt_val)[:200], session_id)
                        if isinstance(interrupt_val, dict) and interrupt_val.get("type") == "ask_user_question":
                            questions = interrupt_val.get("questions", [])
                            logger.info("[interrupt_check] 识别为 AskUserQuestion interrupt: questions=%d, session_id=%s",
                                        len(questions), session_id)
                            
                            interrupt_subagent_id = None
                            interrupt_subagent_name = None
                            interrupt_subagent_title = None

                            # 查找最新触发 AskUserQuestion 的工具调用归属
                            target_call = None
                            for tc in reversed(list(accumulated_tool_calls.values())):
                                if isinstance(tc, dict) and tc.get("name") == "AskUserQuestion":
                                    target_call = tc
                                    break

                            if target_call and target_call.get("subagent_id"):
                                interrupt_subagent_id = target_call.get("subagent_id")
                                sess = accumulated_subagents.get(interrupt_subagent_id, {})
                                interrupt_subagent_name = sess.get("name") or target_call.get("subagent_name")
                            elif current_subagent and current_subagent != "main":
                                interrupt_subagent_name = current_subagent
                                interrupt_subagent_id = matched_call_id
                            elif matched_subagent and matched_subagent != "main":
                                interrupt_subagent_name = matched_subagent
                                interrupt_subagent_id = matched_call_id

                            subagent_title_map = {
                                "sql_domain_agent": "SQL数据专家",
                            }
                            if interrupt_subagent_name and interrupt_subagent_name in subagent_title_map:
                                interrupt_subagent_title = subagent_title_map[interrupt_subagent_name]

                            interrupt_payload: dict[str, Any] = {
                                "type": "interrupt",
                                "questions": questions,
                                "session_id": session_id,
                            }
                            if interrupt_subagent_id:
                                interrupt_payload["subagent_id"] = interrupt_subagent_id
                            if interrupt_subagent_name:
                                interrupt_payload["subagent_name"] = interrupt_subagent_name
                            if interrupt_subagent_title:
                                interrupt_payload["subagent_title"] = interrupt_subagent_title

                            await _emit(interrupt_payload)
                            logger.info("[interrupt_check] interrupt 事件已 emit (subagent=%s)，准备 return, session_id=%s",
                                        interrupt_subagent_name, session_id)
                            return
                        else:
                            logger.info("[interrupt_check] interrupt 值类型不匹配, session_id=%s", session_id)

                final_content = latest_ai_content
                tool_calls = self._serialize_tool_calls(
                    accumulated_tool_calls,
                    final=True,
                )
                logger.info(
                    "流式提取完成：text_len=%d, tool_calls=%d 个, tool_results=%d 个",
                    len(final_content),
                    len(tool_calls),
                    len(accumulated_tool_results),
                )
                # 组装子智能体会话快照：reasoning/content 来自循环聚合，工具链从打标后的 tool_calls 过滤
                subagents_payload: dict[str, dict[str, Any]] = {}
                for cid, sess in accumulated_subagents.items():
                    agent_tools = [tc for tc in tool_calls if tc.get("subagent_id") == cid]
                    sub_results = {
                        tid: accumulated_tool_results[tid]
                        for tid in (tc.get("id") for tc in agent_tools)
                        if tid in accumulated_tool_results
                    }
                    subagents_payload[cid] = {
                        "id": cid,
                        "name": sess["name"],
                        "status": "completed",
                        "reasoningText": sess["reasoning"],
                        "content": sess["content"],
                        "toolCalls": agent_tools,
                        "toolResults": sub_results,
                    }
                await _emit(
                    {
                        "type": "final",
                        "content": final_content,
                        "tool_calls": tool_calls or None,
                        "tool_results": accumulated_tool_results or None,
                        "subagents": subagents_payload or None,
                        "context_warning": context_warning,
                    }
                )

            except asyncio.CancelledError:
                logger.info("流式 Agent 任务被取消: session_id=%s", session_id)
                raise
            except Exception as exc:
                logger.error("流式处理失败: %s", exc, exc_info=True)
                await _emit(
                    {
                        "type": "error",
                        "message": f"错误: {exc}",
                        "retryable": False,
                    }
                )
            finally:
                await event_queue.put(stream_done)

        producer_task = asyncio.create_task(_produce_events())

        try:
            while True:
                event = await event_queue.get()
                if event is stream_done:
                    break
                yield event
        except asyncio.CancelledError:
            logger.info("流式事件消费被取消，准备中断下游图执行: session_id=%s", session_id)
            raise
        finally:
            if producer_task is not None and not producer_task.done():
                producer_task.cancel()
            if producer_task is not None:
                with suppress(asyncio.CancelledError):
                    await producer_task

            if source_iter is not None:
                with suppress(Exception):
                    await source_iter.aclose()


_agent_service: Optional[SQLAgentService] = None
_agent_service_lock: Optional[asyncio.Lock] = None


def _get_agent_service_lock() -> asyncio.Lock:
    """惰性创建 asyncio.Lock，避免模块导入时绑定错误事件循环。"""
    global _agent_service_lock
    if _agent_service_lock is None:
        _agent_service_lock = asyncio.Lock()
    return _agent_service_lock


async def initialize_agent_service(use_ollama: bool = False) -> SQLAgentService:
    """初始化模块级 Agent 单例。"""
    global _agent_service

    if _agent_service is not None:
        return _agent_service

    async with _get_agent_service_lock():
        if _agent_service is None:
            _agent_service = await SQLAgentService.create(use_ollama=use_ollama)
        return _agent_service


def get_agent_service() -> SQLAgentService:
    """获取已初始化的 Agent 服务实例。"""
    if _agent_service is None:
        raise RuntimeError("agent_service 尚未初始化，请先调用 initialize_agent_service()")
    return _agent_service


async def shutdown_agent_service() -> None:
    """关闭模块级 Agent 单例及其资源。"""
    global _agent_service

    if _agent_service is None:
        return

    async with _get_agent_service_lock():
        if _agent_service is None:
            return
        await _agent_service.aclose()
        _agent_service = None
