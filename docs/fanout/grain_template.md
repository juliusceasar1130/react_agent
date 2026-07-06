# 表粒度标注规范 (Grain Annotation)

> 记录时间: 2026-07-06 Asia/Shanghai
> 相关讨论: DDL 注入粒度标注 — P1 实施

---

## 模板格式

```sql
COMMENT ON TABLE {schema}.{table_name} IS 
'Grain:{每行代表的业务含义,含唯一性说明},{潜在风险提示,可选}';
```

**解析规则**（`db_utils.py` 的 `_parse_grain_info` 函数）：
- 注释以 `Grain:` 开头 → 结构化渲染
- `Grain:` 后第一个逗号前的部分 → `-- Grain:` 粒度描述
- 逗号后的部分 → `-- ⚠️` 警告行
- 无 `Grain:` 前缀 → 走原 `-- Description:` 渲染

---

## 表分类与示例

### 1. 流水/事实表（Fact Table）

**特征**：无唯一键、PK 不是业务实体键、同一实体键可能出现多行

```sql
COMMENT ON TABLE mart.mart_vehicle_quality_360 IS 
'Grain:一次检测事件(history_id),vehicle_id可能重复,统计车数需用COUNT(DISTINCT vehicle_id)';

COMMENT ON TABLE fct.fct_vehicle_defect_detection IS 
'Grain:一次缺陷检测记录(history_id),同一vehicle_id可有多条';
```

### 2. 快照表（Snapshot Table）

**特征**：每个实体当前状态的快照，实体键唯一

```sql
COMMENT ON TABLE fct.fct_vehicle_position_current IS 
'Grain:车辆当前位置快照,vehicle_id唯一(一车一行),JOIN安全';

COMMENT ON TABLE mart.mart_position_current_overview IS 
'Grain:工位概览快照,position_id唯一,JOIN安全';
```

### 3. 维度表（Dimension Table）

**特征**：字典/档案类，PK 唯一，JOIN 永远安全

```sql
COMMENT ON TABLE dim.dim_vehicle_profile IS 
'Grain:车辆基础档案(vehicle_id唯一),维度表JOIN安全';

COMMENT ON TABLE dim.dim_process_area IS 
'Grain:工位字典(process_area_name唯一),维度表JOIN安全';

COMMENT ON TABLE dim.carbody_registry IS 
'Grain:车身注册记录(vehicle_id唯一),维度表JOIN安全';
```

### 4. 异常/聚合表

```sql
COMMENT ON TABLE fct.fct_abnormal_vehicle_current IS 
'Grain:异常车辆当前位置(position_id唯一)';

COMMENT ON TABLE mart.mart_abnormal_vehicle_current IS 
'Grain:异常车辆聚合概览(position_id唯一)';
```

---

## DDL 渲染效果

设置注释后，`db_utils.py` 自动输出：

```sql
-- Table: mart_vehicle_quality_360
-- Grain: 一次检测事件(history_id)
-- ⚠️ vehicle_id可能重复,统计车数需用COUNT(DISTINCT vehicle_id)
CREATE TABLE mart_vehicle_quality_360 (
  history_id VARCHAR,
  vehicle_id VARCHAR,
  ...
);

-- Table: fct_vehicle_position_current
-- Grain: 车辆当前位置快照,vehicle_id唯一(一车一行),JOIN安全
CREATE TABLE fct_vehicle_position_current (
  vehicle_id TEXT UNIQUE,    -- 来自唯一索引反射
  ...
);
```

LLM 看到 `-- Grain:` 和 `-- ⚠️` 后，会自动理解表的数据含义和聚合风险，减少 `COUNT(*)` 误用。

---

## 实施要求

- **必须**：`Grain:` 放在注释开头，否则走普通 `-- Description:` 渲染
- **推荐**：逗号分隔粒度和风险提示（中英文逗号均可）
- **修改**：再次执行 `COMMENT ON TABLE` 即覆盖，无需改代码
- **新增表**：建表后立即添加 `COMMENT ON TABLE`，保持数据库文档同步

## 代码实现

| 文件 | 函数 | 作用 |
|---|---|---|
| `backend/app/agent/utils/db_utils.py` | `_parse_grain_info()` | 解析 `Grain:` 注释，返回 `(grain_desc, warnings)` |
| `backend/app/agent/utils/db_utils.py` | `_process_single_table()` | 调用解析函数，渲染为 `-- Grain:` + `-- ⚠️` |
