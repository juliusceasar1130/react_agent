"""
实时各区域车身数量统计场景元数据。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 将场景迁移到按场景名聚合的目录结构
- 调整 SQL 资产引用为 `scope + path` 语义
- 保留 process_area 参数化筛选能力
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_tracking",
    "name": "realtime_area_body_count",
    "title": "实时各区域车身数量统计",
    "description": "基于当前 rb_position_data 实时快照，统计各区域的有效车身数量，支持按区域名称筛选，并输出实时分区域数量口径说明。",
    "triggers": [
        "实时统计各个区域的车身数量",
        "现在每个区域有多少车身",
        "查看各区域实时车身分布",
        "电泳区域有多少车身",
        "电泳和面漆区域各有多少车身",
    ],
    "intent_keywords": [
        "实时",
        "区域",
        "车身数量",
        "分布",
        "当前",
    ],
    "required_inputs": [],
    "optional_inputs": ["process_area"],
    "parameters": {
        "process_area": {
            "type": "array",
            "items_type": "string",
            "description": "工艺区域名称列表，用于筛选特定区域的车身数量，你应该优先检查维度表：process_areas中有哪些值",
            "required": False,
            "source_column": "process_area",
            "source_table": "process_areas",
            "example_values": ["电泳", "面漆", "烘干", "电泳烘干", "面漆烘干"],
            "usage": "当用户询问特定区域时，将此参数添加到 SQL 的 WHERE 子句中。如用户未指定区域，则查询所有区域。",
            "sql_fragment": "AND rp.process_area IN ('{values}')",
        }
    },
    "workflow": [
        "确认用户要的是当前实时快照，而不是某天或某班次的历史窗口。",
        "判断用户是否指定了特定工艺区域：",
        "  - 如指定了单区域（如'电泳区域'），添加 AND rp.process_area = '电泳'",
        "  - 如指定了多区域（如'电泳和面漆'），添加 AND rp.process_area IN ('电泳', '面漆')",
        "  - 如未指定，则查询所有区域，不添加筛选条件",
        "应用有效车辆过滤规则，排除空位、无车记录和无效载体。",
        "按 process_area 聚合统计实时车身数量。",
        "输出各区域实时数量，并附带统计口径说明。",
    ],
    "rules": [
        "只统计 vehicle_id 前缀为 782026 的有效车辆。",
        "排除 body_type = '-----' 与 carrier_id = '0' 的记录。",
        "聚合必须在数据库中使用 GROUP BY 与 COUNT 完成。",
        "process_area 参数值必须与 process_areas 表中的 area_name 匹配。",
    ],
    "gotchas": [
        "这是实时快照统计，不应混入日期、班次或时间窗口条件。",
        "carrier_id = '0' 和 body_type = '-----' 代表空位/无车，不能计入区域数量。",
        "用户可能使用简称（如'电泳'），需匹配完整的区域名称。",
    ],
    "output_contract": "输出字段至少包含 process_area、vehicle_count；默认按 vehicle_count 降序输出，并说明实时统计口径。如用户指定了区域，仅返回指定区域的结果。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "按工艺区域统计实时有效车身数量的 SQL 模板，支持 process_area 参数筛选。",
        }
    ],
    "script_refs": [],
}
