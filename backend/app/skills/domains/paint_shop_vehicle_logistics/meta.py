"""
涂装车间车辆追踪领域元数据。

修改时间: 2026-07-05 Asia/Shanghai
主要修改内容:
- 拆分领域元数据，供技能注册中心装配
- 新增 table_primary_keys 声明各表主键，供 SkeletonService 骨架标注
- 新增 relationships 声明跨表关联关系与基数，供辅助骨架渲染聚焦关系图
"""

DOMAIN_META = {
    "name": "paint_shop_vehicle_logistics",
    "title": "物流追踪",
    "description": "涂装车间车身物流与追踪领域，负责查询车辆的实时位置分布、车间全局产能分布、全生命周期历史轨迹、异常车监控和滞留检测。\n\n【触发关键词】当前位置、产量、吞吐量、实时分布、历史轨迹、异常车、滞留、车身追踪、物流\n【强制调用规则】用户问题包含以上任一关键词时，Agent 必须先调用 load_skill(\"paint_shop_vehicle_logistics\") 加载领域知识，再组织 SQL。",
    "tags": ["paint_shop", "vehicle_tracking", "logistics", "throughput", "scenario_enabled"],
    "associated_tables": [
        "fct.fct_vehicle_position_current",
        "dim.carbody_registry",
        "dim.dim_process_area"
    ],
    # ── 各表主键声明（逻辑主键，非物理约束） ──
    "table_primary_keys": {
        "fct.fct_vehicle_position_current": "vehicle_id",
        "dim.carbody_registry": "vehicle_id",
        "dim.dim_process_area": "process_area",
    },
    # ── 跨表关联关系声明（逻辑关系，对标 dbt schema.yml relationships test） ──
    # 当本技能被作为辅助技能加载时，主技能可通过以下路径关联
    "relationships": [
        {
            "from_table": "fct.fct_vehicle_position_current",
            "from_key": "vehicle_id",
            "to_table": "mart.mart_vehicle_quality_360",
            "to_key": "vehicle_id",
            "cardinality": "1:N",
            "join_safety": "unsafe",
            "note": "位置表一车一行，质量360一车多行(多检测/多缺陷)；位置→质量 JOIN 会 fan out",
            "pre_aggregate_hint": (
                "SELECT vehicle_id, SUM(total_defect_count) AS total_defects, "
                "COUNT(*) AS detection_count "
                "FROM mart.mart_vehicle_quality_360 "
                "GROUP BY vehicle_id"
            ),
        },
        {
            "from_table": "fct.fct_vehicle_position_current",
            "from_key": "vehicle_id",
            "to_table": "fct.fct_vehicle_defect_detection",
            "to_key": "vehicle_id",
            "cardinality": "1:N",
            "join_safety": "unsafe",
            "note": "位置表一车一行，缺陷检测事实表一车多行；JOIN 前必须先对缺陷表预聚合",
            "pre_aggregate_hint": (
                "SELECT vehicle_id, COUNT(*) AS detection_count, "
                "AVG(total_defect_count) AS avg_defects "
                "FROM fct.fct_vehicle_defect_detection "
                "GROUP BY vehicle_id"
            ),
        },
        {
            "from_table": "dim.carbody_registry",
            "from_key": "vehicle_id",
            "to_table": "mart.mart_vehicle_quality_360",
            "to_key": "vehicle_id",
            "cardinality": "1:N",
            "join_safety": "unsafe",
            "note": "注册表一车一行(唯一)，质量360一车多行；JOIN 前必须预聚合质量表",
            "pre_aggregate_hint": (
                "SELECT vehicle_id, COUNT(*) AS detection_count "
                "FROM mart.mart_vehicle_quality_360 "
                "GROUP BY vehicle_id"
            ),
        },
        {
            "from_table": "fct.fct_vehicle_position_current",
            "from_key": "process_area",
            "to_table": "dim.dim_process_area",
            "to_key": "process_area",
            "cardinality": "N:1",
            "join_safety": "safe",
            "note": "位置表多行属同一区域(N侧)，dim_process_area 维度表唯一(1侧)；位置→维度方向 JOIN 安全，每行最多匹配1个区域",
        },
    ],
}
