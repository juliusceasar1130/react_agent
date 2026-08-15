# 02 — 子智能体卡片（SubagentCard）组件与独立思考/工具链 UI 呈现

**What to build:**
在聊天界面中完成主子智能体的视觉与信息呈现解耦。当主 Agent 委派子任务时，主消息下方动态嵌入独立的 `SubagentCard`，展示专属状态 Badge、独立耗时计时的深度思考折叠面板、领域 SQL 工具链（`sql_db_query` / `sql_db_schema`）及过程输出。同时主气泡内的 `task` 工具调用收敛为简洁的委派摘要徽章，彻底消除双份大段文本冗余。

**Blocked by:** 01 — 端到端子智能体流式作用域打标与状态隔离分流

**Status:** done

- [x] 新建 `frontend/src/components/chat/SubagentCard.vue` 组件，包含头部状态徽章、耗时显示、嵌入式独立 `ReasoningAccordion`、领域工具链展示与子智能体 Markdown 输出（复用 `renderMarkdown` 安全渲染）
- [x] 改造 `frontend/src/components/chat/MessageItem.vue`，在主气泡下方根据 `message.subagents` 动态挂载渲染 `SubagentCard` 列表
- [x] 改造主气泡内部的 `ToolCall` 渲染逻辑：当工具名称为 `task` 时，渲染为简洁的“委派子任务: <description>”摘要徽章，不展开庞大的冗余返回值
- [x] 保证所有图标、字体和样式全部本地化打包，100% 遵循离线无外网依赖约束
