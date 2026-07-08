import pytest
import sqlglot
from langchain_core.tools import ToolException
from backend.app.agent.tools.sql_tools import create_wrapped_query_tool
from backend.app.agent.utils.sql_linter import (
    SQLLinter, LintViolation, LintContext, BaseLintRule,
    DMLSecurityRule, MultiStatementRule, DatabasePrefixRule,
    StarSelectRule, AliasPrefixRule, SubqueryDepthRule, CteCountRule,
    _build_lint_context, JoinUniquenessRule, CountDistinctRule,
    ScalarSubqueryRule, NotInSubqueryRule
)

class DummyRule(BaseLintRule):
    rule_id = "DUMMY-001"
    severity = "ERROR"
    
    def check(self, parsed, context):
        return [LintViolation(
            rule_id=self.rule_id,
            severity=self.severity,
            message="Dummy error",
            detail="SELECT *",
            fix_suggestion="Select columns"
        )]

def test_linter_skeleton():
    linter = SQLLinter()
    linter.register(DummyRule())
    
    parsed = sqlglot.parse_one("SELECT * FROM t")
    context = LintContext(table_pk_map={}, table_unique_map={}, table_grain_map={}, is_event_table={})
    result = linter.lint(parsed, context)
    
    assert result.passed is False
    assert len(result.errors) == 1
    assert result.errors[0].rule_id == "DUMMY-001"

def test_security_rules():
    linter = SQLLinter()
    linter.register(DMLSecurityRule())
    linter.register(MultiStatementRule())
    linter.register(DatabasePrefixRule())
    
    context = LintContext(table_pk_map={}, table_unique_map={}, table_grain_map={}, is_event_table={})
    
    # SEC-001 DML Block
    parsed = sqlglot.parse_one("DELETE FROM t")
    assert linter.lint(parsed, context).passed is False
    
    # SEC-002 Multi statement
    rule = MultiStatementRule()
    assert len(rule.check_raw_sql("SELECT * FROM t1; SELECT * FROM t2", context)) == 1
    assert len(rule.check_raw_sql("SELECT * FROM t1 -- comment;", context)) == 0

    # SEC-003 Database Prefix / Allowed schemas
    parsed_cross_db = sqlglot.parse_one("SELECT * FROM other_db.schema.table")
    assert linter.lint(parsed_cross_db, context).passed is False
    
    parsed_sys = sqlglot.parse_one("SELECT * FROM pg_catalog.pg_class")
    assert linter.lint(parsed_sys, context).passed is False
    
    parsed_ok = sqlglot.parse_one("SELECT * FROM fct.fct_table")
    assert linter.lint(parsed_ok, context).passed is True

def test_structural_rules():
    linter = SQLLinter()
    linter.register(StarSelectRule())
    linter.register(AliasPrefixRule())
    linter.register(SubqueryDepthRule(max_depth=3))
    linter.register(CteCountRule(max_cte=3))
    
    context = LintContext(table_pk_map={}, table_unique_map={}, table_grain_map={}, is_event_table={})
    
    # STR-001 Select *
    assert linter.lint(sqlglot.parse_one("SELECT * FROM t"), context).passed is False
    assert linter.lint(sqlglot.parse_one("SELECT t.* FROM t"), context).passed is False
    assert linter.lint(sqlglot.parse_one("SELECT COUNT(*) FROM t"), context).passed is True
    assert linter.lint(sqlglot.parse_one("SELECT COUNT(*) OVER () FROM t"), context).passed is True

    # STR-002 Alias Prefix check
    assert linter.lint(sqlglot.parse_one("SELECT col FROM t1 JOIN t2 ON t1.id = t2.id"), context).passed is False
    assert linter.lint(sqlglot.parse_one("SELECT t1.col FROM t1 JOIN t2 ON t1.id = t2.id"), context).passed is True
    assert linter.lint(sqlglot.parse_one("SELECT col FROM t1 UNION ALL SELECT col FROM t2"), context).passed is True
    assert linter.lint(sqlglot.parse_one("SELECT col FROM t1"), context).passed is True

    # STR-003 Subquery Depth
    assert linter.lint(sqlglot.parse_one("SELECT col FROM (SELECT col FROM (SELECT col FROM (SELECT col FROM t)))"), context).passed is True
    assert linter.lint(sqlglot.parse_one("SELECT col FROM (SELECT col FROM (SELECT col FROM (SELECT col FROM (SELECT col FROM t))))"), context).passed is False
    assert linter.lint(sqlglot.parse_one("WITH cte AS (SELECT col FROM t) SELECT col FROM cte"), context).passed is True

    # STR-004 CTE Count
    res = linter.lint(sqlglot.parse_one("WITH c1 AS (SELECT 1), c2 AS (SELECT 2), c3 AS (SELECT 3), c4 AS (SELECT 4) SELECT 1"), context)
    assert len(res.warnings) == 1
    assert res.passed is True

