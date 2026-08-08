# 业务场景技能与快捷直通查询：通用架构设计规范与 RFC 蓝图 (Universal Scenario Spec & RFC)

> **文档版本**: v3.4 (全量 4 阶段实施完工与 12 场景落地版)  
> **文档修改时间**: 2026-07-27  
> **面向对象**: 系统架构师、后端 Agent 开发者、前端 UI 维护人员  
> **状态标记说明**:  
> - **`[现网已落地]`**: 代码库 (`backend/app/skills/`) 已完整实现且可直接调用的机制。  
> - **`[RFC 规划/待实施]`**: 目标架构愿景，后续迭代需补充代码逻辑后方可启用。

---

## 一、 系统全局分层架构与数据流 (Architecture & Data Flow)

场景元数据 (`scenario.py`) 是连接 **前端 UI 控件**、**后端直通 SQL 执行引擎** 与 **LLM Agent 上下文** 的唯一**数据契约中心 (Single Source of Truth, SSoT)**。

不是所有场景技能都需要快捷直通查询能力。系统通过 **双模判定机制 (Dual Determination Scheme)** 区别处理 “直通+LLM 混合场景” 与 “仅 LLM 智能体场景”。

```
                                  ┌──────────────────────────────┐
                                  │    场景模版 (scenario.py)     │
                                  │  (Single Source of Truth)    │
                                  └──────────────┬───────────────┘
                                                 │
                                     直通能力判定 (is_direct_path_enabled)
                                     ┌───────────┴───────────┐
                       [True / 有 SQL 模板]               [False / 无直通需求]
                                     │                       │
                        ┌────────────┴──────────┐            └─────────────────┐
                        ▼                       ▼                              ▼
        【直通查询路径 (Direct-Path Engine)】       │                【LLM Agent 路径 (Skill Agent)】
   - 面向毫秒级响应、确定性 SQL 执行                   │           - 面向开放式问答、意图识别与复杂推理
   - REST API: /api/scenarios/...                     │           - System Prompt / Dynamic Skill Injection
                        │                             │                                │
┌───────────────────────┼───────────────────────┐     │        ┌───────────────────────┴───────────────────────┐
▼                       ▼                       ▼     ▼        ▼                                               ▼
后端解析器               SQL 执行引擎            前端渲染直通卡片  LLM 提示词渲染器                                 Agent 意图/推理
(resolver.py)         (executor.py)        (ScenarioModal)  (renderers.py)                                (SQLAgent/LangGraph)
- 提取 templates       - 加载 sql/*.sql     - Modal          - 注入规则与 workflow                         - 意图匹配与路由
- 推断 widget 控件      - 命名参数绑定       - Form           - 渲染示例与 SQL 范本                         - 动态 SQL 生成/修正
```

---

## 二、 快捷直通能力判定与兼容方案 (Direct-Path Determination Scheme)

### 2.1 业务背景
在实际业务中：
1. **部分场景支持直通**（如 `stranded_vehicle_detection` 滞留车检测）：具备确定性 SQL 模板、动态参数表单与极速响应诉求；
2. **大部分场景仅依赖 LLM**（如 `vehicle_historical_trace` 轨迹追溯、`model_defect_trend` 缺陷趋势）：虽然包含供 LLM 阅读的 SQL 参考模版，但不需要在前端右侧直通弹窗中提供表单直通；
3. **未来渐进升级**：纯 LLM 场景后续可随时开启直通。

为了防止无直通需求的场景误呈现在直通面板或触发 API 报错，系统引入以下 **双模判定机制**。

### 2.2 双模判定规则

```python
def is_direct_path_enabled(scenario: dict) -> bool:
    """判定场景是否开启快捷直通查询能力 (兼容无缝演进)"""
    # 1. 显式开关判定 (优先级最高)
    if "direct_path_enabled" in scenario:
        return bool(scenario["direct_path_enabled"])
    
    # 2. 隐式结构特征判定 (向下兼容现网场景)
    # 具备合法 SQL 模板引用且默认模板不为空，则默认认为支持直通
    has_sql_refs = bool(scenario.get("sql_template_refs"))
    has_default_tmpl = bool(scenario.get("default_template"))
    return has_sql_refs and has_default_tmpl
```

### 2.3 判定方案在全链路的协同机制

