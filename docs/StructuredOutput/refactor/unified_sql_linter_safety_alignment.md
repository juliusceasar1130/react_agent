# 统一 SQL Linter 安全与合规校验对齐方案 (Unified SQL Linter Safety Alignment)

> **修订日期**：2026-07-19（已根据评审修订 v2）  
> **方案状态**：已落地并合入  
> **文档位置**：`docs/StructuredOutput/refactor/unified_sql_linter_safety_alignment.md`  
> **核心目标**：将预览、导出、画图三个数据库执行入口的 **SQL Linter 合规校验**对齐到同一套 11 条规则，并统一错误出口为 `ToolException` 以触发大模型自愈重写。
>
> **范围声明**：本方案仅对齐 **Linter 校验**与**错误契约**。`sql_db_query` 独有的 `sql_checker_mode=="safety"` 语法检查器、CSV 导出的行数上限保护等不在本方案范围（详见 §四）。

---

## 一、 现状与痛点 (Current Situation & Gaps)

当前系统在执行用户/大模型生成的 SQL 查询时，共有三个独立的工具入口。然而，这三个入口的安全与合规校验机制处于**非对称（不一致）**状态：

| 工具名称 | 作用 | 数据库访问 | 现有校验机制 | 潜在风险 |
| :--- | :--- | :--- | :--- | :--- |
| `sql_db_query` | 聊天框内数据预览（截断前5行） | `original_query_tool.db.run_no_throw` | **极严**：注册执行完整的 **11 条 SQL Linter 规则**（包括 DML 安全、多语句拦截、表别名前缀、JOIN 唯一性校验等）。 | 无明显 Linter 风险，但 Linter 初始化和规则注册高度硬编码在该工具内部，无法复用。 |
| `export_to_csv` | 导出完整数据集为 CSV 文件 | 独立建立 `engine.connect()` 执行 | **极松**：仅使用简单的 `FORBIDDEN_SQL_PATTERN` 正则检查是否存在 DML 关键字。 | **🔴 重大安全与性能隐患**：大模型生成的 SQL 可以绕过 Linter 约束，执行笛卡尔积（Fan-out 行数暴增）、多语句拼接或不符合别名约束的 SQL，导致慢查询或数据膨胀。 |
| `build_chart_artifact` | 提取数据集生成图表 | 独立建立 `engine.connect()` 执行 | **极松**：仅使用简单的 `FORBIDDEN_SQL_PATTERN` 正则检查是否存在 DML 关键字。 | **🔴 重大安全与性能隐患**：同上，不合规的 SQL 会直接导致库级慢查询，且画图统计出的数值可能会因为 JOIN 未去重而翻倍失真。 |

### 核心痛点总结
1. **安全边界倒挂**：只返回 5 行预览的路径校验最严，而真正返回全量敏感数据给用户的 CSV 导出/图表路径校验最松。
2. **代码冗余度高**：Linter 的实例化、规则注册和解析逻辑被硬编码在 `sql_tools.py` 内部，任何规则的更新或配置调整都无法自动辐射至其他工具。
3. **错误出口碎片化（本次新增修订）**：即便校验对齐，若 `export_to_csv` / `build_chart_artifact` 仍以 `return "Error: ..."` 字符串返回错误（现状），LLM 会把错误文本当成"工具成功结果"，无法进入 LangChain 的 `ToolException` 自愈重写通道。本方案要求三工具统一 `raise ToolException` 并设置 `handle_tool_error = True`。

---

## 二、 方案分析与可行性 (Technical Analysis)

### 1. 规则通用性分析
由于预览、导出和图表生成三个工具最终都是在**同一个 PostgreSQL 数据库实例**上执行只读查询，因而它们的合规要求（SQL Dialect 解析、AST 遍历、安全红线、语义约束）是 **100% 相同**的。`SQLLinter` 的 11 条规则对三个工具完全适用。

