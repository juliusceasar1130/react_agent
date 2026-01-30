# backend/app/agent/tools/sql_tools.py
"""
SQL 查询工具工厂

提供包装后的 SQL 查询工具，集成：
1. 技能加载检查
2. 自动 SQL 语法检查
3. 日期格式标准化
"""

import logging
from typing import Any, Optional

from langchain.tools import ToolRuntime, tool as langchain_tool

from backend.app.agent.constants import SQL_ERROR_KEYWORDS
from backend.app.agent.utils.date_utils import normalize_dates_in_text

logger = logging.getLogger(__name__)


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
    def sql_db_query(query: str, runtime: ToolRuntime) -> str:
        """
        Execute a SQL query against the database and return results.

        This tool requires a skill to be loaded first using load_skill().
        The query will be automatically validated before execution.
        Results will have dates normalized to ISO 8601 format (YYYY-MM-DD).

        Input should be a valid SQL query.
        """
        # 1. 技能加载检查
        skills_loaded = runtime.state.get("skills_loaded", [])
        if not skills_loaded:
            return (
                "Error: 请先使用 load_skill() 加载相关业务技能后再执行查询。\n"
                "可用技能请查看系统提示中的 Available Skills 部分。"
            )

        # 2. 自动执行 SQL 语法检查（如果 checker 工具可用）
        if original_checker_tool is not None:
            check_result = original_checker_tool.invoke({"query": query})
            check_result_str = str(check_result).lower()

            # 检查是否有错误指示
            if any(err in check_result_str for err in SQL_ERROR_KEYWORDS):
                logger.warning(f"SQL 语法检查失败: {check_result}")
                return f"SQL 语法检查失败:\n{check_result}\n请修正查询后重试。"

            logger.debug("SQL 语法检查通过")

        # 3. 执行查询
        raw_result = original_query_tool.invoke({"query": query})

        # 4. 对查询结果的日期进行格式转换
        cleaned_result = normalize_dates_in_text(str(raw_result))
        logger.debug("SQL 查询结果已清洗日期格式")

        return cleaned_result

    return sql_db_query
