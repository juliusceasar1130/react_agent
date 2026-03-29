## 1. Implementation

- [x] 1.1 为聊天流式输出新增结构化事件协议与 OpenSpec 规范说明
- [x] 1.2 升级后端 `services.py` 使用 LangGraph v2 多模式 streaming
- [x] 1.3 调整 `/api/chat/stream` 以透传事件并在 `final/error` 路径正确落库
- [x] 1.4 重写前端 SSE 解析与 `StreamEvent` 类型定义
- [x] 1.5 改造消息 store / composable / UI，使流式消息支持阶段状态、工具调用、工具结果和错误态
- [x] 1.6 完成关键路径验证并同步 README / changelog