### 2. 运行时上下文（DDL 信息）的传递可行性
`SQLLinter` 在执行语义级检查（如 `JoinUniquenessRule` 校验关联键唯一性）时需要表结构元信息（即 `custom_table_info`）。
* 在 Agent 初始化阶段，所有的工具均通过 `service.py:_prepare_tools(db, ...)` 进行实例化。
* `db` 实例（`MaterializedViewSQLDatabase`）在初始化时已经通过 `fetch_table_definitions_with_comments(db_url, include_views=True, include_materialized_views=True)` 一次性抓取**全库** DDL 并缓存到 `db._custom_table_info`（`sql_database.py:103`），运行时**不再被 `load_skill` 改写**（`SkillMiddleware` / `skeleton_service` / `rag_middleware` 均为只读消费）。
* 因此，在工具构造阶段将 `db._custom_table_info` 传入 `export_to_csv` 和 `build_chart_artifact` 的工厂函数中是安全的——传入的是 dict **引用**，即便后续有变更也会即时可见，校验上下文完整度有保障。

### 3. 解耦设计：避免 LangChain 依赖下沉
为了保持 `sql_linter.py` 作为**纯粹 SQL 校验工具**的独立性与可测试性，校验函数不应当直接抛出 langchain 专用的 `ToolException`，也不应引入 `emit_stream_status` 等流式框架依赖。
* **解耦方案**：在 `sql_linter.py` 中定义纯 Python 自定义异常 `SQLLintException`。
* **职责分工**：`validate_readonly_query` 只负责校验并抛出 `SQLLintException`；各个工具的外层 Wrapper 捕获该异常，并**统一**转换为 `ToolException` 抛给 LangChain 运行时，引导大模型进行 SQL 自愈重写。状态发射（`emit_stream_status`）保留在各工具内部，不污染纯校验模块。

---

## 三、 推荐方案与代码蓝图 (Proposed Solution)

### 1. [NEW] 定义自定义异常与共享校验函数
在 `sql_linter.py` 中新增 `SQLLintException` 和 `validate_readonly_query` 逻辑，同时导入全局配置 `settings`。为了避免潜在的循环导入，`settings` 可在函数内部延迟引入。

```python
# 修改 [backend/app/agent/utils/sql_linter.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/utils/sql_linter.py)

import re

# 集中存放禁止写操作的 DML 关键字正则（从原 sql_tools.py 迁移）
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|REPLACE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE
)

class SQLLintException(Exception):
    """SQL 合规性校验异常"""
    pass

def validate_readonly_query(query: str, db_custom_info: dict = None) -> None:
    """
    统一执行 SQL 的安全合规校验（DML/DDL 防御、多语句拦截及 11 条 AST 检查规则）。
    若校验未通过，抛出 SQLLintException。
    本函数保持纯校验职责：不引入 emit_stream_status / ToolException 等框架依赖。
    """
    from backend.app.config import settings

    # 1. 【安全提升】无条件执行第一道正则物理阻断，防止 AST 解析成功但规则遗漏（如 TRUNCATE/GRANT）
    if FORBIDDEN_SQL_PATTERN.search(query):
        raise SQLLintException("Error: SQL 仅允许 SELECT/WITH/EXPLAIN 只读查询，禁止执行修改或表结构变更操作。")

    if not settings.sql_linter_enabled:
        return

    db_custom_info = db_custom_info or {}
    context = _build_lint_context(db_custom_info)
    
    linter = SQLLinter(
        rules_severity_override=settings.sql_linter_rules_severity_override,
        disabled_rules=settings.sql_linter_disabled_rules
    )
    
    # 统一注册全部 11 条安全与合规规则
    linter.register(DMLSecurityRule())
    linter.register(MultiStatementRule())
    linter.register(DatabasePrefixRule(allowed_schemas=settings.sql_linter_allowed_schemas))
    linter.register(StarSelectRule())
    linter.register(AliasPrefixRule())
    linter.register(SubqueryDepthRule(max_depth=settings.sql_linter_max_subquery_depth))
    linter.register(CteCountRule(max_cte=settings.sql_linter_max_cte_count))
    linter.register(JoinUniquenessRule())
    linter.register(CountDistinctRule())
    linter.register(ScalarSubqueryRule())
    linter.register(NotInSubqueryRule())
    
    try:
        parsed = sqlglot.parse_one(query)
    except Exception as parse_error:
        # AST 解析失败，执行正则/多语句退避校验
        logger.warning(f"sqlglot 解析 SQL 失败，执行正则退避校验: {parse_error}")
        raw_violations = []
        if FORBIDDEN_SQL_PATTERN.search(query):
            raw_violations.append(LintViolation(
                rule_id="SEC-001",
                severity="ERROR",
                message="SQL 仅允许 SELECT 只读查询，禁止任何写操作 (DML/DDL)。",
                detail=query,
                fix_suggestion="删除写入或更改表结构的指令。"
            ))
        raw_violations.extend(MultiStatementRule().check_raw_sql(query, context))
        
        errors = [v for v in raw_violations if v.severity == "ERROR"]
        if errors:
            dummy_result = LintResult(passed=False, errors=errors, warnings=[])
            raise SQLLintException(dummy_result.format_error_message())
        return

    # 执行完整的 Linter 规则集校验
    result = linter.lint(parsed, context, raw_sql=query)
    for warn in result.warnings:
        logger.warning(f"Linter 警告 [{warn.rule_id}]: {warn.message}")
        
    if not result.passed:
        raise SQLLintException(result.format_error_message())
```

