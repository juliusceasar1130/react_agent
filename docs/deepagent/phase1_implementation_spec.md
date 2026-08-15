# 第一阶段：DeepAgent 多智能体核心功能落地与全链路验证规范 (Phase 1 Spec)

> [!NOTE]
> **文档状态**：🚀 **已落地基线 / Phase 2 演进参考**（Phase 1 核心多智能体机制已全面落地，作为后续 Phase 2 接入知识库与高级分析子智能体的基线范式）。  
> **文档路径**：`docs/deepagent/phase1_implementation_spec.md`  
> **全局索引**：[DeepAgent 文档中心](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/README.md)  
> **关联规范**：`openspec/changes/deepagent-multi-agent-system/phase1_spec.md`  
> **更新时间**：2026-08-09  
> **技术栈基线**：`deepagents 0.7.5` + `langchain 1.3.14` + `langgraph 1.2.9` + `fastapi 0.127.1` + `Vue 3.4`

---

## 问题陈述 (Problem Statement)

系统当前依赖单 ReAct 循环 (`create_agent`)，所有的 SQL 工具、Prompt 规则与全局上下文强行平铺在单一对话窗口中。随着扩展需求增加，系统面临 Prompt 膨胀、SQL 工具误召回、中间试错历史污染主窗口以及高成本模型浪费等问题。

在此第一阶段，我们需要在**保持现有物理文件结构与 HTTP 接口契约完全不变**的前提下，将主 Agent 升级为 `create_deep_agent`，将现有的 Text-to-SQL 逻辑隔离封装为首个专业子智能体 (`sql_domain_agent`)，在服务端实现 LangGraph 流式 v2 字典解包，并在前端聊天界面渲染实时智能体徽章。

---

## 解决方案 (Solution)

在现行代码结构（`backend/app/agent/service.py`、`backend/app/services.py` 及 `frontend/src/`）中实施第一阶段升级：

1. **主 Agent 升级 (`create_deep_agent`)**：将 `SQLAgentService` 的核心 Agent 工厂升级为 `create_deep_agent`，继承默认全量开放的虚拟文件系统 `FilesystemMiddleware`（严禁在根函数传参 `tools="all"`，仅用于接收自定义 `BaseTool` 列表）。
2. **SQL 子智能体封装 (`CompiledSubAgent`)**：将现有的 SQL 工具集与 SQL Prompt 编译为独立的子图 (`sql_subgraph`)，并包装为 `CompiledSubAgent(name="sql_domain_agent", runnable=sql_subgraph)`，直接传入主 Agent 的 `subagents=[...]` 参数（由 `deepagents` 框架自动注入 `SubAgentMiddleware` 与 `task` 工具，无需手动配置）。
3. **中间件精准分层与单点 RAG 继承**：将包含业务术语与三层数据库物理词典（`table_schema_store`, `db_value_lexicon`, `db_row_lexicon`）的 `BusinessRagMiddleware` **统一装配在主 Agent 侧**；利用 `deepagents` 状态深拷贝机制将检索到的 `lexicon_context` 自动透传给 SQL 子智能体，子智能体通过 `PromptCompilerMiddleware` 无缝注入 Prompt（详见 `docs/deepagent/rag_single_retrieval_spec.md`）。
4. **服务端流式 v2 解包与事件派发**：在 `services.py` 中升级 `astream` 参数为 `subgraphs=True, version="v2"`。解析 StreamPart 字典 `{"ns": ..., "type": ..., "data": ...}`。当 `ns` 包含 `"tools:<call_id>"` 时识别为子智能体执行阶段，向前端派发 `subagent_change` SSE 事件。在 `backend/app/schemas.py` 注册 `SubagentChangeStreamEvent` 至 Pydantic `ChatStreamEvent` 联合校验器。
5. **前端状态感知与 UI 徽章**：在 `types/index.ts` 中扩充 `Message` 接口的 `active_subagent` 字段，在 `api/chat.ts` 白名单集合中注册 `subagent_change`，并挂载全新的 `SubAgentBadge.vue` 组件，展示 `🤖 [SQL数据助手]`。

---

## 用户故事 (User Stories)

1. **SQL 试错上下文隔离**：作为企业数据分析师，我希望 SQL 查询生成与语法试错在 SQL 子智能体的独立上下文窗口中完成，以便主对话历史保持干净高效。
2. **通用闲聊自动兜底**：作为普通用户，当我进行日常打招呼或通用知识问答时，我希望系统通过 `general-purpose` 兜底子智能体或主 Agent 直接极速回答，以便不触发无谓的数据库工具。
3. **实时 Agent 状态可视化**：作为前端聊天用户，我希望在消息气泡上方看到当前正在工作中的 Agent 徽章（如 `🤖 [SQL数据助手]`），以便实时感知后台流水线进度。
4. **流式 Token 打字机兼容**：作为前端用户，我希望在多智能体切换时打字机流式输出不发生断流、卡顿或乱码，以便获得流畅的交互体验。
5. **安全截断与 Artifact 渲染**：作为前端用户，我希望 SQL 执行返回的结果能通过 `tool_artifact` 渲染为图式与数据表格，而不会将成千上万行原始 JSON 塞入对话框。
6. **HITL 人机协作交互**：作为数据安全管理员，当 SQL 子智能体触发高危数据库操作或需要用户澄清时，我希望界面弹出确认框并支持一键恢复运行。

---

## 实施决策 (Implementation Decisions)

