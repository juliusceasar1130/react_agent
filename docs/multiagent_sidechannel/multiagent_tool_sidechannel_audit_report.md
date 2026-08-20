# 主子智能体架构下工具侧信道、状态隔离与流式分流深度审查报告

> **文档版本**：v3.0 (Phase 2 工件统一底座与子智能体专属工件内嵌全量落地 · Claude Code 联合审查验收终版)  
> **文档位置**：`docs/multiagent_sidechannel/multiagent_tool_sidechannel_audit_report.md`  
> **更新时间**：2026-08-20  
> **审查对象**：主子智能体协同体系（`deepagents` / `CompiledSubAgent`）下的工具侧信道机制、状态机（`CustomState`）各维度隔离性、工件统一存储底座（`ArtifactStore`）、子智能体专属工件就近内嵌（`SubagentCard`）、SSE 流式分流协议与前端回放渲染链路。  
> **评审基准**：由 Antigravity 完成架构演进与代码实现，经 Claude Code（`w4:p1`）完成跨 Agent 独立对审并 100% 验收通过（Approved）。

---

## 1. 执行摘要与问题综述

面向生产数据查询与分析场景，本项目构建了基于 **Supervisor-Worker（主智能体 - SQL 子智能体）** 的分层协同架构，并为工具链（SQL 查询、图表生成、CSV 导出）设计了 **基于 State 的侧信道（Out-of-Band Channel）** 与 **Claim-Check 凭证引用** 机制，以实现 LLM 上下文 Token 零膨胀与前端毫秒级流式渲染。

但在深入排查多智能体并发与多轮会话生命周期后，发现系统存在 **状态边界泄露、并发竞态覆盖、流式分流缺失、历史回放断裂** 等一系列结构性问题：

```
                             主子智能体协同全景评估
                                       │
    ┌───────────────────┬──────────────┴───────────────┬───────────────────┐
    ▼                   ▼                              ▼                   ▼
【1. 技能状态层】     【2. 知识 RAG 层】            【3. 物理词典层】   【4. 工具侧信道层】
 skills_loaded        rag_context                    lexicon_context     tool_artifact
 列表覆盖丢失          文档集覆盖丢失                  列值映射覆盖丢失     单槽位覆盖/刷新丢失
 (Reducer=_last_wins) (Reducer=_last_wins)           (Reducer=_last_wins) (跨工具翻牌冲刷)
    │                   │                              │                   │
    └───────────────────┴──────────────┬───────────────┴───────────────────┘
                                       ▼
                       【5. SSE 流式分流与前端回放层】
                        - tool_artifact 缺失 subagent_id 溯源
                        - 前端历史扫描过滤 subagent_id 导致刷新全军覆没
```

---

## 2. 核心工具链底层机制与流式时序

本项目三大核心工具均采用 **“主信道高密度压缩 + State 侧信道直推 + 服务端 Claim-Check 存储”** 的三层分立设计：

### 2.1 绘图工具：`build_chart_artifact`
1. **执行与计算**：大模型仅提供声明式入参（`query`, `series`, `x_field`），后端直接执行 SQL 查库，并由 Python 引擎完成类型推断（line vs bar）、数值验证与智能分类透视拆分（`_infer_category_series`）；
2. **Claim-Check 存储落盘**：调用 `ArtifactStore.save_artifact`，将完整配置和 `rows` 写入服务端工件目录（`settings.artifacts_dir/charts/{chart_id}.json`），采用原子写入（临时文件 + `os.replace`），附带 24 小时 TTL 有效期；
3. **双轨交付**：
   - **主信道（给大模型）**：仅返回 `chart_ref`（`chart_id` + 标题），避免海量数据点灌入 Prompt；
   - **State 侧信道（给前端）**：通过 `Command(update={"tool_artifact": chart_spec})` 挂载完整渲染数据；
4. **流式直推时机（为什么图表比文字快）**：
   - 工具执行完毕时，LangGraph 产出 `updates` 状态增量；
   - `chat_service.py` 捕获到 `tool_artifact`，在毫秒级通过 SSE 向前端发射 `type: "tool_artifact"`；
   - 前端接收后，ECharts **即刻渲染出图，无需等待后续大模型总结文字打字机完成**。

### 2.2 CSV 导出工具：`export_to_csv`
1. **物理隔离与 OOM 熔断**：数据库查询结果直接流式落盘为 `data/artifacts/exports/export_xxx.csv`，受 `sql_export_max_rows` 硬上限保护；
2. **敏感路径物理脱敏**：向消息流返回元数据前，主动过滤掉 `stored_path` 服务器物理绝对路径；
3. **纯 Claim-Check**：LLM 上下文与 State 零 Token 消耗，前端通过 `/api/chat/artifacts/{file_id}/download` 异步下载。

