# 快捷场景面板设计规格

> 修改时间: 2026-07-26
> 修改内容: 初始版本，解耦架构 + 泛化性设计

## Goal

在主页右侧增加"快捷场景面板"，罗列常用场景（如滞留车检测），用户点击后直接执行 SQL 并展示结果，绕过 LLM Agent 推理链路。支持手动刷新和参数定制。

## Motivation

当前首页 `WelcomeDashboard` 展示场景卡片，但点击后以聊天消息形式发送给 LLM Agent，由 Agent 决策执行。这种方式耗时较长、结果不确定，不适合用户快速了解"当前有多少滞留车"这类固定查询场景。

## Architecture

### 分层解耦总览

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ScenarioList│  │ParameterForm│ │ResultRenderer│ │ScenarioPanel│  │
│  │(场景列表)  │  │(通用表单)  │  │(结果分发)   │  │(容器/编排) │  │
│  └──────────┘  └──────────┘  └─────┬──────┘  └────────────┘  │
│                                    │                          │
│                    ┌────────┬──────┼──────┬────────┐          │
│                    ▼        ▼      ▼      ▼        ▼          │
│              TableResult ScalarResult ChartResult ...         │
│              (复用 DimensionTable)                             │
├─────────────────────────────────────────────────────────────┤
│                         API Layer                             │
│   GET /api/scenarios                                        │
│   GET /api/scenarios/{domain}/{scenario}/params              │
│   POST /api/scenarios/{domain}/{scenario}/execute            │
├─────────────────────────────────────────────────────────────┤
│                       Backend Modules                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ resolver │  │ executor │  │ formatter│                   │
│  │(参数解析) │  │(SQL执行)  │  │(结果格式化)│                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
│       │             │              │                          │
│       └─────────────┼──────────────┘                          │
│                     ▼                                         │
│              registry / discovery / models                   │
│              (现有技能注册与发现，不变)                          │
└─────────────────────────────────────────────────────────────┘
```

**核心原则：每个模块只做一件事，通过明确的接口通信。**

### 与现有 LLM Agent 链路的关系

```
                    ┌──────────────────────┐
                    │   用户输入/点击场景    │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                                 ▼
   ┌──────────────────┐              ┌──────────────────┐
   │  聊天 Agent 路径   │              │  快捷面板直通路径   │
   │  (现有链路)        │              │  (本次新增)        │
   │  LLM → Skill → SQL│              │  resolver →       │
   │  流式 SSE 返回     │              │  executor →       │
   └──────────────────┘              │  formatter → JSON │
                                     └──────────────────┘
```

两条路径独立，互不干扰。直通路径的 resolver / executor / formatter 均为纯函数，不依赖 HTTP 上下文，可被任何调用方（API、CLI、测试）使用。

## Backend

### 模块职责

#### 1. `resolver.py` — 参数解析层 [NEW]

职责：加载场景定义，解析参数默认值，查询 source_table 可选值。不涉及 SQL 执行。

```python
def resolve_params(
    domain_name: str,
    scenario_name: str,
) -> dict:
    """
    返回参数定义，每个参数已填充 default 值。
    
    {
        "name": "stranded_vehicle_detection",
        "title": "滞留车检测",
        "output_type": "table",
        "parameters": {
            "platform_filter": {
                "type": "string",
                "widget": "select",
                "default": "",
                "options": [{"value": "", "label": "不限"}, {"value": "ADP", "label": "ADP"}],
                ...
            },
            ...
        }
    }
    """

def resolve_source_options(
    source_table: str,
    source_column: str,
) -> list[dict]:
    """
    查询 source_table 中 source_column 的去重值，返回下拉选项。
    LIMIT 200，超出时前端显示"更多选项请搜索"。
    """
