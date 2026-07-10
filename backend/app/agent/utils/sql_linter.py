from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import re
from typing import Optional, List, Dict, Any
import sqlglot
from sqlglot.expressions import Expression

logger = logging.getLogger(__name__)

@dataclass
class LintViolation:
    rule_id: str
    severity: str
    message: str
    detail: Optional[str] = None
    fix_suggestion: Optional[str] = None
    location: Optional[dict] = None

@dataclass
class LintContext:
    table_pk_map: Dict[str, List[str]]
    table_unique_map: Dict[str, List[List[str]]]  # Supports composite unique keys
    table_grain_map: Dict[str, str]
    is_event_table: Dict[str, bool]

@dataclass
class LintResult:
    passed: bool
    errors: List[LintViolation]
    warnings: List[LintViolation]

    def format_error_message(self) -> str:
        lines = [
            "X-SQL-LINTER-STATUS: FAILED",
            "Error: SQL Linter 拦截 — 检测到以下问题：\n"
        ]
        for i, error in enumerate(self.errors, 1):
            lines.append(f"{i}. [{error.severity}] {error.rule_id}: {error.message}")
            if error.detail:
                lines.append(f"   检测到: {error.detail}")
            if error.fix_suggestion:
                lines.append(f"   修复建议: {error.fix_suggestion}\n")
        lines.append("请修正 SQL 后重试。")
        return "\n".join(lines)

class BaseLintRule(ABC):
    rule_id: str
    severity: str

    @abstractmethod
    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        pass


class SQLLinter:
    def __init__(self, rules_severity_override: dict = None, disabled_rules: set[str] = None):
        self._rules: List[BaseLintRule] = []
        self._severity_override = rules_severity_override or {}
        self._disabled_rules = disabled_rules or set()

    def register(self, rule: BaseLintRule) -> None:
        if rule.rule_id in self._disabled_rules:
            logger.info(f"SQL Linter Rule {rule.rule_id} is disabled by configuration.")
            return
        self._rules.append(rule)

    def lint(self, parsed: Expression, context: LintContext, raw_sql: Optional[str] = None) -> LintResult:
        errors: List[LintViolation] = []
        warnings: List[LintViolation] = []
        for rule in self._rules:
            try:
                if raw_sql and hasattr(rule, "check_raw_sql"):
                    violations = rule.check_raw_sql(raw_sql, context)
                elif hasattr(rule, "check_parsed_with_sql"):
                    violations = rule.check_parsed_with_sql(parsed, context, raw_sql)
                else:
                    violations = rule.check(parsed, context)
                for v in violations:
                    if v.rule_id in self._severity_override:
                        v.severity = self._severity_override[v.rule_id]
                    if v.severity == "ERROR":
                        errors.append(v)
                    elif v.severity == "WARNING":
                        warnings.append(v)
            except Exception as e:
                logger.error(f"Error running SQL linter rule {rule.rule_id}: {str(e)}", exc_info=True)
        return LintResult(passed=len(errors) == 0, errors=errors, warnings=warnings)


class DMLSecurityRule(BaseLintRule):
    rule_id = "SEC-001"
    severity = "ERROR"

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        write_nodes = (
            sqlglot.exp.Insert, sqlglot.exp.Update, sqlglot.exp.Delete, 
            sqlglot.exp.Drop, sqlglot.exp.Create, sqlglot.exp.Alter
        )
        for node in parsed.walk():
            if isinstance(node, write_nodes):
                violations.append(LintViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message="SQL 仅允许 SELECT 只读查询，禁止任何写操作 (DML/DDL)。",
                    detail=str(node),
                    fix_suggestion="删除写入或更改表结构的指令。"
                ))
                break
        return violations

class MultiStatementRule(BaseLintRule):
    rule_id = "SEC-002"
    severity = "ERROR"

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        return []

    def check_raw_sql(self, sql: str, context: LintContext) -> List[LintViolation]:
        try:
            statements = sqlglot.parse(sql, read="postgres")
            if len(statements) > 1:
                return [LintViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message="禁止执行分号拼接的多条 SQL 语句 (堆叠查询检测)。",
                    detail=sql,
                    fix_suggestion="合并查询为单条 SQL，或者拆分成独立的工具调用。"
                )]
        except Exception:
            pass
        return []

