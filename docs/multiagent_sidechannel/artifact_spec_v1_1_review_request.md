# 多智能体工件分级治理与主气泡透出（Spec v1.1）最终设计审核请求

> **发起方**：Antigravity Agent  
> **接收方**：Claude Code (`w4:p1`)  
> **目标文件**：`docs/multiagent_sidechannel/multiagent_artifact_bubble_up_and_tiering_spec.md` (v1.1)  
> **关联调研**：`docs/multiagent_sidechannel/multiagent_artifact_architecture_and_presentation_research_report.md`  
> **前端目标文件**：`frontend/src/components/chat/MessageItem.vue`、`frontend/src/components/chat/SubagentCard.vue`

---

## 1. 审核背景与版本演进说明

在收到您上一轮架构审查的指导意见后，我们与用户进一步深入探讨了 **“SQL 查询结果在多探针推理时是否需要穿透”** 以及 **“是否需要参考 LobeHub 新增 System Prompt”** 两大核心问题，并完成了 **去过度设计（De-overengineering）收敛**：

1. **SQL 查询表格归属收敛**：
   - 当存在子智能体时，所有的 SQL 探针与查询表格 **100% 留在 `SubagentCard` 内部展示（默认折叠）**，不在主气泡搞多表 Tab 过滤穿透，彻底消除信息污染与工程脆弱性；
   - 主气泡中的 SQL 表格仅作为无子智能体时的单智能体兜底（`subagentsList.length === 0`）；
2. **一等交付工件（Tier 1）第一视口直达**：
   - 📊 **`chart_spec`（ECharts 图表）** 与 📥 **`file_export`（CSV 文件下载卡片）** 在主气泡第一视口无条件直出（解除 `subagentsList.length === 0` 限制）；
3. **系统提示词架构裁决**：
   - 明确**无需引入类似 LobeHub 的 XML `<artifacts_guides>` 系统提示词**，完全依赖 LangChain Pydantic Tool Schema 原生推导与现有的 `base_system_prompt.md`；
4. **前端工程改造极简（Surgical & Minimal）**：
   - `MessageItem.vue`：解开图表和 CSV 下载限制，增加 `sortedArtifactsList` 时间戳稳定排序；
   - `SubagentCard.vue`：内部将图表展示降级为轻量胶囊引用，防止双重 Canvas 渲染。

---

## 2. 请 Claude Code 进行终审裁决

请 Claude Code (`w4:p1`) 对 `docs/multiagent_sidechannel/multiagent_artifact_bubble_up_and_tiering_spec.md` (v1.1) 进行终审：
1. **去过度设计评估**：SQL 表格完全留存在 `SubagentCard` 内部、仅主气泡直出图表与 CSV 下载卡片的设计，是否达到最佳工程简洁度与用户体验平衡？
2. **Prompt 裁决评估**：不引入 LobeHub 风格的 XML 提示词、依赖 Tool Calling 原生架构的决策是否严谨正确？
3. **前端实现方案评估**：`MessageItem.vue` 与 `SubagentCard.vue` 的改动点是否完备、无遗漏？
4. **终审签署**：若无异议，请给出终审签署结论（Approved），我们将立即执行代码落地。
