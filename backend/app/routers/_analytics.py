import logging
from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine, text

from backend.app.agent.utils.sql_database import build_postgres_search_path_engine_args
from backend.app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_analytics_engine = None


def _get_analytics_engine():
    """懒加载 analytics 数据库 engine，后续请求复用连接池。"""
    global _analytics_engine
    if _analytics_engine is None:
        url = (settings.analytics_database_url or "").strip()
        if not url:
            return None
        engine_args = build_postgres_search_path_engine_args(
            settings.analytics_db_search_path
        )
        _analytics_engine = create_engine(url, pool_pre_ping=True, **engine_args)
    return _analytics_engine


def init_analytics_engine():
    """应用启动时预热 analytics 连接池，避免首次用户请求等待建连。"""
    engine = _get_analytics_engine()
    if engine is None:
        logger.info("ANALYTICS_DATABASE_URL 未配置，跳过 analytics 连接池预热")
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("analytics 数据库连接池预热完成")
    except Exception as exc:
        logger.warning("analytics 数据库连接池预热失败: %s", exc)


@router.get("/dimensions/{table_name}")
def get_dimension_table(table_name: str):
    """获取指定维度表全部数据，用于前端数据字典展示。

    修改时间: 2026-05-20
    修改内容:
    - 白名单从 .env DIMENSION_TABLES 配置读取（settings.dimension_tables）
    - 移除本地 Mock 降级，数据库未配置或连接失败直接返回错误便于排查
    - 懒加载 engine 复用连接池，避免每次请求新建 TCP 连接
    """
    whitelist = settings.dimension_tables
    if not whitelist:
        raise HTTPException(
            status_code=503,
            detail="Dimension tables whitelist is not configured (DIMENSION_TABLES)",
        )

    if table_name not in whitelist:
        raise HTTPException(
            status_code=400,
            detail=f"Table '{table_name}' is not in the dimension whitelist",
        )

    engine = _get_analytics_engine()
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Analytics database is not configured (ANALYTICS_DATABASE_URL)",
        )

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f'SELECT * FROM ods."{table_name}"')
            )
            all_columns = list(result.keys())
            _TIME_COL_PATTERNS = frozenset({"_at", "_time", "_date"})
            skip_indices = [
                i for i, col in enumerate(all_columns)
                if any(col.lower().endswith(p) for p in _TIME_COL_PATTERNS)
            ]
            columns = [
                col for i, col in enumerate(all_columns)
                if i not in skip_indices
            ]
            all_rows = [list(row) for row in result.fetchall()]
            rows = [
                [cell for i, cell in enumerate(row) if i not in skip_indices]
                for row in all_rows
            ]
            limit = settings.dimension_result_hard_limit or 300
            if len(rows) > limit:
                rows = rows[:limit]
            return {
                "table_name": table_name,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
    except Exception as exc:
        logger.error("维度表查询失败 table=%s: %s", table_name, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query dimension table '{table_name}': {exc}",
        )
