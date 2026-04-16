# backend/app/agent/tools/sql_tools.py
"""
SQL 查询工具工厂

提供包装后的 SQL 查询工具，集成：
1. 技能加载检查
2. 自动 SQL 语法检查
3. 日期格式标准化
4. 智能结果限流与超限预警

修改时间: 2026-04-12 03:00 Asia/Shanghai
主要修改内容:
- 默认返回带列名的结构化查询结果，降低 LLM 对 SELECT * 结果的误判风险
- 结果限流逻辑同时兼容旧元组格式与新字典格式
"""

import logging
import re
from typing import Any, List, Optional, Union

from langchain.tools import ToolRuntime, tool as langchain_tool

from backend.app.agent.constants import SQL_ERROR_KEYWORDS
from backend.app.agent.utils import emit_stream_status, normalize_dates_in_text
from backend.app.agent.vector.base import BaseRetriever
from backend.app.config import settings

logger = logging.getLogger(__name__)

# 禁止的 SQL 关键字正则模式 (DML/DDL)，用于保护数据库安全
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|REPLACE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE
)


def _estimate_row_count(result_text: str) -> int:
    """
    估算 LangChain sql_db_query 工具返回的结果字符串中的行数。

    当前工具优先返回带列名的 Python 字典列表文本表示，例如：
    "[{'col1': 'val1'}, {'col1': 'val2'}]"
    同时兼容历史版本的元组列表表示：
    "[('val1', 'val2'), ('val3', 'val4')]"
    """
    stripped = result_text.strip()
    if not stripped.startswith("["):
        return 0

    if stripped.startswith("[{"):
        count = result_text.count("}, {") + result_text.count("},\n{")
        if count == 0 and "{" in stripped:
            return 1
        return count + 1 if count > 0 else 0

    count = result_text.count("), (") + result_text.count("),\n(")

    # 特殊情况处理：
    # 1. 只有一行数据时，可能不包含分隔符
    if count == 0 and stripped.startswith("[") and "(" in result_text:
        return 1
    # 2. 空结果集
    return count + 1 if count > 0 else 0


def _extract_preview_rows(result_text: str, n: int) -> str:
    """
    从结果字符串中提取前 n 行作为预览。

    同时兼容元组列表与字典列表两种字符串表示。
    """
    stripped = result_text.strip()
    separator_pattern = r"\),\s*\("
    item_suffix = ")"

    if stripped.startswith("[{"):
        separator_pattern = r"\},\s*\{"
        item_suffix = "}"

    parts = re.split(separator_pattern, result_text)
    if len(parts) <= n:
        return result_text

    # 截取前 n 个元素并重新使用分隔符拼接
    preview_parts = parts[:n]
    join_token = "}, {" if item_suffix == "}" else "), ("
    preview = join_token.join(preview_parts)
    
    # re.split 会丢掉分隔符中匹配的部分，两端可能缺少闭合字符。
    if not preview.rstrip().endswith(item_suffix):
        preview += item_suffix
    if not preview.rstrip().endswith("]"):
        preview += "]"
    return preview