### 2.3 SQL 查询工具：`sql_db_query`
1. **截断保护与提示引导**：结果超过 `sql_result_hard_limit`（默认 30 行，上限 1000 行）时，主信道仅暴露前 5~10 行预览并发出截断警告，引导转调 `export_to_csv`；
2. **实时结构化表格直推与 DB 直存**：
   - 通过 `tool_artifact`（`kind: "query_result"`）下发，前端在消息区域渲染带行数统计与截断标识的交互式数据表格；
   - **极简架构裁决**：数据量小（< 300KB），无需单独落盘物理文件与开发独立 REST 端点；继续走 `chat_messages.tool_artifacts` 表直接持久化（PostgreSQL TOAST 自动透明压缩），实现 F5 刷新 0 秒秒开。

---

## 3. 全系统六大维度架构深度评估与裁决

### 3.1 维度一：领域技能与场景状态层（Skills & Scenario State）
- **代码位置**：`backend/app/agent/state.py:20-44`
- **现象与风险**：若多子智能体并发执行，`_last_wins` Reducer 会导致后完成者的技能列表直接覆盖先完成者，多轮对话中前序技能被静默抹除。
- **架构裁决（主图瘦身 + 子图沙箱隔离）**：
  - **核心原则**：**主图使用 `CustomState`（仅含 `messages`、`context_warning` 与 `tool_artifact`），子图私有持有 `SqlSubAgentState`（`skills_loaded` 等）；子图严禁将私有技能状态回传污染父图**。
  - **落地状态**：Phase 1 已闭环落地。

---

### 3.2 维度二：业务知识 RAG 检索层（RAG & Context Injection）
- **代码位置**：`backend/app/agent/context.py`、`backend/app/agent/middleware/rag_middleware.py`
- **现象与风险**：多子智能体各自检索领域文档回传父图时，`_last_wins` 导致非最后到达的参考文档全盘丢失。
- **架构裁决（Context API 瞬态通道 + 0 字节 Checkpoint）**：
  - **核心原则**：**通过 `RequestContext` 传输单轮大体量知识切片与 DDL，0 字节入 Checkpoint，彻底消除写冲突**。
  - **落地状态**：Phase 1 已闭环落地。

---

### 3.3 维度三：物理词典与列值消歧层（Database Value Lexicon）
- **架构裁决（黑盒辅助草稿隔离）**：
  - **核心原则**：**物理词典消歧属于 SQL 子智能体编写 SQL 的内部辅助工具，单向消费，不回传父智能体**。
  - **落地状态**：Phase 1 已闭环落地。

---

### 3.4 维度四：人机协同与中断恢复层（HITL Interrupt & Resume）
- **代码位置**：`backend/app/routers/chat.py:460-472`
- **评估现状**：主链路中断与 `/resume` 恢复运行正常，已支持提问者身份（`subagent_name`）透传。

---

### 3.5 维度五：工具侧信道与工件持久化层（Tool Artifacts & Persistence）
- **核心断裂点与评审纠偏**：
  1. **并发覆盖与刷新丢失**：已通过 Phase 0 在 `chat_messages.tool_artifacts` 增加持久化列并在 `final` / `interrupt` 事件全量落库彻底修复；
  2. **工件统一存储收敛（Phase 2 核心）**：合并 `chart_artifacts` 与 `export_files` 为统一 `ArtifactStore`，物理落盘文件采用原子写（临时文件 + `os.replace`），设置统一 24 小时 TTL 与周期性 GC 回收；
  3. **工具层泛型解耦**：解除 `build_chart_artifact` 与 `export_to_csv` 对 `SqlSubAgentState` 的硬绑定，适配未来主智能体直接复用。

---

### 3.6 维度六：存储引擎与快照开销（Checkpointer Storage Bloat）
- **评估裁决**：Context API 彻底消除了 Checkpoint 序列化膨胀，系统承载能力充裕。

---

## 4. 全工具受损现状评估对照矩阵

