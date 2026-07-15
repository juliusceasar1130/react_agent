# backend/tests/agent/vector/test_skills_meta_whitelists.py
from backend.app.skills.discovery import discover_domains

def test_logistics_meta_whitelists():
    domains = discover_domains()
    assert "paint_shop_vehicle_logistics" in domains
    logistics = domains["paint_shop_vehicle_logistics"].meta
    
    # 验证物流关联表
    assert "dim.dim_process_area" in logistics["associated_tables"]
    
    # 验证列检索白名单
    assert "columns_lexicon_whitelist" in logistics
    assert logistics["columns_lexicon_whitelist"] == {
        "dim.dim_process_area": {
            "cols": ["process_area_name", "description"],
            "limit": 1000
        }
    }
    
    # 验证行检索白名单与 pk
    assert "rows_lexicon_whitelist" in logistics
    assert logistics["rows_lexicon_whitelist"] == {
        "dim.dim_process_area": {
            "pk": "process_area_name",
            "semantic_cols": ["description"],
            "limit": 1000
        }
    }

def test_defect_meta_whitelists():
    domains = discover_domains()
    assert "paint_shop_defect_analysis" in domains
    defect = domains["paint_shop_defect_analysis"].meta
    
    # 验证缺陷分析白名单骨架已存在
    assert "columns_lexicon_whitelist" in defect
    assert "rows_lexicon_whitelist" in defect

def test_custom_state_lexicon_context():
    from backend.app.agent.state import CustomState
    state = CustomState(messages=[], lexicon_context={"tables": ["test_table"]})
    assert state["lexicon_context"] == {"tables": ["test_table"]}
