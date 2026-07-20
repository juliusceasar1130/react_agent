# P2 阶段实施方案：提取 QueryResult 抽象与统一 SQL 结果交付通道

> **修订日期**：2026-07-19（已根据评审修订 v2，砍掉 SQL_Hash 缓存总线，改为 result_id 显式复用 + 侧信道交付 + fetch limit+1）  
> **状态**：已全面落地 (COMPLETED)（SQL 预览、ECharts 图表、CSV 导出三大工具的侧信道 Command 改造与前端 kind 分发已全面上线并测试通过）  

> **文档位置**：`docs/StructuredOutput/refactor/query_result_abstraction_and_contract_alignment.md`  
> **核心目标**：从源头不再销毁结构化数据，三工具共用单一只读执行入口 `execute_readonly_query_to_struct`；经 state 侧信道把结构化 payload 送往前端，LLM 仅看必要视图；统一 `kind` 分发取代前端鸭子类型守卫。  
> **范围声明**：本方案仅统一 **三个 SQL 工具**（`sql_db_query` / `export_to_csv` / `build_chart_artifact`）的结果通道，对应诊断根因 **A**（`str()` 销毁）、**B-2/B-3**（重跑与三入口）、**D** 的 SQL 结果契约切片。`skill`/`lexicon`/`ask_user_question` 的返回类型与错误契约（根因 D 其余切片）不在本方案。

---

## 一、 现状与痛点分析 (Current Gaps)

### 1.1 `str()` 在源头销毁结构，截断依赖字符串启发式
`sql_tools.py:292` 一行 `result_str = str(raw_result)` 把 `run_no_throw(include_columns=True)` 刚产出的 `list[dict]` 压成 Python repr 字符串，引发：
* **估行 Bug**：`_estimate_row_count` 用 `str(raw_result).count("}, {")` 估算行数（`sql_tools.py:81-108`），单元格含 `}, {` 即误判，误触发或漏触发截断。
* **预览破损**：`_extract_preview_rows` 用 `re.split(r"\},\s*\{", ...)` 切分后手工补闭合括号（`sql_tools.py:110-138`），极易崩溃。
* **前端只拿字符串**：`ToolResultStreamEvent.content: str`（`schemas.py:153-156`），无法直接渲染交互式表格。

### 1.2 三工具各自直连 DB，执行入口碎片化
同一条 SQL 在会话流程中可能被三个工具各自 `engine.connect()` / `run_no_throw` 重跑（预览 → 画图 → CSV），且 LLM 在后两步重吐 SQL 时易产生微小变动，导致图表/下载与预览口径不一致。根因是**没有共享执行入口**（B-3），而非缺少缓存。

### 1.3 交付通道混淆
* csv 的文件元信息、chart 的 ECharts spec 都以 JSON 串 `return` 给 LLM，迫使 LLM 阅读冗余字段名/路径，易生幻觉。
* 前端拿图表数据需持 `chart_id` 二次 HTTP 拉取（`/api/chat/charts/{chart_id}`），大并发下增加延迟。

---

## 二、 推荐方案与决策 (Proposed Strategies)

### 2.1 核心三件套（保留，评审认可）
1. **`QueryResult` 结构体**：列+行+计数+截断标记+元数据，从源头保结构。
2. **单一执行入口 `execute_readonly_query_to_struct`**：三工具共用，内含 P0 的 `validate_readonly_query` + 单次执行 + 截断判定。消灭 `str()` 销毁、字符串估行、三入口碎片化（B-3）。
3. **`kind` 分发**：前端按 `payload.kind` 注册表分发，取代 `isExportArtifact`/`isChartArtifactRef` 鸭子类型守卫（D）。

### 2.2 result_id 显式复用（替代 v1 的 SQL_Hash 缓存总线）

