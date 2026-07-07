# SQL Linter 执行前检查方案 (P2)

> 记录时间: 2026-07-07 Asia/Shanghai
> 相关讨论: P2 — SQL 执行前 AST 检查 — 三层拦截体系
> 前置依赖: `fanout_research.md` (问题分析), `grain_template.md` (粒度标注规范)

---

## 1. 目标

在 LLM 生成的 SQL **执行前**进行自动化检查，将当前"纯提示词软约束"升级为"执行前硬拦截"，从根源拦截结构错误和逻辑风险，确保只读性与数据准确性，并利用 ToolException 触发 Agent 的自我修复 (Self-Correction) 逻辑。

```
当前工作流:
  Prompt 规则(可能忽略) → 数据库执行(报错/返回膨胀数据) → LLM 重试
  
优化后工作流:
  Prompt 规则(软约束) → SQL Linter(硬拦截/智能警告) ── (不通过，抛出 ToolException) ──> LLM 纠错自愈
                            │
                            ▼ (通过)
                       数据库安全执行
```

---

## 2. 三层拦截体系

| 层 | 名称 | 依赖 | 拦截目标 | 级别 |
|---|---|---|---|---|
| 第一层 | **安全拦截** | 无 | 防破坏、防注入 | ERROR |
| 第二层 | **结构合规** | 无 | 强制 SQL 编写质量，防性能隐患 | ERROR |
| 第三层 | **语义校验** | 表元数据 (DDL) | 结合库表属性与粒度，防数据失真 | ERROR/WARNING |

### 2.1 第一层：安全拦截（零依赖）

| 规则 ID | 规则名称 | 实现方式 | 说明 | 严重度 |
|---|---|---|---|---|
| `SEC-001` | DML/DDL 写操作拦截 | AST 节点检测 (`exp.Insert`, `exp.Update`, `exp.Delete`, `exp.Drop`, `exp.Create`, `exp.Alter` 等) | 拦截所有写入与修改操作。若 AST 解析失败，退避到正则 `FORBIDDEN_SQL_PATTERN` 兜底。 | **ERROR** |
| `SEC-002` | 多语句堆叠检测 | AST 校验 `len(sqlglot.parse(sql, read="postgres")) > 1` | 拦截分号拼接的多条 SQL，从物理层杜绝堆叠注入。 | **ERROR** |
| `SEC-003` | 跨库/系统模式限制 | AST 检查 `exp.Table` 节点。限制 `table.db` 不为空，或 `table.schema` 不在允许的白名单内 | 限制仅能访问白名单内的 Schema。 | **ERROR** |

---

### 2.2 第二层：结构合规（零依赖）

| 规则 ID | 规则名称 | 实现方式 | 说明 | 严重度 |
|---|---|---|---|---|
| `STR-001` | `SELECT *` 拦截 | AST 检查 `exp.Star` 或 `exp.Dot (其 expression 为 Star)` 且其父节点不是聚合函数（如 `Count`） | **防误杀**：允许 `SELECT COUNT(*)` 或 `COUNT(*) OVER (...)`，但拦截裸的 `SELECT *` 或 `SELECT t.*`。 | **ERROR** |
| `STR-002` | 强制表别名前缀 | AST 检查 `exp.Column`，校验 `table` 别名属性是否缺失 | **防误杀**：仅当查询中显式存在 `exp.Join` 节点（联接查询）时激活。对 `UNION ALL` 或独立的单表子查询免除。 | **ERROR** |
| `STR-003` | 子查询嵌套层数限制 | 递归计算 AST 中嵌套子查询的深度值 | **排除 CTE**：CTE 扁平查询不计入嵌套深度，`WITH RECURSIVE` 递归结构不计深度。可配置最大深度阈值。 | **ERROR** |
| `STR-004` | CTE 数量告警 | AST 统计 `exp.CTE` 节点数量 | 只告警不拦截，提示 LLM 优化过长 CTE。可配置最大 CTE 阈值。 | **WARNING** |

---

### 2.3 第三层：语义校验（基于库表元数据）

此层规则通过解析 `db_utils.py` 返回的 DDL 注释（包含 `PRIMARY KEY`、`UNIQUE` 约束和 `-- Grain:` 注释）初始化 `LintContext` 上下文。

