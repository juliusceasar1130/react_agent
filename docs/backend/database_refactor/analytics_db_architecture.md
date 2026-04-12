# Analytics DB 落地与刷新操作手册（最新已验证版）

修改时间：2026-04-11 Asia/Shanghai

主要修改内容：
- 将旧版 `analytics_db` 架构图文档重写为可直接执行的落地与刷新操作手册
- 修正旧版流程中遗漏 `dim` 刷新、`meta.refresh_watermark` 更新、刷新口径错误等问题
- 以当前数据库中已经验证成功的对象结构为准，统一后续执行口径
- 补充当前 `fct_vehicle_position_current` 对异常车与重复调试车场景的局限说明
- 补充下一阶段“正式产品车 / 异常车 / 全量占位”分层优化入口
- 将“当前车辆事实分层优化”第一阶段落地结果同步到手册
- 补充 `fct_position_current_all`、`fct_abnormal_vehicle_current`、`mart_abnormal_vehicle_current` 与 `dim_vehicle_profile.current_*` 最新对象说明
- 补充 `mart_position_current_overview` 当前现场总览对象与对应刷新、验证口径

## 1. 适用范围

本手册面向当前项目的 `analytics_db` 分析库建设与后续刷新维护。

当前项目涉及的两个业务源库：

- `rollerbed_tracking_db`
- `defect_db`

当前分析库策略：

- 在 PostgreSQL 中独立建设 `analytics_db`
- 通过 `postgres_fdw` 挂载两个源库
- 将源表数据同步到本地 `ods` 表
- 在 `fct` / `mart` 中生成给 Agent 使用的分析对象

## 2. 当前已验证的最新状态

截至 2026-04-11，数据库中已经验证存在以下对象：

- 数据库：
  - `analytics_db`
- schema：
  - `src_rb`
  - `src_defect`
  - `ods`
  - `dim`
  - `fct`
  - `mart`
  - `meta`
- `ods` 表：
  - `rb_position_data`
  - `process_areas`
  - `carrier_types`
  - `vehicle_body_types`
  - `vehicle_color_codes`
  - `vehicle_platforms`
  - `history_station_defect_summary`
- `dim` 表：
  - `dim_process_area`
  - `dim_vehicle_profile`
- `fct` 物化视图：
  - `fct_position_current_all`
  - `fct_abnormal_vehicle_current`
  - `fct_vehicle_position_current`
  - `fct_vehicle_defect_detection`
- `mart` 物化视图：
  - `mart_abnormal_vehicle_current`
  - `mart_position_current_overview`
  - `mart_vehicle_quality_360`
- `meta` 表：
  - `sync_job_log`
  - `refresh_watermark`
- 刷新过程：
  - `meta.refresh_analytics_all()`
- 只读角色：
  - `agent_ro`

本手册以下内容，以这套已验证状态为准。

当次校验样例（2026-04-11）：

- `ods.rb_position_data`：`520`
- `ods.history_station_defect_summary`：`60370`
- `fct.fct_position_current_all`：`114`
- `fct.fct_vehicle_position_current`：`102`
- `fct.fct_abnormal_vehicle_current`：`12`
- `mart.mart_vehicle_quality_360`：`60370`
- `mart.mart_abnormal_vehicle_current`：`12`
- `mart.mart_position_current_overview`：`114`

## 3. 旧版流程中已修正的错误

旧版流程有几处容易误导后续执行，现统一修正如下：

1. `meta.refresh_analytics_all()` 旧版只刷新 `ods` 与物化视图，没有刷新 `dim` 表。
2. 当前正式版本的刷新过程会同时重建：
   - `dim.dim_process_area`
   - `dim.dim_vehicle_profile`
   - `meta.refresh_watermark`
3. 当前刷新机制是“全量刷新”，不是增量刷新。
4. `mart.mart_vehicle_quality_360` 当前关联的是：
   - 缺陷检测记录
   - 车辆当前最新位置
   不是“检测当时位置”。
5. 当前 `fct.fct_vehicle_position_current` 已明确收敛为“正式产品车当前事实”。
6. 当前异常车与全量当前占位已分别由：
   - `fct.fct_position_current_all`
   - `fct.fct_abnormal_vehicle_current`
   - `mart.mart_abnormal_vehicle_current`
   承接。
7. 当前 `dim.dim_vehicle_profile` 已补充 `current_*` 字段，用于保留正式产品车的当前绑定快照。

## 3.1 当前已知限制

当前数据库结构已经完成第一阶段分层优化，但仍有两个需要明确的边界：

1. `fct.fct_vehicle_position_current` 现在只面向正式产品车。  
   它已经按 `vehicle_id LIKE '782026%'`、`body_type <> '-----'`、`carrier_id <> '0'` 收窄，不应再拿它回答“全部当前占位”问题。
2. `mart.mart_vehicle_quality_360` 仍然关联的是：
   - 一次缺陷检测
   - 该车当前最新位置  
   它不是“检测当时位置”的严格还原口径。

当前已经通过新增对象修正了异常车与重复调试 `vehicle_id` 的主要问题：

- `fct.fct_position_current_all`
- `fct.fct_abnormal_vehicle_current`
- `mart.mart_abnormal_vehicle_current`

下一阶段如果还要继续增强，重点会转向：

