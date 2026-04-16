# Project Context

更新时间: 2026-04-07 Asia/Shanghai
主要修改内容:
- 将项目定位从旧版通用聊天 / arXiv Agent 更新为当前 SQL Agent + Skills + RAG 体系
- 同步当前环境、流式协议、双模式持久化和业务约束
- 收敛为更适合 OpenSpec proposal/spec 编写的项目上下文说明

## Purpose

这是一个面向生产数据查询场景的**大模型聊天会话管理系统**。

当前项目主线不是通用论文搜索 Agent，而是：

- 多会话聊天与消息持久化
- SQL Agent 查询、统计与解释
- Skills 业务领域知识加载
- 场景级技能（scenario skill）扩展
- RAG 检索增强（PGVector / Milvus Hybrid）
- 结构化流式 SSE 输出
- CSV 导出下载链路
- Agent 状态持久化与自动摘要

## Tech Stack

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI + SQLAlchemy + PostgreSQL + LangChain/LangGraph |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS |
| LLM | DeepSeek / OpenAI 兼容接口 / Ollama（可选） |
| 状态持久化 | AsyncPostgresSaver / PostgresSaver |
| 检索增强 | PGVector / Milvus Hybrid + 可选 NVIDIA Rerank |

## Project Conventions

### Code Style

**后端（Python/FastAPI）**

- CRUD 更新操作使用 `model_dump(exclude_unset=True, exclude_none=True)`
- Response Schema 使用 Pydantic v2 `model_config = ConfigDict(from_attributes=True)`
- 主键统一使用 UUID 字符串
- 优先保持现有模块边界，避免不必要的大范围重构

**前端（Vue 3/TypeScript）**

- 使用 `<script setup>`
- 使用 Pinia Setup Store
- refs 按当前项目写法直接使用，不额外加 `.value`
- 流式阶段与完成态展示职责分离

**文档与记录**

- 新特性和重要优化记录到根目录 `changelog.md`
- `README.md` 记录主要项目特性和目录结构
- 项目长期偏好与背景优先同步到根目录 `memory.md`

### Architecture Patterns

**后端主链路**

```text
api.py
  -> services.py (FastAPI 兼容 Agent 适配层)
  -> agent/service.py (SQL Agent 核心装配)
  -> agent/tools + middleware + skills + vector
```

**关键架构约定**

- FastAPI 本地模式使用 `AsyncConnectionPool + AsyncPostgresSaver`
- LangGraph 托管 / Dev 模式由运行时接管 `checkpointer/store`
- 所有 Agent 调用都必须传递 `config["configurable"]["thread_id"] = session_id`
- 流式接口使用结构化事件协议：`token/status/tool_call/tool_result/final/error`
- 业务知识优先通过 `SkillMiddleware` 和 `BusinessRagMiddleware` 注入，而不是把全量 Schema 或大段说明直接塞进提示词

**技能与工具链路**

- 先加载领域技能（domain skill）
- 必要时再加载场景技能（scenario skill）
- SQL 查询、SQL 示例检索、CSV 导出都应遵守 `required_skill` 约束

### Testing Strategy

- 当前仓库以 `backend/app/test_*.py` 冒烟脚本与模块级验证为主
- 修改 Agent、RAG、skills、流式协议时，优先补充对应模块的针对性验证
- 若变更会影响前端流式展示或下载链路，应同时验证前后端交互

### Git Workflow

- 当前工作区可能处于功能分支，修改前不要假设固定主分支名称
- 保持最小改动原则，不随意回退用户已有修改
- 文档同步类调整可直接修改；涉及新能力、架构性变更或行为变化时，按 OpenSpec 流程先写 proposal

## Domain Context

- **SQL Agent**：项目核心智能体，负责业务数据库查询、统计和结果解释
- **Skills**：业务领域知识载体，按“领域 skill + 场景 skill”二级组织
- **required_skill**：执行 SQL 或检索历史 SQL 示例时必须声明的领域约束
- **BusinessRagMiddleware**：在模型调用前注入业务知识与示例
- **结构化 SSE**：前端默认重点展示最终答案，过程事件用于状态提示与调试
- **export_to_csv**：面向大结果集的导出工具，避免把完整明细塞回 LLM 上下文

## Important Constraints

- 严禁执行破坏性 SQL（如 `DROP`、`DELETE`、`UPDATE` 等）
- 统计类问题优先使用聚合 SQL，不要先拉大量原始数据再让模型汇总
- 查询结果若已被系统截断，不应基于截断结果继续做汇总分析；应改写为聚合 SQL 或建议导出 CSV
- 切换 `EMBEDDING_PROVIDER`（如 `ollama` / `llama_cpp`）后，需要重建对应向量库数据
- 不要再把项目理解为旧版 arXiv 工具场景；当前主线是 SQL Agent + Skills + RAG

## External Dependencies

- **DeepSeek / OpenAI-compatible API**：主要在线模型入口
- **PostgreSQL**：会话消息与 Agent checkpointer 存储
- **业务数据库**：SQL Agent 实际查询的数据源
- **PGVector / Milvus**：RAG 检索后端
- **Ollama / llama.cpp**：可选本地模型与 embedding 服务
- **NVIDIA NIM Rerank**：可选精排服务
