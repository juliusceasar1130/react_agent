# DeepAgent 通用多智能体系统 (Generic Multi-Agent System) 规范文档 (Spec)

> **文档路径**：`openspec/changes/deepagent-multi-agent-system/spec.md`  
> **关联文档**：`docs/deepagent/multi_agent_system_spec.md`  
> **更新时间**：2026-08-09  
> **重构策略**：功能优先（在现行目录中跑通核心功能），而后物理解耦（纯代码搬家）  
> **技术栈基线**：`deepagents 0.7.5` + `langchain 1.3.14` + `langgraph 1.2.9` + `fastapi 0.127.1` + `Vue 3.4`

---

## 一、 问题陈述 (Problem Statement)

系统当前的核心形态是单一 Text-to-SQL 智能体，后端基于 LangChain `create_agent` 单 ReAct 循环。随着系统向通用企业级智能体平台 (Generic Enterprise Agent System) 演进，需要逐步接入业务文档知识库 (RAG)、数据分析研报 (Python/ECharts) 和日常闲聊/通用问答等多领域能力。

如果直接在现有的单 ReAct 循环中继续叠加非 SQL 工具与 Prompt，系统会面临以下痛点：
1. **Prompt 膨胀与指令冲突**：当 System Prompt 同时包含 SQL 语法规约、RAG 规则与闲聊人设时，模型注意力被严重分散 (Context Collapse)，导致 SQL 准确率骤降。
2. **Tool 召回率降级**：工具数量过多导致 LLM 在选择工具时发生误判或无限死循环。
3. **上下文试错污染**：SQL 执行中的错误尝试和试错历史无法被隔离，直接占据主对话窗口 Token 空间。
4. **统一大模型成本高**：日常闲聊与简单的问答如果强制使用与 SQL 复杂推理相同的高成本大模型，会导致严重的 Token 成本浪费与 TTFT 延迟增长。

---

## 二、 解决方案 (Solution)

基于 **`deepagents 0.7.5` + LangGraph 1.2.9** 升级系统架构，从“单一 Text-to-SQL Agent”升格为“基于 `create_deep_agent` 的通用多智能体平台”：

1. **主 Agent Harness (`create_deep_agent`)**：作为系统的全局编排者，负责隐式工具路由、全局文件系统规划（`tools="all"` 完全开放文件读写）与对话历史自动摘要。
2. **隐式工具路由（零 TTFT 损耗）**：主 Agent 通过内置 `SubAgentMiddleware`（`task` 工具）调度子智能体，摒弃显式 Supervisor 意图分类节点，消除额外的 LLM 推理延迟。
3. **专业领域子智能体切分**：
   - **SQL 领域子智能体 (`SQLSubGraph`)**：封装为 `CompiledStateGraph`，拥有独立的上下文窗口，专门处理 Text-to-SQL、图表生成与 CSV 导出。
   - **日常对话子智能体 (`GeneralChatSubAgent`)**【预留·当前阶段暂不实施】：以轻量级声明式字典（Dict）形式定义，支持独立指定更低成本/更快响应的小模型 (`model="openai:gpt-4o-mini"`)。当前阶段仅落地 SQL 子智能体；闲聊/通用问答由 `SubAgentMiddleware` 默认 `general-purpose` 兜底子智能体承接。
4. **FastAPI SSE 流式解包**：服务层在 `.astream(..., subgraphs=True)` 中解析 StreamPart 字典 `{"ns": ..., "type": ..., "data": ...}`，实时透传 Token 与派发 `subagent_change` 领域切换事件。
5. **前端 UI 渐进增强**：Vue 3 前端注册流式事件白名单，通过 `SubAgentBadge.vue` 实时展示激活中的 Agent（如 `🤖 [SQL数据助手]`），保持现有打字机与 `tool_artifact` 渲染 100% 兼容。

---

## 三、 用户故事 (User Stories)