> **v1 方案被否决的理由**：v1 用 `session_id + SQL_Hash` 做隐式缓存。但 (a) LLM 重吐 SQL 时微小变动即 hash 变化 → 缓存 miss，"口径 100% 相同"承诺不成立；(b) 缓存命中返回陈旧数据，违反系统"数值纪律"+ prompt §2.1.3 追问重查要求；(c) **最致命**：预览的 `QueryResult` 是截断的（5 行），CSV 要全量，一个缓存装不下，"三工具共享缓存"自相矛盾。

改为**显式 result_id 复用**：
* `sql_db_query` 执行后，若**未截断**（结果 ≤ `hard_limit`，是完整的有界结果），把 `QueryResult` 按 `result_id`（UUID）存入服务端缓存，带 TTL（建议 10 min）+ `session_id` 作用域。
* `export_to_csv` / `build_chart_artifact` 的工具 args 增加**可选** `result_id`：
  - 传入且命中且未截断 → 直接复用，**零重跑、零漂移**（小结果常见场景）。
  - 未传入 / 未命中 / 已截断 → 自行调用 `execute_readonly_query_to_struct`（仍走单一入口，消除 B-3，只是重跑一次）。
* LLM 由 prompt 引导在复用预览查询时传 `result_id`（见 §3.6）。

**为何这样安全**：复用是 opt-in 且仅对小结果（未截断）生效；大结果（截断）天然回退重跑，不存在"截断缓存喂给 CSV"的矛盾，也不存在陈旧数据（命中即同一份刚查的结果，TTL 兜底）。

### 2.3 侧信道交付（类比 `lexicon_context` 已验证通道）

> **v1 缺口**：v1 说"工具内部通过 SSE 广播 payload""大模型仅返回极简回执"，但 LangChain 工具不能直接发 SSE；若 `return` 完整 payload 则 LLM 必读，若 `return` 极简回执则 payload 无路可达前端。机制未交代。

采用代码库已验证的 **state 侧信道**模式（与 `lexicon_context` 同构：`BusinessRagMiddleware` 写 `state["lexicon_context"]` → `services.py:725` 轮询 → 自定义 SSE 事件 → 前端）：
* 工具返回 `Command(update={"messages": [ToolMessage(receipt)], "<artifact_field>": payload})`（`skill_tools` 已用此模式返回 `Command`）。
* `services.py` 轮询 `state` 中的 artifact 字段，发 `query_result` / `chart_spec` / `file_export` 自定义 SSE 事件。
* 前端 `useChatStream` 处理事件，`MessageItem` 按 `kind` 分发渲染。

**LLM 视图分层**（关键修正，v1 一刀切"极简回执"是错的）：
| 工具 | LLM 收到（ToolMessage） | 前端收到（侧信道 payload） |
|---|---|---|
| `sql_db_query` | **紧凑数据视图**（Markdown 表 + 截断标记 + 元数据）--LLM 需据此写洞察，**不能极简** | `kind:"query_result"` 完整 `QueryResult`（交互表格 + Badge） |
| `export_to_csv` | 极简回执 `"CSV export successful. File ID: xxx"` | `kind:"file_export"`（下载卡片） |
| `build_chart_artifact` | 极简回执 `"Chart generated: <title>"` | `kind:"chart_spec"`（ECharts 配置+数据，**免除二次 HTTP**） |

### 2.4 fetch limit+1 探测（OOM 安全 + 诚实截断标记）

> **v1 缺口**：v1 说"获取真实行数 `len(rows)`"又"截断只保留前 preview_rows 行"--截断时 `len(rows)`=5，语义自相矛盾；且现网 `run_no_throw` 不加 LIMIT，全量捞入内存再估行，大结果 OOM。

`execute_readonly_query_to_struct` 采用 **fetch limit+1** 探测：
* 把原 SQL 包成子查询加安全上限：`SELECT * FROM (<原 SQL>) AS _q LIMIT {hard_limit + 1}`（原 SQL 自带更小 LIMIT 时内层优先）。
* 取回 N 行：
  - N ≤ `hard_limit` → `truncated=False`，`row_count=N`（精确）。
  - N == `hard_limit + 1` → `truncated=True`，`row_count` 未知（仅知 ≥ hard_limit+1），预览只展示前 `preview_rows` 行。
