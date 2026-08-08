# Phase 2: 安全与占位符修补 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 彻底消除 SQL 模板文件中的 `-- {placeholder}` 注释穿透漏洞，并将参数化 `sql_fragment` 统一修补为 SQLAlchemy 安全命名变量绑定 `:param_name` 格式。

**Architecture:** 排查与修复 `vehicle_historical_trace`、`daily_area_body_count` 和 `abnormal_vehicle_monitor` 三个场景的 `sql/main.sql` 文件，移除 `{placeholder}` 占位符行的 `--` 注释前缀；更新其 `scenario.py` 中对应的 `sql_fragment` 字段从字符串插值改为 `:param_name` 命名绑定。

**Tech Stack:** SQL (PostgreSQL), Python 3.12, SQLAlchemy Expression Language / Named Parameter Binding.

---

### User Review Required

> [!IMPORTANT]
> **全表扫描漏过滤防护**：在现有 SQL 模板中，若占位符写为 `-- {placeholder}`，一旦经 `executor.py` 替换为片段（例如 `-- AND BODY_ID = :vehicle_id`），SQL 引擎会将该条件判定为注释，从而造成 WHERE 过滤失效并引发全表扫描。本阶段修改将彻底屏蔽该隐患。

---

### Proposed Changes & File Mapping

#### SQL Templates

##### [MODIFY] [main.sql (vehicle_historical_trace)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/vehicle_historical_trace/sql/main.sql)
- 第 7 行：将 `-- {vehicle_id}` 修改为 `{vehicle_id}`

##### [MODIFY] [main.sql (daily_area_body_count)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/daily_area_body_count/sql/main.sql)
- 第 6 行：将 `-- {date_filter}` 修改为 `{date_filter}`

##### [MODIFY] [main.sql (abnormal_vehicle_monitor)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/abnormal_vehicle_monitor/sql/main.sql)
- 第 10 行：将 `-- {abnormal_type}` 修改为 `{abnormal_type}`

#### Scenario Definitions

##### [MODIFY] [scenario.py (vehicle_historical_trace)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/vehicle_historical_trace/scenario.py)
- 更新 `vehicle_id` 参数的 `sql_fragment` 为 `"AND BODY_ID = :vehicle_id"`

##### [MODIFY] [scenario.py (daily_area_body_count)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/daily_area_body_count/scenario.py)
- 更新 `date_filter` 参数的 `sql_fragment` 为 `'AND DATE("DATE_EVT") = :date_filter'`

##### [MODIFY] [scenario.py (abnormal_vehicle_monitor)](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/abnormal_vehicle_monitor/scenario.py)
- 更新 `abnormal_type` 参数的 `sql_fragment` 为 `"AND abnormal_type = :abnormal_type"`

---

## Detailed Task Breakdown

### Task 1: 修补 `vehicle_historical_trace` SQL 模板与命名参数绑定

**Files:**
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/vehicle_historical_trace/sql/main.sql`
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/vehicle_historical_trace/scenario.py`

- [ ] **Step 1: 移除 `vehicle_historical_trace/sql/main.sql` 第 7 行的 `--` 注释前缀**

在 `vehicle_historical_trace/sql/main.sql` 中将第 7 行修改为：
```sql
SELECT 
    "DATE_EVT",
    "RW_STATION_ID",
    "BODY_ID"
FROM ods.carbody_history
WHERE 1=1
{vehicle_id}
ORDER BY "DATE_EVT" ASC;
```

- [ ] **Step 2: 更新 `vehicle_historical_trace/scenario.py` 的 `sql_fragment`**

在 `vehicle_historical_trace/scenario.py` 中更新 `vehicle_id` 的 `sql_fragment` 属性：
```python
"sql_fragment": "AND BODY_ID = :vehicle_id",
```

- [ ] **Step 3: 验证该场景参数渲染与表达式语法**

运行 Python 验证测试：
```bash
python -c "from backend.app.skills.registry import reload_skills; reload_skills(); from backend.app.skills.direct_path.executor import build_scenario_sql; sql, params = build_scenario_sql('paint_shop_vehicle_logistics', 'vehicle_historical_trace', 'main', {'vehicle_id': '78202600000001'}); print(sql); print(params)"
```
Expected output:
```text
SELECT 
    "DATE_EVT",
    "RW_STATION_ID",
    "BODY_ID"
FROM ods.carbody_history
WHERE 1=1
    AND BODY_ID = :vehicle_id
ORDER BY "DATE_EVT" ASC;
{'vehicle_id': '78202600000001'}
```

