---
type: 组件
title: "Vue 3 聊天前端"
description: "基于 Vue 3 + Pinia + Vite 的聊天单页应用（SPA）：将流式事件同步到按会话划分的消息状态，渲染子代理卡片、恢复产物卡片状态、提供问题导航栏，以及场景/反馈界面。"
tags: [frontend, vue, pinia, streaming, ui, navigation]
openwiki:
  roles: [frontend, domain]
  change_kinds: [ui, protocol]
  source_paths: [frontend/src/stores/messages.ts, frontend/src/api/chat.ts, frontend/src/views/ChatView.vue, frontend/src/components/chat/MessageItem.vue, frontend/src/components/chat/MessageList.vue, frontend/src/components/chat/QuestionRail.vue, frontend/src/composables/useScrollSpy.ts, frontend/src/components/chat/SubagentCard.vue, frontend/src/composables/useChatStream.ts, frontend/src/components/common/SegmentedControl.vue]
  symbols: [useMessagesStore, useChatStream, SubagentCard, ChartGroupCard, QueryResultGroup, StreamingMessage, useScrollSpy, UserQuestionItem, QuestionRail, ThinkingLevel, SegmentedControl]
  validation_commands: [cd frontend && npx vue-tsc --noEmit]
  invariants:
    - Streaming frames are partitioned per session and per subagent_id; streaming-phase and finalized rendering are separate responsibilities.
    - Persisted tool_calls/tool_results JSON is reconstructed into subagent card state on history load.
---

# Vue 3 聊天前端

`frontend/` 是聊天单页应用（Vue 3 `<script setup>` + Pinia setup 风格 store + Vite + Tailwind + ECharts）。它与位于 Nginx 前缀 `/rearch` 下的后端通信（axios 基础路径 `/rearch`，聊天 API `/rearch/api/chat` — 参见 `frontend/src/api/index.ts` 和 `frontend/src/api/chat.ts::API_BASE`）。禁止使用公开 CDN 资源；字体/库均本地化（`AGENTS.md` 离线约束）。

## 状态：Store

| Store | 文件 | 负责内容 |
|---|---|---|
| `useMessagesStore` | `frontend/src/stores/messages.ts` | 每个会话的 `messages` + `streamingMessagesMap`（多会话并行流式传输）；`reconstructSubagents` 根据持久化的 `tool_calls`/`tool_results` JSON 重建 `SubagentSessionState`；从渲染文本中移除内部 `<context_redacted>`/`<context_collapsed>` 标记 |
| `useSessionsStore` | `frontend/src/stores/sessions.ts` | 会话 CRUD 列表状态 |
| `useSkillsStore` | `frontend/src/stores/skills.ts` | 仪表盘技能发现（`GET /api/chat/skills`） |
| `useScenarioPanelStore` | `frontend/src/stores/scenarioPanel.ts` | 快速场景直连路径面板状态 |

## 流式同步

- `frontend/src/composables/useChatStream.ts` 驱动 SSE 消费者；事件通过 `frontend/src/api/chat.ts::parseStreamEvent` 流转（白名单 + 按类型守卫，参见 [streaming-protocol](../workflows/streaming-protocol.md)）。
- `StreamingMessage` / `FinalizedStreamingMessage` / `SubagentSessionState` 类型位于 `frontend/src/types/index.ts`；内部标记移除和子代理重建位于 `stores/messages.ts`。

## 思考强度分段选择器

输入工具栏的思考控制是四档分段选择器（Phase 3 实现；规范：`openspec/changes/phase3-thinking-levels/spec.md`），替换了 Phase 2 的"深度思考" ToggleSwitch：

- `frontend/src/components/common/SegmentedControl.vue` — 通用分段选择器组件（`modelValue` + `options`，`update:modelValue` 事件；Tailwind + 暗色模式，本地打包符合离线约束）。
- `frontend/src/views/ChatView.vue` — 渲染四个档位：关闭（`off`）/ 轻思考（`low`）/ 标准思考（`medium`）/ 深度思考（`high`），默认"标准思考"。
- `frontend/src/composables/useChatStream.ts` — `thinkingLevel` ref（`ThinkingLevel = 'off' | 'low' | 'medium' | 'high'`，来自 `frontend/src/types/index.ts`）；`enableThinking` 改为只读 computed（`thinkingLevel.value !== 'off'`）；`thinkingLevelParam` 在 `off` 时返回 `undefined`。流式与非流式**两处 payload** 均携带 `enable_thinking` + `thinking_level`。
- 后端契约：`ChatRequest.thinking_level: Literal["low","medium","high"]` 仅 `enable_thinking=true` 时生效，映射到 `reasoning_effort`（low→low / medium→medium / high→xhigh）；完整链路见 [采样参数组合与动态注入](../architecture/sampling-profiles.md)。