* **行为变化（需接受）**：截断时不再给 LLM 精确全量 N（现网字符串估行本就不可靠），改为"≥ hard_limit+1，已截断"。这更诚实，且内存有界（最多 `hard_limit+1` 行）。

---

## 三、 详细变更方案 (Proposed Changes)

### 3.1 [NEW] `QueryResult` 与共享执行入口

#### [NEW] `backend/app/agent/utils/query_result.py`
```python
from pydantic import BaseModel
from typing import Any, List, Dict

class QueryResult(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int          # 未截断=精确；截断=hard_limit+1（标记 truncated=True 时不可当全量用）
    truncated: bool
    query_time: str         # 后端执行时刻，取代 [数据真实查询时刻: ...] 文本注入
    source_tables: List[str]  # AST 提取的真实表名（去 CTE），取代 LLM 散文复述

def execute_readonly_query_to_struct(
    query: str,
    db,
    hard_limit: int,
    preview_rows: int,
    is_dimension_query: bool = False,
) -> QueryResult:
    """
    单一只读执行入口（三工具共用）。
    1. 复用 P0 的 validate_readonly_query（静态 Linter，抛 SQLLintException 由工具转 ToolException）。
    2. 包子查询 LIMIT hard_limit+1 执行，用 run_no_throw 的结构化 list[dict] 返回（不再 str()）。
    3. fetch limit+1 判定 truncated，preview_rows 截断预览。
    4. 复用 _extract_table_names（sqlglot）取 source_tables，过滤 CTE 名。
    5. 对 rows 内的日期值做 normalize（迁移自 normalize_dates_in_text）。
    返回完整 QueryResult（未截断时 rows=全量有界；截断时 rows=前 preview_rows）。
    """
```

**保留现网逻辑**：
* **维度表白名单**：`_is_pure_dimension_query`（`sql_tools.py:63-78`）仍用于决定 `hard_limit` 取 `dimension_result_hard_limit` 还是 `sql_result_hard_limit`。`execute_readonly_query_to_struct` 收 `is_dimension_query` 入参，由调用方判定后传入。
* **日期归一化**：`normalize_dates_in_text` 原跑在字符串上，改为对 `rows` 内的日期类型/字符串值归一化（同规则，不同载体）。
* **`source_tables` 语义**：复用 `_extract_table_names`（`sql_tools.py:46-60`，sqlglot `find_all(Table)`）。需验证 CTE 名不被误当表名（`find_all(Table)` 一般只返回真实表引用，但需测试确认）；展示为去重列表。Badge 显示所有涉及表（比 LLM 单标主表更准），prompt 同步放宽（§3.6）。

### 3.2 [MODIFY] result_id 缓存与复用
* 新增服务端进程内缓存 `query_result_cache: dict[result_id -> (QueryResult, session_id, expire_at)]`，TTL 10 min，按 `session_id` 隔离。
* `sql_db_query` 执行后：若 `not truncated`，生成 `result_id` 存入缓存，并在回执中告知 LLM "result_id=xxx, 可被 export_to_csv / build_chart_artifact 复用"。
* `export_to_csv` / `build_chart_artifact` 的 `args_schema` 增加可选 `result_id: str | None`：
  - 命中且 `not truncated` → 直接用缓存的 `QueryResult`（CSV 此时拿到的就是完整有界结果，可全量导出）。
  - 否则 → 自行 `execute_readonly_query_to_struct`（CSV 用更大的 `hard_limit` 或流式 guard，见 §3.4）。

