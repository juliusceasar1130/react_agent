# Phase 0: 工具侧信道工件持久化闭环与多智能体流式分流规范 (Phase 0 Spec)

> **文档标识**：`phase0-tool-artifacts-persistence-and-streaming`  
> **文档路径**：`openspec/changes/phase0-tool-artifacts-persistence-and-streaming/spec.md`  
> **分类标签**：`ready-for-agent`  
> **基准审查**：基于 `docs/agents/multiagent_tool_sidechannel_audit_report.md` (v2.0 Claude Code 跨 Agent 联合评审终版)

---

## Problem Statement

从前端用户的视角来看，当前多智能体生产数据查询与分析系统在产物呈现上存在严重的断裂：

1. **刷新页面历史产物全部蒸发**：当用户在会话中获得了生成的 ECharts 图表、CSV 文件下载卡片或 SQL 数据预览表格后，一旦按 F5 刷新浏览器或切换会话，页面上的**图表卡片、CSV 下载按钮与数据明细表格彻底消失**，只剩下大模型的一段纯文本，用户无法再查看图表或下载刚导出的数据文件。
2. **多子智能体并发执行产物相互覆盖**：当用户的提问触发了多个子智能体并发绘图，或者在同一轮回答中连续触发了“SQL 查表 -> 图表生成 -> CSV 导出”多工具链式调用时，界面上的卡片像翻牌一样被后续工具瞬间抹除，用户永远只能看到最后生成的单个卡片。
3. **大模型回复与界面卡片脱节**：大模型在自然语言总结中明确提到“已为您分别生成了车间A与车间B的趋势图，并导出了明细表”，但界面上只展示了 1 个卡片（甚至刷新后变成 0 个），严重损害了系统的可信度与使用体验。

---

## Solution

从前端用户的视角来看，Phase 0 交付一个**“实时秒级出图出表、历史刷新 100% 还原、多工件稳定并存”**的无缝体验：

1. **历史产物秒级全量复原**：无论是 ECharts 交互图表、CSV 下载按钮，还是 SQL 结构化数据预览表格，在页面按 F5 刷新或重新进入历史会话时，**无需等待二次加载，100% 完整原样复原**。
2. **多工件独立并存无冲突**：多个子智能体并发产出的多份图表，以及复合任务中产出的表格、图表、导出文件，在界面上**各自占据独立卡片并存展示**，绝不互相顶替或被静默丢弃。
3. **打字机与出图无缝同步**：流式阶段图表与表格依然在工具执行完毕的瞬间即刻直出，后续大模型文字在下方流畅打字输出，流式实时态与历史完成态体验完全统一。

---

## User Stories