| 链路层级 | 判定前行为 (旧) | 判定后兼容行为 (新) |
| :--- | :--- | :--- |
| **场景 API (`GET /api/scenarios`)** | 全量返回所有场景，纯 LLM 场景误置于直通面板 | **基于 `is_direct_path_enabled` 过滤**，直通面板只展示开启直通的场景；纯 LLM 场景仅保留在 `GET /api/chat/skills` 列表中。 |
| **直通解析与执行 API** | 无模板时抛出 `ValueError` 或内部 500 | 若 `is_direct_path_enabled` 为 `False`，明确返回 `400 Bad Request: Direct path not supported for this scenario`。 |
| **前端 UI 渲染 (`FloatingScenarioCards.vue`)** | 所有卡片统一展示 “⚡ 一键直通” | 只有开启直通的场景会渲染悬浮卡片并唤起 `ScenarioModal`；纯 LLM 场景保留在技能列表与 Prompt 中。 |
| **`scenario.py` 元数据配置** | 无区分字段 | 增加可选属性 `"direct_path_enabled": True/False`。 |

---

## 三、 元数据分层规范与消费方隔离 (Layered Metadata & Consumption Scopes)

场景元数据采用 **三段解耦结构 (Three-Block Architecture)**。现网代码与演进划分为：

```
                    scenario.py
                        │
      ┌─────────────────┼─────────────────┐
      ▼                 ▼                 ▼
 1. 身份与控制元数据   2. 直通与 UI 元数据   3. LLM Agent 提示词元数据
(IDENTITY META)     (DIRECT_QUERY_META)    (LLM_SKILL_META)
      │                 │                 │
      └─────────────────┼─────────────────┘
                        ▼
            SCENARIO / SCENARIO_META
            (统一组合导出 & 现网必填字段)
```

### 3.1 结构详细定义与落地状态矩阵

| 分层 | 属性 key | 类型 | 消费方标记 | 实现状态 | 职责与约束说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **身份控制** | `skill_name` | `str` | `[两者都需要]` | `[现网已落地]` | 所属领域标识 (如 `paint_shop_vehicle_logistics`) |
| | `name` | `str` | `[两者都需要]` | `[现网已落地]` | 场景唯一英文 key，必须与目录名一致 |
| | `title` | `str` | `[两者都需要]` | `[现网已落地]` | 中文显示名称 (弹窗顶栏标题 / LLM Prompt 标题) |
| | `description` | `str` | `[两者都需要]` | `[现网已落地]` | 场景业务一句话描述 (首页卡片 / LLM 摘要) |
| | `direct_path_enabled`| `bool`| `[仅直通需要]` | `[现网已落地/兼容]` | **显式开启/关闭快捷直通查询** |
| **直通 UI** | `default_template`| `str` | `[仅直通需要]` | `[现网已落地]` | 直通 API 默认执行的 SQL 模板名称 |
| | `output_type` | `str` | `[仅直通需要]` | `[现网已落地]` | `"table"` \| `"scalar"` \| `"chart"` (多序列图表) |
| | `sql_template_refs`| `list` | `[两者都需要]` | `[现网已落地]` | 关联的 SQL 模板物理文件清单 (LLM 亦读取其作为 SQL 范本) |
| | `script_refs` | `list` | `[两者都需要]` | `[现网已落地]` | 关联的脚本资产文件清单 (默认 `[]`) |
| | `parameters` | `dict` | `[两者都需要]` | `[现网已落地]` | 场景参数定义字典 |
| | `parameters.type` | `str` | `[两者都需要]` | `[现网已落地]` | 参数数据类型 (`"string"` / `"integer"` / `"array"`) |
| | `parameters.description`| `str` | `[两者都需要]` | `[现网已落地]` | 参数业务说明 |
| | `parameters.required`| `bool` | `[两者都需要]` | `[现网已落地]` | 是否必填 (前端校验 / LLM 约束) |
| | `parameters.sql_fragment`| `str` | `[两者都需要]`| `[现网已落地]` | SQL 条件片段模板 |
| | `parameters.example_values`| `list`| `[两者都需要]`| `[现网已落地]` | **现网渲染器强依赖**，示例值数组 |
| | `parameters.usage` | `str` | `[两者都需要]` | `[现网已落地]` | **现网渲染器强依赖**，用法说明文本 |
| | `parameters.widget` | `str` | `[仅直通需要]` | `[现网已落地]` | 前端 UI 控件类型 (可选，`resolver.py` 可自动推断) |
| | `parameters.source_table`| `str` | `[两者都需要]` | `[现网已落地]` | 下拉框查库来源表 |
| | `parameters.source_column`| `str`| `[两者都需要]` | `[现网已落地]` | 下拉框查库来源列 |
| **LLM Agent** | `required_inputs` | `list` | `[两者都需要]` | `[现网已落地]` | **现网强依赖**：必填参数 key 列表 |
| | `optional_inputs` | `list` | `[两者都需要]` | `[现网已落地]` | **现网强依赖**：可选参数 key 列表 |
| | `example_questions`| `list` | `[仅 LLM 需要]` | `[现网已落地]` | 首页推荐搜索框示例问题 |
| | `triggers` | `list` | `[仅 LLM 需要]` | `[现网已落地]` | 唤起该场景技能的典型问法匹配 |
| | `intent_keywords`| `list` | `[仅 LLM 需要]` | `[现网已落地]` | 意图识别与路由关键词列表 |
| | `workflow` | `list` | `[仅 LLM 需要]` | `[现网已落地]` | LLM 执行该场景的推导步骤指导 |
| | `rules` | `list` | `[仅 LLM 需要]` | `[现网已落地]` | 业务硬性统计规则与限制条件 |
| | `gotchas` | `list` | `[仅 LLM 需要]` | `[现网已落地]` | 业务边界易错点与防错提示 |
| | `output_contract` | `str` | `[仅 LLM 需要]` | `[现网已落地]` | 期待输出的字段与格式播报要求 |

