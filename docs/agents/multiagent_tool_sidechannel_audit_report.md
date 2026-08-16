# 主子智能体架构下工具侧信道、状态隔离与流式分流深度审查报告

> **文档版本**：v2.0 (Claude Code 跨 Agent 联合评审终版)  
> **文档位置**：`docs/agents/multiagent_tool_sidechannel_audit_report.md`  
> **审查对象**：主子智能体协同体系（`deepagents` / `CompiledSubAgent`）下的工具侧信道机制、状态机（`CustomState`）各维度隔离性、工件持久化闭环、SSE 流式分流协议与前端回放渲染链路。  
> **评审基准**：由 Antigravity 提出架构分析，经 Claude Code（`w4:p1`）完成跨 Agent 独立对审并修正吸收。

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
2. **Claim-Check 存储落盘**：调用 `create_chart_record`，将完整配置和 `rows` 写入服务端工件目录（`settings.chart_artifact_dir/{chart_id}.json`），附带 24 小时 TTL 有效期；
3. **双轨交付**：
   - **主信道（给大模型）**：仅返回 `chart_ref`（`chart_id` + 标题），避免海量数据点灌入 Prompt；
   - **State 侧信道（给前端）**：通过 `Command(update={"tool_artifact": chart_spec})` 挂载完整渲染数据；
4. **流式直推时机（为什么图表比文字快）**：
   - 工具执行完毕时，LangGraph 产出 `updates` 状态增量；
   - `chat_service.py` 捕获到 `tool_artifact`，在毫秒级通过 SSE 向前端发射 `type: "tool_artifact"`；
   - 前端接收后，ECharts **即刻渲染出图，无需等待后续大模型总结文字打字机完成**。

### 2.2 CSV 导出工具：`export_to_csv`
1. **物理隔离与 OOM 熔断**：数据库查询结果直接流式落盘为 `export_xxx.csv`，受 `sql_export_max_rows` 硬上限保护；
2. **敏感路径物理脱敏**：向消息流返回元数据前，主动过滤掉 `stored_path` 服务器物理绝对路径；
3. **纯 Claim-Check**：LLM 上下文与 State 零 Token 消耗，前端通过 `/api/files/download/{file_id}` 异步下载。

### 2.3 SQL 查询工具：`sql_db_query`
1. **截断保护与提示引导**：结果超过 `sql_result_hard_limit` 时，主信道仅暴露前 5~10 行预览并发出截断警告，引导转调 `export_to_csv`；
2. **实时结构化表格直推**：通过 `tool_artifact`（`kind: "query_result"`）下发，前端在消息顶部渲染带行数统计与截断标识的交互式数据表格。

---

## 3. 全系统六大维度架构深度评估与裁决

### 3.1 维度一：领域技能与场景状态层（Skills & Scenario State）
- **代码位置**：`backend/app/agent/state.py:37-40`
  ```python
  skills_loaded: NotRequired[Annotated[List[str], _last_wins]]
  scenarios_loaded: NotRequired[Annotated[List[str], _last_wins]]
  active_skill: NotRequired[Annotated[str | None, _last_wins]]
  ```
- **现象与风险**：若多子智能体并发执行（子智能体 1 加载【涂装缺陷技能】，子智能体 2 加载【车间物流技能】），`_last_wins` Reducer 会导致后完成者的技能列表直接覆盖先完成者，多轮对话中前序技能被静默抹除。
- **架构裁决（主图持有 + 只读投影下发）**：
  - **核心原则**：**主图维护当前会话的 `skills_loaded` 唯一真相源（Single Source of Truth），在 `task` 委派时作为只读上下文深拷贝下发给子图；子图严禁将技能状态回传污染父图**。
  - **防坑纠偏**：不能做完全的“子图隔离断联”，否则同一轮会话中连续派发的子任务无法继承前序任务已激活的领域技能（导致跨 task 重复加载开销）。

---

### 3.2 维度二：业务知识 RAG 检索层（RAG & Context Injection）
- **代码位置**：`backend/app/agent/state.py:41-42`
  ```python
  rag_context: NotRequired[Annotated[List[Document], _last_wins]]
  rag_query: NotRequired[Annotated[str, _last_wins]]
  ```
