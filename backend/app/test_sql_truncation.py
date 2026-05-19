import pytest
from backend.app.agent.tools.sql_tools import _extract_table_names, _is_pure_dimension_query
from backend.app.config import settings

def test_extract_table_names():
    # Simple query
    q1 = "SELECT * FROM colors"
    assert _extract_table_names(q1) == {"colors"}

    # Query with schema
    q2 = "SELECT * FROM public.colors"
    assert _extract_table_names(q2) == {"colors"}

    # Query with JOIN
    q3 = "SELECT * FROM process_areas JOIN car_models ON process_areas.id = car_models.area_id"
    assert _extract_table_names(q3) == {"process_areas", "car_models"}

    # Query with Subquery
    q4 = "SELECT * FROM (SELECT id FROM colors) AS c"
    assert _extract_table_names(q4) == {"colors"}

    # Query with CTE
    q5 = """
    WITH cte AS (
        SELECT id FROM process_areas
    )
    SELECT * FROM cte JOIN car_models ON cte.id = car_models.area_id
    """
    # Note: CTE names are not real tables, but sqlglot Table extraction might extract 'cte' or not depending on context.
    # In standard sqlglot AST, CTEs are references, but Table expression is still created for 'cte'.
    # Let's verify what sqlglot returns. We should assert that the physical tables are present.
    extracted = _extract_table_names(q5)
    assert "process_areas" in extracted
    assert "car_models" in extracted


def test_is_pure_dimension_query():
    # Setup test whitelist
    # We temporarily patch dimension_tables if needed, or rely on our config which has 'process_areas,car_models,colors'
    dim_whitelist = settings.dimension_tables
    print(f"Current whitelist: {dim_whitelist}")
    assert "colors" in dim_whitelist
    assert "process_areas" in dim_whitelist
    assert "car_models" in dim_whitelist

    # Case A: Pure dimension tables
    q_pure = "SELECT * FROM colors JOIN car_models ON colors.model_id = car_models.id"
    assert _is_pure_dimension_query(q_pure) is True

    # Case B: Mixed with non-whitelist table (fact table)
    q_mixed = "SELECT * FROM colors JOIN fct_production ON colors.id = fct_production.color_id"
    assert _is_pure_dimension_query(q_mixed) is False

    # Case C: Single non-whitelist table
    q_fact = "SELECT * FROM fct_production"
    assert _is_pure_dimension_query(q_fact) is False

    # Case D: Malformed query
    assert _is_pure_dimension_query("SELECT FROM WHERE") is False
