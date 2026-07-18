# backend/app/agent/utils/db_utils.py
"""
数据库元数据工具

提供从数据库提取表结构和注释信息的功能。
支持 PostgreSQL 和 MySQL 数据库。
- 自动反射主键（PRIMARY KEY）标注
- 自动反射唯一约束（UNIQUE CONSTRAINT）和唯一索引（UNIQUE INDEX）标注
- 自动解析表注释中 `Grain:` 粒度标注，渲染为结构化的 `-- Grain:` + `-- ⚠️` 警告
"""

import logging
import re
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
        SELECT col_description(c.oid, a.attnum)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE c.relname = :table_name
          AND a.attname = :col_name
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND n.nspname = ANY (current_schemas(false))
        ORDER BY array_position(current_schemas(false), n.nspname)
        LIMIT 1
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
    col: ReflectedColumn,
    col_comment: str | None,
    pk_cols: list[str] | None = None,
    unique_cols: set[str] | None = None,
) -> str:
    """构建单个列的 DDL 定义，可选标注主键列和唯一约束列"""
    col_name = col["name"]
    col_type = str(col["type"])

    col_line = f"  {col_name} {col_type}"
    if col.get("nullable", True) is False:
        col_line += " NOT NULL"
    if col.get("default") is not None:
        col_line += f" DEFAULT {col['default']}"

    # 🔑 主键标注：在主键列后追加 PRIMARY KEY
    if pk_cols and col_name in pk_cols:
        col_line += " PRIMARY KEY"

    # 🏷️ 唯一约束/唯一索引标注（主键本身已保证唯一，不需要额外标注）
    if unique_cols and col_name in unique_cols and not (pk_cols and col_name in pk_cols):
        col_line += " UNIQUE"

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


def _parse_grain_info(table_comment: str) -> tuple[str | None, list[str]]:
    """
    解析表注释中的粒度信息。

    支持的注释格式：
      Grain:一次检测事件(history_id),vehicle_id可能重复,统计车数需用COUNT(DISTINCT vehicle_id)

    Returns:
        (grain_description, warnings)
        - grain_description: 粒度描述文本，无 Grain: 标记时返回 None
        - warnings: 粒度相关的警告行列表
    """
    grain_match = re.match(r"^Grain:([^，,]+)(?:[，,]\s*(.*))?$", table_comment.strip(), re.DOTALL)
    if not grain_match:
        return None, []

    grain_desc = grain_match.group(1).strip()
    extra = grain_match.group(2)
    warnings = []
    if extra and extra.strip():
        warnings.append(extra.strip())
    return grain_desc, warnings


def _process_single_table(
    conn, inspector, table: str, db_dialect: str
) -> str | None:
    """处理单个表，返回表定义字符串（含主键标注）"""
    try:
        # 获取表注释
        table_comment_obj = inspector.get_table_comment(table)
        table_comment = (
            table_comment_obj.get("text", "") if table_comment_obj else ""
        )

        # 获取列信息
        columns = inspector.get_columns(table)

        # 🔑 获取主键约束列名
        pk_cols: list[str] = []
        try:
            pk_constraint = inspector.get_pk_constraint(table)
            if pk_constraint:
                pk_cols = pk_constraint.get("constrained_columns", [])
                if pk_cols:
                    logger.debug(f"表 {table} 主键列: {pk_cols}")
        except Exception as pk_err:
            logger.debug(f"获取表 {table} 主键约束失败（可能无物理主键）: {pk_err}")

        # 🏷️ 获取唯一约束 / 唯一索引列名（合并去重）
        unique_cols: set[str] = set()
        try:
            # 唯一约束（UNIQUE CONSTRAINT）
            unique_constraints = inspector.get_unique_constraints(table)
            for constraint in unique_constraints:
                for col in constraint.get("column_names", []):
                    if col is not None:
                        unique_cols.add(col)
            # 唯一索引（UNIQUE INDEX），覆盖 get_unique_constraints 抓不到的场景
            # 需排除表达式索引（列名为 None），表达式索引无法标注 UNIQUE
            indexes = inspector.get_indexes(table)
            for idx in indexes:
                if idx.get("unique", False):
                    for col in idx.get("column_names", []):
                        if col is not None:
                            unique_cols.add(col)
            if unique_cols:
                logger.debug(f"表 {table} 唯一列: {sorted(unique_cols)}")
        except Exception as uniq_err:
            logger.debug(f"获取表 {table} 唯一约束/索引失败: {uniq_err}")

        # 构建表定义
        definition_lines = [f"-- Table: {table}"]
        if table_comment:
            grain_desc, grain_warnings = _parse_grain_info(table_comment)
            if grain_desc:
                # 结构化粒度标注
                definition_lines.append(f"-- Grain: {grain_desc}")
                for w in grain_warnings:
                    definition_lines.append(f"-- ⚠️ {w}")
            else:
                # 普通描述注释
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

            col_texts.append(_build_column_definition(col, col_comment, pk_cols, unique_cols))

        definition_lines.append(",\n".join(col_texts))
        definition_lines.append(");")

        # 添加样本数据
        definition_lines.extend(_get_sample_rows(conn, table))

        return "\n".join(definition_lines)

    except Exception as table_err:
        logger.error(f"处理表 {table} 时出错: {table_err}")
        return None