- `mart_position_current_overview`
- 位置历史快照层
- 检测时位置或停留时长关联分析

详细方案见：

- [current_vehicle_fact_refactor.md](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/docs/backend/database_refactor/current_vehicle_fact_refactor.md)

## 4. 前置确认

首次搭建前，请先确认源表已存在：

- `rollerbed_tracking_db` 中的基础表来自：
  - [create_tables_postgresql.sql](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/tracking_database/create_tables_postgresql.sql)
- `defect_db` 中需要先存在：
  - `history_station_defect_summary`
- 缺陷汇总表说明文档：
  - [history_station_defect_summary_schema.md](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/defect_database/history_station_defect_summary_schema.md)

默认 PostgreSQL 环境：

- 主机：`localhost`
- 端口：`5432`
- 管理员：`root`
- 密码：`root`

## 5. 一次性初始化流程

这一部分只在首次搭建或重建 `analytics_db` 时执行。

### 5.1 检查 `analytics_db` 是否已存在

先连接到 `postgres` 库或任意管理工具，执行：

```sql
SELECT datname
FROM pg_database
WHERE datname = 'analytics_db';
```

如果已经返回 `analytics_db`，说明库已存在，跳过“创建数据库”步骤。

### 5.2 创建 `analytics_db`

如果数据库不存在，再执行：

```sql
CREATE DATABASE analytics_db
WITH OWNER = root
     ENCODING = 'UTF8'
     TEMPLATE = template0;
```

然后切换到新库：

```sql
\c analytics_db
```

### 5.3 创建 schema

```sql
CREATE SCHEMA IF NOT EXISTS src_rb;
CREATE SCHEMA IF NOT EXISTS src_defect;
CREATE SCHEMA IF NOT EXISTS ods;
CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS fct;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS meta;
```

### 5.4 创建只读角色

如果 `agent_ro` 不存在，再执行：

```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro'
  ) THEN
    CREATE ROLE agent_ro LOGIN PASSWORD '请改成强密码';
  END IF;
END;
$$;
```

授权：

```sql
GRANT CONNECT ON DATABASE analytics_db TO agent_ro;
GRANT USAGE ON SCHEMA ods, dim, fct, mart, meta TO agent_ro;
```

### 5.5 创建 FDW 连接

```sql
CREATE EXTENSION IF NOT EXISTS postgres_fdw;
```

如果外部 server 不存在，再执行：

```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_foreign_server WHERE srvname = 'rollerbed_srv'
  ) THEN
    CREATE SERVER rollerbed_srv
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'localhost', dbname 'rollerbed_tracking_db', port '5432');
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_foreign_server WHERE srvname = 'defect_srv'
  ) THEN
    CREATE SERVER defect_srv
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'localhost', dbname 'defect_db', port '5432');
  END IF;
END;
$$;
```

为 `root` 创建 user mapping：

```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_user_mappings m
    JOIN pg_foreign_server s ON m.srvid = s.oid
    JOIN pg_roles r ON m.umuser = r.oid
    WHERE s.srvname = 'rollerbed_srv' AND r.rolname = 'root'
  ) THEN
    CREATE USER MAPPING FOR root
    SERVER rollerbed_srv
    OPTIONS (user 'root', password 'root');
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_user_mappings m
    JOIN pg_foreign_server s ON m.srvid = s.oid
    JOIN pg_roles r ON m.umuser = r.oid
    WHERE s.srvname = 'defect_srv' AND r.rolname = 'root'
  ) THEN
    CREATE USER MAPPING FOR root
    SERVER defect_srv
    OPTIONS (user 'root', password 'root');
  END IF;
END;
$$;
```

### 5.6 导入外部表

注意：`IMPORT FOREIGN SCHEMA` 只应在外部表尚未导入时执行一次。

```sql
IMPORT FOREIGN SCHEMA public
LIMIT TO (
  rb_position_data,
  process_areas,
  carrier_types,
  vehicle_body_types,
  vehicle_color_codes,
  vehicle_platforms
)
FROM SERVER rollerbed_srv INTO src_rb;

IMPORT FOREIGN SCHEMA public
LIMIT TO (
  history_station_defect_summary
)
FROM SERVER defect_srv INTO src_defect;
```

如果这些外部表已经存在，就不要重复执行上面的导入语句。

## 6. 本地 ODS / DIM / FCT / MART 对象初始化

如果是首次搭建，依次执行以下对象初始化 SQL。

### 6.1 创建 ODS 表

```sql
CREATE TABLE IF NOT EXISTS ods.rb_position_data AS
SELECT * FROM src_rb.rb_position_data WITH NO DATA;

CREATE TABLE IF NOT EXISTS ods.process_areas AS
SELECT * FROM src_rb.process_areas WITH NO DATA;

CREATE TABLE IF NOT EXISTS ods.carrier_types AS
SELECT * FROM src_rb.carrier_types WITH NO DATA;

CREATE TABLE IF NOT EXISTS ods.vehicle_body_types AS
SELECT * FROM src_rb.vehicle_body_types WITH NO DATA;

CREATE TABLE IF NOT EXISTS ods.vehicle_color_codes AS
SELECT * FROM src_rb.vehicle_color_codes WITH NO DATA;

CREATE TABLE IF NOT EXISTS ods.vehicle_platforms AS
SELECT * FROM src_rb.vehicle_platforms WITH NO DATA;

CREATE TABLE IF NOT EXISTS ods.history_station_defect_summary AS
SELECT * FROM src_defect.history_station_defect_summary WITH NO DATA;
```