1. 作为业务分析师，我在查询“近7天各车型缺陷趋势”并获得 ECharts 折线图后，希望按 F5 刷新浏览器后图表依然完整展示在消息中，以便我无需重新向 Agent 提问就能随时查看图表。
2. 作为业务分析师，我在生成图表后希望能够自由放大、缩小图表区域并切换图例，以便进行深度数据探查。
3. 作为车间质量管理员，我在让 Agent “导出车间昨日全部下线车辆明细 CSV”并获得绿色下载卡片后，希望第二天重新打开该历史会话时下载按钮依然有效，以便直接点击下载历史报表。
4. 作为车间调度员，我在提问“查询当前涂装车间在制车”并获得消息顶部的灰白交替结构化 SQL 预览表格后，希望刷新页面后表格依然保留，以便清晰核对各列物理字段值。
5. 作为企业管理层，当我提出一个跨车间对比问题触发 2 个子智能体分别绘制“涂装车间图”和“总装车间图”时，我希望在消息卡片中同时看到这两份图表，而不是先画出来的图被后画出来的图覆盖。
6. 作为业务分析师，当我在一个任务中同时要求“查出前50条数据、画出趋势图并导出 CSV 文件”时，我希望在界面上同时看到数据表格、趋势图和 CSV 下载卡片三者并存，而不是后执行的工具冲刷掉前序工具。
7. 作为系统用户，我希望在多子智能体并发运行并输出思考过程（Reasoning）时，各个子智能体的思考过程独立折叠展示，不发生文字混流与串行乱码。
8. 作为系统用户，当我切换左侧会话列表中的历史会话时，我希望历史消息里的所有图表和文件卡片能在 100 毫秒内即刻渲染完成，不需要感知额外的后端网络请求延迟。
9. 作为业务审计人员，我希望大模型在回复文本中引用的每一个图表标题和文件名称，都能在界面上方找到完全一致的对应卡片，消除任何图文脱节的幻觉感。
10. 作为前端开发者，我希望旧版本已保存的无工件扩展列的历史消息在加载时能够优雅降级，通过解析子智能体快照还原图表和 CSV 下载项，不出现前端白屏或报错。
11. 作为系统管理员，我希望当网络发生短暂抖动但 SSE 连接未断开时，最终消息保存时能够对本轮所有生成的工件进行一次性对齐校验，确保数据库记录的数据与前端屏幕一致。
12. 作为移动端或小屏幕用户，我希望生成的多个图表和数据表格在卡片容器内具有响应式自适应宽度，不发生横向溢出破坏聊天窗口布局。

---

## Implementation Decisions

### 1. 模块边界与架构分工决策 (Architectural Decisions)

- **数据库持久化层 (Database Truth Layer)**：
  - 升级 `chat_messages` 消息表结构，新增 `tool_artifacts` 文本字段（JSON 序列化存储）。
  - 在会话流式执行终点（`final` 汇总阶段），将当轮收集到的所有工件集合以字典形式原子写入该列，使消息表成为历史回放的绝对单点真相源（Single Source of Truth）。
- **SSE 流式传输协议层 (Streaming Delivery Layer)**：
  - 增强 `tool_artifact` 流式事件协议包体，强制挂载 `subagent_id`（子智能体任务 ID）、`subagent_name`（子智能体名称）以及 `tool_call_id`（工具调用唯一标识），形成防碰撞的事件信封。
- **前端状态机工件池 (Pinia State Management Layer)**：
  - 将前端运行时单值映射表升级为基于 `tool_call_id` 唯一索引的多工件字典池（Artifact Pool），彻底隔离不同子智能体与不同工具调用之间的状态空间。
- **前端组件视图渲染层 (Message Presentation Layer)**：
  - 在消息组件中构建穿透合并工具池（Merged Tool Pool），打平扫描主 Agent 与所有子智能体快照中的工具调用与结果。
  - 采用“优先读取落库工件字段，兜底降级走合并工具池”的双轨回放机制，完美兼容新老历史数据。

### 2. 关键数据契约与类型定义 (Data Contracts & Prototype Type Shapes)

#### A. 后端 SSE 事件信封契约 (SSE Envelope)
```json
{
  "type": "tool_artifact",
  "subagent_id": "call_task_9f8a",
  "subagent_name": "sql_domain_agent",
  "tool_call_id": "call_chart_01",
  "artifact": {
    "kind": "chart_spec",
    "chart_id": "cht_20260816_001",
    "chart_type": "line",
    "title": "车型缺陷趋势对比",
    "x_field": "dt",
    "series": [{ "name": "缺陷数", "field": "cnt" }],
    "rows": [{ "dt": "2026-08-10", "cnt": 12 }]
  }
}
```

