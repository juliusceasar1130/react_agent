# SQL Linter 执行前检查方案 (P2)

> 记录时间: 2026-07-06 Asia/Shanghai
> 相关讨论: P2 — SQL 执行前 AST 检查 — 三层拦截体系
> 前置依赖: `fanout_research.md` (问题分析), `grain_template.md` (粒度标注规范)

---

## 1. 目标

在 LLM 生成的 SQL **执行前**进行自动化检查，将当前"纯提示词软约束"升级为"执行前硬约束"，从根源拦截结构错误和逻辑风险。

```
当前链路:
  Prompt 规则(可能忽略) → 数据库执行(报错) → LLM 重试
  
目标链路:
  Prompt 规则(软约束) → SQL Linter(硬拦截) → 数据库执行(安全) → 结果返回
                            ↓ 拦截
                    LLM 根据错误重写
```

---

## 2. 三层拦截体系

| 层 | 名称 | 依赖 | 拦截目标 | 级别 |
|---|---|---|---|---|
| 第一层 | **安全拦截** | 无 | 防破坏 | ERROR |
| 第二层 | **结构合规** | 无 | 防低质量 SQL | ERROR |
| 第三层 | **语义校验** | 表元数据 | 防数据失真 | ERROR/WARNING |

### 2.1 第一层：安全拦截（零依赖）

| 规则 ID | 规则 | 实现方式 | 严重度 |
|---|---|---|---|
| `SEC-001` | DML/DDL 关键字拦截 | AST 节点检测 (`exp.Insert`/`exp.Update`/`exp.Delete`/`exp.Drop` 等) | ERROR |
| `SEC-002` | 多语句堆叠检测 | AST `sqlglot.parse(sql)`, `len(expressions) > 1` 时拦截堆叠注入 | ERROR |
| `SEC-003` | 数据库名前缀检测 | 正则 `\w+\.\w+\.\w+\.\w+` 检测 `db.schema.table` 三层引用 | ERROR |

**说明**：SEC-002 替代原注释注入检测。理由：`sqlglot` 解析 AST 时会自动忽略注释，基于正则的注释内容检查容易被 LLM 的解释性注释误触发（如 `-- 排除已删除的记录` 含 delete 关键词）。改用多语句堆叠检测更彻底、零误报。

### 2.2 第二层：结构合规（零依赖）

| 规则 ID | 规则 | 实现方式 | 严重度 |
|---|---|---|---|
| `STR-001` | `SELECT *` 检测（排除聚合函数） | AST 检查 `exp.Star` 节点，**排除**作为聚合函数参数的情况（如 `COUNT(*)` 是 `Count(this=Star())`，不应拦截） | ERROR |
| `STR-002` | 强制表别名前缀（仅多表查询） | 仅当 `len(parsed.find_all(exp.Table)) > 1` 时激活检查，单表查询豁免 | ERROR |
| `STR-003` | 子查询嵌套层数限制 | AST 递归计算子查询深度（>3 层拦截，CTE 不计入嵌套深度） | ERROR |
| `STR-004` | 多层 CTE 引用检测 | AST 统计 `exp.CTE` 节点数（>3 个 CTE 告警） | WARNING |

### 2.3 第三层：语义校验（需表元数据）

| 规则 ID | 规则 | 实现方式 | 严重度 |
|---|---|---|---|
| `SEM-001` | JOIN 关联列唯一性校验 | AST 提取 ALL JOIN ON 条件。**安全判定**（满足任一即安全）：<br>1. **条件 A**：左表关联列是左表 PK/UNIQUE<br>2. **条件 B**：右表关联列是右表 PK/UNIQUE<br>3. **条件 C**：目标侧是子查询且其 GROUP BY 列包含关联列<br>以上均不满足时拦截 | ERROR |
| `SEM-002` | COUNT DISTINCT 检测 | AST 检查 `exp.CountStar` → 查表 Grain 标注是否有"重复"关键字，提示使用 `COUNT(DISTINCT vehicle_id)` | WARNING |
| `SEM-003` | DELETE/UPDATE 误用检测 | 同 SEC-001（AST 节点检测），作为 AST 法兜底 | ERROR |
| `SEM-004` | 子查询 JOIN 列唯一性校验 | JOIN 目标是子查询时：检查子查询是否对其关联列做了 GROUP BY 去重或 DISTINCT | ERROR |

