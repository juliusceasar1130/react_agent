# 03 — 用户中断（Abort）与错误状态的弹性容错处理

**What to build:**
当用户中途点击“停止生成”（Abort）或 SQL 子智能体执行发生异常/报错时，`SubagentCard` 优雅进入 `interrupted` 或 `error` 状态，保留已经生成的思考片段与已执行 SQL 工具链，不随主消息粗暴清空，也不导致前端崩溃。

**Blocked by:** 02 — 子智能体卡片（SubagentCard）组件与独立思考/工具链 UI 呈现

**Status:** done

- [x] 在 `frontend/src/stores/messages.ts` 的 `finalizeStreamingInterrupted` 中，将活跃的 `subagents` 状态同步标记为 `interrupted` 并持久化到中断消息中
- [x] 在 `frontend/src/stores/messages.ts` 的 `finalizeStreamingError` 中，保留已执行完毕或部分执行的 `subagents` 卡片信息并补写 `memorySubagentsMap`，避免错误时整条消息与思考全清空
- [x] `SubagentCard.vue` 支持渲染 `error` 与 `interrupted` 状态的警示视觉样式与错误详情展开