```

**default 值规则：**
- 取 `example_values[0]`，若 `example_values` 为空则根据 type 给空值（`string → ""`, `integer → null`）

**widget 推断规则（当 `widget` 字段未显式声明时）：**

| `type` | 条件 | 推断 widget |
|--------|------|-------------|
| `string` | 有 `source_table` | `"select"` |
| `string` | 无 `source_table` | `"text"` |
| `integer` | — | `"number"` |
| `array` | — | `"multiselect"` |

**source_table 选项查询：**
- `source_table` 通常带 Schema 前缀（如 `dim.carbody_registry`），需按 `.` 拆分为 `"dim"."carbody_registry"` 后再拼接 SQL
- 仅允许在 **只读数据库（analytics_db）** 中执行，数据库连接使用 `ANALYTICS_DATABASE_URL`（与主 SQL 执行一致）
- 不限制 Schema（`dim` / `ods` / `mart` / `fct` 均可），因为查询仅为 `SELECT DISTINCT column FROM table LIMIT 200`，是只读操作
- 若 `source_column` 包含逗号或复杂表达式（如 `"retention_checkpoint_pass_at, first_seen_at"`），说明该列不适合直接 `SELECT DISTINCT`，优雅降级为文本输入框 + 静态 `example_values` 提示
- SQL：`SELECT DISTINCT "{column}" FROM {schema}.{table} LIMIT 200`
- 结果缓存 60 秒（避免每次切换场景都查 DB）
- 超过 200 条时前端下拉框支持输入过滤

#### 2. `executor.py` — SQL 执行层 [NEW]

职责：加载 SQL 模板 → 参数替换 → 执行。不关心参数从哪来，不关心结果如何格式化。

```python
def execute_scenario(
    domain_name: str,
    scenario_name: str,
    params: dict[str, str],
    template_name: str | None = None,
) -> list[tuple]:
    """
    返回原始查询结果行列表（不格式化）。
    由调用方决定如何格式化。
    """
```

**SQL 模板选择逻辑：**
1. 若调用方指定 `template_name`，使用该模板
2. 否则使用 `scenario.py` 中的 `default_template` 字段
3. 若 `default_template` 也未设置，取 `sql_template_refs[0].name`

**参数替换（防注入）：**

核心原则：用户参数值**绝不直接拼入 SQL 字符串**，必须通过 SQLAlchemy bindparam 传递。

替换流程：
1. 遍历 SQL 模板中的占位符 `{param_name}`
2. 若 `params[param_name]` 为 `None`、`""` 或纯空白 → 视为"未填写"，从 SQL 中**删除包含该占位符的整行**
3. 若参数有值 → 用 `ParameterDefinition.sql_fragment` 替换占位符，但 `{value}` 替换为 SQLAlchemy 命名占位符 `:param_name`
4. 最终 SQL 通过 `text(sql).bindparams(param_name=value, ...)` 参数化执行

**INTERVAL 等引号内嵌场景的处理：**

PostgreSQL 中 `INTERVAL ':days days'` 会将 bindparam 当作字符串字面量，无法绑定。`sql_fragment` 中涉及此类场景时，需使用 Postgres 表达式写法：

```python
# 原 sql_fragment（不兼容 bindparam）
"AND ... > INTERVAL '{value} days'"

# 改为（兼容 bindparam）
"AND ... > make_interval(days => :stranded_days)"
# 或
"AND ... > INTERVAL '1 day' * :stranded_days"
```

已有的 `stranded_vehicle_detection` 场景的 `sql_fragment` 需同步修正。新增场景的 `sql_fragment` 编写规范在 `skills_guide.md` 中补充。

**空值剔除示例：**

```sql
-- 原始模板
WHERE 1=1
    {platform_filter}
    {stranded_days}
ORDER BY ...

-- 用户未填 platform_filter（值为 ""），填了 stranded_days=2
-- 生成 SQL：
WHERE 1=1
    AND ... > make_interval(days => :stranded_days)
ORDER BY ...
```

**SQL 执行：**
- 使用 `ANALYTICS_DATABASE_URL` 连接 PostgreSQL（与 `chart_artifacts.py` / `csv_export_tool.py` 模式一致）
- 结果行数受 `DIMENSION_RESULT_HARD_LIMIT`（默认 300 行）保护

#### 3. `formatter.py` — 结果格式化层 [NEW]

职责：根据 `output_type` 将原始行数据格式化为前端可直接消费的结构。

```python
def format_result(
    rows: list[tuple],
    columns: list[str],
    output_type: str,
) -> dict:
    """
    根据 output_type 返回不同结构：
    
    - "table":  {"type": "table", "columns": [...], "rows": [[...], ...], "row_count": N}
    - "scalar": {"type": "scalar", "value": ..., "label": "..."}
    - "chart":  {"type": "chart", "chart_type": "...", "series": [...], "labels": [...]}
    """
