# 前端代码审计报告（2026-08-30，已合并双代理复核结论）

> 范围：`frontend/src` 全部 59 个文件（约 9500 行）+ vite/tsconfig 工程配置。
> 审计方式：逐文件人工审查 + `npx vue-tsc --noEmit` 实测零错误。
> 复核方式：报告全文发给两个独立代理对照源码逐条复核——
> - **cc**（Claude Code / Sonnet 4.6）：逐文件交叉比对 frontend + backend，耗时约 7 分钟
> - **agy**（Antigravity / Gemini 3.7 Flash）：SSE 全链路 / 状态管理 / 会话生命周期深查
> 复核共识：**原 18 条发现 18/18 属实，无硬性误报**；4 处严重级微调、1 处描述修正、补出 5 条新发现（2 高 + 3 中）、剔除 1 条复核方误报。
> 2026-07-31 `frontend/docs/code-review-2026-07-31.md` 中的历史问题（8 处死代码、ScenarioModal 双实例、test_markdown.js 残留、诊断日志）已确认全部修复。
>
> 路径简写：`F = frontend/src`

## 一、高危（修复优先级最高）

### H1. `final` 事件的 `subagents` 字段被静默丢弃（协议失配）【原 H1，双复核确认】
- `backend/app/services/chat_service.py:1138` 的 final 事件携带 `subagents` 快照；`backend/app/routers/chat.py:356/747` 原样下发 SSE。
- `F/types/index.ts` 的 `StreamEvent['final']` 声明了 `subagents?`；`F/composables/useChatStream.ts` 的 `final` 分支读取 `event.subagents ?? undefined`。
- 但 `F/api/chat.ts` 的 `parseStreamEvent` 的 `final` 分支**未解析 `parsed.subagents`**。
- 结果：服务端快照永远拿不到，`completeStreamingMessage` 回退本地流式累积的 `temp.subagents`，后端多出的字段（如 `description`）丢失。刷新后靠 `fetchMessages` 从库恢复（后端 `routers/chat.py:356-360` 已持久化），故仅"流式落定快照"丢失。
- 修复：`final` 分支补 `subagents` 解析（至少校验为 Record）。

### H2. `useChatStream` 状态非单例 → resume 链路两处失效【复核新发现（agy），已人工确认】
- `sendingSessionsMap` / `activeStreamControllersMap` / `contextWarningsMap` 声明在 `useChatStream()` 函数体内部（`F/composables/useChatStream.ts:32-41`），每次调用生成相互隔离的局部实例。
- `F/components/chat/MessageItem.vue:1005` 为拿 `resumeMessage` 单独调用 `useChatStream()`，与 `ChatView.vue:281` 的实例隔离。
- 后果：
  1. 提交澄清后 `sendingSessionsMap` 写在 MessageItem 局部实例，`ChatView` 的 `isSending` 恒 false → **底部主输入框未被禁用**，用户可并发发新消息，`startStreamingMessage` 会覆盖进行中的流式态；
  2. `ChatView` 的"停止生成"按钮调用本实例的 `stopStreaming()`，其 `activeStreamControllersMap` 为空 → **无法中止 resume 流**。
- 修复：流控状态上提到 store（如 `useChatStreamStore`）或模块级单例，使所有调用方共享同一份状态。

### H3. 历史会话 / 刷新页面后恢复澄清，流式渲染完全失效【复核新发现（agy），已人工确认】
- `resumeMessage` 仅对**已存在**的 `messagesStore.streamingMessagesMap[sessionId]` 置位，条目不存在时（刷新页面、打开历史中断会话）**未调用 `startStreamingMessage` 初始化**。
- 而 `F/stores/messages.ts` 的 `appendStreamingContent / appendStreamingReasoning / upsertStreamingToolCall / setStreamingToolResult` 及 `completeStreamingMessage` 均有 `if (!msg) return` 守卫 → resume 期间**所有流式事件被静默丢弃**。
- 表现：界面在恢复期间完全静止无字，直到流结束靠 `syncMessagesIfCurrent` 全量重拉后"突变"展示。
- 修复：`resumeMessage` 开头确保条目存在（不存在则 `startStreamingMessage`）。

