"""
每日缺陷汇总场景元数据。

修改时间: 2026-04-12 Asia/Shanghai
主要修改内容:
- 新增质量缺陷领域的每日缺陷汇总场景
"""

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "daily_defect_summary",
    "title": "每日缺陷汇总",
    "description": "基于 `mart_vehicle_quality_360` 统计每日缺陷总量、检测次数和车型分布，适合日常质量汇总问题。",
    "triggers": [
        "今天缺陷情况怎么样",
        "按天汇总缺陷",
        "每日缺陷总量统计",
    ],
    "intent_keywords": ["每日", "天", "缺陷", "汇总", "趋势"],
    "required_inputs": [],
    "optional_inputs": ["date_range", "defect_type_name", "tunnel"],
    "parameters": {},
    "workflow": [
        "确认用户要的是按天汇总，而不是单次检测明细。",
        "优先查询 `mart_vehicle_quality_360`。",
        "按 DATE(detect_time) 聚合缺陷总量和检测次数。",
        "如用户指定车型或 tunnel，再增加筛选。",
        "输出日期、总缺陷量、检测次数和必要的口径说明。",
    ],
    "rules": [
        "聚合必须在数据库中使用 GROUP BY、SUM、COUNT 完成。",
        "默认按检测次数统计，除非用户明确要求按唯一车身统计。",
        "优先使用 `mart_vehicle_quality_360`。",
    ],
    "gotchas": [
        "当前分析库没有单独的日汇总 mart，趋势问题需要在 `mart_vehicle_quality_360` 上做日聚合。",
        "如果用户要求按唯一车身统计，需要显式说明去重口径。",
    ],
    "output_contract": "输出字段至少包含 stat_date、total_defect_count、detection_count；必要时补充车型过滤或 tunnel 过滤口径。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "按天汇总缺陷总量和检测次数的 SQL 模板。",
        }
    ],
    "script_refs": [],
}
