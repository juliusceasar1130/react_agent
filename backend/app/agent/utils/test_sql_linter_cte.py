"""
CTE dedup detection tests for JoinUniquenessRule (SEM-001).

Tests that CTEs with dedup patterns (ROW_NUMBER, GROUP BY, DISTINCT, chained)
are recognized as safe JOIN targets, while CTEs without dedup are still flagged.
"""

import pytest
import sqlglot
from backend.app.agent.utils.sql_linter import (
    SQLLinter, JoinUniquenessRule, _build_lint_context,
)


# Shared table setup: dim.carbody_registry (PK=vehicle_id, one side)
#                    mart.mart_vehicle_quality_360 (PK=history_id, many side, vehicle_id not unique)
_TABLE_INFO = {
    "dim.carbody_registry": (
        "CREATE TABLE dim.carbody_registry (\n"
        "  vehicle_id VARCHAR PRIMARY KEY\n"
        ");"
    ),
    "mart.mart_vehicle_quality_360": (
        "-- Grain: 一车多检\n"
        "CREATE TABLE mart.mart_vehicle_quality_360 (\n"
        "  history_id VARCHAR PRIMARY KEY,\n"
        "  vehicle_id VARCHAR,\n"
        "  detect_time VARCHAR\n"
        ");"
    ),
}

_CONTEXT = _build_lint_context(_TABLE_INFO)


def _lint(sql: str) -> list:
    """Run JoinUniquenessRule on the given SQL and return violations."""
    linter = SQLLinter()
    linter.register(JoinUniquenessRule())
    parsed = sqlglot.parse_one(sql, read="postgres")
    result = linter.lint(parsed, _CONTEXT, raw_sql=sql)
    return result.errors


def test_cte_rownumber_join_filter_safe():
    """CTE with ROW_NUMBER + filter rn=1 in JOIN ON → no SEM-001."""
    sql = """
    WITH deduped AS (
      SELECT vehicle_id, ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY detect_time DESC) AS rn
      FROM mart.mart_vehicle_quality_360
    )
    SELECT COUNT(r.vehicle_id)
    FROM dim.carbody_registry r
    JOIN deduped d ON r.vehicle_id = d.vehicle_id AND d.rn = 1
    """
    violations = _lint(sql)
    assert len(violations) == 0, f"Expected no violations, got: {violations}"


def test_cte_groupby_safe():
    """CTE with GROUP BY → no SEM-001."""
    sql = """
    WITH aggregated AS (
      SELECT vehicle_id, MAX(detect_time) AS max_time
      FROM mart.mart_vehicle_quality_360
      GROUP BY vehicle_id
    )
    SELECT COUNT(r.vehicle_id)
    FROM dim.carbody_registry r
    JOIN aggregated a ON r.vehicle_id = a.vehicle_id
    """
    violations = _lint(sql)
    assert len(violations) == 0, f"Expected no violations, got: {violations}"


def test_cte_distinct_safe():
    """CTE with DISTINCT → no SEM-001."""
    sql = """
    WITH deduped AS (
      SELECT DISTINCT vehicle_id
      FROM mart.mart_vehicle_quality_360
    )
    SELECT COUNT(r.vehicle_id)
    FROM dim.carbody_registry r
    JOIN deduped d ON r.vehicle_id = d.vehicle_id
    """
    violations = _lint(sql)
    assert len(violations) == 0, f"Expected no violations, got: {violations}"


def test_cte_chained_grain_propagation():
    """Chained CTE: step1 has GROUP BY, step2 references step1 → no SEM-001."""
    sql = """
    WITH step1 AS (
      SELECT vehicle_id, MAX(detect_time) AS max_time
      FROM mart.mart_vehicle_quality_360
      GROUP BY vehicle_id
    ),
    step2 AS (
      SELECT vehicle_id FROM step1
    )
    SELECT COUNT(r.vehicle_id)
    FROM dim.carbody_registry r
    JOIN step2 s ON r.vehicle_id = s.vehicle_id
    """
    violations = _lint(sql)
    assert len(violations) == 0, f"Expected no violations, got: {violations}"


def test_cte_without_dedup_flagged():
    """CTE without any dedup pattern → SEM-001 still flagged."""
    sql = """
    WITH raw_data AS (
      SELECT vehicle_id, history_id
      FROM mart.mart_vehicle_quality_360
    )
    SELECT COUNT(r.vehicle_id)
    FROM dim.carbody_registry r
    JOIN raw_data d ON r.vehicle_id = d.vehicle_id
    """
    violations = _lint(sql)
    assert len(violations) >= 1, f"Expected SEM-001 violation, got: {violations}"
    assert violations[0].rule_id == "SEM-001"


def test_cte_union_unknown_not_safe():
    """CTE with UNION → conservatively not safe (UNION doesn't guarantee grain=1)."""
    sql = """
    WITH combined AS (
      SELECT vehicle_id FROM mart.mart_vehicle_quality_360
      UNION
      SELECT vehicle_id FROM dim.carbody_registry
    )
    SELECT COUNT(r.vehicle_id)
    FROM dim.carbody_registry r
    JOIN combined c ON r.vehicle_id = c.vehicle_id
    """
    violations = _lint(sql)
    assert len(violations) >= 1, f"Expected SEM-001 violation for UNION CTE, got: {violations}"
    assert violations[0].rule_id == "SEM-001"
