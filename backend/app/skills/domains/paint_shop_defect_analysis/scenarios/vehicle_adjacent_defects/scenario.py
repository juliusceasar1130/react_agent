"""
前后车身缺陷追溯场景元数据。

修改时间: 2026-05-23 Asia/Shanghai
主要修改内容:
- 新增前后车身缺陷追溯场景
"""

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "vehicle_adjacent_defects",
    "title": "前后车身缺陷追溯",
    "description": "基于车身号和指定读写站，查询该点前后通过的 N 辆车，并匹配每辆车与过点时间最接近的一条缺陷检测记录。",
    "example_questions": [
        "帮我查一下车身 78202612345678 在工位 STATION_A 过点时，前后的车有没有缺陷",
        "查询这辆车和它前后一辆车的缺陷记录"
    ],
    "triggers": [
        "前后车身缺陷",
        "相邻车辆缺陷",
        "前后车"
    ],
    "intent_keywords": [
        "前后",
        "相邻",
        "车身",
        "缺陷",
        "最近"
    ],
    "required_inputs": ["vehicle_id", "station_id"],
    "optional_inputs": ["n_adjacent"],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID",
            "required": True,
            "source_column": "BODY_ID",
            "source_table": "ods.carbody_history"
        },
        "station_id": {
            "type": "string",
            "description": "过点读写站 ID",
            "required": True,
            "source_column": "RW_STATION_ID",
            "source_table": "ods.carbody_history"
        },
        "n_adjacent": {
            "type": "integer",
            "description": "前后相邻查询车辆的数量",
            "required": False,
            "default": 1
        }
    },
    "workflow": [
        "确认用户提供了具体的 vehicle_id。",
        "如果用户未提供 station_id，建议先使用单车历史轨迹追溯查询车辆经过的读写站，引导用户选择一个。",
        "将 n_adjacent 默认设置为 1（即前1辆和后1辆）。",
        "执行查询并返回前后车的缺陷数量记录。"
    ],
    "rules": [
        "必须确保 `station_id` 有值才能进行本查询。",
        "结果保留无缺陷检测记录的过点车辆，且明确标记 target/before/after 角色。"
    ],
    "gotchas": [],
    "output_contract": "输出字段必须包含 car_role, BODY_ID, pass_time 以及缺陷统计数量列。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "查询前后相邻车辆最近缺陷记录的 SQL 模板。"
        }
    ],
    "script_refs": [],
}
