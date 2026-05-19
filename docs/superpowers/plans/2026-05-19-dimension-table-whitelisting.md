# Dimension Table Whitelisting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a dynamic SQL truncation bypass for dimension tables using AST parsing to prevent fuzzy-matching dictionary data from being truncated.

**Architecture:** We add environment variables for a dimension table whitelist and a lenient truncation limit. `config.py` parses the whitelist into a set. `sql_tools.py` intercepts queries before truncation, extracts all tables using `sqlglot` AST parsing, and if the query only involves whitelisted dimension tables, it applies the lenient limit instead of the strict limit.

**Tech Stack:** Python, Pydantic, sqlglot

---

### Task 1: Environment and Configuration Setup

**Files:**
- Modify: `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\.env`
- Modify: `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\backend\app\config.py`

- [ ] **Step 1: Add configuration to `.env`**
Add the dimension table configuration underneath the `SQL_RESULT_HARD_LIMIT` configuration in `.env`.

```env
# 维度表/字典表白名单，免受严格的 SQL_RESULT_HARD_LIMIT 约束
DIMENSION_TABLES='process_areas,car_models,colors'
# 纯维度表查询时的宽松硬截断上限
DIMENSION_RESULT_HARD_LIMIT='300'
```

- [ ] **Step 2: Update `Settings` class in `config.py`**
In `config.py`, locate `sql_result_preview_rows` and append the new configurations.

```python
    # 纯维度表查询时的宽松截断上限
    dimension_result_hard_limit: int = int(os.getenv("DIMENSION_RESULT_HARD_LIMIT", "300"))
    
    # 维度表/字典表白名单
    dimension_tables_raw: str = os.getenv("DIMENSION_TABLES", "")
    
    @property
    def dimension_tables(self) -> set[str]:
        if not self.dimension_tables_raw:
            return set()
        return {t.strip().lower() for t in self.dimension_tables_raw.split(",") if t.strip()}
```

- [ ] **Step 3: Commit**
```bash
git add .env backend/app/config.py
git commit -m "feat: add dimension table configuration"
```


### Task 2: Implement AST Table Extraction

**Files:**
- Modify: `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\backend\app\agent\tools\sql_tools.py`

- [ ] **Step 1: Import sqlglot**
At the top of the file, add `import sqlglot` after the standard library imports.

```python
import sqlglot
```

- [ ] **Step 2: Add extraction functions**
Right after `FORBIDDEN_SQL_PATTERN`, add the two AST functions.

```python
def _extract_table_names(query: str) -> set[str]:
    """
    使用 sqlglot AST 精确提取 SQL 中涉及的所有表名。
    能正确处理：CTE、子查询、多表 JOIN、schema 限定名（schema.table）、表别名等。
    """
    try:
        tables = set()
        parsed = sqlglot.parse_one(query, error_level=sqlglot.ErrorLevel.IGNORE)
        for table in parsed.find_all(sqlglot.exp.Table):
            tables.add(table.name.lower())
        return tables
    except Exception:
        # AST 解析失败时回退到保守策略：按事实表查询处理，使用严格截断
        return set()

def _is_pure_dimension_query(query: str) -> bool:
    """
    判断当前查询是否仅涉及维度表/字典表（不含任何事实表）。
    基于 sqlglot AST 精确提取所有涉及的表名后与白名单比对。
    """
    involved_tables = _extract_table_names(query)
    if not involved_tables:
        # 解析失败或空查询，回退到保守策略（严格截断）
        return False

    dim_whitelist = settings.dimension_tables
    if not dim_whitelist:
        return False

    # 只有当所有涉及的表都在维度白名单内，才算纯维度查询
    return involved_tables.issubset(dim_whitelist)
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/agent/tools/sql_tools.py
git commit -m "feat: add AST-based dimension table detection"
```


### Task 3: Apply Dynamic Truncation Limit

**Files:**
- Modify: `f:\000_dev\Python\workplace\rearch_agent\.tree\features\agent\backend\app\agent\tools\sql_tools.py`

- [ ] **Step 1: Replace hard limit logic**
Locate the `sql_db_query` function (inside `create_wrapped_query_tool`). Find the comment `5. 智能结果限流：防止数据库返回结果过大撑爆 LLM 上下文`.
Replace the static `hard_limit` lookup with the dynamic logic.

Change:
```python
        # 5. 智能结果限流：防止数据库返回结果过大撑爆 LLM 上下文
        hard_limit = settings.sql_result_hard_limit       # 获取系统硬限制（如 1000 行），若超过则截断
```

To:
```python
        # 5. 智能结果限流：防止数据库返回结果过大撑爆 LLM 上下文
        is_dim = _is_pure_dimension_query(query)
        hard_limit = (
            settings.dimension_result_hard_limit if is_dim else settings.sql_result_hard_limit
        )
```

- [ ] **Step 2: Check formatting and commit**
The rest of the truncation logic will automatically use the new `hard_limit`.
```bash
git add backend/app/agent/tools/sql_tools.py
git commit -m "feat: apply dynamic hard limit based on AST evaluation"
```
