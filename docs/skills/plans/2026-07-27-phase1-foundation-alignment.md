# Phase 1: 基础契约对齐与直通场景过滤 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成快捷直通场景过滤与 Pydantic Schema 契约对齐，解决纯 LLM 场景泄露到前端快捷直通面板的问题。

**Architecture:** 在 `schemas.py` 中为 `ScenarioSummary` 扩充 `direct_path_enabled` 标识；在 `api.py` 的 `list_scenarios_tree` 路由中引入 `is_direct_path_enabled` 判定过滤；更新 `stranded_vehicle_detection` 与 `vehicle_historical_trace` 的场景元数据配置，确保 API 仅下发具备直通能力的场景。

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest / python unittest.

---

### User Review Required

> [!IMPORTANT]
> **代码性约束**：本阶段修改涉及后端路由与场景元数据，请在应用前确认不会破坏现有 API 字段。`GET /api/scenarios` 过滤后，只有具备直通能力的场景会在前端右侧“快捷直通查询”列表中显示，仅 LLM 场景（如 `vehicle_historical_trace`）将仅存在于 AI Agent 对话技能列表中。

---

### Proposed Changes & File Mapping

#### Backend API & Schemas

##### [MODIFY] [schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/schemas.py)
- 为 `ScenarioSummary` 增加 `direct_path_enabled: Optional[bool] = True` 声明。

##### [MODIFY] [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/api.py)
- 在 `scenarios_router` 中实现 `is_direct_path_enabled(s)` 辅助判定函数；
- 在 `list_scenarios_tree()` 中过滤只下发具备直通能力的场景。

#### Scenario Definitions

##### [MODIFY] [scenario.py (stranded_vehicle_detection)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/scenario.py)
- 增加 `"direct_path_enabled": True` 显式声明。

##### [MODIFY] [scenario.py (vehicle_historical_trace)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/vehicle_historical_trace/scenario.py)
- 增加 `"direct_path_enabled": False` 显式声明，关闭直通面板展示。

#### Documentation

##### [MODIFY] [README.md](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/docs/%E5%BF%AB%E6%8D%B7%E6%9F%A5%E8%AF%A2/README.md)
- 更新 5.1 节，消除 `SCENARIO_META` 命名歧义，规范为以 `SCENARIO` 为主导出。

---

## Detailed Task Breakdown

### Task 1: Schema 对齐 - 为 `ScenarioSummary` 扩展 `direct_path_enabled` 属性

**Files:**
- Modify: `backend/app/schemas.py`

- [ ] **Step 1: 检查并定位 `ScenarioSummary`**

在 `backend/app/schemas.py` 中寻找 `ScenarioSummary` 的类定义：
```python
class ScenarioSummary(BaseModel):
    name: str
    title: str
    description: str
```

- [ ] **Step 2: 修改 `ScenarioSummary` 补充 `direct_path_enabled` 属性**

