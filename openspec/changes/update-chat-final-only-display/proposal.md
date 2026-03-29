# Change: 默认仅展示聊天最终结论

## Why

当前前端会把流式过程状态、工具调用和工具结果直接展示在聊天消息中，导致单轮问答信息密度过高，普通用户难以快速抓住最终结论。

## What Changes

- 调整聊天前端展示策略，默认仅展示最终回答内容
- 保留顶部轻量状态提示，用于生成期间的即时反馈
- 将工具调用、工具结果和错误细节降级为内部调试信息，通过前端调试开关控制显示
- 保持现有后端结构化流式协议与消息落库字段不变

## Impact

- Affected specs: `chat-ui`
- Affected code:
  - `frontend/src/components/MessageItem.vue`
  - `frontend/src/views/ChatView.vue`
  - `frontend/src/stores/messages.ts`
  - `frontend/src/composables/useChatStream.ts`
  - `frontend/src/config/chat.ts`
