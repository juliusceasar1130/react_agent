# backend/app/services.py
from typing import List, Dict, Any, AsyncIterator
from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from langchain_community.agent_toolkits.load_tools import load_tools
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from .config import settings
import logging
import json

logger = logging.getLogger(__name__)


class ResearchAgentService:
    """研究助手Agent服务"""

    def __init__(self):
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self):
        """初始化Agent"""
        try:
            # 1. 初始化DeepSeek模型
            llm = ChatDeepSeek(
                model=settings.deepseek_model,
                temperature=settings.agent_temperature,
                max_tokens=settings.agent_max_tokens,
                timeout=None,
                max_retries=2,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )

            # 2. 加载工具（保持原样）
            tools = load_tools(["arxiv"], llm=llm)

            # 3. 创建Agent
            system_prompt = """你是一个专业的研究助手，专门帮助用户查找、理解和总结学术论文。
            你可以使用以下工具：
            1. arxiv - 在arXiv上搜索和获取学术论文
            
            请按照以下步骤帮助用户：
            1. 理解用户的研究需求
            2. 使用合适的工具搜索相关论文
            3. 提供论文的关键信息：标题、作者、摘要、关键贡献
            4. 如果用户要求，可以提供论文的详细总结
            5. 保持回答专业、准确、有用
            
            **重要提示**：
            - 优先搜索最近2-3年的论文
            - 使用具体的搜索词，避免过于宽泛的查询
            - 最多搜索2-3次，避免过多API调用
            
            记住：始终用中文回答，除非用户特别要求使用其他语言。
            """

            self.agent = create_agent(
                model=llm, tools=tools, system_prompt=system_prompt
            )

            logger.info("Agent初始化成功")

        except Exception as e:
            logger.error(f"Agent初始化失败: {e}")
            raise

    async def process_message(
        self, message: str, history: List[Dict] = None
    ) -> Dict[str, Any]:
        """处理用户消息（非流式）"""
        try:
            if not self.agent:
                self._initialize_agent()

            # 准备消息历史
            langchain_messages = []
            if history:
                for i, msg in enumerate(history):
                    logger.info(f"历史消息 {i}: role={msg['role']}, content长度={len(msg.get('content', ''))}, tool_calls={msg.get('tool_calls')}")

                    if msg["role"] == "user":
                        content = msg.get("content", "")
                        if content:  # 只添加非空内容
                            langchain_messages.append(HumanMessage(content=content))
                        else:
                            logger.warning(f"跳过空内容的用户消息 {i}")

                    elif msg["role"] == "assistant":
                        content = msg.get("content", "")
                        # 确保内容不为空 - 2025-01-01
                        if not content:
                            content = ""
                            logger.warning(f"Assistant 消息 {i} 内容为空，使用空字符串")

                        # 不恢复 tool_calls，让 agent 根据对话内容重新决定是否调用工具 - 2025-01-01
                        # 原因：tool_calls 必须紧跟 tool 消息，但我们没有独立的 tool 消息
                        # 而且 tool_results 可能已过时（如 arXiv 搜索结果）
                        tool_calls_data = msg.get("tool_calls")
                        if tool_calls_data:
                            logger.info(f"Assistant 消息 {i} 包含 tool_calls，但不恢复（让 agent 重新执行工具）")
                        langchain_messages.append(AIMessage(content=content))

                    elif msg["role"] == "tool" and msg.get("content"):
                        tool_call_id = msg.get("tool_call_id", "")
                        content = msg.get("content", "")
                        if tool_call_id and content:
                            langchain_messages.append(
                                ToolMessage(
                                    content=content,
                                    tool_call_id=tool_call_id,
                                )
                            )

            logger.info(f"准备好的历史消息数量: {len(langchain_messages)}")

            # 添加当前消息
            langchain_messages.append(HumanMessage(content=message))

            # 调用Agent（非流式）
            input_data = {"messages": langchain_messages}
            result = self.agent.invoke(input_data)

            # 提取最后一条消息内容
            messages = result.get("messages", [])
            last_message = messages[-1] if messages else None
            content = last_message.content if hasattr(last_message, "content") else ""

            # 提取工具调用信息
            tool_calls = []
            tool_results = {}

            logger.info(f"处理消息列表，共 {len(messages)} 条消息")

            for i, msg in enumerate(messages):
                logger.debug(f"消息 {i}: 类型={type(msg).__name__}, hasattr tool_calls={hasattr(msg, 'tool_calls')}")

                if isinstance(msg, AIMessage):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        logger.info(f"发现 AIMessage 包含 {len(msg.tool_calls)} 个工具调用")
                        for tool_call in msg.tool_calls:
                            # ToolCall 是对象，用字典方式访问属性 - 2025-01-01
                            try:
                                tool_info = {
                                    "name": tool_call["name"] if tool_call["name"] else "",
                                    "args": dict(tool_call["args"]) if tool_call["args"] else {},
                                    "id": tool_call["id"] if tool_call["id"] else "",
                                }
                                # 只添加有效的工具调用（有 name 和 id）- 2025-01-01
                                if tool_info["name"] and tool_info["id"]:
                                    tool_calls.append(tool_info)
                                    logger.info(f"提取工具调用: {tool_info['name']} - {tool_info['id']}")
                            except (KeyError, TypeError) as e:
                                logger.warning(f"提取工具调用信息失败: {e}")

                elif isinstance(msg, ToolMessage):
                    if msg.tool_call_id and msg.content:
                        tool_results[msg.tool_call_id] = msg.content
                        logger.info(f"提取工具结果: {msg.tool_call_id} - 长度={len(msg.content)}")

            logger.info(f"提取完成：tool_calls={len(tool_calls)} 个, tool_results={len(tool_results)} 个")

            # 将tool_calls和tool_results转换为字符串存储
            tool_calls_str = json.dumps(tool_calls) if tool_calls else None
            tool_results_str = json.dumps(tool_results) if tool_results else None

            return {
                "content": content,
                "tool_calls": tool_calls_str,
                "tool_results": tool_results_str,
            }

        except Exception as e:
            logger.error(f"处理消息失败: {e}", exc_info=True)
            return {
                "content": f"处理消息时出错: {str(e)}",
                "tool_calls": None,
                "tool_results": None,
            }

    async def process_stream(self, message: str, history: List[Dict] = None):
        """真正的流式处理用户消息"""
        try:
            if not self.agent:
                self._initialize_agent()

            # 准备消息历史
            langchain_messages = []
            if history:
                for i, msg in enumerate(history):
                    logger.info(f"流式历史消息 {i}: role={msg['role']}, content长度={len(msg.get('content', ''))}, tool_calls={msg.get('tool_calls')}")

                    if msg["role"] == "user":
                        content = msg.get("content", "")
                        if content:  # 只添加非空内容
                            langchain_messages.append(HumanMessage(content=content))
                        else:
                            logger.warning(f"流式跳过空内容的用户消息 {i}")

                    elif msg["role"] == "assistant":
                        content = msg.get("content", "")
                        # 确保内容不为空 - 2025-01-01
                        if not content:
                            content = ""
                            logger.warning(f"流式 Assistant 消息 {i} 内容为空，使用空字符串")

                        # 不恢复 tool_calls，让 agent 根据对话内容重新决定是否调用工具 - 2025-01-01
                        # 原因：tool_calls 必须紧跟 tool 消息，但我们没有独立的 tool 消息
                        # 而且 tool_results 可能已过时（如 arXiv 搜索结果）
                        tool_calls_data = msg.get("tool_calls")
                        if tool_calls_data:
                            logger.info(f"流式 Assistant 消息 {i} 包含 tool_calls，但不恢复（让 agent 重新执行工具）")
                        langchain_messages.append(AIMessage(content=content))

                    elif msg["role"] == "tool" and msg.get("content"):
                        tool_call_id = msg.get("tool_call_id", "")
                        content = msg.get("content", "")
                        if tool_call_id and content:
                            langchain_messages.append(
                                ToolMessage(
                                    content=content,
                                    tool_call_id=tool_call_id,
                                )
                            )

            logger.info(f"准备好的流式历史消息数量: {len(langchain_messages)}")

            # 添加当前消息
            langchain_messages.append(HumanMessage(content=message))

            logger.info(f"开始真正的流式处理，消息: {message[:100]}...")

            # 转换消息格式
            input_messages = []
            for msg in langchain_messages:
                if isinstance(msg, HumanMessage):
                    input_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    input_messages.append({"role": "assistant", "content": msg.content})
                elif isinstance(msg, ToolMessage):
                    input_messages.append(
                        {
                            "role": "tool",
                            "content": msg.content,
                            "tool_call_id": msg.tool_call_id,
                        }
                    )

            logger.info(f"输入消息数量: {len(input_messages)}")

            # 使用 agent.stream() 实现真正的流式
            # 参考您提供的代码：for chunk in agent.stream(... , stream_mode="messages")
            full_content = ""
            accumulated_tool_calls = []

            try:
                # 这里的关键：使用 stream_mode="messages"
                for chunk in self.agent.stream(
                    {"messages": input_messages},
                    stream_mode="messages",  # token by token
                ):
                    # chunk 是一个元组 (message_chunk, metadata)
                    if chunk and len(chunk) > 0:
                        message_chunk = chunk[0]

                        # 记录chunk类型用于调试
                        chunk_type = type(message_chunk).__name__

                        # 检查是否是 AIMessageChunk
                        if hasattr(message_chunk, "content"):
                            chunk_content = message_chunk.content or ""
                            if chunk_content:
                                full_content += chunk_content
                                logger.debug(f"流式chunk内容: {chunk_content}")

                                # 发送内容块
                                yield {
                                    "content": chunk_content,
                                    "is_final": False,
                                    "tool_calls": None,
                                }

                        # 提取工具调用信息（如果有）
                        if (
                            hasattr(message_chunk, "tool_calls")
                            and message_chunk.tool_calls
                        ):
                            for tool_call in message_chunk.tool_calls:
                                # ToolCall 是对象，用字典方式访问属性 - 2025-01-01
                                try:
                                    tool_info = {
                                        "name": tool_call["name"] if tool_call["name"] else "",
                                        "args": dict(tool_call["args"]) if tool_call["args"] else {},
                                        "id": tool_call["id"] if tool_call["id"] else "",
                                    }
                                    # 只添加有效的工具调用（有 name 和 id）- 2025-01-01
                                    if tool_info["name"] and tool_info["id"]:
                                        accumulated_tool_calls.append(tool_info)
                                        logger.info(f"流式工具调用: {tool_info}")
                                except (KeyError, TypeError) as e:
                                    logger.warning(f"流式提取工具调用信息失败: {e}")

            except StopIteration:
                # 流式自然结束
                logger.info("流式处理自然结束")
                pass

            except Exception as e:
                logger.error(f"流式处理过程中出错: {e}", exc_info=True)
                raise

            # 发送最终消息
            logger.info(f"流式处理完成，总内容长度: {len(full_content)}")
            yield {
                "content": "",
                "is_final": True,
                "tool_calls": (
                    accumulated_tool_calls if accumulated_tool_calls else None
                ),
            }

        except Exception as e:
            logger.error(f"流式处理失败: {e}", exc_info=True)
            yield {"content": f"错误: {str(e)}", "is_final": True, "tool_calls": None}


# 创建全局Agent实例
agent_service = ResearchAgentService()
