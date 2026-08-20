# 子智能体专属工件内嵌与富交互调用序列设计规范 (Subagent-Scoped Artifacts & Rich Tool Results Design Spec)

> **文档版本**：v1.1 (Claude Code 跨 Agent 联合评审修订终版)  
> **文档位置**：`docs/superpowers/specs/2026-08-20-subagent-scoped-artifacts-design.md`  
> **设计目标**：实现子智能体（`SubagentCard`）从“日志查看器”向“自闭环专家工作台”的升级，将工具执行产出的结构化数据（SQL 数据表、CSV 导出卡、图表工件）精准就近内嵌在所属子智能体的工具调用节点中，消除空间割裂与视觉噪音。

---

## 1. 现状痛点与重构动机

### 1.1 现状分析
在 Phase 2 重构后，后端工件统一底座（`ArtifactStore`）和持久化机制（`chat_messages.tool_artifacts`）已实现毫秒级流式下发与 100% 历史回溯复原。但目前前端界面呈现存在**“过程在卡片内、产出在卡片外”**的割裂现象：

1. **子智能体卡片内容粗糙**：
   - `<SubagentCard>` 内部对所有 8 种工具统一使用 `<details><pre>{{ toolResults }}</pre></details>` 渲染原始字符串或原始 JSON；
   - SQL 查询返回的结构化数据在卡片内部只是一串可读性极差的 Python 元组文本 `[(2026-08-01, 12, ...)]`。
2. **工件归属感与血缘割裂**：
   - 真正美观的 ECharts 图表、多功能分页数据表格及 CSV 下载卡被集中堆放在**主消息气泡最底部**；
   - 在多智能体协同场景下，用户无法直观辨识哪张数据表格或 CSV 是哪个子智能体查出来的。

### 1.2 预期收益
- **智能体设计自闭环（Self-Contained Subagent）**：子智能体成为独立的分析单元，涵盖：`思考过程` -> `工具序列` -> `专属数据表/工件` -> `专家总结`；
- **血缘清晰（Data Lineage）**：多智能体并发时，各专家的产出一目了然；
- **主气泡极简（De-clutter Main Chat）**：主 Agent 气泡聚焦于最终的高阶业务总结与决策建议，避免长列表或大表格刷屏。

---

## 2. 工具结果分类与分层渲染矩阵

根据子智能体工具箱中 8 种工具的**业务属性与用户认知成本**，制定严格的分层渲染规范：

```
                              子智能体工具结果分层渲染矩阵
                                           │
     ┌─────────────────────────────┼─────────────────────────────┐
     ▼                             ▼                             ▼
【1. 终态工件类 (富交互组件)】    【2. 交互控制类 (状态与引导)】 【3. 过程知识类 (轻量折叠)】
 - sql_db_query                - AskUserQuestion             - search_saved_correct_tool_uses
   └── 渲染 <TableResult>         └── 渲染 蓝色脉冲徽标          - search_db_value_lexicon
 - export_to_csv                     + '定位到表单' 按钮       - search_db_row_lexicon
   └── 渲染 紧凑型 CSV 下载卡                                   - search_db_table_schema
 - build_chart_artifact                                        └── 渲染 轻量折叠代码块
   └── 渲染 紧凑型图表预览卡
```

### 2.1 分类处理策略与精准映射

| 工具名称 | 工具分类 | 识别依据 / 契约 | 内嵌呈现规范 |
| :--- | :---: | :--- | :--- |
| **`sql_db_query`** | **终态工件** | `tool_artifact.kind == "query_result"` | **内嵌交互式分页表格**：直接复用 `<QueryResultGroup>` / `<TableResult>`，归一化 `:is-truncated="Boolean(art.is_truncated ?? art.truncated)"`，绑定 columns, rows, rowCount, totalCount。 |
| **`export_to_csv`** | **终态工件** | `tool_artifact.kind == "file_export"` 或 tool_results 包含 `file_id` | **内嵌极简 CSV 下载卡**：展示文件名、导出总行数、有效时间 `expires_at`，复用 `@/api/exports` 的 `triggerExportDownload(file_id)` 触发安全下载。 |
| **`build_chart_artifact`** | **终态工件** | `tool_artifact.kind == "chart_spec"` 或 tool_results 包含 `chart_id` | **内嵌图表预览卡**：复用 `<ChartArtifactCard>`，展示图表标题、图表类型图标，并提供 `全屏放大` 与 `数据视图` 交互。 |
| **`AskUserQuestion`** | **交互控制** | `tool.name == "AskUserQuestion"` | **维持呼吸灯徽标与锚点定位**：运行中展示 `等待用户确认...` 状态标签与 `定位到表单` 按钮；提交后展示 `已确认` 绿色完成态。 |
| **检索与词典工具**<br>(4 个工具) | **过程知识** | `search_saved_correct_tool_uses`<br>`search_db_value_lexicon`<br>`search_db_row_lexicon`<br>`search_db_table_schema` | **维持轻量 `<details>` 折叠**：格式化 JSON/SQL 代码高亮，默认折叠，供技术排查查看，零视觉干扰。 |

---

## 3. 前端架构与数据流编排设计

### 3.1 数据流架构图

