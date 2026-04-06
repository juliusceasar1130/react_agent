"""
每日各区域车身数量统计场景元数据。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 将场景迁移到按场景名聚合的目录结构
- 调整 SQL 资产引用为 `scope + path` 语义
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_tracking",
    "name": "daily_area_body_count",
    "title": "每日各区域车身数量统计",
    "description": "统计指定日期或当前快照下各工艺区域有效车身数量，并输出分区域数量与总计口径说明。",
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
    "required_inputs": ["stat_date"],
    "optional_inputs": ["shift", "snapshot_time", "area_names"],
    "parameters": {},
    "workflow": [
        "先确认是当前快照还是指定日期/班次窗口。",
        "应用有效车辆过滤规则，排除空位和无车记录。",
        "按 process_area 做聚合统计。",
        "输出各区域数量、总计和统计口径说明。",
    ],
    "rules": [
        "只统计有效车辆。",
        "排除空位/无车记录。",
        "聚合必须在数据库中使用 GROUP BY 与 COUNT 完成。",
    ],
    "gotchas": [
        "当前快照和时间窗口口径不能混用。",
        "carrier_id 与空位规则必须保持一致，避免把空位计入数量。",
    ],
    "output_contract": "输出字段至少包含 process_area、vehicle_count；默认附带总计与统计口径说明。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "按工艺区域统计有效车身数量的 SQL 模板。",
        }
    ],
    "script_refs": [],
}
