import pytest
from backend.app.agent.utils.sql_linter import LintResult, LintViolation

def test_lint_result_error_formatting_includes_header():
    violation = LintViolation(
        rule_id="SEM-001",
        severity="ERROR",
        message="JOIN columns are not unique.",
        detail="JOIN ON t0.a = t1.a",
        fix_suggestion="Use GROUP BY"
    )
    result = LintResult(passed=False, errors=[violation], warnings=[])
    formatted = result.format_error_message()
    
    # Assert header exists at the top
    assert formatted.startswith("X-SQL-LINTER-STATUS: FAILED")
    assert "Error: SQL Linter 拦截 — 检测到以下问题：" in formatted
