# Build Chart Artifact 侧信道交付改造实施方案 (MVP 简化版)

> **日期**：2026-07-20  
> **状态**：待实施  
> **前置依赖**：`04_single_tool_query_result_decoupling.md`（`sql_db_query` Command + tool_artifact 模式已落地）  
> **目标**：将 `build_chart_artifact` 在实时生成阶段由"写磁盘 → 前端二次 HTTP 拉取"改为 Command + tool_artifact 侧信道直推，消除新图表渲染的端到端延迟；同时在历史会话回溯中，维持既有的 "HTTP 延迟懒加载" 以保持架构轻量，不改动数据库表结构与 `_last_wins` 机制。

---

## 一、 方案取舍与 MVP 设计

本方案旨在平衡“首屏极速渲染”与“系统架构复杂性”，通过**双轨制通道**实现改动面最小、抗震度最高的交付：

1. **实时流式阶段（新对话）**：工具通过返回 `Command` 包含 `tool_artifact` (kind: `chart_spec`)，直接进入服务端 SSE 广播队列。前端长连接捕获后**零延迟直渲**，不需要等待 LLM 最终回复，也不产生二次 HTTP 网络开销。
2. **历史会话阶段（回溯/刷新）**：工具仍然调用 `create_chart_record` 将图表 spec 写入临时磁盘，并在返回给 LLM 的 `ToolMessage` 消息正文（`content`）中写入 `chart_artifact_ref` JSON（大小仅 100 字节，不对 LLM 上下文构成压力）。
   * 前端刷新后拉取历史消息时，从 `tool_results` 字段中解析出 `chart_id`。
   * `<ChartArtifactCard>` 按需发起 `GET /api/chat/charts/{chart_id}` 异步拉取渲染。

### 核心收益
* ❌ **不修改** 物理数据库 Schema，无需 DDL 变更。
* ❌ **不改动** `api.py` 的同步/异步双通道落库处理逻辑。
* ❌ **不破坏** `state.py` 的 `_last_wins` reducer 机制，完全规避“图表将同一轮的 SQL 预览表格挤掉”的 bug。
* 🤝 **完美对齐** 04 方案中“`tool_artifact` 纯流式临时态，历史回退依靠 `tool_results`”的既定设计，保持架构一致性。

---

## 二、 改造范围

| 层 | 变更文件 | 说明 |
|---|---|---|
| **后端** | `chart_artifact_tool.py` | 工具改为返回 `Command`。同时携带 `tool_artifact`（用于实时 SSE 直推）与 `ToolMessage.content` 中的 `chart_artifact_ref`（用于历史回溯） |
| **前端** | `MessageItem.vue` | 1. 拆分并过滤 `sqlQueryResult` 防止 SQL 表格污染。<br/>2. 针对流式阶段的新图表支持传入 `chartSpec` 进行直推分发。 |
| **前端** | `ChartArtifactCard.vue` | 1. 声明可选 prop `chartPayload`。<br/>2. 采用防空 `computed` 封装展示字段，防御流式阶段 `artifactRef` 缺失导致的空指针异常。 |
| **后端** | `services.py` / `api.py` | **无需改动**（SSE 转发及历史消息获取保持既有逻辑） |

---

## 三、 详细实施步骤

### Task 1: 改造 `build_chart_artifact` 返回 Command 且保留历史引用

**Files:**
- Modify: `backend/app/agent/tools/chart_artifact_tool.py`
- Test: `backend/app/agent/tools/test_chart_artifact_command.py` (新建)

