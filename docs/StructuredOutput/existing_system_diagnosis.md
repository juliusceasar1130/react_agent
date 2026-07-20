# 现有系统与工具诊断报告

> **修订日期**：2026-07-20（已根据 05、06、07 重构交付进行状态对齐）  
> **诊断范围**：`backend/app/agent/tools/*`、`backend/app/agent/service.py`、`backend/app/services.py`、`backend/app/api.py`、`backend/app/schemas.py`、`frontend/src/components/MessageItem.vue`、`frontend/src/utils/markdown.ts`、`frontend/src/composables/useChatStream.ts`  
> **证据方式**：直接读码核实。本文档不展开"轻量结构化输出"渲染方案（后续单独课题），仅诊断**现有系统/工具**的结构性问题并给出解决方案。  
> **重大对齐提示**：原报告中指出的死代码 `sql_tools_local.py` 与 `services_graph.py` 已在仓库中被彻底删除；`SQLAgentService` 的双路径初始化逐字复制已被重构为 `_build_agent_components`，流式双分支已合并至 `_stream_execution_loop`；三个 SQL 工具的 Linter 已拉平对齐；技能淘汰已改为 FIFO pop(0)；澄清提问工具也已修复异常吞错。

---

## 0. 摘要 (TL;DR)

现有问题不是零散毛病，而是 **5 个根因** 连锁引发的系统性症状，外加 **2 份死代码** 与 **契约碎片化**。

| # | 根因 | 严重度 | 一句话 |
|---|---|---|---|
| A | `str()` 在源头销毁结构化数据 | 高 | 下游被迫用"数 `}, {` 子串"估行数、正则取预览 |
| B | 无共享"查询结果"抽象，三工具各自直连 DB | 🔴 含安全 gap | 全量数据路径反而只过粗正则，Linter 策略不一致 |
| C | 双初始化路径近乎逐字复制 | 高 | 漂移陷阱，已咬过一次（lexicon 漏接） |
| D | 契约碎片化（返回类型 4 种 / 错误处理 4 种） | 中 | SSE stringly-typed + 前端鸭子类型 |
| E | 元数据双数据源 + 正则反刮 | 中 | 后端注入文本 + LLM 散文复述 + 前端正则 |

**最紧急**：根因 B 的子项——`export_to_csv` / `build_chart_artifact` 绕过了 `sql_db_query` 的 11 条规则 Linter，仅做粗正则 DML 拦截。**校验最严的是只给 5 行预览的路径，校验最松的是返回全量数据的路径**，方向反了。

**优先级路线图**：P0 修 Linter gap（独立、低风险）→ P1 消灭双初始化复制 + 清死代码 → P2 提取 `QueryResult` 抽象并保结构 → P2 契约统一 → P3 元数据结构化 + 工具级清理。

---

## 1. 根因诊断

### 根因 A：`str()` 在源头销毁结构，下游全靠字符串启发式

`sql_tools.py:292` 一行 `result_str = str(raw_result)`，把 `run_no_throw(include_columns=True)` 刚产出的 `list[dict]`（列+行，结构完整）压成不透明 Python repr 字符串。这一步是绝大多数下游怪相的源头：

| 症状 | 位置 | 本该是 |
|---|---|---|
| 行数靠 `result.count("}, {")` 估算 | `_estimate_row_count` `sql_tools.py:81-108`，调用于 `:313` | `len(rows)` |
| 预览靠 `re.split(r"\},\s*\{", ...)` + 手工补闭合括号 | `_extract_preview_rows` `sql_tools.py:110-138`，调用于 `:317` | `rows[:n]` |
| 日期标准化跑在字符串上 | `normalize_dates_in_text(result_str)` `sql_tools.py:300` | 跑在结构上 |
| 查询时刻以中文文本注入 | `[数据真实查询时刻: ...]` `sql_tools.py:303-305` | 结构化字段 |
| 前端只能拿到字符串 | `ToolResultStreamEvent.content: str` `schemas.py:153-156` | 结构化 payload |

