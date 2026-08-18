# Phase 1: 基于 Context API 的状态治理与子图沙箱隔离规范

> **分类标签**：`ready-for-agent`  
> **方案标识**：`phase1-state-governance-and-subgraph-isolation`  
> **架构基准**：基于 `docs/agents/multiagent_tool_sidechannel_audit_report.md`（Context API 原生瞬态数据流 + 状态物理沙箱隔离方案）

---

## Problem Statement

在面向企业生产数据查询的多智能体系统（Main Agent + CompiledSubAgent / task 委派）中，用户和系统面临以下核心痛点：

1. **数据库 Checkpoint 快照急剧膨胀与历史上下文污染**：单轮检索产生的大体量数据库 DDL、三层模糊词典及业务术语（可达数十 KB）此前被直接挂载在父图全局持久化状态中。每次状态保存时，Checkpointer 均将这些庞大的静态对象全量序列化并写入 PostgreSQL 数据库，导致 Checkpoint 存储体积以数百 KB/轮的速度急剧膨胀，且历史多轮对话中残留的旧车间 DDL 成为噪声，干扰大模型在后续对话中的注意力。
2. **多子智能体并发执行时的写冲突崩溃**：当主智能体同时委派多个子智能体并发处理不同车间的数据请求时，各子智能体同时尝试向父图的全局共享状态中回写无 Reducer 保护的技能与检索字段，触发 LangGraph 的 `INVALID_CONCURRENT_GRAPH_UPDATE` 状态写冲突异常，导致会话直接中断。
3. **主子智能体职责边界越界与认知过载**：主智能体原本定位为通用意图识别、参数澄清与任务调度中心，却承载了具体车间的垂直 SQL 技能与物理表 DDL，不仅导致主智能体系统提示词冗长，还使得主智能体容易越权臆测底层物理表名，干扰垂直 SQL 专家子智能体的专业决策与自愈机制。
4. **流式事件提取与状态分裂隐患**：若状态设计未彻底理清瞬态数据与长期状态的边界，服务层在提取流式 RAG 和词典事件时容易出现状态打捞失效，导致前端折叠面板事件被静默截断。

---

## Solution

全面采用 LangGraph / DeepAgents 官方标准的 **Context API (`context_schema=RequestContext`)** 作为单轮请求级瞬态数据通道，配合 **父子智能体状态物理沙箱化** 与 **领域技能独占归属**，彻底消除 Checkpoint 膨胀与并发冲突，维持既有错误自愈回路：

1. **Context API 传输单轮瞬态数据（0 字节写入 Checkpoint）**：
   - 建立单轮请求级瞬态数据契约，大体量 RAG 知识、物理词典 DDL 与映射仅通过 Context API 在内存运行时单向向下透传给中间件与提示词编译器；
   - 严格保证 Checkpointer 仅持久化会话消息与轻量控制位，对大体量检索上下文实现 **0 字节写入 Checkpoint**；
   - 服务层流式事件提取直接读取请求上下文，彻底杜绝从 State 中打捞失效的问题。
2. **状态物理沙箱隔离（State Physical Sandboxing）**：
   - 父图全局状态彻底瘦身，仅保留长会话多轮对话必需的字段；
   - 子智能体运行在私有的沙箱状态中，独占维护技能加载状态；
   - 子智能体任务完成时仅通过标准任务工具返回纯文本结果，私有状态自然闭环在子图沙箱生命周期内，不向父图扩散，从根本上杜绝并发写冲突。
3. **领域技能独占归属 SQL 子智能体（Subagent Domain Skill Ownership）**：
   - 技能管理中间件与技能加载工具 100% 独占装配给 SQL 专家子智能体；
   - 主智能体保持纯净编排，仅保留澄清确认工具与长会话摘要能力；
   - 确立清晰的任务委派分工协议，主智能体仅传递业务意图与参数，严禁强行指定底层物理表。

---

## User Stories

1. As a 系统架构师, I want 单轮 RAG 与词典检索数据仅在内存运行时流转而不写入 PostgreSQL Checkpoint 表, so that 数据库存储体积和 I/O 负担大幅降低，且不会发生历史会话上下文污染。
2. As a 最终用户, I want 同时发起多个车间或多个指标的复杂统计查询时系统能够稳定并发响应, so that 不会因为子智能体并发修改状态而遭遇会话崩溃报错。
3. As a 运维工程师, I want 查看系统运行日志时不再看到由状态并发写冲突引发的 `INVALID_CONCURRENT_GRAPH_UPDATE` 错误, so that 系统具备企业级的并发稳定性。
4. As a 最终用户, I want 在提问后看到清晰的数据库物理词典三层折叠面板与业务术语说明实时展开, so that 我能透明地了解智能体参考了哪些数据表结构与字段映射。
5. As a SQL 专家子智能体, I want 独占拥有车间领域的技能加载与 DDL 知识注入能力, so that 我能根据具体的查询任务自主检索、按需激活技能并灵活自愈 SQL 语法。
6. As a 主编排智能体, I want 系统提示词保持轻量纯净且不包含任何具体车间的物理表 DDL, so that 我能专注于理解用户的高阶意图、进行缺参澄清并精准委派任务。
7. As a 开发人员, I want 主智能体向子智能体委派任务时遵守标准任务协议（只传业务意图与过滤条件，不强行指定表名）, so that 模块间耦合度最小化且各司其职。
8. As a 最终用户, I want 当检索服务偶发超时或异常时系统能够平稳降级继续工作, so that 我的聊天会话不会因辅助检索异常而彻底中断。
9. As a 前端开发者, I want 后端流式 SSE 协议在 Context API 架构下依然稳定推送 `rag_context` 与 `lexicon_context` 事件, so that 前端组件无需修改任何事件消费逻辑即可无缝展示。
10. As a 自动化测试工程师, I want 核心单测能在无真实数据库连接的环境下稳定运行, so that CI/CD 流水线能够秒级验证状态隔离与边界完整性。

