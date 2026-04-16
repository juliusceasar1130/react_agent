"""
每日各区域车身数量统计场景元数据。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 将场景迁移到按场景名聚合的目录结构
- 调整 SQL 资产引用为 `scope + path` 语义
- 对齐 `analytics_db` 当前快照口径，改为优先查询 `mart_position_current_overview`
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_tracking",
    "name": "daily_area_body_count",
    "title": "每日各区域车身数量统计",
    "description": "基于 `mart_position_current_overview` 统计当前快照下各工艺区域正式产品车数量，作为日常汇总入口使用。",
    "triggers": [
        "今天每个区域有多少车身",
        "统计各区域车身数量",
        "按区域汇总当前车身分布",
    ],
    "intent_keywords": [
        "区域",
        "车身数量",
        "分布",
        "统计",
        "汇总",
    ],
    "required_inputs": [],
    "optional_inputs": ["process_area"],
    "parameters": {},
    "workflow": [
        "确认用户要的是当前日常汇总，而不是历史某天回放。",
        "优先查询 `mart_position_current_overview`。",
        "筛选 `entity_type = 'product_vehicle'`，只统计正式产品车。",
        "如用户指定工艺区域，再增加 process_area 过滤。",
        "按 process_area 做聚合统计。",
        "输出各区域数量、总计和统计口径说明。",
    ],
    "rules": [
        "只统计正式产品车，不统计异常车。",
        "优先使用 `mart_position_current_overview`，不要直接从 `rb_position_data` 开始写查询。",
        "聚合必须在数据库中使用 GROUP BY 与 COUNT 完成。",
    ],
    "gotchas": [
        "当前分析库还没有位置历史快照层，不支持按任意历史日期回放区域车身数量。",
        "如果问题涉及异常车或全部当前占位，应改用 `mart_position_current_overview` 的对应口径，而不是只统计产品车。",
    ],
    "output_contract": "输出字段至少包含 process_area、vehicle_count；默认附带总计与当前快照统计口径说明。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "按工艺区域统计当前快照下正式产品车数量的 SQL 模板。",
        }
    ],
    "script_refs": [],
}
