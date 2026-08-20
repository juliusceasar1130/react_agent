# Phase 2 代码审查请求（Code Review Request for Claude Code）

## 一、审查背景与目标
在 Phase 1 完成基于 Context API 的状态瘦身与父子 Agent 沙箱隔离后，Phase 2 针对工件物理落盘收敛、工具层状态解耦及前端复合卡片进行垂直切片实施。
现已完成全部 5 个 Tickets 实施，并通过了前端构建检查（`vue-tsc` 0 错误）与后端全量回归测试（77 项测试全部绿色通过）。
请 Claude Code 重点对本次实施的**代码质量、边界安全、异常处理、架构一致性以及潜在风险**进行代码审查。

---

## 二、本次变更涉及的核心文件与职责

### 1. 后端工件统一存储底座 (Backend Artifact Store & GC)
- **`backend/app/artifacts/schemas.py`**:
  - 声明工件种类枚举 `ArtifactKind` (`CHART_SPEC = "chart_spec"`, `FILE_EXPORT = "file_export"`, `QUERY_RESULT = "query_result"`)；
  - 声明统一工件句柄 `ArtifactHandle` 与工件元数据基类 `BaseArtifactRecord`。
- **`backend/app/artifacts/store.py`**:
  - `ArtifactStore` 单例管理 `data/artifacts/charts/` 与 `data/artifacts/exports/`；
  - 使用 `tempfile.NamedTemporaryFile` + `os.replace` 实现文件原子写入，防并发读取脏数据；
  - 路径防越权校验（`os.path.abspath` + `os.path.commonpath`）防止 Directory Traversal；
  - 24 小时 TTL 与 GC 清理机制，针对 Windows 环境文件被占用抛出 `PermissionError`/`OSError` 实施安全跳过与容错；
  - 提供 `save_artifact` / `get_artifact` / `save_export_file` / `get_export_file`。
- **`backend/app/main.py`**:
  - 在 FastAPI `lifespan` 中注册 `_periodic_artifact_gc_loop` 异步后台定时任务（每 60 分钟执行一次 GC 清理，生命周期结束时通过 `asyncio.CancelledError` 优雅取消）。
- **`backend/app/routers/artifacts.py`**:
  - 提供收敛后的统一 REST 路由：`/api/chat/artifacts/{artifact_id}` 及 `/api/chat/artifacts/{artifact_id}/download`；
  - 保持对旧路由 `/charts/{chart_id}` 与 `/files/{file_id}` 的 100% 透明转发兼容。
- **`backend/app/chart_artifacts.py` & `backend/app/export_files.py`**:
  - 改造为极简兼容垫片（Forwarding Shims），转发至 `ArtifactStore`，杜绝重复实现与双重存储。

### 2. 工具层泛型解耦与主子智能体复用适配
- **`backend/app/agent/tools/chart_artifact_tool.py`**:
  - 运行时泛型升级为 `ToolRuntime[RequestContext, Any] | None`，解除对 `SqlSubAgentState` 的硬编码绑定；
  - `required_skill` 设为可选（默认 `""`），主智能体（`CustomState`）与子智能体（`SqlSubAgentState`）均可直接调用；
  - 接入 `ArtifactStore.save_artifact` 统一物理落盘与 ID 分配；
  - 异常统一抛出 `ToolException(f"Error: {e}")`。
- **`backend/app/agent/tools/csv_export_tool.py`**:
  - 运行时泛型升级为 `ToolRuntime[RequestContext, Any] | None`，解除对 `SqlSubAgentState` 的硬编码绑定；
  - `required_skill` 设为可选（默认 `""`）；
  - 接入 `ArtifactStore.save_export_file` 统一物理落盘与 ID 分配；
  - 异常统一抛出 `ToolException(f"Error: {e}")`。
- **`backend/app/agent/middleware/prompt_compiler_middleware.py`**:
  - 统一 `_DELETION_TARGET_CONFIG` 中 `build_chart_artifact` 与 `export_to_csv` 的 `runtime_header: "Error:"`，保障 5-stage 错误信息预扫描与折叠机制零破坏。

### 3. 前端复合 UI 容器与原生分页
- **`frontend/src/components/artifacts/ChartGroupCard.vue`**:
  - 从 `MessageItem.vue` 解耦抽取的独立图表复合容器；
  - 当 `charts` 长度 == 1 时，直接渲染单个 `ChartArtifactCard`；
  - 当 `charts` 长度 > 1 时，顶部展示 Tab 选项卡平滑切换当前选中图表，保留各图表的全屏放大、数据视图与导出能力。
