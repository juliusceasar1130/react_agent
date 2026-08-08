"""
每日各区域实际吞吐量统计场景定义 (daily_area_body_count) - 纯 LLM 场景
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
            "description": "基于 ods.carbody_history 按区域统计历史某日真实吞吐量的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {
        "date_filter": {
            "type": "string",
            "description": "日期过滤条件，用于限定 ods.carbody_history 的 DATE_EVT 范围",
            "required": True,
            "source_column": "DATE_EVT",
            "source_table": "ods.carbody_history",
            "example_values": [
                "DATE(\"DATE_EVT\") = '2026-05-12'",
                "\"DATE_EVT\" >= '2026-05-12' AND \"DATE_EVT\" < '2026-05-13'",
            ],
            "usage": "根据用户指定的日期（如'昨天'→昨天日期，'2026-05-12'→当天），替换 SQL 模板中的 {date_filter} 占位符。推荐使用范围查询避免时区问题。",
            "sql_fragment": 'AND DATE("DATE_EVT") = :date_filter',
        }
    },
}

LLM_SKILL_META = {
    "example_questions": [
        "昨天各区域通过多少车",
        "统计各区域历史日吞吐量",
        "按区域汇总昨天通过车辆数",
    ],
    "triggers": [
        "昨天各区域通过多少车",
        "统计各区域历史日吞吐量",
        "按区域汇总昨天通过车辆数",
    ],
    "intent_keywords": [
        "昨天",
        "历史",
        "日吞吐量",
        "通过",
        "产量",
        "区域",
        "统计",
        "汇总",
    ],
    "workflow": [
        "1. 确认用户要查询的历史日期范围（如“昨天”、“2026-05-12”）。",
        "2. 提醒用户读写站 `RW_STATION_ID` 选择。",
        "3. 查询 `ods.carbody_history` 表。",
        "4. 限定查询时间范围为目标的 `DATE_EVT`。",
        "5. 按读写站聚合，并对 `BODY_ID` 进行去重统计 (COUNT DISTINCT)。",
        "6. 输出各区域在指定时间内的实际吞吐量（通过车辆数）。",
    ],
    "rules": [
        "必须使用 `ods.carbody_history`，绝不能使用 `mart_position_current_overview` 查历史数据。",
        "统计车辆数时必须使用 `COUNT(DISTINCT \"BODY_ID\")`，因为一辆车可能在同一工段产生多条流水。",
        "时间过滤必须基于 `DATE_EVT` 字段。",
    ],
    "gotchas": [
        "这反映的是流水通过量，并不是截面滞留量。",
        "流水表统计包括项目车与量产车在内的全量正常车过站记录。",
    ],
    "output_contract": "输出字段至少包含区域名称、通过车辆总数 (去重后的 BODY_ID 数量)、统计日期范围；默认按数量降序输出。",
}

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "daily_area_body_count",
    "title": "每日各区域实际吞吐量统计",
    "description": "统计过去某天各读写站实际通过的车辆数（真实吞吐量），而非当前快照。",
    "required_inputs": ["date_filter"],
    "optional_inputs": ["process_area"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
