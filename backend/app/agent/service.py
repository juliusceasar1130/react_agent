# backend/app/agent/service.py
"""
SQL Agent 服务

提供生产数据查询 Agent 的核心服务类，整合所有模块化组件。
"""

import logging
import os
import sys
from typing import Any, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from backend.app.agent.constants import EXCLUDED_TOOLS, ToolNames
from backend.app.agent.middleware import SkillMiddleware, BusinessRagMiddleware
from backend.app.agent.tools import create_wrapped_query_tool
from backend.app.agent.utils import fetch_table_definitions_with_comments
from backend.app.agent.utils.vector_store import create_business_vector_store
from backend.app.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("langgraph_dev.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def _configure_proxy_settings() -> None:
    """配置代理环境变量，确保直连数据库和 LLM 服务"""
    for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "192.22.44.99,localhost,127.0.0.1"


def _create_llm(use_ollama: bool = False) -> Any:
    """
    创建 LLM 实例

    Args:
        use_ollama: 是否使用 Ollama 本地模型，默认使用 DeepSeek

    Returns:
        配置好的 LLM 实例
    """
    if use_ollama:
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.agent_temperature,
            num_ctx=settings.ollama_num_ctx,
            keep_alive=settings.ollama_keep_alive,
        )

    return ChatOpenAI(
        model=settings.deepseek_model,
        temperature=settings.agent_temperature,
        openai_api_key=settings.deepseek_api_key,
        openai_api_base=settings.deepseek_base_url,
        max_tokens=settings.agent_max_tokens,
    )


def _create_database_connection() -> tuple[SQLDatabase, dict]:
    """
    创建数据库连接和获取表定义

    Returns:
        tuple: (SQLDatabase 实例, 表定义字典)
    """
    logger.info("开始提取数据库表结构和注释信息...")
    custom_table_info = fetch_table_definitions_with_comments(
        settings.rollerbed_database_url
    )

    db = SQLDatabase.from_uri(
        settings.rollerbed_database_url,
        view_support=True,
        custom_table_info=custom_table_info if custom_table_info else None,
        sample_rows_in_table_info=2,
    )

    logger.info(
        f"SQL Agent 连接到数据库: {settings.rollerbed_database_url}"
    )

    if custom_table_info:
        logger.info(
            f"成功注入 {len(custom_table_info)} 个表的注释信息到 SQLDatabase"
        )
    else:
        logger.warning("未能提取表注释信息，使用默认的表结构描述")

    return db, custom_table_info


def _prepare_tools(db: SQLDatabase, llm: Any) -> list:
    """
    准备 Agent 工具列表

    Args:
        db: SQLDatabase 实例
        llm: LLM 实例

    Returns:
        配置好的工具列表
    """
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    raw_tools = toolkit.get_tools()

    # 获取原始工具
    original_query_tool = next(
        (t for t in raw_tools if t.name == ToolNames.QUERY), None
    )
    original_checker_tool = next(
        (t for t in raw_tools if t.name == ToolNames.CHECKER), None
    )

    if original_query_tool:
        # 创建包装后的查询工具
        wrapped_query_tool = create_wrapped_query_tool(
            original_query_tool, original_checker_tool
        )

        # 用包装后的工具替换原始工具，并移除不需要的工具
        tools = [
            wrapped_query_tool if t.name == ToolNames.QUERY else t
            for t in raw_tools
            if t.name not in EXCLUDED_TOOLS
        ]

        logger.info("SQL 查询工具已包装：技能检查 + 语法检查 + 日期清洗")
        logger.info(
            "已移除 sql_db_list_tables 和 sql_db_schema，强制通过 skills 获取表信息"
        )
    else:
        tools = raw_tools
        logger.warning("未找到 sql_db_query 工具，跳过包装")

    return tools


