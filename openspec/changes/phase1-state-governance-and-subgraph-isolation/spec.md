# Phase 1: 状态治理与图拓扑单向隔离规范 (Phase 1 Spec)

> **文档标识**：`phase1-state-governance-and-subgraph-isolation`  
> **文档路径**：`openspec/changes/phase1-state-governance-and-subgraph-isolation/spec.md`  
> **分类标签**：`ready-for-agent`  
> **基准审查**：基于 `docs/agents/multiagent_tool_sidechannel_audit_report.md` 与 `docs/agents/state_sidechannel_multiagent_report.md`

---

## Problem Statement

在当前多智能体（Main Agent + CompiledSubAgent / task 派发）生产数据查询与分析系统中，状态机管理与子图拓扑存在严重的状态回写冲突、上下文膨胀与异常脆弱性问题：

1. **父图并发写冲突（State Write Collisions）**：
   - 当主 Agent 并发派发多个子智能体（如同时委派两个子智能体分别处理涂装车间与总装车间数据）或子智能体动态调用 `load_skill` 技能时，各个子图执行完毕向父图返回状态，触发 LangGraph 的 `INVALID_CONCURRENT_GRAPH_UPDATE` 状态冲突。
   - 虽然 Phase 0 临时为部分字段补充了 `_last_wins` Reducer，但本质上子智能体的私有内部状态不应越界污染并竞争回写父图的全局 State。
2. **跨 Task 技能重复加载与认知开销（Redundant Skill Reloading）**：
   - 技能状态（`skills_loaded` / `scenarios_loaded`）未在主图与子图之间形成清晰的单向持有与只读投影机制。在多轮交互或多子智能体场景下，子智能体无法直接感知主图已加载的全局领域技能，导致每个子智能体在执行任务时反复调用 `load_skill`，增加了额外的模型思考轮次与 LLM Token 延迟。
3. **子图出口缺乏收口导致 Checkpoint 体积暴涨（Checkpoint Storage Bloat）**：
   - 子智能体在执行过程中检索到的大体量 `rag_context`（长篇知识库切片）、`lexicon_context`（数千字节的物理词典与 DDL 投影）若未经出口白名单收口，会被全盘深拷贝写回父图全局 State，导致 LangGraph Checkpointer 每次保存状态快照时数据体积呈指数级暴涨，并引发多轮会话的上下文膨胀与崩溃（Context Collapse）。
4. **子智能体异常穿透与不可控崩溃（Unhandled Subagent Failures）**：
   - 当子智能体在执行 SQL 查询、复杂运算或数据处理遇到死锁、语法错误或网络异常时，若未进行结构化统一封装，未捕获的 Python 异常会直接穿透并导致整个主图中断崩溃，用户只能看到生硬的 HTTP 500 报错，主 Agent 也丧失了自主降级、重试或向用户友好解释的能力。

---

## Solution

Phase 1 聚焦于**“状态主权单点持有、子图出口白名单收口、只读单向投影、故障结构化自愈”**的架构治理：

1. **技能状态主图单点持有与只读派发投影（Single-Owner Skill State & Read-only Projection）**：
   - 将 `skills_loaded`、`scenarios_loaded`、`active_skill` 的管理主权收敛在主 Agent（Parent Graph）单点持久化维护。
   - 主 Agent 在通过 `task` 委派子智能体时，将当前已加载的领域技能作为只读上下文（Read-only Context）在任务生成阶段直接投影注入到子任务描述或 System Prompt 中。子智能体直接继承主图领域知识，严禁向父图 State 回写 `skills_loaded`，彻底杜绝跨 Task 重复加载开销与状态写冲突。
2. **子图出口白名单收口与瘦身（Subgraph Output Whitelist Sanitization）**：
   - 在子智能体（CompiledSubAgent / task）与父图之间建立严格的出口白名单过滤机制。
   - 子图完成时，仅允许向父图 State 回传：
     - `messages`：包含子智能体执行总结、关键回答或结构化消息；
     - 控制变量：任务完成标记；
     - 结构化错误：若任务失败则返回标准错误包体。
   - 严禁将子图执行过程中的 `rag_context`、`lexicon_context`、内部大体量临时变量回写到父图，确保父图 State 极致轻量，Checkpointer 快照体积维持在最小必要集。