1. **SQL 领域查询隔离**：作为企业数据分析师，我希望将复杂数据查询委派给专门的 SQL 子智能体，以便 SQL 生成与语法试错在独立的上下文窗口中运行，不污染整体对话。
2. **日常对话零延迟**：作为普通用户，我希望日常闲聊、问候与通用知识问答能被快速响应，以便在不触发复杂数据库工具的情况下获得极速打字机体验。
3. **多模型独立降本**：作为系统架构师，我希望能够为日常对话子智能体配置低成本轻量模型，同时为 SQL 推理保留高能力模型，以便在保障质量的同时大幅降低 Token 成本。
4. **实时智能体感知**：作为前端用户，我希望在聊天界面上看到当前正在响应的子智能体徽章，以便清楚了解系统当前的执行流水线。
5. **全局文件系统规划**：作为高级分析师，我希望主 Agent 保留虚拟文件读写与草稿规划能力，以便后续直接生成长篇分析研报与文件产物。
6. **海量数据安全截断**：作为数据安全管理员，我希望 SQL 子智能体只向主 Agent 返回简明文本总结和 `tool_artifact` 结构化对象，以便海量原始数据不刷爆模型上下文。
7. **人机协作 (HITL) 中断确认**：作为数据安全管理员，当 SQL 子智能体触发高危 SQL 或条件不全时，我希望收到确认弹窗并可通过接口恢复运行，以便严格把控系统安全。

---

## 四、 实施决策与目录结构 (Implementation & Directory Structure)

### 1. 主 Agent 架构与 Middleware 分层装配
- 使用 `create_deep_agent` 作为系统主 Agent 入口（签名经本地 `inspect` 核实，以本地 0.7.5 源码为准）。
- **工具参数与 `FilesystemMiddleware` 规则**：
  - `create_deep_agent` 默认已自动装配包含 `ls`/`read_file`/`write_file`/`edit_file`/`delete`/`glob`/`grep`/`execute` 等全量文件读写能力的原生 `FilesystemMiddleware`；
  - 根函数的 `tools` 参数仅用于接收自定义 `BaseTool` 列表。**严禁在根函数传参 `tools="all"`**（否则会导致 `SubAgentMiddleware` 误将其作为字符串序列传入 `general-purpose` 子智能体，引发 `AttributeError: 'function' object has no attribute 'name'` 报错）。
- **主 Agent Middleware 管道（全局长会话管理与全量 RAG 编排）**：
  - `SubAgentMiddleware`（deepagents）：框架自动挂载 `task` 委派工具，提供运行时隐式路由。
  - `FilesystemMiddleware`（deepagents）：默认完全开放沙箱文件读写能力，主 Agent 可直接产出文件产物。
  - `BusinessRagMiddleware`（项目自研）：包含业务术语、同义词与三层数据库物理词典向量检索（主 Agent 可直接回答概念问题或带词典编排 Task）。
  - `RagPromptInjectorMiddleware`（项目自研）：轻量级 Prompt 注入中间件，毫秒级将 RAG 召回内容编译注入主 Agent 的 System Prompt `<runtime_context>` 动态区。
  - `SummarizationMiddleware`（deepagents）：长对话多轮历史 Token 压缩与窗口管理。
  - `ContextWarningMiddleware`（项目自研）：全局 Session 级上下文 Token 告警。
  - `call_limit_middlewares`（ModelCallLimitMiddleware / ToolCallLimitMiddleware）：主 Agent 路由编排防死循环熔断。

- **子智能体 (sql_subgraph) Middleware 管道（领域专属与上下文隔离）**：
  - `SkillMiddleware`（项目自研）：动态挂载场景技能 Prompt。
  - `PromptCompilerMiddleware`（项目自研）：继承主 Agent 深拷贝透传的 `state.lexicon_context`，合并表 DDL、字段注释、数据库词典与全量 SQL 工具历史消息裁剪/折叠至子 System Prompt（子智能体不挂载 `BusinessRagMiddleware`，避免重复检索与指令噪声）。
  - `call_limit_middlewares`（ModelCallLimitMiddleware / ToolCallLimitMiddleware）：子智能体 SQL 工具调用与语法试错防死循环熔断。