```

| `output_type` | 行为 | 使用场景 |
|---------------|------|----------|
| `"table"` | 原样透传列名和行数据 | 滞留车列表、缺陷汇总 |
| `"scalar"` | 取第一行第一列作为单值 | 计数类查询（"当前滞留车总数"） |
| `"chart"` | 需要场景定义 `chart_config` | 未来扩展 |

当前所有场景默认 `"table"`。

#### 4. `models.py` 变更

`ParameterDefinition` 新增字段：

```python
class ParameterDefinition(TypedDict):
    # ... 现有字段 ...
    widget: NotRequired[str]      # 显式控件类型，未指定时由 resolver 推断
```

`ScenarioSkill` 新增字段：

```python
class ScenarioSkill(TypedDict):
    # ... 现有字段 ...
    default_template: NotRequired[str]  # 直通路径默认 SQL 模板名称
    output_type: NotRequired[str]       # 输出格式，默认 "table"
```

#### 5. API 端点（`backend/app/api.py`）

API 层只做参数校验和模块编排，不包含业务逻辑：

```
GET  /api/scenarios                           → registry.get_domain_skills() + list_scenarios_by_skill()
GET  /api/scenarios/{domain}/{scenario}/params?template_name=xxx → resolver.resolve_params()
POST /api/scenarios/{domain}/{scenario}/execute → executor.execute_scenario() → formatter.format_result()
```

**`GET /api/scenarios`**

```json
[
  {
    "domain": "paint_shop_vehicle_logistics",
    "domain_title": "物流追踪",
    "scenarios": [
      {
        "name": "stranded_vehicle_detection",
        "title": "滞留车检测",
        "description": "车间滞留车辆信息查询与检测。"
      }
    ]
  }
]
```

**`GET /api/scenarios/{domain}/{scenario}/params?template_name=xxx`**

返回场景的参数定义，供前端渲染表单。支持可选的 `template_name` 查询参数：

- 当场景有多个 SQL 模板时，不同模板可能关联不同参数（如 `in_process` 需要 `in_process_stranded_days`，`historical` 需要 `stranded_days`）
- 若指定 `template_name`，只返回该模板关联的参数（参数名出现在该 SQL 模板的占位符中）
- 若未指定，使用 `default_template` 对应的参数集
- 响应中额外返回 `templates` 数组和 `default_template`，供前端渲染模板切换 Tabs

```json
{
  "name": "stranded_vehicle_detection",
  "title": "滞留车检测",
  "output_type": "table",
  "templates": [
    {"name": "in_process", "label": "在制滞留"},
    {"name": "historical", "label": "历史滞留"}
  ],
  "default_template": "in_process",
  "parameters": {
    "platform_filter": {
      "type": "string",
      "widget": "select",
      "description": "按平台筛选滞留车",
      "required": false,
      "default": "",
      "options": [
        {"value": "", "label": "不限"},
        {"value": "ADP", "label": "ADP"}
      ]
    },
    "stranded_days": {
      "type": "integer",
      "widget": "number",
      "description": "滞留天数阈值",
      "required": false,
      "default": 2
    }
  }
}
```

**`POST /api/scenarios/{domain}/{scenario}/execute`**

```json
// Request
{
  "params": { "platform_filter": "ADP", "stranded_days": "2" },
  "template_name": "in_process"
}

// Response (output_type="table")
{
  "type": "table",
  "columns": ["vehicle_id", "platform_code", "stranded_hours"],
  "rows": [
    ["V001", "ADP", 3.2],
    ["V002", "ADP", 2.1]
  ],
  "row_count": 2
}

