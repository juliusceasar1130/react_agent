# backend/tests/agent/vector/test_skills_meta_whitelists.py
from backend.app.skills.discovery import discover_domains

def test_logistics_meta_whitelists():
    domains = discover_domains()
    assert "paint_shop_vehicle_logistics" in domains
    logistics = domains["paint_shop_vehicle_logistics"].meta

    # 验证物流关联表
    assert "dim.dim_process_area" in logistics["associated_tables"]

    # 验证列检索白名单（与当前 skill 元数据一致：ods.* 4 张表）
    assert "columns_lexicon_whitelist" in logistics
    assert logistics["columns_lexicon_whitelist"] == {
        "ods.process_areas": {
            "cols": ["area_name"],
            "limit": 1000
        },
        "ods.vehicle_body_types": {
            "cols": ["body_type", "type_name"],
            "limit": 1000
        },
        "ods.vehicle_color_codes": {
            "cols": ["color_code", "color_name"],
            "limit": 1000
        },
        "ods.vehicle_platforms": {
            "cols": ["platform_code", "platform_name"],
            "limit": 1000
        },
    }

    # 验证行检索白名单与 pk
    assert "rows_lexicon_whitelist" in logistics
    assert logistics["rows_lexicon_whitelist"] == {
        "ods.process_areas": {
            "pk": "id",
            "semantic_cols": ["area_name"],
            "limit": 1000
        },
        "ods.vehicle_body_types": {
            "pk": "body_type",
            "semantic_cols": ["type_name"],
            "limit": 1000
        },
        "ods.vehicle_color_codes": {
            "pk": "color_code",
            "semantic_cols": ["color_name"],
            "limit": 1000
        },
        "ods.vehicle_platforms": {
            "pk": "platform_code",
            "semantic_cols": ["platform_name"],
            "limit": 1000
        },
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
