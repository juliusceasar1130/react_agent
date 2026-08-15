# 01 — 后端中断协议身份透传与前端 Store 角色上下文打通

**What to build:**
后端在 LangGraph 中断（`AskUserQuestion`）时，自动根据子图上下文在 `InterruptStreamEvent` 中携带 `subagent_id` / `subagent_name` / `subagent_title`；前端流式协议层（类型定义、白名单、解析器）与 `messagesStore` 完整透传提问者元数据，为上层组件提供确切的智能体角色来源。

**Blocked by:** None — can start immediately

**Status:** done

- [x] 在 `backend/app/schemas.py` 的 `InterruptStreamEvent` 中增加 `subagent_id`, `subagent_name`, `subagent_title` 可选字段
- [x] 在 `backend/app/services/chat_service.py` 中捕获中断时提取当前子智能体身份并注入 `InterruptStreamEvent`
- [x] 在前端 `frontend/src/types/index.ts` 中更新 `InterruptStreamEvent` 类型
- [x] 在前端 `frontend/src/api/chat.ts` 中解析 `interrupt` 事件的 `subagent_id`, `subagent_name`, `subagent_title`
- [x] 在前端 `frontend/src/stores/messages.ts` 中记录提问者身份元数据
