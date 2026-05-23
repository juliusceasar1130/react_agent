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
    "description": "基于车身号和指定读写站，查询该点前后/相邻通过的 N 辆车，并匹配每辆车与过点时间最接近的一条缺陷检测记录。",
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
    ],
    "required_inputs": ["vehicle_id", "station_id"],
    "optional_inputs": ["n_adjacent"],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID",
            "required": True,
            "source_column": "BODY_ID",
            "source_table": "ods.carbody_history",
            "example_values": ["78202612345678"],
            "usage": "用于定位目标车辆，作为主查询参数。",
            "sql_fragment": "WHERE \"BODY_ID\" = '{{vehicle_id}}'"
        },
        "station_id": {
            "type": "string",
            "description": "过点读写站 ID",
            "required": True,
            "source_column": "RW_STATION_ID",
            "source_table": "ods.carbody_history",
            "example_values": ["STATION_A"],
            "usage": "用于确定查询的基准读写站位置。",
            "sql_fragment": "AND \"RW_STATION_ID\" = '{{station_id}}'"
        },
        "n_adjacent": {
            "type": "integer",
            "description": "前后相邻查询车辆的数量",
            "required": False,
            "default": 1,
            "example_values": [1, 3, 5],
            "usage": "控制目标车辆前后查询的数量（例如设置为1代表前1辆和后1辆）。",
            "sql_fragment": "LIMIT {{n_adjacent}}"
        }
    },
    "workflow": [
        "确认用户提供了具体的 vehicle_id。",
        "确认用户提供了具体的 station_id，建议从L3ACC21IS01（面漆1线入口）、L3ACC21IS02（面漆2线入口）、L3ACC21IS03（面漆3线入口）三个读写站中选择。或者自定义。",
        "将 n_adjacent 默认设置为 3（即前3辆和后3辆）。",
        "执行查询并返回前后车的缺陷数量记录。"
    ],
    "rules": [
        "必须确保 `station_id` 有值才能进行本查询。",
        "结果保留无缺陷检测记录的过点车辆，且明确标记 target/before/after 角色。"
    ],
    "gotchas": [],
    "output_contract": "输出字段必须包含 car_role, BODY_ID, body_type, color_code, black_roof, type_name, pass_time 以及各个station_<x>_defect_count缺陷及total_defect_count统计数量列。不要其他输出",
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