---

## 四、 核心实现层机制与深度避坑指南 (Implementation Risk Guidelines)

在开发场景文件与 SQL 模板时，必须遵守以下后端执行层约束与避坑法则：

1. **SQL 注释穿透致命漏洞 Warning (严禁在占位符前加 `--`)**：
   `executor.py` 的替换逻辑为将 `{placeholder}` 替换为 `sql_fragment`。如果 SQL 模板中写成 `-- {vehicle_id}`，替换后会变成 `-- AND BODY_ID = :vehicle_id`（整行变成 SQL 注释），**导致条件失效并引发全表无过滤扫描漏洞**！SQL 模板中的占位符必须单独成行且**绝对不能加 `--` 前缀**。
2. **整行裁剪语法约束**：`executor.py` 采用“未传参整行删除”逻辑。在编写 `sql/*.sql` 模板时，**每个 `{param_name}` 占位符必须单独占据一行**。
3. **后端 API 路由过滤规则**：`backend/app/api.py` 的 `list_scenarios_tree()` 必须校验 `is_direct_path_enabled`，防止仅 LLM 场景泄露到前端直通面板。
4. **Pydantic Schema 对齐**：`backend/app/schemas.py` 中的 `ScenarioSummary` 模型需包含 `direct_path_enabled: Optional[bool] = True`。
5. **多列来源表降级规则**：当 `source_column` 包含逗号多列时，`resolver.py` 会自动降级为不查库。
6. **服务端分页与真实总数感知 (Server-side Pagination & Total Count)**：`executor.py` 自动包裹 `SELECT COUNT(*) FROM (...)` 精确计算物理全量命中数，并采用零侵入子查询 `LIMIT :page_size OFFSET :offset` 实现服务端分页（默认每页 50 条），结合前端 `TableResult.vue` 的 `#` 序号列完成全量行号与分页控制。

---

## 五、 通用规范代码模版 (直通场景 vs 纯 LLM 场景对照)

### 5.1 快捷直通+LLM 混合场景模版 (以 `stranded_vehicle_detection` 滞留车检测为例)

