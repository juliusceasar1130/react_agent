# 04 — 历史会话与页面刷新完整回放

**What to build:**
子智能体会话（专属思考、过程输出、工具链）完整持久化到 `chat_messages.subagents` 列（`create_tables` 幂等 `ADD COLUMN IF NOT EXISTS` 迁移），`final` 事件随流携带快照落库；刷新或切换历史会话时优先还原完整快照，旧数据基于 `tool_calls` 中的 `subagent_id` 元数据兜底重构工具链。

**Blocked by:** 02 — 子智能体卡片（SubagentCard）组件与独立思考/工具链 UI 呈现

**Status:** done

- [x] 后端 `schemas.py`/`models.py`/`crud.py` 新增 `subagents` 列与 `MessageCreate.subagents` 字段，`database.py` 在 `create_tables()` 中执行幂等迁移
- [x] 后端 `chat_service.py` 在循环内按 task call_id 聚合子智能体会话（reasoning 增量去重 + content），`final` 事件携带完整快照；`routers/chat.py` 落库
- [x] 前端 `fetchMessages` 优先解析 `subagents` 快照，旧数据基于 `tool_calls` 按 `subagent_id` 聚合兜底重构
- [x] 验证端到端会话刷新与历史会话切换，确认历史子智能体卡片与 SQL 详情完整展示