## 二、中危

### M1. 中文输入法下按 Enter 确认候选词可能直接发出消息【原 H2，双复核建议降为中】
- `F/views/ChatView.vue:164` `@keydown.enter.exact.prevent="handleSendMessage"`，handler（:403-416）无 `e.isComposing` 检查。
- 同类问题（复核新发现，cc）：`F/components/chat/WelcomeDashboard.vue:25` `@keydown.enter="handleSubmit"` 连 `.exact` 都没有，欢迎页输入框是全页首个焦点控件，同类风险。
- 严重级：cc 认为不丢数据、多数 IME 上屏会消费 keydown，建议降为中；agy 维持高。修复成本极低，两处一并处理。

### M2. 直通场景 SQL 执行走 10 秒超时的 axios 实例【原 H3，双复核降为中】
- `F/api/index.ts:5` 全局 `timeout: 10000`；`F/api/scenarios.ts:108` `executeScenarioApi` 走该实例，慢查询 >10s 整单失败。
- 同文件的 `getScenariosApi / getScenarioParamsApi` 也走该实例。
- 降为中依据：旁路功能、主链路（流式 chat）不受影响、前端 `executeQuery` 有 try/catch 显示错误。
- 注：非流式 `/message` 用裸 `axios` 且 `API_BASE = '/rearch/api/chat'` 为绝对路径，前缀自带、无超时问题（复核方 cc 曾误报"缺 /rearch 前缀"，已核对剔除）。
- 修复：执行类请求单独设更长超时或禁用超时。

### M3. messages store 的 7 个 `memory*Map` 只增不清【原 M1，确认】
`F/stores/messages.ts:90-101` 的 `memoryRagMap / memoryLexiconMap / memoryArtifactMap / memoryArtifactPool / memoryReasoningMap / memoryReasoningDurationMap / memorySubagentsMap` 按消息 id 累积、无淘汰，`clearMessages / deleteSession` 均不回收。量级注：属"持久化字段的流式旁路缓存"，store 存活期内可控，但无淘汰属实。

### M4. `MessageList` 对全量消息做 `deep: true` watch【原 M2，确认（影响略被高估）】
`F/components/chat/MessageList.vue:138-145`：流式阶段每 token 触发对消息数组的深度遍历，随消息数线性增长。已落定历史消息引用未变、`renderMarkdown` 有 rAF 节流，实际开销小于字面估计。建议改为 watch 消息长度 + 最后一条消息。

### M5. `scenarioPanel.executeQuery` 无竞态防护【原 M4，确认】
`F/stores/scenarioPanel.ts` 的 `fetchGuard` 只接了 `fetchDomainTree`；快速切场景/翻页时旧响应可覆盖新结果。

### M6. 错误处理不一致【原 M5，确认，范围扩大】
- `F/views/ChatView.vue` 的 `handleDashboardSubmit` / `handleCreateSession`、`F/components/common/SessionList.vue:52` 的 `handleDeleteSession` 均无 try/catch → unhandled rejection；`handleDashboardSubmit` 失败时输入框残留内容。
- 发送失败提示用原生 `alert()`（ChatView:414）；`SessionItem.vue:127-132` 删除确认用原生 `window.confirm`（复核补充，同源）。

### M7. `DimensionTable.copyText` 无 HTTP 非安全上下文降级【原 M6，确认】
`F/components/artifacts/DimensionTable.vue:200` 直调 `navigator.clipboard.writeText`，未用 `F/utils/helpers.ts` 的 `copyToClipboard`（含 execCommand 降级），HTTP 部署下复制静默失败。

### M8. `deleteSession` 不中止关联的活跃 SSE 流【复核新发现（agy）】
`F/stores/sessions.ts:75-93` 删除正在流式的会话时只清本地展示 + 调后端删除，未 abort 对应 `AbortController` → SSE 连接后台空跑至后端生成完毕，浪费服务端算力且前端游离解析。
- 修复：删除前经共享流控（见 H2 修复）abort 该会话控制器。