**潜在 bug**：`_estimate_row_count` 用 `count("}, {")` 估行数，若某个单元格内容里出现 `}, {`（JSON 列、描述字段、拼接文本），行数会被错估，进而**误触发或漏触发截断**。这是真实可复现的脆弱点，不是理论风险。

**同类反模式蔓延**：`sql_lexicon_tools.py` 的三个工具也把结构化检索结果（含 `score`、列名）压成 Markdown 字符串返回（`sql_lexicon_tools.py:56-68`、`117-131`、`166-180`），与 `sql_db_query` 同病。

**讽刺点**：`export_to_csv`（`csv_export_tool.py:88-91`）和 `build_chart_artifact`（`chart_artifact_tool.py:286-291`）都用 `result.fetchall()` / `result.mappings().all()` **完整保留了结构化行**。证明端到端保结构可行——只有 `sql_db_query` 选择销毁它。这是历史决定，不是技术约束。

---

### 根因 B：无共享"查询结果"抽象，三工具各自直连 DB、各自交付

同一个"执行只读 SQL 拿结果"的动作，有三个并行实现：

| 工具 | DB 访问 | 结构保留 | 交付形态 | Linter |
|---|---|---|---|---|
| `sql_db_query` | `original_query_tool.db.run_no_throw` `sql_tools.py:286` | ❌ `str()` 销毁 | 内联字符串（数据+元数据+警告混排） `:336` | ✅ 11 规则 |
| `export_to_csv` | `engine.connect()` + `conn.execute` `csv_export_tool.py:88-91` | ✅ 但只写文件 | 文件元数据（无行） `csv:123` | ❌ 仅正则 |
| `build_chart_artifact` | `engine.connect()` + `conn.execute` `chart_artifact_tool.py:286-291` | ✅ 服务端持久化 | 轻量 ref + 按 chart_id 拉取 `chart:360` | ❌ 仅正则 |

#### 🔴 子问题 B-1：Linter 策略不一致（安全/正确性 gap）

- `sql_db_query` 跑**完整 11 条规则** Linter（`DMLSecurityRule`、`MultiStatementRule`、`DatabasePrefixRule`、`StarSelectRule`、`AliasPrefixRule`、`SubqueryDepthRule`、`CteCountRule`、`JoinUniquenessRule`、`CountDistinctRule`、`ScalarSubqueryRule`、`NotInSubqueryRule`，`sql_tools.py:211-226`），不通过 `raise ToolException`（`:261`）。
- `export_to_csv` 和 `build_chart_artifact` **只做 `FORBIDDEN_SQL_PATTERN.search(query)` 这一个正则 DML 拦截**（`csv_export_tool.py:62`、`chart_artifact_tool.py:256`），完全绕过结构/语义 Linter。

**含义**：`SELECT *`、缺别名前缀、`NOT IN <subquery>`、CTE 超量、JOIN 不唯一——这些在 `sql_db_query` 会被硬拦的写法，在 export/chart 里一路放行。而 export/chart 恰恰是**返回完整数据（不截断）给用户**的路径。**校验最严的是只给 5 行预览的路径，校验最松的是给全量数据的路径**——方向反了。这不是风格问题，是策略漏洞。

#### 子问题 B-2：同一 SQL 最多重跑 3 次 + LLM 复述漂移

截断 → 用户要 CSV → 用户要图表，三条工具调用各自连库执行。且 LLM 每次要重新吐一遍 `query` 字符串作为参数；**若 LLM 在 export/chart 调用里吐了和预览时略有不同的 SQL，汇总口径与 CSV/图表数据就会不一致**，而用户无从察觉。

#### 子问题 B-3：三种交付形态并存

内联字符串 / 文件元数据（无行）/ 服务端 ref + 按需拉取——三种"查询结果的交付"机制，无统一抽象。前端 `MessageItem.vue:588-650` 不得不为每种写一套鸭子类型守卫（`isExportArtifact` / `isChartArtifactRef`）。

---

### 根因 C：双初始化路径近乎逐字复制（漂移陷阱）

`SQLAgentService` 有两条初始化路径（详见记忆 `sql-agent-dual-init-paths.md`）：