### 2. 重构 `sql_db_query` 工具
简化 `sql_tools.py` 中的重复逻辑，将其委托给共享校验函数。错误出口保持 `raise ToolException`（与现状一致）。

```python
# 修改 [backend/app/agent/tools/sql_tools.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/sql_tools.py)

from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException

# ... 在 sql_db_query 内部：
        # 获取 DDL 字典
        db_custom_info = custom_table_info
        if not db_custom_info and hasattr(original_query_tool, "db"):
            db_custom_info = getattr(original_query_tool.db, "_custom_table_info", None) or {}

        # 统一合规检查
        # 注：原 sql_tools.py:192-196 的 emit_stream_status("正在执行 SQL 合规检查", ...) 保留在此处
        # （状态发射留在工具层，不进入纯校验模块 validate_readonly_query）
        try:
            validate_readonly_query(query, db_custom_info)
        except SQLLintException as exc:
            # 捕获自定义异常并向上包装为 LangChain 要求的 ToolException
            raise ToolException(str(exc))
```

### 3. 工具装配链路打通 (DDL 依赖注入)
修改服务层的装配逻辑，在创建 CSV 和图表工具时传入缓存的表结构字典。

```python
# 修改 [backend/app/agent/service.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/service.py)

def _prepare_tools(db: MaterializedViewSQLDatabase, ...):
    # ...
    # 获取 db 缓存的 DDL 结构体字典（构造时全量填充，运行时只读）
    custom_table_info = getattr(db, "_custom_table_info", None) or {}

    try:
        # 将 DDL 字典传入两个导出/图表工具工厂中
        chart_artifact_tool = create_chart_artifact_tool(db._engine, custom_table_info)
        tools.append(chart_artifact_tool)

        csv_export_tool = create_csv_export_tool(db._engine, custom_table_info)
        tools.append(csv_export_tool)
```

### 4. 重构 `export_to_csv` 和 `build_chart_artifact` 工具
将 Linter 校验应用到执行流程的最前端，并**统一错误出口为 `raise ToolException`**（不再 `return` 错误字符串），同时补齐 `handle_tool_error = True`。

