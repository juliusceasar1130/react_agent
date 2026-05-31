# 持久化模式与流式协议

> 从 CLAUDE.md 迁出，在修改 Agent 持久化逻辑或 SSE 协议时读取。

## 持久化模式

项目是"双模式"持久化，不应只按旧版同步 `PostgresSaver` 理解：

- **FastAPI 本地模式**：
  - 使用 `AsyncConnectionPool + AsyncPostgresSaver`
  - 由 `backend/app/services.py` 启动阶段显式初始化
- **LangGraph 托管 / Dev 模式**：
  - graph 由 `backend/app/agent/service.py:build_agent_graph()` 提供
  - `checkpointer/store` 由 LangGraph 运行时托管注入或接管

### 关键约定

- 所有 Agent 调用都必须传递 `config["configurable"]["thread_id"] = session_id`
- 自动历史管理依赖 checkpointer，不需要手工回放历史消息
- `SummarizationMiddleware`（来自 `langchain.agents.middleware`，非项目自定义）仍在使用，但只是众多中间件之一

## 流式协议

`/api/chat/stream` 已升级为结构化 SSE 事件协议，不再以旧版 `content + is_final` 为主。

### 核心事件类型

- `token`
- `status`
- `tool_call`
- `tool_result`
- `final`
- `error`

### 行为约定

- 前端默认只重点展示最终答案
- 过程事件主要用于轻量状态提示和调试
- `final` 事件中会聚合最终文本、工具调用和工具结果
