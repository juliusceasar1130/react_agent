"""
涂装车间车辆追踪领域元数据。

修改时间: 2026-07-29 Asia/Shanghai
主要修改内容:
- 拆分领域元数据，供技能注册中心装配
- 扩充项目车 (project_vehicle)
"""

DOMAIN_META = {
    "name": "paint_shop_vehicle_logistics",
    "title": "物流追踪",
    "description": "涂装车间车身物流与追踪领域，负责查询车辆的实时位置分布、车间全局产能分布、全生命周期历史轨迹、异常车监控和滞留检测。\n\n【触发关键词】当前位置、产量、吞吐量、实时分布、历史轨迹、异常车、滞留、车身追踪、物流、项目车、试验车、PIN、FIS订单、量产车、正常车\n【强制调用规则】用户问题包含以上任一关键词时，Agent 必须先调用 load_skill(\"paint_shop_vehicle_logistics\") 加载领域知识，再组织 SQL。",
    "tags": ["paint_shop", "vehicle_tracking", "logistics", "throughput", "scenario_enabled"],
    "associated_tables": [
        "fct.fct_vehicle_position_current",
        "dim.carbody_registry",
        "dim.dim_process_area",
        "ods.ods_fis_project_vehicle_orders"
    ],
    # 💡 明确指定哪些表允许被抽取列值和行级实体嵌入，用作检索候选
    "lexicon_enabled_tables": [ 
        "mart.mart_position_current_overview",     
        "ods.process_areas",
        "ods.vehicle_body_types",
        "ods.vehicle_color_codes",
        "ods.vehicle_platforms",
        "dim.carbody_registry"
    ],
    "rows_lexicon_whitelist": {       
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
        }
    },
    "columns_lexicon_whitelist": {
        "ods.process_areas": {
            "cols": ["area_name"],
            "limit": 1000
        },
        "ods.vehicle_body_types": {
            "cols": ["body_type","type_name"],
            "limit": 1000
        },
        "ods.vehicle_color_codes": {
            "cols": ["color_code","color_name"],
            "limit": 1000
        },
        "ods.vehicle_platforms": {
            "cols": ["platform_code","platform_name"],
            "limit": 1000
        }
    }
}
