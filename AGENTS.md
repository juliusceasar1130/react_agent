# CLAUDE.md

## 项目概述

面向生产数据查询场景的**大模型聊天会话管理系统**（SQL Agent + Skills + RAG），基于 FastAPI + LangChain/LangGraph + Vue 3 构建。

核心能力：多会话聊天 UI、SQL Agent 查询分析、Skills 领域知识加载、PGVector/Milvus 检索增强、结构化 SSE 流式输出、Agent 状态持久化。

## 开发环境

```bash
conda activate py312_agent
```

常用命令：

```bash
# 后端
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend && npm run dev

# LangGraph Dev
langgraph dev --allow-blocking
```

Windows 下可直接运行 `start_langgraph_dev.bat`。

## 文档索引

在开始工作前，根据任务类型读取相关文档：

- `agent_docs/architecture.md` — 项目架构速览、后端/前端主链路、技术栈、目录结构（修改跨模块代码时读取）
- `agent_docs/persistence_and_streaming.md` — 持久化双模式与 SSE 流式协议（修改 Agent 持久化或流式逻辑时读取）
- `agent_docs/skills_guide.md` — Skills 开发约定（开发或修改 Skills 时读取，也参考 `docs/skills/guide.md`）
- `agent_docs/data_dictionary_guide.md` — 数据字典设计约定（修改数据字典功能时读取）
- `openspec/project.md` — proposal / spec / plan / 架构性变更时优先查看

## 开发约定

### 后端

- CRUD 更新操作使用 `model_dump(exclude_unset=True, exclude_none=True)`
- Response Schema 使用 Pydantic v2 `model_config = ConfigDict(from_attributes=True)`
- 主键统一使用 UUID 字符串
- 优先遵循现有模块边界，不随意把逻辑重新塞回单文件
- 新增第三方包需更新 `requirements.txt`

### 前端

- 使用 `<script setup>` + Pinia Setup Store
- refs 在 store 中直接使用，不额外加 `.value`
- 流式阶段与完成态展示职责分离

### 文档维护

- 新特性和重要优化记录到 `changelog.md`，`README.md` 记录特性与目录结构
- 若修改内容不适合写进源码文件，应在交付说明里给出修改时间与主要变更

### 本地与离线部署约束

- **禁止直连公网 CDN 资源**：严禁在 `index.html` 或前端代码中直接加载 `fonts.googleapis.com` 等外部公网 CDN 的 JS/CSS/字体。
- **静态资源本地化**：自定义字体（`.woff2` 等）必须下载并放置在 `public/fonts/` 目录中，在 CSS 里通过 `@font-face` 相对路径加载；三方库/图标需通过 npm 安装本地打包。
- **验证无外网依赖**：开发与测试时需注意，不得有任何外网 HTTP/HTTPS 请求，以防因 DNS 失败或连接超时（Timeout）导致首屏渲染卡顿或控制台报错。

## Code Guidelines

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

## 协作偏好

- 默认使用中文进行协作；必要时对关键术语补充英文。
- 代码修改优先遵循最小改动原则（minimal change）。
- 倾向于小步修改、可验证完成。
- 倾向于保持现有风格，而不是主动统一风格。
- 若发现无关问题，可提示，但不默认顺手修复。
- 不确定项目约定时，先查阅现有文档与代码实现。

## MCP

- LangChain docs MCP — 查询 LangChain 官方文档
- Context7 MCP — 查询通用第三方库文档
- chrome-devtools MCP — 浏览器调试与前端问题排查

## 实施原则
-  对于用户提出问题和现象，先分析根因，得到用户确认后实施
- 不要自主提交，必须得到我允许
