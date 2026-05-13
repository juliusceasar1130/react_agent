"""
滞留车检测场景元数据。

修改时间: 2026-05-13 Asia/Shanghai
主要修改内容:
- 新增滞留车检测场景，统一入口工位判定，按末站区分历史/在制滞留
"""

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "stranded_vehicle_detection",
    "title": "滞留车检测",
    "description": "基于 `dim.carbody_registry` 检测涂装车间内滞留超过指定天数的车辆。统一以 `first_rw_station IN ('1L360RB','01IS045','01IS205')` 作为入口，按末站是否在出口工位集合中来区分历史滞留（已到出口）和在制滞留（卡在半路）。",
    "triggers": [
        "有哪些滞留车",
        "查一下滞留车辆",
        "有哪些车滞留了",
        "历史滞留车",
        "在制滞留车",
        "卡在产线上的车",
        "ADP 平台滞留车",
        "超过 3 天的滞留车",
    ],
    "intent_keywords": [
        "滞留",
        "滞留车",
        "超时",
        "停留",
        "卡住",
        "历史滞留",
        "在制滞留",
    ],
    "required_inputs": [],
    "optional_inputs": ["exit_condition", "platform_code", "stranded_days"],
    "parameters": {
        "exit_condition": {
            "type": "string",
            "description": "出口站判定条件，区分历史滞留/在制滞留",
            "required": False,
            "source_column": "last_rw_station",
            "source_table": "dim.carbody_registry",
            "example_values": ["历史滞留", "在制滞留", "全部"],
            "usage": "用户说'历史滞留'→填 AND last_rw_station IN (...)；说'在制滞留'→填 AND last_rw_station NOT IN (...)；没说或说全部→删除注释行。",
            "sql_fragment": "AND \"last_rw_station\" IN ('1J440RB', 'K1IS135', 'K2IS075', 'K3IS140')",
        },
        "platform_filter": {
            "type": "string",
            "description": "按平台筛选滞留车",
            "required": False,
            "source_column": "platform_code",
            "source_table": "dim.carbody_registry",
            "example_values": ["ADP"],
            "usage": "当用户指定平台时，添加 platform_code 过滤。不指定则查全部平台。",
            "sql_fragment": "AND \"platform_code\" = '{value}'",
        },
        "stranded_days": {
            "type": "integer",
            "description": "最小滞留天数阈值，默认 1 天",
            "required": False,
            "source_column": "last_seen_at, first_seen_at",
            "source_table": "dim.carbody_registry",
            "example_values": [1, 2, 3, 5, 7],
            "usage": "替换 SQL 中的 INTERVAL 值。用户说'超过 N 天'时，将 N 填入。默认值为 1。",
            "sql_fragment": "AND (\"last_seen_at\" - \"first_seen_at\") > INTERVAL '{value} days'",
        },
    },
    "workflow": [
        "确认用户要查滞留车、历史滞留车还是在制滞留车。",
        "确认是否按平台或滞留天数筛选。",
        "查询 `dim.carbody_registry` 表。",
        "根据用户表达替换 {exit_condition}, {platform_filter}, {stranded_days} 三个占位符。",
        "输出时 stranded_type 字段会自动区分'历史滞留'和'在制滞留'。",
        "按滞留时长降序输出。",
    ],
    "rules": [
        "必须使用 `dim.carbody_registry`，严禁使用实时快照表。",
        "所有大写列名必须用双引号包裹。",
        "入口工位和出口工位集合已内置在 SQL 中，LLM 不要自行修改。",
        "{exit_condition} 有三种模式：历史滞留用 IN、在制滞留用 NOT IN、全量查则删除注释行。",
    ],
    "gotchas": [
        "stranded_type 字段由 CASE WHEN 自动生成，LLM 不需要也不应该修改它。",
    ],
    "output_contract": "输出字段至少包含 vehicle_id, platform_code, stranded_type, first_seen_at, last_seen_at, first_rw_station, last_rw_station, stranded_hours；按滞留时长降序排列。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "检测滞留车的 SQL 模板，统一入口工位集合，按末站区分历史/在制滞留。",
        }
    ],
    "script_refs": [],
}