| 工具名称 | 实时流式交互态 | 页面刷新后 (F5) 现状 | 前端穿透后效果 | 补全 DB 落库后效果 |
| :--- | :--- | :--- | :--- | :--- |
| **`build_chart_artifact`** | 正常渲染 ECharts 图表 | **❌ 彻底消失** | 🟢 可恢复 (异步请求端点) | 🌟 0 秒即时恢复 (DB直出) |
| **`export_to_csv`** | 正常展示 CSV 下载卡片 | **❌ 彻底消失** | 🟢 可恢复 (异步请求端点) | 🌟 0 秒即时恢复 (DB直出) |
| **`sql_db_query`** | 顶部展示结构化 SQL 表格 | **❌ 彻底消失** | ❌ **依然丢失 (无端点)** | 🌟 **100% 完美复原** |
| **`AskUserQuestion`** | 正常弹出澄清确认卡片 | **🟢 正常** (主 Agent 发起) | 🟢 正常 | 🟢 正常 |
| **`load_skill` / 词典工具** | 调试步骤中展示 | **🟢 正常** (折叠于调试栏) | 🟢 正常 | 🟢 正常 |

---

## 5. 终极演进架构（三层各司其职）

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. 执行层 (Checkpointer) ── 专注 Agent 状态机与断点恢复                │
│    • State 极致轻量：仅保留 messages + 控制变量 + 工件句柄引用         │
│    • skills / rag / lexicon：主图单点持有，派发时只读投影下发          │
│    • 子图出口白名单收口，过滤原始大文档回写                            │
├────────────────────────────────────────────────────────────────────────┤
│ 2. 交付与真相层 (SSE + chat_messages) ── 专注 UI 交互与历史全量回放   │
│    • SSE 事件携带 subagent_id + tool_call_id 溯源                     │
│    • final 结束时 tool_artifacts 同步落库 chat_messages 表            │
│    • F5 刷新时由消息表直接驱动 100% 真相还原                           │
├────────────────────────────────────────────────────────────────────────┤
│ 3. 工件层 (Artifact Store) ── 专注海量数据 Claim-Check 与生命周期      │
│    • Chart / CSV 统一收敛至 ArtifactStore (原子写入 + 统一 TTL + GC)   │
│    • SQL 查询结果由消息表 TOAST 极简直存，前端复用 TableResult 分页    │
│    • 敏感数据列级脱敏策略统一审计                                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 具体落地实施规范

### 6.1 后端工件存储收敛与生命周期（`backend/app/artifacts/`）

1. **统一模型声明** (`schemas.py`):
   ```python
   class ArtifactKind(str, Enum):
       CHART = "chart_spec"
       FILE_EXPORT = "file_export"

   class BaseArtifactRecord(BaseModel):
       artifact_id: str
       kind: ArtifactKind
       tool_call_id: Optional[str] = None
       created_by: str = "main"  # 支持主智能体与各子智能体
       created_at: str
       expires_at: str
       stored_path: str
       payload: dict[str, Any]
   ```

2. **统一原子写与生命周期 GC** (`store.py`):
   - 物理写入采用 `tempfile + os.replace`（Windows 同卷原子替换），消除脏读风险；
   - FastAPI Lifespan 注册每 60 分钟后台定时 GC 任务，独立 `try...except` 保护防 Windows 文件占用中断。

3. **REST 路由统一与向后兼容** (`routers/artifacts.py`):
   - 统一收敛至 `/api/chat/artifacts/{artifact_id}` 与 `/api/chat/artifacts/{artifact_id}/download`；
   - 对既有 `/api/chat/charts/{id}` 与 `/api/chat/files/{id}` 做透明转发兼容。

---

### 6.2 工具层泛型解耦（`chart_artifact_tool.py` & `csv_export_tool.py`）

1. **参数与状态解耦**：
   - `required_skill: str = ""` 设为可选参数；
   - 运行时泛型升级为 `ToolRuntime[RequestContext, Any]`，适配 `CustomState`，为主智能体未来直接复用扫清障碍；
2. **保持 Prompt 裁剪契约**：
   - 发生异常时统一 `raise ToolException(f"Error: ...")`，确保 `PromptCompilerMiddleware` 的 5 阶段预扫描与脱敏稳定运作。

---

### 6.3 前端复合 UI 交互重构（`MessageItem.vue` / 子组件抽取）

1. **组件解耦与多图表 Tab 卡片**：
   - 抽取 `ChartGroupCard.vue`，当多张图表并存时自动聚合为 Tab 切换卡片；
