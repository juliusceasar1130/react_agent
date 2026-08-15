# DeepAgent 多智能体架构设计评审与选型建议报告

> [!IMPORTANT]
> **文档状态**：🏛️ **核心架构决策 (ADR) / 权威基石**（确立否决 Supervisor 显式路由、采纳 `deepagents` 隐式工具调度与 Tool Artifact 安全透传的权威依据）。  
> **文档路径**：`docs/deepagent/architecture_review_report.md`  
> **全局索引**：[DeepAgent 文档中心](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/README.md)  
> **评审对象**：`docs/deepagent/generic_agent_architecture_report.md`  
> **评审时间**：2026-08-09  
> **基准参考文件与来源**：
> - LangChain / DeepAgents 官方文档: `https://docs.langchain.com/oss/python/deepagents/overview`
> - DeepAgents Middleware & Customization Guide: `https://docs.langchain.com/oss/python/deepagents/customization`
> - LangGraph Subgraph Streaming Docs: `https://docs.langchain.com/oss/python/langgraph/use-subgraphs`
> - 项目需求与依赖声明: [`requirements.txt`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/requirements.txt)
> - 项目开发约定与规范: [`AGENTS.md`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/AGENTS.md)
> - 本地架构 PoC 验证脚本: [`backend/app/agent/test_subagent_poc.py`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/backend/app/agent/test_subagent_poc.py)

---

## 一、 综合评审结论 (Executive Summary)

针对 `docs/deepagent/generic_agent_architecture_report.md` 提出的“从单一 Text-to-SQL Agent 升级为基于 `deepagents` 的通用智能体平台”方案，经过对照 **LangChain / DeepAgents 官方文档 (2026最新规范)**、**代码库依赖关系 (`requirements.txt`)** 及 **本地 PoC 验证结果 (`test_subagent_poc.py`)** 进行深度技术审计，结论如下：

1. **整体决策方向正确（高度肯定）**：
   - **否决 Supervisor 显式路由**：逻辑严密且完全符合生产最佳实践。Supervisor 额外引入 1 次 LLM 推理，会显著推迟首字响应时间（TTFT），且领域增加后分类 Prompt 同样膨胀。
   - **采纳 `deepagents` 选择性挂载 + 隐式工具路由**：架构立意准确。`deepagents` 0.7.5 作为 LangChain 官方演进的 Agent Harness，底层继承 LangGraph `create_agent` / `StateGraph`，能够完美兼容项目现有的 Postgres Checkpointer、SSE 流式解包与 HITL 中断恢复机制。
2. **技术栈与版本匹配度高**：
   - 依赖已成功升级并锁定为：`langchain 1.3.14` + `deepagents 0.7.5` + `langgraph 1.2.9` + `fastapi 0.127.1` + `pydantic 2.12.5`（已对照 `requirements.txt` 与本地 `inspect` 核实），包冲突完全解决，处于现代统一架构主线上。
3. **细化改进建议（需在实施中修正）**：
   - **虚拟文件系统工具控制机制修正**：经本地 `inspect` 核实 `deepagents 0.7.5` 真实签名，**不可通过 `excluded_middleware` 移除的是 `SubAgentMiddleware`**（移除会抛 `ValueError`），**而非** `FilesystemMiddleware`--后者不挂载即禁用。`create_deep_agent` **不存在** `filesystem=` 与 `excluded_tools=` 参数；文件系统可见工具通过 `FilesystemMiddleware(tools=[...])` **白名单**控制（可选工具集：`ls`/`read_file`/`write_file`/`edit_file`/`delete`/`glob`/`grep`/`execute`）。建议主 Agent 文件系统能力**完全开放**（`tools="all"`，含读写删），由主 Agent 直接产出文件产物；`execute`（代码执行）依赖沙盒，属范围外。
   - **子智能体上下文截断与 Tool Artifact 避坑**：子智能体返回主 Agent 的结果若过大（如几千条 SQL 数据），会导致主上下文溢出。必须强制规定 SQL 子智能体仅返回“文本总结 + Artifact 标识”，原始数据集通过 `tool_artifact` 结构化透传。
   - **双初始化路径保持同步**：`SQLAgentService` 的同步 `_initialize_agent` 与异步 `_ainitialize_agent` 必须 100% 同步装配 Subagent middleware。

---

## 二、 技术选型与四种候选架构深度对比 (Technical Comparison)

针对通用 Agent 平台的路由与组织形态，对报告提及的 4 种方案进行深入技术评判：

