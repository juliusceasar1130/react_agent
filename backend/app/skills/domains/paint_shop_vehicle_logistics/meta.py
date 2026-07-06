"""
涂装车间车辆追踪领域元数据。

修改时间: 2026-07-05 Asia/Shanghai
主要修改内容:
- 拆分领域元数据，供技能注册中心装配
- table_primary_keys 和 relationships 已移除，PK 信息由数据库自动反射注入 DDL
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
}
