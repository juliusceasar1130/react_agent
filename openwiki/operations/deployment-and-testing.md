---
type: 运维
title: "部署与测试"
description: "如何运行、部署和验证 rearch_agent：开发命令、Docker Compose、双数据库环境布局、工件/词汇表同步配置，以及 pytest 基线 + 标记。"
tags: [operations, deployment, testing, docker]
openwiki:
  roles: [operations, testing]
  change_kinds: [ops]
  source_paths: [docker-compose.yml, backend/Dockerfile, run_backend.py, backend/pyproject.toml, AGENTS.md, requirements.txt, requirements-dev.txt]
  validation_commands: [cd backend && python -m pytest -q]
---

# 部署与测试

## 本地运行

| 项目 | 命令 | 说明 |
|---|---|---|
| 后端（开发） | `uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000` | 从仓库根目录执行；`run_backend.py` 是 Windows 安全封装（设置 `WindowsSelectorEventLoopPolicy` 并关闭 reload） |
| 前端（开发） | `cd frontend && npm run dev` | Vite 开发服务器；构建检查为 `npm run build:check`（`vue-tsc && vite build`） |
| LangGraph 托管模式 | `langgraph dev --allow-blocking` | `langgraph.json` 中的图 `agent` 指向 `backend/app/agent/service.py:build_agent_graph`；`start_langgraph_dev.bat` 对此进行了封装 |
| 生产环境 | `docker-compose up -d --build` | `docker-compose.yml` 构建 `backend/Dockerfile`（`python:3.12-slim`、`WORKDIR /app`、`PYTHONPATH=/app`，使 `backend.app.*` 绝对导入可解析）；加入一个**外部**网络 `savedatabase-postgresql_v2_app-network`，并将 `./backend/app/skills/domains` 挂载为卷（技能内容随镜像发布而无需重建镜像） |

前端假设生产环境中存在 Nginx 代理，将 `/rearch/*` 映射到后端；开发环境依赖 `VITE_...`/相对路径 — 参见 `frontend/src/api/index.ts`。

## 配置

所有配置均由 `.env` 中的 `pydantic-settings` 驱动（仓库根目录；`.env_docker` 是 Compose 变体）— 规范来源是 `backend/app/config.py`。**切勿提交真实密钥；wiki 仅记录配置表面。**

主要配置分组（环境变量 → 含义）：