def _list_db_objects(
    inspector, include_views: bool = False, include_materialized_views: bool = False
) -> list[str]:
    """列出数据库对象（表，可选视图/物化视图），去重保序。"""
    tables = inspector.get_table_names()
    if include_views:
        tables += inspector.get_view_names()
    if include_materialized_views:
        get_materialized_view_names = getattr(
            inspector, "get_materialized_view_names", None
        )
        if callable(get_materialized_view_names):
            tables += get_materialized_view_names()
    return list(dict.fromkeys(tables))


def _build_semantic_summary(
    conn, inspector, table: str, db_dialect: str
) -> str | None:
    """构建表的语义摘要（表名+表注释+字段名及注释），用于向量检索嵌入。

    与 _process_single_table 不同，本函数剥离类型/约束/样本等结构噪声，
    只保留对"表选择"有价值的语义信号。
    """
    try:
        table_comment_obj = inspector.get_table_comment(table)
        table_comment = (
            table_comment_obj.get("text", "") if table_comment_obj else ""
        )

        columns = inspector.get_columns(table)

        field_parts: list[str] = []
        for col in columns:
            col_name = col["name"]
            col_comment = col.get("comment")
            if not col_comment:
                if db_dialect == "postgresql":
                    col_comment = _get_column_comment_postgresql(conn, table, col_name)
                elif db_dialect == "mysql":
                    col_comment = _get_column_comment_mysql(conn, table, col_name)
            if col_comment:
                field_parts.append(f"{col_name}({col_comment})")
            else:
                field_parts.append(col_name)

        lines = [f"表: {table}"]
        if table_comment:
            lines.append(f"说明: {table_comment}")
        if field_parts:
            lines.append(f"字段: {', '.join(field_parts)}")
        return "\n".join(lines)

    except Exception as table_err:
        logger.error(f"构建表 {table} 语义摘要失败: {table_err}")
        return None


def fetch_table_semantic_summaries(
    db_uri: str,
    *,
    engine_args: dict | None = None,
    include_views: bool = False,
    include_materialized_views: bool = False,
) -> Dict[str, str]:
    """提取表的语义摘要字典 {表名: 摘要文本}，供 table_schema_store 嵌入使用。"""
    try:
        engine = create_engine(db_uri, **(engine_args or {}))
        inspector = inspect(engine)
        summaries: Dict[str, str] = {}

        db_dialect = engine.dialect.name
        logger.info(f"检测到数据库类型: {db_dialect}")

        tables = _list_db_objects(inspector, include_views, include_materialized_views)
        logger.info(f"找到 {len(tables)} 个数据库对象")

        with engine.connect() as conn:
            for table in tables:
                summary = _build_semantic_summary(conn, inspector, table, db_dialect)
                if summary:
                    summaries[table] = summary
                    logger.debug(f"已生成语义摘要: {table}")

        engine.dispose()
        logger.info(f"成功提取 {len(summaries)} 个表的语义摘要")
        return summaries

    except Exception as e:
        logger.error(f"提取表语义摘要失败: {e}")
        return {}


def fetch_table_definitions_with_comments(
    db_uri: str,
    *,
    engine_args: dict | None = None,
    include_views: bool = False,
    include_materialized_views: bool = False,
) -> Dict[str, str]:
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
        engine = create_engine(db_uri, **(engine_args or {}))
        inspector = inspect(engine)
        table_definitions: Dict[str, str] = {}

        # 检测数据库类型
        db_dialect = engine.dialect.name
        logger.info(f"检测到数据库类型: {db_dialect}")

        # 获取所有表 / 视图 / 物化视图
        tables = _list_db_objects(inspector, include_views, include_materialized_views)
        logger.info(f"找到 {len(tables)} 个数据库对象")

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
