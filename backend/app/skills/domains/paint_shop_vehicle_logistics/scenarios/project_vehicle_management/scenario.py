"""
项目车综合管理场景定义 (project_vehicle_management) - 支持快捷直通
"""

DIRECT_QUERY_META = {
    "direct_path_enabled": True,             # 开启快捷直通查询
    "output_type": "table",                 # 结果渲染格式
    "default_template": "current_positions", # 默认执行模板
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "current_positions",
            "scope": "scenario",
            "path": "sql/current_positions.sql",
            "description": "在制项目车实时位置",
        },
        {
            "type": "sql",
            "name": "orders_overview",
            "scope": "scenario",
            "path": "sql/orders_overview.sql",
            "description": "项目车台账",
        },
        {
            "type": "sql",
            "name": "quality_defects",
            "scope": "scenario",
            "path": "sql/quality_defects.sql",
            "description": "项目车缺陷检测",
        },
    ],
    "script_refs": [],
    "parameters": {
        "project_stage_filter": {
            "type": "string",
            "description": "按项目阶段筛选 (如 VFF, PT)",
            "required": False,
            "example_values": [],
            "usage": "替换 {project_stage_filter} 占位符；未指定则清理。",
            "widget": "select",
            "source_table": "ods.ods_fis_project_vehicle_orders",
            "source_column": "project_stage",
            "sql_fragment": 'AND pvo."project_stage" = :project_stage_filter',
        },
        "project_vehicle_no_filter": {
            "type": "string",
            "description": "按项目车编号精确/模糊匹配",
            "required": False,
            "example_values": [],
            "usage": "替换 {project_vehicle_no_filter} 占位符。",
            "widget": "input",
            "source_table": "ods.ods_fis_project_vehicle_orders",
            "source_column": "project_vehicle_no",
            "sql_fragment": 'AND pvo."project_vehicle_no" LIKE CONCAT(\'%\', :project_vehicle_no_filter, \'%\')',
        },
        "process_area_filter": {
            "type": "string",
            "description": "按在制工艺区域筛选",
            "required": False,
            "example_values": [],
            "usage": "用于 current_positions 模板。替换 {process_area_filter} 占位符。",
            "widget": "select",
            "source_table": "dim.dim_process_area",
            "source_column": "process_area_name",
            "sql_fragment": 'AND fpc."process_area" = :process_area_filter',
        },
        "has_defect_only_filter": {
            "type": "boolean",
            "description": "仅看有缺陷的项目车",
            "required": False,
            "example_values": [True],
            "widget": "select",
            "usage": "用于 quality_defects 模板。替换 {has_defect_only_filter} 占位符。",
            "sql_fragment": 'AND vde."total_defect_count" > 0',
        },
    },
}

LLM_SKILL_META = {
    "example_questions": [
        "查一下车间里目前有哪些项目车",
        "目前在制 VFF 阶段的项目车都在什么位置",
        "项目车 PP2-EREV-VFF-56 有检测出缺陷吗",
        "查询所有项目车的 FIS 订单明细",
    ],
    "triggers": [
        "项目车",
        "试验车",
        "试制车",
        "VFF项目车",
        "PT项目车",
        "项目车位置",
        "项目车订单",
    ],
    "intent_keywords": ["项目车", "试验车", "试制车", "VFF", "PT", "项目阶段", "项目车编号"],
    "workflow": [
        "1. 意图分流：查在制位置默认使用 current_positions 模板；查订单台账使用 orders_overview 模板；查缺陷质检使用 quality_defects 模板。",
        "2. 参数识别：提取项目阶段（如 VFF/PT）、项目车编号（如 PP2-EREV-VFF-56）或工艺区域。",
        "3. 规范判定：项目车优先级最高，只要关联到 project_vehicle_no 即使车身号为 782026 前缀也算项目车。",
        "4. 结果播报：输出项目车编号、阶段、车身号、当前工艺区域及滚床编号。",
    ],
    "rules": [
        "项目车识别优先级最高，判定依据为 project_vehicle_no 非空。",
        "默认仅列出在馆在制项目车，如果用户查订单全量再使用 orders_overview 模板。",
    ],
    "gotchas": [
        "部分试制车 vehicle_id 可能前 13 位为 PIN 码而非标准 782026 前缀，必须用 pvo.composite_pin_no 关联。",
    ],
    "output_contract": "输出字段至少包含 project_vehicle_no, project_stage, vehicle_id, process_area, current_rb_code。",
}

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "project_vehicle_management",
    "title": "项目车管理",
    "description": "项目车 (VFF/PT 等试制车) 的订单台账、实时位置追踪与缺陷质量 360 汇总。",
    "required_inputs": [],
    "optional_inputs": [
        "project_stage_filter",
        "project_vehicle_no_filter",
        "process_area_filter",
        "has_defect_only_filter",
    ],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