```python
# 修改 [backend/app/agent/tools/csv_export_tool.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/csv_export_tool.py)

from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException
from langchain_core.tools import ToolException
# 删除原 `from backend.app.agent.tools.sql_tools import FORBIDDEN_SQL_PATTERN`
# （DML 拦截已由 Linter 的 DMLSecurityRule / SEC-001 覆盖，FORBIDDEN_SQL_PATTERN 已迁入 sql_linter.py）

def create_csv_export_tool(engine: Engine, custom_table_info: dict = None) -> Any:

    @langchain_tool
    def export_to_csv(query: str, required_skill: str, runtime: ToolRuntime) -> str:
        # 技能加载校验保留；原 FORBIDDEN_SQL_PATTERN 正则块整体删除（已被下方 Linter 覆盖）
        # ... 技能校验后：
        emit_stream_status("正在执行 SQL 合规检查", stage="querying", source="export_to_csv")
        try:
            # 统一执行安全合规校验
            validate_readonly_query(query, custom_table_info)
        except SQLLintException as exc:
            logger.warning(f"export_to_csv 校验未通过拦截: {exc}")
            # 统一错误出口：抛出 ToolException 触发大模型自愈重写
            # （与 sql_db_query 对齐；禁止 return "Error: ..." 字符串，否则 LLM 会把错误当数据）
            raise ToolException(str(exc))

        # 校验通过，进入原 text(query) 执行逻辑

    export_to_csv.handle_tool_error = True   # 与 sql_db_query:338 对齐：捕获 ToolException 并回喂模型
    return export_to_csv
```

```python
# 修改 [backend/app/agent/tools/chart_artifact_tool.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/tools/chart_artifact_tool.py)

from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException
from langchain_core.tools import ToolException
# 删除原 `from backend.app.agent.tools.sql_tools import FORBIDDEN_SQL_PATTERN`（已迁入 sql_linter.py）

def create_chart_artifact_tool(engine: Engine, custom_table_info: dict = None) -> Any:

    @langchain_tool(args_schema=BuildChartArtifactInput)
    def build_chart_artifact(
        # ... 参数列表保持不变
    ) -> str:
        # 技能加载校验保留；原 FORBIDDEN_SQL_PATTERN 正则块整体删除（已被下方 Linter 覆盖）
        emit_stream_status("正在执行 SQL 合规检查", stage="querying", source="build_chart_artifact")
        try:
            # 统一执行安全合规校验
            validate_readonly_query(query, custom_table_info)
        except SQLLintException as exc:
            logger.warning(f"build_chart_artifact 校验未通过拦截: {exc}")
            # 统一错误出口：抛出 ToolException 触发大模型自愈重写（与 sql_db_query 对齐）
            raise ToolException(str(exc))

        # 校验通过，进入原 text(query) 执行与图表生成逻辑

    build_chart_artifact.handle_tool_error = True   # 与 sql_db_query:338 对齐
    return build_chart_artifact
```

---

## 四、 范围与限制 (Scope & Limitations)

本方案是诊断报告（`docs/StructuredOutput/existing_system_diagnosis.md`）中的 **P0 项**，仅对齐 **Linter 校验**与**错误契约**，不涉及以下内容：

1. **`sql_checker_mode=="safety"` 语法检查器未对齐**：`sql_db_query` 在 Linter 之外还会调用 `original_checker_tool` 做一次语法检查（`sql_tools.py:263-277`）。该检查器依赖 SQLDatabase toolkit 的 checker 工具实例，csv/chart 工具不持有该实例，故暂不纳入。重构后三工具仍存在"Linter + checker（仅 sql_db_query）"的非对称，属**已知范围限制**；若需彻底拉平，需重构工具上下文注入（P2）。

2. **Linter 是静态结构分析，不解决性能/DoS**：11 条规则覆盖 DML/多语句/别名/JOIN 唯一性等**结构与安全**问题，但**无法拦截**裸 `CROSS JOIN`、缺失 `ON`、非选择性过滤、全表扫描等导致的慢查询。特别地，**CSV 导出无行数上限**（`csv_export_tool.py:91` `result.fetchall()` 全量捞入内存），一条合法但返回千万行的 SQL 仍可能 OOM 服务端。行数 guard 属 P2（`QueryResult` 抽象），不在本方案。

