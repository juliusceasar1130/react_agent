# backend/app/agent/utils/db_utils.py
"""
数据库元数据工具

提供从数据库提取表结构和注释信息的功能。
支持 PostgreSQL 和 MySQL 数据库。
"""

import logging
from typing import Dict

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import ReflectedColumn

logger = logging.getLogger(__name__)


def _get_column_comment_postgresql(
    conn, table: str, col_name: str
) -> str | None:
    """从 PostgreSQL 获取列注释"""
    comment_query = text(
        """
        SELECT col_description(
            (SELECT oid FROM pg_class WHERE relname = :table_name),
            (SELECT ordinal_position FROM information_schema.columns 
             WHERE table_name = :table_name AND column_name = :col_name)
        )
        """
    )
    result = conn.execute(
        comment_query, {"table_name": table, "col_name": col_name}
    ).scalar()
    return result if result else None


def _get_column_comment_mysql(
    conn, table: str, col_name: str
) -> str | None:
    """从 MySQL 获取列注释"""
    comment_query = text(
        """
        SELECT COLUMN_COMMENT 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = :table_name 
        AND COLUMN_NAME = :col_name
        """
    )
    result = conn.execute(
        comment_query, {"table_name": table, "col_name": col_name}
    ).scalar()
    return result if result else None


def _build_column_definition(
    col: ReflectedColumn, col_comment: str | None
) -> str:
    """构建单个列的 DDL 定义"""
    col_name = col["name"]
    col_type = str(col["type"])

    col_line = f"  {col_name} {col_type}"
    if col.get("nullable", True) is False:
        col_line += " NOT NULL"
    if col.get("default") is not None:
        col_line += f" DEFAULT {col['default']}"
    if col_comment:
        col_line += f"  -- {col_comment}"

    return col_line


def _get_sample_rows(conn, table: str, limit: int = 3) -> list[str]:
    """获取表的样本数据行"""
    sample_lines = []
    try:
        sample_query = text(f"SELECT * FROM {table} LIMIT {limit}")
        samples = conn.execute(sample_query).fetchall()
        if samples:
            sample_lines.append("\n-- Sample rows:")
            for i, row in enumerate(samples, 1):
                row_dict = dict(row._mapping)
                sample_lines.append(f"-- {i}. {row_dict}")
    except Exception as sample_err:
        logger.debug(f"无法获取表 {table} 的样本数据: {sample_err}")
    return sample_lines


def _process_single_table(
    conn, inspector, table: str, db_dialect: str
) -> str | None:
    """处理单个表，返回表定义字符串"""
    try:
        # 获取表注释
        table_comment_obj = inspector.get_table_comment(table)
        table_comment = (
            table_comment_obj.get("text", "") if table_comment_obj else ""
        )

        # 获取列信息
        columns = inspector.get_columns(table)

        # 构建表定义
        definition_lines = [f"-- Table: {table}"]
        if table_comment:
            definition_lines.append(f"-- Description: {table_comment}")

        definition_lines.append(f"CREATE TABLE {table} (")

        col_texts = []
        for col in columns:
            col_name = col["name"]
            col_comment = col.get("comment", None)

            # 如果 SQLAlchemy 没有返回注释，尝试直接查询
            if not col_comment:
                if db_dialect == "postgresql":
                    col_comment = _get_column_comment_postgresql(
                        conn, table, col_name
                    )
                elif db_dialect == "mysql":
                    col_comment = _get_column_comment_mysql(
                        conn, table, col_name
                    )

            col_texts.append(_build_column_definition(col, col_comment))

        definition_lines.append(",\n".join(col_texts))
        definition_lines.append(");")

        # 添加样本数据
        definition_lines.extend(_get_sample_rows(conn, table))

        return "\n".join(definition_lines)

    except Exception as table_err:
        logger.error(f"处理表 {table} 时出错: {table_err}")
        return None


def fetch_table_definitions_with_comments(db_uri: str) -> Dict[str, str]:
    """
    从数据库元数据中提取表结构和注释信息。

    支持 PostgreSQL 和 MySQL 数据库。会尝试多种方式获取列注释：
    1. SQLAlchemy 反射
    2. 数据库特定的系统表查询

    Args:
        db_uri: 数据库连接字符串

    Returns:
        Dict[表名, 带注释的表结构定义(DDL)]
    """
    try:
        engine = create_engine(db_uri)
        inspector = inspect(engine)
        table_definitions: Dict[str, str] = {}

        # 检测数据库类型
        db_dialect = engine.dialect.name
        logger.info(f"检测到数据库类型: {db_dialect}")

        # 获取所有表
        tables = inspector.get_table_names()
        logger.info(f"找到 {len(tables)} 个表")

        with engine.connect() as conn:
            for table in tables:
                definition = _process_single_table(
                    conn, inspector, table, db_dialect
                )
                if definition:
                    table_definitions[table] = definition
                    logger.debug(f"已处理表: {table}")

        engine.dispose()
        logger.info(f"成功提取 {len(table_definitions)} 个表的定义和注释")
        return table_definitions

    except Exception as e:
        logger.error(f"提取表定义失败: {e}")
        return {}