在 `backend/app/schemas.py` 中将 `ScenarioSummary` 修改为：
```python
class ScenarioSummary(BaseModel):
    name: str
    title: str
    description: str
    direct_path_enabled: Optional[bool] = True

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 3: 验证 Schema 语法**

执行 Python 验证脚本：
```bash
python -c "from backend.app.schemas import ScenarioSummary; s = ScenarioSummary(name='test', title='测试', description='说明', direct_path_enabled=True); print(s.model_dump())"
```
Expected output: `{'name': 'test', 'title': '测试', 'description': '说明', 'direct_path_enabled': True}`


---

### Task 2: 场景元数据开关配置 (stranded_vehicle_detection & vehicle_historical_trace)

**Files:**
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/scenario.py`
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/vehicle_historical_trace/scenario.py`

- [ ] **Step 1: 更新 `stranded_vehicle_detection/scenario.py`**

在 `stranded_vehicle_detection/scenario.py` 字典中，添加 `"direct_path_enabled": True`，并保留导出别名 `SCENARIO_META = SCENARIO`：
```python
SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "stranded_vehicle_detection",
    "title": "滞留车检测",
    "description": "车间滞留车辆信息查询与检测。",
    "direct_path_enabled": True,
    "default_template": "in_process",
    "output_type": "table",
    "example_questions": [
        "有哪些滞留车",
        "查一下滞留超过 2 天的车",
        "有哪些 ADP 平台的在制滞留车",
    ],
    "triggers": [
        "有哪些滞留车",
        "查一下滞留车辆",
        "历史滞留车",
        "在制滞留车",
    ],
    "intent_keywords": ["滞留", "滞留车", "超时", "停留", "卡住"],
    "required_inputs": [],
    "optional_inputs": ["platform_filter", "stranded_days", "in_process_stranded_days"],
    "parameters": {
        "platform_filter": {
            "type": "string",
            "description": "按平台筛选滞留车",
            "required": False,
            "source_column": "platform_code",
            "source_table": "dim.carbody_registry",
            "example_values": ["ADP"],
            "usage": "替换 {platform_filter} 占位符；未指定则删除占位符。",
            "sql_fragment": 'AND cr."platform_code" = :platform_filter',
        },
        "stranded_days": {
            "type": "integer",
            "description": "历史滞留天数阈值",
            "required": False,
            "source_column": "retention_checkpoint_pass_at, first_seen_at",
            "source_table": "dim.carbody_registry",
            "example_values": [1, 2, 5],
            "usage": "仅用于 historical 模板。替换 {stranded_days} 占位符（默认 2 天）。",
            "sql_fragment": 'AND (cr."retention_checkpoint_pass_at" - cr."first_seen_at") > make_interval(days => :stranded_days)',
        },
        "in_process_stranded_days": {
            "type": "integer",
            "description": "在制滞留天数阈值",
            "required": False,
            "source_column": "first_seen_at",
            "source_table": "dim.carbody_registry",
            "example_values": [1, 2, 5],
            "usage": "仅用于 in_process 模板。替换 {in_process_stranded_days} 占位符（默认 2 天）。",
            "sql_fragment": 'AND (CURRENT_TIMESTAMP - cr."first_seen_at") > make_interval(days => :in_process_stranded_days)',
        },
    },
    "workflow": [
        "1. 意图分流：默认使用 in_process 模板；若明确提及'历史滞留'才使用 historical 模板。",
        "2. 替换占位符：天数默认 2 天。填入相应 sql_fragment，未指定平台则清理 {platform_filter}。",
        "3. 输出结果：按滞留时长降序排列，在制车需播报当前工艺区域与滚床号。",
    ],
    "rules": [
        "默认仅查在制滞留（in_process 模板），避免全量历史查询。",
        "过滤条件统一作用于主表 `cr` (`dim.carbody_registry`)。",
    ],
    "gotchas": [
        "在制车 `current_rb_code` 可能为空，此时说明最后已知过站并提示暂无精确滚床数据。",
    ],
    "output_contract": "输出字段包含 vehicle_id, platform_code, stranded_type, first_seen_at, retention_checkpoint_pass_at, first_rw_station, retention_checkpoint_station, stranded_hours, current_process_area, current_rb_code；按滞留时长降序排列。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "in_process",
            "scope": "scenario",
            "path": "sql/in_process.sql",
            "description": "在制滞留车查询",
        },
        {
            "type": "sql",
            "name": "historical",
            "scope": "scenario",
            "path": "sql/historical.sql",
            "description": "历史滞留车查询",
        },
    ],
    "script_refs": [],
}

SCENARIO_META = SCENARIO
```

- [ ] **Step 2: 更新 `vehicle_historical_trace/scenario.py`**

在 `vehicle_historical_trace/scenario.py` 中，添加 `"direct_path_enabled": False`，并保留 `SCENARIO_META = SCENARIO`：
```python
SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "vehicle_historical_trace",
    "title": "单车历史轨迹追溯",
    "description": "车身历史轨迹和时间序列。",
    "direct_path_enabled": False,
    "example_questions": [
        "帮我查一下车身 78202612345678 的历史轨迹",
        "这辆车过去都经过了哪些工段",
        "查看单车全生命周期路径"
    ],
    "triggers": [
        "帮我查一下车身 78202612345678 的历史轨迹",
        "这辆车过去都经过了哪些工段",
        "查看单车全生命周期路径",
    ],
    "intent_keywords": [
        "轨迹",
        "历史",
        "追溯",
        "经过",
        "路径",
    ],
    "required_inputs": ["vehicle_id"],
    "optional_inputs": [],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID（通常以 782026 开头）",
            "required": True,
            "source_column": "BODY_ID",
            "source_table": "ods.carbody_history",
            "example_values": ["78202600000001"],
            "usage": "必须将其添加到 SQL 的 WHERE 子句中，过滤 BODY_ID。",
            "sql_fragment": "AND BODY_ID = '{value}'",
        }
    },
    "workflow": [
        "确认用户提供了具体的 vehicle_id。",
        "查询 `ods.carbody_history` 表。",
        "过滤 `BODY_ID` 为用户提供的车身号。",
        "按 `DATE_EVT` 升序排序，以重构时间线。",
        "输出时间戳序列及对应的读写站/节点 (`RW_STATION_ID`)。"
    ],
    "rules": [
        "必须使用 `ods.carbody_history` 查历史轨迹，严禁使用实时快照表。",
        "必须确保按照时间 (`DATE_EVT`) 升序排列结果。",
    ],
    "gotchas": [
        "同一辆车可能在同一个工位产生多次过点事件，不要去重。",
    ],
    "output_contract": "输出字段至少包含时间（DATE_EVT）和工位（RW_STATION_ID）；必须按时间升序排序。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "查询单车历史过点明细的 SQL 模板。",
        }
    ],
    "script_refs": [],
}

