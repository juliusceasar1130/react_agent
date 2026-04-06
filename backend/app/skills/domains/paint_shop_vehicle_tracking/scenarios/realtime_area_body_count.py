"""
实时各区域车身数量统计场景元数据。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增 `realtime_area_body_count` 场景
- 引入实时区域车身数量统计的 workflow、rules、gotchas 与外部 SQL 模板引用
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_tracking",
    "name": "realtime_area_body_count",
    "title": "实时各区域车身数量统计",
    "description": "基于当前 rb_position_data 实时快照，统计各工艺区域的有效车身数量，并输出实时分区域数量口径说明。",
    "triggers": [
        "实时统计各个区域的车身数量",
        "现在每个区域有多少车身",
        "查看各区域实时车身分布",
    ],
    "intent_keywords": [
        "实时",
        "区域",
        "车身数量",
        "分布",
        "当前",
    ],
    "required_inputs": [],
    "optional_inputs": ["area_names"],
    "workflow": [
        "确认用户要的是当前实时快照，而不是某天或某班次的历史窗口。",
        "应用有效车辆过滤规则，排除空位、无车记录和无效载体。",
        "按 process_area 聚合统计实时车身数量。",
        "输出各区域实时数量，并附带统计口径说明。",
    ],
    "rules": [
        "只统计 vehicle_id 前缀为 782026 的有效车辆。",
        "排除 body_type = '-----' 与 carrier_id = '0' 的记录。",
        "聚合必须在数据库中使用 GROUP BY 与 COUNT 完成。",
    ],
    "gotchas": [
        "这是实时快照统计，不应混入日期、班次或时间窗口条件。",
        "carrier_id = '0' 和 body_type = '-----' 代表空位/无车，不能计入区域数量。",
    ],
    "output_contract": "输出字段至少包含 process_area、vehicle_count；默认按 vehicle_count 降序输出，并说明实时统计口径。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "realtime_area_body_count",
            "path": "paint_shop_vehicle_tracking/sql/realtime_area_body_count.sql",
            "description": "按工艺区域统计实时有效车身数量的 SQL 模板。",
        }
    ],
    "script_refs": [],
}