3. **子智能体故障统一封装与自愈（Structured FailedResult & Resilient Recovery）**：
   - 为子智能体执行器定义标准统一的 `FailedResult` 契约（包含 `error_type`、`error_message`、`suggested_action`、`partial_output`）。
   - 当子图发生 SQL 执行异常、超时或数据解析失败时，拦截未捕获异常并包装为结构化 `FailedResult` 安全回传给主 Agent。主 Agent 根据结构化错误信息能够进行自我纠错（如重新澄清参数、换用兜底分析逻辑）或向用户输出清晰友好的解释，绝不引发整个会话服务崩溃。

---

## User Stories

1. 作为企业管理层，当我的复杂跨车间对比问题触发 2 个或多个子智能体并发执行时，我希望系统稳定高效完成，绝不因为后台状态并发写入冲突而报错中断。
2. 作为业务分析师，当主 Agent 已经识别出当前属于“涂装车间”领域并加载了相应技能后，我希望后续委派的子智能体能够直接复用该领域知识，不再重复调用技能加载工具，从而显著缩短回复等待时间。
3. 作为系统架构师，我希望多轮深入对话后，数据库中 LangGraph Checkpointer 保存的状态快照体积保持在轻量级别（不超过 50KB/checkpoint），不因为 RAG 大文档切片的重复回写而发生爆炸式增长。
4. 作为数据库管理员，当子智能体执行 SQL 查询遇到物理表语法错误或字段不存在时，我希望系统不会直接抛出 500 内部服务错误，而是由子智能体将结构化错误返回给主智能体进行自我修正或友好提示。
5. 作为车间质量管理员，当某一个子智能体因为网络超时执行失败时，我希望主智能体能够优雅地捕获该错误，并在最终回复中明确告知“总装车间查询超时，涂装车间数据如下”，提供部分可用的降级答复而不是全盘崩溃。
6. 作为前端用户，我希望在多子智能体并发执行与技能加载过程中，界面上的思考过程与状态流转丝滑流畅，后台状态机保持整洁纯净。
7. 作为后端开发者，我希望子图与父图之间的数据流向具有清晰的单向约束（Parent -> Read-only Subgraph -> Whitelisted Return），消除隐式全局变量修改带来的调试困难。
8. 作为系统运维人员，我希望在服务高并发调用场景下，Checkpointer 的序列化与反序列化延迟稳定在毫秒级，避免因 State 臃肿导致数据库 I/O 阻塞。
9. 作为业务专家，我希望在新增子智能体（如工艺分析子智能体、设备监控子智能体）时，只需遵循标准白名单与 `FailedResult` 协议即可即插即用，无需对父图的状态合并逻辑做侵入式修改。
10. 作为安全审计员，我希望子图内部的敏感临时计算数据随着子图执行结束自然销毁，不残留扩散到父图全局快照中，确保数据隔离性。

---

## Implementation Decisions

### 1. 架构分工与拓扑隔离决策 (Architectural Decisions)

- **主图技能单点主权机制 (Parent-Owned Skill State)**：
  - `skills_loaded` 与 `scenarios_loaded` 的持久化写入权限仅保留在主 Agent（Parent Graph）上。
  - 在主 Agent 装配 `SkillMiddleware`，负责初始意图识别与领域技能预加载；子智能体只保留 `PromptCompilerMiddleware` 与 SQL 执行工具，不再装配可回写父图状态的 `SkillMiddleware`。
  - 主图派发子任务时，将主图的技能大纲与已加载 DDL 作为 Prompt 增强内容自动合并至 Task 说明中。
- **子图出口白名单收口 (Subgraph Whitelist Sanitization)**：
  - 明确子图向父图回写的白名单字段集合：仅允许 `messages`。
  - 显式屏蔽 `rag_context`、`lexicon_context`、`rag_query` 等临时检索字段的回写，防止深拷贝污染。
  - 通过 LangGraph 的 Output Schema 或子智能体包装器对返回值进行严格清洗过滤。
- **结构化异常统一协议 (`FailedResult` Protocol)**：
  - 定义统一的子智能体失败响应格式：
    ```python
    class FailedResult(BaseModel):
        success: bool = False
        error_type: str  # e.g., "SQL_EXECUTION_ERROR", "TIMEOUT", "SCHEMA_NOT_FOUND"
        error_message: str
        suggested_action: Optional[str] = None
        context_details: Optional[dict[str, Any]] = None
    ```
  - 子图入口与执行器包裹 `try...except` 保护罩，捕获全部未处理异常并转换为 `FailedResult` JSON 文本消息回传，防止主图中断。

