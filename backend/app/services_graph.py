# backend/app/services_graph.py
"""
LangGraph 1.0+ SQL Agent Service
Based on: https://docs.langchain.com/oss/python/langgraph/sql-agent
"""
import os
import re
import logging
from typing import Literal, Dict, Any
from datetime import datetime

# 清除代理环境变量
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(var, None)
os.environ["NO_PROXY"] = "192.22.44.99,localhost,127.0.0.1"

import dateutil.parser
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from .config import settings

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
            # 使用 dayfirst=True 处理 DD/MM/YYYY 格式
            dt_obj = dateutil.parser.parse(original, dayfirst=True)
            return dt_obj.strftime("%Y-%m-%d")
        except Exception:
            return match.group(0)  # 解析失败时保留原始值
    
    # 匹配 DD/MM/YYYY HH:MM:SS 格式
    datetime_pattern = r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\b'
    
    def replace_datetime(match):
        try:
            original = match.group(0)
            dt_obj = dateutil.parser.parse(original, dayfirst=True)
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return match.group(0)
    
    # 先替换完整的日期时间，再替换纯日期
    result = re.sub(datetime_pattern, replace_datetime, text)
    result = re.sub(date_pattern, replace_date, result)
    return result


class SQLGraphService:
    """
    LangGraph 1.0+ 版本的 SQL Agent 服务
    基于官方文档的多步骤工作流模式
    """

    def __init__(self):
        self.llm = None
        self.db = None
        self.tools = None
        self.checkpointer = None
        self.conn_pool = None
        self.graph = None
        self._initialize()

    def _initialize(self):
        """初始化所有组件"""
        try:
            
            # 1. 初始化 Ollama 模型 (本地大模型)
            # self.llm = ChatOpenAI(
            #     model=settings.ollama_model,
            #     temperature=settings.agent_temperature,
            #     openai_api_key="ollama",  # Ollama 不需要真实的 API key
            #     openai_api_base=f"{settings.ollama_base_url}/v1",
            #     max_tokens=settings.agent_max_tokens,
            # )
            
            self.llm = ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=settings.agent_temperature,
                num_ctx=settings.ollama_num_ctx,
                keep_alive=settings.ollama_keep_alive,
            )

            # # 1. 初始化 DeepSeek 模型 (联网大模型)
            # self.llm = ChatOpenAI(
            #     model=settings.deepseek_model,
            #     temperature=settings.agent_temperature,
            #     openai_api_key=settings.deepseek_api_key,
            #     openai_api_base=settings.deepseek_base_url,
            #     max_tokens=settings.agent_max_tokens,
            # )

            # 2. 连接 MySQL 数据库
            self.db = SQLDatabase.from_uri(settings.mysql_database_url)
            logger.info(f"SQL Graph Agent 连接到 MySQL 数据库")

            # 3. 创建 SQL 工具包
            toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
            self.tools = toolkit.get_tools()
            
            # 提取特定工具
            self.list_tables_tool = next(
                tool for tool in self.tools if tool.name == "sql_db_list_tables"
            )
            self.get_schema_tool = next(
                tool for tool in self.tools if tool.name == "sql_db_schema"
            )
            self.run_query_tool = next(
                tool for tool in self.tools if tool.name == "sql_db_query"
            )

            # 4. 初始化 PostgresSaver
            self.conn_pool = ConnectionPool(
                conninfo=settings.database_url, min_size=1, max_size=10, timeout=30
            )
            self.checkpointer = PostgresSaver(self.conn_pool)

            try:
                self.checkpointer.setup()
                logger.info("PostgresSaver 检查点表初始化成功")
            except Exception as setup_error:
                logger.info(f"检查点表已存在或创建跳过: {setup_error}")

            # 5. 构建图
            self.graph = self._build_graph()
            logger.info("SQL Graph Agent 初始化成功 (LangGraph 1.0+ 版本)")

        except Exception as e:
            logger.error(f"SQL Graph Agent 初始化失败: {e}")
            raise

    def _build_graph(self):
        """
        构建 LangGraph 工作流
        基于官方文档: list_tables -> get_schema -> generate_query -> check_query -> run_query
        """
        builder = StateGraph(MessagesState)

        # 添加节点
        builder.add_node("list_tables", self._list_tables)
        builder.add_node("call_get_schema", self._call_get_schema)
        builder.add_node("get_schema", ToolNode([self.get_schema_tool]))
        builder.add_node("generate_query", self._generate_query)
        builder.add_node("check_query", self._check_query)
        builder.add_node("run_query", self._run_query_with_date_clean)

        # 添加边
        builder.add_edge(START, "list_tables")
        builder.add_edge("list_tables", "call_get_schema")
        builder.add_edge("call_get_schema", "get_schema")
        builder.add_edge("get_schema", "generate_query")
        builder.add_conditional_edges("generate_query", self._should_continue)
        builder.add_edge("check_query", "run_query")
        builder.add_edge("run_query", "generate_query")

        return builder.compile(checkpointer=self.checkpointer)

    def _list_tables(self, state: MessagesState) -> Dict[str, Any]:
        """列出所有可用表"""
        tool_call = {
            "name": "sql_db_list_tables",
            "args": {},
            "id": "list_tables_call",
            "type": "tool_call",
        }
        tool_call_message = AIMessage(content="", tool_calls=[tool_call])
        tool_message = self.list_tables_tool.invoke(tool_call)
        response = AIMessage(f"可用的数据库表: {tool_message.content}")
        return {"messages": [tool_call_message, tool_message, response]}

    def _call_get_schema(self, state: MessagesState) -> Dict[str, Any]:
        """强制 LLM 调用 get_schema 工具"""
        llm_with_tools = self.llm.bind_tools(
            [self.get_schema_tool], tool_choice="any"
        )
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def _generate_query(self, state: MessagesState) -> Dict[str, Any]:
        """生成 SQL 查询"""
        system_prompt = f"""You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {self.db.dialect} query to run,
then look at the results of the query and return the answer.
Unless the user specifies a specific number of examples, always limit your query to at most {settings.sql_agent_top_k} results.

You can order the results by a relevant column to return the most interesting examples.
Never query for all columns from a specific table, only ask for relevant columns.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.).

注意：使用中文进行回复。
注意：DATE_EVT 是字符串格式，在编写 SQL 时应该使用 STR_TO_DATE(DATE_EVT, '%d/%m/%Y %H:%i:%s.%f') 进行转换。
"""
        system_message = {"role": "system", "content": system_prompt}
        llm_with_tools = self.llm.bind_tools([self.run_query_tool])
        response = llm_with_tools.invoke([system_message] + state["messages"])
        return {"messages": [response]}

    def _check_query(self, state: MessagesState) -> Dict[str, Any]:
        """检查 SQL 查询的正确性"""
        check_prompt = f"""You are a SQL expert with strong attention to detail.
Double check the {self.db.dialect} query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins
- 确保 DATE_EVT 字段使用了 STR_TO_DATE 函数进行转换

If there are any mistakes, rewrite the query.
If there are no mistakes, just reproduce the original query.
You will call the appropriate tool to execute the query after running this check.
"""
        system_message = {"role": "system", "content": check_prompt}
        
        # 从上一条消息中提取查询
        tool_call = state["messages"][-1].tool_calls[0]
        user_message = {"role": "user", "content": tool_call["args"]["query"]}
        
        llm_with_tools = self.llm.bind_tools(
            [self.run_query_tool], tool_choice="any"
        )
        response = llm_with_tools.invoke([system_message, user_message])
        response.id = state["messages"][-1].id
        return {"messages": [response]}

    def _run_query_with_date_clean(self, state: MessagesState) -> Dict[str, Any]:
        """
        执行查询并进行日期格式清洗 (策略 A: 无条件清洗)
        """
        # 获取最后一条消息中的工具调用
        last_message = state["messages"][-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"messages": []}
        
        tool_call = last_message.tool_calls[0]
        query = tool_call["args"].get("query", "")
        
        try:
            # 执行查询
            result = self.run_query_tool.invoke({"query": query})
            result_content = result if isinstance(result, str) else str(result)
            
            # 策略 A: 无条件进行日期格式清洗
            cleaned_result = normalize_dates_in_text(result_content)
            
            logger.info(f"查询执行成功，结果已进行日期格式清洗")
            
            tool_message = ToolMessage(
                content=cleaned_result,
                tool_call_id=tool_call["id"],
            )
            return {"messages": [tool_message]}
            
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            error_message = ToolMessage(
                content=f"查询执行错误: {str(e)}",
                tool_call_id=tool_call["id"],
            )
            return {"messages": [error_message]}

    def _should_continue(self, state: MessagesState) -> Literal["check_query", "__end__"]:
        """判断是否继续执行"""
        messages = state["messages"]
        last_message = messages[-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return END
        else:
            return "check_query"

    async def process_message(
        self, message: str, session_id: str, config: dict = None
    ) -> Dict[str, Any]:
        """处理用户消息（非流式）"""
        try:
            if config is None:
                config = {"configurable": {"thread_id": str(session_id)}}

            result = self.graph.invoke(
                {"messages": [HumanMessage(content=message)]}, config=config
            )

            # 提取最后一条消息内容
            messages = result.get("messages", [])
            last_message = messages[-1] if messages else None
            content = last_message.content if hasattr(last_message, "content") else ""

            return {
                "content": content,
                "tool_calls": None,
                "tool_results": None,
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
            if config is None:
                config = {"configurable": {"thread_id": str(session_id)}}

            logger.info(f"开始流式处理，消息: {message[:100]}...")

            for chunk in self.graph.stream(
                {"messages": [HumanMessage(content=message)]},
                config=config,
                stream_mode="values",
            ):
                messages = chunk.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, "content") and last_msg.content:
                        yield {
                            "content": last_msg.content,
                            "is_final": False,
                            "tool_calls": None,
                        }

            yield {"content": "", "is_final": True, "tool_calls": None, "tool_results": None}

        except Exception as e:
            logger.error(f"流式处理失败: {e}", exc_info=True)
            yield {"content": f"错误: {str(e)}", "is_final": True, "tool_calls": None}


# 创建全局实例（可选，用于对比测试）
agent_service = SQLGraphService()