### 2. 子智能体声明与注册范式
- **范式 B（CompiledSubAgent + `task` 委派 —— SQL 领域，生产范式）**：
  将 `SQLAgentService` 的 SQL 工具集与 Prompt 封装为 `SQLSubGraph`（`CompiledStateGraph`），再用 `CompiledSubAgent(name="sql_domain_agent", description="...", runnable=sql_subgraph)` 包装，通过 `create_deep_agent(subagents=[...])` 注入主 Agent——**框架自动挂载 `SubAgentMiddleware` + `task` 工具，无需手动加 `middleware=[SubAgentMiddleware(...)]`**。
- **任务委派协议规范 (Task Delegation Protocol)**：
  - **主子职责分离**：主 Agent 在调用 `task` 工具时，仅传递用户的【业务目标】、【业务意图】、【业务过滤条件】与【期望产物格式】，**严禁强行硬编码指定数据库物理表名、视图名或具体的 SQL 语法**（由 SQL 子智能体自主进行最优表推导与 Schema 自愈）。
  - **自适应探索授权**：若用户提问模糊或存在多数据源选择，主 Agent 会在 `task.description` 中自动包含探查授权：“*该需求属于探索性查询，请充分利用 search_db_value_lexicon 和物理词典工具探查数据落地点与列值映射后再生成 SQL。*”

### 3. 流式协议与 FastAPI 服务层/Schema 序列化规范
- 服务层调用 `astream(input, config=config, stream_mode=["messages", "updates", "custom"], subgraphs=True, version="v2")`。
- **v2 解包契约**：每个 chunk 为 `StreamPart` dict，含 `type`/`ns`/`data` 三键。子智能体事件经 `ns` 识别——主 Agent 为 `()`，子智能体为 `("tools:<task_call_id>",)`。
- **Pydantic Schema 校验契约 (`backend/app/schemas.py`)**：
  服务端新增流式事件（如 `subagent_change` 和 `plan_update`）时，**必须在 `schemas.py` 中定义对应的 `BaseModel` 并注册到 `ChatStreamEvent` 联合类型与 `_chat_stream_event_adapter` 中**，否则 API 层的 `_encode_sse` 会抛出 Pydantic `ValidationError`。

### 4. 目标前后端重构目录结构对齐

#### 4.1 后端目录结构 (`backend/app/`)
```text
backend/app/
├── main.py                        # FastAPI 应用入口（路由挂载与生命周期管理）
├── config.py / database.py        # 全局配置与 SQLAlchemy 依赖注入
├── models.py / schemas.py / crud.py # 数据模型、Pydantic Schema 与 CRUD
│
├── routers/                       # 📂 从 api.py 解耦出的领域路由层 (重构阶段二解耦)
│   ├── __init__.py                # 路由统一导出与挂载
│   ├── chat.py                    # SSE 聊天与 Resume 端点
│   ├── sessions.py                # 会话管理 CRUD 端点
│   ├── skills.py                  # 技能配置端点
│   └── system.py                  # 健康检查与系统端点
│
├── services/                      # 📂 解耦出的服务控制层 (重构阶段二解耦)
│   ├── chat_service.py            # 主会话控制与 Agent 生命周期
│   └── stream_service.py          # astream(subgraphs=True) (namespace, chunk) 解包与 SSE 格式化
│
├── agent/                         # 📂 DeepAgent 核心模块 (重构阶段一落地方向)
│   ├── service.py                 # 主 Agent 工厂 (双初始化路径: _initialize_agent / _ainitialize_agent)
│   ├── state.py                   # DeepAgentState 全局图状态
│   ├── llm.py                     # LLM 适配器与 ReasoningAwareChatDeepSeek
│   │
│   ├── subagents/                 # 🚀 多领域子智能体核心目录 (重构阶段二创建)
│   │   ├── __init__.py            # CompiledSubAgent 导出清单
│   │   ├── sql/                   # 📊 SQL 领域子智能体 (SQLSubGraph)
│   │   │   ├── agent.py           # CompiledSubAgent 声明与子图编排
│   │   │   ├── tools.py           # wrapped_sql_query, build_chart_artifact, export_to_csv
│   │   │   └── prompts.py         # SQL 专属 Prompt 模板
│   │   └── chat/                  # 💬 预留：日常对话/闲聊子智能体 (GeneralChatSubAgent)
│   │       ├── agent.py           # 声明式字典/轻量模型配置
│   │       └── prompts.py         # 闲聊人设 Prompt
│   │
│   ├── middleware/                # Agent 中间件层 (Skill, RAG, Warning, Prompt)
│   ├── tools/                     # 共享工具集 (AskUserQuestion, sql_lexicon_tools)
│   └── vector/                    # 向量检索实现 (PGVector / Milvus)
│
└── skills/                        # 业务领域技能 (Domain & Scenario Skills 核心资产)
```