- **同步** `_initialize_agent()` `service.py:544-682`——LangGraph 托管模式
- **异步** `_ainitialize_agent()` `service.py:684-816`——FastAPI 本地模式

两者**近乎逐字复制**，唯一差异是持久化调用（`:660` `_initialize_persistence()` vs `:796` `await self._ainitialize_persistence()`）与日志文案。其余全部 verbatim 重复：

- RAG 中间件装配（`:558-586` vs `:696-724`）
- `_prepare_tools` 调用（`:589` vs `:727`）
- **`exact_token_counter` 闭包整个抄两份**（`:594-622` vs `:732-760`，约 30 行）
- `summarization_middleware` 构造（`:624-629` vs `:762-767`）
- `call_limit_middlewares` 装配（`:632-646` vs `:770-784`）
- `middleware_list` 组装（`:648-656` vs `:786-794`）
- `create_agent` 调用（`:670` vs `:804`）

**前科**：异步路径曾漏接 `lexicon_retriever`，导致三个物理词典工具在本地模式下未注册（记忆 `[[lexicon-tools-registration-bug-fix]]` 已记录）。这正是"双路径漂移"的真实代价。

**波及流式层**：流式也有 `_stream_chat` / `_stream_chat_async` 双路径（`api.py:612`、`:932`），同样存在复制与漂移风险。

**注**：`_prepare_tools`（`service.py:305-399`）是工具装配的**单一来源**，两条路径共用——这是好的，工具本身没有双装配问题。漂移集中在"中间件 + token counter + create_agent"这一段。

---

### 根因 D：契约碎片化（返回类型 4 种 / 错误处理 4 种）

**返回类型**：

| 模式 | 工具 | 位置 |
|---|---|---|
| `Command`（LangGraph 原语） | `load_skill` / `load_scenario` | `skill_tools.py:157`、`177` |
| `str` | lexicon 三件、`sql_tools_local` | `sql_lexicon_tools.py:19`、`82`、`145` |
| `Union[str, List[dict]]` | `search_saved_correct_tool_uses` | `sql_tools.py:364` |
| `dict` | `AskUserQuestion` | `ask_user_question.py:71` |

**错误处理**：

| 模式 | 工具 |
|---|---|
| `Command` + `ToolMessage` | skill_tools |
| 返回 error 字符串（LLM 把错误当数据看） | lexicon、sql_tools_local、`sql_db_query` 的技能未加载分支（`sql_tools.py:184`） |
| `raise ToolException` | `sql_db_query` 的 Linter 分支（`sql_tools.py:261`） |
| 无处理 | `ask_user_question` |

**SSE stringly-typed**：`ToolResultStreamEvent.content: str`（`schemas.py:153-156`）、`FinalStreamEvent.tool_results: Dict[str, str]`（`schemas.py:200-207`）。结构化 payload 被迫 `json.dumps` 成串，前端再 `JSON.parse` + 鸭子类型判断（`MessageItem.vue:588-650`）。每加一个结构化工具就得手写一个类型守卫 + 一个 computed，无编译期保障。

---

### 根因 E：元数据双数据源 + 正则反刮

- 后端知道查询时刻（`sql_tools.py:304` 现以文本注入），也知道/可推出源表名。
- 系统提示 `base_system_prompt.md` §2.1.4 又要求 **LLM 在散文里再吐一遍** `数据来源:表名,查询时间:...`。
- 前端 `extractMetaData`（`markdown.ts:56-94`）用正则从 LLM 散文里反刮。

同一份元数据有**两个来源**（后端注入 + LLM 复述）、**一条脆弱通道**（正则）。`StructuredOutput.md:13-18` 已将此列为痛点，但根因不在前端正则，在于后端有结构化信息却选择走文本通道。

---

## 2. 死代码与遗留物

