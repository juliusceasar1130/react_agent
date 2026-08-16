# 01 — 历史工件持久化与 F5 刷新全量复原闭环 (Artifact Persistence and Replay)

**What to build:**  
实现会话工件的端到端持久化与历史回放闭环。当用户在聊天中执行 SQL 数据查询、生成 ECharts 图表或导出 CSV 文件后，服务端在生成结束时将该轮对话产生的所有工件数据（表格、图表、文件元数据）原子持久化到数据库中。用户在按 F5 刷新浏览器或切换历史会话时，消息组件直接从消息记录中读取工件数据，实现 ECharts 图表、CSV 下载按钮与 SQL 预览表格的 0 秒即时、100% 完整原样复原。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 数据库模型 `ChatMessage` 与响应 Schema `MessageResponse` 扩展 `tool_artifacts` 字段（JSON 格式文本）
- [ ] 后端在会话流式执行完成（`final` 事件）时，将当轮收集到的所有工件集合原子写入 `chat_messages.tool_artifacts` 列
- [ ] 前端 `MessageItem.vue` 直接基于 `message.tool_artifacts` 渲染 `sqlQueryResult`（SQL 表格）、`chartSpec`（ECharts 图表）与 `fileExport`（CSV 下载卡片）
- [ ] 用户在生成图表、导出 CSV 或查询 SQL 数据后，按 F5 刷新页面，图表、下载按钮与数据表格 100% 完整显示且功能正常
- [ ] 编写自动化测试覆盖 `tool_artifacts` 的数据库 CRUD 读写与接口反序列化