// Response (output_type="scalar")
{
  "type": "scalar",
  "value": 12,
  "label": "当前滞留车总数"
}
```

### 6. 多步查询

当前所有场景的 SQL 模板均为单条 SELECT，不引入多步 pipeline。若未来有场景需要多步，方案是在 `scenario.py` 中新增合并后的 SQL 模板（用 CTE / 子查询），仍走单查询通道。

## Frontend

### 组件树与职责

```
ScenarioPanel.vue (容器/编排)
├── ScenarioList.vue (左侧场景列表)
│   └── 按领域分组，点击选中场景
├── ParameterForm.vue (通用参数表单)
│   └── 输入: ParameterDef[] → 输出: Record<string, string>
└── ResultRenderer.vue (结果分发器)
    ├── TableResult.vue (复用 DimensionTable)
    ├── ScalarResult.vue (单值展示)
    └── ChartResult.vue (未来扩展)
```

**组件间通信全部通过 store，组件之间零直接依赖。**

### 7. `ScenarioPanel.vue` — 容器组件 [NEW]

职责：布局编排 + 模板 Tab 切换 + 抽屉开关。不包含表单逻辑、不包含结果渲染逻辑。

```
┌──────────────────────────────────────────────────┐
│  ← 场景列表     │  滞留车检测            │  🔄 ✕  │
│──────────────────────────────────────────────────│
│                  │  [在制滞留|历史滞留]            │  ← 模板 Tabs（多模板场景）
│                  │  <ParameterForm />             │
│   <ScenarioList />│──────────────────────────────│
│                  │  <ResultRenderer />            │
│                  │                                │
└──────────────────────────────────────────────────┘
```

交互流程：
1. 打开抽屉 → `store.fetchScenarioList()`
2. 点击 ScenarioList 中的场景 → `store.selectScenario(domain, scenario)` → 自动加载参数 → 自动执行首次查询
3. 若场景有多个 SQL 模板（`templates.length > 1`），顶部渲染 Tab 切换条，默认选中 `default_template`
4. 切换 Tab → 重新加载该模板对应的参数 → 重新执行查询
5. ParameterForm 值变更 → `store.updateParams(params)` → 用户点击"查询" → `store.executeQuery()`
6. 点击"刷新" → `store.refresh()`（沿用当前参数和模板）
7. 点击"←" → 返回场景列表视图
8. 切换场景时保留各场景的**参数 + 模板**状态（store 按 key 缓存）

### 8. `ScenarioList.vue` — 场景列表 [NEW]

职责：展示场景树，发射选中事件。不依赖 ParameterForm 或 ResultRenderer。

Props: 无（数据从 store 读取）
Emits: `select(domain, scenario)`

```
┌──────────────────┐
│ 🔍 搜索场景...    │  ← 可选的搜索过滤
│──────────────────│
│ 物流追踪          │
│  ├ 滞留车检测  ✓  │
│  ├ 异常车监控     │
│  ├ 实时区域车数   │
│  ├ 每日区域车数   │
│  └ 车辆历史轨迹   │
│                  │
│ 缺陷分析          │
│  ├ 每日缺陷汇总   │
│  ├ 车型缺陷趋势   │
│  └ ...           │
└──────────────────┘
```

### 9. `ParameterForm.vue` — 通用参数表单 [NEW]

职责：根据 `ParameterDef` 渲染表单控件，输出参数键值对。**与场景完全解耦，可复用于任何动态表单场景。**

```
Props:  parameters: Record<string, ParameterDef>
        values: Record<string, string>       ← 当前值（双向绑定）
Emits:  update(params: Record<string, string>)
        submit()                              ← 点击"查询"
```

**控件映射（由 `widget` 字段决定，未指定时按 type 推断）：**

| `widget` | 渲染控件 | 适用场景 |
|----------|---------|---------|
| `"text"` | `<input type="text">` | 自由文本 |
| `"number"` | `<input type="number">` | 整数/小数 |
| `"select"` | `<select>` + 空选项"不限" | 有 source_table 的枚举 |
| `"multiselect"` | 多选标签组 | 数组类型 |
| `"date"` | `<input type="date">` | 未来扩展 |
| `"switch"` | 开关组件 | 未来扩展 |

控件渲染逻辑封装在 `widgets/` 子目录中，每个 widget 一个小组件，`ParameterForm` 根据 `widget` 字段动态选择。

```
components/
├── ParameterForm.vue          ← 表单容器，遍历 parameters 渲染子控件
├── widgets/
│   ├── TextWidget.vue         ← widget="text"
│   ├── NumberWidget.vue       ← widget="number"
│   ├── SelectWidget.vue       ← widget="select"
│   └── MultiSelectWidget.vue  ← widget="multiselect"
```

### 10. `ResultRenderer.vue` — 结果分发器 [NEW]

职责：根据 `output_type` 分发到对应的渲染组件。不关心数据从哪来。

```
Props:  result: ScenarioResult | null
        loading: boolean
        error: string | null