### 6.2 ODS 主键与索引

首次创建后执行一次：

```sql
ALTER TABLE ods.rb_position_data ADD PRIMARY KEY (id);
ALTER TABLE ods.process_areas ADD PRIMARY KEY (id);
ALTER TABLE ods.carrier_types ADD PRIMARY KEY (id);
ALTER TABLE ods.vehicle_body_types ADD PRIMARY KEY (id);
ALTER TABLE ods.vehicle_color_codes ADD PRIMARY KEY (id);
ALTER TABLE ods.vehicle_platforms ADD PRIMARY KEY (id);
ALTER TABLE ods.history_station_defect_summary ADD PRIMARY KEY (history_id);
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_ods_rb_vehicle_id
ON ods.rb_position_data(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_ods_rb_process_area
ON ods.rb_position_data(process_area);

CREATE INDEX IF NOT EXISTS idx_ods_rb_vehicle_updated_at
ON ods.rb_position_data(vehicle_updated_at);

CREATE INDEX IF NOT EXISTS idx_ods_defect_vehicle_id
ON ods.history_station_defect_summary(serial_number);

CREATE INDEX IF NOT EXISTS idx_ods_defect_detect_time
ON ods.history_station_defect_summary(date_time);
```

### 6.3 创建 `meta` 表

```sql
CREATE TABLE IF NOT EXISTS meta.sync_job_log (
  id BIGSERIAL PRIMARY KEY,
  job_name TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  message TEXT
);

CREATE TABLE IF NOT EXISTS meta.refresh_watermark (
  source_name TEXT PRIMARY KEY,
  watermark_value TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 6.4 创建 `dim` 表

如果 `dim.dim_vehicle_profile` 已经存在旧版结构，需要先补齐当前绑定快照字段：

```sql
ALTER TABLE dim.dim_vehicle_profile
  ADD COLUMN IF NOT EXISTS current_position_id BIGINT,
  ADD COLUMN IF NOT EXISTS current_carrier_id VARCHAR(50),
  ADD COLUMN IF NOT EXISTS current_carrier_type VARCHAR(20),
  ADD COLUMN IF NOT EXISTS current_process_area VARCHAR(50),
  ADD COLUMN IF NOT EXISTS current_full_rb_code VARCHAR(255),
  ADD COLUMN IF NOT EXISTS current_position_updated_at TIMESTAMPTZ;
