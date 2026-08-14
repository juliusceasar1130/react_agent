# 03 — 前端流式事件白名单扩展与 SubAgentBadge.vue 智能体徽章

**What to build:**  
在前依赖项与 UI 层扩展支持多智能体状态感知：扩展 `types/index.ts` 中 `Message` 接口；在 `api/chat.ts` 的 `STREAM_EVENT_TYPES` 白名单 Set 注册 `'subagent_change'`；在 `stores/messages.ts` 响应并绑定事件；开发并挂载 `components/SubAgentBadge.vue`（严格遵守离线 SVG 部署规范）。

**Blocked by:** 02 — 服务层 StreamPart 流式 v2 字典解包与领域切换事件派发

**Status:** COMPLETED

- [x] `frontend/src/types/index.ts` 扩展 `active_subagent` 字段
- [x] `frontend/src/api/chat.ts` 注册 `'subagent_change'` 白名单并增加解析分支
- [x] `frontend/src/stores/messages.ts` 在 `handleStreamEvent` 中响应并更新消息状态
- [x] 新建 `frontend/src/components/SubAgentBadge.vue` 智能体感知徽章
- [x] `frontend/src/components/MessageItem.vue` 中挂载徽章组件
