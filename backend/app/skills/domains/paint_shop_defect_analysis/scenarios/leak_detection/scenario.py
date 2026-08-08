"""
漏检与未检测车辆监控场景定义 (leak_detection) - 纯 LLM 场景
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
            "description": "基于读写站过站历史和全局关联判定漏检车辆的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {
        "start_time": {
            "type": "string",
            "description": "开始过车时间 (格式: YYYY-MM-DD HH:MM:SS)",
            "required": True,
            "source_column": "DATE_EVT",
            "source_table": "ods.carbody_history",
            "example_values": ["2026-06-29 08:00:00"],
            "usage": "限制过车记录的开始时间范围，用于初步过滤。",
            "sql_fragment": "h.\"DATE_EVT\" >= :start_time",
        },
        "end_time": {
            "type": "string",
            "description": "结束过车时间 (格式: YYYY-MM-DD HH:MM:SS)",
            "required": True,
            "source_column": "DATE_EVT",
            "source_table": "ods.carbody_history",
            "example_values": ["2026-06-29 17:00:00"],
            "usage": "限制过车记录的结束时间范围，用于初步过滤。",
            "sql_fragment": "h.\"DATE_EVT\" <= :end_time",
        },
        "station_id": {
            "type": "string",
            "description": "检测线入口读写站代码 (L3ACC21IS01: 1线, L3ACC21IS02: 2线, L3ACC21IS03: 3线)",
            "required": False,
            "source_column": "RW_STATION_ID",
            "source_table": "ods.carbody_history",
            "example_values": ["L3ACC21IS02"],
            "usage": "可选的过站读写站代码过滤条件。",
            "sql_fragment": "AND h.\"RW_STATION_ID\" = :station_id",
        },
    },
}

LLM_SKILL_META = {
    "example_questions": [
        "查询昨天有过车记录但是没有检测记录的车辆",
        "统计今天上午8点到12点从面漆入口过去但没检测的车辆",
        "帮我找出上周经过面漆线入口却漏检的车身",
    ],
    "triggers": [
        "有过车记录但是没有检测记录",
        "漏检车",
        "检测失败没有记录",
        "未检测车辆列表",
        "过车无缺陷记录",
    ],
    "intent_keywords": [
        "过车",
        "没有检测",
        "无检测",
        "检测失败",
        "漏检",
        "未检测",
    ],
    "workflow": [
        "1. 确认用户提供了明确的时间段（start_time 与 end_time）。如果提问模糊（如'昨天'），按标准时间转换公式计算边界。",
        "2. 将 `ods.carbody_history` 限制在 `L3ACC21IS01`, `L3ACC21IS02`, `L3ACC21IS03` 读写站，代表车辆已到达检测入口。",
        "3. 与 `fct.fct_vehicle_defect_detection` 进行 LEFT JOIN 连接车身ID，过滤检测主键为 NULL 的漏检车身。",
        "4. 关联 `dim.dim_vehicle_profile` 获取车型名称 and 位置信息，按过车时间 `pass_time` 升序排列输出列表。",
    ],
    "rules": [
        "必须告知用户查询的读写站过点时间范围说明。",
        "输出结果中应明确区分：车辆是从面漆哪一条线（1线/2线/3线）的读写站检测口驶入的。",
        "如果漏检车辆数为 0，应友好告知用户在指定时间段内所有通过检测口的车辆均有正常检测记录。",
    ],
    "gotchas": [
        "不能直接查 mart_vehicle_quality_360，因为它的时间是车身首次进车间或当前位置更新时间，无法代表经过面漆检测入口的时间。必须关联 ods.carbody_history 的 DATE_EVT 进行过滤。",
        "由于分流改道等原因，经过2线入口的车辆有可能在1线检测。因此 LEFT JOIN 必须仅在车辆ID上做全局关联，不可强行绑定通道号，以免把改道检测车误判为漏检。",
    ],
    "output_contract": """输出格式：Markdown 表格，包含以下字段：
- BODY_ID: 车身ID
- pass_station: 检测口读写站 (L3ACC21IS01/02/03)
- expected_line: 对应过站线 (1线/2线/3线)
- pass_time: 经过检测口的时间
- type_name: 车型中文名
- current_process_area: 车辆当前所在工艺区域（以便找回车辆）
- current_carrier_id: 车辆当前载体卡号""",
}

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "leak_detection",
    "title": "漏检与未检测车辆监控",
    "description": "基于面漆3个检测线入口读写站的过站历史，查询指定过车时间内已通过检测口但无任何缺陷检测记录的车辆，防止假阳性误报。",
    "required_inputs": ["start_time", "end_time"],
    "optional_inputs": ["station_id"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
