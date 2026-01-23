# backend/app/services.py
import os

# 清除代理环境变量，让请求直接发送到 Ollama
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(var, None)
os.environ["NO_PROXY"] = "192.22.44.99,localhost,127.0.0.1"

import logging
import json
import re
from typing import List, Dict, Any, AsyncIterator

import dateutil.parser
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from langgraph.checkpoint.postgres import PostgresSaver
from .config import settings
from langchain_core.tools import tool as langchain_tool

logger = logging.getLogger(__name__)


def normalize_dates_in_text(text: str) -> str:
    """
    检测并转换文本中的非 ISO 日期格式为 ISO 8601 格式。
    策略 A: 无条件运行，对所有结果进行清洗。
    """
    # 匹配 DD/MM/YYYY 或 DD-MM-YYYY 格式的日期
    date_pattern = r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b'
    
    def replace_date(match):
        try:
            original = match.group(0)
            dt_obj = dateutil.parser.parse(original, dayfirst=True)
            return dt_obj.strftime("%Y-%m-%d")
        except Exception:
            return match.group(0)
    
    # 匹配 DD/MM/YYYY HH:MM:SS 格式
    datetime_pattern = r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\b'
    
    def replace_datetime(match):
        try:
            original = match.group(0)
            dt_obj = dateutil.parser.parse(original, dayfirst=True)
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return match.group(0)
    
    result = re.sub(datetime_pattern, replace_datetime, text)
    result = re.sub(date_pattern, replace_date, result)
    return result


class SQLAgentService:
    """生产数据查询 Agent 服务"""

    def __init__(self):
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self):
        """初始化 Agent"""
        try:
            
            # 1. 初始化 DeepSeek 模型 (联网大模型)
            # llm = ChatOpenAI(
            #     model=settings.deepseek_model,
            #     temperature=settings.agent_temperature,
            #     openai_api_key=settings.deepseek_api_key,
            #     openai_api_base=settings.deepseek_base_url,
            #     max_tokens=settings.agent_max_tokens,
            # )

            # 1. 初始化 Ollama 模型
            llm = ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=settings.agent_temperature,
                num_ctx=settings.ollama_num_ctx,
                keep_alive=settings.ollama_keep_alive,
            )

            # 2. 连接 rollerbed_database_url 数据库
            db = SQLDatabase.from_uri(settings.rollerbed_database_url)
            logger.info(f"SQL Agent 连接到 rollerbed_database_url 数据库: {settings.rollerbed_database_url}")

            # 3. 创建 SQL 工具包
            toolkit = SQLDatabaseToolkit(db=db, llm=llm)
            raw_tools = toolkit.get_tools()

            # 3.1 深度工具包装：对 sql_db_query 进行日期清洗包装
            # 这样模型在中间推理步骤中看到的就是 ISO 8601 格式的日期            
            
            original_query_tool = next(
                (t for t in raw_tools if t.name == "sql_db_query"), None
            )
            
            if original_query_tool:
                @langchain_tool
                def sql_db_query(query: str) -> str:
                    """Execute a SQL query against the database and return results.
                    Input should be a valid SQL query.
                    The results will have dates normalized to ISO 8601 format (YYYY-MM-DD).
                    """
                    raw_result = original_query_tool.invoke({"query": query})
                    cleaned_result = normalize_dates_in_text(str(raw_result))
                    logger.debug(f"SQL 查询结果已清洗日期格式")
                    return cleaned_result
                
                # 用包装后的工具替换原始工具
                tools = [sql_db_query if t.name == "sql_db_query" else t for t in raw_tools]
                logger.info("SQL 查询工具已包装日期清洗逻辑")
            else:
                tools = raw_tools
                logger.warning("未找到 sql_db_query 工具，跳过包装")

            # 4. 定义 SQL Agent 系统提示词
            system_prompt = f"""You are an 120JPH paint shop agent designed to interact with a SQL database.
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

注意：- 使用中文进行回复
     - <DATE_EVT>是字符串格式，在编写sql时应该使用STR_TO_DATE(DATE_EVT, '%d/%m/%Y %H:%i:%s.%f')进行转换
     - 如果用户问你 <你是谁><你好>等问题，你应该简单描述你的擅长的功能并给出示例，不需要进行任何数据库操作。
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

            logger.info(
                "SQL Agent 初始化成功（PostgresSaver 和 SummarizationMiddleware 已启用）"
            )

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
