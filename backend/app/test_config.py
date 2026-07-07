import os
from backend.app.config import Settings

def test_linter_settings():
    os.environ["SQL_LINTER_ENABLED"] = "False"
    os.environ["SQL_LINTER_MAX_SUBQUERY_DEPTH"] = "5"
    os.environ["SQL_LINTER_MAX_CTE_COUNT"] = "6"
    os.environ["SQL_LINTER_ALLOWED_SCHEMAS"] = "public,ods"
    os.environ["SQL_LINTER_RULES_SEVERITY_OVERRIDE"] = "SEM-001:WARNING,SEM-002:INFO"
    
    try:
        settings = Settings()
        assert settings.sql_linter_enabled is False
        assert settings.sql_linter_max_subquery_depth == 5
        assert settings.sql_linter_max_cte_count == 6
        assert settings.sql_linter_allowed_schemas == ["public", "ods"]
        assert settings.sql_linter_rules_severity_override == {
            "SEM-001": "WARNING",
            "SEM-002": "INFO"
        }
    finally:
        for k in [
            "SQL_LINTER_ENABLED",
            "SQL_LINTER_MAX_SUBQUERY_DEPTH",
            "SQL_LINTER_MAX_CTE_COUNT",
            "SQL_LINTER_ALLOWED_SCHEMAS",
            "SQL_LINTER_RULES_SEVERITY_OVERRIDE"
        ]:
            os.environ.pop(k, None)