- [ ] **Step 1: 编写单元测试**
  新建 `backend/app/agent/tools/test_chart_artifact_command.py`，验证工具同时返回 `Command` 且 `ToolMessage` 中依然包含回溯 JSON：
  ```python
  import pytest
  from unittest.mock import MagicMock
  from langgraph.types import Command

  def test_build_chart_artifact_mvp_returns():
      from backend.app.agent.tools.chart_artifact_tool import create_chart_artifact_tool

      engine = MagicMock()
      mock_conn = MagicMock()
      mock_conn.__enter__ = MagicMock(return_value=mock_conn)
      mock_conn.__exit__ = MagicMock(return_value=False)
      # 确保 dict(row) 可用：使用字典数据结构模拟 mappings
      mock_row = {"detection_date": "2026-01", "defect_count": 10}
      mock_conn.execute.return_value.mappings.return_value.all.return_value = [
          mock_row
      ]
      engine.connect.return_value = mock_conn

      tool = create_chart_artifact_tool(engine)
      result = tool.invoke({
          "query": "SELECT detection_date, defect_count FROM t",
          "required_skill": "test_skill",
          "chart_type": "line",
          "title": "缺陷趋势",
          "description": "",
          "x_field": "detection_date",
          "series": [{"name": "缺陷数", "field": "defect_count"}],
      })

      # 验证 Command 结构
      assert isinstance(result, Command)
      assert "messages" in result.update
      assert "tool_artifact" in result.update

      # 验证流式 Payload
      artifact = result.update["tool_artifact"]
      assert artifact["kind"] == "chart_spec"
      assert artifact["title"] == "缺陷趋势"
      assert "rows" in artifact

      # 验证历史回溯用 ToolMessage 格式 (必须包含 chart_artifact_ref 鸭子守卫)
      msg = result.update["messages"][0]
      import json
      parsed_ref = json.loads(msg.content)
      assert parsed_ref["kind"] == "chart_artifact_ref"
      assert "chart_id" in parsed_ref
  ```

- [ ] **Step 2: 运行测试验证失败**
  ```bash
  pytest backend/app/agent/tools/test_chart_artifact_command.py -v
  ```

- [ ] **Step 3: 修改 `chart_artifact_tool.py`**
  ```python
  # 导入 Command 与 ToolMessage
  from langgraph.types import Command
  from langchain_core.messages import ToolMessage
  ```
  在完成 `payload` 构造后，保持磁盘缓存调用并使用 `Command` 返回：
  ```python
            payload = {
                "kind": "chart_spec",
                "chart_type": resolved_chart_type,
                "title": title,
                "description": description,
                "x_field": x_field,
                "series": normalized_series,
                "rows": rows,
            }
            
            # 保留磁盘写入，生成供历史回溯用的引用 JSON (含 chart_id)
            chart_ref = create_chart_record(payload=payload)

            emit_stream_status(
                "图表已生成",
                stage="writing",
                source="build_chart_artifact",
            )

            # 同时返回：
            # 1. messages：大模型接收的轻量 JSON Ref (同时持久化进 tool_results)
            # 2. tool_artifact：前端实时直推的完整 spec
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=json.dumps(chart_ref, ensure_ascii=False),
                        tool_call_id=str(runtime.tool_call_id) if runtime and hasattr(runtime, "tool_call_id") else "call_unknown",
                    )
                ],
                "tool_artifact": {
                    "kind": "chart_spec",
                    "chart_id": chart_ref["chart_id"],  # 使用磁盘分配的统一寻址 ID
                    "chart_type": resolved_chart_type,
                    "title": title,
                    "description": description,
                    "x_field": x_field,
                    "series": normalized_series,
                    "rows": rows,
                },
            })
  ```

---

### Task 2: 前端适配双轨制展示与防灾处理

**Files:**
- Modify: `frontend/src/components/MessageItem.vue`
- Modify: `frontend/src/components/ChartArtifactCard.vue`

- [ ] **Step 1: 隔离 `MessageItem.vue` 计算属性，防止表格污染**
  在 `MessageItem.vue` 中定义 `sqlQueryResult` 与 `chartSpec`：
  ```typescript
  // 判断实时侧信道推送的 tool_artifact 是否为 chart_spec
  const chartSpec = computed(() => {
    const artifact = queryResult.value
    if (artifact && artifact.kind === 'chart_spec') {
      return artifact
    }
    return null
  })

  // 仅在 kind === 'query_result'，或者具有 columns 时作为表格渲染数据，过滤掉图表
  const sqlQueryResult = computed(() => {
    const artifact = queryResult.value
    if (artifact && (artifact.kind === 'query_result' || (!artifact.kind && artifact.columns))) {
      return artifact
    }
    return null
  })
  ```
  在模板中，修改表格预览的判断为 `v-if="!isUser && sqlQueryResult"`，并加入图表直推区（优先于旧的 chartArtifacts 列表）：
  ```html
  <!-- 智能 SQL 数据预览表格模块 (防冲突修改) -->
  <div v-if="!isUser && sqlQueryResult" class="mt-3 px-4 pb-3 text-left animate-fade-in">
    <!-- ... -->
  </div>

  <!-- 新机制：侧信道直达的图表，无需二次 HTTP (流式渲染优先) -->
  <div v-if="chartSpec" class="space-y-3 px-4 pb-3">
    <ChartArtifactCard :chart-payload="chartSpec" />
  </div>

  <!-- 旧机制：历史消息懒加载 (兼容刷新及历史对话) -->
  <div v-else-if="!isUser && chartArtifacts.length > 0" class="space-y-3 px-4 pb-3">
    <ChartArtifactCard
      v-for="artifact in chartArtifacts"
      :key="artifact.chart_id"
      :artifact-ref="artifact"
    />
  </div>
  ```