---

## Implementation Decisions

### 1. 单轮请求级瞬态上下文契约 (`RequestContext`)
- 声明请求级瞬态上下文类型，作为主子智能体、中间件与服务层的统一瞬态数据管道；
- 该契约包含以下字段（来自经过验证的运行时原型）：
  ```python
  class RequestContext(TypedDict, total=False):
      lexicon_context: Optional[dict[str, Any]]
      rag_context: Optional[List[Document]]
      rag_query: Optional[str]
      user_id: Optional[str]
      session_id: Optional[str]
  ```
- 架构规则：主图与子图均装配该上下文契约，Checkpointer 永不持久化此契约中的任何字段。

### 2. 父图全局持久化状态瘦身 (`MainAgentState` / `CustomState`)
- 父图全局状态剔除所有瞬态检索与私有技能字段，仅保留多轮会话必需的最小集：
  ```python
  class CustomState(AgentState):
      context_warning: Annotated[Optional[str], _last_wins]
      tool_artifact: Annotated[Optional[Dict[str, Any]], _last_wins]
  ```
- 架构规则：主智能体仅依靠消息历史与轻量控制位维持多轮对话。

### 3. 子智能体私有沙箱状态 (`SqlSubAgentState`)
- 为垂直领域子智能体声明独立的私有沙箱状态，仅在子图执行生命周期内有效：
  ```python
  class SqlSubAgentState(AgentState):
      skills_loaded: Annotated[List[str], _last_wins]
      active_skill: Annotated[Optional[str], _last_wins]
      scenarios_loaded: Annotated[List[str], _last_wins]
      active_scenario: Annotated[Optional[str], _last_wins]
  ```
- 架构规则：子图私有字段绝不向父图状态提升，子智能体仅通过任务工具返回文本结果。

### 4. 检索中间件单向注入 Context API
- 业务 RAG 与词典检索中间件在模型调用前执行检索，并将结果写入运行时上下文（`runtime.context`）；
- 正常检索成功与异常回退分支均统一写入运行时上下文并返回空（`return None`），严禁向状态回写废弃键值；
- 移除依赖状态中历史查询字段的失效防重复逻辑，改由运行时上下文比对。

### 5. 提示词编译器动态接入 Context API
- 提示词编译器与系统提示注入中间件在构建模型请求时，优先从运行时上下文读取瞬态 DDL 与业务术语；
- 动态编译生成包含规则区与上下文区的双分区 XML 格式系统提示词，避免多系统消息引发的推理引擎校验错误；
- 消费侧保留对状态的防御性读取，确保向下兼容。

### 6. 服务层流式事件提取与请求上下文规范化
- 服务层在发起流式调用与非流式调用时，统一构造并显式预置包含全量规范字段的请求上下文实例；
- 流式执行循环直接从该请求上下文实例中读取检索数据并发射前端流式事件，彻底移除对持久化状态的二次查询。

---

## Testing Decisions

### 1. 良好测试的定义原则
- 严格遵循**外部行为驱动测试（Behavior-Driven Testing）**：仅验证外部契约、数据流向、状态污染隔离与并发安全性，不绑定易变的内部实现细节；
- 具备**零外部网络与数据库强依赖**特性：单测必须通过内存实例或确定性打桩运行，确保在隔离环境下 100% 确定性通过。

### 2. 核心测试切面 (Testing Seams)
- **切面 1：持久化零污染切面** — 验证调用完成后 Checkpointer 的持久化快照中 100% 不包含任何瞬态检索字段；
- **切面 2：多子智能体并发沙箱切面** — 验证多个子智能体并发加载不同车间技能并汇总时，父图状态纯净且无写冲突；
- **切面 3：主子组件职责边界切面** — 验证主智能体仅含编排工具与中间件，SQL 子智能体独占持有技能管理中间件；
- **切面 4：动态提示词编译切面** — 验证提示词编译器能够从运行时上下文中提取 DDL 并动态拼装入系统提示词。

### 3. 既有参考模式 (Prior Art)
- 借鉴 `backend/tests/agent/test_custom_state_concurrent.py` 中的 LangGraph 状态归约测试模式；
- 借鉴 `backend/tests/test_tool_artifacts_persistence.py` 中的工件隔离测试模式。

---

## Out of Scope

1. **子智能体间直接点对点横向通信**：子智能体之间的交互严格通过主智能体统一中转与任务委派，暂不引入子智能体间的直接网状通讯。
2. **多租户权限与 ACL 动态过滤**：本规范聚焦于单会话请求级的数据流与状态沙箱治理，企业级多租户数据权限隔离属于后续独立阶段。
3. **前端 UI 组件重构**：前端保持既有的 SSE 事件订阅机制与三层折叠面板渲染逻辑，前端代码无需因此状态治理而重构。

---

## Further Notes

1. **无破坏性与平滑迁移**：通过在消费侧中间件保留向下兼容的回退机制，既有单测与上层业务调用均可平滑过渡至新架构。
2. **故障处理原则**：维持原有 SQL 工具错误反馈机制与大模型自主纠错回路，不引入额外的复杂异常包装器。