```
 [ 后端 SSE 流 / DB 持久化 ] 
              │
              ▼ (tool_artifacts 池: Keyed by tool_call_id, 包含 subagent_name)
    ┌────────────────────────────────────────────────────────┐
    │                    MessageItem.vue                     │
    │                                                        │
    │  1. 解析 memoryArtifactPool / message.tool_artifacts   │
    │  2. 全量工件池向下单向注入 subagentsList               │
    └───────────┬────────────────────────────────┬───────────┘
                │                                │
        (子智能体专属工件)               (主智能体工件 / 顶层兜底)
                ▼                                ▼
    ┌──────────────────────┐          ┌──────────────────────┐
    │   SubagentCard.vue   │          │   MessageItem 气泡区  │
    │                      │          │                      │
    │ - 思考折叠           │          │ - 主 Agent 最终回复  │
    │ - 工具调用链         │          │ - 全局兜底表格/图表/  │
    │   └── 内嵌 TableResult│          │   CSV (仅无子智能体) │
    │   └── 内嵌 CSV卡片   │          │ - 快捷一键制图 Banner│
    │ - 专家执行总结       │          └──────────────────────┘
    └──────────────────────┘
```

### 3.2 组件职责划分与接口改造

#### 1. `frontend/src/components/chat/SubagentCard.vue`
- **Props 扩充**：
  ```typescript
  interface Props {
    subagent: SubagentSessionState
    // 注入当前消息的全局工件池 (包含流式实时池与历史持久化池)
    artifactsPool?: Record<string, any>
  }
  ```
- **工件匹配计算方法**：
  ```typescript
  // 根据 tool.id (即 tool_call_id) 精准匹配对应的工件实体
  const getToolArtifact = (toolCallId: string) => {
    if (!props.artifactsPool) return null
    return props.artifactsPool[toolCallId] || null
  }
  ```
- **工具项模板插槽渲染**：
  - 当 `tool.name === 'sql_db_query'` 且 `getToolArtifact(tool.id)` 存在时：
    渲染 `<QueryResultGroup :tables="[art]" />` / `<TableResult :columns="art.columns" :rows="art.rows" :row-count="art.rows?.length || 0" :total-count="art.total_count || art.row_count || 0" :is-truncated="Boolean(art.is_truncated ?? art.truncated)" />`；
  - 当 `tool.name === 'export_to_csv'` 且 `getToolArtifact(tool.id)` 存在时：
    渲染紧凑型 CSV 下载卡（绑定文件名、行数与下载链接）；
  - 否则回退为既有的 `<pre>{{ subagent.toolResults[tool.id] }}</pre>` 折叠块。
- **智能默认展开策略**：
  - 若子智能体正在运行（`subagent.status === 'running'`）或包含未折叠的数据表格产出，卡片默认展开（`isExpanded = ref(true)`），确保用户无需手动点击即可直接分析数据。

#### 2. `frontend/src/components/chat/MessageItem.vue`
- **全量消重与降级范围（消重三剑客）**：
  - `MessageItem` 外层的 `<QueryResultGroup>`、`<ChartGroupCard>` 以及内联 CSV 下载卡片（行 229-306），统一作为**无子智能体时的兜底展示容器**；
  - 当 `subagentsList.length > 0` 且工件已被子智能体卡片内嵌消费时，外层对应的表格、图表与 CSV 块自动隐藏，彻底消除“双重重复展示”现象。

---

## 4. 边界安全性、向后兼容与性能考虑

1. **零后端改动（Zero Backend Impact）**：
   - 后端 `tool_artifact` 规范在 Phase 2 已完整注入 `tool_call_id`、`subagent_name`、`created_by`，数据库存储格式 100% 兼容，无需任何 DDL 迁移或后端代码改动。
2. **历史消息 100% 幂等还原**：
   - 页面刷新（F5）或切换历史会话时，`message.tool_artifacts` 包含完整的 `tool_call_id` 映射字典，前端纯通过 ID 索引进行无损关联，历史表现与实时流式 100% 一致。
3. **表格分页性能隔离**：
   - 每个子智能体卡片内部的 `<TableResult>` 持有独立的 `currentPage` 和 `pageSize` 响应式状态，多智能体并发产生多张表格时，各表格翻页完全独立，互不干扰。

---

## 5. 验证与验收标准 (Acceptance Criteria)

- [ ] **AC 1 (SQL 专家自闭环)**：当 `sql_domain_agent` 执行查询时，`<SubagentCard>` 内部工具序列对应项直接渲染带原生分页的 `<TableResult>`，不再显示生硬的元组文本。
- [ ] **AC 2 (CSV 导出卡片化)**：当执行 `export_to_csv` 时，卡片内部直接展示带有文件名、行数与下载按钮的精致卡片。
- [ ] **AC 3 (消重与去噪)**：子智能体产生的表格、图表与 CSV 下载块不再在主气泡外部重复堆叠；主气泡仅展示主 Agent 业务总结与跨领域一键制图 Banner。
- [ ] **AC 4 (历史回溯一致性)**：F5 刷新页面后，所有子智能体卡片内的历史表格与 CSV 下载卡完好如初。
- [ ] **AC 5 (类型与测试健全)**：`npm run build:check` 0 错误，后端 pytest 自动化回归 100% 全绿。
