"""
滞留车检测场景定义 (stranded_vehicle_detection) - 支持快捷直通
"""

DIRECT_QUERY_META = {
    "direct_path_enabled": True,        # [仅直通需要] 显式开启快捷直通查询面板
    "output_type": "table",            # [仅直通需要] 结果格式: table | scalar
    "default_template": "in_process",   # [仅直通需要] 默认模板标识
    "sql_template_refs": [             # [两者都需要] SQL 模板清单
        {
            "type": "sql",
            "name": "in_process",
            "scope": "scenario",
            "path": "sql/in_process.sql",
            "description": "在制滞留车查询",
        },
        {
            "type": "sql",
            "name": "historical",
            "scope": "scenario",
            "path": "sql/historical.sql",
            "description": "历史滞留车查询",
        },
    ],
    "script_refs": [],
    "parameters": {
        "vehicle_type_filter": {
            "type": "string",
            "description": "车辆类型筛选（默认产品车）",
            "required": False,
            "default": "product_vehicle",
            "example_values": ["product_vehicle", "project_vehicle", "abnormal_vehicle", "all"],
            "usage": "替换 {vehicle_type_filter} 占位符。默认筛选产品车 (product_vehicle)。",
            "widget": "select",
            "options": [
                {"value": "product_vehicle", "label": "产品车"},
                {"value": "project_vehicle", "label": "项目车"},
                {"value": "abnormal_vehicle", "label": "异常车"},
                {"value": "all", "label": "不限"},
            ],
            "sql_fragment": "AND (:vehicle_type_filter = 'all' OR (:vehicle_type_filter = 'product_vehicle' AND NULLIF(trim(cr.\"project_vehicle_no\"), '') IS NULL AND NULLIF(trim(cr.\"vehicle_id\"), '') LIKE '782026%') OR (:vehicle_type_filter = 'project_vehicle' AND NULLIF(trim(cr.\"project_vehicle_no\"), '') IS NOT NULL) OR (:vehicle_type_filter = 'abnormal_vehicle' AND NULLIF(trim(cr.\"project_vehicle_no\"), '') IS NULL AND (NULLIF(trim(cr.\"vehicle_id\"), '') NOT LIKE '782026%' OR NULLIF(trim(cr.\"vehicle_id\"), '') IS NULL)))",
        },
        "platform_filter": {
            "type": "string",
            "description": "按车型平台筛选",
            "required": False,
            "example_values": [],
            "usage": "替换 {platform_filter} 占位符；未指定则删除占位符。",
            "widget": "select",
            "source_table": "dim.carbody_registry",
            "source_column": "platform_code",
            "sql_fragment": 'AND cr."platform_code" = :platform_filter',
        },
        "stranded_days": {
            "type": "integer",
            "description": "历史滞留天数阈值",
            "required": False,
            "example_values": [2, 3],
            "usage": "仅用于 historical 模板。替换 {stranded_days} 占位符（默认 2 天）。",
            "source_table": "dim.carbody_registry",
            "source_column": "retention_checkpoint_pass_at, first_seen_at",
            "sql_fragment": 'AND (cr."retention_checkpoint_pass_at" - cr."first_seen_at") > make_interval(days => :stranded_days)',
        },
        "in_process_stranded_days": {
            "type": "integer",
            "description": "在制滞留天数阈值",
            "required": False,
            "example_values": [2, 3],
            "usage": "仅用于 in_process 模板。替换 {in_process_stranded_days} 占位符（默认 2 天）。",
            "source_table": "dim.carbody_registry",
            "source_column": "first_seen_at",
            "sql_fragment": 'AND (CURRENT_TIMESTAMP - cr."first_seen_at") > make_interval(days => :in_process_stranded_days)',
        },
    },
}

LLM_SKILL_META = {
    "example_questions": ["有哪些滞留车", "查一下滞留超过 2 天的车", "有哪些 ADP 平台的在制滞留车", "查一下项目车滞留情况"],
    "triggers": ["有哪些滞留车", "查一下滞留车辆", "历史滞留车", "在制滞留车", "项目滞留车"],
    "intent_keywords": ["滞留", "滞留车", "超时", "停留", "卡住", "产品车", "项目车"],
    "workflow": [
        "1. 意图分流：默认使用 in_process 模板；若明确提及'历史滞留'才使用 historical 模板。",
        "2. 使用工具咨询滞留天数，推荐 2 天。默认筛选产品车 (vehicle_type_filter='product_vehicle')，除非用户明确询问项目车或全量车。未指定平台则清理 {platform_filter}。",
        "3. 输出结果：按滞留时长降序排列，在制车需播报当前工艺区域与滚床号。",
    ],
    "rules": [
        "默认仅查在制滞留（in_process 模板），避免全量历史查询。",
        "默认优先查询产品车（product_vehicle）的滞留情况；若用户明确询问试制/试验项目车，需设置 vehicle_type_filter='project_vehicle'；若查询异常车，设为 vehicle_type_filter='abnormal_vehicle'；若查询不限类型，设为 'all'。",
        "过滤条件统一作用于主表 `cr` (`dim.carbody_registry`)。",
    ],
    "gotchas": [
        "在制车 `current_rb_code` 可能为空，此时说明没有采集到数据提示暂无精确滚床数据。",
    ],
    "output_contract": "输出字段包含 vehicle_id, project_vehicle_no, platform_code, stranded_type, first_seen_at, retention_checkpoint_pass_at, first_rw_station, retention_checkpoint_station, stranded_hours, current_process_area, current_rb_code；按滞留时长降序排列。",
}

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "stranded_vehicle_detection",
    "title": "滞留车检测",
    "description": "车间滞留车辆信息查询与检测。",
    "required_inputs": [],
    "optional_inputs": ["vehicle_type_filter", "platform_filter", "stranded_days", "in_process_stranded_days"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
