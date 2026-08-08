"""
实时各区域车身数量统计场景定义 (realtime_area_body_count) - 纯 LLM 场景
"""

DIRECT_QUERY_META = {
    "direct_path_enabled": False,       # [仅直通需要] 显式关闭直通，不下发到右侧直通弹窗面板
    "output_type": "table",            # [仅直通需要]
    "default_template": "main",         # [仅直通需要]
    "sql_template_refs": [             # [两者都需要] SQL 模板清单
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "按工艺区域统计实时正常车（项目车与量产车）数量的 SQL 模板，支持 process_area 参数筛选。",
        }
    ],
    "script_refs": [],
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
            "sql_fragment": "AND overview.process_area IN (:process_area)",
        }
    },
}

LLM_SKILL_META = {
    "example_questions": [
        "现在每个区域有多少车身",
        "查看各区域实时车身分布",
        "电泳区域有多少车身",
    ],
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
    "workflow": [
        "1. 确认用户要的是当前实时快照，而不是某天或某班次的历史窗口。",
        "2. 优先查询 `mart_position_current_overview`，不要直接从源表开始写查询。",
        "3. 判断用户是否指定了特定工艺区域：",
        "  - 如指定了单区域（如'电泳区域'），添加 AND overview.process_area = '电泳'",
        "  - 如指定了多区域（如'电泳和面漆'），添加 AND overview.process_area IN ('电泳', '面漆')",
        "  - 如未指定，则查询所有区域，不添加筛选条件",
        "4. 默认筛选正常车 `entity_type IN ('project_vehicle', 'product_vehicle')`（包含项目车与量产车）。",
        "5. 按 process_area 聚合统计实时车身数量。",
        "6. 输出各区域实时数量，并附带统计口径说明。",
    ],
    "rules": [
        "默认统计所有正常车（项目车与量产车），不统计异常车。",
        "优先使用 `mart_position_current_overview`。",
        "聚合必须在数据库中使用 GROUP BY 与 COUNT 完成。",
        "process_area 参数值必须与 `dim_process_area.process_area_name` 匹配。",
    ],
    "gotchas": [
        "这是实时快照统计，不应混入日期、班次或时间窗口条件。",
        "如果用户问的是异常车或全部当前占位，不能继续只筛选正常车。",
        "用户可能使用简称（如'电泳'），需匹配完整的区域名称。",
    ],
    "output_contract": "输出字段至少包含 process_area、vehicle_count；默认按 vehicle_count 降序输出，并说明实时统计口径。如用户指定了区域，仅返回指定区域的结果。",
}

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "realtime_area_body_count",
    "title": "实时各区域车身数量统计",
    "description": "当前快照，统计各区域正常车（项目车与量产车）数量，支持按区域名称筛选，并输出实时分区域数量口径说明。",
    "required_inputs": [],
    "optional_inputs": ["process_area"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