| 规则 ID | 规则名称 | 判定逻辑 | 防误杀与降级机制 | 严重度 |
|---|---|---|---|---|
| `SEM-001` | JOIN 关联列唯一性校验 | 提取多表 `JOIN ON` 关联列集合。满足任一条件即判定安全，否则拦截：<br>1. **物理主/唯一键**：关联列集是对应表唯一/主键列集的超集。<br>2. **子查询 GROUP BY/DISTINCT**：右侧子查询的分组或 DISTINCT 列覆盖关联列。<br>3. **极值子查询过滤**：通过 `MAX(col)`/`MIN(col)` 过滤特定列并关联外层键。<br>4. **ROW_NUMBER 窗口过滤**：子查询含 `ROW_NUMBER()` 且外层 ON 过滤为 `= 1`。<br>5. **LIMIT 1 全局去重**：右侧子查询带有 `LIMIT 1`。 | **1. 复合主键支持**：如上进行超集包含比对。<br>**2. 无聚合函数降级**：若整个 SQL 中无 SUM/AVG/COUNT，降级为 `WARNING`。<br>**3. 旁路豁免**：检测到行首有 `-- linter-bypass: SEM-001` 强制放行。 | **ERROR** |
| `SEM-002` | 聚合去重校验 | 在 `is_event_table` 标记为 True 的表上，使用未加 `DISTINCT` 的 `COUNT` 聚合 | **1. 本级 Select 存在 GROUP BY 放行**：分组统计单实体事件数豁免，且校验粒度局限在各自的 Select 块内部，不被子查询内的 Group By 屏蔽干扰。<br>**2. 降级为 WARNING**：只警告不拦截，防过度敏感受伤。<br>**3. 统一覆盖**：`COUNT(*)` 与 `COUNT(col)` 均进行检查。<br>**4. 旁路豁免**：包含 `-- linter-bypass: SEM-002`。 | **WARNING** |
| `SEM-003` | 标量子查询唯一性 | 检查 scalar subquery（如 `col = (SELECT ...)`） | **1. 包含 LIMIT 1 放行**。<br>**2. 使用 MAX/MIN/AVG 等聚合函数放行**。<br>**3. 排除 Table Subquery**：若子查询作为 FROM/JOIN 数据源，自动忽略免检。<br>4. 否则作为 `WARNING` 提示有报错隐患。 | **WARNING** |
| `SEM-004` | `NOT IN` 安全性检测 | 检查 `NOT IN` 子查询以防范 NULL 值穿透陷阱 | **1. 字字面量列表放行**：若右侧为 `('A', 'B')` 等常量，直接放行。<br>**2. 子查询拦截**：若右侧为 `SELECT` 子查询，强制拦截并引导改写为 `NOT EXISTS`。 | **ERROR** |

---

## 3. 可配置化设计 (Settings Config)
在 `backend/app/config.py` 的 `Settings` 类中新增 Linter 专用配置字段，允许环境变量和本地配置文件（dotenv）动态控制：

```python
# === SQL Linter 配置 ===
sql_linter_enabled: bool = True
sql_linter_max_subquery_depth: int = 3
sql_linter_max_cte_count: int = 3
sql_linter_allowed_schemas_raw: str = Field(
    default="mart,fct,dim,ods,meta,public",
    validation_alias="sql_linter_allowed_schemas"
)
sql_linter_rules_severity_raw: str = Field(
    default="",
    validation_alias="sql_linter_rules_severity_override"
)

@property
def sql_linter_allowed_schemas(self) -> list[str]:
    return [s.strip().lower() for s in self.sql_linter_allowed_schemas_raw.split(",") if s.strip()]

@property
def sql_linter_rules_severity_override(self) -> dict[str, str]:
    result = {}
    if not self.sql_linter_rules_severity_raw:
        return result
    for pair in self.sql_linter_rules_severity_raw.split(","):
        if ":" in pair:
            rule_id, severity = pair.split(":", 1)
            result[rule_id.strip().upper()] = severity.strip().upper()
    return result
```

---

## 4. 模块架构与数据模型

### 4.1 代码结构

```
backend/app/agent/utils/sql_linter.py    ← 新文件：核心 Linter 引擎与规则集
backend/app/agent/tools/sql_tools.py     ← 修改：集成 linter 到包装后的 sql_db_query
```

### 4.2 核心数据模型