---

### Task 2: 修补 `daily_area_body_count` SQL 模板与命名参数绑定

**Files:**
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/daily_area_body_count/sql/main.sql`
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/daily_area_body_count/scenario.py`

- [ ] **Step 1: 移除 `daily_area_body_count/sql/main.sql` 第 6 行的 `--` 注释前缀**

在 `daily_area_body_count/sql/main.sql` 中将第 6 行修改为：
```sql
SELECT 
    h."RW_STATION_ID" as station_id,
    COUNT(DISTINCT h."BODY_ID") AS throughput_count
FROM ods.carbody_history h
WHERE 1=1
{date_filter}
GROUP BY h."RW_STATION_ID"
ORDER BY throughput_count DESC;
```

- [ ] **Step 2: 更新 `daily_area_body_count/scenario.py` 的 `sql_fragment`**

在 `daily_area_body_count/scenario.py` 中更新 `date_filter` 的 `sql_fragment` 属性：
```python
"sql_fragment": 'AND DATE("DATE_EVT") = :date_filter',
```

- [ ] **Step 3: 验证 SQL 构建**

运行 Python 测试命令：
```bash
python -c "from backend.app.skills.registry import reload_skills; reload_skills(); from backend.app.skills.direct_path.executor import build_scenario_sql; sql, params = build_scenario_sql('paint_shop_vehicle_logistics', 'daily_area_body_count', 'main', {'date_filter': '2026-05-12'}); print(sql); print(params)"
```
Expected output: 包含 `AND DATE("DATE_EVT") = :date_filter` 且无 `--` 注释阻挡。

---

### Task 3: 修补 `abnormal_vehicle_monitor` SQL 模板与命名参数绑定

**Files:**
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/abnormal_vehicle_monitor/sql/main.sql`
- Modify: `backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/abnormal_vehicle_monitor/scenario.py`

- [ ] **Step 1: 移除 `abnormal_vehicle_monitor/sql/main.sql` 第 10 行的 `--` 注释前缀**

在 `abnormal_vehicle_monitor/sql/main.sql` 中修改为：
```sql
SELECT 
    carrier_id,
    process_area,
    abnormal_type,
    abnormal_reason,
    vehicle_id,
    vehicle_updated_at
FROM mart.mart_abnormal_vehicle_current
WHERE 1=1
{abnormal_type}
ORDER BY process_area, abnormal_type;
```

- [ ] **Step 2: 更新 `abnormal_vehicle_monitor/scenario.py` 的 `sql_fragment`**

在 `abnormal_vehicle_monitor/scenario.py` 中更新 `abnormal_type` 的 `sql_fragment` 属性：
```python
"sql_fragment": "AND abnormal_type = :abnormal_type",
```

- [ ] **Step 3: 验证 SQL 构建**

运行 Python 测试命令：
```bash
python -c "from backend.app.skills.registry import reload_skills; reload_skills(); from backend.app.skills.direct_path.executor import build_scenario_sql; sql, params = build_scenario_sql('paint_shop_vehicle_logistics', 'abnormal_vehicle_monitor', 'main', {'abnormal_type': 'non_product_prefix'}); print(sql); print(params)"
```
Expected output: 包含 `AND abnormal_type = :abnormal_type` 且无 `--` 注释。

---

## Verification Plan

### Automated Verification
1. 运行全局资产校验：
   ```bash
   python backend/app/skills/domains/verify_assets.py
   ```
2. 运行所有修补场景的 SQL 构建单元测试：
   ```bash
   conda run -n py312_agent python -c "from backend.app.skills.registry import reload_skills; reload_skills(); from backend.app.skills.direct_path.executor import build_scenario_sql; print('1:', build_scenario_sql('paint_shop_vehicle_logistics', 'vehicle_historical_trace', 'main', {'vehicle_id': '78202600000001'})[0]); print('2:', build_scenario_sql('paint_shop_vehicle_logistics', 'daily_area_body_count', 'main', {'date_filter': '2026-05-12'})[0]); print('3:', build_scenario_sql('paint_shop_vehicle_logistics', 'abnormal_vehicle_monitor', 'main', {'abnormal_type': 'empty_vehicle_id'})[0])"
   ```
   预期输出：所有替换后的表达式中包含正确的 `:param` 条件，且无行开头的 `-- AND` 注释现象。