def create_wrapped_query_tool(
    original_query_tool: Any,
    original_checker_tool: Optional[Any] = None,
) -> Any:
    """
    创建包装后的 SQL 查询工具

    将原始的 sql_db_query 工具包装，添加以下功能：
    1. 检查是否已加载相关业务技能
    2. 自动执行 SQL 语法检查（如果 checker 工具可用）
    3. 对查询结果进行日期格式标准化

    Args:
        original_query_tool: 原始的 sql_db_query 工具
        original_checker_tool: 可选的 sql_db_query_checker 工具

    Returns:
        包装后的 sql_db_query 工具
    """

    @langchain_tool
    def sql_db_query(query: str, required_skill: str, runtime: ToolRuntime) -> str:
        """
        Execute a SQL query against the database and return results.

        IMPORTANT: You must specify the 'required_skill' parameter with the exact skill name
        that this query depends on (e.g., 'paint_shop_vehicle_tracking'). The skill must have been loaded
        via load_skill() first. If you are switching to a different business domain,
        call load_skill() for the new domain BEFORE calling this tool.

        The query will be automatically validated before execution.
        Results will have dates normalized to ISO 8601 format (YYYY-MM-DD).

        Args:
            query: A valid SQL query string.
            required_skill: The name of the skill/domain this query belongs to.
        """
        # 0. 安全性拦截：检查是否包含非法的 DML/DDL 关键字
        if FORBIDDEN_SQL_PATTERN.search(query):
            logger.warning(f"安全审计拦截：检测到危险 SQL 关键字。Query: {query}")
            return (
                "Error: 严重安全警告 - 该操作已被系统拦截。\n"
                "SQL Agent 仅允许执行只读查询 (SELECT)，禁止执行任何涉及修改数据 (INSERT, UPDATE, DELETE) "
                "或修改结构 (DROP, ALTER, TRUNCATE) 的指令。"
            )

        # 1. 精确技能加载校验：确认当前查询所需的特定技能已被加载
        skills_loaded = runtime.state.get("skills_loaded", [])
        if required_skill not in skills_loaded:
            return (
                f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再执行查询。\n"
                f"当前已加载的技能: {skills_loaded or '无'}。\n"
                "可用技能请查看系统提示中的 Available Skills 部分。"
            )

        # 2. 自动执行 SQL 语法检查（如果 checker 工具可用）
        if original_checker_tool is not None:
            emit_stream_status(
                "正在检查 SQL 语法",
                stage="querying",
                source="sql_db_query_checker",
            )
            check_result = original_checker_tool.invoke({"query": query})
            check_result_str = str(check_result).lower()

            # 检查是否有错误指示
            if any(err in check_result_str for err in SQL_ERROR_KEYWORDS):
                logger.warning("SQL 语法检查失败: %s", check_result)
                return f"SQL 语法检查失败:\n{check_result}\n请修正查询后重试。"

            logger.debug("SQL 语法检查通过")

        # 3. 执行查询
        emit_stream_status(
            "正在执行 SQL 查询",
            stage="querying",
            source="sql_db_query",
        )
        if hasattr(original_query_tool, "db") and hasattr(original_query_tool.db, "run_no_throw"):
            raw_result = original_query_tool.db.run_no_throw(
                query,
                include_columns=True,
            )
        else:
            raw_result = original_query_tool.invoke({"query": query})
        result_str = str(raw_result)

        # 4. 对查询结果的日期进行格式转换
        emit_stream_status(
            "已收到查询结果，正在整理数据",
            stage="writing",
            source="sql_db_query",
        )
        cleaned_result = normalize_dates_in_text(result_str)
        logger.debug("SQL 查询结果已清洗日期格式")

        # 5. 智能结果限流：防止数据库返回结果过大撑爆 LLM 上下文
        hard_limit = settings.sql_result_hard_limit       # 获取系统硬限制（如 1000 行），若超过则截断
        preview_rows = settings.sql_result_preview_rows   # 获取超限时返还给大模型的预览数据行数（如 5 行）
        estimated_rows = _estimate_row_count(cleaned_result) # 通过字符串特征估算查询结果的总行数

        if estimated_rows >= hard_limit:
            # 执行截断逻辑：只返回前 N 行预览数据 + 系统防御说明
            preview_data = _extract_preview_rows(cleaned_result, preview_rows)
            logger.warning(
                "SQL 查询结果超限截断: 估算行数=%d, 硬限制=%d, 预览行数=%d",
                estimated_rows, hard_limit, preview_rows,
            )
            # 这里的返回内容会被 Agent 直接作为观察内容 (Observation)，
            # 注入 SYSTEM WARNING 的目的是通过 Prompt 强力引导模型不要产生错误的汇总逻辑。
            return (
                f"⚠️ SYSTEM WARNING: 查询结果已达到系统硬限制 ({hard_limit} 行) 并被强制截断。\n"
                f"以下仅展示前 {preview_rows} 行数据预览，基于此数据进行的汇总分析可能不完整或不准确。\n\n"
                f"建议操作：\n"
                f"1. 如果用户需要完整原始数据，请建议使用 export_to_csv 工具导出为 CSV 文件下载。\n"
                f"2. 如果需要统计分析，请改写 SQL 使用 GROUP BY / COUNT / SUM 等聚合函数，让数据库完成计算。\n\n"
                f"数据预览 (前 {preview_rows} 行):\n{preview_data}"
            )

        # 情况 A: 未超限 - 说明结果集规模可控，全量返回（适合维度表查询或已聚合后的结果）
        logger.debug("SQL 查询结果未超限 (估算行数=%d), 全量返回", estimated_rows)
        return cleaned_result

    return sql_db_query


