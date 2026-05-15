"""
车型缺陷趋势场景元数据。

修改时间: 2026-05-15 Asia/Shanghai
主要修改内容:
- 补齐 title 和 example_questions 字段
"""

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "model_defect_trend",
    "title": "车型缺陷趋势",
    "description": "基于 `mart_vehicle_quality_360` 统计某车型或各车型在时间维度上的缺陷趋势。",
    "example_questions": [
        "A7 车型最近的缺陷趋势",
        "各个车型的缺陷趋势对比",
        "最近一周的缺陷波动情况"
    ],
    "triggers": [
        "某车型最近缺陷趋势",
        "各车型缺陷趋势",
        "A7 最近缺陷是否升高",
    ],
    "intent_keywords": ["车型", "趋势", "缺陷", "最近", "波动"],
    "required_inputs": [],
    "optional_inputs": ["defect_type_name", "date_range", "tunnel", "cycle"],
    "parameters": {},
    "workflow": [
        "确认用户要的是趋势，而不是单次检测列表。",
        "优先查询 `mart_vehicle_quality_360`。",
        "按 DATE(detect_time) 和 defect_type_name 聚合检测次数与平均缺陷数。",
        "如用户指定 tunnel 或 cycle，再增加条件。",
        "输出时间趋势并说明统计口径。",
    ],
    "rules": [
        "优先使用 `defect_type_name` 作为车型名称展示字段。",
        "如用户提到 model 编码，再补充 defect_model 过滤。",
        "趋势统计默认输出检测次数与每次检测平均缺陷数。",
    ],
    "gotchas": [
        "`defect_type_name` 是可读名称，`defect_model` 是业务编码，不要混用。",
        "如果要比较不同车型，输出时应保持时间粒度一致。",
    ],
    "output_contract": "输出字段至少包含 stat_date、defect_type_name、detection_count、avg_defect_per_detection。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "按日期和车型统计缺陷趋势的 SQL 模板。",
        }
    ],
    "script_refs": [],
}
