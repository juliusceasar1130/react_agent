"""
前后车身缺陷追溯场景定义 (vehicle_adjacent_defects) - 纯 LLM 场景
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
            "description": "查询前后相邻车辆最近缺陷记录的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID",
            "required": True,
            "source_column": "BODY_ID",
            "source_table": "ods.carbody_history",
            "example_values": ["78202612345678"],
            "usage": "用于定位目标车辆，作为主查询参数。",
            "sql_fragment": "WHERE \"BODY_ID\" = :vehicle_id",
        },
        "station_id": {
            "type": "string",
            "description": "过点读写站 ID",
            "required": True,
            "source_column": "RW_STATION_ID",
            "source_table": "ods.carbody_history",
            "example_values": ["STATION_A"],
            "usage": "用于确定查询的基准读写站位置。",
            "sql_fragment": "AND \"RW_STATION_ID\" = :station_id",
        },
        "n_adjacent": {
            "type": "integer",
            "description": "前后相邻查询车辆的数量",
            "required": False,
            "default": 1,
            "example_values": [1, 3, 5],
            "usage": "控制目标车辆前后查询的数量（例如设置为1代表前1辆和后1辆）。",
            "sql_fragment": "LIMIT :n_adjacent",
        },
    },
}

LLM_SKILL_META = {
    "example_questions": [
        "查询这辆车和它前后一辆车的缺陷记录",
        "查询某车的前后N台车信息",
    ],
    "triggers": ["前后车身缺陷", "相邻车辆缺陷", "前后车"],
    "intent_keywords": [
        "前后",
        "相邻",
        "车身",
        "缺陷",
    ],
    "workflow": [
        "1. 必须确认用户提供了具体的 vehicle_id。",
        "2. 必须确认用户提供了具体的 station_id，提醒从L3ACC21IS01（面漆1线入口）、L3ACC21IS02（面漆2线入口）、L3ACC21IS03（面漆3线入口）三个读写站中选择。**不要替用户选择**",
        "3. 提醒用户将 n_adjacent 默认设置为 3（即前3辆和后3辆）。",
        "4. 执行查询并返回前后车的缺陷数量记录。",
    ],
    "rules": [
        "必须确保 `station_id`和`station_id` 有值才能进行本查询。",
        "结果保留无缺陷检测记录的过点车辆，且明确标记 target/before/after 角色。",
    ],
    "gotchas": [],
    "output_contract": """输出格式：Markdown 表格，列顺序如下：
1. car_role — 角色（target/目标车, before/前车, after/后车）
2. BODY_ID — 车身ID
3. body_type — EINES代码
4. color_code — 颜色代码
5. black_roof — 是否黑顶
6. type_name — 车型名称
7. pass_time — 过点时间
8. **total_defect_count** — 缺陷总数（须**加粗**）
9. station_1_defect_count — 右侧缺陷数
10. station_2_defect_count — 左侧缺陷数
11. station_3_defect_count — 车顶缺陷数
12. station_4_defect_count — 前盖缺陷数
13. station_5_defect_count — 尾门缺陷数

规则：保留所有车辆行（含 total_defect_count=0）；不输出 detect_time、time_diff_sec 等中间计算字段。仅输出表格，不附加解释说明。""",
}

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "vehicle_adjacent_defects",
    "title": "前后车身顺序及缺陷追溯",
    "description": "基于过点历史信息，查询某车前后或者相邻车身信息，包括陷检测记录。",
    "required_inputs": ["vehicle_id", "station_id"],
    "optional_inputs": ["n_adjacent"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