### M9. `VariantB` Bento 抽屉 `fetchTableData` 无竞态防护【复核新发现（cc）】
`F/components/chat/VariantB.vue` `openDrawer` 快速切换抽屉时旧表响应可覆盖 `tableData`（无 AbortController / 请求序号），与 M5 同类、独立位置。

### M10. 网络中断时的消息错位路径（待补查）【复核新发现（cc），中低】
`handleStreamMessage` 内 `hasTerminalEvent` 校验抛错（"流式响应未正常结束"）时，`sendMessage` 的 catch 移除乐观 user 消息并重新拉取；若后端已持久化该条 assistant 消息，历史中可能出现"assistant 回复无对应 user 提问"的错位。仅在客户端断开/网络中断时可能触发，建议补查评估。

## 三、低危

1. **echarts 全量引入**【原 M3，降为低】：`F/components/artifacts/ChartArtifactCard.vue:36` `import * as echarts from 'echarts'`，全项目唯一一处，建议 `echarts/core` 按需注册。
2. **`plan_update` 死契约**【原 M7，描述修正】：`useChatStream.ts:227` `case 'plan_update': return` 为空操作；cc 全后端 grep 证实后端**从不 emit** 该事件（仅 `schemas.py:235` 类型声明 + `chat_service.py:558` 白名单"接受"）。定性为"前端为将来预留、后端未实现"，非"事件被丢弃"。
3. **`final` 事件的 `context_warning` 未解析**【复核新发现（agy），定性降级】：与 H1 同病灶（`chat_service.py:1139`、`chat.py:371` 下发，前端 `final` 分支不解析）。但前端另有 `status(source=context_warning)` 事件通道在喂预警横幅，属部分冗余；需确认后端两通道是否都发，若都发则低危。
4. 全局 `document.querySelector` 定位脆弱【原低 1，确认】：`SubagentCard.vue:382` 与 `FloatingClarificationDock.vue:79` 多实例时会抓错；`SubagentCard` 兜底选择器 `.animate-fade-in` 会命中消息列表所有入场动画元素。
5. `MessageItem` 的 `renderedContent` rAF 未在卸载时取消【原低 2，确认】：`MessageItem.vue:818-833` 卸载后回调仍写一次 ref（无效写，无泄漏）。
6. `api/index.ts` 响应拦截器 `return response.data` 破坏 axios 返回类型【原低 3，确认】：调用处大量 `as` 断言。
7. `useDateFormat.parseServerDate` 假设无时区 ISO 串为 UTC【原低 4，确认】：当前后端 `func.now()` 为 UTC 故一致；`formatFullDateTime` 用本地时区展示同一 Date，无 bug 但时区契约未文档化（复核补充）。
8. `ChartArtifactCard` 无 ResizeObserver【原低 5，确认】：容器尺寸变化时图表不自适应（初始渲染有 nextTick + 显式 resize，影响轻微）。
9. `AdminReviewPanel.handleReject` 用 `feedback: 'none'` 表达"忽略案例"【原低 6，确认】：与收藏态 'collected' 切换语义易混。
10. `.env.local` 的 `VITE_CHAT_DEBUG_STREAM=true`【原低 7，确认】：构建期 flag，`vite build` 默认读 `.env.local`，生产构建时注意勿继承（会带出控制台 debug 日志与 `showDebugDetails` 调试 UI）。
11. 无 ESLint/Prettier、零自动化测试、`@types/markdown-it` 靠本地 shim【原低 8，确认】。

## 四、验证过的干净项（复核抽查确认）

- SSE 解析层：跨 chunk buffer、`[DONE]` 前必须见终端事件、未知事件按 schema 拒收、AbortController 取消 + finally releaseLock、尾部残留 payload 校验——健壮无泄漏。
- 流式状态机：多会话并行流、`useRequestGuard` 防会话切换竞态、落定只推当前显示会话、停止生成保留片段落定——自洽（但受 H2 单例缺陷影响 resume 路径）。
- XSS：markdown-it `html: false` + DOMPurify html profile + 外链 `noopener noreferrer nofollow`；代码块复制按钮 `data-copy-content` 已 encodeURIComponent 且在 DOMPurify `ADD_ATTR` 白名单内；`SubagentCard` 的 `toolResults`/`args_text` 均为 Vue 插值转义；澄清回答拼入用户消息后走同一渲染链路。**复核未发现额外 XSS 面**。
- 离线约束合规：全代码 grep 无公网 CDN / 外部 http(s) 资源（唯一 http 是 vite dev 代理 target，非浏览器请求）。
- `npx vue-tsc --noEmit` 零错误，可复现。

