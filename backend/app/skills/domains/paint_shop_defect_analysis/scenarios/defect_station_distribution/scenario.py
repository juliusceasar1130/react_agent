"""
缺陷部位分布场景定义 (defect_station_distribution) - 纯 LLM 场景
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
            "description": "汇总 5 个部位缺陷数量的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {},
}

LLM_SKILL_META = {
    "example_questions": [
        "缺陷主要集中在哪些部位？",
        "A7 车型的部位缺陷分布情况",
        "右侧和左侧哪个部位的缺陷更多？",
    ],
    "triggers": [
        "缺陷主要集中在哪些部位",
        "某车型部位缺陷分布",
        "右侧左侧车顶哪个缺陷最多",
    ],
    "intent_keywords": ["部位", "工位", "分布", "右侧", "左侧", "车顶", "前盖", "尾门"],
    "workflow": [
        "1. 确认用户关注的是部位分布，而不是单次检测异常列表。",
        "2. 优先查询 `mart_vehicle_quality_360`。",
        "3. 分别汇总 5 个 station_*_defect_count。",
        "4. 如用户指定车型、tunnel 或 cycle，再增加过滤。",
        "5. 输出各部位缺陷数量及主要缺陷来源。",
    ],
    "rules": [
        "需要明确 5 个部位字段的业务含义。",
        "部位统计应在数据库中使用 SUM 完成。",
        "优先使用 `mart_vehicle_quality_360`。",
    ],
    "gotchas": [
        "5 个 station 字段分别对应右侧、左侧、车顶、前盖、尾门。",
        "如果用户要求按车型比较，应确保对比口径一致。",
    ],
    "output_contract": "输出字段至少包含各部位缺陷数量；建议同时给出 total_defect_count 或主要缺陷来源说明。",
}

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "defect_station_distribution",
    "title": "缺陷部位分布",
    "description": "基于 `mart_vehicle_quality_360` 分析 5 个检测部位的缺陷分布，适合识别主要缺陷来源。",
    "required_inputs": [],
    "optional_inputs": ["defect_type_name", "date_range", "tunnel", "cycle"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