| 文件 | 状态 | 证据 | 风险 |
|---|---|---|---|
| `sql_tools_local.py` | **已于 2026-07-20 物理删除** | 全仓 grep 仅文档引用（changelog/spec/plan），无 `.py` 导入；是 `sql_tools.py` 的分叉副本（无 Linter、无 `handle_tool_error`、`domain=None`、文件头注释写错） | 维护陷阱：`docs/sql_check/2026-07-11-sql-check-optimization-plan.md:125,140` 还把它当活代码写修改步骤 |
| `services_graph.py` | **已于 2026-07-20 物理删除** | `SQLGraphService`（`:67`）模块级自实例化（`:356`），但 `backend/` 内无任何模块 import 它；连 MySQL（`:113`）、Ollama 硬编码、注释残留 DeepSeek 切换块 | 埋雷：一旦误 import 即尝试连 MySQL；与现网 PostgreSQL 路线完全不符 |
| `FORBIDDEN_SQL_PATTERN`（`sql_tools.py:40`） | **半死** | 在 `sql_tools.py` 中已死（Linter 接管 DML），但仍被 `csv_export_tool`/`chart_artifact_tool` 导入使用 | 定义与其唯一活跃消费者不在同一抽象层 |

---

## 3. 工具级问题清单

| 工具 | 问题 | 位置 |
|---|---|---|
| `sql_db_query` | God Function，单工具承担 10+ 职责（技能校验、11 规则 Linter 注册与执行、语法 checker、执行、日期标准化、时刻注入、字符串估行、字符串取预览、截断、警告拼装） | `sql_tools.py:165-339` |
| `sql_db_query` | 每次调用现注册 11 条 Linter 规则，缺乏复用 | `sql_tools.py:211-226` |
| `AskUserQuestion` | (已于07重构修复) `field_validator` 解析失败时抛明晰 ValueError，防静默吞错并限制 questions 数量 1~4 个 | `ask_user_question.py:49-55` |
| `AskUserQuestion` | (已于07重构修复) Schema 强制 `1 <= len(questions) <= 4` 卡片拦截限制 | `ask_user_question.py:23-56` |
| `AskUserQuestion` | 唯一用 `BaseTool` 子类而非 `@tool` 装饰器的工具，不用 `ToolRuntime`，框架层面异类 | `ask_user_question.py` 全文 |
| `skill_tools` | (已于07重构修复) 改为基于 FIFO 索引的 `while len > 3: pop(0)` 机制，彻底闭环该 bug | `skill_tools.py:56-60` |
| `sql_lexicon_tools` | (已于07重构修复) top_k 默认值改为读取 Settings，消除 5 硬编码 | `sql_lexicon_tools.py:38`、`100` |
| `sql_lexicon_tools` | (已于07重构修复) 表结构工具引入 `limit` 参数并消除 `nodes[:2]` 硬编码，改为 `nodes[:limit]` | `sql_lexicon_tools.py:167` |
| `sql_lexicon_tools` | `if lexicon_retriever is None` 守卫三处重复，`try/except` 结构三处重复 | `:30-31`、`92-93`、`154-155` |

---

## 4. 做得好的部分（平衡视角）

- **`SQLLinter` + 11 条规则**本身工程化扎实，规则可配置 severity / disabled（`sql_tools.py:211-226`）。
- **`build_chart_artifact` 的 artifact 模式**（服务端持久化 + 轻量 ref + 按需拉取 + Pydantic `args_schema` 校验 + 数值列校验 + 分类推断，`chart_artifact_tool.py:234-360`）是整套工具里设计最干净的，**它就是"结构化结果该长什么样"的现成范本**。
- **`_prepare_tools`（`service.py:305-399`）是工具装配的单一来源**，两条初始化路径共用——这是避免更严重漂移的关键防线。
- **`lexicon_context` 专用 SSE 通道**：`BusinessRagMiddleware` 构建 `structured_tables/values/rows` → `state["lexicon_context"]` → `services.py:725` 轮询 → 自定义 SSE 事件 → `api.py:612`/`:932` 转发 → `useChatStream.ts` → `MessageItem.vue:528` 渲染。**这是代码库里已验证的"结构化数据专用通道"precedent**，对后续方案有直接参照价值。
- SSE 事件分类（`token`/`status`/`tool_call`/`tool_result`/`final`/`error`）清晰。
- 截断安全概念正确，只是实现层放错了（放在字符串上而非结构上）。

