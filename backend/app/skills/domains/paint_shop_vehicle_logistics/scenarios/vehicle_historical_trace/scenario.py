"""
单车历史轨迹追溯场景元数据。

修改时间: 2026-05-13 Asia/Shanghai
主要修改内容:
- 新增单车历史轨迹追溯场景
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "vehicle_historical_trace",
    "title": "单车历史轨迹追溯",
    "description": "基于 `ods.carbody_history` 还原单辆车的完整历史过点路径与时间序列。",
    "triggers": [
        "帮我查一下车身 78202612345678 的历史轨迹",
        "这辆车过去都经过了哪些工段",
        "查看单车全生命周期路径",
    ],
    "intent_keywords": [
        "轨迹",
        "历史",
        "追溯",
        "经过",
        "路径",
    ],
    "required_inputs": ["vehicle_id"],
    "optional_inputs": [],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID（通常以 782026 开头）",
            "required": True,
            "source_column": "BODY_ID",
            "source_table": "ods.carbody_history",
            "example_values": ["78202600000001"],
            "usage": "必须将其添加到 SQL 的 WHERE 子句中，过滤 BODY_ID。",
            "sql_fragment": "AND BODY_ID = '{value}'",
        }
    },
    "workflow": [
        "确认用户提供了具体的 vehicle_id。",
        "查询 `ods.carbody_history` 表。",
        "过滤 `BODY_ID` 为用户提供的车身号。",
        "按 `DATE_EVT` 升序排序，以重构时间线。",
        "输出时间戳序列及对应的工位/节点 (`RW_STATION_ID`)。"
    ],
    "rules": [
        "必须使用 `ods.carbody_history` 查历史轨迹，严禁使用实时快照表。",
        "必须确保按照时间 (`DATE_EVT`) 升序排列结果。",
    ],
    "gotchas": [
        "同一辆车可能在同一个工位产生多次过点事件，不要去重。",
    ],
    "output_contract": "输出字段至少包含时间（DATE_EVT）和工位（RW_STATION_ID）；必须按时间升序排序。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "查询单车历史过点明细的 SQL 模板。",
        }
    ],
    "script_refs": [],
}
