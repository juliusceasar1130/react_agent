# Project Context

## Purpose

这是一个**大模型聊天会话管理系统**，支持多会话管理、流式/非流式聊天输出、LangChain Agent 工具调用（arXiv 论文搜索）、对话历史持久化、Agent 状态管理（PostgresSaver）以及自动对话摘要（SummarizationMiddleware）。

## Tech Stack

| 层 | 技术 |
|---|------|
| **后端** | FastAPI + SQLAlchemy + PostgreSQL + LangChain + DeepSeek |
| **前端** | Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS |
| **状态存储** | PostgresSaver + psycopg_pool |
| **AI 集成** | langchain-deepseek |

## Project Conventions

### Code Style

**后端（Python/FastAPI）**
- CRUD 函数返回 `Optional[T]`
- 创建操作返回模型实例
- 更新使用 `model_dump(exclude_unset=True, exclude_none=True)` 过滤 None 值
- 所有 Response Schema 配置 `model_config = ConfigDict(from_attributes=True)`
- 使用 `Depends(get_db)` 注入数据库会话
- 主键统一使用 UUID 字符串

**前端（Vue 3/TypeScript）**
- 使用 `<script setup>` 语法
- Props 和 Emits 使用 TypeScript 接口/泛型定义
- 使用 Pinia Setup Stores，Refs 自动解包（不使用 `.value`）
- 使用 Tailwind CSS 工具类，响应式设计（移动优先）

### Architecture Patterns

**后端分层架构**
```
API Layer (api.py) → CRUD Layer (crud.py) → Database Layer (models.py)
                              ↓
                    Agent Service Layer (services.py)
                              ↓
                    PostgresSaver (checkpoints 表)
```

**数据流**
- `ChatSession` / `ChatMessage` 表：存储聊天记录，供前端查询展示
- `PostgresSaver` 检查点表：自动管理 Agent 状态和对话历史
- `thread_id` 对应系统的 `session_id`

**关键集成模式**
- PostgresSaver 使用 `ConnectionPool` 而非 `from_conn_string()`
- 所有 Agent 调用必须传递 `config = {"configurable": {"thread_id": str(session_id)}}`
- SummarizationMiddleware 在 token 超过 4000 时自动触发摘要

### Testing Strategy

- 后端：使用 FastAPI 测试客户端
- 单元测试覆盖 CRUD 操作和 Agent 服务
- 集成测试验证 API 端点和流式输出

### Git Workflow

- **主分支**: `master`
- **开发分支**: `production_sql`
- **分支策略**: 功能分支从 `master` 创建，合并前需通过测试
- **提交规范**: 使用 `git-commit` skill 创建结构化提交记录

## Domain Context

- **LLM 对话系统**：基于 DeepSeek 模型的对话生成
- **LangChain Agent**：支持工具调用的智能代理架构
- **PostgresSaver**：LangGraph 检查点存储，用于持久化 Agent 状态
- **流式输出（SSE）**：服务器发送事件实现实时流式响应
- **arXiv 工具**：论文搜索工具集成

## Important Constraints

- 首次启动 PostgresSaver 会自动创建检查点表（`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`）
- 会话删除时级联删除消息，但 PostgresSaver 检查点需要通过 Agent API 重建
- 前端不应重复调用 `createMessage()`，因为 `/message` 端点已创建用户消息

## External Dependencies

- **DeepSeek API**: LLM 模型提供商
- **PostgreSQL 15+**: 主数据库和检查点存储
- **arXiv API**: 论文搜索工具数据源
