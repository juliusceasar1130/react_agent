# backend/app/services.py
import os

# 清除代理环境变量，让请求直接发送到 Ollama
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(var, None)
os.environ["NO_PROXY"] = "192.22.44.99,localhost,127.0.0.1"

import logging
import sys
import json
import re
from typing import List, Dict, Any, AsyncIterator

# 配置日志 - 确保 langgraph dev 模式下能看到日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("langgraph_dev.log", encoding="utf-8")
    ]
)

import dateutil.parser
from sqlalchemy import create_engine, inspect, text
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk

# from langgraph.checkpoint.postgres import PostgresSaver
from backend.app.config import settings
from langchain_core.tools import tool as langchain_tool

logger = logging.getLogger(__name__)
from langchain.tools import tool









from backend.app.skills import SKILLS
@langchain_tool
def load_skill(skill_name: str) -> str:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about how to handle a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "expense_reporting", "travel_booking")
    """
    # Find and return the requested skill
    for skill in SKILLS:
        if skill["name"] == skill_name:
            return f"Loaded skill: {skill_name}\n\n{skill['content']}"

    # Skill not found
    available = ", ".join(s["name"] for s in SKILLS)
    return f"Skill '{skill_name}' not found. Available skills: {available}"


from langchain.agents.middleware import ModelRequest, ModelResponse, AgentMiddleware
from langchain.messages import SystemMessage
from typing import Callable

class SkillMiddleware(AgentMiddleware):  
    """Middleware that injects skill descriptions into the system prompt."""

    # Register the load_skill tool as a class variable
    tools = [load_skill]  

    def __init__(self):
        """Initialize and generate the skills prompt from SKILLS."""
        # Build skills prompt from the SKILLS list
        skills_list = []
        for skill in SKILLS:
            skills_list.append(
                f"- **{skill['name']}**: {skill['description']}"
            )
        self.skills_prompt = "\n".join(skills_list)

    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """提取公共逻辑：将技能描述注入到系统提示词中"""
        skills_addendum = ( 
            f"\n\n## Available Skills\n\n{self.skills_prompt}\n\n"
            "Use the load_skill tool when you need detailed information "
            "about handling a specific type of request."
        )
        # 追加系统提示词
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        new_system_message = SystemMessage(content=new_content)
        logger.info("SkillMiddleware: Injected skill descriptions into system prompt")
        logger.info(f"Modified system message: {new_system_message}")
        return request.override(system_message=new_system_message)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Sync: Inject skill descriptions into system prompt."""
        modified_request = self._modify_request(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Async: Inject skill descriptions into system prompt."""
        modified_request = self._modify_request(request)
        return await handler(modified_request)







def normalize_dates_in_text(text: str) -> str:
    """
    检测并转换文本中的非 ISO 日期格式为 ISO 8601 格式。
    策略 A: 无条件运行，对所有结果进行清洗。
    """
    # 匹配 DD/MM/YYYY 或 DD-MM-YYYY 格式的日期
    date_pattern = r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"

    def replace_date(match):
        try:
            original = match.group(0)
            dt_obj = dateutil.parser.parse(original, dayfirst=True)
            return dt_obj.strftime("%Y-%m-%d")
        except Exception:
            return match.group(0)

    # 匹配 DD/MM/YYYY HH:MM:SS 格式
    datetime_pattern = r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\b"

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


def fetch_table_definitions_with_comments(db_uri: str) -> Dict[str, str]:
    """
    从数据库元数据中提取表结构和注释信息。
    支持 PostgreSQL 和 MySQL 数据库。
    
    Args:
        db_uri: 数据库连接字符串
        
    Returns:
        Dict[表名, 带注释的表结构定义]
    """
    try:
        engine = create_engine(db_uri)
        inspector = inspect(engine)
        table_definitions = {}
        
        # 检测数据库类型
        db_dialect = engine.dialect.name
        logger.info(f"检测到数据库类型: {db_dialect}")
        
        # 获取所有表
        tables = inspector.get_table_names()
        logger.info(f"找到 {len(tables)} 个表")
        
        with engine.connect() as conn:
            for table in tables:
                try:
                    # 获取表注释
                    table_comment_obj = inspector.get_table_comment(table)
                    table_comment = table_comment_obj.get('text', '') if table_comment_obj else ''
                    
                    # 获取列信息
                    columns = inspector.get_columns(table)
                    
                    # 构建表定义字符串
                    definition_lines = []
                    definition_lines.append(f"-- Table: {table}")
                    if table_comment:
                        definition_lines.append(f"-- Description: {table_comment}")
                    
                    definition_lines.append(f"CREATE TABLE {table} (")
                    
                    col_texts = []
                    for col in columns:
                        col_name = col['name']
                        col_type = str(col['type'])
                        
                        # 尝试从不同来源获取注释
                        col_comment = col.get('comment', None)
                        
                        # 如果 SQLAlchemy 没有返回注释，尝试直接查询
                        if not col_comment and db_dialect == 'postgresql':
                            # PostgreSQL 注释查询
                            comment_query = text("""
                                SELECT col_description(
                                    (SELECT oid FROM pg_class WHERE relname = :table_name),
                                    (SELECT ordinal_position FROM information_schema.columns 
                                     WHERE table_name = :table_name AND column_name = :col_name)
                                )
                            """)
                            result = conn.execute(
                                comment_query,
                                {"table_name": table, "col_name": col_name}
                            ).scalar()
                            col_comment = result if result else None
                            
                        elif not col_comment and db_dialect == 'mysql':
                            # MySQL 注释查询
                            comment_query = text("""
                                SELECT COLUMN_COMMENT 
                                FROM information_schema.COLUMNS 
                                WHERE TABLE_SCHEMA = DATABASE() 
                                AND TABLE_NAME = :table_name 
                                AND COLUMN_NAME = :col_name
                            """)
                            result = conn.execute(
                                comment_query,
                                {"table_name": table, "col_name": col_name}
                            ).scalar()
                            col_comment = result if result else None
                        
                        # 构建列定义
                        col_line = f"  {col_name} {col_type}"
                        if col.get('nullable', True) is False:
                            col_line += " NOT NULL"
                        if col.get('default') is not None:
                            col_line += f" DEFAULT {col['default']}"
                        if col_comment:
                            col_line += f"  -- {col_comment}"
                        
                        col_texts.append(col_line)
                    
                    definition_lines.append(",\n".join(col_texts))
                    definition_lines.append(");")
                    
                    # 添加样本数据
                    try:
                        sample_query = text(f"SELECT * FROM {table} LIMIT 3")
                        samples = conn.execute(sample_query).fetchall()
                        if samples:
                            definition_lines.append("\n-- Sample rows:")
                            for i, row in enumerate(samples, 1):
                                # 将 Row 对象转换为字典
                                row_dict = dict(row._mapping)
                                definition_lines.append(f"-- {i}. {row_dict}")
                    except Exception as sample_err:
                        logger.debug(f"无法获取表 {table} 的样本数据: {sample_err}")
                    
                    table_definitions[table] = "\n".join(definition_lines)
                    logger.debug(f"已处理表: {table}")
                    
                except Exception as table_err:
                    logger.error(f"处理表 {table} 时出错: {table_err}")
                    # 如果单个表失败，继续处理其他表
                    continue
        
        engine.dispose()
        logger.info(f"成功提取 {len(table_definitions)} 个表的定义和注释")
        return table_definitions
        
    except Exception as e:
        logger.error(f"提取表定义失败: {e}")
        return {}


class SQLAgentService:
    """生产数据查询 Agent 服务"""

    def __init__(self):
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self):
        """初始化 Agent"""
        try:

            # 1. 初始化 DeepSeek 模型 (联网大模型)
            llm = ChatOpenAI(
                model=settings.deepseek_model,
                temperature=settings.agent_temperature,
                openai_api_key=settings.deepseek_api_key,
                openai_api_base=settings.deepseek_base_url,
                max_tokens=settings.agent_max_tokens,
            )

            # 1. 初始化 Ollama 模型
            # llm = ChatOllama(
            #     model=settings.ollama_model,
            #     base_url=settings.ollama_base_url,
            #     temperature=settings.agent_temperature,
            #     num_ctx=settings.ollama_num_ctx,
            #     keep_alive=settings.ollama_keep_alive,
            # )

            # 2. 连接 rollerbed_database_url 数据库
            # 2.1 提取表和字段的注释信息
            logger.info("开始提取数据库表结构和注释信息...")
            custom_table_info = fetch_table_definitions_with_comments(
                settings.rollerbed_database_url
            )
            
            # 2.2 创建 SQLDatabase 对象并注入自定义表信息
            db = SQLDatabase.from_uri(
                settings.rollerbed_database_url,
                view_support=True,
                custom_table_info=custom_table_info if custom_table_info else None,
                sample_rows_in_table_info=2  # 如果 custom_table_info 为空，则使用默认的样本行
            )
            logger.info(
                f"SQL Agent 连接到 rollerbed_database_url 数据库: {settings.rollerbed_database_url}"
            )
            if custom_table_info:
                logger.info(f"成功注入 {len(custom_table_info)} 个表的注释信息到 SQLDatabase")
            else:
                logger.warning("未能提取表注释信息，使用默认的表结构描述")

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
                    # 对查询的结果的日期进行格式转换
                    cleaned_result = normalize_dates_in_text(str(raw_result))
                    logger.debug(f"SQL 查询结果已清洗日期格式")
                    return cleaned_result

                # 用包装后的工具替换原始工具
                tools = [
                    sql_db_query if t.name == "sql_db_query" else t for t in raw_tools
                ]
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

            # 5. 初始化 PostgresSaver（在 LangGraph API 环境下，持久化由平台自动处理）
            # from psycopg_pool import ConnectionPool
            #
            # self.conn_pool = ConnectionPool(
            #     conninfo=settings.database_url, min_size=1, max_size=10, timeout=30
            # )
            #
            # self.checkpointer = PostgresSaver(self.conn_pool)
            #
            # try:
            #     self.checkpointer.setup()
            #     logger.info("PostgresSaver 检查点表初始化成功")
            # except Exception as setup_error:
            #     logger.info(f"检查点表已存在或创建跳过: {setup_error}")
            self.checkpointer = None  # 或者直接不定义，但在 create_agent 中移除它

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
                # checkpointer=self.checkpointer, # 移除自定义 checkpointer，由 LangGraph API 接管
                middleware=[summarization_middleware,SkillMiddleware()],
            )

            logger.info(
                "SQL Agent 初始化成功（PostgresSaver 和 SummarizationMiddleware 已启用）"
            )

        except Exception as e:
            logger.error(f"SQL Agent 初始化失败: {e}")
            raise


# 创建全局 Agent 实例
agent_service = SQLAgentService().agent