- **`frontend/src/components/artifacts/QueryResultGroup.vue`**:
  - 从 `MessageItem.vue` 解耦抽取的独立表格复合容器；
  - 将表格流解析为 `sqlQueryResultsList` 数组，按 `subagent_name` 分组聚合多表格；
  - 复用 `TableResult.vue` 原生内置分页组件（20/50/100 条每页切换），支持多表格独立翻页与绝对行号计算。
- **`frontend/src/components/chat/MessageItem.vue`**:
  - 引入 `ChartGroupCard` 与 `QueryResultGroup` 进行工件呈现编排，大幅简化主消息组件内部渲染模板与复杂度。
- **`frontend/src/components/agent/SubAgentBadge.vue` & `frontend/src/utils/helpers.ts`**:
  - 统一映射子智能体标题为 `SQL数据专家`（`sql_domain_agent: 'SQL数据专家'`）。

---

## 三、验证情况
1. **前端类型检查与打包**：
   - 运行 `npm run build:check`（`vue-tsc && vite build`）：0 错误通过，构建耗时 37.36s。
2. **后端全量自动化测试**：
   - 运行 `python -m pytest backend/tests/agent/ ...` 共 77 项测试：100% 绿色通过（77 passed, 0 failed）。

---

## 四、请 Claude Code 重点审查的维度
1. **原子写与并发安全性**：`ArtifactStore` 中 `tempfile` + `os.replace` 在跨平台（尤其是 Windows）环境下的文件替换逻辑是否健壮？
2. **生命周期与资源泄露**：FastAPI lifespan 中 `_periodic_artifact_gc_loop` 的任务启停与异常捕获是否会引发未捕获的死循环或协程泄露？
3. **工具层泛型解耦兼容性**：工具将 `ToolRuntime[RequestContext, Any]` 中的 State 泛型放宽后，在 LangGraph 运行时或 LangChain `create_agent` 装配时是否存在边缘风险？
4. **前端状态还原与流式一致性**：`MessageItem.vue` 计算属性从 `memoryArtifactPool`（流式）与 `message.tool_artifacts`（F5 刷新持久化态）解析多图表、多表格与多 CSV 的逻辑是否完备无丢失风险？
5. **代码整洁度与潜在坏味道**：是否有未使用的导入、死代码或不符合项目规范的地方？

---

## 五、Claude Code 代码审查结论与整改闭环落实

### 1. 评审结论
Claude Code 经过多维度源码静态分析与逻辑推演，提出 4 个 High 缺陷与 4 个 Medium/Low 优化项。经整改后，二次复核全部通过（`Approved`）。

### 2. 整改与修复对照表
- **H1 防越权严格校验**：`ArtifactStore._resolve_managed_file` 采用 `allowed_base_dirs` 安全白名单校验，越界直接抛出 `PermissionError`；
- **H2 敏感路径脱敏**：在 `routers/artifacts.py`、`chart_artifacts.py`、`export_files.py` 中全量剥离对外返回的 `stored_path`；
- **H3 CSV 临时源文件清理**：`save_export_file` 复制工件到托管目录后，主动删除工具生成的临时源文件；
- **H4 created_by 角色解析**：工具层角色解析增加 `config['metadata']` 与 `configurable` 支持，子智能体默认回退 `sql_domain_agent`；
- **M1 路由模型校验修复**：`save_artifact` payload 补齐 `chart_id=artifact_id`，防止旧路由返回 500；
- **M2 配置项补齐**：`Settings` 增加 `artifacts_dir`，并在 `ArtifactStore` 中提供对历史目录的回退只读查找；
- **M3 截断总数与提示增强**：`QueryResultGroup.vue` 修正 `currentTotalCount` 优先取 `row_count`（全量记录数），并补齐截断场景下的防御性引导提示；
- **Schema 优化与错误处理规范**：工具显式指定 `args_schema` 隔离模型可见参数，参数统一为 `runtime: ToolRuntime[RequestContext, Any]` 彻底杜绝 Pydantic `CallableSchema` 序列化崩溃；规范沉淀至 `AGENTS.md`。

### 3. 最终自动化回归结果
- 前端 `npm run build:check`：0 错误，生产打包 100% 成功。
- 后端 pytest 全量套件：78 项测试全绿通过（78 passed, 0 failed）。