- [ ] **Step 2: 对 `ChartArtifactCard.vue` 做防空保护**
  为防御流式渲染阶段 `artifactRef` 必为 `undefined` 的风险，通过 `computed` 进行属性包装：
  ```typescript
  interface Props {
    artifactRef?: ChartArtifactRef   // 历史消息异步拉取用
    chartPayload?: ChartArtifact     // 实时侧信道直传用
  }

  const props = defineProps<Props>()

  const displayTitle = computed(() => artifact.value?.title ?? props.artifactRef?.title ?? '')
  const displayDescription = computed(() => artifact.value?.description ?? '')
  const displayChartType = computed(() => artifact.value?.chart_type ?? props.artifactRef?.chart_type ?? 'line')
  const displayPointCount = computed(() => artifact.value?.rows?.length ?? props.artifactRef?.point_count ?? 0)
  const displayExpiresAt = computed(() => artifact.value?.expires_at ?? props.artifactRef?.expires_at ?? '')
  ```
  在组件模板中绑定：
  ```html
  <div class="text-sm font-semibold text-slate-900">{{ displayTitle }}</div>
  <div v-if="displayDescription" class="mt-1 text-xs leading-5 text-slate-600">{{ displayDescription }}</div>
  <div class="mt-1 text-xs leading-5 text-slate-600">
    {{ displayChartType === 'line' ? '折线图' : '柱状图' }} · {{ displayPointCount }} 个点
  </div>
  ```
  并重构加载逻辑，监听 `chart_id` 变化：
  ```typescript
  const loadArtifact = async () => {
    chartInstance?.dispose()
    chartInstance = null
    artifact.value = null
    loading.value = true
    error.value = null
    try {
      if (props.chartPayload) {
        artifact.value = props.chartPayload
      } else if (props.artifactRef) {
        artifact.value = await getChartArtifactApi(props.artifactRef.chart_id)
      } else {
        throw new Error('未提供图表数据或引用')
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '图表加载失败'
    } finally {
      loading.value = false
    }
    await renderChart()
  }

  watch(() => props.chartPayload?.chart_id ?? props.artifactRef?.chart_id, () => {
    void loadArtifact()
  })
  ```

---

## 四、 风险与限制

1. **`_last_wins` 覆盖风险（已规避）**：由于未将 `tool_artifact` 字段进行物理落库，图表与表格的共存关系依然依靠 `tool_results` 中的历史消息独立解析恢复，完美避免了同一轮中 SQL 预览表格被图表在 state 中强行覆盖的问题。
2. **磁盘垃圾清理**：历史会话中图表仍依赖本地磁盘文件缓存，需关注 `CHART_ARTIFACT_TTL_HOURS` 配置是否合理。

---

## 五、 验证清单

- [ ] 新对话中要求生成图表，前端长连接实时接收图表数据并完成首屏渲染。
- [ ] 检查 Network 面板，图表生成时**无任何针对 `/api/chat/charts/` 接口的 HTTP GET 请求**。
- [ ] 连续生成图表和 SQL 数据，验证下方的 SQL 预览表格展示正常，无 UI 被图表覆盖或挤压。
- [ ] 手动刷新浏览器或切换至历史会话，验证历史图表能够通过 HTTP 回退路径正常懒加载出来。
- [ ] 运行 `pytest backend/app/agent/tools/test_chart_artifact_command.py` 通过。