---

## 3. 模块架构

### 3.1 代码结构

```
backend/app/agent/utils/sql_linter.py    ← 新文件
backend/app/agent/tools/sql_tools.py     ← 修改
```

### 3.2 核心数据模型

```python
# === 违规记录 ===
@dataclass
class LintViolation:
    rule_id: str            # "SEC-001" / "STR-001" / "SEM-001"
    severity: str           # "ERROR" | "WARNING" | "INFO"
    message: str            # 人类可读的错误描述
    detail: str | None      # 检测到的具体内容（如具体哪个表使用了 SELECT *）
    fix_suggestion: str     # 修复建议
    location: dict | None   # 可选：AST 定位信息

# === 规则基类 ===
class BaseLintRule(ABC):
    """所有检查规则的抽象基类"""
    rule_id: str
    severity: str

    @abstractmethod
    def check(self, sql: str, context: "LintContext") -> list[LintViolation]:
        ...

# === 上下文 ===
@dataclass
class LintContext:
    """检查上下文（仅第三层需填充元数据）"""
    table_pk_map: dict[str, list[str]]      # {table_name: [pk_col1, pk_col2]}
    table_unique_map: dict[str, list[str]]  # {table_name: [unique_col1]}
    table_grain_map: dict[str, str]         # {table_name: "semantic_grain"}
    is_event_table: dict[str, bool]         # {table_name: True/False}

# === 编排器 ===
class SQLLinter:
    """规则编排器：注册 → 执行 → 分级返回"""

    def __init__(self):
        self._rules: list[BaseLintRule] = []

    def register(self, rule: BaseLintRule) -> None:
        ...

    def lint(self, sql: str, context: LintContext | None = None) -> LintResult:
        """执行所有注册的规则"""
        ...

@dataclass
class LintResult:
    """检查结果"""
    passed: bool                    # True = 所有 ERROR 级别规则通过
    errors: list[LintViolation]     # ERROR 级别违规
    warnings: list[LintViolation]   # WARNING 级别违规
    messages: list[str]             # 格式化后的消息列表（可直接返回给 LLM）
```

### 3.3 规则实现

```
BaseLintRule
├── DMLSecurityRule        (SEC-001, SEC-003 合并)    ← AST 节点检测
├── MultiStatementRule     (SEC-002)                  ← 堆叠查询拦截
├── DatabasePrefixRule     (SEC-003)                  ← 正则
├── StarSelectRule         (STR-001)                  ← AST，排除 COUNT(*)
├── AliasPrefixRule        (STR-002)                  ← AST，仅多表时激活
├── SubqueryDepthRule      (STR-003)                  ← AST 递归
├── JoinUniquenessRule     (SEM-001, SEM-004 合并)    ← AST + 表元数据
└── CountDistinctRule      (SEM-002)                  ← AST + Grain 元数据
```

---

## 4. 集成方案

### 4.1 在 `sql_tools.py` 中的插入点

```python
def create_wrapped_query_tool(
    original_query_tool: Any,
    original_checker_tool: Optional[Any] = None,
    custom_table_info: Optional[dict] = None,  # ← [新增] 供第三层语义校验
) -> Any:

    # ── [新增] 初始化 SQL Linter ──────────────────────
    sql_linter = _init_linter(custom_table_info)
    # ──────────────────────────────────────────────────

    @langchain_tool
    def sql_db_query(query, required_skill, runtime):

        # Step 0: 安全拦截
        # Step 1: 技能加载校验

        # ── [NEW] Step 1.5: SQL Linter 执行前检查 ──────────
        lint_result = sql_linter.lint(query)
        if not lint_result.passed:
            return lint_result.format_error_message()
        # ──────────────────────────────────────────────────

        # Step 2: SQL 语法检查
        # Step 3: 执行查询
        # Step 4: 日期标准化
        # Step 5: 结果限流
```

### 4.2 错误返回格式

```python
return (
    "Error: SQL Linter 拦截 — 检测到以下问题：\n\n"
    "1. [ERROR] STR-001: 禁止使用 SELECT *。\n"
    "   检测到: SELECT * FROM quality_360\n"
    "   修复建议: 显式声明所需列名，如 SELECT history_id, vehicle_id, ...\n\n"
    "2. [ERROR] STR-002: 缺少表别名前缀。\n"
    "   检测到: JOIN quality_360 ON vehicle_id = vehicle_id\n"
    "   修复建议: 为 quality_360 指定别名 q，如 JOIN quality_360 q ON q.vehicle_id = pc.vehicle_id\n\n"
    "请修正 SQL 后重试。"
)
```