#### 4.2 前端目录结构 (`frontend/src/`)
```text
frontend/src/
├── api/                           # 📂 API 与 SSE 通信层 (chat.ts 注册 STREAM_EVENT_TYPES)
├── types/                         # 📂 TypeScript 类型中心 (Message, SubAgentTrace, ToolArtifact)
├── stores/                        # 📂 Pinia Setup Stores (messages.ts, sessions.ts)
├── composables/                   # 📂 组合式 Hooks (useChatStream, useConfirmation)
│
├── components/                    # 📂 Vue 3 领域组件库 (重构阶段二模块化)
│   ├── chat/                      # 💬 聊天主流程组件 (MessageList, MessageItem, ReasoningAccordion)
│   ├── agent/                     # 🤖 多 Agent 状态可视化 (SubAgentBadge, TaskPlannerCard, InterruptModal)
│   ├── artifacts/                 # 📊 结构化数据产物组件 (ChartArtifactCard, TableResult, ScalarResult)
│   └── common/                    # 🛠️ 通用基础 UI 组件 (ToggleSwitch, FloatingScenarioCards, ScenarioModal)
│
├── utils/                         # 📂 通用纯函数 (helpers.ts, markdown.ts)
└── views/                         # 📂 页面视图 (ChatView.vue)
```

---

## 五、 重构阶段与实施路线图 (Functionality-First Roadmap)

遵循 **“优先保证功能正常，而后进行目录物理拆分”** 的风险隔离原则，重构划分为 4 个渐进实施阶段：

