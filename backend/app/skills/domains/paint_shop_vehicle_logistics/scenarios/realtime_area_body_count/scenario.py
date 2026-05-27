"""
实时各区域车身数量统计场景元数据。

修改时间: 2026-04-16 Asia/Shanghai
主要修改内容:
- 将场景迁移到按场景名聚合的目录结构
- 调整 SQL 资产引用为 `scope + path` 语义
- 保留 process_area 参数化筛选能力
- 对齐 `analytics_db` 当前总览口径，优先查询 `mart_position_current_overview`
- 补充领域技能摘要相关字段注释，便于后续维护
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    # 会进入领域技能一级摘要，作为场景唯一标识展示。
    "name": "realtime_area_body_count",
    "title": "实时各区域车身数量统计",
    # 会进入领域技能一级摘要，作为场景说明展示。
    "description": "当前快照，统计各区域正式产品车数量，支持按区域名称筛选，并输出实时分区域数量口径说明。",
    "example_questions": [
        "现在每个区域有多少车身",
        "查看各区域实时车身分布",
        "电泳区域有多少车身"
    ],
    # 当前仅在 load_scenario 二级加载时完整展示，不进入领域技能一级摘要。
    "triggers": [
        "实时统计各个区域的车身数量",
        "现在每个区域有多少车身",
        "查看各区域实时车身分布",
        "电泳区域有多少车身",
        "电泳和面漆区域各有多少车身",
    ],
    # 当前仅用于场景命中提示/理解，不进入领域技能一级摘要。
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
            "description": "工艺区域名称列表，用于筛选特定区域的车身数量，你应该优先检查维度表：dim_process_area 中有哪些值",
            "required": False,
            "source_column": "process_area",
            "source_table": "dim_process_area",
            "example_values": ["电泳", "面漆", "烘干", "电泳烘干", "面漆烘干"],
            "usage": "当用户询问特定区域时，将此参数添加到 SQL 的 WHERE 子句中。如用户未指定区域，则查询所有区域。",
            "sql_fragment": "AND overview.process_area IN ('{values}')",
        }
    },
    "workflow": [
        "确认用户要的是当前实时快照，而不是某天或某班次的历史窗口。",
        "优先查询 `mart_position_current_overview`，不要直接从源表开始写查询。",
        "判断用户是否指定了特定工艺区域：",
        "  - 如指定了单区域（如'电泳区域'），添加 AND overview.process_area = '电泳'",
        "  - 如指定了多区域（如'电泳和面漆'），添加 AND overview.process_area IN ('电泳', '面漆')",
        "  - 如未指定，则查询所有区域，不添加筛选条件",
        "筛选 `entity_type = 'product_vehicle'`，只统计正式产品车。",
        "按 process_area 聚合统计实时车身数量。",
        "输出各区域实时数量，并附带统计口径说明。",
    ],
    "rules": [
        "只统计正式产品车，不统计异常车。",
        "优先使用 `mart_position_current_overview`。",
        "聚合必须在数据库中使用 GROUP BY 与 COUNT 完成。",
        "process_area 参数值必须与 `dim_process_area.process_area_name` 匹配。",
    ],
    "gotchas": [
        "这是实时快照统计，不应混入日期、班次或时间窗口条件。",
        "如果用户问的是异常车或全部当前占位，不能继续只筛选正式产品车。",
        "用户可能使用简称（如'电泳'），需匹配完整的区域名称。",
    ],
    "output_contract": "输出字段至少包含 process_area、vehicle_count；默认按 vehicle_count 降序输出，并说明实时统计口径。如用户指定了区域，仅返回指定区域的结果。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "按工艺区域统计实时正式产品车数量的 SQL 模板，支持 process_area 参数筛选。",
        }
    ],
    "script_refs": [],
}