| 评估维度 | 方案 A：现状单 ReAct | 方案 B：Supervisor 显式路由 | 方案 C：自建子图工具隐式路由 | 方案 D：deepagents 选择性采纳（推荐） |
| :--- | :--- | :--- | :--- | :--- |
| **路由拓扑** | 单层 ReAct Loop，工具扁平 | StateGraph 分层拓扑，显式意图节点 | 主 Agent 挂载子图封装的 `@tool` | `create_deep_agent` + `SubAgentMiddleware` |
| **首字延迟 (TTFT)** | 基线 (1 次 LLM) | **退化 (2 次 LLM 串行)** | 基线 (1 次 LLM) | **基线 (1 次 LLM，零 TTFT 损耗)** |
| **上下文隔离性** | 差（SQL 试错污染全局） | 强（节点独立 State） | 强（子图内部独立 Context） | **极强（`SubAgent` 独立 Context 窗口）** |
| **系统复杂度与维护**| 极低，但能力受限 | 高（需维护分类节点及复杂 Edge） | 中（需自建 task 派发与 Todo） | **低（复用官方 Harness 维护的标准轮子）** |
| **LangGraph 兼容性**| 纯单图 | 需改写拓扑重接 Checkpointer | 原样兼容 | **100% 兼容 (底层即 LangGraph)** |
| **生产级特性支持** | 无 Task 规划 | 需自建 Task 状态 | 需自建 Task 状态 | **内置 SubAgent / Summarization / PatchToolCalls / Memory / HITL 全栈**（TodoList 属 `langchain.agents.middleware`） |

### 关键评测结论：
- **方案 B (Supervisor) 致命伤**：用户每次提问均触发 Supervisor LLM 判定领域，对于“查询底漆车间在制车”这类明确数据请求，额外增加 1.5s~3s 的分类延迟，严重破坏用户打字机体验。
- **方案 D (DeepAgents) 优势**：主 Agent 将子智能体作为 `task` 工具调用。模型通过 System Prompt 和工具描述，在第 1 次 ReAct 循环中直接选择目标子智能体，兼具**零 TTFT 延迟**与**完全上下文隔离**。

---

## 三、 官方 DeepAgents 核心机制与项目契约对齐 (Deep-dive Audit)

### 3.1 官方 Middleware 机制与项目特有 Middleware 融合
`deepagents` 提供了开箱即用的 Middleware 栈，项目自研的中间件与官方栈的集成策略如下：

1. **项目保留与挂载的自定义 Middleware**：
   - `BusinessRagMiddleware`：在 SQL / 知识库子智能体构建时注入业务术语与向量上下文。
   - `ContextWarningMiddleware`：在 Prompt 超过临界值时注入警告。
   - `PromptCompilerMiddleware`：合并 System Message 逻辑。
2. **`deepagents` 0.7.5 完整 Middleware 栈**（经本地 `inspect` `deepagents.middleware` 子模块 + 官方 customization 文档双向核实，以本地源码为准；默认栈首到尾顺序）：
   - `SkillsMiddleware`（仅传 `skills`）→ `FilesystemMiddleware` → `SubAgentMiddleware`（仅有同步子智能体时，`general-purpose` 默认自动添加）→ **`SummarizationMiddleware`**（`deepagents.middleware.summarization`，deepagents 自有，压缩消息历史）→ **`PatchToolCallsMiddleware`**（`deepagents.middleware.patch_tool_calls`，deepagents 独有，修复悬空 tool call / 中断时修补消息历史）→ 用户 `middleware=` → profile extras → 提示缓存 → `MemoryMiddleware`（仅传 `memory=`）→ `HumanInTheLoopMiddleware`（仅传 `interrupt_on=`）。
   - **⚠️ 纠错**：`SummarizationMiddleware` 与 `PatchToolCallsMiddleware` **确属 deepagents 默认栈**。前次评审误判为“不存在 / 仅属 langchain”，系只查 `dir(deepagents)` 顶层、漏查 `deepagents.middleware` 子模块所致，特此修正。`langchain.agents.middleware` 另有同名 `SummarizationMiddleware`（`service.py:27` 当前所用），与 deepagents 版**非同一类**（`is` 判定 False）；迁移后默认栈挂 deepagents 版。
   - `FilesystemMiddleware`：**可选**，不挂载即禁用。通过 `tools=` 白名单（>=0.7）或 `backend=`/`permissions=` 控制；传 `.name` 匹配实例可替换默认栈成员（需自行传 `backend`，`deepagents>=0.7`）。主 Agent 采**完全开放**（`tools="all"`）。
   - `SubAgentMiddleware`：**不可 `excluded_middleware` 移除**（抛 `ValueError`）；`create_deep_agent(subagents=[...])` 自动挂载。本地签名无官方示例的 `default_model`/`default_tools`。
   - `TodoListMiddleware`：**不在 deepagents 默认栈**，来自 `langchain.agents.middleware`，仅在 `DeepAnalyst` 子智能体内部按需挂载。