### 2. 状态结构与协议定义 (State & Contract Shapes)

#### A. 瘦身后精简的父图全局状态 (`CustomState`)
```python
class CustomState(AgentState):
    """
    Phase 1 治理后的轻量级 Agent 状态。
    仅保留父图长会话所必需的控制与引用变量。
    """
    skills_loaded: NotRequired[Annotated[List[str], _last_wins]]
    scenarios_loaded: NotRequired[Annotated[List[str], _last_wins]]
    active_skill: NotRequired[Annotated[str | None, _last_wins]]
    active_scenario: NotRequired[Annotated[str | None, _last_wins]]
    context_warning: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
    tool_artifact: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
    # 彻底剔除大体量临时检索状态: rag_context / lexicon_context 不再作为跨轮次持久化全局变量
```

#### B. 只读投影 Task 描述注入格式 (Read-Only Task Projection)
```markdown
# 委派任务目标
查询涂装车间近7天在制车统计并生成趋势图。

# 继承的父图领域技能上下文 (Read-Only Projection)
- 活跃领域: paint_shop_skill
- 关联表结构与业务规则:
  [DDL 与易错字段说明已在主图完成检索并注入，子图直接基于此规划 SQL]
```

---

## Testing Decisions

### 1. 测试原则 (Testing Principles)
- 遵循**外部黑盒行为测试（External Behavior-Driven）**。
- 严密验证：**并发多子智能体派发无状态冲突**、**父图 Checkpoint 体积保持轻量**、**子智能体异常安全降级回传**。

### 2. 核心测试覆盖模块 (Test Targets)
1. **多子智能体并发执行测试 (`test_subagent_concurrency.py`)**：
   - 模拟主 Agent 同时派发 2~3 个子智能体并发执行不同 SQL 任务，验证无 `INVALID_CONCURRENT_GRAPH_UPDATE` 异常，所有任务正常汇总。
2. **技能单向投影与免重复加载测试 (`test_skill_single_owner_projection.py`)**：
   - 验证主图加载 `paint_shop_skill` 后派发子智能体，子智能体未重复触发 `load_skill` 工具调用，且直接利用已投影的 DDL 生成正确 SQL。
3. **Checkpoint 体积与白名单出口过滤测试 (`test_checkpoint_size_and_whitelist.py`)**：
   - 验证子智能体执行大体量检索后，返回父图的 State 快照中不包含 `rag_context` 与 `lexicon_context` 原始对象，单个 Checkpoint 序列化体积小于 50KB。
4. **子智能体异常与 `FailedResult` 容灾测试 (`test_subagent_failed_result_resilience.py`)**：
   - 模拟子智能体内部 SQL 语法错误或连接超时，验证主图不抛出未捕获异常，主 Agent 能够接收到 `FailedResult` 并输出友好的错误解释。

### 3. 代码库先验参考 (Prior Art)
- `backend/tests/agent/test_custom_state_concurrent.py`（并发写测试基准）
- `backend/tests/test_tool_artifacts_persistence.py`（工件持久化集成基准）

---

## Out of Scope

以下内容不属于 Phase 1 的交付范围，将在后续阶段推进：

1. **Phase 2 UI 复合展示容器**：前端多图表 Tab 轮播切换、多 SQL 查询表格按子智能体分 Tab / 多折叠面板展示。
2. **Phase 2 统一 Artifact Store**：基于 TTL 自动清理与列级脱敏的中央工件管理器。
3. **Phase 3 断线续传**：基于 SSE `Last-Event-ID` 的断线自动重连与差量补齐。
4. **分布式动态 Worker 池**：跨物理节点的子智能体 RPC 分布式调度（当前保持在本地 asyncio / LangGraph 并发调度）。

---

## Further Notes

- **向后兼容性**：Phase 1 的状态治理与子图白名单收口完全发生在后端图执行层与中间件层，对前端现有的 SSE 事件流和消息结构 100% 透明兼容，无需前端配合做破坏性升级。
- **与 Phase 0 成果的协同**：Phase 0 建立的 `tool_artifacts` 消息表落库机制与 Phase 1 的 State 瘦身相得益彰——大体量工件与展示数据全量交由 `chat_messages` 消息表承载，LangGraph Checkpointer 则专注于纯粹轻量的高性能状态机流转。
