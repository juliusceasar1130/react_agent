"""
涂装车间质量缺陷分析领域元数据。

修改时间: 2026-07-05 Asia/Shanghai
主要修改内容:
- 新增质量缺陷分析领域元数据，供技能注册中心自动发现
- 新增 table_primary_keys 声明各表主键，供 SkeletonService 骨架标注
- 新增 relationships 声明跨表关联关系与基数，供辅助骨架渲染聚焦关系图
"""

DOMAIN_META = {
    "name": "paint_shop_defect_analysis",
    "title": "质量缺陷分析",
    "description": "涂装车间质量缺陷汇总分析领域，面向车型缺陷趋势、部位分布、tunnel/cycle 对比和黑车顶对比等问题。\n\n【触发关键词】缺陷、缺陷率、缺陷汇总、部位分布、tunnel、cycle、黑车顶、车型趋势、对比\n【强制调用规则】用户问题包含以上任一关键词时，Agent 必须先调用 load_skill(\"paint_shop_defect_analysis\") 加载领域知识，再组织 SQL。",
    "tags": ["paint_shop", "quality", "defect", "scenario_enabled"],
    "associated_tables": [
        "mart.mart_vehicle_quality_360"
    ],
    # ── 各表主键声明（逻辑主键，非物理约束） ──
    "table_primary_keys": {
        # 缺陷事件主键，未检测车辆则为 NULL
        "mart.mart_vehicle_quality_360": "history_id",
        # 缺陷检测事实层主键
        "fct.fct_vehicle_defect_detection": "history_id",
        # 以车身为中心的质量富集全量表主键
        "fct.fct_vehicle_defect_enriched": "vehicle_id",
    },
    # ── 跨表关联关系声明（逻辑关系，对标 dbt schema.yml relationships test） ──
    # 当本技能被作为辅助技能加载时，主技能可通过以下路径关联
    "relationships": [
        {
            "from_table": "mart.mart_vehicle_quality_360",
            "from_key": "vehicle_id",
            "to_table": "fct.fct_vehicle_position_current",
            "to_key": "vehicle_id",
            "cardinality": "N:1",
            "join_safety": "safe",
            "note": "质量360粒度为一次检测事件(N侧)，位置表一车一行(1侧)；质量→位置方向 JOIN 安全，每行最多匹配1个位置",
        },
        {
            "from_table": "mart.mart_vehicle_quality_360",
            "from_key": "vehicle_id",
            "to_table": "dim.carbody_registry",
            "to_key": "vehicle_id",
            "cardinality": "N:1",
            "join_safety": "safe",
            "note": "质量360粒度为一次检测事件(N侧)，carbody_registry 一车一行(1侧)；N→1 方向 JOIN 安全，每行最多匹配1条注册信息",
        },
        {
            "from_table": "mart.mart_vehicle_quality_360",
            "from_key": "vehicle_id",
            "to_table": "dim.dim_vehicle_profile",
            "to_key": "vehicle_id",
            "cardinality": "N:1",
            "join_safety": "safe",
            "note": "质量360粒度为一次检测事件(N侧)，dim_vehicle_profile 一车一行(1侧)；N→1 方向 JOIN 安全，每行最多匹配1条画像记录",
        },
    ],
}