```

```
ResultRenderer.vue
  ├── loading → 骨架屏
  ├── error → 错误提示 + 重试按钮
  └── data →
        ├── type="table" → TableResult.vue
        ├── type="scalar" → ScalarResult.vue
        └── type="chart" → ChartResult.vue (未来)
```

**`TableResult.vue`** — 复用 `DimensionTable` 组件，传入 `columns` + `rows`。双击单元格支持注入到聊天输入框（复用现有 `dblclick-cell` 机制）。

**`ScalarResult.vue`** — 大数字 + 标签展示，用于计数类结果。

### 11. `scenarioPanel.ts` Store [NEW]

```typescript
export const useScenarioPanelStore = defineStore('scenarioPanel', () => {
  // 抽屉状态
  const visible = ref(false)
  const view = ref<'list' | 'detail'>('list')  // 场景列表 or 场景详情

  // 场景列表
  const scenarios = ref<ScenarioSummary[]>([])
  const selectedDomain = ref<string | null>(null)
  const selectedScenario = ref<string | null>(null)

  // 参数
  const paramDefs = ref<Record<string, ParameterDef>>({})
  // 按 "domain/scenario" 缓存参数值，切换场景时保留
  const paramCache = ref<Record<string, Record<string, string>>>({})

  // 结果
  const result = ref<ScenarioResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // actions
  async function fetchScenarioList() { ... }
  async function selectScenario(domain: string, scenario: string) { ... }
  async function executeQuery() { ... }
  async function refresh() { ... }
  function updateParams(params: Record<string, string>) { ... }
  function open(targetDomain?: string, targetScenario?: string) { ... }
  function close() { ... }
})
```

### 12. `api/scenarios.ts` [NEW]

```typescript
export interface ScenarioSummary {
  domain: string
  domain_title: string
  scenarios: { name: string; title: string; description: string }[]
}

export interface ParameterDef {
  type: string
  widget: string
  description: string
  required: boolean
  default: string | null
  options?: { value: string; label: string }[]
}

export interface TemplateInfo {
  name: string
  label: string
}

export interface ScenarioParams {
  name: string
  title: string
  output_type: string
  templates?: TemplateInfo[]        // 多模板场景的 Tab 列表
  default_template?: string         // 默认模板
  parameters: Record<string, ParameterDef>
}

export interface TableResult {
  type: 'table'
  columns: string[]
  rows: (string | number)[][]
  row_count: number
}

export interface ScalarResult {
  type: 'scalar'
  value: number | string
  label: string
}

export type ScenarioResult = TableResult | ScalarResult

