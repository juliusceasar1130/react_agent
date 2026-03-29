# backend/app/services.py
"""
FastAPI 兼容 Agent 服务适配层。

修改时间: 2026-03-27 20:40 Asia/Shanghai
主要修改内容:
- 本地 FastAPI 改为异步生命周期管理，不再在模块导入时立即初始化 Agent
- 切回 ainvoke / astream，并继续保留结构化流式事件协议
- 新增 initialize/get/shutdown 三段式单例管理，便于 startup/shutdown 中显式控制资源
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.app.agent.service import SQLAgentService as CoreSQLAgentService

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

    @staticmethod
    def _build_config(session_id: str, config: Optional[dict]) -> dict:
        """构造 LangGraph 会话配置。"""
        if config is not None:
            return config
        return {"configurable": {"thread_id": str(session_id)}}

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
        name: str = "",
        args: Any = None,
        args_text_delta: str = "",
    ) -> dict[str, Any]:
        """更新工具调用聚合信息。"""
        existing = tool_calls.get(
            tool_call_id,
            {
                "id": tool_call_id,
                "name": "",
                "args": {},
                "args_text": "",
            },
        )

        if name:
            existing["name"] = name
        if args is not None:
            existing["args"] = self._normalize_tool_args(args)
        if args_text_delta:
            existing["args_text"] = f"{existing.get('args_text', '')}{args_text_delta}"
            parsed = self._safe_load_json(existing["args_text"])
            if parsed is not None:
                existing["args"] = parsed

        tool_calls[tool_call_id] = existing
        return existing

    def _collect_tool_calls_from_message(
        self,
        message: Any,
        tool_calls: dict[str, dict[str, Any]],
    ) -> None:
        """从 AIMessage / 完整消息中提取工具调用。"""
        raw_tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in raw_tool_calls:
            try:
                tool_call_id = tool_call["id"] if tool_call.get("id") else ""
                tool_name = tool_call["name"] if tool_call.get("name") else ""
                if not tool_call_id or not tool_name:
                    continue

                self._upsert_tool_call(
                    tool_calls,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    args=tool_call.get("args"),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                logger.warning("提取工具调用信息失败: %s", exc)

    def _collect_tool_call_chunk_events(
        self,
        message: Any,
        tool_calls: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """从流式消息块中提取 tool_call_chunk 事件。"""
        events: list[dict[str, Any]] = []
        for block in self._iter_content_blocks(message):
            if block.get("type") != "tool_call_chunk":
                continue

            block_index = block.get("index", 0)
            tool_call_id = block.get("id") or f"tool_call_chunk_{block_index}"
            is_new = tool_call_id not in tool_calls
            tool_info = self._upsert_tool_call(
                tool_calls,
                tool_call_id=tool_call_id,
                name=block.get("name") or "",
                args_text_delta=block.get("args") or "",
            )

            if not tool_info.get("name") and not tool_info.get("args_text"):
                continue

            events.append(
                {
                    "type": "tool_call",
                    "id": tool_info["id"],
                    "name": tool_info.get("name") or f"tool_call_{block_index}",
                    "args_text": tool_info.get("args_text") or "",
                    "status": "started" if is_new else "streaming",
                }
            )

        return events

    def _collect_tool_result_event(
        self,
        message: Any,
        tool_results: dict[str, str],
    ) -> Optional[dict[str, Any]]:
        """从 ToolMessage 中提取工具结果事件。"""
        if not isinstance(message, ToolMessage):
            return None

        content = self._extract_message_content(message)
        if not message.tool_call_id or not content:
            return None

        previous = tool_results.get(message.tool_call_id)
        tool_results[message.tool_call_id] = content

        if previous == content:
            return None

        return {
            "type": "tool_result",
            "id": message.tool_call_id,
            "content": content,
        }

    @staticmethod
    def _serialize_tool_calls(
        tool_calls: dict[str, dict[str, Any]],
        *,
        final: bool = False,
    ) -> list[dict[str, Any]]:
        """将工具调用聚合结果序列化为列表。"""
        serialized = []
        for item in tool_calls.values():
            serialized.append(
                {
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "args": item.get("args", {}) or {},
                    "args_text": item.get("args_text", "") or "",
                    "status": "completed" if final else (item.get("status") or "streaming"),
                }
            )
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
                tool_result_event = self._collect_tool_result_event(message, tool_results)
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

            # 兼容 subgraphs=True 时可能出现的 (namespace, mode, data) 形状。
            if (
                len(chunk) == 3
                and isinstance(chunk[1], str)
            ):
                return chunk[1], chunk[2]

        return None, chunk

    @staticmethod
    def _status_signature(event: dict[str, Any]) -> tuple[str, str, str]:
        """构建状态事件签名，用于去重。"""
        return (
            event.get("stage", ""),
            event.get("text", ""),
            event.get("source", ""),
        )

    async def process_message(
        self, message: str, session_id: str, config: dict = None
    ) -> Dict[str, Any]:
        """处理用户消息（非流式）。"""
        try:
            resolved_config = self._build_config(session_id, config)
            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=message)]},
                config=resolved_config,
            )

            content, tool_calls, tool_results = self._extract_tool_data_from_result(
                result
            )

            return {
                "content": content,
                "tool_calls": json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                "tool_results": json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
            }

        except Exception as exc:
            logger.error("处理消息失败: %s", exc, exc_info=True)
            return {
                "content": f"处理消息时出错: {exc}",
                "tool_calls": None,
                "tool_results": None,
            }

    async def process_stream(
        self, message: str, session_id: str, config: dict = None
    ) -> AsyncIterator[dict[str, Any]]:
        """流式处理用户消息，输出结构化事件。"""
        try:
            resolved_config = self._build_config(session_id, config)
            logger.info("开始流式处理，消息: %s...", message[:100])

            accumulated_text: list[str] = []
            accumulated_tool_calls: dict[str, dict[str, Any]] = {}
            accumulated_tool_results: dict[str, str] = {}
            final_text_fallback = ""
            last_status_signature: Optional[tuple[str, str, str]] = None

            initial_status = {
                "type": "status",
                "stage": "thinking",
                "text": "正在分析问题",
                "source": "agent",
            }
            yield initial_status
            last_status_signature = self._status_signature(initial_status)

            async for chunk in self.agent.astream(
                {"messages": [HumanMessage(content=message)]},
                config=resolved_config,
                stream_mode=["messages", "updates", "custom"],
                version="v2",
            ):
                if not chunk:
                    continue

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

                    for text_segment in self._extract_text_segments(message_chunk):
                        if not text_segment:
                            continue
                        accumulated_text.append(text_segment)
                        yield {
                            "type": "token",
                            "text": text_segment,
                            "node": node_name,
                        }

                    for event in self._collect_tool_call_chunk_events(
                        message_chunk,
                        accumulated_tool_calls,
                    ):
                        yield event

                    tool_result_event = self._collect_tool_result_event(
                        message_chunk,
                        accumulated_tool_results,
                    )
                    if tool_result_event:
                        yield tool_result_event

                elif chunk_type == "updates" and isinstance(chunk_data, dict):
                    for node_name, state_update in chunk_data.items():
                        status_event = self._build_status_event(
                            node_name,
                            has_tool_results=bool(accumulated_tool_results),
                            has_tokens=bool(accumulated_text),
                        )
                        if status_event:
                            status_signature = self._status_signature(status_event)
                            if status_signature != last_status_signature:
                                yield status_event
                                last_status_signature = status_signature

                        if not isinstance(state_update, dict):
                            continue

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
                            )
                            if not getattr(last_message, "tool_calls", None):
                                final_text_fallback = self._extract_message_content(
                                    last_message
                                )

                        tool_result_event = self._collect_tool_result_event(
                            last_message,
                            accumulated_tool_results,
                        )
                        if tool_result_event:
                            yield tool_result_event

                elif chunk_type == "custom":
                    custom_event = self._normalize_custom_event(chunk_data)
                    if not custom_event:
                        continue

                    if custom_event.get("type") == "status":
                        status_signature = self._status_signature(custom_event)
                        if status_signature == last_status_signature:
                            continue
                        last_status_signature = status_signature

                    yield custom_event

            final_content = "".join(accumulated_text) or final_text_fallback
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
            yield {
                "type": "final",
                "content": final_content,
                "tool_calls": tool_calls or None,
                "tool_results": accumulated_tool_results or None,
            }

        except Exception as exc:
            logger.error("流式处理失败: %s", exc, exc_info=True)
            yield {
                "type": "error",
                "message": f"错误: {exc}",
                "retryable": False,
            }

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