## 五、复核过程中的误报剔除

- cc 声称"非流式 `/message` 用裸 axios 缺 `/rearch` 前缀，生产可能 404"——**不成立**：`chat.ts` 的 `API_BASE = '/rearch/api/chat'` 是绝对路径，前缀自带。

## 六、建议修复顺序

1. H2 + H3（resume 链路：流控单例化 + resume 初始化流式消息，两处关联，建议一次修完）
2. H1（`final` 补 `subagents` 解析，顺手评估同病灶的 `context_warning`，低危 3）
3. M1（两处 IME Enter 防护，几行小改）
4. M2 / M5 / M9（三处请求竞态/超时，统一接 `useRequestGuard` + 分类超时）
5. M8（deleteSession abort 流）、M6（错误处理统一）
6. 其余低危按机会处理。

## 七、修复实施与双 Agent 复评（2026-08-30 同日完成）

### 已修复（未提交，diff 见 `git diff -- frontend/src/`）

| 项 | 文件 | 变更 |
|---|---|---|
| H1 | `api/chat.ts` | `final` 分支补 `subagents` 校验与解析（服务端快照优先于本地累积）；`context_warning` 确认走 `status` 通道，不解析，留注释 |
| H2 | `composables/useChatStream.ts` | 流控/偏好五个 ref 上提为模块级单例（ChatView / MessageItem 共享） |
| H3 | `composables/useChatStream.ts` | `resumeMessage` 前置 `startStreamingMessage` 初始化流式条目 |
| M1 | `views/ChatView.vue` / `components/chat/WelcomeDashboard.vue` | Enter 改 `handleEnterKey`：`e.isComposing` 时不拦截，上屏后才发送 |
| M2 | `api/scenarios.ts` | `executeScenarioApi` 单独 `timeout: 60000` |
| M5 | `stores/scenarioPanel.ts` | 新增独立 `paramsGuard` / `queryGuard`，响应/错误/收尾全分支加 `isFresh` 守卫 |
| M8 | `useChatStream.ts` + `stores/sessions.ts` | 新增 `abortSessionStream` 导出；`deleteSession` 第一步调用（abort 先于删除 API，有意取舍） |
| M9 | `components/chat/VariantB.vue` | `fetchTableData` 请求序号 + 目标表比对双守卫 |
| 补修 | `views/ChatView.vue` | 复评发现：Shift+Enter 分支补 `.prevent`，修复双换行/中间换行跑位（既有 bug，非本次引入） |

累计 8 文件 +90/-15。验证：`vue-tsc --noEmit` 零错误、`vite build` 成功、dev server 模块图冒烟零 error。

### 双 Agent 复评结论（diff 独立评审）

- **cc (Claude Sonnet 4.6)**：APPROVED。无 blocker/major；对照后端 `schemas.py`/`crud.py`/`models.py` 全链路交叉验证 8 项修复。minor 2 条：① `sendingSessionsMap` 仅删除失败路径残留（归入 M3 择期）；② VariantB 无 AbortController 主动中断（防覆盖已达成，可接受）。nit 5 条均不构成问题。
- **agy (Gemini 3.7 Flash)**：APPROVED。无 blocker/major/minor；全链路走查与边界分析。nit 2 条：① Shift+Enter 双换行 bug（**已修复**）；② `subagents` 浅校验较 `tool_calls` 宽松（后端结构稳定，风格问题，择期统一）。

**综合裁决：通过，可合入。** 残留择期项：M3（memory*Map 清理，含删除失败路径残留）、M4/M6/M7/M10、低危 1-11；`subagents` 深度校验风格统一。
