# 01 — 改造前端组件调用点为直通领域路径并恢复深度思考等组件渲染

**What to build:**
更新 `ChatView.vue`, `MessageItem.vue`, `ScenarioModal.vue`, `VariantB.vue` 中的所有组件 import 路径，直接指向 `@/components/chat/`, `@/components/agent/`, `@/components/artifacts/`, `@/components/common/` 领域子路径；彻底恢复 `ReasoningAccordion`（深度思考折叠面板）、`SubAgentBadge` 等子组件的原生 DOM 渲染能力。

**Blocked by:** None — can start immediately.

**Status:** completed

- [x] `MessageItem.vue` 更新同级和跨领域直接导入（`ReasoningAccordion`, `AskUserQuestionCard`, `SubAgentBadge`, `ChartArtifactCard`）
- [x] `ChatView.vue` 将 9 个组件导入切换至领域真实路径
- [x] `ScenarioModal.vue` 与 `VariantB.vue` 更新为真实路径