| 分组 | 变量 | 控制内容 |
|---|---|---|
| LLM | `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`OLLAMA_*`、`AGENT_TEMPERATURE`、`AGENT_MAX_TOKENS` | 供应商选择（[agent-service](../architecture/agent-service.md)） |
| Prompts | `MAIN_SYSTEM_PROMPT_PATH`（主编排器提示词）、`SYSTEM_PROMPT_PATH`（SQL 子代理提示词） | 文件支持的系统提示词模板的路径；默认值解析为已提交的 `backend/app/agent/prompts/` 和 `backend/app/agent/subagents/sql/` 文件（[agent-prompts](../architecture/agent-prompts.md)） |
| Databases | `DATABASE_URL`（聊天会话 + 代理检查点 + pgvector `rag_store`）、`ANALYTICS_DATABASE_URL` + `ANALYTICS_DB_SEARCH_PATH`（业务 SQL 目标） | 两个不同的 Postgres 角色：应用数据库与分析数据库 |
| SQL safety | `SQL_AGENT_TOP_K`、`SQL_RESULT_HARD_LIMIT`、`SQL_RESULT_PREVIEW_ROWS`、`DIMENSION_RESULT_HARD_LIMIT`、`DIMENSION_TABLES`、`SQL_LINTER_ENABLED`、`SQL_LINTER_DISABLED_RULES`、`SQL_CHECKER_MODE` | [tools-and-sql-linter](../architecture/tools-and-sql-linter.md) 中的防护流水线 |
| RAG / 词汇表 | `RAG_BACKEND`（`pgvector` \| `milvus_hybrid`）、`RAG_SIMILARITY_THRESHOLD`、`MILVUS_*`、`EMBEDDING_PROVIDER`、`RERANK_*`、`NVIDIA_API_KEY`、`DB_LEXICON_SYNC_ON_STARTUP`、`MILVUS_OVERWRITE` | [rag-and-lexicon](../domain/rag-and-lexicon.md) 中的检索；`backend/app/main.py` 中的启动时词汇表同步任务 |
| Artifacts | `ARTIFACTS_DIR`、`ARTIFACTS_TTL_HOURS`（遗留 `CHART_ARTIFACT_DIR`、`SQL_EXPORT_DIR`、`*_TTL_HOURS`） | [artifact-lifecycle](../workflows/artifact-lifecycle.md) |
| Context management | `LLM_CONTEXT_WINDOW`、`LLM_CONTEXT_WARN_TOKENS`、`LLM_CONTEXT_SAFETY_BUFFER`、`LLM_CONTEXT_SUMMARIZE_TRIGGER_TOKENS`、`TOKEN_ESTIMATOR_ENGINE`（`llama_cpp` \| `vllm`） | 上下文警告与摘要（[middleware-pipeline](../architecture/middleware-pipeline.md)） |
| Call limits | `AGENT_MODEL_CALL_RUN_LIMIT`、`AGENT_TOOL_CALL_RUN_LIMIT`、`AGENT_CALL_LIMIT_EXIT_BEHAVIOR` | 防循环熔断器 |

OpenWiki wiki 本身由 `.github/workflows/openwiki-update.yml` 刷新（计划任务 + 手动，使用 LangSmith 连接器执行 `openwiki code --update`）。

## 测试套件

`backend/pyproject.toml` 中的基线配置：`testpaths = ["tests"]`、`pythonpath = [".."]`（将仓库根目录加入 `sys.path`，因此从 `backend/` 运行时 `backend.app.*` 导入可解析）、`addopts = "-m 'not integration'"`，标记 `integration`（需要实时 Milvus/Postgres/LLM）和 `smoke`（针对运行中的后端）。

| 层级 | 命令 | 范围 |
|---|---|---|
| 聚焦（默认，静默） | `cd backend && python -m pytest <path> -q` | 单元 + 基于 mock 的测试；`-q` 保持输出精简，失败时仍输出完整信息 |
| 完整非集成测试套件 | `cd backend && python -m pytest -q` | `tests/` 目录树，排除带 `integration`/`smoke` 标记的测试 |
| **有条件**的集成测试 | `cd backend && python -m pytest -m integration` | 仅在实时 Postgres/Milvus/LLM 可用时执行；否则测试跳过或因连接失败 |
| **有条件**的冒烟测试 | `cd backend && python -m pytest tests/smoke -m smoke` | 黄金路径端到端测试；需要运行中的后端（`run_backend.py`） |
| 前端 | `cd frontend && npx vue-tsc --noEmit` | 类型级检查；没有前端单元测试套件 |

测试布局（各页面聚焦测试集见其 `test_paths`）：

- `backend/tests/agent/` — 代理单元测试（状态沙箱化、上下文流、工具兼容性、中间件、RAG/词汇表、持久化）。
- `backend/tests/test_routers_coverage.py` — 所有路由器的端点级覆盖，包括 stream/resume。
- `backend/tests/test_tool_artifacts_persistence.py`、`test_scenario_quick_panel_*.py` — 持久化 + 场景引擎。
- `backend/tests/smoke/test_smoke_golden_path.py` — 有条件黄金路径。

## wiki 指向更深层运维上下文的入口

- 设计意图：`docs/`（`docs/llamaindex_rag/` 和 `docs/progresql_vector开发指南/` 中的 RAG 部署说明、`docs/deepagent/` 中的架构报告、`docs/agent_best_practices.md` 中的代理最佳实践）。
- 变更日志：根目录 `changelog.md`（体量较大；按功能名称 grep，而非通读全文）。
- 架构变更的 OpenSpec 差异：`openspec/`。