def test_context_parser():
    custom_table_info = {
        "ods.carbody_history": (
            "-- Table: ods.carbody_history\n"
            "-- Grain: 一次 FIS 上线注册事件(ID)\n"
            "CREATE TABLE ods.carbody_history (\n"
            "  id VARCHAR PRIMARY KEY,\n"
            "  vehicle_id VARCHAR UNIQUE\n"
            ");"
        ),
        "mart.mart_vehicle_quality_360": (
            "-- Table: mart.mart_vehicle_quality_360\n"
            "-- Grain: 一车多检(history_id)\n"
            "CREATE TABLE mart.mart_vehicle_quality_360 (\n"
            "  history_id VARCHAR PRIMARY KEY,\n"
            "  vehicle_id VARCHAR\n"
            ");"
        ),
        "mart.composite_table": (
            "CREATE TABLE mart.composite_table (\n"
            "  col1 INT,\n"
            "  col2 INT,\n"
            "  col3 INT,\n"
            "  CONSTRAINT pk_comp PRIMARY KEY (col1, col2),\n"
            "  CONSTRAINT uq_comp UNIQUE (col2, col3)\n"
            ");"
        )
    }
    context = _build_lint_context(custom_table_info)
    assert context.table_pk_map["ods.carbody_history"] == ["id"]
    assert context.table_unique_map["ods.carbody_history"] == [["id"], ["vehicle_id"]]
    assert context.is_event_table["mart.mart_vehicle_quality_360"] is True
    assert context.is_event_table["ods.carbody_history"] is False
    assert context.table_pk_map["mart.composite_table"] == ["col1", "col2"]
    assert ["col1", "col2"] in context.table_unique_map["mart.composite_table"]
    assert ["col2", "col3"] in context.table_unique_map["mart.composite_table"]

def test_semantic_rules():
    custom_table_info = {
        "dim.carbody_registry": (
            "CREATE TABLE dim.carbody_registry (\n"
            "  vehicle_id VARCHAR PRIMARY KEY\n"
            ");"
        ),
        "mart.mart_vehicle_quality_360": (
            "-- Grain: 一车多检\n"
            "CREATE TABLE mart.mart_vehicle_quality_360 (\n"
            "  history_id VARCHAR PRIMARY KEY,\n"
            "  vehicle_id VARCHAR\n"
            ");"
        )
    }
    context = _build_lint_context(custom_table_info)
    linter = SQLLinter()
    linter.register(JoinUniquenessRule())
    linter.register(CountDistinctRule())
    linter.register(ScalarSubqueryRule())
    linter.register(NotInSubqueryRule())

    # SEM-001: unsafe N:N join with aggregate function (ERROR)
    parsed_unsafe_join = sqlglot.parse_one(
        "SELECT SUM(1) FROM dim.carbody_registry r JOIN mart.mart_vehicle_quality_360 q ON r.vehicle_id = q.vehicle_id"
    )
    assert linter.lint(parsed_unsafe_join, context).passed is False

    # SEM-001: safe join (one side is PK)
    parsed_safe_join = sqlglot.parse_one(
        "SELECT SUM(1) FROM mart.mart_vehicle_quality_360 q JOIN dim.carbody_registry r ON q.vehicle_id = r.vehicle_id"
    )
    assert linter.lint(parsed_safe_join, context).passed is True

    # SEM-001: bypass
    parsed_bypass = sqlglot.parse_one(
        "-- linter-bypass: SEM-001\n"
        "SELECT SUM(1) FROM dim.carbody_registry r JOIN mart.mart_vehicle_quality_360 q ON r.vehicle_id = q.vehicle_id"
    )
    assert linter.lint(parsed_bypass, context, raw_sql="-- linter-bypass: SEM-001\nSELECT SUM(1) FROM dim.carbody_registry r JOIN mart.mart_vehicle_quality_360 q ON r.vehicle_id = q.vehicle_id").passed is True

    # SEM-001: safe join using MAX subquery filter
    parsed_max_subquery = sqlglot.parse_one(
        "SELECT COUNT(r.vehicle_id) FROM dim.carbody_registry r JOIN mart.mart_vehicle_quality_360 q "
        "ON r.vehicle_id = q.vehicle_id AND q.detect_time = (SELECT MAX(q2.detect_time) FROM mart.mart_vehicle_quality_360 q2 WHERE q2.vehicle_id = r.vehicle_id)"
    )
    assert linter.lint(parsed_max_subquery, context).passed is True

    # SEM-001: safe join using ROW_NUMBER() = 1 in subquery
    parsed_row_number = sqlglot.parse_one(
        "SELECT COUNT(r.vehicle_id) FROM dim.carbody_registry r JOIN ("
        "  SELECT vehicle_id, ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY detect_time DESC) AS rn "
        "  FROM mart.mart_vehicle_quality_360"
        ") q ON r.vehicle_id = q.vehicle_id AND q.rn = 1"
    )
    assert linter.lint(parsed_row_number, context).passed is True

    # SEM-001: safe join using LIMIT 1 in subquery
    parsed_limit_one = sqlglot.parse_one(
        "SELECT COUNT(r.vehicle_id) FROM dim.carbody_registry r JOIN ("
        "  SELECT vehicle_id FROM mart.mart_vehicle_quality_360 LIMIT 1"
        ") q ON r.vehicle_id = q.vehicle_id"
    )
    assert linter.lint(parsed_limit_one, context).passed is True

    # SEM-002: COUNT(*) on event table without distinct (WARNING)
    parsed_count = sqlglot.parse_one("SELECT COUNT(*) FROM mart.mart_vehicle_quality_360")
    res_count = linter.lint(parsed_count, context)
    assert len(res_count.warnings) == 1
    assert res_count.passed is True  # Warning does not block

    # SEM-002: COUNT(*) on event table outer select without distinct, but subquery HAS group by (should STILL trigger warning on outer count)
    parsed_count_sub_groupby = sqlglot.parse_one(
        "SELECT COUNT(*) FROM mart.mart_vehicle_quality_360 JOIN ("
        "  SELECT vehicle_id FROM dim.carbody_registry GROUP BY vehicle_id"
        ") sub ON sub.vehicle_id = mart_vehicle_quality_360.vehicle_id"
    )
    res_count_sub = linter.lint(parsed_count_sub_groupby, context)
    assert len(res_count_sub.warnings) == 1
    assert res_count_sub.passed is True

    # SEM-004: NOT IN subquery (ERROR)
    parsed_notin = sqlglot.parse_one("SELECT * FROM dim.carbody_registry WHERE vehicle_id NOT IN (SELECT vehicle_id FROM mart.mart_vehicle_quality_360)")
    assert linter.lint(parsed_notin, context).passed is False

    # SEM-004: NOT IN constant list (PASS)
    parsed_notin_literal = sqlglot.parse_one("SELECT * FROM dim.carbody_registry WHERE vehicle_id NOT IN ('1', '2')")
    assert linter.lint(parsed_notin_literal, context).passed is True


