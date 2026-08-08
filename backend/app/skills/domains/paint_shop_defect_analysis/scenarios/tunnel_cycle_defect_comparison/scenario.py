"""
Tunnel 与 Cycle 缺陷对比场景定义 (tunnel_cycle_defect_comparison) - 纯 LLM 场景
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
            "description": "按 tunnel 和 cycle 聚合缺陷数量的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {},
}

LLM_SKILL_META = {
    "example_questions": [
        "不同检测通道 (Tunnel) 的缺陷差异",
        "对比第一次检测和复检的缺陷分布",
        "查看某车型在各检测周期的质量表现",
    ],
    "triggers": [
        "不同 tunnel 的缺陷差异",
        "不同 cycle 的缺陷对比",
        "某车型 tunnel cycle 下缺陷差异",
    ],
    "intent_keywords": ["tunnel", "cycle", "通道", "检测次数", "对比", "差异"],
    "workflow": [
        "1. 确认用户要比较的是 tunnel、cycle 还是两者组合。",
        "2. 优先查询 `mart_vehicle_quality_360`。",
        "3. 按 tunnel 和 cycle 聚合缺陷总量、检测次数。",
        "4. 如用户指定车型或时间范围，再加过滤。",
        "5. 输出差异对比并说明统计口径。",
    ],
    "rules": [
        "默认按检测次数口径聚合。",
        "如用户要求按唯一车身比较，应显式增加去重逻辑。",
        "优先使用 `mart_vehicle_quality_360`。",
    ],
    "gotchas": [
        "同一台车可以有多个 cycle，直接统计会按检测次数累加。",
        "不同 tunnel / cycle 的样本量可能差异较大，解释结果时应注意检测次数。",
    ],
    "output_contract": "输出字段至少包含 tunnel、cycle、detection_count、total_defect_count；必要时可补 avg_defect_per_detection。",
}

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "tunnel_cycle_defect_comparison",
    "title": "Tunnel 与 Cycle 缺陷对比",
    "description": "基于 `mart_vehicle_quality_360` 对比不同检测通道和检测次数下的缺陷差异。",
    "required_inputs": [],
    "optional_inputs": ["defect_type_name", "date_range", "tunnel", "cycle"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
