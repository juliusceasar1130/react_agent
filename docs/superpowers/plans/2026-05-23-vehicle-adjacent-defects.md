# vehicle_adjacent_defects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a new scenario skill `vehicle_adjacent_defects` to query cars adjacent to a target car at a specific station and fetch their closest defect records.

**Architecture:** A new directory `vehicle_adjacent_defects` will be created inside the existing `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/` directory containing a configuration (`scenario.py`) and a complex SQL template (`sql/main.sql`).

**Tech Stack:** Python, PostgreSQL, SQL.

---

### Task 1: Create Scenario Metadata and SQL Template

**Files:**
- Create: `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/scenario.py`
- Create: `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/sql/main.sql`

- [ ] **Step 1: Write SQL template**

Create `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/sql/main.sql` with the following content:

```sql
WITH target_event AS (
    SELECT "BODY_ID", "DATE_EVT"
    FROM ods.carbody_history
    WHERE "BODY_ID" = '{{vehicle_id}}' 
      AND "RW_STATION_ID" = '{{station_id}}'
    ORDER BY "DATE_EVT" DESC
    LIMIT 1
),
adjacent_events AS (
    SELECT "BODY_ID", "DATE_EVT", 'target' AS car_role
    FROM target_event
    UNION ALL
    SELECT "BODY_ID", "DATE_EVT", 'before' AS car_role
    FROM (
        SELECT "BODY_ID", "DATE_EVT"
        FROM ods.carbody_history
        WHERE "RW_STATION_ID" = '{{station_id}}'
          AND "DATE_EVT" < (SELECT "DATE_EVT" FROM target_event)
        ORDER BY "DATE_EVT" DESC
        LIMIT {{n_adjacent}}
    ) b
    UNION ALL
    SELECT "BODY_ID", "DATE_EVT", 'after' AS car_role
    FROM (
        SELECT "BODY_ID", "DATE_EVT"
        FROM ods.carbody_history
        WHERE "RW_STATION_ID" = '{{station_id}}'
          AND "DATE_EVT" > (SELECT "DATE_EVT" FROM target_event)
        ORDER BY "DATE_EVT" ASC
        LIMIT {{n_adjacent}}
    ) a
),
defect_matches AS (
    SELECT 
        a.car_role,
        a."BODY_ID",
        a."DATE_EVT" AS pass_time,
        d.detect_time,
        ABS(EXTRACT(EPOCH FROM (d.detect_time - a."DATE_EVT"))) AS time_diff_sec,
        d.station_1_defect_count,
        d.station_2_defect_count,
        d.station_3_defect_count,
        d.station_4_defect_count,
        d.station_5_defect_count,
        ROW_NUMBER() OVER(PARTITION BY a."BODY_ID" ORDER BY ABS(EXTRACT(EPOCH FROM (d.detect_time - a."DATE_EVT"))) ASC) as rn
    FROM adjacent_events a
    LEFT JOIN fct.fct_vehicle_defect_enriched d 
      ON a."BODY_ID" = d.vehicle_id
)
SELECT 
    car_role,
    "BODY_ID",
    pass_time,
    detect_time,
    time_diff_sec,
    station_1_defect_count,
    station_2_defect_count,
    station_3_defect_count,
    station_4_defect_count,
    station_5_defect_count
FROM defect_matches
WHERE rn = 1
ORDER BY pass_time ASC;
```

- [ ] **Step 2: Write scenario metadata**

Create `backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects/scenario.py` with the following content:

```python
"""
前后车身缺陷追溯场景元数据。

修改时间: 2026-05-23 Asia/Shanghai
主要修改内容:
- 新增前后车身缺陷追溯场景
"""

SCENARIO = {
    "skill_name": "paint_shop_defect_analysis",
    "name": "vehicle_adjacent_defects",
    "title": "前后车身缺陷追溯",
    "description": "基于车身号和指定读写站，查询该点前后通过的 N 辆车，并匹配每辆车与过点时间最接近的一条缺陷检测记录。",
    "example_questions": [
        "帮我查一下车身 78202612345678 在工位 STATION_A 过点时，前后的车有没有缺陷",
        "查询这辆车和它前后一辆车的缺陷记录"
    ],
    "triggers": [
        "前后车身缺陷",
        "相邻车辆缺陷",
        "前后车"
    ],
    "intent_keywords": [
        "前后",
        "相邻",
        "车身",
        "缺陷",
        "最近"
    ],
    "required_inputs": ["vehicle_id", "station_id"],
    "optional_inputs": ["n_adjacent"],
    "parameters": {
        "vehicle_id": {
            "type": "string",
            "description": "车身唯一标识 ID",
            "required": True,
            "source_column": "BODY_ID",
            "source_table": "ods.carbody_history"
        },
        "station_id": {
            "type": "string",
            "description": "过点读写站 ID",
            "required": True,
            "source_column": "RW_STATION_ID",
            "source_table": "ods.carbody_history"
        },
        "n_adjacent": {
            "type": "integer",
            "description": "前后相邻查询车辆的数量",
            "required": False,
            "default": 1
        }
    },
    "workflow": [
        "确认用户提供了具体的 vehicle_id。",
        "如果用户未提供 station_id，建议先使用单车历史轨迹追溯查询车辆经过的读写站，引导用户选择一个。",
        "将 n_adjacent 默认设置为 1（即前1辆和后1辆）。",
        "执行查询并返回前后车的缺陷数量记录。"
    ],
    "rules": [
        "必须确保 `station_id` 有值才能进行本查询。",
        "结果保留无缺陷检测记录的过点车辆，且明确标记 target/before/after 角色。"
    ],
    "gotchas": [],
    "output_contract": "输出字段必须包含 car_role, BODY_ID, pass_time 以及缺陷统计数量列。",
    "sql_template_refs": [
        {
            "type": "sql",
            "name": "main",
            "scope": "scenario",
            "path": "sql/main.sql",
            "description": "查询前后相邻车辆最近缺陷记录的 SQL 模板。"
        }
    ],
    "script_refs": [],
}
```

- [ ] **Step 3: Commit files**

```bash
git add backend/app/skills/domains/paint_shop_defect_analysis/scenarios/vehicle_adjacent_defects
git commit -m "feat(skill): add vehicle_adjacent_defects scenario"
```
