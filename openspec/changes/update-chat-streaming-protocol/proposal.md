# Change: 升级聊天流式协议与前端消费链路

## Why

当前聊天流式链路仍停留在“纯文本增量 + 最终块补工具信息”的模式，难以稳定解析 SSE、难以展示工具执行过程，也无法充分利用 LangChain / LangGraph 官方 streaming 的多模式能力。

## What Changes

- 将 `/api/chat/stream` 的 SSE 负载从旧版 chunk 协议升级为结构化事件协议
- 后端切换到 LangGraph `version="v2"` 多模式 streaming，并透传 token / status / tool_call / tool_result / final / error 事件
- 前端重写 SSE 解析逻辑，改为事件驱动的流式状态管理与展示
- 为流式消息增加阶段状态、工具调用、工具结果与错误态展示

## Impact

- Affected specs: `sql-agent`
- Affected code:
  - `backend/app/services.py`
  - `backend/app/api.py`
  - `backend/app/schemas.py`
  - `frontend/src/api/chat.ts`
  - `frontend/src/stores/messages.ts`
  - `frontend/src/composables/useChatStream.ts`
  - `frontend/src/components/MessageItem.vue`
