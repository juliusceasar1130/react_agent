# backend/app/agent/service.py
"""
SQL Agent 服务

提供生产数据查询 Agent 的核心服务类，整合所有模块化组件。

修改时间: 2026-03-27 20:40 Asia/Shanghai
主要修改内容:
- 新增 FastAPI 本地异步运行链路，支持 AsyncPostgresSaver 初始化与关闭
- 保留 LangGraph 托管模式同步建图逻辑，避免影响现有 graph factory
- 本地 FastAPI 可通过 `create_local_async()` 切回 ainvoke / astream
- 2026-04-16 11:00 Asia/Shanghai: 为本地 AsyncConnectionPool 增加 `connect_timeout`，修复 Windows 下连接池初始化长时间挂起后超时的问题
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI

from backend.app.agent.constants import EXCLUDED_TOOLS, ToolNames
from backend.app.agent.middleware import (
    BusinessRagMiddleware,
    ContextWarningMiddleware,
    SkillMiddleware,
    SafeMergeSystemMiddleware,
)
from backend.app.agent.tools import (
    create_chart_artifact_tool,
    create_csv_export_tool,
    create_sql_example_search_tool,
    create_wrapped_query_tool,
)
from backend.app.agent.utils import (
    LlamaCppTokenEstimator,
    MaterializedViewSQLDatabase,
    build_postgres_search_path_engine_args,
    ensure_windows_selector_loop,
    fetch_table_definitions_with_comments,
)
from backend.app.agent.vector.base import BaseRetriever
from backend.app.agent.vector.factory import create_business_retriever_and_reranker
from backend.app.config import settings

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.store.base import BaseStore
    from langgraph_sdk.runtime import ServerRuntime

logger = logging.getLogger(__name__)

# 仅用于 LangGraph 调试入口，避免每次调用工厂都重新初始化模型/数据库元信息。
_MANAGED_AGENT_SERVICE: Optional["SQLAgentService"] = None


def _create_context_warning_middleware() -> ContextWarningMiddleware:
    """创建上下文窗口告警中间件。"""
    return ContextWarningMiddleware(
        estimator=LlamaCppTokenEstimator(
            base_url=settings.llama_cpp_tokenize_base_url,
            timeout=settings.llm_context_tokenizer_timeout,
        ),
        enabled=settings.llm_context_warning_enabled,
        context_window=settings.llm_context_window,
        warn_tokens=settings.llm_context_warn_tokens,
        output_reserve=settings.agent_max_tokens,
        safety_buffer=settings.llm_context_safety_buffer,
    )


def _configure_proxy_settings() -> None:
    """配置代理环境变量，确保直连数据库和 LLM 服务。"""
    for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "192.22.44.99,localhost,127.0.0.1"


def _is_langgraph_managed_runtime() -> bool:
    """
    检测是否处于 LangGraph 托管运行环境。

    如果检测到 LANGGRAPH_API_URL，说明运行在托管环境，
    Store 和 Checkpointer 会由 LangGraph 自动注入。
    """
    is_langgraph_api = (
        os.environ.get("LANGGRAPH_API_URL") is not None
        or "langgraph" in os.environ.get("PATH", "").lower()
    )
    return is_langgraph_api


def _create_llm(use_ollama: bool = False) -> Any:
    """
    创建 LLM 实例。

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

    # 1. 组装标准参数
    kwargs: dict[str, Any] = {
        "model": settings.deepseek_model,
        "temperature": settings.agent_temperature,
        "openai_api_key": settings.deepseek_api_key,
        "openai_api_base": settings.deepseek_base_url,
        "max_tokens": settings.agent_max_tokens,
        "request_timeout": settings.llm_timeout,
        "max_retries": settings.llm_max_retries,
    }

    # top_p 和 presence_penalty 属于 OpenAI 官方一级标准参数，直接在顶层参数传递以防触发 UserWarning
    if settings.llm_top_p is not None:
        kwargs["top_p"] = settings.llm_top_p
    if settings.llm_presence_penalty is not None:
        kwargs["presence_penalty"] = settings.llm_presence_penalty

    # 2. 动态检测并将 vLLM 特有的非标准采样参数安全包裹在 extra_body 中透传，规避 OpenAI SDK 的参数强拦截
    extra_body: dict[str, Any] = {}
    if settings.llm_top_k is not None:
        extra_body["top_k"] = settings.llm_top_k
    if settings.llm_repetition_penalty is not None:
        extra_body["repetition_penalty"] = settings.llm_repetition_penalty
    if settings.llm_min_p is not None:
        extra_body["min_p"] = settings.llm_min_p
    if settings.llm_enable_thinking is not None:
        extra_body["chat_template_kwargs"] = {"enable_thinking": settings.llm_enable_thinking}

    if extra_body:
        kwargs["extra_body"] = extra_body

    logger.info("Initializing ChatOpenAI with arguments: %s", {k: v for k, v in kwargs.items() if k != "openai_api_key"})
    return ChatOpenAI(**kwargs)