#### B. 消息表持久化工件字段契约 (`chat_messages.tool_artifacts`)
```json
{
  "call_chart_01": {
    "kind": "chart_spec",
    "chart_id": "cht_20260816_001",
    "title": "车型缺陷趋势对比",
    "chart_type": "line",
    "x_field": "dt",
    "series": [{ "name": "缺陷数", "field": "cnt" }],
    "rows": [{ "dt": "2026-08-10", "cnt": 12 }]
  },
  "call_export_01": {
    "kind": "file_export",
    "file_id": "exp_20260816_002",
    "filename": "defect_details.csv",
    "row_count": 120,
    "col_count": 8,
    "size_bytes": 45020
  },
  "call_sql_01": {
    "kind": "query_result",
    "columns": ["dt", "car_model", "defect_cnt"],
    "rows": [["2026-08-10", "Audi A7", 12]],
    "row_count": 1,
    "truncated": false
  }
}
```

#### C. 前端工件池索引规则 (Frontend Artifact Pool)
- 强制以 **`tool_call_id`** 作为主键索引：`memoryArtifactPool[messageId][toolCallId] = ArtifactPayload`。
- 严禁使用 `kind` 或 `default` 作为回退主键，防止异构工具相互冲刷。

---

## Testing Decisions

### 1. 测试原则 (Testing Principles)
- 严格遵循**外部黑盒行为测试（External Behavior-Driven）**，不绑定函数内部私有临时变量。
- 重点验证端到端生命周期的完整闭环：**“触发工具 -> SSE 信封校验 -> DB 数据落库 -> 模拟 F5 重新拉取消息 -> 校验工件完整复原”**。

### 2. 核心测试覆盖模块 (Test Targets)
- **后端持久化与路由集成测试**：
  - 测试 `ChatMessage` 模型 CRUD 对 `tool_artifacts` 字段的正确序列化与反序列化。
  - 测试 `/chat/stream` 路由在包含 `build_chart_artifact`、`export_to_csv`、`sql_db_query` 时，最终写入数据库的 `tool_artifacts` 字典完整性。
  - 测试 `/chat/sessions/{session_id}/messages` 接口能够正确返回包含 `tool_artifacts` 的消息列表。
- **多智能体并发工件隔离测试**：
  - 模拟 2 个子智能体并发返回不同的 `tool_artifact`，断言 SSE 事件独立携带有各自的 `subagent_id` 与 `tool_call_id`，且落库后两个工件均完整存在。
- **前端工具池穿透与渲染兼容测试**：
  - 单元测试验证：当传入嵌套有 `subagents` 的历史消息时，合并工具池能正确提取出子智能体内部的 `build_chart_artifact` 与 `export_to_csv` 引用。

### 3. 代码库先验参考 (Prior Art)
- `backend/tests/agent/test_custom_state_concurrent.py`（多智能体并发状态归约测试模式）
- `backend/tests/test_chat_sessions.py`（会话与消息 CRUD 集成测试模式）

---

## Out of Scope

以下内容不属于 Phase 0 的交付范围，将在后续阶段推进：

1. **Phase 1 状态机重构**：将 `skills_loaded` / `rag_context` / `lexicon_context` 完全移出父图 State 并建立只读投影机制。
2. **Phase 2 UI 复合容器重构**：将多图表展示升级为 Tab 轮播组件、多 SQL 查询表格升级为按子智能体分 Tab/多折叠面板容器（Phase 0 保持图表与 CSV 垂直卡片列表并存展示，多 SQL 查询数据在数据库工件池中已全量落库保存）。
3. **Phase 3 断线重连**：基于 SSE `Last-Event-ID` 的断线自动续传。
4. **统一工件存储中心**：将 SQL 查询预览数据单独抽取为独立后端工件文件。

---

## Further Notes

- **零破坏平滑迁移**：`chat_messages.tool_artifacts` 列设计为 `nullable=True`。对于系统中已经存在的旧历史消息，列值为 `None`，前端自动平滑降级执行 `Merged Tool Pool` 进行快照解析，保证存量历史数据绝对安全、零报错。
- **性能评估**：`tool_artifacts` 仅存储在消息表中，不参与 LangGraph 内部的逐步 Checkpointer 序列化，不会对多轮会话的图执行速度造成任何负担。

