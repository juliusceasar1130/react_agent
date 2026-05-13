"""
实时异常车监控场景元数据。

修改时间: 2026-05-13 Asia/Shanghai
主要修改内容:
- 新增实时异常车监控场景
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "abnormal_vehicle_monitor",
    "title": "实时异常车监控",
    "description": "基于 `mart_abnormal_vehicle_current` 监控当前车间内的异常车辆（如空车身、非产品前缀的调试车）。",
    "triggers": [
        "当前车间内有哪些异常车",
        "找一下当前的空占位",
        "排查一下设备采集异常",
        "异常车分布",
    ],
    "intent_keywords": [
        "异常",
        "空车身",
        "空跑",
        "非产品",
        "调试车",
        "错误",
    ],
    "required_inputs": [],
    "optional_inputs": ["abnormal_type"],
    "parameters": {
        "abnormal_type": {
            "type": "string",
            "description": "异常类型编码，用于筛选特定类型的异常车",
            "required": False,
            "source_column": "abnormal_type",
            "source_table": "mart_abnormal_vehicle_current",
            "example_values": ["empty_vehicle_id_with_carrier", "non_product_prefix", "blank_vehicle_id_with_carrier"],
            "usage": "当用户询问特定异常时，将其添加到 SQL 的 WHERE 子句中。",
            "sql_fragment": "AND abnormal_type = '{value}'",
        }
    },
    "workflow": [
        "确认用户是在查询当前的现场异常情况。",
        "查询 `mart_abnormal_vehicle_current` 表。",
        "如用户指定了具体异常类型，增加 abnormal_type 过滤。",
        "按工艺区域或异常类型做统计，或者直接输出明细。",
        "返回当前的异常车清单及异常原因 (`abnormal_reason`)。"
    ],
    "rules": [
        "异常车仅在制阶段存在，严禁使用历史流水表去查询历史异常车。",
        "必须使用 `mart_abnormal_vehicle_current` 或 `fct_abnormal_vehicle_current`。",
    ],
    "gotchas": [
        "异常车的 vehicle_id 可能是残缺的、重复的甚至是 '--------------'，不要用 vehicle_id 作为唯一键去重。",
    ],
    "output_contract": "输出字段至少包含 carrier_id, process_area, abnormal_type, abnormal_reason；默认按区域排序输出明细或汇总。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "查询当前异常车明细的 SQL 模板。",
        }
    ],
    "script_refs": [],
}