### 3.3 [MODIFY] 侧信道交付链路
* **工具返回 `Command`**（`skill_tools` 同款模式）：
  ```python
  return Command(update={
      "messages": [ToolMessage(content=<紧凑视图或极简回执>, name=..., tool_call_id=...)],
      "tool_artifact": {"kind": "query_result"|"chart_spec"|"file_export", ...payload, "message_id": ...},
  })
  ```
* **`services.py`**：流式聚合时轮询 `state.get("tool_artifact")`，发 `{"type": "tool_artifact", "artifact": ...}` SSE 事件（与 `lexicon_context` 事件同构，`api.py:612`/`:932` 同步/异步双路径转发）。
* **`schemas.py`**：新增 `ToolArtifactStreamEvent`（`type: "tool_artifact"`, `artifact: dict`），不动旧 `ToolResultStreamEvent`（向后兼容，见 §3.5）。

### 3.4 [MODIFY] 三工具改造

#### `sql_tools.py`
* `sql_db_query` 改调 `execute_readonly_query_to_struct`，拿到 `QueryResult`。
* **LLM 视图**：把 `QueryResult.rows[:preview_rows]` 渲染成 Markdown 表 + 截断标记 + `result_id` 提示，作为 `ToolMessage.content`（LLM 据此写洞察）。
* **前端侧信道**：`Command(update={"messages": [ToolMessage(紧凑视图)], "tool_artifact": {"kind":"query_result", "result": QueryResult, "result_id": ...}})`。
* **删除** `_estimate_row_count`、`_extract_preview_rows`、`str(raw_result)`、`[数据真实查询时刻: ...]` 文本注入。
* `handle_tool_error = True` 保留（P0 已设）。

#### `csv_export_tool.py`
* 改调 `execute_readonly_query_to_struct`（或命中 `result_id` 缓存），**移除 `engine.connect()` 直连**。
* **OOM guard**（补诊断 §五.2 的 P2 项）：CSV 取全量时设独立 `csv_hard_limit`（如 100k 行），超限 `raise ToolException("结果集过大，请加聚合/范围条件后重试")`，避免 `fetchall()` 撑爆内存。
* **LLM 视图**：极简回执 `"CSV export successful. File ID: xxx"`。
* **前端侧信道**：`kind:"file_export"`（含 file_id/filename/row_count/col_count/columns）。

#### `chart_artifact_tool.py`
* 改调 `execute_readonly_query_to_struct`（或命中 `result_id`），**移除 `engine.connect()` 直连**。
* 复用 `QueryResult.columns`/`rows` 做 series/x_field 校验与 chart_spec 推断（现网逻辑保留，数据源换掉）。
* **LLM 视图**：极简回执 `"Chart generated: <title>"`。
* **前端侧信道**：`kind:"chart_spec"`（完整 ECharts 配置+数据），**免除前端二次 `/api/chat/charts/{chart_id}` 拉取**。

### 3.5 [MODIFY] 契约统一与前端适配

#### `schemas.py`
* 新增 `ToolArtifactStreamEvent`（专用事件，`kind` 判别），不破坏旧 `ToolResultStreamEvent`。

#### `MessageItem.vue`
* 新增 `toolArtifact` 处理：`useChatStream` 收 `tool_artifact` 事件，按 `artifact.kind` 注册表分发：
  - `query_result` → 交互式表格（排序/筛选/CSV 导出）+ 元数据 Badge（直接读 `query_time`/`source_tables`，**退役 `extractMetaData` 正则**）。
  - `chart_spec` → 图表组件（直接用 payload，不再二次 HTTP）。
  - `file_export` → CSV 下载卡片。
* **向后兼容**：旧持久化消息的 `tool_results: Dict[str,str]` 仍是字符串，保留现 `isExportArtifact`/`isChartArtifactRef` 守卫作**历史消息回退路径**；新消息走 `tool_artifact` 分发。两者并存，不互斥。
* **移除** `extractMetaData` 对**新消息**的正则反刮（历史消息仍走老路径）。