def _get_business_database_url() -> str:
    """获取业务 SQL 查询入口，优先 analytics_db，回退 rollerbed 源库。"""
    analytics_db_url = settings.analytics_database_url.strip()
    if analytics_db_url:
        return analytics_db_url
    return settings.rollerbed_database_url


def _get_business_database_engine_args(db_url: str) -> dict[str, Any]:
    """为业务数据库连接生成 engine_args。"""
    analytics_db_url = settings.analytics_database_url.strip()
    if analytics_db_url and db_url == analytics_db_url:
        return build_postgres_search_path_engine_args(settings.analytics_db_search_path)
    return {}


def _create_database_connection() -> tuple[MaterializedViewSQLDatabase, dict]:
    """
    创建数据库连接和获取表定义。

    Returns:
        tuple: (MaterializedViewSQLDatabase 实例, 表定义字典)
    """
    db_url = _get_business_database_url()
    engine_args = _get_business_database_engine_args(db_url)

    logger.info("开始提取数据库表结构和注释信息...")
    custom_table_info = fetch_table_definitions_with_comments(
        db_url,
        engine_args=engine_args,
        include_views=True,
        include_materialized_views=True,
    )

    db = MaterializedViewSQLDatabase.from_uri(
        db_url,
        engine_args=engine_args,
        view_support=True,
        custom_table_info=custom_table_info if custom_table_info else None,
        sample_rows_in_table_info=2,
    )

    logger.info("SQL Agent 连接到数据库: %s", db_url)

    if custom_table_info:
        logger.info("成功注入 %d 个表的注释信息到 SQLDatabase", len(custom_table_info))
    else:
        logger.warning("未能提取表注释信息，使用默认的表结构描述")

    return db, custom_table_info


def _create_local_checkpointer() -> tuple["BaseCheckpointSaver", Any]:
    """本地模式下手动创建 PostgresSaver。"""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool
    import psycopg

    logger.info("正在连接 PostgreSQL 数据库用于本地 checkpointer...")

    try:
        logger.info("正在初始化 checkpoints 表（使用 autocommit 模式）...")
        with psycopg.connect(settings.database_url, autocommit=True) as setup_conn:
            temp_checkpointer = PostgresSaver(setup_conn)
            temp_checkpointer.setup()
        logger.info("PostgresSaver 检查点表初始化成功")
    except Exception as setup_error:
        logger.error("初始化检查点表失败: %s", setup_error, exc_info=True)
        logger.error("请检查数据库连接和权限: %s", settings.database_url)
        raise RuntimeError(f"无法初始化 checkpoints 表: {setup_error}") from setup_error

    conn_pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=10,
        timeout=30,
    )
    checkpointer = PostgresSaver(conn_pool)
    return checkpointer, conn_pool


