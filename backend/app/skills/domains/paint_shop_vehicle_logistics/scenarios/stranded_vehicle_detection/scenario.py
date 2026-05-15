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
    "description": "基于 `dim.carbody_registry` 检测涂装车间内的滞留车辆。场景提供多个专用 SQL 模板：`in_process`（默认，带 JOIN，查询在制车辆位置）和 `historical`（查询已出口历史车辆）。请根据用户问题意图选择最匹配的模板进行参数填充。",
    "example_questions": [
        "有哪些滞留车",
        "查一下滞留超过 3 天的车",
        "有哪些 ADP 平台的滞留车"
    ],
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
    "optional_inputs": ["platform_filter", "stranded_days"],
    "parameters": {

        "platform_filter": {
            "type": "string",
            "description": "按平台筛选滞留车",
            "required": False,
            "source_column": "platform_code",
            "source_table": "dim.carbody_registry",
            "example_values": ["ADP"],
            "usage": "当用户指定平台时，添加 cr.platform_code 过滤。不指定则查全部平台。",
            "sql_fragment": "AND cr.\"platform_code\" = '{value}'",
        },
        "stranded_days": {
            "type": "integer",
            "description": "最小滞留天数阈值，默认 1 天",
            "required": False,
            "source_column": "last_seen_at, first_seen_at",
            "source_table": "dim.carbody_registry",
            "example_values": [1, 2, 3, 5, 7],
            "usage": "替换 SQL 中的 INTERVAL 值。用户说'超过 N 天'时，将 N 填入。默认值为 1。",
            "sql_fragment": 'AND (cr."last_seen_at" - cr."first_seen_at") > INTERVAL \'{value} days\'',
        },
    },
    "workflow": [
        "判断用户意图：如果未明确说明（默认）或指明'在制滞留'，选择 `in_process` 模板；如果明确指明'历史滞留'，选择 `historical` 模板。",
        "确认是否按平台或滞留天数筛选。",
        "根据用户表达替换选定模板中的 {platform_filter}, {stranded_days} 两个占位符。",
        "按滞留时长降序输出，同时在自然语言回答中，针对在制车明确合并播报其所在的工艺区域 (current_process_area) 与具体滚床号 (current_rb_code)。",
    ],
    "rules": [
        "默认只查在制滞留（使用 in_process 模板），绝对不要默认查所有类型，以保证效率。",
        "过滤条件应统一应用于主表 `cr` (`dim.carbody_registry`)。",
        "所有大写列名必须用双引号包裹，带别名时如 `cr.\"last_seen_at\"`。",
        "场景下方提供了多个 SQL 模板，必须根据用户意图（在制 vs 历史）选择正确的模板，严禁将 in_process 的 JOIN 逻辑强行套用到历史查询中。",
        "入口/出口过滤和 JOIN 逻辑已内置在各个模板中，直接使用对应模板，不要自行修改这些基础条件。"
    ],
    "gotchas": [
        "部分在制车的 `current_rb_code` 可能为空。此时应说明其最后已知过站为 `last_rw_station`，并告知暂无当前精确滚床数据。",
        "stranded_type 字段已硬编码在各个模板中，LLM 不需要自行推导。"
    ],
    "output_contract": "输出字段包含 vehicle_id, platform_code, stranded_type, first_seen_at, last_seen_at, first_rw_station, last_rw_station, stranded_hours, current_process_area, current_rb_code；按滞留时长降序排列。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "in_process",
            "scope": "scenario",
            "path": "sql/in_process.sql",
            "description": "在制滞留车查询（默认优先使用）。包含了对当前事实表的 JOIN 以及对历史车的过滤。",
        },
        {
            "type": "sql",
            "name": "historical",
            "scope": "scenario",
            "path": "sql/historical.sql",
            "description": "历史滞留车查询（仅当用户明确要求时使用）。去除了 JOIN 操作，以提升历史记录查询效率。",
        }
    ],
    "script_refs": [],
}