```python
"""
滞留车检测场景定义 (stranded_vehicle_detection) - 支持快捷直通
"""

DIRECT_QUERY_META = {
    "direct_path_enabled": True,        # [仅直通需要] 显式开启快捷直通查询面板
    "output_type": "table",            # [仅直通需要] 结果格式: table | scalar
    "default_template": "in_process",   # [仅直通需要] 默认模板标识
    "sql_template_refs": [             # [两者都需要] SQL 模板清单
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
    "parameters": {
        "platform_filter": {
            "type": "string",
            "description": "按车型平台筛选",
            "required": False,
            "example_values": ["ADP"],
            "usage": "替换 {platform_filter} 占位符；未指定则删除占位符。",
            "widget": "select",
            "source_table": "dim.carbody_registry",
            "source_column": "platform_code",
            "sql_fragment": 'AND cr."platform_code" = :platform_filter',
        },
        "stranded_days": {
            "type": "integer",
            "description": "历史滞留天数阈值",
            "required": False,
            "example_values": [1, 2, 5],
            "usage": "仅用于 historical 模板。替换 {stranded_days} 占位符（默认 2 天）。",
            "source_table": "dim.carbody_registry",
            "source_column": "retention_checkpoint_pass_at, first_seen_at",
            "sql_fragment": 'AND (cr."retention_checkpoint_pass_at" - cr."first_seen_at") > make_interval(days => :stranded_days)',
        },
        "in_process_stranded_days": {
            "type": "integer",
            "description": "在制滞留天数阈值",
            "required": False,
            "example_values": [1, 2, 5],
            "usage": "仅用于 in_process 模板。替换 {in_process_stranded_days} 占位符（默认 2 天）。",
            "source_table": "dim.carbody_registry",
            "source_column": "first_seen_at",
            "sql_fragment": 'AND (CURRENT_TIMESTAMP - cr."first_seen_at") > make_interval(days => :in_process_stranded_days)',
        },
    },
}

LLM_SKILL_META = {
    "example_questions": ["有哪些滞留车", "查一下滞留超过 2 天的车"],
    "triggers": ["有哪些滞留车", "查一下滞留车辆"],
    "intent_keywords": ["滞留", "滞留车"],
    "workflow": ["1. 意图分流：默认使用 in_process 模板。"],
    "rules": ["默认仅查在制滞留。"],
    "gotchas": ["在制车 current_rb_code 可能为空。"],
    "output_contract": "输出字段包含 vehicle_id, platform_code 等。",
}

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "stranded_vehicle_detection",
    "title": "滞留车检测",
    "description": "车间滞留车辆信息查询与检测。",
    "required_inputs": [],
    "optional_inputs": ["platform_filter", "stranded_days", "in_process_stranded_days"],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
```

---

### 5.2 纯 LLM 场景模版 (以 `vehicle_historical_trace` 单车历史轨迹追溯为例)

> **特点**：保留 `sql_template_refs` 给 LLM 阅读 SQL 脚手架，但设置 `direct_path_enabled: False` 不下发到直通面板。

```python
"""
单车历史轨迹追溯场景定义 (vehicle_historical_trace) - 纯 LLM 场景
"""

DIRECT_QUERY_META = {
    "direct_path_enabled": False,       # [仅直通需要] 显式关闭直通，不下发到右侧直通弹窗面板
    "output_type": "table",            # [仅直通需要]
    "default_template": "main",         # [仅直通需要]
    "sql_template_refs": [             # [两者都需要] 保留！renderers.py 会将 sql/main.sql 渲染给 LLM 看
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "查询单车历史过点明细的 SQL 模板。",
        }
    ],
    "script_refs": [],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID（通常以 782026 开头）",
            "required": True,
            "example_values": ["78202600000001"],
            "usage": "必须将其添加到 SQL 的 WHERE 子句中，过滤 BODY_ID。",
            "source_table": "ods.carbody_history",
            "source_column": "BODY_ID",
            "sql_fragment": "AND BODY_ID = :vehicle_id",
        }
    },
}

LLM_SKILL_META = {
    "example_questions": [
        "帮我查一下车身 78202612345678 的历史轨迹",
        "这辆车过去都经过了哪些工段",
        "查看单车全生命周期路径",
    ],
    "triggers": [
        "帮我查一下车身 78202612345678 的历史轨迹",
        "这辆车过去都经过了哪些工段",
        "查看单车全生命周期路径",
    ],
    "intent_keywords": ["轨迹", "历史", "追溯", "经过", "路径"],
    "workflow": [
        "1. 确认用户提供了具体的 vehicle_id。",
        "2. 查询 `ods.carbody_history` 表。",
        "3. 过滤 `BODY_ID` 为用户提供的车身号。",
        "4. 按 `DATE_EVT` 升序排序，以重构时间线。",
        "5. 输出时间戳序列及对应的读写站/节点 (`RW_STATION_ID`)。",
    ],
    "rules": [
        "必须使用 `ods.carbody_history` 查历史轨迹，严禁使用实时快照表。",
        "必须确保按照时间 (`DATE_EVT`) 升序排列结果。",
    ],
    "gotchas": ["同一辆车可能在同一个工位产生多次过点事件，不要去重。"],
    "output_contract": "输出字段至少包含时间（DATE_EVT）和工位（RW_STATION_ID）；必须按时间升序排序。",
}

SCENARIO = {
    "skill_name": "paint_shop_vehicle_logistics",
    "name": "vehicle_historical_trace",
    "title": "单车历史轨迹追溯",
    "description": "车身历史轨迹和时间序列。",
    "required_inputs": ["vehicle_id"],
    "optional_inputs": [],
    **DIRECT_QUERY_META,
    **LLM_SKILL_META,
}

SCENARIO_META = SCENARIO
```

