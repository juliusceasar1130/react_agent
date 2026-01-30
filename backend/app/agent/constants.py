# backend/app/agent/constants.py
"""
Agent 常量定义

集中管理工具名称、配置键等 Magic Strings，提高代码可维护性。
"""


class ToolNames:
    """SQL 工具包中的工具名称常量"""

    QUERY = "sql_db_query"
    CHECKER = "sql_db_query_checker"
    LIST_TABLES = "sql_db_list_tables"
    SCHEMA = "sql_db_schema"


# 需要从工具列表中排除的工具（已被包装或由 skills 替代）
EXCLUDED_TOOLS = frozenset(
    {
        ToolNames.CHECKER,  # 已合并到 sql_db_query
        ToolNames.LIST_TABLES,  # 强制使用 skills 中的表信息
        ToolNames.SCHEMA,  # 强制使用 skills 中的表结构
    }
)

# SQL 语法检查的错误关键词
SQL_ERROR_KEYWORDS = frozenset({"error", "invalid", "syntax", "incorrect"})

# 日期格式模式
DATE_PATTERN = r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"
DATETIME_PATTERN = (
    r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\b"
)
