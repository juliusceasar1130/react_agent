
# CLAUDE.md

This file provides repository-specific guidance for Claude Code when working in this project.

修改时间: 2026-04-07 Asia/Shanghai
主要修改内容:
- 同步当前项目环境为 `py312_agent`
- 将项目定位从旧版通用聊天/arXiv Agent 更新为当前 SQL Agent + Skills + RAG 架构
- 更新流式协议、持久化模式、目录结构与开发入口说明

## 使用优先级

当以下文档出现冲突时，优先级建议如下：

1. `AGENTS.md`
2. `memory.md`
3. `README.md`
4. 本文件 `CLAUDE.md`

涉及 proposal / spec / plan / 架构性变更时，优先查看 `openspec/AGENTS.md`。

## 项目概述

这是一个面向生产数据查询场景的**大模型聊天会话管理系统**，当前核心形态是：

- 多会话聊天 UI
- SQL Agent 查询与分析
- Skills 业务领域知识加载
- 场景级技能（scenario skill）扩展
- RAG 检索增强（PGVector / Milvus Hybrid）
- 结构化流式 SSE 输出
- Agent 状态持久化与自动摘要

## 当前技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI + SQLAlchemy + PostgreSQL + LangChain/LangGraph |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS |
| LLM | DeepSeek / OpenAI 兼容接口 / Ollama（可选） |
| 状态持久化 | AsyncPostgresSaver / PostgresSaver |
| 检索增强 | PGVector / Milvus Hybrid + 可选 NVIDIA Rerank |

## 开发环境

项目约定环境：

```bash
conda activate py312_agent
```

常用启动命令：

```bash
# 后端
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm run dev

# LangGraph Dev
conda activate py312_agent
langgraph dev --allow-blocking
```

Windows 下可直接使用：

```bat
start_langgraph_dev.bat
```

## 当前架构速览

### 后端主链路

- `backend/app/api.py`
  - FastAPI 路由入口
  - 处理会话、消息、聊天和文件下载接口
- `backend/app/services.py`
  - FastAPI 兼容 Agent 适配层
  - 提供 `process_message()` / `process_stream()`
  - 输出结构化流式事件
- `backend/app/agent/service.py`
  - SQL Agent 核心装配
  - 管理模型、工具、middleware、skills、RAG 与 checkpointer
- `backend/app/agent/tools/`
  - SQL 查询、安全检查、CSV 导出、技能工具
- `backend/app/agent/middleware/`
  - `SkillMiddleware`
  - `BusinessRagMiddleware`
- `backend/app/skills/`
  - 领域技能、场景技能、注册与自动发现
- `backend/app/agent/vector/`
  - PGVector / Milvus Hybrid / rerank / 初始化工具

### 前端主链路

- `frontend/src/views/ChatView.vue`
  - 聊天主界面
- `frontend/src/composables/useChatStream.ts`
  - 流式聊天与事件消费
- `frontend/src/stores/messages.ts`
  - 消息状态与流式状态
- `frontend/src/components/MessageItem.vue`
  - 助手完成态 Markdown 渲染
- `frontend/src/api/chat.ts`
  - 聊天相关 API

## 当前持久化模式

项目现在是“双模式”持久化，不应再只按旧版同步 `PostgresSaver` 理解：

- FastAPI 本地模式：
  - 使用 `AsyncConnectionPool + AsyncPostgresSaver`
  - 由 `backend/app/services.py` 启动阶段显式初始化
- LangGraph 托管 / Dev 模式：
  - graph 由 `backend/app/agent/service.py:build_agent_graph()` 提供
  - `checkpointer/store` 由 LangGraph 运行时托管注入或接管

关键约定：

- 所有 Agent 调用都必须传递 `config["configurable"]["thread_id"] = session_id`
- 自动历史管理依赖 checkpointer，不需要手工回放历史消息
- `SummarizationMiddleware` 仍在使用，但只是中间件的一部分，不再是唯一关键特性

## 当前流式协议

`/api/chat/stream` 已升级为结构化 SSE 事件协议，不再以旧版 `content + is_final` 为主。

核心事件类型：

- `token`
- `status`
- `tool_call`
- `tool_result`
- `final`
- `error`

其中：

- 前端默认只重点展示最终答案
- 过程事件主要用于轻量状态提示和调试
- `final` 事件中会聚合最终文本、工具调用和工具结果

## 当前核心能力

### SQL Agent

- 基于 LangChain/LangGraph 构建
- 主要面向业务数据库查询、统计与解释
- 严禁执行破坏性 SQL
- 强调聚合查询优先，避免把大量原始明细拉回模型再汇总

### Skills 体系

- 先加载领域技能（domain skill）
- 必要时再加载场景技能（scenario skill）
- 新场景采用目录聚合与自动发现机制
- SQL 工具调用时需要通过 `required_skill` 显式声明依赖领域

### RAG 检索增强

- 支持 `pgvector` 与 `milvus_hybrid`
- Milvus 支持 `ollama` 与 `llama.cpp` embedding provider
- 可选接入 NVIDIA Rerank

### 导出与下载

- 大结果集可走 `export_to_csv`
- 下载接口为 `GET /api/chat/files/{file_id}`
- 前端通过 `file_id` 下载，不暴露服务器绝对路径

## 重要目录

```text
backend/app/
  api.py
  services.py
  services_graph.py
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

openspec/
  AGENTS.md
  project.md
```

## 开发约定

### 后端

- CRUD 返回风格延续现有模式，更新操作使用 `model_dump(exclude_unset=True, exclude_none=True)`
- Response Schema 使用 Pydantic v2 `model_config = ConfigDict(from_attributes=True)`
- 主键统一使用 UUID 字符串
- 优先遵循现有模块边界，不随意把逻辑重新塞回单文件

### 前端

- 使用 `<script setup>`
- 使用 Pinia Setup Store
- refs 在 store 中按当前项目写法直接使用，不额外加 `.value`
- 流式阶段与完成态展示职责分离

### 文档维护

- 新特性和重要优化记录到 `changelog.md`
- `README.md` 主要记录项目特性和目录结构
- 若修改内容不适合写进源码文件，应在交付说明里给出修改时间与主要变更

## 常见注意点

### 1. 不要再把项目理解成 arXiv 论文搜索 Agent

历史上存在这类定位，但当前主线已经是 SQL Agent + Skills + RAG。

### 2. 不要默认使用旧版流式格式

现在应优先兼容结构化事件协议；旧版 `is_final` 风格只能视为历史资料。

### 3. 不要把本地 FastAPI 模式简单写成同步 PostgresSaver

当前本地主链路使用异步 saver，只有托管或特定兼容模式下才会出现同步 saver 代码路径。

### 4. 不要跳过 skills 约束直接查库

SQL 查询和历史 SQL 示例检索需要遵守 `required_skill` 约束，否则容易出现跨领域误查。

### 5. 大结果不要直接塞回模型上下文

优先改写为聚合 SQL，或走 CSV 导出。

## 推荐阅读

- `AGENTS.md`
- `memory.md`
- `README.md`
- `docs/backend/聊天流式输出结构化事件开发指南.md`
- `docs/backend/PostgresSaver集成重构总结.md`
- `docs/backend/RAG架构与技术总结.md`
- `docs/backend/skills/README.md`

## 备注

如果你发现本文件再次落后，请优先以实际代码和 `README.md` 为准，然后同步更新本文件与 `changelog.md`。
