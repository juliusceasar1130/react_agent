# backend/app/agent/middleware/safe_merge_middleware.py
"""
终极安全合并中间件。

将 ModelRequest.system_message 和在历史对话 `messages` 首部或中间任意位置的 RAG 业务知识 SystemMessage，
安全高效地合并成唯一的一个全局 System 消息，以完美规避本地 vLLM 在 strict 格式下引发的多 system 400 报错。
"""

import logging
from typing import Callable, Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage, AIMessage
from langchain_core.runnables.config import ensure_config

from backend.app.agent.state import CustomState
from backend.app.config import settings

logger = logging.getLogger(__name__)


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


class SafeMergeSystemMiddleware(AgentMiddleware[CustomState]):
    """
    系统提示词与 RAG 背景知识终极合并中间件。
    """

    state_schema = CustomState

    def _project_and_collapse_messages(self, messages: list[Any]) -> list[Any]:
        """Memory-only projection of messages, collapsing old tool results outside the sliding window."""
        if not messages:
            return []

        # 1. Perform a shallow copy of messages to protect State messages
        projected = [msg for msg in messages]

        # 2. Count HumanMessages from the end to find the sliding window boundary
        protect_turns = settings.llm_context_collapse_protect_turns
        boundary_index = 0
        human_count = 0
        for idx in range(len(projected) - 1, -1, -1):
            if isinstance(projected[idx], HumanMessage):
                human_count += 1
                if human_count == protect_turns:
                    boundary_index = idx
                    break

        # 3. Collapse collapsible tool messages outside the sliding window
        for idx in range(boundary_index):
            msg = projected[idx]
            if isinstance(msg, ToolMessage) and msg.name in COLLAPSIBLE_TOOLS:
                # Process sql_db_query collapse
                if msg.name == "sql_db_query":
                    content_str = str(msg.content)
                    is_err = "Error" in content_str or "exception" in content_str.lower()
                    
                    if is_err:
                        projected[idx] = ToolMessage(
                            content="[SQL execution failed. Detailed error log collapsed. Re-run with corrected SQL if needed.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                    else:
                        projected[idx] = ToolMessage(
                            content="[SQL execution successful. Result content collapsed. Re-run query if details are needed.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                
                # Process search_saved_correct_tool_uses collapse
                elif msg.name == "search_saved_correct_tool_uses":
                    projected[idx] = ToolMessage(
                        content="[SQL examples retrieved and collapsed: reference examples shown in earlier step.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )
                
                # Process chart generation collapse
                elif msg.name == "build_chart_artifact":
                    projected[idx] = ToolMessage(
                        content="[Chart generated successfully. ECharts JSON config collapsed.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )
                
                # Process CSV export collapse
                elif msg.name in ("export_to_csv", "export_query_to_csv"):
                    projected[idx] = ToolMessage(
                        content="[CSV export completed and collapsed. User has already received the download link.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )

        return projected

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
                    "🛡️ SafeMergeSystemMiddleware: 成功将客户端运行时思考参数 %s 注入到模型网络调用中", 
                    client_enable_thinking
                )
        except Exception as e:
            logger.warning("🛡️ SafeMergeSystemMiddleware: 动态注入思考模式参数失败: %s", e)

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        # 新增首部调用：动态注入客户端思考模式配置
        self._inject_thinking_config(request)
        
        raw_messages = list(request.messages) if request.messages else []
        projected_messages = self._project_and_collapse_messages(raw_messages)

        filtered_messages = []
        rag_texts = []

        # 1. 深度遍历全量历史消息队列，定位并抽干所有的 RAG SystemMessage
        for msg in projected_messages:
            if isinstance(msg, SystemMessage):
                content = getattr(msg, "content", "")
                is_rag = False
                
                if isinstance(content, str) and "__business_rag_context__" in content:
                    is_rag = True
                elif hasattr(msg, "content_blocks"):
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if "__business_rag_context__" in block.get("text", ""):
                                is_rag = True
                                break

                if is_rag:
                    # 提取该条 RAG 消息的纯文本内容，存入暂存器
                    rag_text = _get_string_content(msg)
                    if rag_text:
                        rag_texts.append(rag_text)
                    # ⚠️ 注意：此处故意不将该消息放入 filtered_messages，以实现彻底的物理抽干！
                    continue

            # 保留其他所有普通消息
            filtered_messages.append(msg)

        # 获取原始 system_message 文本
        sys_text = _get_string_content(request.system_message)

        # 动态获取当前日期和时间并准备注入模板
        import datetime
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"\n\n[系统提示: {date_str}]"

        # 2. 如果检索到了任何 RAG 消息，执行物理合并与对话历史大一统抽干
        if rag_texts:
            logger.info(f"🛡️ SafeMergeSystemMiddleware: 全局打捞检测到 {len(rag_texts)} 条 RAG 消息，正在开启安全自愈合并...")
            
            # 提取全局核心提示词与所有搜集到的 RAG 消息的纯文本
            merged_rag_text = "\n\n".join(rag_texts)
            
            # 用纯文本大一统构筑 SystemMessage，并保证当前日期在整个提示词的最末尾
            merged_content = f"{sys_text}\n\n{merged_rag_text}{date_prompt}"
            new_system_message = SystemMessage(content=merged_content)
            
            logger.info(
                "🛡️ SafeMergeSystemMiddleware: 多 System 消息全量打捞合并完成，"
                "已将所有 RAG 消息规范化为纯文本 SystemMessage 并从 messages 列表中彻底抽干物理抹除！"
            )
            return request.override(
                system_message=new_system_message,
                messages=filtered_messages
            )

        new_system_message = SystemMessage(content=f"{sys_text}{date_prompt}")
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