```

```sql
CREATE TABLE IF NOT EXISTS dim.dim_process_area (
  process_area_name VARCHAR(50) PRIMARY KEY,
  source_area_id INTEGER,
  description VARCHAR(200),
  sort_order INTEGER,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  etl_loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dim.dim_vehicle_profile (
  vehicle_id VARCHAR(255) PRIMARY KEY,
  body_type VARCHAR(5),
  tracking_type_name VARCHAR(100),
  defect_model INTEGER,
  defect_type_name VARCHAR(100),
  platform_code VARCHAR(10),
  platform_name VARCHAR(50),
  color_code VARCHAR(255),
  color_name VARCHAR(50),
  is_black_roof BOOLEAN,
  black_roof_raw_tracking VARCHAR(32),
  black_roof_raw_defect VARCHAR(100),
  tracking_last_seen_at TIMESTAMPTZ,
  defect_last_seen_at TIMESTAMP,
  current_position_id BIGINT,
  current_carrier_id VARCHAR(50),
  current_carrier_type VARCHAR(20),
  current_process_area VARCHAR(50),
  current_full_rb_code VARCHAR(255),
  current_position_updated_at TIMESTAMPTZ,
  etl_loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_dim_process_area_sort_order
ON dim.dim_process_area(sort_order);

CREATE INDEX IF NOT EXISTS idx_dim_vehicle_profile_type_name
ON dim.dim_vehicle_profile(defect_type_name, tracking_type_name);

CREATE INDEX IF NOT EXISTS idx_dim_vehicle_profile_color_code
ON dim.dim_vehicle_profile(color_code);

CREATE INDEX IF NOT EXISTS idx_dim_vehicle_profile_platform_code
ON dim.dim_vehicle_profile(platform_code);

CREATE INDEX IF NOT EXISTS idx_dim_vehicle_profile_current_carrier_id
ON dim.dim_vehicle_profile(current_carrier_id);

CREATE INDEX IF NOT EXISTS idx_dim_vehicle_profile_current_process_area
ON dim.dim_vehicle_profile(current_process_area);
```

### 6.5 创建事实层与分析层物化视图

如果数据库中已经存在旧版同名物化视图，而你需要升级到本手册对应的最新定义，请先按依赖顺序删除旧对象，再执行下面 SQL：

```sql
DROP MATERIALIZED VIEW IF EXISTS mart.mart_abnormal_vehicle_current;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_position_current_overview;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_vehicle_quality_360;
DROP MATERIALIZED VIEW IF EXISTS fct.fct_abnormal_vehicle_current;
DROP MATERIALIZED VIEW IF EXISTS fct.fct_vehicle_position_current;
DROP MATERIALIZED VIEW IF EXISTS fct.fct_position_current_all;
```

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS fct.fct_position_current_all AS
SELECT
  id AS position_id,
  plc,
  tag,
  rb_index,
  COALESCE(plc, '') || COALESCE(rb_index, '') AS full_rb_code,
  remark,
  process_area,
  carrier_id,
  carrier_type,
  NULLIF(trim(vehicle_id), '') AS vehicle_id,
  body_type,
  color_code,
  platform_code,
  black_roof_flag,
  rework_flag,
  raw_data,
  position_created_at,
  vehicle_updated_at,
  CASE
    WHEN NULLIF(trim(vehicle_id), '') LIKE '782026%'
         AND COALESCE(body_type, '') <> '-----' THEN 'product_vehicle'
    ELSE 'abnormal_vehicle'
  END AS entity_type,
  CASE
    WHEN NULLIF(trim(vehicle_id), '') = '--------------' THEN 'empty_vehicle_id_with_carrier'
    WHEN COALESCE(body_type, '') = '-----'
         AND NULLIF(trim(vehicle_id), '') LIKE '782026%' THEN 'undefined_body_type_with_carrier'
    WHEN NULLIF(trim(vehicle_id), '') IS NULL THEN 'blank_vehicle_id_with_carrier'
    WHEN NULLIF(trim(vehicle_id), '') NOT LIKE '782026%' THEN 'non_product_prefix'
    ELSE NULL
  END AS abnormal_type
FROM ods.rb_position_data
WHERE COALESCE(NULLIF(trim(carrier_id), ''), '0') <> '0'
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fct_position_current_all_position_id
ON fct.fct_position_current_all(position_id);

CREATE INDEX IF NOT EXISTS idx_fct_position_current_all_vehicle_id
ON fct.fct_position_current_all(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_fct_position_current_all_carrier_id
ON fct.fct_position_current_all(carrier_id);

CREATE INDEX IF NOT EXISTS idx_fct_position_current_all_process_area
ON fct.fct_position_current_all(process_area);

CREATE INDEX IF NOT EXISTS idx_fct_position_current_all_entity_type
ON fct.fct_position_current_all(entity_type, abnormal_type);

CREATE MATERIALIZED VIEW IF NOT EXISTS fct.fct_vehicle_position_current AS
SELECT DISTINCT ON (vehicle_id)
  vehicle_id,
  position_id,
  plc,
  tag,
  rb_index,
  full_rb_code,
  remark,
  process_area,
  carrier_id,
  carrier_type,
  body_type,
  color_code,
  platform_code,
  black_roof_flag,
  rework_flag,
  raw_data,
  position_created_at,
  vehicle_updated_at
FROM fct.fct_position_current_all
WHERE entity_type = 'product_vehicle'
  AND vehicle_id LIKE '782026%'
ORDER BY vehicle_id, vehicle_updated_at DESC NULLS LAST, position_created_at DESC, position_id DESC
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fct_vehicle_position_current_vehicle_id
ON fct.fct_vehicle_position_current(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_fct_vehicle_position_current_carrier_id
ON fct.fct_vehicle_position_current(carrier_id);

CREATE INDEX IF NOT EXISTS idx_fct_vehicle_position_current_process_area
ON fct.fct_vehicle_position_current(process_area);

CREATE MATERIALIZED VIEW IF NOT EXISTS fct.fct_vehicle_defect_detection AS
SELECT
  history_id,
  trim(serial_number) AS vehicle_id,
  model,
  type_name,
  black_roof,
  date_time AS detect_time,
  color_code,
  tunnel,
  cycle,
  station_1_defect_count,
  station_2_defect_count,
  station_3_defect_count,
  station_4_defect_count,
  station_5_defect_count,
  total_defect_count
FROM ods.history_station_defect_summary
WHERE serial_number IS NOT NULL
  AND trim(serial_number) <> ''
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fct_vehicle_defect_detection_history_id
ON fct.fct_vehicle_defect_detection(history_id);

CREATE INDEX IF NOT EXISTS idx_fct_vehicle_defect_detection_vehicle_id
ON fct.fct_vehicle_defect_detection(vehicle_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS fct.fct_abnormal_vehicle_current AS
SELECT
  position_id,
  plc,
  tag,
  rb_index,
  full_rb_code,
  remark,
  process_area,
  carrier_id,
  carrier_type,
  vehicle_id,
  body_type,
  color_code,
  platform_code,
  black_roof_flag,
  rework_flag,
  raw_data,
  position_created_at,
  vehicle_updated_at,
  entity_type,
  abnormal_type,
  CASE abnormal_type
    WHEN 'non_product_prefix' THEN 'carrier_id 非 0，但 vehicle_id 前缀不是 782026。'
    WHEN 'empty_vehicle_id_with_carrier' THEN 'carrier_id 非 0，但 vehicle_id 为 --------------。'
    WHEN 'blank_vehicle_id_with_carrier' THEN 'carrier_id 非 0，但 vehicle_id 为空。'
    WHEN 'undefined_body_type_with_carrier' THEN 'carrier_id 非 0，vehicle_id 为产品前缀，但 body_type 为 -----。'
    ELSE 'carrier_id 非 0，但当前占位不满足正式产品车规则。'
  END AS abnormal_reason
FROM fct.fct_position_current_all
WHERE entity_type = 'abnormal_vehicle'
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fct_abnormal_vehicle_current_position_id
ON fct.fct_abnormal_vehicle_current(position_id);

CREATE INDEX IF NOT EXISTS idx_fct_abnormal_vehicle_current_abnormal_type
ON fct.fct_abnormal_vehicle_current(abnormal_type);

CREATE INDEX IF NOT EXISTS idx_fct_abnormal_vehicle_current_carrier_id
ON fct.fct_abnormal_vehicle_current(carrier_id);

CREATE INDEX IF NOT EXISTS idx_fct_abnormal_vehicle_current_vehicle_id
ON fct.fct_abnormal_vehicle_current(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_fct_abnormal_vehicle_current_process_area
ON fct.fct_abnormal_vehicle_current(process_area);

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mart_vehicle_quality_360 AS
SELECT
  d.history_id,
  d.vehicle_id,
  d.detect_time,
  d.model AS defect_model,
  d.type_name AS defect_type_name,
  d.black_roof AS defect_black_roof,
  d.color_code AS defect_color_code,
  d.tunnel,
  d.cycle,
  d.station_1_defect_count,
  d.station_2_defect_count,
  d.station_3_defect_count,
  d.station_4_defect_count,
  d.station_5_defect_count,
  d.total_defect_count,
  p.process_area,
  p.plc,
  p.rb_index,
  p.full_rb_code,
  p.carrier_id,
  p.carrier_type,
  ct.type_name_cn AS carrier_type_name_cn,
  p.body_type,
  bt.type_name AS tracking_type_name,
  p.color_code AS tracking_color_code,
  cc.color_name AS tracking_color_name,
  p.platform_code,
  vp.platform_name,
  p.black_roof_flag,
  p.rework_flag,
  p.position_created_at,
  p.vehicle_updated_at
FROM fct.fct_vehicle_defect_detection d
LEFT JOIN fct.fct_vehicle_position_current p
  ON p.vehicle_id = d.vehicle_id
LEFT JOIN ods.carrier_types ct
  ON ct.type_code = p.carrier_type
LEFT JOIN ods.vehicle_body_types bt
  ON bt.body_type = p.body_type
LEFT JOIN ods.vehicle_color_codes cc
  ON cc.color_code = p.color_code
LEFT JOIN ods.vehicle_platforms vp
  ON vp.platform_code = p.platform_code
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_mart_vehicle_quality_360_vehicle_id
ON mart.mart_vehicle_quality_360(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_mart_vehicle_quality_360_detect_time
ON mart.mart_vehicle_quality_360(detect_time);

CREATE INDEX IF NOT EXISTS idx_mart_vehicle_quality_360_process_area
ON mart.mart_vehicle_quality_360(process_area);

CREATE INDEX IF NOT EXISTS idx_mart_vehicle_quality_360_carrier_id
ON mart.mart_vehicle_quality_360(carrier_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mart_abnormal_vehicle_current AS
SELECT
  a.position_id,
  a.vehicle_id,
  a.abnormal_type,
  a.abnormal_reason,
  a.process_area,
  dpa.description AS process_area_description,
  dpa.sort_order AS process_area_sort_order,
  a.carrier_id,
  a.carrier_type,
  ct.type_name_cn AS carrier_type_name_cn,
  a.plc,
  a.rb_index,
  a.full_rb_code,
  a.remark,
  a.body_type,
  bt.type_name AS tracking_type_name,
  a.color_code,
  cc.color_name AS tracking_color_name,
  a.platform_code,
  vp.platform_name,
  a.black_roof_flag,
  a.rework_flag,
  a.position_created_at,
  a.vehicle_updated_at
FROM fct.fct_abnormal_vehicle_current a
LEFT JOIN dim.dim_process_area dpa
  ON dpa.process_area_name = a.process_area
LEFT JOIN ods.carrier_types ct
  ON ct.type_code = a.carrier_type
LEFT JOIN ods.vehicle_body_types bt
  ON bt.body_type = a.body_type
LEFT JOIN ods.vehicle_color_codes cc
  ON cc.color_code = a.color_code
LEFT JOIN ods.vehicle_platforms vp
  ON vp.platform_code = a.platform_code
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mart_abnormal_vehicle_current_position_id
ON mart.mart_abnormal_vehicle_current(position_id);

CREATE INDEX IF NOT EXISTS idx_mart_abnormal_vehicle_current_abnormal_type
ON mart.mart_abnormal_vehicle_current(abnormal_type);

CREATE INDEX IF NOT EXISTS idx_mart_abnormal_vehicle_current_carrier_id
ON mart.mart_abnormal_vehicle_current(carrier_id);

CREATE INDEX IF NOT EXISTS idx_mart_abnormal_vehicle_current_process_area
ON mart.mart_abnormal_vehicle_current(process_area);

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mart_position_current_overview AS
SELECT
  p.position_id,
  p.entity_type,
  CASE
    WHEN p.entity_type = 'product_vehicle' THEN '正式产品车'
    ELSE '异常车'
  END AS entity_type_name,
  CASE
    WHEN p.entity_type = 'product_vehicle' THEN 'product_vehicle'
    ELSE COALESCE(a.abnormal_type, p.abnormal_type, 'unknown_abnormal')
  END AS vehicle_status_code,
  CASE
    WHEN p.entity_type = 'product_vehicle' THEN '正式产品车'
    ELSE COALESCE(a.abnormal_reason, 'carrier_id 非 0，但当前占位不满足正式产品车规则。')
  END AS vehicle_status_name,
  COALESCE(a.abnormal_type, p.abnormal_type) AS abnormal_type,
  a.abnormal_reason,
  p.process_area,
  dpa.description AS process_area_description,
  dpa.sort_order AS process_area_sort_order,
  p.carrier_id,
  p.carrier_type,
  ct.type_name_cn AS carrier_type_name_cn,
  p.plc,
  p.tag,
  p.rb_index,
  p.full_rb_code,
  p.remark,
  p.vehicle_id,
  p.body_type,
  bt.type_name AS tracking_type_name,
  p.color_code,
  cc.color_name AS tracking_color_name,
  p.platform_code,
  vp.platform_name,
  p.black_roof_flag,
  p.rework_flag,
  CASE
    WHEN COALESCE(p.black_roof_flag, '') IN ('1', 'Y', 'y', 'T', 't') THEN TRUE
    ELSE FALSE
  END AS is_black_roof,
  CASE
    WHEN COALESCE(p.rework_flag, '') IN ('1', 'Y', 'y', 'T', 't') THEN TRUE
    ELSE FALSE
  END AS is_rework,
  p.position_created_at,
  p.vehicle_updated_at
FROM fct.fct_position_current_all p
LEFT JOIN fct.fct_abnormal_vehicle_current a
  ON a.position_id = p.position_id
LEFT JOIN dim.dim_process_area dpa
  ON dpa.process_area_name = p.process_area
LEFT JOIN ods.carrier_types ct
  ON ct.type_code = p.carrier_type
LEFT JOIN ods.vehicle_body_types bt
  ON bt.body_type = p.body_type
LEFT JOIN ods.vehicle_color_codes cc
  ON cc.color_code = p.color_code
LEFT JOIN ods.vehicle_platforms vp
  ON vp.platform_code = p.platform_code
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mart_position_current_overview_position_id
ON mart.mart_position_current_overview(position_id);

CREATE INDEX IF NOT EXISTS idx_mart_position_current_overview_entity_type
ON mart.mart_position_current_overview(entity_type, abnormal_type);

CREATE INDEX IF NOT EXISTS idx_mart_position_current_overview_process_area
ON mart.mart_position_current_overview(process_area);

CREATE INDEX IF NOT EXISTS idx_mart_position_current_overview_carrier_id
ON mart.mart_position_current_overview(carrier_id);

CREATE INDEX IF NOT EXISTS idx_mart_position_current_overview_vehicle_id
ON mart.mart_position_current_overview(vehicle_id);
```

### 6.6 授权

```sql
GRANT SELECT ON ALL TABLES IN SCHEMA ods, dim, fct, mart, meta TO agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA ods, dim, fct, mart, meta
GRANT SELECT ON TABLES TO agent_ro;
```

## 7. 最新正式版一键刷新过程

以下过程是当前数据库已经验证通过的正式刷新版本。

```sql
CREATE OR REPLACE PROCEDURE meta.refresh_analytics_all()
LANGUAGE plpgsql
AS $$
DECLARE
  v_log_id BIGINT;
BEGIN
  INSERT INTO meta.sync_job_log(job_name, status, message)
  VALUES ('refresh_analytics_all', 'running', 'start')
  RETURNING id INTO v_log_id;

  TRUNCATE TABLE
    ods.process_areas,
    ods.carrier_types,
    ods.vehicle_body_types,
    ods.vehicle_color_codes,
    ods.vehicle_platforms,
    ods.rb_position_data,
    ods.history_station_defect_summary,
    dim.dim_process_area,
    dim.dim_vehicle_profile;

  INSERT INTO ods.process_areas SELECT * FROM src_rb.process_areas;
  INSERT INTO ods.carrier_types SELECT * FROM src_rb.carrier_types;
  INSERT INTO ods.vehicle_body_types SELECT * FROM src_rb.vehicle_body_types;
      INSERT INTO ods.vehicle_color_codes SELECT * FROM src_rb.vehicle_color_codes;
      INSERT INTO ods.vehicle_platforms SELECT * FROM src_rb.vehicle_platforms;
      INSERT INTO ods.rb_position_data SELECT * FROM src_rb.rb_position_data;
      INSERT INTO ods.history_station_defect_summary SELECT * FROM src_defect.history_station_defect_summary;

      REFRESH MATERIALIZED VIEW fct.fct_position_current_all;
      REFRESH MATERIALIZED VIEW fct.fct_vehicle_position_current;
      REFRESH MATERIALIZED VIEW fct.fct_vehicle_defect_detection;
      REFRESH MATERIALIZED VIEW fct.fct_abnormal_vehicle_current;

      INSERT INTO dim.dim_process_area (
          process_area_name,
          source_area_id,
      description,
      sort_order,
      created_at,
      updated_at,
      etl_loaded_at
  )
  SELECT
      area_name,
      id,
      description,
      sort_order,
      created_at,
      updated_at,
      now()
  FROM ods.process_areas;

      INSERT INTO dim.dim_vehicle_profile (
          vehicle_id,
          body_type,
          tracking_type_name,
          defect_model,
      defect_type_name,
      platform_code,
      platform_name,
      color_code,
      color_name,
          is_black_roof,
          black_roof_raw_tracking,
          black_roof_raw_defect,
          tracking_last_seen_at,
          defect_last_seen_at,
          current_position_id,
          current_carrier_id,
          current_carrier_type,
          current_process_area,
          current_full_rb_code,
          current_position_updated_at,
          etl_loaded_at
      )
      WITH latest_tracking AS (
          SELECT
              vehicle_id,
              position_id,
              carrier_id,
              carrier_type,
              process_area,
              full_rb_code,
              body_type,
              color_code,
              platform_code,
              black_roof_flag,
              vehicle_updated_at
          FROM fct.fct_vehicle_position_current
      ),
      latest_defect AS (
          SELECT DISTINCT ON (trim(serial_number))
              trim(serial_number) AS vehicle_id,
          model AS defect_model,
          type_name AS defect_type_name,
          black_roof AS black_roof_raw_defect,
          color_code AS defect_color_code,
          date_time AS defect_last_seen_at,
          history_id
      FROM ods.history_station_defect_summary
      WHERE serial_number IS NOT NULL
        AND trim(serial_number) <> ''
      ORDER BY trim(serial_number), date_time DESC NULLS LAST, history_id DESC
  ),
  vehicle_union AS (
      SELECT vehicle_id FROM latest_tracking
      UNION
      SELECT vehicle_id FROM latest_defect
  )
  SELECT
      u.vehicle_id,
      t.body_type,
      bt.type_name AS tracking_type_name,
      d.defect_model,
      d.defect_type_name,
      t.platform_code,
      vp.platform_name,
      COALESCE(t.color_code, d.defect_color_code) AS color_code,
      cc.color_name,
      CASE
          WHEN COALESCE(t.black_roof_flag, '') IN ('1', 'Y', 'y', 'T', 't') THEN TRUE
          WHEN COALESCE(d.black_roof_raw_defect, '') ILIKE '%黑%' THEN TRUE
          ELSE FALSE
          END AS is_black_roof,
          t.black_roof_flag AS black_roof_raw_tracking,
          d.black_roof_raw_defect,
          t.vehicle_updated_at AS tracking_last_seen_at,
          d.defect_last_seen_at,
          t.position_id AS current_position_id,
          t.carrier_id AS current_carrier_id,
          t.carrier_type AS current_carrier_type,
          t.process_area AS current_process_area,
          t.full_rb_code AS current_full_rb_code,
          t.vehicle_updated_at AS current_position_updated_at,
          now() AS etl_loaded_at
      FROM vehicle_union u
      LEFT JOIN latest_tracking t
        ON t.vehicle_id = u.vehicle_id
  LEFT JOIN latest_defect d
    ON d.vehicle_id = u.vehicle_id
  LEFT JOIN ods.vehicle_body_types bt
    ON bt.body_type = t.body_type
  LEFT JOIN ods.vehicle_color_codes cc
        ON cc.color_code = COALESCE(t.color_code, d.defect_color_code)
      LEFT JOIN ods.vehicle_platforms vp
        ON vp.platform_code = t.platform_code;

      REFRESH MATERIALIZED VIEW mart.mart_vehicle_quality_360;
      REFRESH MATERIALIZED VIEW mart.mart_abnormal_vehicle_current;
      REFRESH MATERIALIZED VIEW mart.mart_position_current_overview;

      INSERT INTO meta.refresh_watermark(source_name, watermark_value, updated_at)
      VALUES
        ('ods.rb_position_data.max_vehicle_updated_at', (SELECT COALESCE(MAX(vehicle_updated_at)::text, '') FROM ods.rb_position_data), now()),
        ('ods.history_station_defect_summary.max_date_time', (SELECT COALESCE(MAX(date_time)::text, '') FROM ods.history_station_defect_summary), now()),
        ('ods.history_station_defect_summary.max_history_id', (SELECT COALESCE(MAX(history_id)::text, '') FROM ods.history_station_defect_summary), now())
      ON CONFLICT (source_name) DO UPDATE
      SET watermark_value = EXCLUDED.watermark_value,
          updated_at = EXCLUDED.updated_at;

      GRANT SELECT ON ALL TABLES IN SCHEMA ods, dim, fct, mart, meta TO agent_ro;

      UPDATE meta.sync_job_log
      SET finished_at = now(), status = 'success', message = 'done'
  WHERE id = v_log_id;
EXCEPTION WHEN OTHERS THEN
  UPDATE meta.sync_job_log
  SET finished_at = now(), status = 'failed', message = SQLERRM
  WHERE id = v_log_id;
  RAISE;
END;
$$;
```

## 8. 首次刷新

```sql
CALL meta.refresh_analytics_all();
```

## 9. 日常验证 SQL

### 9.1 验证 schema / 表 / 物化视图

```sql
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('src_rb','src_defect','ods','dim','fct','mart','meta')
ORDER BY schema_name;

SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema IN ('src_rb','src_defect','ods','dim','fct','mart','meta')
ORDER BY table_schema, table_name;

SELECT schemaname, matviewname
FROM pg_matviews
WHERE schemaname IN ('fct','mart')
ORDER BY schemaname, matviewname;
```

### 9.2 验证数据量

```sql
SELECT count(*) FROM ods.rb_position_data;
SELECT count(*) FROM ods.history_station_defect_summary;
SELECT count(*) FROM dim.dim_process_area;
SELECT count(*) FROM dim.dim_vehicle_profile;
SELECT count(*) FROM fct.fct_position_current_all;
SELECT count(*) FROM fct.fct_vehicle_position_current;
SELECT count(*) FROM fct.fct_abnormal_vehicle_current;
SELECT count(*) FROM fct.fct_vehicle_defect_detection;
SELECT count(*) FROM mart.mart_vehicle_quality_360;
SELECT count(*) FROM mart.mart_abnormal_vehicle_current;
SELECT count(*) FROM mart.mart_position_current_overview;
```

### 9.3 验证刷新日志与水位

```sql
SELECT *
FROM meta.sync_job_log
ORDER BY id DESC
LIMIT 5;

SELECT *
FROM meta.refresh_watermark
ORDER BY source_name;
```

### 9.4 验证异常车分类结果

```sql
SELECT abnormal_type, count(*)
FROM fct.fct_abnormal_vehicle_current
GROUP BY abnormal_type
ORDER BY abnormal_type;

SELECT
  position_id,
  vehicle_id,
  carrier_id,
  abnormal_type,
  process_area
FROM fct.fct_abnormal_vehicle_current
ORDER BY vehicle_updated_at DESC NULLS LAST, position_created_at DESC, position_id DESC
LIMIT 20;

SELECT
  entity_type,
  vehicle_status_code,
  count(*)
FROM mart.mart_position_current_overview
GROUP BY entity_type, vehicle_status_code
ORDER BY entity_type, vehicle_status_code;
```

### 9.5 验证 `agent_ro` 权限

```sql
SELECT
  has_schema_privilege('agent_ro', 'mart', 'USAGE') AS mart_usage,
  has_table_privilege('agent_ro', 'mart.mart_vehicle_quality_360', 'SELECT') AS mart_select,
  has_table_privilege('agent_ro', 'mart.mart_abnormal_vehicle_current', 'SELECT') AS abnormal_mart_select,
  has_table_privilege('agent_ro', 'mart.mart_position_current_overview', 'SELECT') AS overview_mart_select,
  has_schema_privilege('agent_ro', 'dim', 'USAGE') AS dim_usage,
  has_table_privilege('agent_ro', 'dim.dim_vehicle_profile', 'SELECT') AS dim_select,
  has_table_privilege('agent_ro', 'fct.fct_position_current_all', 'SELECT') AS position_all_select;
```

## 10. 后续怎么执行

### 10.1 手工刷新

后续日常刷新只需要执行：

```sql
CALL meta.refresh_analytics_all();
```

### 10.2 Windows 定时任务

如果 `psql` 已经在 PATH 中，可以直接使用：

```powershell
psql -U root -h localhost -p 5432 -d analytics_db -c "CALL meta.refresh_analytics_all();"
```

如果 `psql` 不在 PATH 中，请使用 PostgreSQL 安装目录下的完整路径，或者使用 pgAdmin / 其他 SQL 客户端执行。

### 10.3 建议频率

- `rb_position_data` 相关分析：每 `5` 分钟
- 缺陷汇总相关分析：每 `15` 到 `30` 分钟

当前正式版本是“全量刷新”，先以稳定为主，后续再考虑增量刷新。

## 10.4 下一阶段优化建议

如果后续要支持以下查询：

- 调试车或异常车当前分布
- 通过 `carrier_id` 反查当前车辆
- 相同异常 `vehicle_id` 在不同位置同时存在
- 正式产品车与异常车分开统计

建议按以下方向演进：

1. 保留当前 `ods` / `dim` / `fct` / `mart` 基础结构
2. 新增 `fct_position_current_all`
3. 将 `fct_vehicle_position_current` 明确收窄为正式产品车事实
4. 新增 `fct_abnormal_vehicle_current`
5. 将 `mart_vehicle_quality_360` 明确为正式产品车质量分析主表
6. 将 `mart_position_current_overview` 作为当前现场总览统一入口
7. 视需要继续新增更细的异常车或时序主题 `mart`

详细方案见：

- [current_vehicle_fact_refactor.md](/F:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/docs/backend/database_refactor/current_vehicle_fact_refactor.md)

## 11. 项目接入

确认 `analytics_db` 跑通后，再做两件事：

1. 在 `.env` 中增加：

```env
ANALYTICS_DATABASE_URL='postgresql://agent_ro:你的密码@localhost:5432/analytics_db'
```

2. 修改项目代码，让 SQL Agent 默认连接 `analytics_db`

## 12. 两个重要提醒

1. 当前 `mart.mart_vehicle_quality_360` 关联的是“缺陷检测”和“车辆当前最新位置”，不是“检测当时位置”。
2. 如果后面要分析“检测时所在区域”或“停留时长与缺陷关系”，下一步要补车辆位置历史快照层，而不是直接依赖当前这张 `mart` 表。
