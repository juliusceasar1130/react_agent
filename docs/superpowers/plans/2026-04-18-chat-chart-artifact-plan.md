# Chat Chart Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有聊天式 SQL Agent 中新增“用户明确要求后再生成图表”的能力，并确保大数据不重复进入 LLM 上下文。

**Architecture:** 采用“LLM 只决策图表意图，后端工具生成并存储 chart artifact，前端按 artifact 渲染”的路径。第一阶段不改造 `sql_db_query` 的返回协议，而是新增一个可重复执行聚合 SQL 的图表工具，返回给 LLM 轻量 `chart_ref`，再由前端通过 `chart_id` 拉取完整 `chart_spec`。

**Tech Stack:** FastAPI, LangChain/LangGraph agent tools, SQLAlchemy, Vue 3, Pinia, SSE, Apache ECharts

---

## Recommended Path

### Chosen Approach: Artifact-Ref Chart Flow

```text
用户明确要求生成图表
    ->
LLM 判断图型与字段
    ->
build_chart_artifact 工具执行聚合 SQL
    ->
后端存储完整 chart_spec，返回 chart_ref 给 LLM
    ->
assistant 最终文本 + chart_ref 落库
    ->
前端根据 chart_id 拉取完整 chart_spec
    ->
ECharts 渲染图表卡片
```

**Why this path**
- 复用当前 `tool_call` / `tool_result` / `final` 流式协议，不引入第二条聊天链路。
- 避免把大 `rows` 再回流给 LLM，控制上下文体积。
- 与现有 `export_to_csv -> file_id -> 前端下载` 模式一致，便于复用维护经验。

### Rejected Approach A: 直接把完整 `chart_spec + rows` 作为工具返回

**Why reject**
- 工具返回会进入 `ToolMessage.content`，在当前 agent loop 中会回流给模型。
- 大 `rows` 会重复进入上下文与 `tool_results` 持久化，增加 token 与存储压力。

### Deferred Approach B: 完整 Vanna 风格 `query_result_id -> chart_id` 两级 artifact

**Why defer**
- 需要显著改造 `sql_db_query` 协议，让它稳定返回结构化 `query_result_ref`。
- 当前 `sql_db_query` 直接向模型返回字符串结果，改造风险比新增图表工具更高。
- 可作为第二阶段优化，在第一阶段功能稳定后再推进。

---

## Scope Boundaries

- 第一阶段只在“用户明确要求生成图表”时生成，不自动生成图表。
- 第一阶段只支持聚合型图表，不支持原始明细大表直接绘图。
- 第一阶段只支持 `line`、`bar` 两种图型。
- 第一阶段最多支持双 Y 轴，不支持自定义 formatter / HTML tooltip / 任意 JS。
- 第一阶段前端只在消息卡片内展示图表，不做独立报表页。

---

## File Structure

- Create: `backend/app/chart_artifacts.py`
  - 负责 `chart_id` 生成、chart spec 落盘、读取、过期控制。
- Create: `backend/app/agent/tools/chart_artifact_tool.py`
  - 负责校验图表请求、执行 SQL、生成并存储 chart artifact、向 LLM 返回轻量 `chart_ref`。
- Modify: `backend/app/agent/tools/__init__.py`
  - 导出新图表工具工厂。
- Modify: `backend/app/agent/service.py`
  - 注入图表工具，补系统提示词中“何时提醒、何时调用图表工具”的规则。
- Modify: `backend/app/api.py`
  - 新增 `GET /api/chat/charts/{chart_id}`，供前端读取完整图表 artifact。
- Modify: `backend/app/schemas.py`
  - 新增图表 artifact 响应模型与轻量 ref 模型。
- Modify: `backend/app/config.py`
  - 新增图表 artifact 目录与 TTL 配置。
- Create: `backend/app/test_chart_artifacts.py`
  - 覆盖 chart artifact 存取、ID 校验、过期与路径安全。
- Create: `backend/app/test_chart_artifact_tool.py`
  - 覆盖图表工具参数校验、技能校验、行数限制、轻量返回值格式。
- Create: `frontend/src/api/charts.ts`
  - 提供 `chart_id -> chart_spec` 的读取 API。
- Create: `frontend/src/components/ChartArtifactCard.vue`
  - 根据 `chart_id` 拉取并渲染完整图表。
- Modify: `frontend/src/types/index.ts`
  - 新增 `ChartArtifactRef`、`ChartArtifact` 类型。
