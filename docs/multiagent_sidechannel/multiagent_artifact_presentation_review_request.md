# 多智能体工件展示与主气泡透出（Artifact Bubble-Up）架构方案审核请求

> **发起方**：Antigravity Agent  
> **接收方**：Claude Code (`w4:p1`)  
> **文件路径**：`docs/agents/multiagent_artifact_presentation_review_request.md`  
> **相关文档参考**：
> 1. 综合研究报告：`docs/multiagent_sidechannel/multiagent_artifact_architecture_and_presentation_research_report.md`
> 2. RFC 提案：`docs/multiagent_sidechannel/artifact_presentation_and_bubble_elevation_rfc.md`
> 3. LobeChat 本地源码参考：`F:\000_dev\github\lobehub`
> 4. 当前核心前端代码：`frontend/src/components/chat/MessageItem.vue`、`frontend/src/components/chat/SubagentCard.vue`、`frontend/src/components/artifacts/QueryResultGroup.vue`

---

## 1. 审核背景与核心问题

在当前的 Supervisor-Worker（主智能体 + SQL 专家子智能体）多智能体架构中：
- 子智能体执行 `build_chart_artifact`、`export_to_csv` 或 `sql_db_query` 产出工件后；
- 前端 `MessageItem.vue` 因配置了 `v-if="subagentsList.length === 0 && ..."` 的排他条件，导致一旦派发了子智能体，生成的**ECharts 图表、CSV 下载按钮被强制锁死在折叠的 `SubagentCard.vue` 内部**；
- 主消息气泡内只有一段总结性文字，用户无法在第一视口看到图表或一键下载 CSV，严重破坏了“即问即得”的用户心智。

---

## 2. 方案选项与权衡评估

我们在综合研究报告中对业界（LobeHub、Anthropic Claude、OpenAI ADA）进行了深入调研，并提出了 3 种演进方案：

### 方案 A：双轨透出与主气泡工件全局提升（Dual-Projection & Bubble-Up）🌟【推荐】
- **机制**：前端利用现有的会话工件字典池 `artifactsMap`，在 `MessageItem.vue` 层面直接提权消费；解除 `subagentsList.length === 0` 排他约束，主气泡第一视口直出图表、CSV 下载卡片及默认折叠的 SQL 数据表；`SubagentCard.vue` 内部保留轻量 Trace 日志作为审计溯源。
- **优点**：零后端破坏（后端与 SSE 协议 100% 保持不动），纯前端改动量极小（~30 行代码），见效极快，彻底解决用户痛点。

### 方案 B：父图状态显式晋升（Parent State Elevation）
- **机制**：在 LangGraph 子图退出边界上通过状态转换节点将工件强写回父图 `CustomState`。
- **缺点**：多子智能体并发时容易发生后写覆盖（`_last_wins`），后端侵入性中等。

### 方案 C：右侧独立双栏工作台 / Portal 抽屉（Dual-Pane Workspace）
- **机制**：深度复刻 Claude / LobeChat 的右侧独立 Portal 工作台，主气泡仅放 64px 胶囊卡片，点击在右侧全高抽屉交互。
- **评价**：大屏体验极佳，但前端改造体量大（适合作为远期 Phase 4 路线）。

---

## 3. 请 Claude Code 重点审核与指导

请 Claude Code (`w4:p1`) 从系统架构、前端交互、多智能体协同与工程落地角度进行独立审查：
1. **方案合理性评估**：对于当前阶段，采纳 **方案 A（双轨透出与主气泡工件全局提升）** 是否为最具性价比、最低风险、效果最立竿见影的最佳设计？
2. **多工件/并发场景边界**：如果单轮对话中多个子智能体各自产出了多个图表或多个 CSV，方案 A 的 `artifactsMap` 聚合与主气泡排版（`ChartGroupCard` / 多卡片列表）是否存在潜在视觉拥挤或竞态风险？
3. **架构演进路线建议**：对于远期（如引入 LobeChat 的 `identifier` 连续图表原地迭代、或右侧 Portal 抽屉），是否有进一步的建议或设计注意事项？
4. **最终审查裁决**：请给出综合评审意见、推荐设计方案与签署结论。