```python
# === 违规记录 ===
@dataclass
class LintViolation:
    rule_id: str            # "SEC-001" / "STR-001" / "SEM-001"
    severity: str           # "ERROR" | "WARNING" | "INFO"
    message: str            # 人类可读的简明错误描述
    detail: str | None      # 检测到的危险代码片段（如 "SELECT * FROM quality_360"）
    fix_suggestion: str     # 具体的重写指导建议
    location: dict | None   # 错误所在的行号/位置（可选）

# === 规则基类 ===
class BaseLintRule(ABC):
    """所有检查规则的抽象基类"""
    rule_id: str
    severity: str

    @abstractmethod
    def check(self, parsed: sqlglot.Expression, context: "LintContext") -> list[LintViolation]:
        ...

# === 检查上下文 ===
@dataclass
class LintContext:
    """元数据上下文（由 custom_table_info DDL 解析初始化）"""
    table_pk_map: dict[str, list[str]]      # {table_name: [pk_col1, pk_col2]}
    table_unique_map: dict[str, list[list[str]]]  # {table_name: [[unique_cols1], [unique_cols2]]} 支持复合唯一键
    table_grain_map: dict[str, str]         # {table_name: "semantic_grain"}
    is_event_table: dict[str, bool]         # {table_name: True/False}

# === 编排器 ===
class SQLLinter:
    """规则编排器：负责规则注册、AST 解析和异常处理"""

    def __init__(self):
        self._rules: list[BaseLintRule] = []

    def register(self, rule: BaseLintRule) -> None:
        self._rules.append(rule)

    def lint(self, sql: str, context: LintContext | None = None) -> LintResult:
        """执行所有注册的规则"""
        ...
```

---

## 5. 集成方案与 ToolException 纠错设计

### 5.1 引入 ToolException 自愈

为防止 LLM 将 Linter 拦截提示误判为正常查询结果，在 `sql_tools.py` 中捕获并抛出 `ToolException`：

```python
from langchain_core.tools import ToolException

def create_wrapped_query_tool(
    original_query_tool: Any,
    original_checker_tool: Optional[Any] = None,
    custom_table_info: Optional[dict] = None,
) -> Any:

    # 载入配置并初始化 Linter
    sql_linter = _init_linter(custom_table_info)

    @langchain_tool(handle_tool_errors=True)  # 💡 强行开启 ToolError 捕获
    def sql_db_query(query: str, required_skill: str, runtime: ToolRuntime) -> str:
        # Step 0: 如果开启了 Linter，则编译方言并解析 AST 检查
        if settings.sql_linter_enabled:
            try:
                parsed = sqlglot.parse_one(query, read="postgres")
            except Exception as exc:
                # 解析失败退避至安全正则校验
                if FORBIDDEN_SQL_PATTERN.search(query):
                    raise ToolException(
                        "Error: 严重安全拦截 - 检测到非法的写操作关键字，请仅编写 SELECT 只读查询。"
                    )
                parsed = None

            if parsed:
                # 运行 Linter 检查
                lint_result = sql_linter.lint(parsed)
                if not lint_result.passed:
                    # ── [CRITICAL] 抛出异常，强制 Agent 进行 Self-Correction ──
                    raise ToolException(lint_result.format_error_message())

        # Step 1: 技能加载校验
        # Step 2: 执行查询 ...
```

---

## 6. 测试策略与边界测试用例

为达到**生产级零误杀（False Positive = 0%）**，测试套件需覆盖以下边界用例：

```python
# === 1. 边界与退避路径测试 ===
["SELECT col FROM table WHERE a = 1; DELETE FROM table", "ERROR", "堆叠注入拦截"]
["SELECT public.carbody_registry.vehicle_id FROM public.carbody_registry", "PASS", "模式限定符列别名校验放行"]
["SELECT COUNT(*) OVER (PARTITION BY vehicle_id) FROM t", "PASS", "窗口函数 Star 聚合放行"]

# === 2. 复合唯一键与 JOIN 校验 ===
# t1 (复合主键 a, b), t2 (非主键 x, y)
["SELECT * FROM t1 JOIN t2 ON t1.a = t2.x AND t1.b = t2.y", "PASS", "复合关联匹配放行"]
["SELECT * FROM t1 JOIN t2 ON t1.a = t2.x", "ERROR", "部分主键匹配拦截"]

# === 3. CTE 嵌套与 UNION 别名校验 ===
["SELECT col FROM t1 UNION SELECT col FROM t2", "PASS", "UNION 裸列放行（豁免别名）"]
["WITH RECURSIVE cte AS (...) SELECT * FROM cte", "PASS", "递归 CTE 深度豁免"]
```
