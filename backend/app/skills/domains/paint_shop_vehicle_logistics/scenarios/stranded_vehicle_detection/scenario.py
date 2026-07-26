"""
滞留车检测场景元数据。

修改时间: 2026-07-24 Asia/Shanghai
主要修改内容:
- 精简场景元数据，去重合并冗余规则与触发词，提高 LLM 提示词 Token 效率
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "stranded_vehicle_detection",
    "title": "滞留车检测",
    "description": "车间滞留车辆信息查询与检测。",
    "example_questions": [
        "有哪些滞留车",
        "查一下滞留超过 2 天的车",
        "有哪些 ADP 平台的在制滞留车",
    ],
    "triggers": [
        "有哪些滞留车",
        "查一下滞留车辆",
        "历史滞留车",
        "在制滞留车",
    ],
    "intent_keywords": ["滞留", "滞留车", "超时", "停留", "卡住"],
    "required_inputs": [],
    "optional_inputs": ["platform_filter", "stranded_days", "in_process_stranded_days"],
    "parameters": {
        "platform_filter": {
            "type": "string",
            "description": "按平台筛选滞留车",
            "required": False,
            "source_column": "platform_code",
            "source_table": "dim.carbody_registry",
            "example_values": ["ADP"],
            "usage": "替换 {platform_filter} 占位符；未指定则删除占位符。",
            "sql_fragment": "AND cr.\"platform_code\" = '{value}'",
        },
        "stranded_days": {
            "type": "integer",
            "description": "历史滞留天数阈值",
            "required": False,
            "source_column": "retention_checkpoint_pass_at, first_seen_at",
            "source_table": "dim.carbody_registry",
            "example_values": [1, 2, 5],
            "usage": "仅用于 historical 模板。替换 {stranded_days} 占位符（默认 2 天）。",
            "sql_fragment": 'AND (cr."retention_checkpoint_pass_at" - cr."first_seen_at") > INTERVAL \'{value} days\'',
        },
        "in_process_stranded_days": {
            "type": "integer",
            "description": "在制滞留天数阈值",
            "required": False,
            "source_column": "first_seen_at",
            "source_table": "dim.carbody_registry",
            "example_values": [1, 2, 5],
            "usage": "仅用于 in_process 模板。替换 {in_process_stranded_days} 占位符（默认 2 天）。",
            "sql_fragment": "AND (CURRENT_TIMESTAMP - cr.\"first_seen_at\") > INTERVAL '{value} days'",
        },
    },
    "workflow": [
        "1. 意图分流：默认使用 in_process 模板；若明确提及'历史滞留'才使用 historical 模板。",
        "2. 替换占位符：天数默认 2 天。填入相应 sql_fragment，未指定平台则清理 {platform_filter}。",
        "3. 输出结果：按滞留时长降序排列，在制车需播报当前工艺区域与滚床号。",
    ],
    "rules": [
        "默认仅查在制滞留（in_process 模板），避免全量历史查询。",
        "过滤条件统一作用于主表 `cr` (`dim.carbody_registry`)。",
    ],
    "gotchas": [
        "在制车 `current_rb_code` 可能为空，此时说明最后已知过站并提示暂无精确滚床数据。",
    ],
    "output_contract": "输出字段包含 vehicle_id, platform_code, stranded_type, first_seen_at, retention_checkpoint_pass_at, first_rw_station, retention_checkpoint_station, stranded_hours, current_process_area, current_rb_code；按滞留时长降序排列。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "in_process",
            "scope": "scenario",
            "path": "sql/in_process.sql",
            "description": "在制滞留车查询（默认优先使用）。",
        },
        {
            "type": "sql",
            "name": "historical",
            "scope": "scenario",
            "path": "sql/historical.sql",
            "description": "历史滞留车查询（仅当明确查历史时使用）。",
        },
    ],
    "script_refs": [],
}