### 3.2 流式协议与前端解包机制 (`astream(subgraphs=True, version="v2")`)
- **后端解包逻辑**：
  在 FastAPI 服务层（`services.py`），调用 LangGraph 的 `astream(input, config=config, stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2")`。
  `version="v2"` 下每个 chunk 为 `StreamPart` dict（含 `type`/`ns`/`data`），**非 v1 的 `(namespace, chunk)` 元组**。子智能体事件经 `ns` 识别：主 Agent 为 `()`，子智能体为 `("tools:<task_call_id>",)`（namespace 是 `tools:<call_id>`，非子智能体 name）；判断任意层级子智能体：`any(s.startswith("tools:") for s in chunk["ns"])`。
- **前端无感透传与渐进增强**：
  后端解析 chunk 后：
  1. `chunk["type"]=="messages"` 时 `data=(token, metadata)`，token 打包为标准 SSE `data: {"type": "token", "content": "..."}`，保证现有打字机渲染零破坏；
  2. 检测到 `ns` 出现/切换 `tools:` 段时派发 `data: {"type": "subagent_change", ...}`；子智能体显示名需从 `task` 调用 args 的 `subagent_name` 或 run metadata `lc_agent_name` 映射，**不能直接从 namespace 取**；
  3. 前端在 `frontend/src/api/chat.ts` 的 `STREAM_EVENT_TYPES` 白名单 Set 中注册 `subagent_change` 与 `plan_update`，Pinia Store 据此驱动 `SubAgentBadge.vue` 组件渲染。

---

## 四、 关键实施建议与避坑指南 (Recommendations & Action Items)

### 1. 严格遵循项目代码规范 (`AGENTS.md`)
- **双初始化路径**：修改 `backend/app/agent/service.py` 时，必须同步修改同步 `_initialize_agent`（`service.py:606`，供 `start_langgraph_dev.bat` / LangGraph Dev 驱动）与异步 `_ainitialize_agent`（`service.py:632`，供 FastAPI 本地驱动）。当前两处均为 `create_agent`（:620 / :646），迁移时需同步改为 `create_deep_agent`。
- **静态资源 100% 本地化**：新增的前端组件（如 `SubAgentBadge.vue`、`TaskPlannerCard.vue`）严禁引用任何公网 CDN 字体或 CSS，图标一律采用本地 SVG / Lucide Vue Next。

### 2. 子智能体结果返回规范
- **防止 Tool Result 冲毁主上下文**：
  当 SQL 子智能体执行查询并返回大量 JSON 数据时，如果直接作为 Tool Result 文本返还给主 Agent，会导致主 Agent 上下文瞬间爆满。
  **约束规约**：SQL 子智能体的最终输出必须包含结构化 `tool_artifact`，而返回给主 Agent 的 text 仅为简明摘要（例如：“已成功为您查询底漆车间在制车数据，共 42 条，表格与图表已生成”）。

### 3. Human-In-The-Loop (HITL) 中断适配
- 当 SQL 子智能体因高危 SQL 或条件不全触发 LangGraph `interrupt()` 时，主 Graph 会暂停运行。
- 后端需捕获该中断状态并向前端发送 `interrupt` SSE 事件；前端通过 `InterruptModal.vue` 收集用户确认后，调用 `/api/chat/resume` 接口，以 `Command(resume=...)` 恢复 Graph 执行。

---

## 五、 总结与后项目落地路线

`docs/deepagent/generic_agent_architecture_report.md` 的架构方向（否决 Supervisor、采纳 deepagents 隐式路由）正确。但需注意：PoC 脚本 `backend/app/agent/test_subagent_poc.py` 实际验证的是 **`subagent.as_tool()` 把子图包装为普通 tool 挂载** 的路径 + `astream(subgraphs=True)` 元组解包，**并未使用 `SubAgentMiddleware`/`task`/`subagents=` 委派机制**；两者是不同的子智能体集成路径。正式实施前需补一个真正基于 `SubAgentMiddleware` + `CompiledSubAgent` + `task` 委派的 PoC，验证 `general-purpose` 兜底、namespace 隔离与 `interrupt_on` HITL 后，方可宣称方案 D 全线通过。

建议按照报告中规划的**三步走路线图**正式启动编码实施：
1. **阶段 1**：将主 Agent harness 升级为 `create_deep_agent`，封装 `SQLSubGraph` 子智能体，完成 backend 服务层 `(namespace, chunk)` 元组解包；
2. **阶段 2**：更新前端 SSE 白名单与 Pinia Store，上线 `SubAgentBadge.vue` 实时提示组件；
3. **阶段 3**：接入知识库 RAG 与 Deep Data Analyst 子智能体，引入 `TaskPlannerCard.vue` 支持多步骤规划展示。