3. **未消除"同 SQL 重跑 3 次"**（诊断根因 B-2）：三工具仍各自直连 DB 执行，本方案只统一校验，未统一执行路径。统一执行属 P2。

4. **`SQLLintException` 解耦为可选设计**：引入自定义异常是为保持 `sql_linter.py` 与 LangChain 解耦、便于独立单测（故 `validate_readonly_query` 内**不引入** `emit_stream_status` 等流式依赖，状态发射保留在各工具内）。若后续认为翻译层冗余，也可让 `validate_readonly_query` 直接 `raise ToolException`，但需相应调整单测。

---

## 五、 中间件错误判定连带影响分析 (Middleware Impact Analysis)

将 csv/chart 的错误出口从 `return "Error: ..."` 改为 `raise ToolException` 后，需确认不破坏 `PromptCompilerMiddleware` 的失败判定。该中间件以 5 阶段流水线处理消息历史（`prompt_compiler_middleware.py:101-127`），其中 Stage 2 `_stage_prescan_failures`（`:153-195`）识别失败的工具调用，Stage 4 物理删除其 AIMessage+ToolMessage 配对（`:292-323`）。

### 1. 判定机制：字符串匹配 ToolMessage content

Stage 2 对窗口外（`range(ctx.boundary_index)`，`:155`）的 ToolMessage，按 `_DELETION_TARGET_CONFIG`（`:140-151`）逐工具判定 `is_failed`，优先级：
1. `has_linter` 且 content 含 `"X-SQL-LINTER-STATUS: FAILED"`（`:172`）；
2. `has_runtime` 且 content 含各自 `runtime_header`（`:174`）；
3. **else 兜底**：非 JSON list 成功态时，`"error" / "exception" / "failed"` 子串匹配（小写，`:188-192`）。

### 2. 为什么 `raise ToolException` 不会破坏检测

- **sql_db_query 已是先例**：它现在就 `raise ToolException(result.format_error_message())` + `handle_tool_error=True`（`sql_tools.py:261`+`:338`），而 Stage 3 能稳定识别其 Linter 错误（靠 `"X-SQL-LINTER-STATUS: FAILED"` / `"Linter 拦截"` 标记，`:216-220`）。这反证：`raise ToolException` 经 `handle_tool_error` 回填的 ToolMessage content **完整保留了 `format_error_message()` 文本**（含上述标记与 "error"/"FAILED" 关键字）。
- **csv/chart 复用同一 `validate_readonly_query`**，ToolMessage content 与 sql_db_query 同源，关键字匹配同样命中。
- **逐工具核对**：

| 工具 | 在配置表? | 改后检测路径 | 是否仍生效 |
|---|---|---|---|
| `build_chart_artifact` | 在（`has_linter=False`） | 兜底子串匹配（content 含 "error"/"FAILED"） | ✅ 一致 |
| `export_to_csv` | **不在** | Stage 2 直接 `continue` 跳过（`:165-166`） | ✅ 一致（均不处理） |

- **自愈链路未断**：Stage 2 只扫窗口外消息，当前 ReAct 循环内（保护窗口）的 csv/chart 失败不被扫描、不被删，LLM 看得到错误并能改写重试。

### 3. 配置表与重构后状态的差异（决策点）

重构让 csv/chart 都跑 Linter，而 `_DELETION_TARGET_CONFIG` 仍是旧认知，需明确处理：

- **`build_chart_artifact` 的 `has_linter: False`**：语义上已陈旧（chart 现在跑 Linter），但**功能上是 no-op**--无论 `has_linter` 取值，Linter 错误都会落到兜底分支被 `"error"/"failed"` 子串命中。可选改为 `True` 以对齐语义，但不影响行为。
- **`export_to_csv` 在配置表中物理删除**：**决定纳入**。评估结论是：即使 CSV 列名中包含 "error" 或 "failed" 导致成功的 CSV 消息在滑动窗口外被误判为失败并物理删除，也是符合预期的。因为数据已经成功导出，用户也已经得到了下载链接，物理删除旧的历史消息对对话的后文无实质负面干扰，反而可以进一步清空冗余上下文节省 Token 空间。故最终在 `_DELETION_TARGET_CONFIG` 中将其设置为 `has_linter: True`。

