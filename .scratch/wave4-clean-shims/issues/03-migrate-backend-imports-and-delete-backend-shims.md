# 03 — 后端主入口直连 routers 模块并清理后端已废弃 Shim 文件

**What to build:**
更新 `main.py` 直接从 `backend.app.routers` 导入路由；更新 `service.py` 及测试用例直接从 `backend.app.agent.subagents.sql.tools` 导入工具；物理删除 `backend/app/api.py`、`backend/app/agent/tools/sql_tools.py` 和 `sql_lexicon_tools.py` 垫片。

**Blocked by:** None — can start immediately.

**Status:** completed

- [x] `main.py` 路由导入改为 `from .routers import router, scenarios_router, init_analytics_engine`
- [x] `service.py` 与 `test_sql_lexicon_tools.py` 改为直接从 `subagents/sql/tools.py` 导入
- [x] 物理删除 `backend/app/api.py`
- [x] 物理删除 `backend/app/agent/tools/sql_tools.py` 与 `sql_lexicon_tools.py`
