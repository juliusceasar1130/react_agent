# 01 — 端到端子智能体流式作用域打标与状态隔离分流

**What to build:**
打通后端到前端的端到端流式作用域管道。当主 Agent 委派任务时，后端识别流式命名空间中的 `tools:<call_id>` 并结合委派元数据为 SSE 流式事件附加 `subagent_id`（task 的 call_id）和 `subagent_name`（如 `sql_domain_agent`）；前端 SSE 解析器四处同步解析，并在 Pinia Store 中按 `subagent_id` 将子智能体的思考内容、工具调用和过程输出分流到独立的 `SubagentSessionState` 槽中，彻底杜绝与主 Agent 的状态混杂。

**Blocked by:** None — can start immediately

**Status:** done

- [x] 后端 `schemas.py` 为 `TokenStreamEvent`、`ReasoningStreamEvent`、`StatusStreamEvent`、`ToolCallStreamEvent`、`ToolResultStreamEvent` 增加 `subagent_id`, `subagent_name` 可选字段（序列化 `exclude_none=True` 保证向后兼容）
- [x] 后端 `chat_service.py` 在 `astream` 循环中解析 `ns`（以 `tools:<call_id>` 查 `active_task_targets` 为主；未知 call_id 不打标并告警，name 兜底不猜测 call_id），在事件分发时注入 `subagent_id` 与 `subagent_name`
- [x] 前端 `types/index.ts` 新增 `SubagentSessionState` 接口，并为 `StreamEvent` 联合类型、`StreamingMessage`、`Message` 扩展 `subagents: Record<string, SubagentSessionState>` 映射
- [x] 前端 `api/chat.ts` 在 `STREAM_EVENT_TYPES` 白名单与 `parseStreamEvent` 分支中同步解析 `subagent_id`、`subagent_name`
- [x] 前端 `stores/messages.ts` 与 `composables/useChatStream.ts` 在处理思考、工具与内容事件时，根据 `subagent_id` 路由到对应 Subagent 的状态槽，工具调用按子智能体会话内 id upsert 去重累加
