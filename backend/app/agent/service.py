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
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from backend.app.agent.constants import EXCLUDED_TOOLS, ToolNames
from backend.app.agent.middleware import (
    BusinessRagMiddleware,
    ContextWarningMiddleware,
    SkillMiddleware,
    PromptCompilerMiddleware,
)
from backend.app.agent.tools import (
    create_chart_artifact_tool,
    create_csv_export_tool,
    create_sql_example_search_tool,
    create_wrapped_query_tool,
)
from backend.app.agent.tools.ask_user_question import AskUserQuestion
from backend.app.agent.utils import (
    LlamaCppTokenEstimator,
    VllmTokenEstimator,
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


def _create_token_estimator() -> Any:
    """根据配置创建 Token 估算器实例。"""
    engine = getattr(settings, "token_estimator_engine", "llama_cpp").lower()
    if engine == "vllm":
        # 如果 vllm_tokenize_base_url/model 为空字符串，则通过 or 回退到 deepseek 的默认配置
        base_url = getattr(settings, "vllm_tokenize_base_url", None) or getattr(
            settings, "deepseek_base_url", "http://127.0.0.1:8089"
        )
        model_name = getattr(settings, "vllm_tokenize_model", None) or getattr(
            settings, "deepseek_model", "deepseek-chat"
        )

        return VllmTokenEstimator(
            base_url=base_url,
            model_name=model_name,
            timeout=settings.llm_context_tokenizer_timeout,
        )
    else:
        return LlamaCppTokenEstimator(
            base_url=settings.llama_cpp_tokenize_base_url,
            timeout=settings.llm_context_tokenizer_timeout,
        )


def _create_context_warning_middleware(estimator: Any) -> ContextWarningMiddleware:
    """创建上下文窗口告警中间件。"""
    return ContextWarningMiddleware(
        estimator=estimator,
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
        extra_body["chat_template_kwargs"] = {
            "enable_thinking": settings.llm_enable_thinking
        }

    if extra_body:
        kwargs["extra_body"] = extra_body

    logger.info(
        "Initializing ChatOpenAI with arguments: %s",
        {k: v for k, v in kwargs.items() if k != "openai_api_key"},
    )
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
    lexicon_retriever: Optional[Any] = None,
) -> list:
    """
    准备 Agent 工具列表。

    Args:
        db: SQLDatabase 实例
        llm: LLM 实例
        retriever: 可选业务检索器，用于 SQL 示例检索
        lexicon_retriever: 可选物理词典检索器，用于纠偏/结构自愈

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
        chart_artifact_tool = create_chart_artifact_tool(db._engine)
        tools.append(chart_artifact_tool)
        logger.info("已注入图表 artifact 工具：build_chart_artifact")

        csv_export_tool = create_csv_export_tool(db._engine)
        tools.append(csv_export_tool)
        logger.info("已注入 CSV 导出工具：export_to_csv")
    except Exception as exc:
        logger.warning("注入图表/CSV导出工具失败: %s", exc)

    try:
        tools.append(AskUserQuestion())
        logger.info("已注入澄清与确认工具：AskUserQuestion")
    except Exception as exc:
        logger.warning("注入澄清与确认工具失败: %s", exc)

    if lexicon_retriever is not None:
        try:
            from backend.app.agent.tools.sql_lexicon_tools import (
                create_db_value_lexicon_tool,
                create_db_row_lexicon_tool,
                create_db_table_schema_tool,
            )

            tools.append(create_db_value_lexicon_tool(lexicon_retriever))
            tools.append(create_db_row_lexicon_tool(lexicon_retriever))
            tools.append(create_db_table_schema_tool(lexicon_retriever))
            logger.info(
                "已注入物理词典纠偏/探索工具集 (search_db_value_lexicon, search_db_row_lexicon, search_db_table_schema)"
            )
        except Exception as exc:
            logger.warning("注入物理词典工具失败: %s", exc)

    return tools


class SystemPromptLoader:
    """系统提示词动态加载器，支持缓存和热重载。"""

    _lock = threading.Lock()

    def __init__(self, template_path: str):
        self.template_path = Path(template_path)
        self._cached_prompt: str = ""
        self._last_modified_time: float = 0.0

    def load(self, force_reload: bool = False) -> str:
        """加载提示词模板并返回（带缓存和热重载）。"""
        if not self.template_path.exists():
            raise FileNotFoundError(f"系统提示词模板文件不存在: {self.template_path}")

        mtime = self.template_path.stat().st_mtime
        should_reload = (
            not self._cached_prompt
            or force_reload
            or (settings.debug and mtime > self._last_modified_time)
        )

        if should_reload:
            with self._lock:
                # 双重检查，避免并发重复加载
                if (
                    not self._cached_prompt
                    or force_reload
                    or (settings.debug and mtime > self._last_modified_time)
                ):
                    logger.info("加载系统提示词模板: %s", self.template_path)
                    self._cached_prompt = self.template_path.read_text(encoding="utf-8")
                    self._last_modified_time = mtime

        return self._cached_prompt


_system_prompt_loader = SystemPromptLoader(settings.system_prompt_path)


def _build_system_prompt(db: MaterializedViewSQLDatabase) -> str:
    """构建 Agent 系统提示词。"""
    template_str = _system_prompt_loader.load()
    template = PromptTemplate.from_template(template_str)
    return template.format(
        dialect=db.dialect,
        top_k=settings.sql_agent_top_k,
    )


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
                    # 在主线程/主事件循环环境下，提前对惰性初始化的检索器进行连接预热
                    if hasattr(retriever, "warmup"):
                        retriever.warmup()
                    doc_k = 10 if reranker is not None else 5
                    rag_middleware = BusinessRagMiddleware(
                        retriever=retriever,
                        reranker=reranker,
                        doc_k=doc_k,
                        score_threshold=getattr(
                            settings, "rag_similarity_threshold", None
                        ),
                        db=db,
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

            lexicon_retriever = rag_middleware.lexicon_retriever if rag_middleware else None
            tools = _prepare_tools(db, llm, retriever=retriever, lexicon_retriever=lexicon_retriever)
            system_prompt = _build_system_prompt(db)

            token_estimator = _create_token_estimator()

            def exact_token_counter(messages: list) -> int:
                formatted = []
                system_contents = []

                # 借鉴 PromptCompilerMiddleware 的思路：物理抽干并合并所有的 system 消息
                for m in messages:
                    msg_type = getattr(m, "type", "")
                    if msg_type == "system":
                        system_contents.append(str(m.content))
                    else:
                        role = "user"
                        if msg_type == "human":
                            role = "user"
                        elif msg_type == "ai":
                            role = "assistant"
                        elif msg_type == "tool":
                            role = "tool"
                        formatted.append({"role": role, "content": str(m.content)})

                # 如果收集到了任何 system 消息，将其统一合并成一条，强制放置在最头部 [0] 索引位置
                if system_contents:
                    formatted.insert(
                        0, {"role": "system", "content": "\n\n".join(system_contents)}
                    )

                if hasattr(token_estimator, "count_messages_tokens"):
                    return token_estimator.count_messages_tokens(formatted)
                else:
                    return token_estimator.count_json_like_tokens(formatted)

            summarization_middleware = SummarizationMiddleware(
                model=llm,
                trigger=("tokens", settings.llm_context_summarize_trigger_tokens),
                keep=("messages", 5),
                token_counter=exact_token_counter,
            )

            # 构建调用限制中间件（防止Agent无限调用工具无法跳出）
            call_limit_middlewares: list[Any] = []
            if settings.agent_model_call_run_limit > 0:
                call_limit_middlewares.append(
                    ModelCallLimitMiddleware(
                        run_limit=settings.agent_model_call_run_limit,
                        exit_behavior=settings.agent_call_limit_exit_behavior,  # type: ignore[arg-type]
                    )
                )
            if settings.agent_tool_call_run_limit > 0:
                call_limit_middlewares.append(
                    ToolCallLimitMiddleware(
                        run_limit=settings.agent_tool_call_run_limit,
                        exit_behavior=settings.agent_call_limit_exit_behavior,  # type: ignore[arg-type]
                    )
                )

            middleware_list = [
                *call_limit_middlewares,
                summarization_middleware,
                SkillMiddleware(db),
                _create_context_warning_middleware(token_estimator),
                PromptCompilerMiddleware(),
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
                    # 在主线程/主事件循环环境下，提前对惰性初始化的检索器进行连接预热
                    if hasattr(retriever, "warmup"):
                        retriever.warmup()
                    doc_k = 10 if reranker is not None else 5
                    rag_middleware = BusinessRagMiddleware(
                        retriever=retriever,
                        reranker=reranker,
                        doc_k=doc_k,
                        score_threshold=getattr(
                            settings, "rag_similarity_threshold", None
                        ),
                        db=db,
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

            lexicon_retriever = rag_middleware.lexicon_retriever if rag_middleware else None
            tools = _prepare_tools(db, llm, retriever=retriever, lexicon_retriever=lexicon_retriever)
            system_prompt = _build_system_prompt(db)

            token_estimator = _create_token_estimator()

            def exact_token_counter(messages: list) -> int:
                formatted = []
                system_contents = []

                # 借鉴 PromptCompilerMiddleware 的思路：物理抽干并合并所有的 system 消息
                for m in messages:
                    msg_type = getattr(m, "type", "")
                    if msg_type == "system":
                        system_contents.append(str(m.content))
                    else:
                        role = "user"
                        if msg_type == "human":
                            role = "user"
                        elif msg_type == "ai":
                            role = "assistant"
                        elif msg_type == "tool":
                            role = "tool"
                        formatted.append({"role": role, "content": str(m.content)})

                # 如果收集到了任何 system 消息，将其统一合并成一条，强制放置在最头部 [0] 索引位置
                if system_contents:
                    formatted.insert(
                        0, {"role": "system", "content": "\n\n".join(system_contents)}
                    )

                if hasattr(token_estimator, "count_messages_tokens"):
                    return token_estimator.count_messages_tokens(formatted)
                else:
                    return token_estimator.count_json_like_tokens(formatted)

            summarization_middleware = SummarizationMiddleware(
                model=llm,
                trigger=("tokens", settings.llm_context_summarize_trigger_tokens),
                keep=("messages", 5),
                token_counter=exact_token_counter,
            )

            # 构建调用限制中间件（防止Agent无限调用工具无法跳出）
            call_limit_middlewares: list[Any] = []
            if settings.agent_model_call_run_limit > 0:
                call_limit_middlewares.append(
                    ModelCallLimitMiddleware(
                        run_limit=settings.agent_model_call_run_limit,
                        exit_behavior=settings.agent_call_limit_exit_behavior,  # type: ignore[arg-type]
                    )
                )
            if settings.agent_tool_call_run_limit > 0:
                call_limit_middlewares.append(
                    ToolCallLimitMiddleware(
                        run_limit=settings.agent_tool_call_run_limit,
                        exit_behavior=settings.agent_call_limit_exit_behavior,  # type: ignore[arg-type]
                    )
                )

            middleware_list = [
                *call_limit_middlewares,
                summarization_middleware,
                SkillMiddleware(db),
                _create_context_warning_middleware(token_estimator),
                PromptCompilerMiddleware(),
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
