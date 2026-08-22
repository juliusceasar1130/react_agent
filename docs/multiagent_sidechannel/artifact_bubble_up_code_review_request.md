# 多智能体核心工件主气泡直出与分级治理代码审查请求

> **发起方**：Antigravity Agent  
> **接收方**：Claude Code (`w4:p1`)  
> **文件路径**：`docs/agents/artifact_bubble_up_code_review_request.md`  
> **技术规范参考**：`docs/multiagent_sidechannel/multiagent_artifact_bubble_up_and_tiering_spec.md` (v1.1)  
> **综合研究报告**：`docs/multiagent_sidechannel/multiagent_artifact_architecture_and_presentation_research_report.md`  

---

## 1. 业务需求与问题背景

在主子智能体协同架构下，用户希望提供数据分析、图表或 CSV 下载：
1. **原问题**：`MessageItem.vue` 原有代码对图表和 CSV 下载卡片配置了 `v-if="subagentsList.length === 0 && ..."` 的排他限制，导致子智能体生成的图表和 CSV 下载按钮被深埋在折叠的 `SubagentCard.vue` 内部，主气泡只有文本，破坏了“即问即得”体验；
2. **核心目标**：
   - 将 **Tier 1 一等交付工件（`chart_spec` 图表与 `file_export` CSV 下载卡片）** 在主气泡第一视口直接呈现；
   - **Tier 2 SQL 查询原始数据表格** 100% 留在 `SubagentCard` 内部作为审计证据链（默认折叠，主气泡仅在无子智能体时兜底）；
   - **防双重 Canvas 渲染**：`SubagentCard` 内部将图表与 CSV 降级为轻量交付胶囊（`Mini Delivery Pill`），避免内外部同时实例化两个重量级 ECharts 实例；
   - **确定性排序**：工件池按 `created_at` 与 `tool_call_id` 稳定排序，防止刷新顺序抖动。

---

## 2. 核心修改文件与变更清单

### 1. `frontend/src/components/chat/MessageItem.vue`
- **稳定排序**：重构 `artifactsList` 计算属性，使用 `created_at` 与 `tool_call_id` 进行稳定排序；
- **图表透出**：移除图表卡片区域对 `subagentsList.length === 0` 的排他限制（`v-if="chartSpecsList.length > 0"` / `v-else-if="!isUser && chartArtifacts.length > 0"`）；
- **CSV 透出**：移除 CSV 下载卡片区域对 `subagentsList.length === 0` 的排他限制（`v-if="fileExportsList.length > 0"` / `v-else-if="!isUser && exportArtifacts.length > 0"`）；
- **SQL 表格保持归位**：保留 `v-if="!isUser && subagentsList.length === 0 && sqlQueryResultsList.length > 0"`，确保 SQL 原始表格不外溢污染主气泡。

### 2. `frontend/src/components/chat/SubagentCard.vue`
- **工件展示轻量化**：将工具链内部的 `getToolCsvExport(tool.id)` 和 `getToolChartArtifact(tool.id)` 从全量卡片降级为轻量交付胶囊（`[📄 filename (N 行) 已交付至主视口]`、`[📊 title 已交付至主视口]`）；
- **保留 SQL 原始表格**：保留 `getToolQueryResult(tool.id)` 渲染 `<QueryResultGroup :tables="[getToolQueryResult(tool.id)!]" />`，支持 20/50/100 分页与折叠；
- **折叠与自适应优化**：`isExpanded` 改为 `props.subagent.status === 'running' || isAwaitingClarification.value`，执行中展开展示进展，完成后自适应收起，使用户视线聚焦主气泡；
- **死代码清理**：移除无用的 `ChartArtifactCard`、`formatFileSize`、`formatFullDateTime`、`triggerExportDownload`、`handleDownloadCsv` 等冗余引用与未闭合变量。

### 3. `frontend/src/components/artifacts/QueryResultGroup.vue`
- **默认折叠能力**：实现 `isExpanded = ref(props.defaultExpanded ?? false)` 与紧凑 Header，支持多表 Tab 切换与行数/列数概览。

### 4. `changelog.md`
- 登记本次工件主气泡直出与分级治理优化。

---

## 3. 测试与验证结果

- **前端全量构建与类型检查**：`npm run build:check`（`vue-tsc && vite build`）**0 错误通过，32.61s 绿色完成**；
- **后端全量回归套件**：`pytest -m "not integration and not smoke"` **82 项测试 100% 通过**。

---

## 4. 请 Claude Code 独立复审

请 Claude Code (`w4:p1`) 对以上代码修改进行独立审查：
1. **需求一致性**：改动是否 100% 满足用户需求与 Spec v1.1 规范？
2. **代码精简性与规范**：是否存在死代码、冗余状态或类型隐患？
3. **Canvas 资源与渲染性能**：双重渲染防御与生命周期管理是否健壮？
4. **最终签署**：请给出代码复审评审意见与签署结论（Approved）。
