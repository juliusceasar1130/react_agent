# 文档索引

本文档目录按主题归类，便于快速定位。

## 📂 目录说明

| 目录 | 说明 |
|:---|:---|
| `architecture/` | 系统架构设计（120JPH 系列架构图、RAG 架构、技能架构） |
| `business/` | 业务场景与需求（涂装车间数据查询、缺陷追溯、滞留车检测） |
| `deployment/` | 部署与运维（本地大模型部署、vLLM、LangChain/PostgreSQL 配置） |
| `development/` | 开发规范与指南（前后端开发规范、最佳实践、渲染指南） |
| `design-patterns/` | 设计模式与分析（AskUserQuestion、上下文持久化、SQL 截断、内存与持久化） |
| `reference/` | 参考材料（架构图、关系图等） |

---

## 📋 文档清单

### 系统架构设计 (`architecture/`)

| 文件 | 说明 |
|:---|:---|
| `120jph_agent_architecture.md` | 120JPH 智能助手架构说明 |
| `120jph_agent_architecture_ppt.md` | 汇报版 PPT 架构图 |
| `120jph_agent_architecture.html` | 架构可视化 HTML |
| `120jph_agent_architecture.relationship.md` | 架构关系图 |
| `120jph_agent_harness_engineering.relationship.md` | Harness 工程关系图 |
| `120jph_agent_rag_architecture_detailed.relationship.md` | RAG 详细架构关系图 |
| `120jph_agent_rag_architecture_simplified.relationship.md` | RAG 简化架构关系图 |
| `120jph_skills_architecture.excalidraw` | 技能架构图（Excalidraw） |
| `120jph_skills_architecture_ppt.excalidraw` | 技能架构 PPT（Excalidraw） |

### 业务场景 (`business/`)

| 文件 | 说明 |
|:---|:---|
| `生产数据查询智能体需求.md` | 生产数据查询智能体需求文档 |
| `前后车身顺序及缺陷追溯架构设计.flowchart.md` | 缺陷追溯场景架构设计 |
| `滞留车检测场景架构设计.flowchart.md` | 滞留车检测场景架构设计 |

### 部署运维 (`deployment/`)

| 文件 | 说明 |
|:---|:---|
| `本地大模型部署与Agent架构选型技术方案报告.md` | 本地大模型部署与架构选型 |
| `vLLM 部署与多系统消息冲突解决方案.md` | vLLM 部署与消息冲突解决 |
| `llama.cpp 与 LangChain 配置要点总结.md` | llama.cpp + LangChain 配置 |
| `LangChain + PostgreSQL 注释识别最佳实践.md` | LangChain + PostgreSQL 最佳实践 |

### 开发规范 (`development/`)

| 文件 | 说明 |
|:---|:---|
| `开发规范与最佳实践.md` | 项目开发规范与最佳实践 |
| `agent_best_practices.md` | LangChain SQL Agent 最佳实践 |
| `前端聊天消息Markdown渲染开发指南.md` | 前端 Markdown 渲染指南 |
| `前后端与Nginx架构知识总结.md` | 前后端与 Nginx 架构总结 |
| `sql_agent.md` | SQL Agent 开发文档 |

### 设计模式 (`design-patterns/`)

| 文件 | 说明 |
|:---|:---|
| `ask_user_question_design_pattern.md` | AskUserQuestion 设计模式 |
| `clarification_turn_persistence_analysis.md` | 澄清轮次持久化分析 |
| `sql_result_truncation_analysis.md` | SQL 结果截断分析 |
| `langgraph_memory_and_persistence_guide.md` | LangGraph 内存与持久化指南 |
| `数据库日期时间记录与大模型处理分析报告.md` | 日期时间格式与大模型处理分析 |

### 参考材料 (`reference/`)

| 文件 | 说明 |
|:---|:---|
| `rearch_agent项目架构图.canvas` | 项目架构图（Obsidian Canvas） |

---

## 历史归档

| 操作 | 说明 |
|:---|:---|
| `reconstructed_system_prompt.py` | **已删除**（原 `docs/` 根目录），功能已被 `backend/app/agent/subagents/sql/base_system_prompt.md` + `prompts.py` 替代 |
