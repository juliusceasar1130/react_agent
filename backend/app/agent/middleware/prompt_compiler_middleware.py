# backend/app/agent/middleware/prompt_compiler_middleware.py
"""
系统提示词与 RAG 背景知识终极编译合并中间件（提示词编译器）。

将静态系统提示词模版、已激活技能的 DDL 及 Gotchas、已加载的辅助技能 Skeleton 骨架，
以及在 CustomState 中传递的 RAG 检索上下文和系统日期，安全高效地合并成唯一的一个全局 System 消息，
以完美规避本地 vLLM 在 strict 格式下引发的多 system 400 报错。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage, AIMessage
from langchain_core.runnables.config import ensure_config

from backend.app.agent.state import CustomState
from backend.app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _CollapseContext:
    """Pipeline shared context for boundary, deletion, and collapse tracking."""
    messages: list[Any]
    boundary_index: int = 0
    deleted_call_ids: set[str] = field(default_factory=set)
    kept_call_ids: set[str] = field(default_factory=set)
    redacted_count: int = 0
    kept_count: int = 0
    deleted_count: int = 0


# 定义需折叠替换的白名单工具名
COLLAPSIBLE_TOOLS = {
    "sql_db_query",
    "search_saved_correct_tool_uses",
    "build_chart_artifact",
    "export_to_csv",
    "export_query_to_csv"
}


def _get_string_content(msg) -> str:
    """安全地将 SystemMessage 的 content (可能是 str 或 List[Dict/Str]) 转换为纯文本字符串。"""
    if msg is None:
        return ""
    
    # 1. 优先读取 content_blocks 结构块属性
    content_blocks = getattr(msg, "content_blocks", None)
    if isinstance(content_blocks, list):
        texts = []
        for block in content_blocks:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    texts.append(block["text"])
                elif "text" in block:
                    texts.append(block["text"])
                else:
                    texts.append(str(block))
        return "\n".join(texts)

    # 2. 备用读取 content 属性
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    texts.append(block["text"])
                elif "text" in block:
                    texts.append(block["text"])
                else:
                    texts.append(str(block))
        return "\n".join(texts)
    return str(content)


class PromptCompilerMiddleware(AgentMiddleware[CustomState]):
    """
    系统提示词与 RAG 背景知识终极合并中间件。
    """

    state_schema = CustomState

    def _project_and_collapse_messages(self, messages: list[Any]) -> list[Any]:
        """
        5-stage Pipeline: boundary → prescan → redaction → physical deletion → standard collapse.
        """
        if not messages:
            return []

        # Stage 1: Compute sliding window boundary
        boundary_index = self._stage_compute_boundary(messages)
        ctx = _CollapseContext(messages=messages, boundary_index=boundary_index)

        # Stage 2: Pre-scan window-out failed tools
        self._stage_prescan_failures(ctx)

        # Stage 3: Redaction (Linter failure handling)
        projected = self._stage_redaction(messages, ctx)

        # Stage 4: Physical deletion of failed pairs
        after_deletion = self._stage_physical_deletion(projected, ctx)

        # Stage 5: Standard collapse for remaining tools
        final = self._stage_standard_collapse(after_deletion, ctx)

        # Logging
        self._log_collapse_results(ctx)

        return final

    def _stage_compute_boundary(self, messages: list[Any]) -> int:
        """Stage 1: Compute sliding window boundary from the end."""
        protect_turns = settings.llm_context_collapse_protect_turns
        human_count = 0
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                human_count += 1
                if human_count == protect_turns:
                    return idx
        return 0

    _DELETION_TARGET_CONFIG = {
        "sql_db_query": {
            "has_linter": True,
            "has_runtime": True,
            "runtime_header": "X-SQL-EXECUTION-STATUS: FAILED",
        },
        "build_chart_artifact": {
            "has_linter": False,
            "has_runtime": True,
            "runtime_header": "X-CHART-STATUS: FAILED",
        },
    }

    def _stage_prescan_failures(self, ctx: _CollapseContext) -> None:
        """Stage 2: Pre-scan window-out messages for failed tool calls."""
        for idx in range(ctx.boundary_index):
            msg = ctx.messages[idx]
            if not isinstance(msg, ToolMessage):
                continue
            if msg.name not in self._DELETION_TARGET_CONFIG:
                continue

            config = self._DELETION_TARGET_CONFIG[msg.name]
            content_str = str(msg.content)
            is_failed = False

            if config["has_linter"] and "X-SQL-LINTER-STATUS: FAILED" in content_str:
                is_failed = True
            elif config["has_runtime"] and config["runtime_header"] in content_str:
                is_failed = True
            else:
                # Fallback: JSON success detection + keyword matching
                is_json_success = False
                try:
                    import json
                    data = json.loads(content_str)
                    if isinstance(data, list):
                        is_json_success = True
                except Exception:
                    pass

                if not is_json_success:
                    is_failed = (
                        "error" in content_str.lower() or
                        "exception" in content_str.lower() or
                        "failed" in content_str.lower()
                    )

            if is_failed:
                ctx.deleted_call_ids.add(msg.tool_call_id)

    def _find_last_human_index(self, messages: list[Any]) -> int:
        """返回最后一条 HumanMessage 的索引，找不到返回 0。"""
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                return idx
        return 0

    def _stage_redaction(self, messages: list[Any], ctx: _CollapseContext) -> list[Any]:
        """Stage 3: Redact past Linter failures, keeping last N as correction clues within current ReAct loop."""
        projected = list(messages)
        last_human_idx = self._find_last_human_index(projected)
        keep_count = settings.llm_context_redaction_keep_count

        # Only scan sql_db_query messages within the current ReAct loop (after last HumanMessage)
        sql_tool_infos = []
        for idx in range(last_human_idx, len(projected)):
            msg = projected[idx]
            if isinstance(msg, ToolMessage) and msg.name == "sql_db_query":
                content_str = str(msg.content)
                is_linter_error = (
                    "X-SQL-LINTER-STATUS: FAILED" in content_str or
                    "validation failed by Linter" in content_str or
                    ("Linter 拦截" in content_str or "SQL Linter" in content_str)
                )
                is_runtime_error = (
                    "error" in content_str.lower() or
                    "exception" in content_str.lower()
                )
                is_failed = is_linter_error or is_runtime_error

                sql_tool_infos.append({
                    "idx": idx,
                    "tool_call_id": msg.tool_call_id,
                    "is_linter_error": is_linter_error,
                    "is_failed": is_failed,
                })

        # Find successful SQL in current ReAct loop
        last_success_idx = -1
        for idx_in_list in range(len(sql_tool_infos) - 1, -1, -1):
            if not sql_tool_infos[idx_in_list]["is_failed"]:
                last_success_idx = idx_in_list
                break

        # Collect failed call_ids AFTER the last success in current ReAct loop, keep last N
        ctx.kept_call_ids = set()
        active_failed_ids = []
        if last_success_idx == -1:
            active_failed_ids = [
                info["tool_call_id"] for info in sql_tool_infos if info["is_failed"]
            ]
        else:
            active_failed_ids = [
                info["tool_call_id"] for info in sql_tool_infos[last_success_idx + 1:] if info["is_failed"]
            ]

        if active_failed_ids:
            ctx.kept_call_ids = set(active_failed_ids[-keep_count:])

        # Redact failures not in kept set (scans all messages, not just current loop)
        for idx in range(len(projected)):
            msg = projected[idx]
            if not (isinstance(msg, ToolMessage) and msg.name == "sql_db_query"):
                continue

            content_str = str(msg.content)
            is_linter_error = (
                "X-SQL-LINTER-STATUS: FAILED" in content_str or
                "validation failed by Linter" in content_str or
                ("Linter 拦截" in content_str or "SQL Linter" in content_str)
            )

            if is_linter_error:
                should_redact = msg.tool_call_id not in ctx.kept_call_ids
                if should_redact:
                    ctx.redacted_count += 1
                    projected[idx] = ToolMessage(
                        content="[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )
                    for back_idx in range(idx - 1, -1, -1):
                        aimsg = projected[back_idx]
                        if isinstance(aimsg, AIMessage) and hasattr(aimsg, "tool_calls"):
                            if any(tc.get("id") == msg.tool_call_id for tc in aimsg.tool_calls):
                                projected[back_idx] = AIMessage(
                                    content="[Invalid SQL attempt. Redacted to save context space.]",
                                    tool_calls=aimsg.tool_calls
                                )
                                break
                else:
                    ctx.kept_count += 1

        return projected

    def _stage_physical_deletion(self, projected: list[Any], ctx: _CollapseContext) -> list[Any]:
        """Stage 4: Physically delete failed tool call pairs (AIMessage + ToolMessage)."""
        if not ctx.deleted_call_ids:
            return projected

        filtered = []
        for msg in projected:
            if isinstance(msg, ToolMessage) and msg.tool_call_id in ctx.deleted_call_ids:
                ctx.deleted_count += 1
                continue

            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                remaining_tool_calls = []
                for tc in msg.tool_calls:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tc_id not in ctx.deleted_call_ids:
                        remaining_tool_calls.append(tc)

                if not remaining_tool_calls:
                    ctx.deleted_count += 1
                    continue

                if len(remaining_tool_calls) != len(msg.tool_calls):
                    msg = AIMessage(
                        content=msg.content,
                        tool_calls=remaining_tool_calls,
                        id=getattr(msg, "id", None)
                    )

            filtered.append(msg)

        return filtered

    def _stage_standard_collapse(self, messages: list[Any], ctx: _CollapseContext) -> list[Any]:
        """Stage 5: Collapse remaining COLLAPSIBLE_TOOLS outside the sliding window."""
        for idx in range(len(messages)):
            msg = messages[idx]
            if not (isinstance(msg, ToolMessage) and msg.name in COLLAPSIBLE_TOOLS):
                continue
            if msg.tool_call_id in ctx.kept_call_ids:
                continue
            if idx >= ctx.boundary_index:
                continue

            if msg.name == "sql_db_query":
                messages[idx] = ToolMessage(
                    content="[SQL execution successful. Result content collapsed. Re-run query if details are needed.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name == "search_saved_correct_tool_uses":
                messages[idx] = ToolMessage(
                    content="[SQL examples retrieved and collapsed: reference examples shown in earlier step.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name == "build_chart_artifact":
                messages[idx] = ToolMessage(
                    content="[Chart generated successfully. ECharts JSON config collapsed.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name in ("export_to_csv", "export_query_to_csv"):
                messages[idx] = ToolMessage(
                    content="[CSV export completed and collapsed. User has already received the download link.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )

        return messages

    def _log_collapse_results(self, ctx: _CollapseContext) -> None:
        """Emit audit logs for redaction and physical deletion stages."""
        if ctx.redacted_count > 0 or ctx.kept_count > 0:
            logger.info(
                "🛡️ Redaction: %d failures redacted, %d kept as correction clue. Kept call_ids: %s",
                ctx.redacted_count, ctx.kept_count, ctx.kept_call_ids
            )
        if ctx.deleted_call_ids:
            logger.info(
                "🗑️ Paired physical deletion: %d failed pairs removed. Deleted call_ids: %s",
                len(ctx.deleted_call_ids), ctx.deleted_call_ids
            )

    def _inject_thinking_config(self, request: ModelRequest) -> None:
        """从当前协程的运行时上下文(ContextVar)中，打捞客户端传过来的思考模式，并动态覆写网络发包参数"""
        try:
            # 1. 自动捕获当前协程专属的运行期配置
            runnable_config = ensure_config()
            configurable = runnable_config.get("configurable") or {}
            client_enable_thinking = configurable.get("enable_thinking")
            
            # 2. 如果客户端显式指定了参数，我们对当次模型请求参数进行安全改写
            if client_enable_thinking is not None:
                if request.model_settings is None:
                    request.model_settings = {}
                    
                if "extra_body" not in request.model_settings:
                    request.model_settings["extra_body"] = {}
                    
                extra_body = request.model_settings["extra_body"]
                if "chat_template_kwargs" not in extra_body:
                    extra_body["chat_template_kwargs"] = {}
                    
                # 动态改写 chat_template_kwargs，保证在网络包的根层级发出
                extra_body["chat_template_kwargs"]["enable_thinking"] = client_enable_thinking
                logger.info(
                    "🛡️ PromptCompilerMiddleware: 成功将客户端运行时思考参数 %s 注入到模型网络调用中", 
                    client_enable_thinking
                )
        except Exception as e:
            logger.warning("🛡️ PromptCompilerMiddleware: 动态注入思考模式参数失败: %s", e)

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """读取 state 中的 RAG 文本直接拼装至系统消息，并清理历史留存的 RAG 污染消息"""
        self._inject_thinking_config(request)
        
        raw_messages = list(request.messages) if request.messages else []
        projected_messages = self._project_and_collapse_messages(raw_messages)

        # 1. 直接从 request.state 中获取结构化 RAG 文本
        lexicon_ctx = request.state.get("lexicon_context") if request.state else {}
        if not lexicon_ctx:
            lexicon_ctx = {}
        rag_text = lexicon_ctx.get("formatted_text", "")

        # 2. 防御性过滤历史数据库中可能残留的老旧 RAG 消息 (向下兼容)
        filtered_messages = []
        for msg in projected_messages:
            if isinstance(msg, SystemMessage):
                content = getattr(msg, "content", "")
                if isinstance(content, str) and "__business_rag_context__" in content:
                    continue
                elif hasattr(msg, "content_blocks"):
                    is_legacy_rag = False
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if "__business_rag_context__" in block.get("text", ""):
                                is_legacy_rag = True
                                break
                    if is_legacy_rag:
                        continue
            filtered_messages.append(msg)

        # 3. 解析 content_blocks 区分静态与动态部分
        blocks = getattr(request.system_message, "content_blocks", None)
        base_sys_text = ""
        skills_addendum = ""
        active_ddl = ""
        secondary_ddl = ""

        if isinstance(blocks, list) and len(blocks) > 0:
            base_sys_text = blocks[0].get("text", "") if isinstance(blocks[0], dict) else str(blocks[0])
            for block in blocks[1:]:
                text = block.get("text", "") if isinstance(block, dict) else str(block)
                if "## Available Skills" in text:
                    skills_addendum = text
                elif "## Active Domain Knowledge" in text:
                    active_ddl = text
                elif "## Secondary Domain Knowledge" in text:
                    secondary_ddl = text
        else:
            base_sys_text = _get_string_content(request.system_message)

        # 4. 组装静态区 (System Rules)
        static_parts = [base_sys_text]
        if skills_addendum:
            static_parts.append(skills_addendum)
        system_rules_content = "\n\n".join(static_parts).strip()
        system_rules_xml = f"<system_rules>\n{system_rules_content}\n</system_rules>"

        # 5. 组装动态区 (Runtime Context)
        import datetime
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"[系统提示: {date_str}]"

        dynamic_parts = [date_prompt]
        if active_ddl:
            dynamic_parts.append(active_ddl.strip())
        if secondary_ddl:
            dynamic_parts.append(secondary_ddl.strip())
        if rag_text:
            dynamic_parts.append(rag_text.strip())
            
        runtime_context_content = "\n\n".join(dynamic_parts).strip()
        runtime_context_xml = f"<runtime_context>\n{runtime_context_content}\n</runtime_context>"

        # 6. 合并编译并重载 ModelRequest
        compiled_content = f"{system_rules_xml}\n\n{runtime_context_xml}"
        new_system_message = SystemMessage(content=compiled_content)
        
        logger.info("🛡️ PromptCompilerMiddleware: 静态/动态双分区编译合并完成。")
        return request.override(
            system_message=new_system_message,
            messages=filtered_messages
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """同步运行链路"""
        modified_request = self._modify_request(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """异步运行链路"""
        modified_request = self._modify_request(request)
        return await handler(modified_request)