class DatabasePrefixRule(BaseLintRule):
    rule_id = "SEC-003"
    severity = "ERROR"

    def __init__(self, allowed_schemas: Optional[List[str]] = None):
        self.allowed_schemas = allowed_schemas or ["mart", "fct", "dim", "ods", "meta", "public"]

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        for table in parsed.find_all(sqlglot.exp.Table):
            # table.catalog is database name, table.db is schema name in sqlglot Table node
            if table.catalog:
                violations.append(LintViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message="禁止进行跨库限定名查询 (不得带数据库名称前缀)。",
                    detail=str(table),
                    fix_suggestion=f"移除数据库名称前缀，仅使用 schema 限定，如 '{table.db}.{table.name}' 或 '{table.name}'。"
                ))
                continue
            
            schema = table.db.lower() if table.db else "public"
            if schema not in self.allowed_schemas:
                violations.append(LintViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"禁止查询受保护的或非白名单 Schema：'{schema}'。",
                    detail=str(table),
                    fix_suggestion=f"请仅访问业务 Schema 白名单中的表: {', '.join(self.allowed_schemas)}。"
                ))
        return violations


class StarSelectRule(BaseLintRule):
    rule_id = "STR-001"
    severity = "ERROR"

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        for select in parsed.find_all(sqlglot.exp.Select):
            for projection in select.selects:
                is_star = False
                if isinstance(projection, sqlglot.exp.Star):
                    is_star = True
                elif isinstance(projection, sqlglot.exp.Column) and projection.name == "*":
                    is_star = True
                elif isinstance(projection, sqlglot.exp.Dot) and isinstance(projection.expression, sqlglot.exp.Star):
                    is_star = True
                
                if is_star:
                    violations.append(LintViolation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        message="禁止在业务查询中使用 SELECT * 或表别名通配符 (*)。",
                        detail=str(select),
                        fix_suggestion="显式声明所有需要查询的列，例如 'SELECT history_id, vehicle_id, ...'。"
                    ))
                    break
        return violations

class AliasPrefixRule(BaseLintRule):
    rule_id = "STR-002"
    severity = "ERROR"

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        has_join = any(isinstance(node, sqlglot.exp.Join) for node in parsed.walk())
        if not has_join:
            return []

        for col in parsed.find_all(sqlglot.exp.Column):
            if col.name == "*":
                continue
            if not col.table:
                violations.append(LintViolation(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    message=f"多表关联查询中，必须显式指定列的表别名前缀：'{col.name}' 缺少前缀。",
                    detail=str(col),
                    fix_suggestion=f"在列名前追加其所在的表别名前缀，如 't.{col.name}'。"
                ))
        return violations


class SubqueryDepthRule(BaseLintRule):
    rule_id = "STR-003"
    severity = "ERROR"

    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth

    def _get_max_depth(self, node: Expression) -> int:
        if isinstance(node, sqlglot.exp.CTE):
            return 0
        
        depths = [0]
        for child in node.iter_expressions():
            depths.append(self._get_max_depth(child))
        
        is_nested_select = isinstance(node, sqlglot.exp.Select) and node.parent is not None and not isinstance(node.parent, (sqlglot.exp.Subquery, sqlglot.exp.CTE))
        is_subquery_node = isinstance(node, sqlglot.exp.Subquery)
        
        current = 1 if (is_nested_select or is_subquery_node) else 0
        return current + max(depths)

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        subquery_depth = self._get_max_depth(parsed)
        if subquery_depth > self.max_depth:
            violations.append(LintViolation(
                rule_id=self.rule_id,
                severity=self.severity,
                message=f"子查询嵌套层数过深，当前嵌套深度: {subquery_depth}，最大允许深度: {self.max_depth}。",
                detail=f"嵌套深度: {subquery_depth}",
                fix_suggestion="使用公共表表达式 (CTE) 扁平化嵌套子查询结构。"
            ))
        return violations


class CteCountRule(BaseLintRule):
    rule_id = "STR-004"
    severity = "WARNING"

    def __init__(self, max_cte: int = 3):
        self.max_cte = max_cte

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        ctes = list(parsed.find_all(sqlglot.exp.CTE))
        if len(ctes) > self.max_cte:
            violations.append(LintViolation(
                rule_id=self.rule_id,
                severity=self.severity,
                message=f"CTE 语句定义过多，当前共有 {len(ctes)} 个 CTE，可能对性能和可读性有影响。",
                detail=f"CTE 数量: {len(ctes)}",
                fix_suggestion="评估是否可以减少不必要的中间视图，合并逻辑。"
            ))
        return violations


