# 02 — SSE 流式工件溯源信封与前端多智能体工件池 (SSE Stream Envelope and Artifact Pool)

**What to build:**  
实现 SSE 流式阶段多子智能体工件的精准分流与前端独立槽位并存。后端在发射 `tool_artifact` 流式事件时，将当前的 `subagent_id`（子智能体任务 ID）、`subagent_name`（子智能体名称）以及 `tool_call_id`（工具调用唯一标识）封装入事件信封。前端 Pinia Store 将工件存储从单值字典升级为以 `tool_call_id` 为唯一索引的多工件字典池（Artifact Pool）。在多个子智能体并发绘图或同一会话中连续触发“查表 + 绘图 + 导出”时，所有卡片在界面上独立并存展示，彻底消除实时流式阶段的翻牌式冲刷覆盖。

**Blocked by:** 01 — 历史工件持久化与 F5 刷新全量复原闭环 (Artifact Persistence and Replay)

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 后端 `chat_service.py` 在发射 `tool_artifact` SSE 事件时，携带 `subagent_id`、`subagent_name` 与 `tool_call_id` 溯源字段
- [ ] 前端 `api/chat.ts` 与 `types/index.ts` 扩展 `ToolArtifactStreamEvent` 类型契约
- [ ] 前端 Pinia Store (`messages.ts`) 与 `useChatStream.ts` 升级为以 `tool_call_id` 唯一索引的多工件字典池 `memoryArtifactPool`，废弃易碰撞的单值覆盖
- [ ] 前端 `MessageItem.vue` 在流式阶段支持多工件独立并存展示，多子智能体并发绘图或链式工具调用时卡片不发生互相顶替
- [ ] 大模型打字机流式输出完成后，工件展示平滑过渡到 Ticket 01 的持久化状态，体验无缝对齐
