"""
单车历史轨迹追溯场景定义 (vehicle_historical_trace) - 纯 LLM 场景
"""

DIRECT_QUERY_META = {
    "direct_path_enabled": False,       # [仅直通需要] 显式关闭直通，不下发到右侧直通弹窗面板
    "output_type": "table",            # [仅直通需要]
    "default_template": "main",         # [仅直通需要]
    "sql_template_refs": [             # [两者都需要] 保留！renderers.py 会将 sql/main.sql 渲染给 LLM 看
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "查询单车历史过点明细的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID（通常以 782026 开头）",
            "required": True,
            "example_values": ["78202600000001"],
            "usage": "必须将其添加到 SQL 的 WHERE 子句中，过滤 BODY_ID。",
            "source_table": "ods.carbody_history",
            "source_column": "BODY_ID",
            "sql_fragment": "AND BODY_ID = :vehicle_id",
        }
    },
}

LLM_SKILL_META = {
    "example_questions": [
        "帮我查一下车身 78202612345678 的历史轨迹",
        "这辆车过去都经过了哪些工段",
        "查看单车全生命周期路径",
    ],
    "triggers": [
        "帮我查一下车身 78202612345678 的历史轨迹",
        "这辆车过去都经过了哪些工段",
        "查看单车全生命周期路径",
    ],
    "intent_keywords": ["轨迹", "历史", "追溯", "经过", "路径"],
    "workflow": [
        "1. 确认用户提供了具体的 vehicle_id。",
        "2. 查询 `ods.carbody_history` 表。",
        "3. 过滤 `BODY_ID` 为用户提供的车身号。",
        "4. 按 `DATE_EVT` 升序排序，以重构时间线。",
        "5. 输出时间戳序列及对应的读写站/节点 (`RW_STATION_ID`)。",
    ],
    "rules": [
        "必须使用 `ods.carbody_history` 查历史轨迹，严禁使用实时快照表。",
        "必须确保按照时间 (`DATE_EVT`) 升序排列结果。",
    ],
    "gotchas": ["同一辆车可能在同一个工位产生多次过点事件，不要去重。"],
    "output_contract": "输出字段至少包含时间（DATE_EVT）和工位（RW_STATION_ID）；必须按时间升序排序。",
}

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "vehicle_historical_trace",
    "title": "单车历史轨迹追溯",
    "description": "车身历史轨迹和时间序列。",
    "required_inputs": ["vehicle_id"],
    "optional_inputs": [],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