2. **多 SQL 表格按子智能体分组与分页**：
   - 抽取 `QueryResultGroup.vue`，按 `subagent_name` 聚合展示多表格，复用 [`TableResult.vue`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/frontend/src/components/artifacts/TableResult.vue) 内置分页栏；
   - 统一使用 [`SUBAGENT_TITLES`](file:///F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/frontend/src/utils/helpers.ts) 映射标题（统一显示为 `SQL数据专家`）。

---

### 6.4 子智能体专属工件就近内嵌与自闭环工作台（`SubagentCard.vue` · Phase 2 扩展）

1. **就近内嵌渲染矩阵**：
   - `SubagentCard.vue` 引入 `artifactsPool?: Record<string, any>`，基于 `tool_call_id` 建立精准索引；
   - `sql_db_query` 节点就近内嵌带原生 20/50/100 分页与截断提示的 `<QueryResultGroup>` / `<TableResult>`；
   - `export_to_csv` 节点就近内嵌精致 CSV 下载卡（通过 `@/api/exports` 的 `triggerExportDownload` 安全下载）；
   - `build_chart_artifact` 节点就近内嵌 `<ChartArtifactCard>` 支持实时图表交互与全屏放大。
2. **全景消重与降级闭环**：
   - `MessageItem.vue` 当存在子智能体时，外层的表格、图表与内联 CSV 下载卡全景自动隐藏消重；无子智能体时作为外层兜底容器展示。
3. **智能展开策略**：
   - 当子智能体包含未折叠的结构化工件产出或处于 `running` 状态时，卡片智能默认保持展开，提升用户分析效率。

---

## 7. 分阶段实施路线图

| 阶段 | 优先级 | 核心任务 | 当前状态 / 解决的痛点 |
| :--- | :---: | :--- | :--- |
| **Phase 0**<br>(工件持久化与流式分流) | 🔴 **P0** | 1. 工具自身携带内部真实 `tool_call_id` 并由 SSE 信封携带 `subagent_id` 溯源<br>2. `chat_messages` 增加 `tool_artifacts` 列，并在 `final` 及 `interrupt` 事件 100% 同步落库<br>3. 前端基于 Pinia 工件池以 `tool_call_id` 唯一索引<br>4. `MessageItem.vue` 支持多图表与多 CSV 导出卡片并列展示，F5 刷新历史 100% 原样复原 | **✅ 已落地闭环并经 CC 审查通过 (53 passed)**<br>• 彻底解决 F5 刷新后图表/CSV/表格消失；<br>• 彻底消除多子智能体工件并发覆盖；<br>• 数据库已完整保存多 SQL 查询明细。 |
| **Phase 1**<br>(状态治理与图拓扑隔离) | 🟡 **P1** | 1. 采用 Context API (`context_schema=RequestContext`) 传输单轮大体量 DDL/知识切片，0 字节入 Checkpoint<br>2. 状态物理沙箱隔离：父图 `CustomState` 瘦身，子图 `SqlSubAgentState` 私有持有技能状态，彻底消除并发写冲突<br>3. 主子职责分离：主 Agent 纯净编排，SQL 子智能体独占拥有 SkillMiddleware 与 DDL 编译能力，维持既有错误自愈回路 | **✅ 已落地闭环并通过全量回归测试 (26 passed)**<br>• 彻底消除父图并发写冲突（INVALID_CONCURRENT_GRAPH_UPDATE）；<br>• 彻底消除检索切片对 Checkpoint 的上下文污染；<br>• 降低 Checkpoint 序列化体积 90% 以上；<br>• 服务层直接从 `req_context` 提取 RAG/Lexicon 事件并稳定推送。 |
| **Phase 2 & 扩展**<br>(工件收敛与自闭环专家卡片) | 🟢 **P2** | 1. 合并 `chart_artifacts` 与 `export_files` 物理落盘为统一 `ArtifactStore`（原子写 + 统一 24h TTL + 后台定期 GC），彻底清理历史垫片<br>2. `sql_db_query` 确立 DB 直存极简裁决，0 磁盘 IO，F5 刷新 0 秒秒开<br>3. 图表与 CSV 工具解耦 `required_skill`，统一纯正 `ToolRuntime`，根治 `CallableSchema` 崩溃，开启严格 Schema 验证<br>4. **子智能体专属工件就近内嵌**：`SubagentCard` 内嵌数据表、CSV 下载卡与图表预览，外层全景消重，实现智能体完整工作台 | **✅ 已全量落地闭环并经 CC 审查通过 (Approved · 82 passed)**<br>• 统一物理工件生命周期治理与路径防越权；<br>• 彻底解除主子智能体复用工件工具的阻碍；<br>• 彻底消除“执行在卡片内、表格在卡片外”的空间割裂感；<br>• 前端 `vue-tsc` + `vite build` 100% 编译通过（0 错误）。 |
| **Phase 3**<br>(韧性演进) | ⚪ **P3** | 1. Checkpoint 体积与 P95 序列化延迟监控告警<br>2. SSE 断线 Last-Event-ID 续传机制 | **规划中**<br>• 高并发环境下的系统韧性与自愈保障。 |