```text
===================================================================
【第一阶段：核心功能落地与全链路验证 (在现行文件结构中动刀)】
===================================================================
1.1 后端 Agent 引擎升级 (backend/app/agent/service.py)：
    - 将主 Agent 实例化函数升级为 create_deep_agent
    - 配置 tools="all" 开放主 Agent 文件系统能力
    - 将现有 SQL 工具集封装为 CompiledSubAgent(name="sql_domain_agent", runnable=sql_subgraph)，通过 subagents=[...] 注入
    - 确保 _initialize_agent (同步路径) 与 _ainitialize_agent (异步路径) 100% 同步更新

1.2 后端服务层流式 v2 解包 (backend/app/services.py)：
    - 将 astream 调用参数升级为 subgraphs=True, version="v2"
    - 解析 StreamPart 字典中的 ns 路径：当包含 "tools:<call_id>" 时判定为子智能体消息
    - 当检测到 ns 发生领域切换时，向事件队列派发 subagent_change SSE 事件

1.3 前端流式感知与 UI 徽章挂载 (frontend/src/)：
    - 在 frontend/src/types/index.ts 的 Message 接口中扩展 active_subagent 状态
    - 在 frontend/src/api/chat.ts 的 STREAM_EVENT_TYPES 白名单 Set 中注册 subagent_change
    - 在 frontend/src/stores/messages.ts 的 handleStreamEvent 中响应并驱动状态
    - 挂载 SubAgentBadge.vue 组件呈现 🤖 [SQL数据助手] 徽章（遵守零外网 CDN 约束）

1.4 端到端功能全量冒烟测试：
    - 验证：数据查询正向链路、打字机输出、HITL 确认框、CSV 导出、单元测试全绿 PASS

===================================================================
【第二阶段：物理目录拆分与代码结构解耦 (纯代码搬家，零业务风险)】
===================================================================
2.1 后端 Agent 目录规范化：
    - 建立 backend/app/agent/subagents/sql/ 目录，将 SQL 工具与 Prompt 隔离移入

2.2 巨型单文件解耦 (api.py & services.py)：
    - 将 backend/app/api.py (53KB) 拆分为 routers/ (chat.py, sessions.py, skills.py, system.py)
    - 将 backend/app/services.py (42KB) 拆分为 services/ (chat_service.py, stream_service.py)

2.3 前端组件库领域化拆分：
    - 将 frontend/src/components/ 下的 19 个散落组件按领域划分为 chat/, agent/, artifacts/, common/ 目录

===================================================================
【第三阶段：HITL 中断与增强特性验证】
===================================================================
3.1 验证 SQL 触发 AskUserQuestion / interrupt 时 SSE 派发与 InterruptModal 弹窗
3.2 验证 Command(resume=...) 恢复 Graph 执行机制

===================================================================
【第四阶段：全链路回归与后续扩展】
===================================================================
4.1 运行 Pytest 全量测试套件与 Vite 前端打包编译，确认 100% PASS
4.2 保持接口契约，为后续预留接入 KnowledgeRAGSubAgent 与 DeepAnalystSubAgent 打下坚实基础
```

---

## 六、 测试决策 (Testing Decisions)

### 1. 测试切缝 (Test Seams)
- **高阶流式与路由切缝**：在 FastAPI 服务层的 `astream(subgraphs=True)` 消息解析处设立测试切缝。
- **子智能体隔离切缝**：针对 `SQLSubGraph` 的独立输入输出设置单元测试切缝。

### 2. 行为测试范畴
- **隐式路由测试**：测试用户提问“查询底漆车间在制车”时主 Agent 能否正确选择 `sql_domain_agent`；提问闲聊时由 `general-purpose` 兜底/主 Agent 直接回答。
- **流式解包测试**：验证 StreamPart 字典 `ns` 解析逻辑，确保 `subagent_change` 事件正确派发且打字机 Token 零丢包。
- **HITL 中断与恢复测试**：测试 `interrupt()` 触发后派发 `interrupt` 事件，以及通过 `Command(resume=...)` 正确恢复 Graph 流程。

### 3. 参考先例 (Prior Art)
- [`backend/app/agent/test_compiled_subagent_v2_poc.py`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/backend/app/agent/test_compiled_subagent_v2_poc.py)：已全量验证 `CompiledSubAgent` + `subagents=[...]` + `astream(subgraphs=True, version="v2")` 字典解包（100% PASS）。

---

## 七、 范围外事项 (Out of Scope)

1. **多租户云端沙盒隔离**：初期采用本地虚拟文件系统（`StateBackend`），物理 Docker/E2B 云端代码沙盒暂不在此规范范围内。
2. **底层数据库 Schema 改动**：不涉及 PostgreSQL 物理表结构或已有向量索引的重构。

---

## 八、 补充说明 (Further Notes)

- 升级到 `deepagents 0.7.5` 后，若未来需要接入 `DeepAnalyst` 子智能体，可在其内部启用 `TodoListMiddleware` 与 Python 代码解释器。
- 修改涉及子智能体与中间件装配时，必须同时保持 `_initialize_agent`（同步路径，`service.py:606`）与 `_ainitialize_agent`（异步路径，`service.py:632`）100% 同步更新。
