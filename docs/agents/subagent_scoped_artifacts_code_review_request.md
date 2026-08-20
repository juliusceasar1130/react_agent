# Subagent-Scoped Artifacts 代码审查请求 (Code Review Request)

## 一、 审查背景与目标
针对 Phase 2 扩展需求：**子智能体专属工件内嵌与富交互调用序列**（设计规范见 `docs/superpowers/specs/2026-08-20-subagent-scoped-artifacts-design.md` v1.1），完成代码实现。
核心改造点：
1. `frontend/src/components/chat/SubagentCard.vue`：引入 `artifactsPool`，基于 `tool_call_id` 在工具调用项下方内嵌渲染 `<QueryResultGroup>` / `<TableResult>`（SQL 数据表）、紧凑型 CSV 下载卡、`<ChartArtifactCard>`（图表预览）；支持智能默认展开。
2. `frontend/src/components/chat/MessageItem.vue`：将 `artifactsMap` 注入 `SubagentCard`，并在 `subagentsList.length > 0` 时将外层的表格、图表、内联 CSV 下载卡全面消重降级（仅在无子智能体时外层兜底展示）。

## 二、 关键变更文件清单
- `frontend/src/components/chat/SubagentCard.vue`
- `frontend/src/components/chat/MessageItem.vue`
- `docs/superpowers/specs/2026-08-20-subagent-scoped-artifacts-design.md`
- `.scratch/subagent-scoped-artifacts/issues/` (Tickets 01-04)
- `changelog.md`
- `README.md`

## 三、 审查重点清单
1. **工件匹配与渲染健壮性**：`getToolArtifact` 与 `getParsedToolResult` 是否能覆盖实时流式与历史回放？
2. **消重与降级逻辑**：`MessageItem.vue` 中外层表格/图表/CSV 在有/无子智能体时的显示/隐藏逻辑是否严密？
3. **TypeScript 类型安全与构建质量**：是否满足 `vue-tsc` 严格检查？
4. **性能与状态隔离**：各子智能体卡片内部组件的响应式状态是否独立无污染？
