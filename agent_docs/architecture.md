# 项目架构速览

> 从 CLAUDE.md 迁出，仅在需要了解项目整体结构时读取。

## 项目概述

这是一个面向生产数据查询场景的**大模型聊天会话管理系统**，当前核心形态是：

- 多会话聊天 UI
- SQL Agent 查询与分析
- Skills 业务领域知识加载
- 场景级技能（scenario skill）扩展
- RAG 检索增强（PGVector / Milvus Hybrid）
- 结构化流式 SSE 输出
- Agent 状态持久化与自动摘要

## 技术栈

| 层         | 技术                                                    |
| ---------- | ------------------------------------------------------- |
| 后端       | FastAPI + SQLAlchemy + PostgreSQL + LangChain/LangGraph |
| 前端       | Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS        |
| LLM        | DeepSeek / OpenAI 兼容接口 / Ollama（可选）             |
| 状态持久化 | AsyncPostgresSaver / PostgresSaver                      |
| 检索增强   | PGVector / Milvus Hybrid + 可选 NVIDIA Rerank           |

## 后端主链路

- `backend/app/api.py` — FastAPI 路由入口，处理会话、消息、聊天和文件下载接口
- `backend/app/services.py` — FastAPI 本地模式 Agent 适配层，提供 `process_message()` / `process_stream()`
- `backend/app/services_graph.py` — LangGraph 托管/Dev 模式 Agent 适配层
- `backend/app/config.py` — 应用级配置（模型、数据库、RAG 等）
- `backend/app/chart_artifacts.py` — ECharts 图表 artifact 生成与缓存
- `backend/app/agent/service.py` — SQL Agent 核心装配，管理模型、工具、middleware、skills、RAG 与 checkpointer
- `backend/app/agent/tools/` — SQL 查询、安全检查、CSV 导出、技能工具
- `backend/app/agent/middleware/` — `SkillMiddleware`、`BusinessRagMiddleware`、`ContextWarningMiddleware`
- `backend/app/agent/development/` — Agent 开发配置、数据加载、Hybrid 与 Vector 开发工具
- `backend/app/skills/` — 领域技能、场景技能、注册与自动发现
- `backend/app/agent/vector/` — PGVector / Milvus Hybrid / rerank / 初始化工具

## 前端主链路

- `frontend/src/views/ChatView.vue` — 聊天主界面
- `frontend/src/composables/useChatStream.ts` — 流式聊天与 SSE 事件消费
- `frontend/src/composables/useConfirmation.ts` — 危险操作确认逻辑
- `frontend/src/stores/messages.ts` — 消息状态与流式状态（Pinia Setup Store）
- `frontend/src/stores/sessions.ts` — 会话列表与当前会话状态
- `frontend/src/components/MessageItem.vue` — 助手完成态 Markdown 渲染
- `frontend/src/components/ChartArtifactCard.vue` — ECharts 图表 artifact 卡片展示
- `frontend/src/components/EmptyState.vue` — 空状态欢迎占位
- `frontend/src/api/chat.ts` — 聊天流式 API
- `frontend/src/api/sessions.ts` — 会话 CRUD API
- `frontend/src/api/messages.ts` — 消息历史 API
- `frontend/src/api/exports.ts` — 文件下载 API
- `frontend/src/api/charts.ts` — 图表 artifact API

## 目录结构

```text
backend/app/
  api.py
  services.py
  services_graph.py
  config.py
  chart_artifacts.py
  agent/
  skills/

frontend/src/
  api/
  components/
  composables/
  stores/
  views/

docs/
  backend/
  obsidian/
  todolist/
```