async def _create_local_async_checkpointer() -> tuple["BaseCheckpointSaver", Any]:
    """本地模式下手动创建 AsyncPostgresSaver。"""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    ensure_windows_selector_loop()
    logger.info("正在连接 PostgreSQL 数据库用于本地 async checkpointer...")

    conn_pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=10,
        timeout=30,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "connect_timeout": 5,
        },
    )

    try:
        await conn_pool.open(wait=True, timeout=30)
        checkpointer = AsyncPostgresSaver(conn_pool)
        logger.info("正在初始化 async checkpoints 表...")
        await checkpointer.setup()
        logger.info("AsyncPostgresSaver 检查点表初始化成功")
        return checkpointer, conn_pool
    except Exception:
        await conn_pool.close()
        raise


def _prepare_tools(
    db: MaterializedViewSQLDatabase,
    llm: Any,
    retriever: Optional[BaseRetriever] = None,
) -> list:
    """
    准备 Agent 工具列表。

    Args:
        db: SQLDatabase 实例
        llm: LLM 实例
        retriever: 可选业务检索器，用于 SQL 示例检索

    Returns:
        配置好的工具列表
    """
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    raw_tools = toolkit.get_tools()

    original_query_tool = next(
        (t for t in raw_tools if t.name == ToolNames.QUERY), None
    )
    original_checker_tool = next(
        (t for t in raw_tools if t.name == ToolNames.CHECKER), None
    )

    if original_query_tool:
        wrapped_query_tool = create_wrapped_query_tool(
            original_query_tool, original_checker_tool
        )

        tools = [
            wrapped_query_tool if t.name == ToolNames.QUERY else t
            for t in raw_tools
            if t.name not in EXCLUDED_TOOLS
        ]

        logger.info("SQL 查询工具已包装：技能检查 + 语法检查 + 日期清洗 + 智能限流")
        logger.info(
            "已移除 sql_db_list_tables 和 sql_db_schema，强制通过 skills 获取表信息"
        )
    else:
        tools = raw_tools
        logger.warning("未找到 sql_db_query 工具，跳过包装")

    if retriever is not None:
        try:
            sql_example_tool = create_sql_example_search_tool(retriever)
            tools.append(sql_example_tool)
            logger.info(
                "已注入 SQL 示例检索工具：search_saved_correct_tool_uses（基于业务向量检索器）"
            )
        except Exception as exc:
            logger.warning(
                "注入 SQL 示例检索工具失败，将继续使用现有工具集合: %s",
                exc,
            )

    try:
        business_db_url = _get_business_database_url()
        chart_artifact_tool = create_chart_artifact_tool(
            business_db_url,
            engine_args=_get_business_database_engine_args(business_db_url),
        )
        tools.append(chart_artifact_tool)
        logger.info("已注入图表 artifact 工具：build_chart_artifact")

        business_db_url = _get_business_database_url()
        csv_export_tool = create_csv_export_tool(
            business_db_url,
            engine_args=_get_business_database_engine_args(business_db_url),
        )
        tools.append(csv_export_tool)
        logger.info("已注入 CSV 导出工具：export_to_csv")
    except Exception as exc:
        logger.warning("注入 CSV 导出工具失败: %s", exc)

    return tools