### 4. 既有问题（不在本方案范围，记录备查）

- **csv 失败被 Stage 5 误折叠为 "completed"**：`_stage_standard_collapse`（`:325-361`）对窗口外的 `export_to_csv` 一律折叠为 `"[CSV export completed and collapsed.]"`（`:354-358`），不区分成败，对失败的 csv 是误导性文案。**本重构不引入也不修复**（return 字符串时同样如此）。彻底修复需增强 Stage 2 成功态识别（认 dict-JSON artifact），属 P2。
- **判定机制本身的脆弱性**：靠子串匹配 content 判定成败，属诊断报告根因 D/E 类脆弱性。LangChain 在 `handle_tool_error=True` 捕获 `ToolException` 时本会打结构化错误语义标记，未来可改读结构化标记而非正则。属 P2+。

---

## 六、 校验效果与验证方案 (Verification & Testing)

重构完成后，需通过以下方案验证 Linter 校验与错误契约是否完全对齐：

### 1. 自动化单元测试
在测试套件中为 `export_to_csv` 和 `build_chart_artifact` 追加针对 Linter 拦截的测试用例：
* **测试用例 1（DML 拦截）**：输入 `UPDATE t_qm_defect SET count = 0;`。期望结果：工具被拦截，抛出 `ToolException`（含 `SEC-001` 报错）。
* **测试用例 2（多语句拦截）**：输入 `SELECT 1; SELECT 2;`。期望结果：工具被拦截，抛出 `SEC-002` 错误。
* **测试用例 3（Ambiguous Column 拦截）**：在有多表 JOIN 的 SQL 中故意去掉字段的前缀（如 `SELECT id FROM ...`）。期望结果：工具拦截，抛出 `STR-002` 错误。
* **测试用例 4（错误契约对齐）**：对 `export_to_csv` 与 `build_chart_artifact` 输入会触发 `AliasPrefixRule` 的 SQL，期望：工具**抛出 `ToolException`**（而非返回 `"Error: ..."` 字符串），且因 `handle_tool_error=True`，错误以 `ToolMessage` 回喂模型并触发自愈重写，而非中断 Agent。

### 2. 交互日志 diff 检查
在本地启动服务，在会话中诱导大模型写出不带别名前缀的 SQL 并执行导出，检查后端控制台日志，确认有 Linter 的警告记录与拦截动作：
```bash
[WARNING] Linter 校验拦截:
X-SQL-LINTER-STATUS: FAILED
Error: SQL Linter 拦截 - 检测到以下问题：
1. [ERROR] STR-002: 多表关联查询中，必须显式指定列的表别名前缀...
```

### 3. 错误契约一致性验证
确认三个工具在 Linter 拦截时行为一致：
- 均抛出 `ToolException`（而非返回 `"Error: ..."` 字符串），错误信息以 `ToolMessage` 语义回喂模型；
- `export_to_csv` / `build_chart_artifact` 均已设置 `handle_tool_error = True`（与 `sql_db_query:338` 对齐），确保异常被捕获而非中断 Agent；
- 大模型基于报错改写 SQL 并重试的自愈链路打通（可在日志中观察到重试后的成功执行）。

### 4. 中间件兼容性验证
确认 `PromptCompilerMiddleware` 的失败判定不被破坏（详见 §五）：
- 对 `build_chart_artifact` 触发 Linter 失败，确认 Stage 2 仍能识别（日志可见 `🗑️ Paired physical deletion` 含该 call_id）；
- 对 `export_to_csv` 触发 Linter 失败，确认当前循环内 LLM 能看到错误并自愈重试（窗口内不被删）；
- 对 `export_to_csv` 成功导出（结果含列名 `error_count`），确认**不被误删**（csv 不在 `_DELETION_TARGET_CONFIG`，Stage 2 跳过）。