class DummyTool:
    name = "sql_db_query"
    description = "Dummy SQL query tool"
    def invoke(self, *args, **kwargs):
        return "[]"

def test_tool_linter_integration(monkeypatch):
    from backend.app.config import settings
    monkeypatch.setattr(settings, "sql_linter_enabled", True)

    custom_table_info = {
        "dim.carbody_registry": "CREATE TABLE dim.carbody_registry (vehicle_id VARCHAR PRIMARY KEY);"
    }
    wrapped = create_wrapped_query_tool(DummyTool(), custom_table_info=custom_table_info)
    monkeypatch.setattr(wrapped, "args_schema", None)
    
    class DummyRuntime:
        state = {"skills_loaded": ["test_skill"]}
        
        def emit_stream_status(self, *args, **kwargs):
            pass
            
        def run_db_query(self, *args, **kwargs):
            return "[]"
    
    # SELECT * is blocked, and since handle_tool_error=True, it returns the error message string
    res = wrapped.invoke({
        "query": "SELECT * FROM dim.carbody_registry",
        "required_skill": "test_skill",
        "runtime": DummyRuntime()
    })
    assert "STR-001" in res


def test_disabled_rules():
    linter = SQLLinter(disabled_rules={"STR-001"})
    linter.register(StarSelectRule())
    
    context = LintContext(table_pk_map={}, table_unique_map={}, table_grain_map={}, is_event_table={})
    parsed = sqlglot.parse_one("SELECT * FROM t")
    assert linter.lint(parsed, context).passed is True


def test_tool_linter_integration_disabled(monkeypatch):
    from backend.app.config import settings
    monkeypatch.setattr(settings, "sql_linter_enabled", True)
    monkeypatch.setattr(settings, "sql_linter_disabled_rules_raw", "STR-001")

    custom_table_info = {
        "dim.carbody_registry": "CREATE TABLE dim.carbody_registry (vehicle_id VARCHAR PRIMARY KEY);"
    }
    wrapped = create_wrapped_query_tool(DummyTool(), custom_table_info=custom_table_info)
    monkeypatch.setattr(wrapped, "args_schema", None)
    
    class DummyRuntime:
        state = {"skills_loaded": ["test_skill"]}
        
        def emit_stream_status(self, *args, **kwargs):
            pass
            
        def run_db_query(self, *args, **kwargs):
            return "[]"
            
        def run_no_throw(self, *args, **kwargs):
            return "[]"

    # STR-001 SELECT * is bypassed now because it is disabled
    res = wrapped.invoke({
        "query": "SELECT * FROM dim.carbody_registry",
        "required_skill": "test_skill",
        "runtime": DummyRuntime()
    })
    assert res.endswith("[]")