---

### 5.3 全量 12 业务场景解耦与直通状态分布 (Global Scenario Matrix)

截至 2026-07-27，代码库中全量 12 个业务场景已统一完成 **三段解耦结构** 重构与直通标记配置：

| 领域分类 | 场景唯一名称 (key) | 场景中文标题 | 直通状态 (`direct_path_enabled`) | 说明 |
| :--- | :--- | :--- | :---: | :--- |
| **车身物流** | `stranded_vehicle_detection` | 滞留车检测 | **`True`** | ⚡ **当前阶段唯一直通场景**，支持弹窗模版切换 |
| | `vehicle_historical_trace` | 单车历史轨迹追溯 | `False` | 纯 LLM 场景，保留 SQL 范本供 Agent 阅读 |
| | `realtime_area_body_count` | 实时各区域车身数量统计 | `False` | 纯 LLM 场景 |
| | `daily_area_body_count` | 每日各区域实际吞吐量统计 | `False` | 纯 LLM 场景 |
| | `abnormal_vehicle_monitor` | 实时异常车监控 | `False` | 纯 LLM 场景 |
| **缺陷质量** | `vehicle_adjacent_defects` | 前后车身顺序及缺陷追溯 | `False` | 纯 LLM 场景 |
| | `leak_detection` | 漏检与未检测车辆监控 | `False` | 纯 LLM 场景 |
| | `model_defect_trend` | 车型缺陷趋势 | `False` | 纯 LLM 场景 |
| | `tunnel_cycle_defect_comparison` | Tunnel 与 Cycle 缺陷对比 | `False` | 纯 LLM 场景 |
| | `defect_station_distribution` | 缺陷部位分布 | `False` | 纯 LLM 场景 |
| | `daily_defect_summary` | 每日缺陷汇总 | `False` | 纯 LLM 场景 |
| | `black_roof_defect_comparison` | 黑车顶缺陷对比 | `False` | 纯 LLM 场景 |

---

## 六、 新场景二次开发 SOP (Developer Standard Operating Procedure)

新增业务场景时，开发人员需遵循以下步骤：

1. **确定直通需求**：评估该场景是否具备确定性的直通 SQL 模板与前端表单诉求。
   - **若需要直通**：使用 5.1 模版，配置 `direct_path_enabled: True`；
   - **若不需要直通**：使用 5.2 模版，配置 `direct_path_enabled: False`。
2. **编写 SQL 模板**：在场景目录下新建 `sql/main.sql`，**独占一行且不带 `--` 注释**书写占位符（如 `{vehicle_id}`）。
3. **编写 `scenario.py`**：填入必填属性（包含 `required_inputs`/`optional_inputs`、`example_values` 与 `usage`）。
4. **导出校验**：确保导出主变量名为 **`SCENARIO`**。
5. **验证资产路径**：运行 `python backend/app/skills/domains/verify_assets.py` 进行无错校验。

---

## 七、 实施与开发阶段划分 Roadmap (Development Phases)

为保障系统平滑过渡、最小化线上风险并逐步实现完整的架构愿景，项目开发划分为 **四个渐进阶段**：