### 1. 修改的模块与接口职责 (Modules & Interfaces)
- **`backend/app/agent/service.py` (Core Agent Engine)**：
  - 将主 Agent 实例化逻辑从 LangChain `create_agent` 切换为 `create_deep_agent`（不传 `tools="all"`）。
  - 同步更新 `_initialize_agent`（LangGraph CLI / Dev 同步路径）与 `_ainitialize_agent`（FastAPI 异步路径）。
  - 精准进行中间件分层：将包含三层物理词典的全量 `BusinessRagMiddleware` 挂载在主 Agent 入口处；`SkillMiddleware` 与 `PromptCompilerMiddleware` 挂载给子智能体，子智能体直接透传读取父 State 的 `lexicon_context`；`call_limit_middlewares` 在主/子 Agent 双重挂载防死循环。
- **`backend/app/schemas.py` & `backend/app/services.py` (FastAPI Service & Validation Layer)**：
  - `schemas.py`: 新增 `SubagentChangeStreamEvent` 与 `PlanUpdateStreamEvent` 模型并注册到 `ChatStreamEvent` 联合类型与 `_chat_stream_event_adapter`。
  - `services.py`: 在 `_stream_execution_loop` 中升级 `astream(input_data, config=config, stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2")`。
  - 增加字典类型判断：当 `chunk` 为 `dict` 且 `chunk["ns"]` 包含 `tools:` 段时，映射 `subagent_name="sql_domain_agent"`，推送到 SSE 事件队列。
- **`frontend/src/` (Vue 3 Frontend)**：
  - `types/index.ts`：扩展 `Message` 接口的 `active_subagent?: string` 属性。
  - `api/chat.ts`：在 `STREAM_EVENT_TYPES` 白名单 Set 中添加 `'subagent_change'` 和 `'plan_update'`。
  - `components/SubAgentBadge.vue`：新建基于本地 Lucide Vue Next 图标的轻量徽章组件。
  - `components/MessageItem.vue`：在消息头部集成 `SubAgentBadge.vue`。

### 2. 原型验证出的关键数据契约 (Prototype Type Shapes)

#### A. 主 Agent 与 CompiledSubAgent 注册原型 (来自 `test_compiled_subagent_v2_poc.py`)
```python
# SQL 领域子图构建
sql_subgraph = create_agent(
    model=llm_instance,
    tools=sql_tools,
    system_prompt=SQL_SYSTEM_PROMPT,
    middleware=subagent_middleware_list, # 包含 BusinessRagMiddleware, SkillMiddleware, PromptCompilerMiddleware
)

# 包装为 CompiledSubAgent 挂载入 subagents
sql_compiled_subagent = CompiledSubAgent(
    name="sql_domain_agent",
    description="【SQL 领域专家子智能体】专用于处理与数据库查询、统计分析相关的请求。",
    runnable=sql_subgraph
)

# 主 Agent 实例化 (框架自动挂载 SubAgentMiddleware + task 工具 + FilesystemMiddleware)
main_agent = create_deep_agent(
    model=llm_instance,
    subagents=[sql_compiled_subagent],
    middleware=main_middleware_list, # 包含 BusinessRagMiddleware, SummarizationMiddleware, ContextWarningMiddleware
    checkpointer=checkpointer,
)
```

#### B. 流式 v2 字典解包原型
```python
# StreamPart 结构: {"type": "messages"|"updates"|"custom", "ns": ("tools:call_id",), "data": ...}
if isinstance(chunk, dict):
    ns = chunk.get("ns", ())
    chunk_type = chunk.get("type")
    data = chunk.get("data")
    
    # 子智能体领域识别
    is_subagent = any(segment.startswith("tools:") for segment in ns)
    if is_subagent and current_subagent != "sql_domain_agent":
        current_subagent = "sql_domain_agent"
        yield format_sse_event("subagent_change", {"active_subagent": current_subagent, "display_name": "SQL数据助手"})
```

---

## 测试决策 (Testing Decisions)

### 1. 测试切缝 (Test Seams)
- **核心解包切缝**：FastAPI `services.py` 中的 `_stream_execution_loop` 解析 `astream(subgraphs=True, version="v2")` 的 StreamPart 字典。
- **子智能体隔离切缝**：直接针对 `sql_subgraph` 输入 SQL 提问，验证其上下文独立性。

### 2. 行为测试准则 (Behavior-Focused Testing)
- **正向 Text-to-SQL 测试**：提问“底漆车间在制车数量”，验证主 Agent 是否正确委派给 `sql_domain_agent`，并正确返回数据与 `tool_artifact`。
- **流式 SSE 协议测试**：通过 HTTP SSE 客户端调取 `/api/v1/chat/stream`，验证接收到 `subagent_change`、`token` 及 `tool_artifact` 事件的顺序与结构。
- **HITL 中断与恢复测试**：测试高危操作触发 `interrupt()` 后返回 `type: interrupt` 事件，且调用 `/api/v1/chat/resume` 恢复运行。

### 3. 参考先例 (Prior Art)
- [`backend/app/agent/test_compiled_subagent_v2_poc.py`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/backend/app/agent/test_compiled_subagent_v2_poc.py)：已全量验证 `create_deep_agent` + `subagents=[CompiledSubAgent(...)]` + `astream(version="v2", subgraphs=True)` 字典解包 100% 成功。

---

## 范围外事项 (Out of Scope)

1. **物理目录搬家与解耦**：将 `api.py` 拆分为 `routers/`、将 `services.py` 拆分为 `services/` 及物理子目录划分移至**第二阶段**。
2. **多租户 Docker 沙盒**：文件系统依然基于本地 `StateBackend`，暂不引入云端容器沙盒。

---

## 补充说明 (Further Notes)

- 修改 `backend/app/agent/service.py` 时，必须确保 `_initialize_agent`（同步路径）与 `_ainitialize_agent`（异步路径）修改完全一致。
- 所有前端 UI 代码严格遵循离线部署原则（`AGENTS.md`），严禁使用公网 CDN 静态资源。
