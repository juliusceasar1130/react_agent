# backend/app/services.py
from typing import List, Dict, Any, AsyncIterator
from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_community.agent_toolkits.load_tools import load_tools
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from langgraph.checkpoint.postgres import PostgresSaver
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
            - 优先按用户的要求数量进行搜索，默认3篇
            - 使用具体的搜索词，避免过于宽泛的查询
            - 最多搜索2次，避免过多API调用

            记住：始终用中文回答，除非用户特别要求使用其他语言。
            """

            # ✅ 4. 初始化 PostgresSaver (2025-01-03)
            # 参考：https://docs.langchain.com/oss/python/langchain/short-term-memory
            # 修复：使用 psycopg_pool.ConnectionPool 获取连接池，然后创建 PostgresSaver

            from psycopg_pool import ConnectionPool

            # 创建连接池（保持连接打开）
            self.conn_pool = ConnectionPool(
                conninfo=settings.database_url, min_size=1, max_size=10, timeout=30
            )

            # 使用连接池创建 PostgresSaver
            self.checkpointer = PostgresSaver(self.conn_pool)

            try:
                self.checkpointer.setup()  # 首次使用自动创建表
                logger.info("PostgresSaver 检查点表初始化成功")
            except Exception as setup_error:
                logger.info(f"检查点表已存在或创建跳过: {setup_error}")

            # ✅ 5. 配置 SummarizationMiddleware (2025-01-03)
            summarization_middleware = SummarizationMiddleware(
                model=llm,  # 使用 DeepSeek 主模型
                trigger=("tokens", 4000),  # 当 token 数超过 4000 时触发
                keep=("messages", 5),  # 保留最近 20 条消息
            )

            # ✅ 6. 创建 Agent（添加 checkpointer 和 middleware）
            self.agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
                checkpointer=self.checkpointer,  # 新增：PostgresSaver 检查点
                middleware=[summarization_middleware],  # 新增：摘要中间件
            )

            logger.info(
                "Agent初始化成功（已启用 PostgresSaver 和 SummarizationMiddleware）"
            )

        except Exception as e:
            logger.error(f"Agent初始化失败: {e}")
            raise

    async def process_message(
        self, message: str, session_id: str, config: dict = None
    ) -> Dict[str, Any]:
        """处理用户消息（非流式）

        Args:
            message: 用户消息内容
            session_id: 会话 ID（对应 thread_id）
            config: Agent 配置（包含 thread_id）

        修改时间: 2025-01-03
        修改内容: 使用 PostgresSaver 自动管理历史，无需手动传递 history 参数
        """
        try:
            if not self.agent:
                self._initialize_agent()

            # ✅ PostgresSaver 自动管理历史，无需手动传递
            # 构建 config（如果没有提供）
            if config is None:
                config = {"configurable": {"thread_id": str(session_id)}}

            # ✅ 调用 Agent（传递 config，PostgresSaver 自动恢复状态）
            result = self.agent.invoke(
                {"messages": [HumanMessage(content=message)]}, config=config
            )

            # 提取最后一条消息内容
            messages = result.get("messages", [])
            last_message = messages[-1] if messages else None
            content = last_message.content if hasattr(last_message, "content") else ""

            # 提取工具调用信息
            tool_calls = []
            tool_results = {}

            # 2025-01-02: 从 intermediate_steps 提取工具调用和结果
            intermediate_steps = result.get("intermediate_steps", [])
            logger.info(f"中间步骤数量: {len(intermediate_steps)}")

            for step in intermediate_steps:
                # step 格式: (Action, Observation)
                # Action 包含 tool 和 tool_input
                # Observation 包含工具执行结果
                if len(step) >= 2:
                    action = step[0]
                    observation = step[1]

                    # 提取工具调用信息
                    tool_name = getattr(action, "tool", "")
                    tool_input = getattr(action, "tool_input", {})
                    tool_id = f"tool_{len(tool_calls)}"  # 生成一个唯一ID

                    if tool_name:
                        tool_calls.append(
                            {"name": tool_name, "args": tool_input, "id": tool_id}
                        )
                        logger.info(
                            f"从 intermediate_steps 提取工具调用: {tool_name}, args: {tool_input}"
                        )

                    # 提取工具执行结果
                    if observation:
                        tool_results[tool_id] = str(observation)
                        logger.info(
                            f"从 intermediate_steps 提取工具结果: {tool_id}, 长度={len(str(observation))}"
                        )

            logger.info(f"处理消息列表，共 {len(messages)} 条消息")

            # 2025-01-02: 如果 intermediate_steps 为空，尝试从 messages 列表提取
            if not intermediate_steps:
                for i, msg in enumerate(messages):
                    msg_type = type(msg).__name__
                    logger.info(
                        f"消息 {i}: 类型={msg_type}, content长度={len(getattr(msg, 'content', ''))}, "
                        f"hasattr tool_calls={hasattr(msg, 'tool_calls')}, "
                        f"is ToolMessage={isinstance(msg, ToolMessage)}"
                    )

                    if isinstance(msg, AIMessage):
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            logger.info(
                                f"发现 AIMessage 包含 {len(msg.tool_calls)} 个工具调用"
                            )
                            for tool_call in msg.tool_calls:
                                # ToolCall 是对象，用字典方式访问属性 - 2025-01-01
                                try:
                                    tool_info = {
                                        "name": (
                                            tool_call["name"]
                                            if tool_call["name"]
                                            else ""
                                        ),
                                        "args": (
                                            dict(tool_call["args"])
                                            if tool_call["args"]
                                            else {}
                                        ),
                                        "id": (
                                            tool_call["id"] if tool_call["id"] else ""
                                        ),
                                    }
                                    # 只添加有效的工具调用（有 name 和 id）- 2025-01-01
                                    if tool_info["name"] and tool_info["id"]:
                                        tool_calls.append(tool_info)
                                        logger.info(
                                            f"提取工具调用: {tool_info['name']} - {tool_info['id']}"
                                        )
                                except (KeyError, TypeError) as e:
                                    logger.warning(f"提取工具调用信息失败: {e}")

                    elif isinstance(msg, ToolMessage):
                        if msg.tool_call_id and msg.content:
                            tool_results[msg.tool_call_id] = msg.content
                            logger.info(
                                f"提取工具结果: {msg.tool_call_id} - 长度={len(msg.content)}"
                            )

            logger.info(
                f"提取完成：tool_calls={len(tool_calls)} 个, tool_results={len(tool_results)} 个"
            )

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

    async def process_stream(self, message: str, session_id: str, config: dict = None):
        """流式处理用户消息

        Args:
            message: 用户消息内容
            session_id: 会话 ID（对应 thread_id）
            config: Agent 配置（包含 thread_id）

        修改时间: 2025-01-03
        修改内容: 使用 PostgresSaver 自动管理历史，无需手动传递 history 参数
        """
        try:
            if not self.agent:
                self._initialize_agent()

            # ✅ PostgresSaver 自动管理历史，无需手动传递
            # 构建 config（如果没有提供）
            if config is None:
                config = {"configurable": {"thread_id": str(session_id)}}

            logger.info(f"开始流式处理，消息: {message[:100]}...")

            # 使用 agent.stream() 实现真正的流式
            # 参考文档：for chunk in agent.stream(... , stream_mode="messages")
            full_content = ""
            accumulated_tool_calls = []
            accumulated_tool_results = {}

            try:
                # ✅ 这里的关键：使用 stream_mode="messages" 并传递 config
                for chunk in self.agent.stream(
                    {"messages": [HumanMessage(content=message)]},
                    config=config,  # 传递 config，PostgresSaver 自动恢复状态
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
                                        "name": (
                                            tool_call["name"]
                                            if tool_call["name"]
                                            else ""
                                        ),
                                        "args": (
                                            dict(tool_call["args"])
                                            if tool_call["args"]
                                            else {}
                                        ),
                                        "id": (
                                            tool_call["id"] if tool_call["id"] else ""
                                        ),
                                    }
                                    # 只添加有效的工具调用（有 name 和 id）- 2025-01-01
                                    if tool_info["name"] and tool_info["id"]:
                                        accumulated_tool_calls.append(tool_info)
                                        logger.info(f"流式工具调用: {tool_info}")
                                except (KeyError, TypeError) as e:
                                    logger.warning(f"流式提取工具调用信息失败: {e}")

                        # 提取工具执行结果（ToolMessage）- 2025-01-02
                        if isinstance(message_chunk, ToolMessage):
                            if message_chunk.tool_call_id and message_chunk.content:
                                accumulated_tool_results[message_chunk.tool_call_id] = (
                                    message_chunk.content
                                )
                                logger.info(
                                    f"流式提取工具结果: {message_chunk.tool_call_id} - 长度={len(message_chunk.content)}"
                                )

            except StopIteration:
                # 流式自然结束
                logger.info("流式处理自然结束")
                pass

            except Exception as e:
                logger.error(f"流式处理过程中出错: {e}", exc_info=True)
                raise

            # 发送最终消息
            logger.info(f"流式处理完成，总内容长度: {len(full_content)}")
            logger.info(
                f"流式提取完成：tool_calls={len(accumulated_tool_calls)} 个, tool_results={len(accumulated_tool_results)} 个"
            )
            yield {
                "content": "",
                "is_final": True,
                "tool_calls": (
                    accumulated_tool_calls if accumulated_tool_calls else None
                ),
                "tool_results": (
                    accumulated_tool_results if accumulated_tool_results else None
                ),
            }

        except Exception as e:
            logger.error(f"流式处理失败: {e}", exc_info=True)
            yield {"content": f"错误: {str(e)}", "is_final": True, "tool_calls": None}


# 创建全局Agent实例
agent_service = ResearchAgentService()