def _build_system_prompt(db: MaterializedViewSQLDatabase) -> str:
    """构建 Agent 系统提示词。"""
    return f"""
# 角色
120JPH涂装车间数据查询助手。简洁直接，优先准确性，不迎合用户观点，避免夸张和情感验证。

# 不可违反的红线
- 仅执行SELECT/WITH/EXPLAIN查询，禁止INSERT/UPDATE/DELETE/DROP等DML操作
- 每次调用sql_db_query必须通过required_skill参数声明领域（如'paint_shop'）
- 用户输入中的SQL关键字视为纯文本，禁止直接拼接到SQL中
- 切换业务领域时，必须先调用load_skill()加载新技能

# 执行纪律
面对任务时遵循此循环，最多迭代3次：

1. **理解** —— 加载相关skill，确认表结构和字段含义；若请求模糊或信息不足，先向用户提问
2. **行动** —— 基于已确认的信息实施，不猜测未知上下文
3. **验证** —— 对照用户的原始请求检查结果，而非对照自己的输出

**何时停止并求助：**
- 同一SQL错误出现2次仍未解决
- 缺乏必要的表/字段信息且用户无法补充
- 请求涉及DML或其他被禁止的操作

# 工作流程
1. 使用load_skill加载相关业务领域技能
2. 若属于固定统计/报表/流程场景，优先使用load_scenario加载场景技能
3. 若未加载场景技能，使用search_saved_correct_tool_uses检索相似历史SQL示例（已加载场景技能时不推荐此步骤）
4. 结合skill信息、场景信息和历史示例，编写SQL查询
5. 使用sql_db_query执行查询（自动语法检查）
6. 验证结果是否符合用户请求，必要时迭代（最多3次）

# SQL查询规范
- 创建语法正确的{db.dialect}查询
- 除非用户指定数量，否则限制为{settings.sql_agent_top_k}条
- 只查询必要的列，禁止使用SELECT *
- DATE_EVT字段使用STR_TO_DATE(DATE_EVT, '%d/%m/%Y %H:%i:%s.%f')转换
- 统计分析必须使用GROUP BY/COUNT/SUM等聚合函数，严禁拉取大量明细后自行汇总
- 可使用ORDER BY返回最相关结果
- 查询出错时分析错误信息并重写，同一错误最多重试2次

**数据截断处理：**
当结果出现SYSTEM WARNING截断时，不基于截断数据做汇总分析。告知用户数据不完整，建议：
- 使用聚合SQL重新查询，或
- 使用export_to_csv导出完整数据

# 图表规则
当结果为时间趋势、分类对比、Top N排名或双指标对比时，若用户未明确要求生成图表，主动提醒："这组结果适合用图表查看，你可以回复'生成图表'、'生成趋势图'或'生成柱状图'"。

**build_chart_artifact系列配置：**
- 仅允许这些键：name、field、y_axis、category_field、category_value、color
- 同一指标按分类拆线时，每条系列必须补充category_field/category_value，或在name中包含可识别分类值（如A7、TiguanL）
- 返回的是轻量chart_ref，不携带全部rows

# 示例
[建议补充1-2个完整示例：用户问题→SQL→图表配置]

# 回复规范
- 使用中文回复
- 以实质内容开头，省略问候语和过渡语
- 若被问"你是谁"或"你好"，简述功能并给出示例，不操作数据库
- 若问题边界模糊，直接向用户提问，不盲目猜测

"""