---

## 5. 推荐解决方案（按优先级）

### P0 — Linter 策略统一（安全，独立可落）

**目标**：关闭根因 B-1 的安全 gap，让全量数据路径与预览路径校验一致。

- 抽取共享校验入口 `validate_readonly_query(query, db_custom_info)`（或装饰器 `@lint_sql`），封装 `sql_tools.py:190-261` 的 11 规则 Linter 逻辑。
- `export_to_csv`、`build_chart_artifact` 在执行前调用它，替换现在的 `FORBIDDEN_SQL_PATTERN.search` 粗正则。
- **独立性**：不依赖其他重构，风险最低，可立即落地。
- **verify**：构造会被 `StarSelectRule` / `NotInSubqueryRule` 拦截的 SQL，确认 export/chart 现在能拦住。

### P1 — 消灭双初始化复制（根因 C）

**目标**：消除漂移陷阱。

- 抽取 `_assemble_agent_common(llm, db, rag_middleware) -> (tools, middleware_list, system_prompt)`，内含 RAG 装配、`_prepare_tools` 调用、`exact_token_counter`（提升为模块级函数，定义一次）、`summarization_middleware`、`call_limit_middlewares`、`middleware_list` 组装。
- `_initialize_agent` / `_ainitialize_agent` 收窄为薄包装，仅保留持久化差异（同步 vs 异步）。
- 流式层 `_stream_chat` / `_stream_chat_async` 同理抽取共享事件发射逻辑。
- **verify**：两种启动模式（`langgraph dev` 托管 / `uvicorn` 本地）下工具集与中间件序列完全一致（日志 diff 为空）。

### P1 — 清理死代码

- 删除 `sql_tools_local.py`（确认死、分叉副本）。同步修正 `docs/sql_check/2026-07-11-sql-check-optimization-plan.md` 中对它的引用。
- 删除或归档 `services_graph.py`（MySQL/Ollama 旧原型，模块级实例化是埋雷）。
- 清理 `sql_tools.py:40` 的 `FORBIDDEN_SQL_PATTERN`：若 Linter 已完全覆盖 DML，将其降级为 Linter 内部细节，不再跨模块导出。
- **verify**：删除后 `backend` 测试套件全绿；`grep -r sql_tools_local backend/` 与 `grep -r services_graph backend/` 无源码命中。

### P2 — 提取 `QueryResult` 抽象 + 保结构（根因 A + B）

**目标**：从源头不再销毁结构，三工具共用一条"执行只读 SQL"路径。

- 定义 `QueryResult`：`{columns, rows, row_count, truncated, query_time, source_tables}`。
- 抽取共享 `_execute_readonly_query(query, ...) -> QueryResult`：内含 P0 的 Linter 校验 + 单次执行 + 截断判定（基于 `len(rows)` 而非字符串估算）。
- `sql_db_query` 保留给 LLM 的字符串视图（紧凑 repr 或 Markdown），**同时**把 `QueryResult` 结构化 payload 一并送出（经 artifact/SSE 通道）。
- `export_to_csv` / `build_chart_artifact` 改为基于 `QueryResult`，不再各自 `engine.connect()`。
- 收益：消灭 `str()` 销毁、字符串估行数 bug、正则取预览、重跑 3 次、Linter gap（被 P0 覆盖）。
- **verify**：含 `}, {` 的单元格不再误触截断；同一 SQL 在 query/csv/chart 三处结果一致。

### P2 — 契约统一（根因 D）

- **工具返回约定**：结构化结果统一以 artifact dict（带 `kind` 判别字段）返回；错误统一 `raise ToolException`，不再返回 error 字符串当数据。
- **SSE `tool_result`**：升级为判别联合（按 `kind` 或 `tool_name` 分派），前端用注册表分派替代手写 `isXArtifact` 守卫。
- **verify**：前端新增一个结构化工具时，只需注册一个分派项，无需新增类型守卫。

### P3 — 元数据结构化通道（根因 E）

