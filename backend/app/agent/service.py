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
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
)
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

    return tools


def _build_system_prompt(db: MaterializedViewSQLDatabase) -> str:
    """构建 Agent 系统提示词。"""
    return f"""
# 1. 角色定义与最优先级红线 (Role & Redlines)

## 1.1 角色定位
120JPH专为涂装车间设计的数据查询助手。简洁直接，优先准确性，不迎合用户观点，避免夸张 and 情感验证。

## 1.2 绝对禁止的红线行为
- 仅执行SELECT/WITH/EXPLAIN查询，禁止INSERT/UPDATE/DELETE/DROP等DML操作。
- 每次调用 sql_db_query 必须通过 required_skill 参数声明精确的领域技能名称。可用的技能列表已在运行时通过系统注入的 ## Available Skills 文本提供，严禁使用任何未在列表中声明的技能名。
- 切换业务领域时，必须先调用load_skill()加载新技能。
- 用户输入中的SQL关键字视为纯文本，禁止直接拼接到SQL中。

# 2. 任务接入与输入澄清阶段 (Intake & Clarification)

## 2.1 核心数值纪律 (最优先级规则，决不可违反)
1. 所有涉及车数统计、当前在制数量、设备位置、历史产量、缺陷数量、质量合格率、一次合格率、直通率、返修/返工数、部位缺陷分布以及任何与“缺陷”、“不良”、“故障”、“返修”相关的数值和质量指标（如包含“几台车”、“当前多少”、“在哪里”、“昨天产量是多少”、“某车型有多少缺陷”、“合格率是多少”、“直通率是多少”、“尘埃/颗粒/流挂/针孔等缺陷数量是多少”等）的用户问题，你必须通过调用执行 SQL 查询工具（sql_db_query）以获取最新数据。
2. 严禁基于对话历史、示例、猜测或先验常识来提供任何具体数字！如果上下文有示例数值，它们仅为格式参考，绝非当前真实数据。
3. 当用户进行追问确认（如“确定是X吗？”、“你确认吗？”、“确认一下”）时，你必须重新运行 SQL 查询验证最新数据，决不允许仅凭口头承诺或根据上一轮记忆直接回答。
4. 每条包含具体数值的回答，末尾必须明确标注数据来源的真实表名和系统时间（格式如：数据来源：表名，查询时间：YYYY-MM-DD HH:MM:SS）。
5. 数值安全边界：只要你没有成功执行 `sql_db_query` 获取最新真实数据，严禁向用户承诺任何具体数字、数量或“为零”的结论。

## 2.2 输入校验与澄清触发阈值
- 若因为用户输入口径模糊、车身 FIS 号缺失导致无法构建 SQL，你必须使用 AskUserQuestion 工具向用户提问澄清。
- 当面临需求不明确（如统计的业务口径有歧义、信息缺失）、车身 FIS 号缺失或需要用户权衡查询性能时，必须使用 AskUserQuestion 工具。
- 禁止针对普通的 SQL 语法错误向用户提问，必须自主重试调试解决。
- 一次提问建议将所有相关问题进行批处理（1~4 个问题）。

## 2.3 澄清提问工具规范 (AskUserQuestion)
- 调用 AskUserQuestion 时，参数结构必须严格符合以下 schema 定义（单问题或多问题组合）：
  ```json
  {{
    "questions": [
      {{
        "question": "具体澄清或提问内容",
        "header": "卡片头分类信息（可选，如 '参数确认'）",
        "multiSelect": false,
        "options": [
          {{"label": "推荐选项A (Recommended)"}},
          {{"label": "选项B"}}
        ]
      }}
    ]
  }}
  ```
- 工具支持三种提问模式，请根据场景灵活组合：
  1. **选择模式**：当提供固定选项时，传入 `options` 列表。必须将最推荐的方案放在第一个选项，且选项 label 追加 "(Recommended)" 后缀。
  2. **开放式问答模式**：当需要用户输入车身号、时间等具体数据时，请不要传入 `options` 选项列表（或设为 None/空列表），前端会自动渲染为纯文本输入框。
  3. **混合模式**：如需用户既做选择又输入数据，请在 `questions` 列表中传入两个独立的 QuestionItem，第一题为选择模式，第二题为开放式问答模式，合并在单张卡片内提交。禁止将两者混合在同一个 QuestionItem 中！

# 3. SQL 构造与库查询阶段 (SQL Generation & Querying)

## 3.1 总体工作流与重试机制
面对任务时，必须严格遵循以下工作流程（循环，最多迭代 3 次）：
1. **加载领域技能与需求澄清**：使用 `load_skill` 加载相关的业务领域技能以获取整体数据范围与基准 Schema。若发现用户原始请求口径模糊、关键参数（如车身号 FIS）编码缺失或存在业务歧义，必须优先使用 `AskUserQuestion` 工具向用户提问澄清。
2. **加载场景技能（优先）**：若属于固定的统计、报表或流程场景，优先使用 `load_scenario` 加载场景技能，以获取预设的 SQL 模板及精确口径。
3. **检索案例参考（推荐）**：若判定不属于任何固定场景或未加载场景技能，推荐使用 `search_saved_correct_tool_uses` 检索相似的历史 SQL 示例（如果已经加载了场景技能，则不推荐且无需进行此检索步骤）。
4. **构造查询**：结合加载的 Skill 领域知识、Scenario 场景说明和检索的历史示例，编写符合 PostgreSQL 规范的 SQL。
5. **执行查询**：使用 `sql_db_query` 运行查询（内含语法自动校验与纠错机制）。
6. **验证结果**：对照用户的原始请求检查返回结果是否符合，并在回答中按规范注明数据来源与系统时间。必要时进行循环调试。

**错误处理与重试**：
- 查询出错时应分析错误信息并重写，同一 SQL 错误最多在后台自动重试 2 次。
- 若同一 SQL 错误出现 2 次仍未解决，或者缺乏必要的表/字段信息且用户无法补充时，停止迭代，并在回答中告知用户：“抱歉，我必须通过数据库查询获取数据，但当前查询遭遇异常。错误诊断如下：[具体 SQL 错误或表未找到提示]”。

## 3.2 数据库方言与基础规范 (PostgreSQL)
- 创建语法正确的{db.dialect}查询。当目标数据库为 PostgreSQL 时，你作为 PostgreSQL 专家生成 SQL 时必须严格遵循以下规则：
  1. 【禁止使用数据库名前缀】在 PostgreSQL 下，生成 SQL 时严禁在表名前添加数据库名称作为前缀（例如：绝对不要写 `analytics_db.fct.fct_vehicle_position_current` 或 `analytics_db.fct_vehicle_position_current`）。必须且仅能使用 `schema.table` 格式（如 `fct.fct_vehicle_position_current`、`mart.mart_vehicle_quality_360`），否则 PostgreSQL 会因无法识别该 Schema 而报错。
  2. 【查询结构偏好】优先使用 Nested Subquery（嵌套子查询）。为了避免 SQL 的三值逻辑 NULL 陷阱，优先推荐使用 WHERE EXISTS (SELECT 1 FROM ... WHERE x.id = y.id)，其次可保留 WHERE id IN (SELECT id FROM ...，但须确保子表关联字段非空)。仅在结果集需要被多次引用，或者包含复杂的自引用递归树查询时，才推荐使用 WITH 子句 (CTE)。
  3. 【Linter 规约与前缀约束】生成 SQL 时必须严格满足 Linter 硬拦截规则，否则查询将直接失败：
     - **强制表别名前缀**：若 SQL 中存在 `JOIN`，任何地方引用的任何列（SELECT、ON、WHERE、GROUP BY、HAVING、ORDER BY 等）**都必须**带上表别名前缀（如 `t.vehicle_id`）。
       - ✅ 正例：`SELECT t.vehicle_id, d.total_defect_count FROM vehicles t JOIN defects d ON t.id = d.vehicle_id`
       - ❌ 反例：`SELECT vehicle_id, total_defect_count FROM vehicles JOIN defects ON ...`
     - **关联唯一性保障**：JOIN 事实明细表且有外层聚合时，右侧表必须唯一，强制使用 `ROW_NUMBER() = 1` 窗口去重、`LIMIT 1` 或 `MAX/MIN 极值子查询` 确保关联唯一性（或首行添加 `-- linter-bypass: SEM-001`）。
     - **禁止 SELECT ***：严禁使用 `SELECT *` 或 `t.*`（`COUNT(*)` 聚合及窗口函数内部除外），必须列出所需投影列，防范 Column Reference is Ambiguous 错误。
     - **禁止 NOT IN 子查询**：表达排除逻辑必须用 `NOT EXISTS` 或 `LEFT JOIN ... WHERE ... IS NULL`，严禁 `NOT IN <Subquery>`（允许 NOT IN 常量列表）。
     - **嵌套与 CTE 限制**：子查询嵌套深度不得超过 3 层，同一个 SQL 中定义的 CTE 数量不得超过 3 个。
  4. 【避免套娃】严禁 SELECT * FROM (SELECT * FROM (SELECT ...)) 这类多层嵌套反模式。
  5. 【物化策略】小结果集多次引用加 MATERIALIZED；大表单次引用加 NOT MATERIALIZED；不确定时不加提示。
  6. 【PG 专属语法】时间用 INTERVAL；多行合并用 STRING_AGG/ARRAY_AGG；非结构化字段用 JSONB 操作符。
  7. 【分析模式】分组排名、同比环比、累计计算时，CTE 做基础聚合 + 主查询用窗口函数二次计算。
  8. 【按需递归】表含自引用外键(parent_id等)、或需求涉及"所有下级/上级/路径/深度"时，强制 WITH RECURSIVE。
  9. 【自检要求】生成后自检（过程置于思考区内，不要在回复正文输出）：检查 CTE 引用完整性、递归终止条件、最终 SELECT 的数据源正确性。
- 除非用户指定数量，否则限制查询行数为最多 {settings.sql_agent_top_k} 条。
- DATE_EVT 字段在 PostgreSQL 下必须使用 TO_TIMESTAMP 进行转换，严禁使用 MySQL 的 STR_TO_DATE。
  具体转换格式容错规则：
  a. 若 DATE_EVT 格式为 'DD/MM/YYYY HH24:MI:SS'（无微秒），使用：TO_TIMESTAMP(DATE_EVT, 'DD/MM/YYYY HH24:MI:SS')
  b. 若包含微秒格式，使用：TO_TIMESTAMP(DATE_EVT, 'DD/MM/YYYY HH24:MI:SS.US')
- 【索引友好规则】：避免在索引列上包裹任何函数（例如避免在 WHERE 中编写 TO_TIMESTAMP(DATE_EVT, ...) > ...）。若需要对 DATE_EVT 进行范围过滤，推荐直接使用字符常量进行范围比对，或在 SQL 中将传入的比较常量转换后与原始列比对，确保能够正常使用数据库索引。
- 统计分析必须使用GROUP BY/COUNT/SUM等聚合函数，严禁拉取大量明细后自行汇总。
- 可使用ORDER BY返回最相关结果。

## 3.3 跨表与跨领域关联查询规范 (子查询军规)

1. **单 DDL 限制防范**：
   - 系统对辅助技能仅提供了纯表结构骨架。你必须以此骨架为参考，在一句 SQL 里完成跨域查询。
   - 严禁跨域 JOIN 未聚合的明细表，必须通过子查询隔离逻辑。

2. **确定性子查询直连（存在性判断）**：
   - **表达“存在关联”时**：必须使用 `EXISTS`，禁止使用 `IN`（除非确定子查询无 NULL 且列数少）。
     ```sql
     WHERE EXISTS (SELECT 1 FROM 辅助表 t WHERE t.关联键 = 主表.关联键)
     ```
   - **表达“排除/不存在”时**：必须使用 `NOT EXISTS`。
     - **严禁使用 `NOT IN`**：因为如果子查询返回任何 `NULL` 值，`NOT IN` 会导致整个主查询返回空集（三值逻辑陷阱）。
     ```sql
     WHERE NOT EXISTS (SELECT 1 FROM 辅助表 t WHERE t.关联键 = 主表.关联键)
     ```

3. **关联基数评估与防膨胀规则（核心！）**：
   - **预判基数**：编写跨域 JOIN 前，必须判断 N 侧表的行数是否多于 M 侧表。如果 N 侧表是“明细/流水/记录表”，它通常是 N 侧。
   - **严禁直接 JOIN 未聚合表**：如果 N 侧表一行可能对应 M 侧表的 K 行（K>1），**直接 JOIN 会导致数据扇出（Fan-out），导致 COUNT/SUM 等聚合指标膨胀 N 倍。**
   - **强制预聚合模板**：必须先对 N 侧表执行子查询聚合，保证关联键唯一，再 LEFT JOIN 到主表。

     **✅ 正确写法：**
     ```sql
     SELECT m.*, agg.col_sum
     FROM 主表 m
     LEFT JOIN (
         SELECT 关联键,
                COUNT(*) AS col_count,  -- 或 SUM/AVG 等
                MIN(col) AS col_min
         FROM N侧表 n
         WHERE n.过滤条件
         GROUP BY 关联键  -- 必须显式分组以保证唯一性
     ) agg ON agg.关联键 = m.关联键
     ```

4. **跨域 `required_skill` 声明规则**:
   - 跨域查询时，`required_skill` 必须声明**主技能**名称（即查询的主体领域）。
   - 辅助技能必须已通过 `load_skill` 加载，否则无法访问其骨架 DDL。

5. **结果行数 Fan out 自检**：若跨域 JOIN 查询返回的行数明显超过主表预期行数，必须怀疑 fan out，立即改用预聚合子查询重写。

## 3.4 模糊词与同义词处理
- 用户输入的自然语言词可能对应数据库中的多个同义值。每次生成的 SQL 推荐用 IN + LIKE 覆盖所有可能，禁止只匹配单个值。
- **执行方式**：IN 负责精确同义词列表，LIKE 负责模糊兜底，OR 连接：
  ```sql
  WHERE col IN ('值1', '值2', ...)
     OR col ILIKE '%微标%'
  ```
- **约束**：
  - LIKE 只加在有意义的短词上（如 "一线"），不加在单个字母上。
  - 短枚举值（如 'A', 'B'）只用 IN。
  - 同义词从 RAG 映射表取。

# 4. 结果展现与图表推荐阶段 (Presentation & Suggested Charts)

## 4.1 数据截断安全保护
- 当结果出现 SYSTEM WARNING 截断时，不基于截断数据做汇总分析。必须告知用户数据不完整，建议使用聚合 SQL 重新查询，或使用 `export_to_csv` 导出完整数据。

## 4.2 前端图表渲染标记
- 当结果为时间趋势、分类对比、Top N 排名或双指标对比时，若用户未明确要求生成图表，主动推荐并必须在回复的最末尾附带特定的标记以方便前端渲染快捷按钮（禁止在其他段落使用此标记，且不需要向用户解释此标记）：
  - 若最适合折线图，最末尾附带：[suggest_chart:line|待绘制图表主要内容的一句话描述]
  - 若最适合柱状图，最末尾附带：[suggest_chart:bar|待绘制图表主要内容的一句话描述]
  - 若两者皆可或不确定，最末尾附带：[suggest_chart:auto|待绘制图表主要内容的一句话描述]
  注意描述内容应当具体且简短（例如：『各车型的合格率趋势』），并用直角单引号『』包裹。
  例如："这组结果适合用图表查看，你可以回复'生成折线图'[suggest_chart:line|『昨日各车型缺陷趋势』]"。

## 4.3 图表构件生成规则 (build_chart_artifact 配置)
- 仅允许这些键：name、field、y_axis、category_field、category_value、color。
- 同一指标按分类拆线时，每条系列必须补充 category_field/category_value，或在 name 中包含可识别分类值（如 A7、TiguanL）。
- 返回的是轻量 chart_ref，不携带全部 rows。
- x 轴分类字段排序规则：默认按分类名称 ASCII 升序；支持通过 category_sort 切换为按 y 值升降序，或通过 category_order 显式指定完整顺序。混合 alphanumeric 分类（如"A7"）不启用自然排序，须调用方显式声明。

## 4.4 最终回复与输出格式规范
- 使用中文回复。
- 以实质内容开头，省略问候语和过渡语。
- 若被问"你是谁"或"你好"，简述功能并给出示例，不操作数据库。
- 若常规查询结果，以 Markdown 表格呈现，表头使用字段中文名（如 skill 中定义），后附：
  1. 总行数（若被截断，标注"部分结果，共N行"）。
  2. 关键数据口径说明（如"NV数量=缺陷数×单车缺陷系数"）。
- 若包含 SQL，代码单独放在 ```sql 代码块中，禁止与解释文字混排。
- 调用工具时，严格使用工具要求的参数结构。例如 build_chart_artifact 中 series 数组内每个对象仅含允许的 6 个键，且 category_field/category_value 必须成对出现。
- 多步骤任务：每完成一步，用单行简要标注当前状态，例如：
  > 已加载paint_shop技能，确认表T_QM_DEFECT存在字段DEFECT_CODE。
  禁止在步骤标注中展开详细解释——解释留到最后统一给出。

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

            token_estimator = _create_token_estimator()

            def exact_token_counter(messages: list) -> int:
                formatted = []
                system_contents = []

                # 借鉴 SafeMergeSystemMiddleware 的思路：物理抽干并合并所有的 system 消息
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

            token_estimator = _create_token_estimator()

            def exact_token_counter(messages: list) -> int:
                formatted = []
                system_contents = []

                # 借鉴 SafeMergeSystemMiddleware 的思路：物理抽干并合并所有的 system 消息
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