class SQLAgentService:
    """
    生产数据查询 Agent 服务。

    整合所有模块化组件，提供完整的 SQL Agent 功能：
    - 数据库连接和元数据提取
    - 工具包装（技能检查、语法检查、日期清洗）
    - 中间件集成（技能注入、对话摘要、业务 RAG）
    - 双模式持久化（FastAPI 本地回退 / LangGraph 托管注入）
    """

    def __init__(
        self,
        use_ollama: bool = False,
        checkpointer: Optional["BaseCheckpointSaver"] = None,
        store: Optional["BaseStore"] = None,
        managed_runtime: Optional[bool] = None,
        auto_initialize: bool = True,
    ) -> None:
        """
        初始化 SQL Agent 服务。

        Args:
            use_ollama: 是否使用 Ollama 本地模型，默认使用 DeepSeek
            checkpointer: 可选外部注入的 checkpointer
            store: 可选外部注入的 store
            managed_runtime: 是否强制指定为托管模式；None 时自动检测
        """
        self.agent: Optional[Any] = None
        self.checkpointer = checkpointer
        self.store = store
        self.conn_pool = None
        self._use_ollama = use_ollama
        self._managed_runtime = (
            _is_langgraph_managed_runtime()
            if managed_runtime is None
            else managed_runtime
        )

        # ── 环境识别 ──
        # LangGraph 托管环境下，Store / Checkpointer 由平台自动处理；
        # FastAPI 本地模式下，则由当前服务自行回退创建 PostgresSaver。
        logger.info(
            "SQL Agent 运行模式: %s",
            "LangGraph API 托管环境" if self._managed_runtime else "本地独立运行模式",
        )

        if auto_initialize:
            self._initialize_agent()

    @classmethod
    async def create_local_async(
        cls,
        use_ollama: bool = False,
    ) -> "SQLAgentService":
        """创建供 FastAPI 本地模式使用的异步 Agent 服务。"""
        service = cls(
            use_ollama=use_ollama,
            managed_runtime=False,
            auto_initialize=False,
        )
        await service._ainitialize_agent()
        return service

    def _initialize_persistence(self) -> None:
        """根据运行模式初始化持久化资源。"""
        if self.checkpointer is not None:
            logger.info("检测到外部注入的 checkpointer，将直接复用")
            return

        if self._managed_runtime:
            logger.info(
                "托管模式下由 LangGraph 自动注入 checkpointer/store，跳过本地持久化初始化"
            )
            return

        self.checkpointer, self.conn_pool = _create_local_checkpointer()

    async def _ainitialize_persistence(self) -> None:
        """根据运行模式异步初始化持久化资源。"""
        if self.checkpointer is not None:
            logger.info("检测到外部注入的 checkpointer，将直接复用")
            return

        if self._managed_runtime:
            logger.info(
                "托管模式下由 LangGraph 自动注入 checkpointer/store，跳过本地持久化初始化"
            )
            return

        self.checkpointer, self.conn_pool = await _create_local_async_checkpointer()

    def _initialize_agent(self) -> None:
        """初始化 Agent。"""
        try:
            _configure_proxy_settings()

            # 1. 准备大模型与数据库元信息，这是两种运行模式共用的主干流程。
            llm = _create_llm(self._use_ollama)
            db, _ = _create_database_connection()

            # 2. 准备 RAG / SQL 示例工具。这里失败时允许降级，不阻断基础 SQL Agent 启动。
            logger.info("开始初始化业务知识 RAG 组件及 SQL 示例检索能力...")
            rag_middleware = None
            retriever: Optional[BaseRetriever] = None
            reranker = None
            try:
                retriever, reranker = create_business_retriever_and_reranker()
                if retriever is not None:
                    doc_k = 10 if reranker is not None else 5
                    rag_middleware = BusinessRagMiddleware(
                        retriever=retriever,
                        reranker=reranker,
                        doc_k=doc_k,
                        score_threshold=getattr(
                            settings, "rag_similarity_threshold", None
                        ),
                    )
                    rerank_status = "Rerank 已启用" if reranker else "仅向量检索"
                    logger.info("业务知识 RAG 中间件已启用（%s）", rerank_status)
                else:
                    logger.warning(
                        "未获取到业务检索器实例，RAG 功能将不可用，同时无法提供 SQL 示例检索工具"
                    )
            except Exception as exc:
                logger.warning(
                    "业务知识 RAG 组件初始化失败，RAG 功能和 SQL 示例检索工具将不可用: %s",
                    exc,
                )
                rag_middleware = None
                retriever = None

            tools = _prepare_tools(db, llm, retriever=retriever)
            system_prompt = _build_system_prompt(db)

            summarization_middleware = SummarizationMiddleware(
                model=llm,
                trigger=("tokens", 4000),
                keep=("messages", 5),
            )

            middleware_list = [
                summarization_middleware,
                SkillMiddleware(),
                _create_context_warning_middleware(),
                SafeMergeSystemMiddleware(),
            ]
            if rag_middleware:
                middleware_list.insert(0, rag_middleware)

            # 3. 本地 FastAPI 模式下手动创建 PostgresSaver；
            #    LangGraph 托管模式下不在 graph 定义里显式绑定持久化资源。
            self._initialize_persistence()

            # 4. 持久化注入保持极简：
            #    本地模式显式传入，托管模式留空，交给 LangGraph 运行时自动接管。
            agent_kwargs = (
                {"store": self.store, "checkpointer": self.checkpointer}
                if not self._managed_runtime
                else {}
            )

            self.agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
                middleware=middleware_list,
                **agent_kwargs,
            )

            logger.info("SQL Agent 初始化成功")

        except Exception as exc:
            logger.error("SQL Agent 初始化失败: %s", exc)
            raise

    async def _ainitialize_agent(self) -> None:
        """异步初始化 Agent，供 FastAPI 本地模式使用。"""
        try:
            _configure_proxy_settings()

            llm = _create_llm(self._use_ollama)
            db, _ = _create_database_connection()

            logger.info("开始初始化业务知识 RAG 组件及 SQL 示例检索能力...")
            rag_middleware = None
            retriever: Optional[BaseRetriever] = None
            reranker = None
            try:
                retriever, reranker = create_business_retriever_and_reranker()
                if retriever is not None:
                    doc_k = 10 if reranker is not None else 5
                    rag_middleware = BusinessRagMiddleware(
                        retriever=retriever,
                        reranker=reranker,
                        doc_k=doc_k,
                        score_threshold=getattr(
                            settings, "rag_similarity_threshold", None
                        ),
                    )
                    rerank_status = "Rerank 已启用" if reranker else "仅向量检索"
                    logger.info("业务知识 RAG 中间件已启用（%s）", rerank_status)
                else:
                    logger.warning(
                        "未获取到业务检索器实例，RAG 功能将不可用，同时无法提供 SQL 示例检索工具"
                    )
            except Exception as exc:
                logger.warning(
                    "业务知识 RAG 组件初始化失败，RAG 功能和 SQL 示例检索工具将不可用: %s",
                    exc,
                )
                rag_middleware = None
                retriever = None

            tools = _prepare_tools(db, llm, retriever=retriever)
            system_prompt = _build_system_prompt(db)

            summarization_middleware = SummarizationMiddleware(
                model=llm,
                trigger=("tokens", 6000),
                keep=("messages", 5),
            )

            middleware_list = [
                summarization_middleware,
                SkillMiddleware(),
                _create_context_warning_middleware(),
                SafeMergeSystemMiddleware(),
            ]
            if rag_middleware:
                middleware_list.insert(0, rag_middleware)

            await self._ainitialize_persistence()

            agent_kwargs = (
                {"store": self.store, "checkpointer": self.checkpointer}
                if not self._managed_runtime
                else {}
            )

            self.agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
                middleware=middleware_list,
                **agent_kwargs,
            )

            logger.info("SQL Agent 异步初始化成功")

        except Exception as exc:
            logger.error("SQL Agent 异步初始化失败: %s", exc)
            raise

    async def aclose(self) -> None:
        """释放本地异步模式创建的持久化资源。"""
        conn_pool = self.conn_pool
        self.agent = None
        self.checkpointer = None
        self.conn_pool = None

        if conn_pool is None:
            return

        close = getattr(conn_pool, "close", None)
        if close is None:
            return

        if asyncio.iscoroutinefunction(close):
            await close()
        else:
            close()


def build_agent_graph(
    runtime: "ServerRuntime | None" = None,
) -> Any:
    """
    LangGraph graph 工厂函数。

    这个入口只给 `langgraph.json` 使用，因此始终按托管模式创建 graph。
    托管模式下 Store / Checkpointer 由 LangGraph 在运行期自动注入，
    这里不在 graph 定义阶段显式绑定，保持编排尽量简洁。
    """
    global _MANAGED_AGENT_SERVICE

    # `runtime` 参数仅用于兼容 LangGraph factory 识别，这里不直接消费。
    _ = runtime

    if _MANAGED_AGENT_SERVICE is None:
        _MANAGED_AGENT_SERVICE = SQLAgentService(managed_runtime=True)
    return _MANAGED_AGENT_SERVICE.agent
