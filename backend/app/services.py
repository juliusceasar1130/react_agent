# backend/app/services.py
from typing import List, Dict, Any, AsyncIterator
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from langgraph.checkpoint.postgres import PostgresSaver
from .config import settings
import logging
import json

logger = logging.getLogger(__name__)


class SQLAgentService:
    """生产数据查询 Agent 服务"""

    def __init__(self):
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self):
        """初始化 Agent"""
        try:
            # 1. 初始化 Ollama 模型 (Qwen3:30b)
            llm = ChatOllama(
                model=settings.ollama_model,
                temperature=settings.agent_temperature,
                base_url=settings.ollama_base_url,
                num_ctx=settings.ollama_num_ctx,
                keep_alive=settings.ollama_keep_alive,
            )

            # 2. 连接 MySQL 数据库
            db = SQLDatabase.from_uri(settings.mysql_database_url)
            logger.info(f"SQL Agent 连接到 MySQL 数据库: {settings.mysql_database_url}")

            # 3. 创建 SQL 工具包
            toolkit = SQLDatabaseToolkit(db=db, llm=llm)
            tools = toolkit.get_tools()

            # 4. 定义 SQL Agent 系统提示词
            system_prompt = f"""You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {db.dialect} query to run,
then look at the results of the query and return the answer. Unless the user
specifies a specific number of examples they wish to obtain, always limit your
query to at most {settings.sql_agent_top_k} results.

You can order the results by a relevant column to return the most interesting
examples in the database. Never query for all the columns from a specific table,
only ask for the relevant columns given the question.

You MUST double check your query before executing it. If you get an error while
executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the
database.

To start you should ALWAYS look at the tables in the database to see what you
can query. Do NOT skip this step.

Then you should query the schema of the most relevant tables.
"""

            # 5. 初始化 PostgresSaver（保留状态管理）
            from psycopg_pool import ConnectionPool

            self.conn_pool = ConnectionPool(
                conninfo=settings.database_url, min_size=1, max_size=10, timeout=30
            )

            self.checkpointer = PostgresSaver(self.conn_pool)

            try:
                self.checkpointer.setup()
                logger.info("PostgresSaver 检查点表初始化成功")
            except Exception as setup_error:
                logger.info(f"检查点表已存在或创建跳过: {setup_error}")

            # 6. 配置 SummarizationMiddleware
            summarization_middleware = SummarizationMiddleware(
                model=llm,
                trigger=("tokens", 4000),
                keep=("messages", 5),
            )

            # 7. 创建 Agent
            self.agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
                checkpointer=self.checkpointer,
                middleware=[summarization_middleware],
            )

            logger.info("SQL Agent 初始化成功（PostgresSaver 和 SummarizationMiddleware 已启用）")

        except Exception as e:
            logger.error(f"SQL Agent 初始化失败: {e}")
            raise

    async def process_message(
        self, message: str, session_id: str, config: dict = None
    ) -> Dict[str, Any]:
        """处理用户消息（非流式）"""
        try:
            if not self.agent:
                self._initialize_agent()

            if config is None:
                config = {"configurable": {"thread_id": str(session_id)}}

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

            intermediate_steps = result.get("intermediate_steps", [])
            logger.info(f"中间步骤数量: {len(intermediate_steps)}")

            for step in intermediate_steps:
                if len(step) >= 2:
                    action = step[0]
                    observation = step[1]

                    tool_name = getattr(action, "tool", "")
                    tool_input = getattr(action, "tool_input", {})
                    tool_id = f"tool_{len(tool_calls)}"

                    if tool_name:
                        tool_calls.append(
                            {"name": tool_name, "args": tool_input, "id": tool_id}
                        )

                    if observation:
                        tool_results[tool_id] = str(observation)

            logger.info(f"处理消息列表，共 {len(messages)} 条消息")

            # 如果 intermediate_steps 为空，尝试从 messages 列表提取
            if not intermediate_steps:
                for i, msg in enumerate(messages):
                    msg_type = type(msg).__name__

                    if isinstance(msg, AIMessage):
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
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
                                    if tool_info["name"] and tool_info["id"]:
                                        tool_calls.append(tool_info)
                                except (KeyError, TypeError) as e:
                                    logger.warning(f"提取工具调用信息失败: {e}")

                    elif isinstance(msg, ToolMessage):
                        if msg.tool_call_id and msg.content:
                            tool_results[msg.tool_call_id] = msg.content

            logger.info(
                f"提取完成：tool_calls={len(tool_calls)} 个, tool_results={len(tool_results)} 个"
            )

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
        """流式处理用户消息"""
        try:
            if not self.agent:
                self._initialize_agent()

            if config is None:
                config = {"configurable": {"thread_id": str(session_id)}}

            logger.info(f"开始流式处理，消息: {message[:100]}...")

            full_content = ""
            accumulated_tool_calls = []
            accumulated_tool_results = {}

            try:
                for chunk in self.agent.stream(
                    {"messages": [HumanMessage(content=message)]},
                    config=config,
                    stream_mode="messages",
                ):
                    if chunk and len(chunk) > 0:
                        message_chunk = chunk[0]

                        chunk_type = type(message_chunk).__name__

                        if hasattr(message_chunk, "content"):
                            chunk_content = message_chunk.content or ""
                            if chunk_content:
                                full_content += chunk_content
                                logger.debug(f"流式chunk内容: {chunk_content}")

                                yield {
                                    "content": chunk_content,
                                    "is_final": False,
                                    "tool_calls": None,
                                }

                        if (
                            hasattr(message_chunk, "tool_calls")
                            and message_chunk.tool_calls
                        ):
                            for tool_call in message_chunk.tool_calls:
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
                                    if tool_info["name"] and tool_info["id"]:
                                        accumulated_tool_calls.append(tool_info)
                                        logger.info(f"流式工具调用: {tool_info}")
                                except (KeyError, TypeError) as e:
                                    logger.warning(f"流式提取工具调用信息失败: {e}")

                        if isinstance(message_chunk, ToolMessage):
                            if message_chunk.tool_call_id and message_chunk.content:
                                accumulated_tool_results[message_chunk.tool_call_id] = (
                                    message_chunk.content
                                )
                                logger.info(
                                    f"流式提取工具结果: {message_chunk.tool_call_id} - 长度={len(message_chunk.content)}"
                                )

            except StopIteration:
                logger.info("流式处理自然结束")
                pass

            except Exception as e:
                logger.error(f"流式处理过程中出错: {e}", exc_info=True)
                raise

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


# 创建全局 Agent 实例
agent_service = SQLAgentService()