- **现象与风险**：多子智能体各自检索领域文档回传父图时，`_last_wins` 导致非最后到达的参考文档全盘丢失。
- **架构裁决（单向消费机制 + 子图出口收口）**：
  - **核心原则**：**RAG 检索上下文只向下派发，子智能体完成后仅返回高层业务结论与工件引用，出口白名单剔除 `rag_context` 回写（One-Way Downstream Context）**。
  - **论证**：子图无需将几千 Token 的原始切片文档塞回父图，彻底根除父图 State 并发写冲突，大幅减轻 Checkpoint 存储与 Token 膨胀。

---

### 3.3 维度三：物理词典与列值消歧层（Database Value Lexicon）
- **代码位置**：`backend/app/agent/state.py:44`
  ```python
  lexicon_context: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
  ```
- **现象与风险**：并发子智能体探查到的列值映射字典在写入 `lexicon_context` 时发生单槽位冲刷覆盖。
- **架构裁决（黑盒辅助草稿隔离）**：
  - **核心原则**：**物理词典消歧属于 SQL 子智能体编写 SQL 的内部辅助工具，单向消费，不回传父智能体**。
  - **论证**：主 Agent 只关心最终数据结论，无需感知物理底层 `model_code = 'AU721'` 的映射细节。

---

### 3.4 维度四：人机协同与中断恢复层（HITL Interrupt & Resume）
- **代码位置**：`backend/app/routers/chat.py:460-472`
- **评估现状**：
  - 目前系统中，意图澄清与确认通常发生在大模型规划的最前端（由主 Agent 发起），主链路的中断与 `/resume` 恢复运行正常；
  - 若未来涉及子图深层内部中断，保持观测并作为次要扩展项，当前无需过度设计。

---

### 3.5 维度五：工具侧信道与工件持久化层（Tool Artifacts & Persistence）
- **代码位置**：`state.py:45`、`models.py:31-53`、`MessageItem.vue:797-878`
- **核心断裂点与评审纠偏**：
  1. **并发覆盖**：主 Agent 无图表仲裁逻辑，全局 State 的 `tool_artifact` 采用 `_last_wins`，并发产生多个图表时仅保留最后一个；
  2. **刷新全军覆没（致命漏洞）**：
     - `chat_messages` 数据库表未存 `tool_artifact`，刷新后运行时内存清空；
     - 前端历史工具扫描只看外层主 Agent 的 `task`，`.filter(t => !t.subagent_id)` 把子智能体的 `build_chart_artifact`、`export_to_csv` 全盘过滤；
     - **CC 评审关键纠偏**：前端仅合并工具池**只能修复 Chart 和 CSV，修不了 SQL 预览表格**（因为 SQL 查询没有落盘独立 JSON，也没有 GET 端点）。**必须在后端 `chat_messages` 表增加 `tool_artifacts` 列并在 `final` 事件同步落库**，方可实现 100% 闭环复原！
  3. **异构工具翻牌式冲刷**：SQL 表格、图表、CSV 共用同一个 `tool_artifact` 键，链式调用时后一个产物瞬间抹除前一个产物的 UI 卡片；
  4. **图文脱节**：大模型文本总结了多张图表/文件，界面只展示最后一张图，给用户造成“幻觉”误解。

---

### 3.6 维度六：存储引擎与快照开销（Checkpointer Storage Bloat）
- **评估裁决**：
  - 当前系统数据规模下 PostgreSQL 承载能力充裕，遵循“避免过早优化（Premature Optimization）”原则，此项暂缓，优先攻克交互体验与状态隔离。

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
│    • Chart / CSV / QueryResult 统一管理与 TTL 过期回收                 │
│    • 敏感数据列级脱敏策略统一审计                                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 具体落地实施规范

### 6.1 后端 SSE 事件信封与数据库闭环（`chat_service.py` & `chat.py`）

1. **SSE 发射增加溯源字段**：
   ```python
   # chat_service.py
   if "tool_artifact" in state_update:
       artifact_val = state_update.get("tool_artifact")
       if artifact_val:
           await _emit({
               "type": "tool_artifact",
               "subagent_id": matched_call_id,
               "subagent_name": matched_subagent,
               "tool_call_id": matched_call_id, # 唯一工具调用 ID
               "artifact": artifact_val
           })
   ```

2. **`chat_messages` 表扩充与 final 落库**：
   - 数据库模型 `ChatMessage` 增加 `tool_artifacts = Column(Text, nullable=True)`；
   - 在 `chat.py` 的 `final` 事件捕获中，将累计收集的所有工件打包为 JSON 存入 `tool_artifacts`。

---

### 6.2 前端 Pinia Store 工件池升级（`messages.ts`）

