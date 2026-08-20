# 多智能体侧信道与工件体系架构知识库 (Multi-Agent Sidechannel & Tool Architecture)

> **知识库定位**：收录本项目在 Supervisor-Worker 分层协同、基于 State 的工具侧信道设计、工件 Claim-Check 存储底座、子智能体卡片就近内嵌以及面向 Agent 的工具开发规范等核心架构资产。

---

## 📚 目录与精选文档

### 1. 架构总纲与审查报告 (Audit & Roadmap)
- **[`multiagent_tool_sidechannel_audit_report.md`](./multiagent_tool_sidechannel_audit_report.md)**
  - **核心内容**：多智能体架构下工具侧信道、状态隔离与流式分流深度审查总纲（v3.0 终版）。
  - **涵盖范围**：全系统六大维度架构评估、TOAST / `ArtifactStore` 双轨持久化方案、子智能体专属工件就近内嵌以及 Phase 0~3 实施路线图。

### 2. 模式研究与理论依据 (Theoretical Foundations)
- **[`state_sidechannel_multiagent_report.md`](./state_sidechannel_multiagent_report.md)**
  - **核心内容**：基于 State 的侧信道设计模式与行业实践深度研究报告。
  - **涵盖范围**：全局黑板、工件凭证（Claim-Check）、状态投影（Projection）、增量聚合器（Reducer）等 6 种模式分析，以及行业顶级框架（LangGraph、Anthropic、AutoGen、OpenAI）的对比评测。

### 3. 工程规范与开发实战 (Development & Best Practices)
- **[`tool_development_and_error_handling_guide.md`](./tool_development_and_error_handling_guide.md)**
  - **核心内容**：LangChain 自定义工具开发、参数 Schema 隔离与异常拦截最佳实践指南。
  - **涵盖范围**：四项核心铁律（`raise ToolException`、`handle_tool_error=True`、`"Error: "` 契约前缀、纯正 `ToolRuntime` 注入）、Pydantic `args_schema` 隔离根治 `CallableSchema` 崩溃，以及实战代码模板。

---

## 🚀 建议阅读顺序

1. **新上手开发者 / 工具开发者**：优先通读 **《3. 工具开发与异常拦截指南》**，掌握工具编写的四大铁律与标准模板；
2. **架构师 / 核心维护者**：先读 **《1. 深度审查总纲报告》** 理解系统演进与路线图，再读 **《2. 模式与理论报告》** 理解底层设计权衡与边界。
