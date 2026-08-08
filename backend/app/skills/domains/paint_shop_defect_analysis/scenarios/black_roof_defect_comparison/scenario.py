"""
黑车顶缺陷对比场景定义 (black_roof_defect_comparison) - 纯 LLM 场景
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
            "description": "黑车顶与非黑车顶缺陷对比的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {},
}

LLM_SKILL_META = {
    "example_questions": [
        "黑车顶和非黑车顶的缺陷对比",
        "黑车顶车型的缺陷是否更多？",
        "最近一周黑车顶的缺陷差异情况",
    ],
    "triggers": [
        "黑车顶和非黑车顶缺陷对比",
        "黑车顶车型缺陷是否更多",
        "黑车顶缺陷差异",
    ],
    "intent_keywords": ["黑车顶", "对比", "缺陷", "roof", "black_roof"],
    "workflow": [
        "1. 确认用户要比较的是黑车顶与非黑车顶。",
        "2. 优先查询 `mart_vehicle_quality_360`。",
        "3. 按照黑车顶标记分组聚合缺陷总量和检测次数。",
        "4. 如用户指定车型或时间范围，再增加过滤。",
        "5. 输出对比结果并说明黑车顶字段口径。",
    ],
    "rules": [
        "优先使用 `defect_black_roof` 或业务统一后的黑车顶字段做分组。",
        "应在结果中说明黑车顶字段是文本标记，不是严格布尔值。",
        "聚合必须在数据库中完成。",
    ],
    "gotchas": [
        "`defect_black_roof` 是文本标记字段，不能假设所有值都是严格布尔。",
        "如果需要更严格口径，应在 SQL 中显式定义黑车顶分组规则。",
    ],
    "output_contract": "输出字段至少包含 black_roof_group、detection_count、total_defect_count；必要时可补 avg_defect_per_detection。",
}

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "black_roof_defect_comparison",
    "title": "黑车顶缺陷对比",
    "description": "基于 `mart_vehicle_quality_360` 对比黑车顶与非黑车顶车型的缺陷数量和检测次数差异。",
    "required_inputs": [],
    "optional_inputs": ["defect_type_name", "date_range", "tunnel", "cycle"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