## 消息与产物渲染

- `frontend/src/components/chat/MessageItem.vue` — 消息气泡：状态行、`ReasoningAccordion`（思考过程）、`SubagentCard` 列表、Markdown 正文、调试面板；在等待澄清时显示"等待您的确认..."（[clarification-flow](../workflows/clarification-flow.md)）。它还会解析子代理的 `[suggest_chart:<type>|『desc』]` 标记（一键折线图/柱状图按钮）以及由 `frontend/src/utils/markdown.ts` 提取的 `数据来源：` 页脚——这两种标记格式均由 [agent-prompts](../architecture/agent-prompts.md) 中记录的提示词契约定义，因此在那里修改标记会破坏此 UI。
- `frontend/src/components/chat/SubagentCard.vue` — 每个子代理的"专家工作台"：独立状态徽章、耗时、推理折叠面板、内部工具调用链以及嵌入产物。分层规则（`docs/multiagent_sidechannel/` 中的 spec v1.1）：Tier-1 交付物上浮到主气泡；`query_result` 表格和过程跟踪保持在此卡片内折叠。
- `frontend/src/components/artifacts/` — `ChartGroupCard.vue`（单图表视图 + 多图表选项卡）、`ChartArtifactCard.vue`、`QueryResultGroup.vue` / `TableResult.vue`（支持原生 20/50/100 分页和绝对行号的多表格切换器）、`DimensionTable.vue`、`ResultRenderer.vue` / `ScalarResult.vue`（直连路径场景输出，与 `frontend/src/components/common/ScenarioModal.vue` 和 `chat/FloatingScenarioCards.vue` 配合使用）。
- `frontend/src/components/chat/MessageList.vue` — 渲染 `MessageItem` 列表的滚动容器；它挂载 `QuestionRail` 和 scroll-spy（参见 [问题导航栏](#问题导航栏)），并向 `ChatView` 暴露 `scrollToBottom` / `scrollToMessage`。
- `frontend/src/components/chat/AskUserQuestionCard.vue` + `FloatingClarificationDock.vue` — 澄清卡片；`ReasoningAccordion.vue` — 思考面板。
- `frontend/src/components/agent/AdminReviewPanel.vue` — [RAG 反馈流水线](../domain/rag-and-lexicon.md) 的黄金案例审查界面。
- `frontend/src/components/chat/VariantB.vue` — 聊天页布局外壳（方案 B：微缩/展开双态侧边栏 + Bento 数据字典看板抽屉联动），由 `frontend/src/views/ChatView.vue` 直接渲染；侧边栏内通过插槽挂入 `SessionList` 与消息区。
- `frontend/src/views/ChatView.vue` — 单一视图；`WelcomeDashboard.vue` 是基于元数据的仪表盘（技能发现）。

## 问题导航栏

`frontend/src/components/chat/QuestionRail.vue` + `frontend/src/composables/useScrollSpy.ts`（两者均为 chat-nav 功能新增；规范：`docs/superpowers/specs/2026-08-23-question-navigation-rail-design.md`，计划：`docs/superpowers/plans/2026-08-23-question-rail.md`）添加一条位于右边缘的刻度导航栏，允许长会话在用户问题之间跳转。

- `MessageList.vue` 负责装配：它计算 `userQuestions: UserQuestionItem[]`（来自 `messages` 中 `role === 'user'` 的项，`index` 从 1 开始），并调用 `useScrollSpy(containerRef, userQuestions)`，其返回 `{ activeId, scrollToMessage, calculateActiveMessage }`。会话切换时，在 `fetchMessages` 之前将 `activeMessageId` 重置为 `null`。`defineExpose` 现同时向 `ChatView.vue`（`messageListRef`）暴露 `scrollToBottom` 和 `scrollToMessage`。
- `QuestionRail.vue` 渲染悬浮层：在 `questions.length < 2`、`loading` 为真（`messagesStore.loading`），或处于 `md` 断点以下（`hidden md:flex`）时隐藏。折叠状态为垂直刻度列（活动刻度更宽/更深）；悬停展开磨砂玻璃卡片，列出截断的问题文本；每一行发出 `select(id)`，由 `MessageList` 连接到 `scrollToMessage`。刻度使用 `v-memo`，并带有 `role="navigation"`/`aria-label` 无障碍属性。
- `MessageItem.vue` 为用户气泡添加 DOM 锚点 `:id="msg-${message.id}"`（仅限 user 角色），并添加 `.highlight-pulse` 关键帧样式（1.2 秒 box-shadow/scale "呼吸" 光晕，自动移除）。
- `useScrollSpy` 不变量：rAF 节流的滚动处理器；`ACTIVATION_OFFSET_TOP = 120px`（当用户消息顶部位于容器顶部 + 120px 或更高处时，该消息为"活动"状态）；滚动至距底部 `BOTTOM_THRESHOLD = 40px` 范围内时，强制 *最后一个* 用户问题为活动状态；消息流上的 `ResizeObserver` 会在流式内容/图表增长时重新校准；`scrollToMessage` 平滑滚动到 `el.top - 16px`，并通过强制重排重新触发 `.highlight-pulse`；`onUnmounted` 取消 rAF、定时器、监听器和 observer。

```mermaid
flowchart TD
    A["QuestionRail: select event"] --> B["useScrollSpy.scrollToMessage(id)"]
    B --> C["smooth-scroll to msg-{id} anchor"]
    B --> D["retrigger .highlight-pulse for 1.2s"]
    E["scroll event + ResizeObserver"] --> F["rAF-throttled calculateActiveMessage"]
    F --> G{"scrolled within 40px of bottom?"}
    G -->|yes| H["activeId = last user question"]
    G -->|no| I["activeId = last question whose top is above viewport top + 120px"]
    G --> J["QuestionRail active tick + expanded-card highlight"]
    F --> J
```
*问题导航栏运行时流程：用户驱动的定位（点击路径）和被动 scroll-spy（滚动路径）都收敛到 `activeId`。*

注意：设计规范的 §2.1 还列出了键盘导航（方向键/Enter），但已发布的 `QuestionRail.vue` 仅实现了鼠标交互（`mouseenter`/`mouseleave`/click）——没有键盘事件处理器。应将规范文本视为未实现意图，而非当前行为。

## 不变量与验证

- 子代理帧必须在端到端保留 `subagent_id`/`subagent_name` 元数据（后端测试：`backend/tests/agent/test_subagent_stream_scoping.py`；前端对应项：`STREAM_EVENT_TYPES` + `parseStreamEvent`）。
- **没有专门的前端单元测试套件** —— 有限的验证是类型检查：`cd frontend && npx vue-tsc --noEmit`（仓库的 `build:check` 脚本为 `vue-tsc && vite build`）。
- 新的后端流事件需要三处前端注册（`AGENTS.md` 中的不变量，规范文档位于 [streaming-protocol](../workflows/streaming-protocol.md)）。

## 变更配方：添加或重新调整消息卡片元素样式

1. 组件：添加在 `frontend/src/components/chat/`（消息级）或 `frontend/src/components/artifacts/`（数据交付物）下；保持流式阶段渲染与最终化渲染分离（仓库约定）。
2. 新的持久化字段：扩展 `frontend/src/types/index.ts` 中的 `Message`/`StreamingMessage` 类型以及 `stores/messages.ts` 中的重建逻辑。
3. 如果它渲染子代理工作，请基于 `SubagentSessionState`（`subagent_id` = 任务调用 id），而不是消息级假设。
4. 构建前使用 `cd frontend && npx vue-tsc --noEmit` 验证。

## 变更配方：扩展问题导航栏或滚动定位

该导航栏是一个四文件契约；保持各部分同步：

1. **锚点不变量**：`MessageItem.vue` 仅对用户消息绑定 `:id="'msg-' + message.id"`；`useScrollSpy` 通过 `document.getElementById(`msg-${id}`)` 解析锚点，并将 `.highlight-pulse` 作用于同一节点。在某一处重命名 `msg-` 前缀会静默破坏定位。
2. **数据契约**：`UserQuestionItem`（`frontend/src/composables/useScrollSpy.ts`）由 `MessageList.vue` 的 `userQuestions` 计算属性产生。修改项形状（例如添加 `index` 显示）时，需同时更新该类型和该计算属性。
3. **可见性规则**位于 `QuestionRail.vue` 的根 `v-if`（`questions.length >= 2 && !loading`）和 `hidden md:flex` 断点类中——请在该处调整，而非在父组件中调整。
4. **阈值**（`ACTIVATION_OFFSET_TOP = 120`、`BOTTOM_THRESHOLD = 40`、`- 16` 滚动内边距、1.2 秒脉冲窗口）是 `useScrollSpy.ts` / `MessageItem.vue` 样式中的模块常量；请就地修改，并注意与 `MessageList.vue` 中现有 `scrollToBottom` 自动跟随逻辑（`isNearBottom` / `bottomThreshold = 96` 是独立的 96px 常量——不要将其与 scroll-spy 的 40px 常量"去重"）的交互。
5. **会话切换重置**：对 `sessionsStore.currentSessionId` 的 `watch` 必须确保在 `fetchMessages` 之前 `activeMessageId.value = null`，否则上一会话中过期的 `activeId` 会在新会话中点亮刻度。
6. 使用 `cd frontend && npx vue-tsc --noEmit` 验证；没有前端单元测试套件，因此唯一的静态检查是类型检查。