def create_sql_example_search_tool(
    retriever: BaseRetriever,
    *,
    top_k: int = 2,
) -> Any:
    """
    创建 SQL 示例检索工具 search_saved_correct_tool_uses。

    该工具用于根据用户的自然语言问题，检索历史上「已验证成功」的 SQL 示例，
    供 Agent 在编写最终 SQL 之前进行参考和改写（few-shot 学习）。

    返回结果为一个列表，每个元素包含：
      - question: 历史问题或说明文本
      - sql: 已成功执行的 SQL 语句
      - description: 示例的中文描述（如果有）
      - domain: 业务域（如果有）
      - score: 相似度/融合得分
    注意：调用前需要先使用 load_skill() 加载相关业务技能；
    如果未加载技能，本工具会返回错误信息字符串而不是示例列表。
    """

    @langchain_tool
    def search_saved_correct_tool_uses(question: str, required_skill: str, runtime: ToolRuntime) -> Union[str, List[dict]]:
        """
        根据当前用户问题检索历史 SQL 示例。

        使用向量检索（doc_type='sql_example'）从业务知识库中召回
        与当前问题语义接近、且已验证成功的 SQL 示例。

        IMPORTANT: 必须通过 required_skill 参数声明本次检索依赖的技能名称（与 sql_db_query 保持一致）。
        该技能必须已通过 load_skill() 预先加载，否则返回错误提示。

        Args:
            question: 当前用户问题的自然语言描述。
            required_skill: 本次检索依赖的技能/业务域名称，必须与 sql_db_query 的 required_skill 保持一致。
        """
        # 0. 精确技能加载校验（与 sql_db_query 保持一致）
        skills_loaded = runtime.state.get("skills_loaded", [])
        if required_skill not in skills_loaded:
            return (
                f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再检索 SQL 示例。\n"
                f"当前已加载的技能: {skills_loaded or '无'}。\n"
                "可用技能请查看系统提示中的 Available Skills 部分。"
            )

        if not question or not question.strip():
            logger.warning("search_saved_correct_tool_uses: 收到空问题，直接返回空列表")
            return []

        try:
            emit_stream_status(
                "正在检索历史 SQL 示例",
                stage="retrieving",
                source="search_saved_correct_tool_uses",
            )
            results = retriever.retrieve(
                query=question,
                k=top_k,
                doc_type="sql_example",
                domain=None,
            )
        except Exception as exc:
            logger.error(
                "search_saved_correct_tool_uses: 检索 SQL 示例时出错，将返回空结果: %s",
                exc,
            )
            return []

        examples: List[dict] = []
        for scored in results:
            doc = scored.document
            metadata = doc.metadata or {}

            # 优先从 metadata["sql"] 读取 SQL；兼容旧结构中的 tool_args.sql
            sql_text = metadata.get("sql", "")
            if not sql_text:
                tool_args = metadata.get("tool_args") or {}
                if isinstance(tool_args, dict):
                    sql_text = tool_args.get("sql", "") or tool_args.get("query", "")

            examples.append(
                {
                    "question": doc.page_content or metadata.get("question", ""),
                    "sql": sql_text,
                    "description": metadata.get("description", ""),
                    "domain": metadata.get("domain", ""),
                    "score": scored.score,
                }
            )

        logger.info(
            "search_saved_correct_tool_uses: 已检索到 %d 条 SQL 示例（doc_type=sql_example）",
            len(examples),
        )
        return examples

    return search_saved_correct_tool_uses
