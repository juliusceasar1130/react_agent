# CLAUDE.md

## 项目概述

面向生产数据查询场景的**大模型聊天会话管理系统**，基于 FastAPI + LangGraph **DeepAgent**（主协调代理 + 编译型 SQL 领域子代理）+ Vue 3 构建。

核心能力：多会话聊天 UI、DeepAgent 协同（主协调 + SQL 领域子代理）、Skills 领域知识动态加载、PGVector/Milvus 与三层数据库术语表检索增强、结构化 SSE 流式输出、人在回路澄清、Agent 状态持久化及旁路工件存储（图表/CSV/表格）。

## 开发环境

```bash
conda activate py312_agent
```

常用命令：

```bash
# 后端 (FastAPI 本地模式)
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
# 或运行根目录脚本: python run_backend.py / start_backend.bat

# 前端
cd frontend && npm run dev

# LangGraph Dev (托管调试模式)
langgraph dev --allow-blocking
# Windows 下可直接运行 start_langgraph_dev.bat
```

## 文档索引（OpenWiki 知识库）

在开始工作前，优先查阅 OpenWiki 结构化文档与任务路由：

- **快速上手与任务路由表**：`openwiki/quickstart.md` — 知识库总入口，包含源码入口、关键符号、聚焦测试与最小验证指令
- **系统架构**：`openwiki/architecture/overview.md` — 运行时拓扑、双持久化模式、代理装配与中间件流水线
- **提示词与契约**：`openwiki/architecture/agent-prompts.md` — 模板化提示词加载与主↔子代理协作契约
- **领域技能与场景**：`openwiki/domain/skills-and-scenarios.md` — 领域技能开发（权威规范参阅 `docs/skills/scenario_architecture_spec.md`）
- **RAG 与术语表**：`openwiki/domain/rag-and-lexicon.md` — 向量检索与三层数据库术语表机制
- **流协议与工作流**：`openwiki/workflows/streaming-protocol.md`（SSE 流式协议）、`openwiki/workflows/clarification-flow.md`（澄清循环）、`openwiki/workflows/artifact-lifecycle.md`（工件旁路）
- **前端开发**：`openwiki/frontend/chat-app.md` — Vue 3 单页应用组件与状态管理
- **部署与测试**：`openwiki/operations/deployment-and-testing.md` — 运行配置与测试规范
- **架构变更提案**：`openspec/project.md` — 架构性提案/规范/计划

## 开发约定

### 后端

- CRUD 更新操作使用 `model_dump(exclude_unset=True, exclude_none=True)`
- Response Schema 使用 Pydantic v2 `model_config = ConfigDict(from_attributes=True)`
- 主键统一使用 UUID 字符串
- 优先遵循现有模块边界，不随意把逻辑重新塞回单文件
- 新增第三方包需更新 `requirements.txt`
- **注意双初始化路径**：`SQLAgentService` 有同步 (`_initialize_agent`) 和异步 (`_ainitialize_agent`) 两条初始化路径，分别用于 LangGraph 托管模式和 FastAPI 本地模式。修改工具注册、中间件装配、RAG 接线时，必须同步更新两边
- **LangChain 工具错误与异常处理规范**：
  1. **异常类型统一**：工具内部遇到可预期的业务/参数错误时，必须统一 `raise ToolException(...)`，严禁抛出未经拦截的裸异常（如 `ValueError`、`Exception`），防止图崩溃中断。
  2. **强制开启错误拦截开关**：所有暴露给 Agent 的工具必须显式配置 `tool.handle_tool_error = True`（或 `@tool(..., handle_tool_error=True)`），使框架安全捕获 `ToolException` 并转化为 `ToolMessage(status="error")`，确保 ReAct 能够持续闭环自愈。
  3. **错误消息前缀契约**：所有错误文案必须以 `"Error: "` 开头（如 `raise ToolException("Error: 字段不存在")`），以配合 `PromptCompilerMiddleware` 的 Stage 2 失败调用预扫描与历史轮次上下文安全折叠。
  4. **参数 Schema 隔离与类型声明**：工具应显式指定 Pydantic `args_schema` 声明大模型可见参数；框架注入参数必须采用纯 `runtime: ToolRuntime[RequestContext, Any]`，严禁使用 `| None = None` 联合类型，防止 Pydantic 生成 JSON Schema 时触发 `CallableSchema` 序列化崩溃。

### 前端

- 使用 `<script setup>` + Pinia Setup Store
- refs 在 store 中直接使用，不额外加 `.value`
- 流式阶段与完成态展示职责分离
- **流式事件注册与过滤防丢机制**：若后端新增流式事件（如 `tool_artifact`），前端必须同步更新三处地方，以防被网络拦截层静默过滤丢弃：
  1) `@/types` 中的 `StreamEvent` 联合类型声明；
  2) `@/api/chat` 中的 `STREAM_EVENT_TYPES` 白名单 Set 集合；
  3) `@/api/chat` 中 `parseStreamEvent` 的 `switch` 解析分支。

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
- 对于用户提出问题和现象，先分析根因，得到用户确认后实施
- 不要自主提交git commit，必须得到我允许

<!-- OPENWIKI:START -->

## OpenWiki

See [AGENTS.md](AGENTS.md) for OpenWiki agent instructions.

<!-- OPENWIKI:END -->