def _build_lint_context(custom_table_info: dict) -> LintContext:
    table_pk_map = {}
    table_unique_map = {}
    table_grain_map = {}
    is_event_table = {}

    for full_name, ddl in custom_table_info.items():
        clean_name = full_name.lower().strip()
        table_pk_map[clean_name] = []
        table_unique_map[clean_name] = []
        table_grain_map[clean_name] = ""
        is_event_table[clean_name] = False

        # 1. Parse Grain Comments
        grain_match = re.search(r"--\s*Grain:\s*(.*)", ddl, re.IGNORECASE)
        if grain_match:
            grain_desc = grain_match.group(1).strip()
            table_grain_map[clean_name] = grain_desc
            if any(k in grain_desc for k in ["多检", "重复", "多行", "明细", "多条"]):
                is_event_table[clean_name] = True

        # 2. Parse DDL Lines for PK and UNIQUE constraints (column level)
        for line in ddl.split("\n"):
            stripped_line = line.strip().lower()
            if "create table" in stripped_line or stripped_line.startswith("--") or not stripped_line:
                continue
            
            # Extract column name (first token)
            parts = stripped_line.split()
            if not parts or parts[0].startswith(")") or parts[0] in ("constraint", "primary", "unique"):
                continue
            col_name = parts[0].replace('"', '').replace('`', '').strip()
            
            if "primary key" in stripped_line:
                table_pk_map[clean_name].append(col_name)
                table_unique_map[clean_name].append([col_name])
            elif "unique" in stripped_line:
                table_unique_map[clean_name].append([col_name])

        # 3. Parse table level constraints (e.g. PRIMARY KEY (col1, col2) or CONSTRAINT uq UNIQUE (col1))
        pk_match = re.search(r"(?:constraint\s+\w+\s+)?primary\s+key\s*\(([^)]+)\)", ddl, re.IGNORECASE)
        if pk_match:
            cols = [c.strip().replace('"', '').replace('`', '').lower() for c in pk_match.group(1).split(",")]
            cols = [c for c in cols if c]
            if cols:
                for col in cols:
                    if col not in table_pk_map[clean_name]:
                        table_pk_map[clean_name].append(col)
                if cols not in table_unique_map[clean_name]:
                    table_unique_map[clean_name].append(cols)

        uq_matches = re.finditer(r"(?:constraint\s+\w+\s+)?unique\s*\(([^)]+)\)", ddl, re.IGNORECASE)
        for uq_match in uq_matches:
            cols = [c.strip().replace('"', '').replace('`', '').lower() for c in uq_match.group(1).split(",")]
            cols = [c for c in cols if c]
            if cols and cols not in table_unique_map[clean_name]:
                table_unique_map[clean_name].append(cols)

    return LintContext(
        table_pk_map=table_pk_map,
        table_unique_map=table_unique_map,
        table_grain_map=table_grain_map,
        is_event_table=is_event_table
    )

def _is_rule_bypassed(raw_sql: Optional[str], rule_id: str) -> bool:
    if not raw_sql:
        return False
    pattern = rf"--\s*linter-bypass:\s*(?:[^,\n]*,\s*)*{rule_id}"
    return bool(re.search(pattern, raw_sql, re.IGNORECASE))