### 3.6 [MODIFY] 系统提示词联动
* `base_system_prompt.md` §2.1.4：放宽"末尾必须标注数据来源表名和系统时间"要求--改为"前端 Badge 已结构化展示来源与查询时刻，正文可省略元数据复述；若需强调可简述主表"。
* 引导 LLM 复用 `result_id`：在 §3.x 增补"当用户基于上一次查询结果要求导出 CSV 或生成图表时，优先复用上次 `sql_db_query` 回执中的 `result_id`，避免重吐 SQL 导致口径偏差"。

---

## 四、 验证方案 (Verification)

### 自动化测试
* `pytest backend/app/agent/tools/test_unified_linter.py`（P0 Linter 回归）。
* 新增 `backend/app/agent/tools/test_query_result.py`：
  - fetch limit+1：构造恰好 `hard_limit` / `hard_limit+1` / 远超的结果，验证 `truncated` 与 `row_count` 语义。
  - 特殊字符单元格（含 `}, {`、JSON 串）：验证不再误判行数（根因 A bug 回归）。
  - `result_id` 复用：命中/未命中/已截断三态，验证 CSV 拿到的是完整有界结果而非 5 行预览。
  - CSV OOM guard：超 `csv_hard_limit` 抛 `ToolException`。
  - `source_tables` 提取：含 CTE/子查询/JOIN，验证 CTE 名不混入。

### 手动验证
1. 普通查询：前端收到 `query_result` 事件，交互表格正常渲染，Badge 显示 `query_time`/`source_tables`，**无 LLM 散文复述、无前端正则反刮**。
2. 超限查询：行数被 fetch limit+1 精准识别，预览 5 行，标记"已截断 ≥N"。
3. 复用链路：预览后要求导出 CSV（LLM 传 `result_id`），CSV 与预览口径一致，零重跑；图表同理且**无二次 HTTP 延迟**。
4. 历史消息兼容：打开 P2 前的旧会话，旧字符串 `tool_results` 仍正常渲染（走守卫回退路径）。

---

## 五、 范围与限制 (Scope & Limitations)

1. **仅 SQL 三工具结果通道**：`skill`/`lexicon`/`ask_user_question` 的返回类型与错误契约（根因 D 其余切片）未触及，留后续。
2. **CSV OOM guard 是基础防护**：`csv_hard_limit` 防 `fetchall()` 撑爆，但不解决"合法但慢的查询"（非选择性过滤、全表扫描）--Linter 是静态结构分析，挡不住（同 Linter 方案 §四.2）。
3. **`source_tables` 展示所有涉及表**：比 LLM 单标主表更准但更繁，需 prompt 配合（§3.6）让 LLM 不再复述。
4. **result_id 复用仅对未截断小结果生效**：大结果仍重跑（无法避免，因预览未捞全量）；这是诚实取舍，非缺陷。
5. **侧信道依赖 `services.py` 同步/异步双路径转发**：需在 `_stream_chat` / `_stream_chat_async`（`api.py:612`/`:932`）两处都加 `tool_artifact` 转发，与 `lexicon_context` 同款（注意双路径同步，见诊断根因 C）。

---

## 六、 与诊断报告的覆盖关系

| 诊断项 | 本方案 |
|---|---|
| 根因 A（`str()` 销毁） | ✅ 完全消除（`execute_readonly_query_to_struct` 保结构） |
| 根因 B-2（同 SQL 重跑 3 次） | 🟡 部分缓解（result_id 复用消除小结果重跑；大结果仍重跑） |
| 根因 B-3（三入口碎片化） | ✅ 完全消除（单一执行入口） |
| 根因 D（SQL 结果契约切片） | ✅ 统一 `kind` 分发 + 侧信道；其余工具契约未触及 |
| 根因 E（元数据双源+正则） | ✅ `query_time`/`source_tables` 走结构化字段，退役正则（新消息） |
| 工具级：`sql_db_query` God Function | 🟡 进一步缓解（移走估行/取预览/时刻注入） |
