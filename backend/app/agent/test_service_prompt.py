# backend/app/agent/test_service_prompt.py
from unittest.mock import MagicMock
from backend.app.agent.service import _build_system_prompt

def test_build_system_prompt_pg17_compatibility():
    """Verify that the generated system prompt complies with PG17 and includes optimization rules."""
    mock_db = MagicMock()
    mock_db.dialect = "postgresql"
    
    prompt = _build_system_prompt(mock_db)
    
    # 1. Assert MySQL STR_TO_DATE is removed
    assert "STR_TO_DATE(" not in prompt
    
    # 2. Assert TO_TIMESTAMP and US/non-US timestamp tolerances exist
    assert "TO_TIMESTAMP" in prompt
    assert "DD/MM/YYYY HH24:MI:SS.US" in prompt
    assert "DD/MM/YYYY HH24:MI:SS" in prompt
    
    # 3. Assert required_skill example is dynamic instead of hardcoded 'paint_shop'
    assert "## Available Skills" in prompt
    assert "如 'paint_shop'" not in prompt
    
    # 4. Assert EXISTS recommendation and NULL traps are stated
    assert "WHERE EXISTS" in prompt
    assert "三值逻辑" in prompt
    
    # 5. Assert AskUserQuestion structured format is enforced
    assert "multiSelect" in prompt
    assert "questions" in prompt
    
    # 6. Assert global SELECT * ban and Ambiguous Column warnings are present
    assert "SELECT *" in prompt
    assert "Column Reference is Ambiguous" in prompt
    
    # 7. Assert NOT IN NULL traps are explicitly banned
    assert "NOT IN" in prompt
    assert "NOT EXISTS" in prompt
    
    # 8. Assert index-friendly rules on DATE_EVT columns
    assert "索引" in prompt
    assert "DATE_EVT" in prompt

    # 9. Assert Phase 1 Cascade query rules
    assert "嵌套子查询" in prompt
    assert "表别名前缀" in prompt
