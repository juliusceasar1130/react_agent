# DeepAgent 多智能体架构文档中心 (Documentation Hub)

> 本目录收录了系统从“单一 Text-to-SQL 智能体”升级为“企业级通用多智能体系统 (Generic Enterprise Multi-Agent Platform)”过程中的核心技术报告、架构决策记录 (ADR)、系统规格说明 (Spec) 与重构演进路线图。

---

## 🗺️ 文档导航与分类地图 (Taxonomy & Navigation)

```
docs/deepagent/
├── README.md                              # 📖 本文档（全局导航与知识索引）
│
├── 🏛️ 核心基石与架构决策 (ADR & Knowledge)
│   ├── architecture_review_report.md      # 多智能体架构技术选型与深度审计报告 (为什么选择 deepagents + 隐式路由)
│   ├── rag_single_retrieval_spec.md       # 单点 RAG 检索与 State 状态深拷贝继承机制权威规范
│   └── refactoring_roadmap.md             # Stage 0 ~ Wave 4 架构重构与物理解耦全量落地路线图
│
└── 🚀 演进蓝图与系统规格 (Future Evolution & Specs)
    ├── generic_agent_architecture_report.md # 通用企业级智能体平台长远演进蓝图 (RAG/数据研报/长任务规划)
    ├── multi_agent_system_spec.md         # 通用多智能体系统需求总规格书 (System Spec)
    └── phase1_implementation_spec.md      # 第一阶段实施规范 (SQL Sub-Agent + 状态流式感知)
```

---

## 📚 详细文档索引与阅读指南

### 一、 核心基石与架构决策（必读 / 长期维护）

| 文档名称 | 定位与核心内容 | 关键决策 / 适用场景 |
| :--- | :--- | :--- |
| **[`architecture_review_report.md`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/architecture_review_report.md)** | **核心架构决策 (ADR)**<br>审计多智能体方案，对比四种候选拓扑。 | 1. 否决 Supervisor 显式分类节点，消除 1 次额外 LLM 延迟（保住零 TTFT）。<br>2. 确立 `deepagents 0.7.5` 选择性挂载与隐式工具路由机制。<br>3. 确立 SQL 子智能体海量数据安全截断与 Tool Artifact 结构化透传铁律。 |
| **[`rag_single_retrieval_spec.md`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/rag_single_retrieval_spec.md)** | **RAG 状态继承规范**<br>解决多智能体循环中同 Turn 重复检索难题。 | 1. 基于 `deepagents/subagents.py` State 深拷贝机制，确立“主 Agent 入口单点检索 -> 子 Agent 自动继承状态”。<br>2. 彻底解决子图重型指令噪声稀释 Query 及重复检索延迟。 |
| **[`refactoring_roadmap.md`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/refactoring_roadmap.md)** | **架构重构演进基线**<br>记录系统全波次解耦过程。 | 完整记录 Stage 0（测试基线）到 Wave 1-4（后端 API 拆分、services 转包、SQL 子智能体归纳、前端领域化及 Shim 清理）的全部落地细节。 |

---

### 二、 演进蓝图与系统规格（前瞻规划 / 迭代指引）

| 文档名称 | 定位与核心内容 | 后续演进目标 |
| :--- | :--- | :--- |
| **[`generic_agent_architecture_report.md`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/generic_agent_architecture_report.md)** | **平台演进总蓝图**<br>从单一 Text-to-SQL 跃迁至通用智能体。 | 规划三大未来核心领域能力：<br>1. **Knowledge RAG Sub-Agent**（企业规程文档问答）；<br>2. **Deep Analyst Sub-Agent**（Python/ECharts 研报分析）；<br>3. **长流程多步规划 (Deep Research)**。 |
| **[`multi_agent_system_spec.md`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/multi_agent_system_spec.md)** | **多智能体总规格书**<br>多 Agent 协作交互契约。 | 规定主/子智能体上下文隔离、SSE 流式事件协议（`subagent_change`）、HITL 人机协同中断恢复机制。 |
| **[`phase1_implementation_spec.md`](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-deepagent/docs/deepagent/phase1_implementation_spec.md)** | **Phase 1 实施规范**<br>首个 SQL 专业子智能体落地。 | 作为 Phase 1（已完成）的技术规范，同时作为后续编制 **Phase 2（知识库与高级分析接入）** 的标准范式模版。 |
