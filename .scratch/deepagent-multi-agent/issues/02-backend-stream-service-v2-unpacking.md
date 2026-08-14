# 02 — 服务层 StreamPart 流式 v2 字典解包与领域切换事件派发

**What to build:**  
在现行的 `backend/app/services.py` 中，升级 `astream` 调用的模式与版本为 `stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2"`。增加字典类型判断，解析 `chunk["ns"]`。当识别到 `ns` 包含 `tools:<call_id>` 时，判定进入子智能体输出阶段，向 SSE 队列派发包含 `active_subagent: "sql_domain_agent"` 的 `subagent_change` 事件。

**Blocked by:** 01 — 后端 Agent 核心引擎升级 (create_deep_agent + CompiledSubAgent)

**Status:** COMPLETED

- [x] `services.py` 中升级 `astream` 声明为 `subgraphs=True, version="v2"`
- [x] 增加 `chunk` 字典 `ns` 提取与子智能体识别逻辑
- [x] 状态切换时向 SSE 事件队列推送 `subagent_change` 事件
- [x] 维持既有 `token` 打字机与 `tool_artifact` 事件推送不受影响