```
 Phase 1: 基础契约与直通过滤 ──► Phase 2: 安全与占位符修补 ──► Phase 3: Token 剥离与自动派生 ──► Phase 4: 高级控件与图表契约
 (解决纯 LLM 泄露与 API 对齐)      (修补 SQL 注释漏洞与参数绑定)     (LLM Context 60% 成本精简)       (DateWidget & Chart 扩展)
```

### 阶段一：基础契约对齐与直通场景过滤 (Phase 1) —— 【已于 2026-07-27 全量完工并验证通过】
* **主要目标**：解决纯 LLM 场景泄露到前端直通侧边栏的问题，完成 FastAPI 与 Pydantic Schema 对齐。
* **实施任务**：
  1. 在 `backend/app/schemas.py` 的 `ScenarioSummary` 中添加 `direct_path_enabled: Optional[bool] = True` 字段；
  2. 修改 `backend/app/api.py` 的 `list_scenarios_tree()` 函数，增加 `is_direct_path_enabled(s)` 校验逻辑，仅把开启直通的场景下发到直通列表；
  3. 将 `stranded_vehicle_detection/scenario.py` 更新为带有 `direct_path_enabled: True` 的标准模版；
  4. 将现有仅依赖 LLM 的场景（如 `vehicle_historical_trace`）配置 `direct_path_enabled: False`；
  5. 修正 `docs/快捷查询/README.md` 5.1 节中的导出名，保持 `SCENARIO` 与 `SCENARIO_META` 协同。
* **验收标准**：启动服务后访问 `GET /api/scenarios`，确认返回列表中仅包含 `stranded_vehicle_detection` 滞留车直通场景。

### 阶段二：安全与漏洞修补 (Phase 2) —— 【已于 2026-07-27 全量完工并验证通过】
* **主要目标**：修补 SQL 注释穿透漏洞，统一参数绑定与占位符规范。
* **实施任务**：
  1. 扫描排查所有场景目录下的 `sql/*.sql` 模板，修复如 `-- {vehicle_id}` 的注释穿透行，确保占位符独占一行且不带 `--`；
  2. 统一各场景 `scenario.py` 中的 `sql_fragment` 写法，推荐采用 `:param_name` 命名绑定模式。
* **验收标准**：运行 `python backend/app/skills/domains/verify_assets.py` 通过无错校验；直通接口在传参和未传参时均能安全执行并生成干净 SQL。

### 阶段三：Token 精简与渲染隔离 RFC (Phase 3) —— 【已于 2026-07-27 全量完工并验证通过】
* **主要目标**：在 LLM 上下文渲染层实现按需剥离，节省 60% Prompt Token 消耗，并简化模版维护。
* **实施任务**：
  1. 修改 `backend/app/skills/renderers.py` 的 `render_scenario_for_llm` 函数：
     - 在拼接 System Prompt 时，仅输出 `name`、`type`、`description` 和 `sql_fragment`；
     - 自动剔除 `widget`、`source_table`、`source_column` 等纯前端 UI 渲染元数据；
  2. 修改 `backend/app/skills/discovery.py`：
     - 增加 `required_inputs` 与 `optional_inputs` 的内存自动派生兜底逻辑（若模版中未填，由字典的 `required` 属性派生）；
     - 增加 `getattr(module, "SCENARIO") or getattr(module, "SCENARIO_META")` 的容错获取。
* **验收标准**：输出 `render_scenario_for_llm` 的渲染结果，确认纯 UI 属性已被剔除，Prompt Token 占用下降 50%+，且 Agent SQL 生成准确率不受影响。

### 阶段四：高级控件与 UI/数据契约扩展 (Phase 4) —— 【已于 2026-07-27 全量完工并验证通过】
* **主要目标**：支持日期控件与可视化图表输出契约。
* **实施任务**：
  1. 在 `backend/app/skills/direct_path/resolver.py` 中扩充 `type=="date"` 与 `type=="daterange"` 的控件推断分支；
  2. 前端新增 `DateWidget.vue` 并在 `ParameterForm.vue` 中完成组件注册映射；
  3. 在 `backend/app/skills/direct_path/formatter.py` 中扩展 `output_type=="chart"` 的契约格式化分支。
* **验收标准**：端到端支持按日期范围筛选与柱状图/折线图结果渲染。
