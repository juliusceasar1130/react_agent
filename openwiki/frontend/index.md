# 文件

- [Vue 3 聊天前端](chat-app.md) - 基于 Vue 3 + Pinia + Vite 的聊天单页应用（SPA）：将流式事件同步到按会话划分的消息状态（模块级单例流控），渲染子代理卡片、恢复产物卡片状态、提供问题导航栏，以及带竞态防护与分类超时的场景/反馈界面。
- [前端流式发送 / 恢复 / 停止 / 删除生命周期](streaming-lifecycle.md) - 前端流式会话的完整生命周期：模块级单例流控状态（streamMode / thinkingLevel / activeStreamControllersMap / sendingSessionsMap / contextWarningsMap）在 ChatView 与 MessageItem 间的共享，发送、resume、停止生成、删除会话 abort 的顺序契约，以及 useRequestGuard 竞态防护与 executeScenarioApi 60s 超时等不变式。