def _build_system_prompt(db: SQLDatabase) -> str:
    """构建 Agent 系统提示词"""
    return f"""You are an 120JPH paint shop agent designed to interact with a SQL database.

工作流程：
1. 在查询数据前，你必须先使用 load_skill 工具加载相关业务领域的技能
2. 从技能内容中了解可用的表结构、字段含义和业务规则
3. 根据技能提供的信息编写 SQL 查询
4. 使用 sql_db_query 工具执行查询（会自动进行语法检查）

SQL 查询规则：
- 创建语法正确的 {db.dialect} 查询
- 除非用户指定数量，否则查询结果限制为 {settings.sql_agent_top_k} 条
- 可以使用 ORDER BY 返回最相关的结果
- 只查询必要的列，不要使用 SELECT *
- 如果查询出错，分析错误信息后重写查询
- 严禁执行 DML 语句（INSERT, UPDATE, DELETE, DROP 等）

注意事项：
- 使用中文进行回复
- <DATE_EVT> 是字符串格式，在编写 SQL 时应使用 STR_TO_DATE(DATE_EVT, '%d/%m/%Y %H:%i:%s.%f') 进行转换
- 如果用户问"你是谁"、"你好"等问题，简单描述你的功能并给出示例，不需要进行数据库操作
- 如果用户提到问题你不理解，或者边界模糊，请直接向用户提问，让用户补充信息，不要盲目猜测和猜想
- 回答用户问题时，应该简明扼要，不要啰嗦
"""


class SQLAgentService:
    """
    生产数据查询 Agent 服务

    整合所有模块化组件，提供完整的 SQL Agent 功能：
    - 数据库连接和元数据提取
    - 工具包装（技能检查、语法检查、日期清洗）
    - 中间件集成（技能注入、对话摘要）
    """

    def __init__(self, use_ollama: bool = False) -> None:
        """
        初始化 SQL Agent 服务

        Args:
            use_ollama: 是否使用 Ollama 本地模型，默认使用 DeepSeek
        """
        self.agent: Optional[Any] = None
        self.checkpointer = None
        self._use_ollama = use_ollama
        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """初始化 Agent"""
        try:
            # 配置代理设置
            _configure_proxy_settings()

            # 1. 创建 LLM
            llm = _create_llm(self._use_ollama)

            # 2. 连接数据库
            db, _ = _create_database_connection()

            # 3. 准备工具
            tools = _prepare_tools(db, llm)

            # 4. 构建系统提示词
            system_prompt = _build_system_prompt(db)

            # 5. 创建业务知识向量库（仅使用 Documentation 类型）
            logger.info("开始初始化业务知识 RAG 向量库...")
            try:
                vector_store = create_business_vector_store(collection_name="rag_store", embedding_model="baai/bge-m3", pg_connection_string=settings.database_url)
                logger.info(f"向量库创建成功，正在初始化 BusinessRagMiddleware...")
                
                # 只使用 Documentation 类型作为业务知识注入系统提示词
                # DDL 和 SQL Example 类型预留，后续开发
                rag_middleware = BusinessRagMiddleware(
                    vector_store=vector_store,
                    doc_k=5,  # Documentation 类型检索数量
                    score_threshold=settings.rag_similarity_threshold,  # 使用配置文件中的相似度阈值
                )
                logger.info("业务知识 RAG 中间件已启用（仅使用 Documentation 类型）")
            except ValueError as e:
                # NVIDIA_API_KEY 未设置等配置错误
                logger.warning(f"业务知识向量库初始化失败，RAG 功能将不可用: {e}")               
                rag_middleware = None
            except Exception as e:
                # 其他错误（数据库连接、网络等）
                logger.warning(f"业务知识向量库初始化失败，RAG 功能将不可用: {e}")
                rag_middleware = None

            # 6. 配置 SummarizationMiddleware
            summarization_middleware = SummarizationMiddleware(
                model=llm,
                trigger=("tokens", 4000),
                keep=("messages", 5),
            )

            # 7. 构建中间件列表
            middleware_list = [
                summarization_middleware,
                SkillMiddleware(),
            ]
            if rag_middleware:
                middleware_list.insert(0, rag_middleware)  # RAG 中间件放在最前面

            # 8. 创建 Agent
            self.agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
                middleware=middleware_list,
            )

            logger.info(
                "SQL Agent 初始化成功（SummarizationMiddleware、SkillMiddleware 和 BusinessRagMiddleware 已启用）"
            )

        except Exception as e:
            logger.error(f"SQL Agent 初始化失败: {e}")
            raise


# 创建全局 Agent 实例
agent_service = SQLAgentService().agent