class JoinUniquenessRule(BaseLintRule):
    rule_id = "SEM-001"
    severity = "ERROR"

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        return []

    def check_parsed_with_sql(self, parsed: Expression, context: LintContext, raw_sql: Optional[str] = None) -> List[LintViolation]:
        if _is_rule_bypassed(raw_sql, self.rule_id):
            return []

        violations = []
        joins = list(parsed.find_all(sqlglot.exp.Join))
        if not joins:
            return []

        has_aggregates = any(
            isinstance(node, (sqlglot.exp.Sum, sqlglot.exp.Avg, sqlglot.exp.Count, sqlglot.exp.Min, sqlglot.exp.Max))
            for node in parsed.walk()
        )

        for join in joins:
            on_condition = join.args.get("on")
            if not on_condition:
                continue
            
            right_table_node = join.this
            right_table_name = ""
            right_alias = ""
            
            if isinstance(right_table_node, sqlglot.exp.Table):
                right_table_name = f"{right_table_node.db + '.' if right_table_node.db else ''}{right_table_node.name}".lower().strip()
                right_alias = right_table_node.alias.lower() if right_table_node.alias else right_table_node.name.lower()
            elif isinstance(right_table_node, sqlglot.exp.Subquery):
                right_alias = right_table_node.alias.lower() if right_table_node.alias else ""
                sub_select = right_table_node.this
                if isinstance(sub_select, sqlglot.exp.Select):
                    if sub_select.args.get("group") or sub_select.args.get("distinct"):
                        continue

            right_join_cols = set()
            for col in on_condition.find_all(sqlglot.exp.Column):
                col_table = col.table.lower() if col.table else ""
                if col_table == right_alias or (not col_table and right_alias == ""):
                    right_join_cols.add(col.name.lower())

            right_safe = False
            if right_table_name in context.table_unique_map:
                for u_set in context.table_unique_map[right_table_name]:
                    if set(u_set).issubset(right_join_cols):
                        right_safe = True
                        break

            if not right_safe:
                if self._is_max_min_subquery_filter(on_condition, right_alias, right_join_cols):
                    right_safe = True
                elif self._is_rownumber_one_filter(on_condition, right_table_node, right_alias):
                    right_safe = True
                elif self._is_limit_one_subquery(right_table_node):
                    right_safe = True

            if not right_safe:
                severity = self.severity if has_aggregates else "WARNING"
                violations.append(LintViolation(
                    rule_id=self.rule_id,
                    severity=severity,
                    message="JOIN 关联列不满足唯一性约束，存在数据扇出 (Fan-out) 膨胀风险。",
                    detail=f"JOIN ON {str(on_condition)}",
                    fix_suggestion="对多的一侧表使用子查询先进行 GROUP BY 聚合，或为 JOIN ON 条件补充完整的主键对。"
                ))

        return violations

    def _is_max_min_subquery_filter(self, on_condition: Expression, right_alias: str, join_cols_right: set) -> bool:
        for eq in on_condition.find_all(sqlglot.exp.EQ):
            left, right = eq.left, eq.right
            target_col = None
            subquery_node = None
            
            if isinstance(left, sqlglot.exp.Column) and left.table.lower() == right_alias:
                target_col = left
                subquery_node = right
            elif isinstance(right, sqlglot.exp.Column) and right.table.lower() == right_alias:
                target_col = right
                subquery_node = left
                
            if not target_col or not subquery_node:
                continue
                
            if isinstance(subquery_node, sqlglot.exp.Subquery):
                subquery_node = subquery_node.this
                
            if not isinstance(subquery_node, sqlglot.exp.Select):
                continue
                
            has_extreme = False
            for proj in subquery_node.selects:
                extreme_func = proj.find(sqlglot.exp.Max) or proj.find(sqlglot.exp.Min)
                if extreme_func:
                    arg_col = extreme_func.find(sqlglot.exp.Column)
                    if arg_col and arg_col.name.lower() == target_col.name.lower():
                        has_extreme = True
                        break
                        
            if not has_extreme:
                continue
                
            where_clause = subquery_node.args.get("where")
            if where_clause:
                for sub_eq in where_clause.find_all(sqlglot.exp.EQ):
                    sub_l, sub_r = sub_eq.left, sub_eq.right
                    for c in [sub_l, sub_r]:
                        if isinstance(c, sqlglot.exp.Column) and c.name.lower() in join_cols_right:
                            return True
        return False

    def _is_rownumber_one_filter(self, on_condition: Expression, right_table_node: Expression, right_alias: str) -> bool:
        if not isinstance(right_table_node, sqlglot.exp.Subquery):
            return False
        sub_select = right_table_node.this
        if not isinstance(sub_select, sqlglot.exp.Select):
            return False

        # 找到被命名的 ROW_NUMBER() 别名
        rn_aliases = []
        for proj in sub_select.selects:
            if isinstance(proj, sqlglot.exp.Alias):
                # 检查 projection 中是否含有 row_number() 匿名函数或窗口函数
                if any(isinstance(n, sqlglot.exp.RowNumber) or (isinstance(n, sqlglot.exp.Anonymous) and n.name.lower() == "row_number") for n in proj.walk()):
                    rn_aliases.append(proj.alias.lower())

        if not rn_aliases:
            return False

        # 检查外层 ON 条件中，该别名是否被过滤为 = 1
        for eq in on_condition.find_all(sqlglot.exp.EQ):
            l, r = eq.left, eq.right
            for alias_name in rn_aliases:
                if (isinstance(l, sqlglot.exp.Column) and l.name.lower() == alias_name and l.table.lower() == right_alias and str(r) == "1") or \
                   (isinstance(r, sqlglot.exp.Column) and r.name.lower() == alias_name and r.table.lower() == right_alias and str(l) == "1"):
                    return True
        return False

    def _is_limit_one_subquery(self, right_table_node: Expression) -> bool:
        if not isinstance(right_table_node, sqlglot.exp.Subquery):
            return False
        sub_select = right_table_node.this
        if not isinstance(sub_select, sqlglot.exp.Select):
            return False
        
        limit_node = sub_select.args.get("limit")
        if limit_node and str(limit_node.expression) == "1":
            return True
        return False

