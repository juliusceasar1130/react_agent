# backend/tests/agent/utils/test_semantic_summary.py
from unittest.mock import MagicMock

from backend.app.agent.utils.db_utils import _build_semantic_summary


def test_build_semantic_summary_with_column_comments():
    """字段注释来自 inspector 时，摘要含 字段名(注释) 且不含类型噪声。"""
    mock_conn = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": "涂装车间位置概览"}
    mock_inspector.get_columns.return_value = [
        {"name": "entity_type", "comment": "实体类型"},
        {"name": "entity_id", "comment": "实体ID"},
    ]

    result = _build_semantic_summary(
        mock_conn, mock_inspector, "mart_position_current_overview", "postgresql"
    )

    assert "表: mart_position_current_overview" in result
    assert "说明: 涂装车间位置概览" in result
    assert "entity_type(实体类型)" in result
    assert "entity_id(实体ID)" in result
    # 不含类型/约束噪声
    assert "VARCHAR" not in result
    assert "NOT NULL" not in result
    assert "BIGINT" not in result


def test_build_semantic_summary_no_table_comment():
    """无表注释时省略说明行，字段仍正常输出。"""
    mock_conn = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ""}
    mock_inspector.get_columns.return_value = [{"name": "area_name", "comment": "区域名"}]

    result = _build_semantic_summary(mock_conn, mock_inspector, "process_areas", "postgresql")

    assert "表: process_areas" in result
    assert "说明:" not in result
    assert "area_name(区域名)" in result


def test_build_semantic_summary_fallback_column_comment():
    """inspector 未返回列注释时，走 PostgreSQL fallback 查询。"""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = "回退注释"
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ""}
    mock_inspector.get_columns.return_value = [{"name": "col1", "comment": None}]

    result = _build_semantic_summary(mock_conn, mock_inspector, "t1", "postgresql")

    assert "col1(回退注释)" in result


def test_build_semantic_summary_column_without_comment():
    """列无任何注释时，仅输出字段名（不带括号）。"""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = None
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ""}
    mock_inspector.get_columns.return_value = [{"name": "col1", "comment": None}]

    result = _build_semantic_summary(mock_conn, mock_inspector, "t1", "postgresql")

    assert "字段: col1" in result