SCENARIO_META = SCENARIO
```

- [ ] **Step 3: 运行资产与重载验证脚本**

```bash
python backend/app/skills/domains/verify_assets.py
```
Expected output: `No missing assets found in scenario files.`

---

### Task 3: 后端路由过滤 - 实现 `is_direct_path_enabled` 判定与 `list_scenarios_tree` 过滤

**Files:**
- Modify: `backend/app/api.py:1197-1217`

- [ ] **Step 1: 定位 `api.py` 的 `scenarios_router`**

打开 `backend/app/api.py` 找到第 1195 行起的 `list_scenarios_tree` 路由代码：
```python
@scenarios_router.get("", response_model=List[ScenarioSummary])
def list_scenarios_tree():
    ...
```

- [ ] **Step 2: 实现 `is_direct_path_enabled` 辅助判定与过滤逻辑**

更新 `list_scenarios_tree` 及其辅助函数：
```python
def is_direct_path_enabled(scenario: dict) -> bool:
    """判定场景是否开启快捷直通查询能力 (支持显式标志与模板特征判定)"""
    if "direct_path_enabled" in scenario:
        return bool(scenario["direct_path_enabled"])
    return bool(scenario.get("sql_template_refs")) and bool(scenario.get("default_template"))


@scenarios_router.get("", response_model=List[ScenarioSummary])
def list_scenarios_tree():
    """获取全量业务领域及其下属快捷场景列表 (自动过滤仅 LLM 场景)。"""
    summary_list = []
    domain_skills = get_domain_skills()
    for domain_name, domain_info in domain_skills.items():
        scenarios_items = []
        for s in list_scenarios_by_skill(domain_name):
            # 仅当场景支持直通时，才放入快捷场景面板列表
            if is_direct_path_enabled(s):
                scenarios_items.append({
                    "name": s["name"],
                    "title": s.get("title", s["name"]),
                    "description": s.get("description", ""),
                    "direct_path_enabled": True,
                })
        if scenarios_items:
            summary_list.append({
                "domain": domain_name,
                "domain_title": domain_info.get("title") or domain_name.replace("_", " ").title(),
                "scenarios": scenarios_items,
            })
    return summary_list
```

- [ ] **Step 3: 验证 API 输出过滤效果**

运行 Python 命令行验证：
```bash
python -c "from backend.app.skills.registry import reload_skills; reload_skills(); from backend.app.api import list_scenarios_tree; print(list_scenarios_tree())"
```
Expected output: 仅包含 `stranded_vehicle_detection` 场景，`vehicle_historical_trace` 等 `direct_path_enabled: False` 的场景不会出现在该列表中！

---

### Task 4: 更新文档与 SOP 规范

**Files:**
- Modify: `docs/快捷查询/README.md:115-154`

- [ ] **Step 1: 更新 `docs/快捷查询/README.md` 5.1 节二次开发指南**

确保示例中的主变量名为 `SCENARIO` 且带有 `SCENARIO_META = SCENARIO` 别名：
```python
SCENARIO = {
    "skill_name": "<domain_name>",
    "name": "<scenario_name>",
    "title": "<场景标题>",
    "description": "<场景说明>",
    "direct_path_enabled": True,
    "output_type": "table",
    "default_template": "in_process",
    ...
}

SCENARIO_META = SCENARIO
```

---

## Verification Plan

### Automated Verification
1. 运行 `verify_assets.py` 资产校验：
   ```bash
   python backend/app/skills/domains/verify_assets.py
   ```
2. 运行技能重载与列表过滤验证：
   ```bash
   python -c "from backend.app.skills.registry import reload_skills; reload_skills(); from backend.app.api import list_scenarios_tree; res = list_scenarios_tree(); print([s['name'] for d in res for s in d['scenarios']])"
   ```
   预期输出：只输出带有直通模板且 `direct_path_enabled: True` 的场景列表。

### Manual Verification
1. 启动后端：`uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000`
2. 访问 `http://localhost:8000/api/scenarios` 验证 API 返回结果。