class CountDistinctRule(BaseLintRule):
    rule_id = "SEM-002"
    severity = "WARNING"

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        return []

    def check_parsed_with_sql(self, parsed: Expression, context: LintContext, raw_sql: Optional[str] = None) -> List[LintViolation]:
        if _is_rule_bypassed(raw_sql, self.rule_id):
            return []

        violations = []
        for select in parsed.find_all(sqlglot.exp.Select):
            if select.args.get("group"):
                continue

            table_node = select.find(sqlglot.exp.Table)
            if not table_node:
                continue
            table_name = f"{table_node.db + '.' if table_node.db else ''}{table_node.name}".lower().strip()
            
            if context.is_event_table.get(table_name, False):
                for count in select.find_all(sqlglot.exp.Count):
                    ancestor = count.find_ancestor(sqlglot.exp.Select)
                    if ancestor == select and not count.args.get("distinct"):
                        violations.append(LintViolation(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"在事件明细表 '{table_name}' 上直接执行非去重计数 (COUNT)，可能导致实体数翻倍偏大。",
                            detail=str(count),
                            fix_suggestion="如果需要统计车辆数，请使用 COUNT(DISTINCT vehicle_id) 代替 COUNT(*)。"
                        ))
        return violations

class ScalarSubqueryRule(BaseLintRule):
    rule_id = "SEM-003"
    severity = "WARNING"

    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        for sub in parsed.find_all(sqlglot.exp.Subquery):
            # 过滤掉作为 FROM 或 JOIN 数据源的表子查询
            is_table_subquery = False
            curr = sub
            while curr.parent:
                if isinstance(curr.parent, (sqlglot.exp.From, sqlglot.exp.Join)):
                    if curr.parent.this == curr:
                        is_table_subquery = True
                        break
                curr = curr.parent
            if is_table_subquery:
                continue

            sub_select = sub.this
            if isinstance(sub_select, sqlglot.exp.Select):
                has_limit = sub_select.args.get("limit") is not None
                has_aggregates = any(
                    isinstance(node, (sqlglot.exp.Sum, sqlglot.exp.Avg, sqlglot.exp.Count, sqlglot.exp.Min, sqlglot.exp.Max))
                    for node in sub_select.walk()
                )
                if not (has_limit or has_aggregates):
                    violations.append(LintViolation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        message="标量子查询可能返回多行数据，导致 SQL 运行时崩溃错误。",
                        detail=str(sub),
                        fix_suggestion="在子查询尾部添加 LIMIT 1，或在子查询中使用聚合函数（如 MAX, MIN）。"
                    ))
        return violations

class NotInSubqueryRule(BaseLintRule):
    rule_id = "SEM-004"
    severity = "ERROR"
    def check(self, parsed: Expression, context: LintContext) -> List[LintViolation]:
        violations = []
        for in_node in parsed.find_all(sqlglot.exp.In):
            is_not_in = in_node.args.get("is_not", False) or (in_node.parent and isinstance(in_node.parent, sqlglot.exp.Not))
            if is_not_in:
                query_node = in_node.args.get("query")
                if isinstance(query_node, (sqlglot.exp.Select, sqlglot.exp.Subquery)):
                    violations.append(LintViolation(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        message="禁止使用 NOT IN 子查询，防范 NULL 值穿透导致返回空集的逻辑漏洞。",
                        detail=str(in_node.parent if isinstance(in_node.parent, sqlglot.exp.Not) else in_node),
                        fix_suggestion="请将 NOT IN 改写为等价的 NOT EXISTS 存在性查询。"
                    ))
        return violations
