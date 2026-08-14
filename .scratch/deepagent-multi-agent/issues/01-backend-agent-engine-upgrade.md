# 01 — 后端 Agent 核心引擎升级 (create_deep_agent + CompiledSubAgent)

**What to build:**  
在现行的 `backend/app/agent/service.py` 中，将主 Agent 工厂升级为 `create_deep_agent`，配置 `tools="all"` 完全开放虚拟文件系统；将现有的 SQL 工具与 Prompt 隔离编译为 SQL 子图 (`sql_subgraph`)，并包装为 `CompiledSubAgent(name="sql_domain_agent", runnable=sql_subgraph)` 直接传入 `subagents=[...]` 参数。同步更新 `_initialize_agent`（同步路径）与 `_ainitialize_agent`（异步路径）。

**Blocked by:** None — can start immediately

**Status:** COMPLETED

- [x] 导入 `create_deep_agent` 与 `CompiledSubAgent` 取代原 `create_agent`
- [x] 隔离构建 SQL 子图 (`sql_subgraph`) 并用 `CompiledSubAgent` 包装
- [x] 主 Agent 装配 `create_deep_agent(tools="all", subagents=[sql_compiled_subagent])`
- [x] 保持 `_initialize_agent` 与 `_ainitialize_agent` 100% 同步装配
- [x] 运行 `test_compiled_subagent_v2_poc.py` 验证实例化正常
