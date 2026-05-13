"""
涂装车间车辆追踪领域元数据。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 拆分领域元数据，供技能注册中心装配
"""

DOMAIN_META = {
    "name": "paint_shop_vehicle_logistics",
    "description": "涂装车间车身物流与追踪领域，负责查询车辆的实时位置分布、车间全局产能分布（各区域多少车）、全生命周期历史轨迹、以及载体运行状态和异常车监控。注意：此领域不处理缺陷质量数据。",
    "tags": ["paint_shop", "vehicle_tracking", "logistics", "throughput", "scenario_enabled"],
}