### 4.3 `LintContext` 初始化

```python
def _init_linter(custom_table_info: Optional[dict]) -> SQLLinter:
    """根据是否提供表元数据初始化不同级别的 linter"""
    linter = SQLLinter()

    # 第一、二层规则（零依赖）—— 始终注册
    linter.register(DMLSecurityRule())
    linter.register(MultiStatementRule())
    linter.register(DatabasePrefixRule())
    linter.register(StarSelectRule())
    linter.register(AliasPrefixRule())
    linter.register(SubqueryDepthRule())

    # 第三层规则（需表元数据）
    if custom_table_info:
        context = _build_lint_context(custom_table_info)
        linter.register(JoinUniquenessRule(context))
        linter.register(CountDistinctRule(context))

    return linter
```

---

## 5. 实施计划

### 5.1 分阶段实施

| 阶段 | 内容 | 工作量 | 交付物 |
|---|---|---|---|
| **P2.1a** | 创建 `sql_linter.py` 框架（`LintViolation`、`BaseLintRule`、`SQLLinter`、`LintResult`） | 30min | 基础数据模型 + 编排器 |
| **P2.1b** | 实现第一层规则：`DMLSecurityRule` (AST) + `CommentInjectionRule` + `DatabasePrefixRule` | 30min | 安全拦截三条规则 |
| **P2.1c** | 实现第二层规则：`StarSelectRule` + `AliasPrefixRule` + `SubqueryDepthRule` | 40min | 结构合规三条规则 |
| **P2.1d** | 集成到 `create_wrapped_query_tool` | 15min | 拦截生效 |
| **P2.1e** | 单元测试：正常 SQL / 含风险 SQL / 边界情况 | 30min | 测试用例 |
| **P2.2a** | 实现 `_build_lint_context` 元数据提取 + `LintContext` | 20min | 上下文构建 |
| **P2.2b** | 实现第三层规则：`JoinPKRule` + `CountDistinctRule` | 40min | 语义校验规则 |
| **P2.2c** | 第三层集成 + 集成测试 | 20min | 全链路生效 |

### 5.2 优先级排序

```
P2.1 (先做, ~2.5小时) ─────────────────
  ├─ 建立框架 + 安全规则 → 立即拦截破坏性操作
  ├─ 结构规则 → 拦截低质量 SQL
  └─ 集成测试 → 确认不影响正常查询

P2.2 (后做, ~1.5小时) ─────────────────
  ├─ 元数据上下文 → 复用 db_utils.py 的 PK/UNIQUE 输出
  └─ 语义规则 → 拦截数据失真风险
```

---

## 6. 测试策略

### 6.1 测试用例

```python
# === 第一层：安全 ===
["DELETE FROM table", "ERROR", "DML 拦截"]
["INSERT INTO table VALUES (1)", "ERROR", "DML 拦截"]
["SELECT 1; DROP TABLE users", "ERROR", "堆叠查询拦截（替代注释注入）"]
["SELECT * FROM analytics_db.fct.table", "ERROR", "数据库名前缀"]

# 注释含关键字不应误报
["SELECT * FROM t -- 排除已删除记录", "PASS", "注释不触发安全拦截"]

# === 第二层：结构 ===
["SELECT * FROM t", "ERROR", "裸 SELECT *"]
["SELECT COUNT(*) FROM t", "PASS", "COUNT(*) 不被误杀"]
["SELECT a.col FROM t1 a JOIN t2 ON col = col", "ERROR", "多表别名缺失"]
["SELECT col FROM single_table", "PASS", "单表免别名"]
["SELECT * FROM (SELECT * FROM (SELECT * FROM t))", "ERROR", "子查询超深"]
["WITH a AS (...) SELECT * FROM (SELECT * FROM t)", "PASS", "CTE 不计深度"]

# === 第三层：语义 ===
["SELECT COUNT(*) FROM quality_360", "WARNING", "COUNT 未 DISTINCT（需要 Grain 元数据）"]
["SELECT t1.a, t2.b FROM dim t1 JOIN fact t2 ON t1.id = t2.fk", "PASS", "N:1 JOIN 安全（左表 id 是 PK）"]
["SELECT t1.a, t2.b FROM fact t1 JOIN dim t2 ON t1.fk = t2.id", "PASS", "N:1 JOIN 安全（右表 id 是 PK）"]
["SELECT t1.a, t2.b FROM t1 JOIN t2 ON t1.a = t2.non_pk", "ERROR", "双侧均非 PK/UNIQUE"]

# === 白名单（必须全部 PASS）===
["SELECT vehicle_id FROM position_current", "PASS", "简单单表查询"]
["WITH cte AS (SELECT id FROM t) SELECT * FROM cte", "PASS", "CTE 正常"]
["SELECT a.col1, b.col2 FROM t1 a LEFT JOIN t2 b ON a.id = b.id", "PASS", "规范多表查询"]
["SELECT pc.vehicle_id, pc.process_area FROM fct.fct_vehicle_position_current pc WHERE pc.vehicle_id = 'ABC123'", "PASS", "带条件查询"]
["SELECT COUNT(*), vehicle_id FROM quality_360 GROUP BY vehicle_id", "PASS", "合法聚合查询"]
```