```typescript
// messages.ts
// 以 tool_call_id 为唯一 Key 归集工件池
const memoryArtifactPool = ref<Record<string, Record<string, AnyArtifact>>>({})

const setStreamingArtifact = (
  sessionId: string,
  artifact: AnyArtifact,
  toolCallId?: string,
  subagentId?: string
) => {
  const msg = getCurrentStreamingMessage(sessionId)
  if (!msg) return
  const artifactKey = toolCallId || artifact.chart_id || artifact.file_id || 'default'
  if (!memoryArtifactPool.value[msg.id]) {
    memoryArtifactPool.value[msg.id] = {}
  }
  memoryArtifactPool.value[msg.id][artifactKey] = {
    ...artifact,
    tool_call_id: toolCallId,
    subagent_id: subagentId
  }
}
```

---

### 6.3 前端组件渲染合并与容器重构（`MessageItem.vue`）

```typescript
// 1. 合并主 Agent 与所有子智能体的【工具调用列表】
const allEffectiveToolCalls = computed<StreamToolCall[]>(() => {
  const mainCalls = toolCallList.value
  const subCalls = subagentsList.value.flatMap(sub => sub.toolCalls || [])
  return [...mainCalls, ...subCalls]
})

// 2. 合并主 Agent 与所有子智能体的【工具结果字典】
const allEffectiveToolResults = computed<Record<string, string>>(() => {
  const merged = { ...rawToolResults.value }
  for (const sub of subagentsList.value) {
    if (sub.toolResults) {
      Object.assign(merged, sub.toolResults)
    }
  }
  return merged
})

// 3. 多工件聚合解析（优先使用落库的 tool_artifacts，无落库时走合并工具池兜底）
const currentArtifacts = computed<Record<string, AnyArtifact>>(() => {
  const msg = props.message as Message
  if (msg.tool_artifacts) {
    return parseJson<Record<string, AnyArtifact>>(msg.tool_artifacts) || {}
  }
  const msgId = msg.id
  if (msgId && messagesStore.memoryArtifactPool[msgId]) {
    return messagesStore.memoryArtifactPool[msgId]
  }
  return {}
})
```

---

## 7. 分阶段实施路线图

| 阶段 | 优先级 | 核心任务 | 当前状态 / 解决的痛点 |
| :--- | :---: | :--- | :--- |
| **Phase 0**<br>(工件持久化与流式分流) | 🔴 **P0** | 1. 工具自身携带内部真实 `tool_call_id` 并由 SSE 信封携带 `subagent_id` 溯源<br>2. `chat_messages` 增加 `tool_artifacts` 列，并在 `final` 及 `interrupt` 事件 100% 同步落库<br>3. 前端基于 Pinia 工件池以 `tool_call_id` 唯一索引<br>4. `MessageItem.vue` 支持多图表与多 CSV 导出卡片并列展示，F5 刷新历史 100% 原样复原 | **✅ 已落地闭环并经 CC 审查通过 (53 passed)**<br>• 彻底解决 F5 刷新后图表/CSV/表格消失；<br>• 彻底消除多子智能体工件并发覆盖；<br>• 数据库已完整保存多 SQL 查询明细。 |
| **Phase 1**<br>(状态治理与图拓扑隔离) | 🟡 **P1** | 1. `skills_loaded` 改为主图持有 + task 派发时只读投影<br>2. 子图出口白名单收口，剔除 `rag_context` 与 `lexicon_context` 回写父图 State<br>3. 子智能体异常统一封装 `FailedResult` 结构化回传 | **待启动**<br>• 消除父图并发写冲突；<br>• 消除跨 task 重复加载技能；<br>• 降低 Checkpoint 序列化体积。 |
| **Phase 2**<br>(工件收敛与复合 UI) | 🟢 **P2** | 1. Chart / CSV / QueryResult 收敛到统一 Artifact Store 与 TTL 管理<br>2. 前端 `MessageItem.vue` 重构复合展示容器（多图表 Tab 轮播、多 SQL 表格按子智能体分 Tab/折叠展示） | **待启动**<br>• 统一敏感数据脱敏策略；<br>• 提升多 SQL 表格与多图表并存时的交互体验。 |
| **Phase 3**<br>(韧性演进) | ⚪ **P3** | 1. Checkpoint 体积与 P95 序列化延迟监控告警<br>2. SSE 断线 Last-Event-ID 续传机制 | **规划中**<br>• 高并发环境下的系统韧性与自愈保障。 |