export function getScenariosApi(): Promise<ScenarioSummary[]>
export function getScenarioParamsApi(domain: string, scenario: string): Promise<ScenarioParams>
export function executeScenarioApi(
  domain: string, scenario: string,
  params: Record<string, string>, templateName?: string
): Promise<ScenarioResult>
```

### 13. 现有组件变更

**VariantB.vue：**
- 新增 `showScenarioPanel` prop 和 `toggle-scenario-panel` emit
- 新增 ScenarioPanel 抽屉（与 Bento 抽屉互斥，同时只显示一个）
- 复用现有 slide-over 抽屉结构和动画

**WelcomeDashboard.vue：**
- 每个场景卡片增加"快速查看"按钮
- 点击 → emit `quick-view(domain, scenario)` → ChatView 打开 ScenarioPanel

**ChatView.vue：**
- header 增加"快捷场景"按钮
- 新增 `showScenarioPanel` 状态
- 处理 WelcomeDashboard 的 `quick-view` 事件

## Scope 汇总

| 文件 | 变更类型 | 职责 |
|------|----------|------|
| `backend/app/skills/resolver.py` | **NEW** | 参数解析 + 默认值 + source_table 选项 |
| `backend/app/skills/executor.py` | **NEW** | SQL 模板加载 + 参数替换 + 执行 |
| `backend/app/skills/formatter.py` | **NEW** | 按 output_type 格式化结果 |
| `backend/app/skills/models.py` | 修改 | `widget` / `output_type` / `default_template` 字段 |
| `backend/app/api.py` | 修改 | 3 个 API 端点（纯编排，无业务逻辑） |
| `backend/app/schemas.py` | 修改 | Pydantic v2 响应模型 |
| `stranded_vehicle_detection/scenario.py` | 修改 | `sql_fragment` 中 INTERVAL 改为 `make_interval(days => ...)` 兼容 bindparam |
| 各场景 `scenario.py` | 按需修改 | 补充 `default_template` |
| `frontend/src/api/scenarios.ts` | **NEW** | API 调用层 |
| `frontend/src/stores/scenarioPanel.ts` | **NEW** | 状态管理 |
| `frontend/src/components/ScenarioPanel.vue` | **NEW** | 抽屉容器/编排 |
| `frontend/src/components/ScenarioList.vue` | **NEW** | 场景列表 |
| `frontend/src/components/ParameterForm.vue` | **NEW** | 通用参数表单 |
| `frontend/src/components/widgets/*.vue` | **NEW** | 表单控件组件 |
| `frontend/src/components/ResultRenderer.vue` | **NEW** | 结果分发器 |
| `frontend/src/components/TableResult.vue` | **NEW** | 表格结果（复用 DimensionTable） |
| `frontend/src/components/ScalarResult.vue` | **NEW** | 标量结果 |
| `frontend/src/components/VariantB.vue` | 修改 | 集成抽屉 |
| `frontend/src/components/WelcomeDashboard.vue` | 修改 | 快速查看按钮 |
| `frontend/src/views/ChatView.vue` | 修改 | header 按钮 + 事件连线 |

## Implementation Order

1. 后端 models 扩展（`widget` / `output_type` / `default_template`）
2. `resolver.py` — 参数解析（含 source_table 白名单、多列降级）
3. `executor.py` — SQL 执行（含 INTERVAL 表达式改造、空值剔除）
4. `formatter.py` — 结果格式化
5. 各场景 `scenario.py` — 补充 `default_template`，修正 `sql_fragment` INTERVAL 用法
6. `schemas.py` — 定义 Pydantic v2 响应模型
7. `api.py` — 3 个 API 端点
8. 前端 API 层 + Store
9. 前端原子组件（widgets → ParameterForm → ResultRenderer 子组件）
10. 前端容器组件（ScenarioList → ScenarioPanel）
11. 现有组件集成（VariantB → WelcomeDashboard → ChatView）

## Project Conventions

### Pydantic v2 Response Schemas

遵循项目约定，在 `backend/app/schemas.py` 中定义 API 响应模型（如未存在则新建）：

```python
from pydantic import BaseModel, ConfigDict

class ScenarioSummary(BaseModel):
    domain: str
    domain_title: str
    scenarios: list[ScenarioItem]

class ScenarioItem(BaseModel):
    name: str
    title: str
    description: str

class ScenarioParamsResponse(BaseModel):
    name: str
    title: str
    output_type: str
    templates: list[TemplateInfo] | None = None
    default_template: str | None = None
    parameters: dict[str, ParameterDefSchema]

    model_config = ConfigDict(from_attributes=True)

# 执行请求/响应模型同理
```

API 端点通过 `response_model` 声明返回类型。

### 前端规范

- 使用 `<script setup>` + Pinia Setup Store 风格
- Store 内 ref 直接使用，不额外加 `.value`
- 表单控件和抽屉图标使用项目已有 Icon 库，不引用公网 CDN
- 组件间全部通过 store 通信，零直接依赖

## Testing

- **后端单测**：resolver 参数解析 / executor 参数替换、占位符清理、SQL 注入防护 / formatter 各 output_type 输出
- **前端验证**：抽屉打开/关闭、场景切换、参数表单各 widget 渲染、查询执行、刷新、error 状态