### 6.2 零误杀验证（部署前必做）

P2.1 阶段完成后，收集目前系统已有的正常 SQL 案例（从日志/历史记录提取），跑一遍 Linter 确保：

- **False Positive Rate = 0%**：所有历史正常的 SQL 必须全部 PASS
- 若发现误杀，优先调整规则逻辑，而非关闭规则
- 将验证通过的 SQL 加入白名单测试套件，防止后续规则变更回退

---

## 7. 决策记录

| 序号 | 决策 | 选项 | 选择理由 |
|---|---|---|---|
| 1 | 规则基类 vs 函数列表 | **基类** | 扩展性更好，新规则只需继承 + 注册两步 |
| 2 | AST vs 正则 | **AST 优先**，正则兜底 | AST 更精确（如安全检测用 AST，数据库名前缀用正则） |
| 3 | 分层 vs 单文件 | **分层模块** | 第一二层可独立发布，无需等元数据 |
| 4 | 拦截 vs 仅告警 | **ERROR 拦截 + WARNING 附加** | 安全/结构问题不可绕过，语义问题可提示 |
| 5 | 注释注入 vs 堆叠检测 | **堆叠检测替代注释正则** | sqlglot 解析 AST 自动忽略注释，正则易误报解释性文本 |
| 6 | SELECT * 检查范围 | **排除 COUNT(*) 参数** | 避免误杀 `SELECT COUNT(*)` 这一最常用聚合 |
| 7 | 别名检查范围 | **仅多表查询激活** | 单表查询强制别名过于严苛 |
| 8 | JOIN 安全判定 | **任一关联列在对应表 PK/UNIQUE 即安全** | N:1 JOIN（dim→fact）天然安全，不应拦截 |
| 9 | 子查询 JOIN 安全 | **GROUP BY 含关联列即安全** | 预聚合子查询虽无物理 PK，但语义上唯一 |
| 10 | 零误杀验证 | **部署前必做** | P2.1 完成即收集历史 SQL 验证，防止误拦截影响正常查询 |
| 11 | 单测优先 vs 后补 | **实现后立即补单测** | 防止后续规则改动破坏已有拦截 |

---

## 8. 风险和缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| sqlglot AST 解析复杂 SQL 失败 | 漏检 | 捕获异常并 fallback 到正则兜底 |
| `COUNT(*)` 被 `SELECT *` 规则误杀 | 最常用聚合被拦 | `StarSelectRule` 排除作为聚合参数（`Count(this=Star())`）的 Star 节点 |
| 解释性注释含 DML 关键字被误杀 | 正常查询被拦 | 改为多语句堆叠检测，彻底消除注释误报 |
| JOIN 双侧均非 PK 的合法 N:M 被拦 | 正常业务被拦 | 仅对 JOIN 侧均非 PK/UNIQUE 时拦截，双侧合法用 WARNING 而非 ERROR |
| 子查询深度限制太紧 | 合法 CTE 被拦 | CTE 不计入嵌套深度；阈值设为 ≥4 再报警 |
| 第三层元数据缺失导致漏检 | 语义校验失效 | `_init_linter` 优雅降级，无元数据时不注册第三层规则，不影响正常查询