- Modify: `frontend/src/components/MessageItem.vue`
  - 识别图表工具结果，渲染图表卡片。
- Modify: `frontend/package.json`
  - 新增 `echarts` 依赖。

---

## Unclear Items To Resolve Before Coding

1. 图表工具是否在第一阶段允许 LLM 传入 `chart_type=auto`
   - 已确认：允许。
   - 工具内部按字段形态兜底为 `line` 或 `bar`。

2. 图表 artifact 是否复用现有 `export_files.py`
   - 推荐：不直接复用。
   - 原因：`export_files.py` 当前强绑定 `file_export` 语义与文件下载；图表更适合独立 `chart_artifacts.py`，减少副作用。

3. 用户跨轮要求“把刚才结果画成图”时是否重跑 SQL
   - 已确认：第一阶段允许重跑聚合 SQL。
   - 原因：不改现有 `sql_db_query` 协议，保持最小改动。

4. 图表点数上限
   - 已确认：默认 `100`。
   - 必须支持通过环境变量配置，例如 `CHART_ARTIFACT_MAX_POINTS`。
   - 超过则拒绝生成并提示先聚合。

5. 图表 artifact 是否需要像 CSV 一样设置过期时间
   - 已确认：需要，默认 `24h`。
   - 必须支持通过环境变量配置，例如 `CHART_ARTIFACT_TTL_HOURS`。
   - 便于清理临时工件，避免无限增长。

6. 是否需要首版支持“下载图片/导出 PNG”
   - 推荐：第一阶段不做，只做聊天内嵌渲染。

---

### Task 1: Define Chart Artifact Contract and Storage

**Files:**
- Create: `backend/app/chart_artifacts.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/app/test_chart_artifacts.py`

- [ ] **Step 1: Write the failing backend artifact tests**

```python
from backend.app.chart_artifacts import create_chart_record, get_chart_record


def test_create_chart_record_returns_chart_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_ARTIFACT_DIR", str(tmp_path))
    record = create_chart_record(
        payload={
            "kind": "chart_spec",
            "chart_type": "line",
            "title": "demo",
            "x_field": "stat_date",
            "series": [{"name": "count", "field": "detection_count", "y_axis": "left"}],
            "rows": [{"stat_date": "2026-04-01", "detection_count": 1}],
        }
    )
    assert record["kind"] == "chart_artifact_ref"
    assert record["chart_id"].startswith("cht_")


def test_get_chart_record_returns_full_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_ARTIFACT_DIR", str(tmp_path))
    created = create_chart_record(
        payload={
            "kind": "chart_spec",
            "chart_type": "bar",
            "title": "demo",
            "x_field": "model",
            "series": [{"name": "count", "field": "detection_count", "y_axis": "left"}],
            "rows": [{"model": "A", "detection_count": 10}],
        }
    )
    payload = get_chart_record(created["chart_id"])
    assert payload["kind"] == "chart_spec"
    assert payload["rows"][0]["detection_count"] == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda activate py312_agent; python -m pytest -p no:cacheprovider backend/app/test_chart_artifacts.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing function errors for `chart_artifacts`.

- [ ] **Step 3: Implement minimal chart artifact storage**

```python
# backend/app/chart_artifacts.py
CHART_ID_PATTERN = re.compile(r"^cht_[a-f0-9]{32}$")


