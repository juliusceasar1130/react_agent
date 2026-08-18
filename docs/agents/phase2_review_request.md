请协助对系统架构升级的【Phase 2 实施方案：工件统一治理与复合 UI】进行跨 Agent 独立评审。

### 背景说明
在刚刚完成的 Phase 0（工件持久化落库与流式溯源信封）与 Phase 1（基于 Context API 的瞬态数据通道与子图状态物理沙箱隔离，全量 51 项测试通过）基础上，现正式制定 Phase 2 实施方案。

经深入论证与权衡，我们做出了一项关键架构裁决：
> **关键裁决**：`sql_db_query` 的查询结果**不落本地磁盘文件、不提供独立异步拉取 REST 端点**。因为其数据量极小（`SQL_RESULT_HARD_LIMIT` 默认 30 行，上限 1000 行，约几十 KB），继续通过 PostgreSQL `chat_messages.tool_artifacts`（借助 PG TOAST 自动压缩机制）直接存储与直出，可确保 F5 刷新 0 延迟秒开，避免过度设计。

---

### Phase 2 实施方案概览

```
                               Phase 2 核心架构全景
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 物理工件底座 (ArtifactStore) ── 专注文件/复杂配置生命周期与 GC             │
│    • 合并 chart_artifacts + export_files ──> backend/app/artifacts/         │
│    • 统一分配 ID (cht_*, exp_*)，统一 24 小时 TTL 与 FastAPI 周期性 GC 清理  │
│    • 统一 REST 端点 /api/artifacts/* (兼容现有 /api/charts/ 和 /api/files/) │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. 即时表格工件 (DB Direct Store) ── 保持极简直出 (0 磁盘 IO / 0 额外接口)  │
│    • sql_db_query 维持通过 chat_messages.tool_artifacts 直接存储           │
│    • 享受 PostgreSQL 原生 TOAST 压缩，F5 刷新 0 延迟秒开                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. 工具层解耦 (Tool Decoupling) ── 消除技能硬依赖，适配主子双向复用         │
│    • required_skill 设为可选，ToolRuntime 泛型支持 CustomState              │
│    • 严格保持 ToolException("Error: ...") 契约，Prompt 中间件裁剪 100% 稳定 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. 前端复合展示 (Composite UI) ── 提升多工件并存时的交互质感               │
│    • 多图表：从垂直堆叠升级为 Tab 切换卡片 / Carousel 轮播                  │
│    • 多表格：支持按子智能体 (涂装/总装) 分组展示，集成纯前端轻量分页/滚动    │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 具体 Tickets 拆解：
- **Ticket 01（后端）**：合并 `chart_artifacts.py` 与 `export_files.py` 为 `backend/app/artifacts/store.py`；实现统一 `ArtifactStore` 单例，管理 `data/artifacts/charts/` 与 `exports/` 目录；定义强类型 `BaseArtifactRecord` / `ArtifactHandle`（含 `created_by`, `tool_call_id`, `created_at`, `expires_at`）；FastAPI Lifespan 注册每 60 分钟后台定时 GC 任务；收敛 `/api/artifacts/` 路由并保留原有 `/api/charts/` 与 `/api/files/` 路由兼容。
- **Ticket 02（后端）**：改造 `build_chart_artifact` 与 `export_to_csv` 调用 `ArtifactStore`；将 `required_skill` 设为可选，运行时泛型升级为 `ToolRuntime[RequestContext, Any]`，消除对 `SqlSubAgentState` 的硬依赖，适配未来主智能体直接挂载使用；保持 `raise ToolException(f"Error: ...")` 统一错误抛出格式，确保 `PromptCompilerMiddleware` 的 5 阶段裁剪流水线（Stage 1-5 预扫描、脱敏、物理删除、折叠）100% 稳定。
- **Ticket 03（前端）**：多图表复合容器（`ChartArtifactCard.vue` / `MessageItem.vue`），当产生多张图表时从垂直堆叠升级为 Tab 切换卡片或并排对比视图，支持全屏预览与图表类型切换。
- **Ticket 04（前端）**：多 SQL 表格分 Tab / 折叠展示（`MessageItem.vue`），将原单值 `sqlQueryResult` 重构为列表，按子智能体角色（`subagent_title`）分组折叠展示，并集成纯前端轻量分页（>15 行分页）与虚拟滚动。
- **Ticket 05（质量与测试）**：编写 `test_artifact_store_lifecycle.py` 与 `test_tools_main_and_subagent_compatibility.py`，执行后端全量回归与前端 Vite 生产打包。

---

### 请重点从以下四个维度进行评审并给出意见：
1. **必要性与范围合理性（Necessity & Scope）**：
   - 裁决 `sql_db_query` 不单独落盘而仅由 `chat_messages` 存储是否合理？
   - 整体范围是否符合“Simplicity First”原则，有无过度设计或遗漏关键项？
2. **架构分层与抽象（Architecture & Layering）**：
   - `ArtifactStore` 单例设计、`created_by` 多角色设计以及与工具层的职责分工是否清晰稳健？
   - 工具层将 `required_skill` 设为可选以适配未来主智能体复用的设计是否安全？
3. **前后端交互契约与鲁棒性（Contracts & Robustness）**：
   - 多图表 Tab 轮播与多表格前端分页的交互方案是否合理？
   - F5 刷新历史复原链路、Pinia `memoryArtifactPool` 与 `chat_messages.tool_artifacts` 的闭环是否足够坚固？
4. **潜在风险与落地建议（Risks & Actionable Advice）**：
   - 实施过程中有无潜在坑点（如文件系统并发锁、路径安全、时区、GC 异常）？
   - 针对 Phase 2 给出一锤定音的评审结论（Approve / Approve with suggestions / Request changes）。