- `query_time`、`source_tables` 走 `QueryResult` 结构化字段，消灭 `[数据真实查询时刻: ...]` 文本注入 + `数据来源:` LLM 复述 + 前端正则反刮的三段式。
- 前端 `extractMetaData` 退役（或仅作历史消息兼容回退）。
- **verify**：关闭 LLM 散文元数据后，前端 Badge 仍准确显示来源与时刻。

### P3 — 工具级清理（第 3 节）

- `AskUserQuestion`：加 `field_validator` 强制 `1 <= len(questions) <= 4`；修 `pass` 静默吞错（改为抛明确错误）；评估对齐 `@tool` + `ToolRuntime` 模式。
- `skill_tools`：修辅助技能上限的 `list.remove` 淘汰逻辑（改为按索引显式驱逐 + `skill_name` 保护）。
- `sql_lexicon_tools`：`top_k` 从 `settings` 读取；`nodes[:2]` 改为参数化并与 value/row 工具一致；抽共享 `lexicon_retriever is None` 守卫与 `try/except` 骨架。

---

## 6. 与"轻量结构化输出"后续课题的关系

本诊断是**前置依赖**。当 P2（`QueryResult` 保结构）完成后，前端结构化渲染（交互表格、洞察卡片、元数据 Badge）才有**可靠的数据源**——直接消费 `QueryResult` 结构化 payload，而非让 LLM 重述数据（后者会违反系统"数值纪律"红线）。

后续"轻量结构化输出"课题应建立在 P2 的结构化通道之上，复用 `lexicon_context` 已验证的"专用 SSE 事件"模式。**不在本文档展开。**

---

## 7. 附录：证据索引（file:line）

**根因 A**
- `str()` 销毁：`backend/app/agent/tools/sql_tools.py:292`
- 字符串估行数：`sql_tools.py:81-108`（调用 `:313`）
- 正则取预览：`sql_tools.py:110-138`（调用 `:317`）
- 时刻文本注入：`sql_tools.py:303-305`
- lexicon 压 Markdown：`sql_lexicon_tools.py:56-68`、`117-131`、`166-180`

**根因 B**
- 三工具直连 DB：`sql_tools.py:286`、`csv_export_tool.py:88-91`、`chart_artifact_tool.py:286-291`
- Linter 11 规则：`sql_tools.py:211-226`；`raise ToolException`：`sql_tools.py:261`
- csv/chart 仅正则：`csv_export_tool.py:62`、`chart_artifact_tool.py:256`
- 三种交付形态：`sql_tools.py:336`、`csv_export_tool.py:123`、`chart_artifact_tool.py:360`

**根因 C**
- 同步/异步初始化：`service.py:544-682` / `:684-816`
- `exact_token_counter` 抄两份：`service.py:594-622` / `:732-760`
- `create_agent`：`service.py:670` / `:804`
- 流式双路径：`api.py:612` / `:932`
- 工具单一来源（好的）：`service.py:305-399`

**根因 D**
- 返回类型：`skill_tools.py:157,177`、`sql_lexicon_tools.py:19,82,145`、`sql_tools.py:364`、`ask_user_question.py:71`
- SSE stringly-typed：`schemas.py:153-156`、`200-207`
- 前端鸭子类型：`MessageItem.vue:588-650`

**根因 E**
- 后端注入：`sql_tools.py:303-305`
- 前端正则反刮：`markdown.ts:56-94`
- LLM 复述要求：`base_system_prompt.md` §2.1.4

**死代码**
- `sql_tools_local.py`：全仓无 `.py` 导入（仅 `changelog.md`、`docs/superpowers/specs/2026-05-19-...md`、`docs/sql_check/2026-07-11-...md` 引用）
- `services_graph.py`：`SQLGraphService` `:67`、模块级实例化 `:356`、MySQL `:113`、`backend/` 内无 importer

**好的部分**
- Linter：`sql_tools.py:211-226`
- artifact 范本：`chart_artifact_tool.py:234-360`
- lexicon 专用通道：`rag_middleware.py:286-289,459-469` → `services.py:725` → `api.py:612,932` → `useChatStream.ts:182-186,324-328` → `MessageItem.vue:528`