def create_chart_record(*, payload: dict[str, Any]) -> dict[str, Any]:
    chart_id = f"cht_{uuid4().hex}"
    # persist full payload to <chart_id>.json
    # return lightweight ref only
    return {
        "kind": "chart_artifact_ref",
        "chart_id": chart_id,
        "chart_type": payload["chart_type"],
        "title": payload["title"],
        "point_count": len(payload["rows"]),
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
```

- [ ] **Step 4: Add config and schema support**

```python
# backend/app/config.py
chart_artifact_dir: str = os.getenv(
    "CHART_ARTIFACT_DIR",
    str(Path(tempfile.gettempdir()) / "sql_agent_charts"),
)
chart_artifact_ttl_hours: int = int(os.getenv("CHART_ARTIFACT_TTL_HOURS", "24"))
chart_artifact_max_points: int = int(os.getenv("CHART_ARTIFACT_MAX_POINTS", "100"))
```

```python
# backend/app/schemas.py
class ChartArtifactRef(BaseModel):
    kind: Literal["chart_artifact_ref"]
    chart_id: str
    chart_type: Literal["line", "bar"]
    title: str
    point_count: int
    created_at: datetime
    expires_at: datetime


class ChartArtifactResponse(BaseModel):
    kind: Literal["chart_spec"]
    chart_type: Literal["line", "bar"]
    title: str
    description: str | None = None
    x_field: str
    series: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda activate py312_agent; python -m pytest -p no:cacheprovider backend/app/test_chart_artifacts.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/chart_artifacts.py backend/app/config.py backend/app/schemas.py backend/app/test_chart_artifacts.py
git commit -m "feat: add chart artifact storage"
```

### Task 2: Add Chart Generation Tool with Compact LLM Return

**Files:**
- Create: `backend/app/agent/tools/chart_artifact_tool.py`
- Modify: `backend/app/agent/tools/__init__.py`
- Test: `backend/app/test_chart_artifact_tool.py`

- [ ] **Step 1: Write the failing tool tests**

```python
from types import SimpleNamespace

from backend.app.agent.tools.chart_artifact_tool import create_chart_artifact_tool


def test_chart_tool_requires_loaded_skill():
    tool = create_chart_artifact_tool("sqlite:///")
    runtime = SimpleNamespace(state={"skills_loaded": []})
    result = tool.invoke(
        {
            "query": "SELECT 1 AS x, 2 AS y",
            "required_skill": "paint_shop_defect_analysis",
            "chart_type": "line",
            "title": "demo",
            "description": "demo",
            "x_field": "x",
            "series": [{"name": "y", "field": "y", "y_axis": "left"}],
            "runtime": runtime,
        }
    )
    assert "请先使用 load_skill" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda activate py312_agent; python -m pytest -p no:cacheprovider backend/app/test_chart_artifact_tool.py -v`
Expected: FAIL because the tool module does not exist.

- [ ] **Step 3: Implement minimal chart tool**

```python
# backend/app/agent/tools/chart_artifact_tool.py
@langchain_tool
def build_chart_artifact(
    query: str,
    required_skill: str,
    chart_type: str,
    title: str,
    description: str,
    x_field: str,
    series: list[dict[str, Any]],
    runtime: ToolRuntime,
) -> str:
    # validate SQL safety and loaded skill
    # run query with include_columns=True
    # validate x_field and series fields
    # enforce row/series limits
    # store full chart_spec
    # return lightweight chart_artifact_ref JSON string
```

- [ ] **Step 4: Enforce the no-large-payload rule**

```python
if len(rows) > settings.chart_artifact_max_points:
    return (
        "Error: 图表点数超过上限，当前结果不适合直接绘图。"
        "请先聚合、缩小时间范围，或继续使用 export_to_csv。"
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda activate py312_agent; python -m pytest -p no:cacheprovider backend/app/test_chart_artifact_tool.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/tools/chart_artifact_tool.py backend/app/agent/tools/__init__.py backend/app/test_chart_artifact_tool.py
git commit -m "feat: add chart artifact tool"
```

### Task 3: Wire the Tool into the Agent and API

**Files:**
- Modify: `backend/app/agent/service.py`
- Modify: `backend/app/api.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/app/test_chart_api.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_get_chart_endpoint_returns_chart_payload(client, chart_record):
    response = client.get(f"/api/chat/charts/{chart_record['chart_id']}")
    assert response.status_code == 200
    assert response.json()["kind"] == "chart_spec"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda activate py312_agent; python -m pytest -p no:cacheprovider backend/app/test_chart_api.py -v`
Expected: FAIL with 404 or missing endpoint.

- [ ] **Step 3: Register tool and prompt rules**

```python
# backend/app/agent/service.py
chart_tool = create_chart_artifact_tool(
    business_db_url,
    engine_args=_get_business_database_engine_args(business_db_url),
)
tools.append(chart_tool)
```

```text
- 当结果适合可视化但用户未明确要求时，只提醒可继续生成图表。
- 当用户明确要求生成图表时，优先调用 build_chart_artifact。
- build_chart_artifact 返回给你的只是轻量 chart_ref，不要期待工具返回全部 rows。
```

- [ ] **Step 4: Add chart artifact fetch endpoint**

```python
@router.get("/charts/{chart_id}", response_model=ChartArtifactResponse)
def get_chart_artifact(chart_id: str):
    return get_chart_record(chart_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda activate py312_agent; python -m pytest -p no:cacheprovider backend/app/test_chart_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/service.py backend/app/api.py backend/app/schemas.py backend/app/test_chart_api.py
git commit -m "feat: expose chart artifact api"
```

### Task 4: Render Chart Artifacts on the Frontend

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/api/charts.ts`
- Create: `frontend/src/components/ChartArtifactCard.vue`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/MessageItem.vue`

- [ ] **Step 1: Add the chart dependency**

```json
{
  "dependencies": {
    "echarts": "^5.5.0"
  }
}
```

- [ ] **Step 2: Add chart artifact types and API**

```ts
// frontend/src/types/index.ts
export interface ChartArtifactRef {
  kind: 'chart_artifact_ref'
  chart_id: string
  chart_type: 'line' | 'bar'
  title: string
  point_count: number
  created_at?: string
  expires_at?: string
  message?: string
}

export interface ChartArtifact {
  kind: 'chart_spec'
  chart_type: 'line' | 'bar'
  title: string
  description?: string
  x_field: string
  series: Array<{ name: string; field: string; y_axis: 'left' | 'right' }>
  rows: Array<Record<string, string | number | null>>
}
```

```ts
// frontend/src/api/charts.ts
export const getChartArtifactApi = (chartId: string): Promise<ChartArtifact> =>
  api.get(`/api/chat/charts/${chartId}`)
```

- [ ] **Step 3: Render chart cards**

```vue
<!-- frontend/src/components/ChartArtifactCard.vue -->
<template>
  <div class="rounded-2xl border border-sky-200 bg-white p-4">
    <div class="text-sm font-semibold text-sky-900">{{ artifact?.title ?? title }}</div>
    <div ref="chartRef" class="mt-3 h-72 w-full"></div>
  </div>
</template>
```

- [ ] **Step 4: Integrate with MessageItem**

```ts
const chartArtifacts = computed<ChartArtifactRef[]>(() => {
  return toolCallList.value.flatMap((tool) => {
    if (tool.name !== 'build_chart_artifact') return []
    const parsed = parseJson<ChartArtifactRef>(rawToolResults.value[tool.id])
    return parsed?.kind === 'chart_artifact_ref' ? [parsed] : []
  })
})
```

- [ ] **Step 5: Verify frontend build**

Run: `npm --prefix frontend run build:check`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/src/api/charts.ts frontend/src/components/ChartArtifactCard.vue frontend/src/types/index.ts frontend/src/components/MessageItem.vue
git commit -m "feat: render chart artifacts in chat"
```

### Task 5: Add Integration Verification and Documentation

**Files:**
- Modify: `changelog.md`
- Optional Modify: `README.md`

- [ ] **Step 1: Verify backend test suite for touched areas**

Run: `conda activate py312_agent; python -m pytest -p no:cacheprovider backend/app/test_skill_registry.py backend/app/test_chart_artifacts.py backend/app/test_chart_artifact_tool.py backend/app/test_chart_api.py -v`
Expected: PASS

- [ ] **Step 2: Verify frontend type/build check**

Run: `npm --prefix frontend run build:check`
Expected: PASS

- [ ] **Step 3: Document the feature**

```markdown
## 2026-04-18 xx:xx - 新增聊天图表 artifact 渲染链路
- 新增 build_chart_artifact 工具
- 新增 chart_id -> chart_spec 读取接口
- 前端支持在消息卡片中渲染 line / bar 图表
- 图表工具返回轻量 chart_ref，不再把大 rows 回流给 LLM
```

- [ ] **Step 4: Commit**

```bash
git add changelog.md README.md
git commit -m "docs: describe chart artifact flow"
```

---

## Phase 2 (Optional Optimization After MVP)

- 将 `sql_db_query` 升级为可选输出 `query_result_ref`
- 新增 `visualize_query_result(source_id, ...)`
- 避免“刚查完又重跑一次 SQL” 的重复开销
- 仅在 MVP 跑通、交互确认有效后再评估是否值得推进

---

## Self-Review

- Spec coverage: 覆盖了图表工具、artifact 存储、后端读取接口、前端渲染、验证与文档更新。
- Placeholder scan: 无 `TODO/TBD` 占位；未落定项已集中列在 “Unclear Items”。
- Type consistency: 统一采用 `chart_artifact_ref` 与 `chart_spec` 两级结构；第一阶段不引入 `query_result_ref`，避免命名混乱。

---

Plan complete and saved to `docs/superpowers/plans/2026-04-18-chat-chart-artifact-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
