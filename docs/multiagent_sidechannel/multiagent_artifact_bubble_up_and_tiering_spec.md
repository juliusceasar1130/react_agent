# 多智能体工件分级治理与主气泡透出（Artifact Bubble-Up & Tiering）技术规范

> **规范版本**：v1.1 (权威终版 · 经 Claude Code 联合复审、LobeHub 架构对比与去过度设计收敛)  
> **文档位置**：`docs/multiagent_sidechannel/multiagent_artifact_bubble_up_and_tiering_spec.md`  
> **归属专区**：`docs/multiagent_sidechannel/`（多智能体侧信道与工件体系架构知识库）  
> **关联文档**：
> - 综合研究报告：[`multiagent_artifact_architecture_and_presentation_research_report.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/multiagent_sidechannel/multiagent_artifact_architecture_and_presentation_research_report.md)
> - RFC 提案：[`artifact_presentation_and_bubble_elevation_rfc.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/multiagent_sidechannel/artifact_presentation_and_bubble_elevation_rfc.md)
> - 架构审查总纲：[`multiagent_tool_sidechannel_audit_report.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/multiagent_sidechannel/multiagent_tool_sidechannel_audit_report.md)

---

## 1. 概述与核心原则

### 1.1 核心问题定义
在当前 Supervisor-Worker（主智能体调度 + SQL 专家子智能体执行）的多智能体体系中：
- **排他锁限制**：`MessageItem.vue` 中配置了 `v-if="subagentsList.length === 0 && ..."` 的排他判断；
- **交付物深埋**：一旦派发了子智能体，生成的 **ECharts 趋势图表**、**CSV 下载卡片** 被强制锁死在折叠的 `SubagentCard.vue` 内部；
- **用户路径过长**：用户在主消息气泡中只能看到一段纯文本，必须手动展开子卡片、滚动跳过思考链与参数才能找到图表和下载按钮，破坏了“即问即得”的业务体验。

### 1.2 规范设计原则（Simplicity First）
1. **一等交付物直达（Primary Deliverables Bubble-Up）**：核心图表与 CSV 下载卡片在主气泡第一视口（Primary Viewport）直接呈现；
2. **拒绝过度设计（Zero Over-engineering）**：**所有 SQL 探针及其查询结果表格 100% 留在 `SubagentCard` 内部**，不在主气泡搞多表 Tab 过滤穿透；主气泡只作为无子智能体时的兜底；
3. **双轨体验（Dual-Projection Model）**：主气泡负责业务交付（Markdown + Chart + CSV），子卡片负责执行审计（CoT + SQL + 原始表），内外部防双重重量级 Canvas 渲染；
4. **标准工具调用驱动（Schema-Driven）**：依赖 LangChain Pydantic Tool Schema 与现有 `base_system_prompt.md`，**无需引入类似 LobeHub 的 XML `<artifacts_guides>` 系统提示词**。

---

## 2. 工件分级与展示归属规范（Artifact Tiering & Presentation Scope）

```
                           工件分类与界面呈现拓扑
                                     │
    ┌────────────────────────────────┼────────────────────────────────┐
    ▼                                ▼                                ▼
【Tier 1: 一等交付工件】          【Tier 2: 原始数据证据链】       【Tier 3: 过程痕迹工件】
 (Primary Deliverables)            (Underlying Evidence Tables)     (Process Traces)
 - 📊 ECharts 图表 (chart_spec)   - 📋 SQL 查询结果 (query_result) - 🔍 中间 SQL 探针 / 表结构查询
 - 📥 CSV 导出文件 (file_export)                                  - 🧠 思维链 (CoT) / 词典消歧
                                                                  - ⚡ 工具调用入参 / 耗时审计
    │                                │                                │
    ▼                                ▼                                ▼
【100% 无条件提升至主气泡】        【100% 归位留在 SubagentCard】    【100% 锁死在 SubagentCard 内部】
```

### 2.1 分级定义与交付约定

| 工件级别 | 包含资产类型 | 业务属性 | 主气泡展示策略 (MessageItem) | 子卡片展示策略 (SubagentCard) |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: 一等交付工件**<br>*(Primary Deliverables)* | 1. **`chart_spec`** (ECharts 图表)<br>2. **`file_export`** (CSV 文件) | 业务最终可视化与导出资产 | **100% 无条件提升呈现**<br>（置于回复正文下方第一视口） | **降级为轻量引用胶囊**<br>（避免内外部双重实例化 Canvas） |
| **Tier 2: 原始数据证据链**<br>*(Underlying Evidence)* | **`query_result`** (SQL 数据表格) | 原始数据结构化结果 | **不穿透（仅在无子智能体时兜底）**<br>（主气泡保持极致清爽） | **完整呈现表格**<br>（默认紧凑折叠，供展开排查与审计） |
| **Tier 3: 过程痕迹工件**<br>*(Process Traces)* | 1. 思维链 (CoT)<br>2. 表结构探测 SQL<br>3. 词典消歧探针<br>4. 参数与耗时日志 | 算法推理脚手架与调试信息 | **❌ 严禁外溢至主气泡** | **完整展示于子卡片折叠区**<br>（支持技术审计） |

---

## 3. 为什么 SQL 数据表留在子卡片而不是穿透到主气泡？

1. **认知模型解耦**：
   - 用户使用智能体是为了获取**归纳提炼后的业务结论**，而不是 3 张未经处理的原始数据库二维表；
   - 大模型在 Markdown 正文里已经输出了结构化总结（或 Markdown 排版表格）；
2. **彻底杜绝信息垃圾场**：
   - 避免在主气泡中塞入“正文 + 多个 SQL 探针 Tab + 图表 + CSV 下载卡片”的混乱布局；
   - 前端无需编写脆弱的“正则过滤元数据 SQL”、“动态计算 Tab 名字”等过度设计逻辑；
3. **与 OpenAI / Claude 行业标准完全对齐**：
   - OpenAI 的 Python 计算表全部留在 `[>_ Analyzed]` 胶囊里；
   - Claude 的工具结果全部留在 Tool 块里；
   - 只有最终图表和导出文件才会出现在主气泡中。

---

## 4. 系统提示词架构裁决（Prompt Architecture Decision）

### 裁决结论：无需新增类似 LobeHub 的 XML `<artifacts_guides>` 系统提示词
- **LobeHub** 依赖庞大 Prompt 是因为其采用纯前端文本标记（逼迫 LLM 手写 `<lobeArtifact>` XML 标签）；
- **本项目** 基于标准的 LangChain / LangGraph Tool Calling（`build_chart_artifact`, `export_to_csv`），后端 Python 自动执行、验证并由 State 侧信道直推；
- 现有的 [`base_system_prompt.md`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/backend/app/agent/subagents/sql/base_system_prompt.md) §4.1 与 §4.2 已包含完备的图表触发门禁与 CSV 建议策略，**零 Prompt 冗余与维护负担**。

---

## 5. 前端工程改造细则（Surgical & Minimal）

### 5.1 `MessageItem.vue` 改造细则

#### 1. 响应式计算属性与稳定排序
```typescript
// 1. 提取全局工件字典池，并按时间戳与 tool_call_id 执行确定性稳定排序
const artifactsList = computed<Array<Record<string, unknown>>>(() => {
  const list = Object.values(artifactsMap.value)
  return list.sort((a, b) => {
    const tA = (a.created_at as string) || ''
    const tB = (b.created_at as string) || ''
    if (tA && tB) return tA.localeCompare(tB)
    return String(a.tool_call_id || '').localeCompare(String(b.tool_call_id || ''))
  })
})

// 2. Tier 1 一等交付工件提取 (主气泡直出)
const chartSpecsList = computed<ChartArtifact[]>(() => {
  return artifactsList.value
    .filter((a) => a && (a as any).kind === 'chart_spec')
    .map((a) => a as unknown as ChartArtifact)
})

const fileExportsList = computed<ExportArtifact[]>(() => {
  return artifactsList.value
    .filter((a) => a && (a as any).kind === 'file_export')
    .map((a) => a as unknown as ExportArtifact)
})
```

#### 2. Template 挂载层级解耦
```html
<!-- 1. Tier 1 图表工件挂载区 (主气泡直出，解除 subagentsList.length === 0 限制) -->
<div v-if="chartSpecsList.length > 0" class="mt-3 space-y-3 animate-fade-in">
  <ChartGroupCard :charts="chartSpecsList" />
</div>

<!-- 2. Tier 1 CSV 文件导出卡片挂载区 (主气泡直出，解除 subagentsList.length === 0 限制) -->
<div v-if="!isUser && fileExportsList.length > 0" class="mt-3 space-y-3 px-1 pb-1 animate-fade-in">
  <div
    v-for="fExport in fileExportsList"
    :key="fExport.file_id"
    class="flex items-center justify-between rounded-xl border border-emerald-200/80 bg-emerald-50/40 p-3 shadow-2xs dark:border-emerald-900/60 dark:bg-emerald-950/30"
  >
    <div class="flex items-center gap-2.5 min-w-0">
      <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100/80 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300 font-bold text-xs">
        CSV
      </div>
      <div class="min-w-0">
        <div class="truncate text-xs font-semibold text-emerald-950 dark:text-emerald-100">
          {{ fExport.filename }}
        </div>
        <div class="text-[11px] text-emerald-700/80 dark:text-emerald-300/70 mt-0.5">
          <span>共 {{ fExport.row_count }} 行 × {{ fExport.col_count || 0 }} 列</span>
          <span v-if="fExport.size_bytes"> · {{ formatFileSize(fExport.size_bytes) }}</span>
          <span v-if="fExport.expires_at"> · 有效期至 {{ formatFullDateTime(fExport.expires_at) }}</span>
        </div>
      </div>
    </div>
    <button
      type="button"
      @click="handleExportDownload(fExport.file_id)"
      class="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white shadow-xs hover:bg-emerald-700 active:scale-95 transition-all shrink-0 cursor-pointer border-0"
    >
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      <span>下载 CSV</span>
    </button>
  </div>
</div>

<!-- 3. Tier 2 SQL 数据表格挂载区 (仅在无子智能体时作为外层兜底展示) -->
<div
  v-if="!isUser && subagentsList.length === 0 && sqlQueryResultsList.length > 0"
  class="mt-3 text-left animate-fade-in"
>
  <QueryResultGroup :tables="sqlQueryResultsList" />
</div>
```

---

### 5.2 `SubagentCard.vue` 改造细则（防双重渲染）

在 `SubagentCard.vue` 的工具步骤中：
- 当该步骤产生 `chart_spec` 时，渲染**轻量胶囊引用**，避免与主气泡产生两个相同的 Canvas 实例；
- 当该步骤产生 `sql_db_query` 时，渲染**折叠数据表格（`QueryResultGroup`）**，供展开排查。

```html
<!-- SubagentCard 内部对已透出图表的轻量化引用 -->
<div v-if="getToolChartArtifact(tool.id)" class="mt-2 flex items-center justify-between rounded-lg bg-primary/5 border border-primary/20 px-2.5 py-1.5 text-xs text-primary dark:bg-primary/10">
  <div class="flex items-center gap-1.5 truncate">
    <span>📊</span>
    <span class="font-medium truncate">{{ getToolChartArtifact(tool.id)!.title || '图表工件' }}</span>
  </div>
  <span class="text-[10px] text-neutral-400 shrink-0">已交付至主视口</span>
</div>
```

---

## 6. 视觉动线编排（Visual Hierarchy）

主气泡重构后的自上而下视线流线：

```
┌─────────────────────────────────────────────────────────────┐
│  MessageItem (主消息气泡)                                    │
├─────────────────────────────────────────────────────────────┤
│  1. 思考链折叠区 (ReasoningAccordion - 默认收起)            │
│  2. 子智能体过程卡片 (SubagentCard - 默认收起/审计日志)      │
│     - ⚡ SQL 数据专家 (已完成 · 1.2s) [展开详情 ⌄]           │
│       └─ 内部包含中间 SQL 语句与原始表格 (默认折叠)           │
│  3. 主回复正文 (Markdown Content)                           │
│  ─────────────────────────────────────────────────────────  │
│  4. ★ 核心工件交付区 (Artifact Delivery Zone - 第一视口)    │
│     ├─ 📊 交互式 ECharts 图表 (ChartGroupCard · 首屏直达)    │
│     └─ 📥 CSV 导出与下载卡片 (CSV Export Card · 一键下载)    │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 质量保障与验收矩阵

| 序号 | 验收测试场景 | 预期行为 | 判定标准 |
| :---: | :--- | :--- | :---: |
| **TC-01** | 用户要求生成图表（触发子智能体） | 主气泡第一视口直接渲染 ECharts 图表；SubagentCard 内部显示轻量胶囊引用；SQL 表格不重复出现在主气泡 | ✅ 必须通过 |
| **TC-02** | 用户要求导出 CSV（触发子智能体） | 主气泡第一视口直接渲染绿色 CSV 下载卡片；点击一键触发下载 API | ✅ 必须通过 |
| **TC-03** | 多子智能体并发执行产出多图表 | `ChartGroupCard` 并列呈现全部图表，且按时间戳稳定排序，无顺序抖动 | ✅ 必须通过 |
| **TC-04** | F5 页面刷新回放 | 页面刷新后，直接从 `message.tool_artifacts` 秒级恢复图表与 CSV，顺序 100% 一致 | ✅ 必须通过 |
| **TC-05** | 前端全量构建与类型检查 | `npm run build:check`（`vue-tsc && vite build`）通过 | ✅ 0 错误通过 |
| **TC-06** | 后端全量测试回归 | `pytest -m "not integration and not smoke"` | ✅ 82 passed 全绿 |
