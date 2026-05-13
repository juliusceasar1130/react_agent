# Analytics DB 落地与刷新操作手册（最新已验证版）

修改时间：2026-05-12 Asia/Shanghai

主要修改内容：
- 新增 `fct.fct_vehicle_defect_enriched` 物化视图：以 carbody 为中心，整合缺陷检测记录的全量分析宽表
- 优化 `refresh_analytics_all()` 过程：在 MART 刷新后增加 `fct_vehicle_defect_enriched` 的刷新步骤
- 补充属性一致性验证与漏检分析 SQL
- 优化 JOIN 性能：移除 JOIN 条件中的 `trim()`，强调 ODS 层清洗数据
- (2026-05-10)：新增 `carbody_history` 数据库接入、`dim.carbody_registry` 与 `meta.refresh_carbody()`
- 原始变动（2026-04-15）：
- 补充 Windows 定时任务下 `pgpass.conf` 认证方案，解决 `psql` 无法交互输入密码的问题
- 新增 `defect_database/scripts/refresh_analytics_db.ps1` Windows 宿主机刷新包装脚本说明
- 新增文档目录，便于在长文档中快速定位章节
- 删除已过时的“10.4 下一阶段优化建议”章节，避免与当前已落地状态重复或混淆
- 明确本手册为 `analytics_db` 最终落地口径，`current_vehicle_fact_refactor.md` 仅保留为历史设计记录
- 补充基于 MCP 对实时 `analytics_db` 的实际对象、字段、物化视图定义与数据量校验结果
- 将 `current_vehicle_fact_refactor.md` 中仍有参考价值的设计解释、适用边界与查询入口合并进本手册
- 将旧版 `analytics_db` 架构图文档重写为可直接执行的落地与刷新操作手册
- 修正旧版流程中遗漏 `dim` 刷新、`meta.refresh_watermark` 更新、刷新口径错误等问题
- 以当前数据库中已经验证成功的对象结构为准，统一后续执行口径
- 补充当前 `fct_vehicle_position_current` 对异常车与重复调试车场景的局限说明
- 补充下一阶段“正式产品车 / 异常车 / 全量占位”分层优化入口
- 将“当前车辆事实分层优化”第一阶段落地结果同步到手册
- 补充 `fct_position_current_all`、`fct_abnormal_vehicle_current`、`mart_abnormal_vehicle_current` 与 `dim_vehicle_profile.current_*` 最新对象说明
- 补充 `mart_position_current_overview` 当前现场总览对象与对应刷新、验证口径
- 修正文档内失效的旧仓库绝对路径引用，改为当前仓库实际文件路径

## 目录

- [1. 适用范围](#1-适用范围)
- [2. 当前已验证的最新状态](#2-当前已验证的最新状态)
- [3. 旧版流程中已修正的错误](#3-旧版流程中已修正的错误)
- [3.1 当前已知限制](#31-当前已知限制)
- [3.2 为什么必须拆分“全部占位 / 正式产品车 / 异常车”](#32-为什么必须拆分全部占位--正式产品车--异常车)
- [3.2.1 重复调试 `vehicle_id` 会被错误压缩](#321-重复调试-vehicle_id-会被错误压缩)
- [3.2.2 产品车与异常车的建模依据不同](#322-产品车与异常车的建模依据不同)
- [3.2.3 为什么不能再把 `fct_vehicle_position_current` 当成总入口](#323-为什么不能再把-fct_vehicle_position_current-当成总入口)
- [3.3 建议查询入口](#33-建议查询入口)
- [4. 前置确认](#4-前置确认)
- [5. 一次性初始化流程](#5-一次性初始化流程)
- [5.1 检查 `analytics_db` 是否已存在](#51-检查-analytics_db-是否已存在)
- [5.2 创建 `analytics_db`](#52-创建-analytics_db)
- [5.3 创建 schema](#53-创建-schema)
- [5.4 创建只读角色](#54-创建只读角色)
- [5.5 创建 FDW 连接](#55-创建-fdw-连接)
- [5.6 导入外部表](#56-导入外部表)
- [6. 本地 ODS / DIM / FCT / MART 对象初始化](#6-本地-ods--dim--fct--mart-对象初始化)
- [6.1 创建 ODS 表](#61-创建-ods-表)
- [6.2 ODS 主键与索引](#62-ods-主键与索引)
- [6.3 创建 `meta` 表](#63-创建-meta-表)
- [6.4 创建 `dim` 表](#64-创建-dim-表)
- [6.5 创建事实层与分析层物化视图](#65-创建事实层与分析层物化视图)
- [6.6 授权](#66-授权)
- [7. 最新正式版一键刷新过程](#7-最新正式版一键刷新过程)
- [8. 首次刷新](#8-首次刷新)
- [9. 日常验证 SQL](#9-日常验证-sql)
- [9.1 验证 schema / 表 / 物化视图](#91-验证-schema--表--物化视图)
- [9.2 验证数据量](#92-验证数据量)
- [9.3 验证刷新日志与水位](#93-验证刷新日志与水位)
- [9.4 验证异常车分类结果](#94-验证异常车分类结果)
- [9.5 验证 `agent_ro` 权限](#95-验证-agent_ro-权限)
- [10. 后续怎么执行](#10-后续怎么执行)
- [10.1 手工刷新](#101-手工刷新)
- [10.2 Windows 定时任务](#102-windows-定时任务)
- [10.3 建议频率](#103-建议频率)
- [11. 项目接入](#11-项目接入)
- [12. 两个重要提醒](#12-两个重要提醒)

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

本手册与 `current_vehicle_fact_refactor.md` 的关系：

- 本手册是当前项目后续执行、刷新、校验、接入时应采用的唯一落地基线
- `current_vehicle_fact_refactor.md` 保留为第一阶段分层重构的历史设计记录
- 若两份文档出现口径差异，以本手册和实时数据库对象定义为准

## 2. 当前已验证的最新状态

2026-04-14 通过 MCP 直连实时 `analytics_db` 校验，数据库中当前存在以下对象：

- 数据库：
  - `analytics_db`
- schema：
  - `src_rb`
  - `src_defect`
  - `src_carbody`
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
  - `carbody_history`
- `dim` 表：
  - `dim_process_area`
  - `dim_vehicle_profile`
  - `carbody_registry`
- `fct` 物化视图：
  - `fct_position_current_all`
  - `fct_abnormal_vehicle_current`
  - `fct_vehicle_position_current`
  - `fct_vehicle_defect_detection` (仅缺陷事件)
  - `fct_vehicle_defect_enriched` (车身中心全量视图)
- `mart` 物化视图：
  - `mart_abnormal_vehicle_current`
  - `mart_position_current_overview`
  - `mart_vehicle_quality_360`
- `meta` 表：
  - `sync_job_log`
  - `refresh_watermark`
- 刷新过程：
  - `meta.refresh_analytics_all()`
  - `meta.refresh_carbody()`
- 只读角色：
  - `agent_ro`

本手册以下内容，以这套已验证状态为准。

当次实时校验结果（2026-04-14，当前数据水位仍停留在 2026-04-11 刷新批次）：

- `ods.rb_position_data`：`520`
- `ods.history_station_defect_summary`：`60370`
- `dim.dim_process_area`：`15`
- `dim.dim_vehicle_profile`：`54430`
- `fct.fct_position_current_all`：`114`
- `fct.fct_vehicle_position_current`：`102`
- `fct.fct_abnormal_vehicle_current`：`12`
- `fct.fct_vehicle_defect_detection`：`60370`
- `fct.fct_vehicle_defect_enriched`：`>= 54430` (取决于 carbody 记录数)
- `mart.mart_vehicle_quality_360`：`60370`
- `mart.mart_abnormal_vehicle_current`：`12`
- `mart.mart_position_current_overview`：`114`

当次实时校验还确认：

- `dim.dim_vehicle_profile` 已实际存在以下当前绑定快照字段：
  - `current_position_id`
  - `current_carrier_id`
  - `current_carrier_type`
  - `current_process_area`
  - `current_full_rb_code`
  - `current_position_updated_at`
- `fct.fct_position_current_all` 的真实定义已按当前占位进行分类：
  - `product_vehicle`
  - `abnormal_vehicle`
- `fct.fct_abnormal_vehicle_current` 当前实时分类结果为：
  - `empty_vehicle_id_with_carrier`：`8`
  - `non_product_prefix`：`4`
- `meta.refresh_watermark` 当前记录为：
  - `ods.rb_position_data.max_vehicle_updated_at = 2026-04-03 06:11:32.191541+00`
  - `ods.history_station_defect_summary.max_date_time = 2026-04-08 11:54:19`
  - `ods.history_station_defect_summary.max_history_id = 1301806`

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

以上边界与后续方向，原本分散记录在 `current_vehicle_fact_refactor.md` 中，现已并入本手册。

## 3.2 为什么必须拆分“全部占位 / 正式产品车 / 异常车”

本次分层优化的根本原因，不是命名调整，而是业务实体唯一性不同。

### 3.2.1 重复调试 `vehicle_id` 会被错误压缩

旧版 `fct.fct_vehicle_position_current` 的核心逻辑是：

- 从 `ods.rb_position_data` 中取数
- 按 `vehicle_id` 使用 `DISTINCT ON (vehicle_id)` 保留最新一条

这套逻辑对正式产品车基本成立，但对异常车或调试车不成立。  
如果现场有多台调试车共用同一个临时 `vehicle_id`，例如 `88888888888888`，那么按 `vehicle_id` 去重后只能保留一条，无法代表“当前全部占位”。

### 3.2.2 产品车与异常车的建模依据不同

正式产品车当前采用的识别口径是：

- `vehicle_id LIKE '782026%'`
- `body_type <> '-----'`
- `carrier_id <> '0'`

异常车则可能出现以下情况：

- `vehicle_id` 前缀不是 `782026`
- `vehicle_id = '--------------'`
- `vehicle_id` 为空
- `vehicle_id` 虽是产品前缀，但 `body_type = '-----'`

因此异常车不能继续与正式产品车共用同一个“按 `vehicle_id` 唯一化”的事实表。

### 3.2.3 为什么不能再把 `fct_vehicle_position_current` 当成总入口

如果继续把 `fct.fct_vehicle_position_current` 当成“全部车辆当前事实”，会导致：

1. 多台调试车共用 `vehicle_id` 时被错误合并
2. 异常车统计被系统性低估
3. `carrier_id -> vehicle_id` 的当前绑定关系不完整
4. Agent 容易把“正式产品车事实”误认为“全部现场事实”

因此当前正式落地口径已经拆为：

- `fct.fct_position_current_all`：当前全部有效占位
- `fct.fct_vehicle_position_current`：当前正式产品车
- `fct.fct_abnormal_vehicle_current`：当前异常车

## 3.3 建议查询入口

为避免 Agent 或后续开发继续混用口径，当前建议的查询入口固定如下：

- 正式产品车当前分布：
  - `fct.fct_vehicle_position_current`
- 当前异常车监控：
  - `fct.fct_abnormal_vehicle_current`
  - `mart.mart_abnormal_vehicle_current`
- 当前现场总览：
  - `fct.fct_position_current_all`
  - `mart.mart_position_current_overview`
- 质量与当前位置关联：
  - `mart.mart_vehicle_quality_360`

一句话原则：

- 不再试图让一张表同时承担“全部占位、正式产品车、异常车”三种不同口径

## 4. 前置确认

首次搭建前，请先确认源表已存在：

- `rollerbed_tracking_db` 中的基础表来自：
  - [create_tables_postgresql.sql](/F:/000_dev/Python/workplace/savedatabase-postgresql_v2/create_tables_postgresql.sql)
- `defect_db` 中需要先存在：
  - `history_station_defect_summary`
- 缺陷汇总表说明文档：
  - [history_station_defect_summary_schema.md](/F:/000_dev/Python/workplace/savedatabase-postgresql_v2/defect_database/defect_database_from_agent/history_station_defect_summary_schema.md)

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

### 5.7 创建 carbody FDW 连接与外部表

```sql
-- schema
CREATE SCHEMA IF NOT EXISTS src_carbody;

-- FDW server
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_foreign_server WHERE srvname = 'carbody_srv'
  ) THEN
    CREATE SERVER carbody_srv
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'localhost', dbname 'carbody_history', port '5432');
  END IF;
END;
$$;

-- user mapping
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_user_mappings m
    JOIN pg_foreign_server s ON m.srvid = s.oid
    JOIN pg_roles r ON m.umuser = r.oid
    WHERE s.srvname = 'carbody_srv' AND r.rolname = 'root'
  ) THEN
    CREATE USER MAPPING FOR root
    SERVER carbody_srv
    OPTIONS (user 'root', password 'root');
  END IF;
END;
$$;

-- 导入外部表（仅一次）
IMPORT FOREIGN SCHEMA public
LIMIT TO (carbody_history)
FROM SERVER carbody_srv INTO src_carbody;
```

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

-- ---------------------------------------------------------
-- fct.fct_vehicle_defect_enriched
-- 以 carbody 为中心，LEFT JOIN 缺陷事件，保留双源属性
-- ---------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS fct.fct_vehicle_defect_enriched AS
SELECT
  -- ===== carbody 权威车身维度（驱动表）=====
  cvp.vehicle_id,
  cvp.body_type,
  cvp.platform_code,
  cvp.color_code,
  cvp.black_roof_flag,
  cvp.rework_flag,
  cvp.reserved_1,
  cvp.reserved_2,
  cvp.first_seen_at,
  cvp.last_seen_at,
  cvp.first_rw_station,
  cvp.last_rw_station,
  cvp.first_body_type,
  cvp.last_body_type,
  cvp.station_pass_count,

  -- ===== 缺陷检测事件（可为 NULL）=====
  d.history_id,
  d.model                     AS defect_model,
  d.type_name                 AS defect_type_name,
  d.black_roof                AS defect_black_roof,
  d.color_code                AS defect_color_code,
  d.date_time                 AS detect_time,
  d.tunnel,
  d.cycle,
  d.station_1_defect_count,
  d.station_2_defect_count,
  d.station_3_defect_count,
  d.station_4_defect_count,
  d.station_5_defect_count,
  d.total_defect_count,

  -- ===== 检测覆盖标记 =====
  CASE WHEN d.history_id IS NOT NULL THEN TRUE ELSE FALSE END AS has_defect_record

FROM dim.carbody_registry cvp
LEFT JOIN ods.history_station_defect_summary d
  -- 性能优化：此处不使用 trim() 以利用 ods 层的索引。要求 ODS 加载时已完成数据清洗。
  ON cvp.vehicle_id = d.serial_number
  AND d.serial_number <> ''
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_fct_vehicle_defect_enriched_vehicle_id
ON fct.fct_vehicle_defect_enriched(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_fct_vehicle_defect_enriched_detect_time
ON fct.fct_vehicle_defect_enriched(detect_time);

CREATE INDEX IF NOT EXISTS idx_fct_vehicle_defect_enriched_body_type
ON fct.fct_vehicle_defect_enriched(body_type);

CREATE INDEX IF NOT EXISTS idx_fct_vehicle_defect_enriched_has_defect
ON fct.fct_vehicle_defect_enriched(has_defect_record);

-- UNIQUE INDEX：支持 REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS idx_fct_vehicle_defect_enriched_unique
ON fct.fct_vehicle_defect_enriched(vehicle_id, COALESCE(history_id, -1));


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
GRANT SELECT ON fct.fct_vehicle_defect_enriched TO agent_ro; -- 明确授予新视图权限
ALTER DEFAULT PRIVILEGES IN SCHEMA ods, dim, fct, mart, meta
GRANT SELECT ON TABLES TO agent_ro;
```

### 6.7 创建 `ods.carbody_history`

```sql
CREATE TABLE IF NOT EXISTS ods.carbody_history AS
SELECT * FROM src_carbody.carbody_history WITH NO DATA;

-- PK + 索引
ALTER TABLE ods.carbody_history ADD PRIMARY KEY ("ID");
CREATE INDEX IF NOT EXISTS idx_ods_carbody_body_id         ON ods.carbody_history("BODY_ID");
CREATE INDEX IF NOT EXISTS idx_ods_carbody_date_evt        ON ods.carbody_history("DATE_EVT");
CREATE INDEX IF NOT EXISTS idx_ods_carbody_body_id_date    ON ods.carbody_history("BODY_ID", "DATE_EVT");
CREATE INDEX IF NOT EXISTS idx_ods_carbody_rw_station      ON ods.carbody_history("RW_STATION_ID");
```

### 6.8 创建 `dim.carbody_registry`

```sql
-- 首/末过站聚合表，78 前缀过滤，每车一行
-- MDS_DATA 提取规则见 carbody_history/MDS数据提取规则.md
CREATE TABLE IF NOT EXISTS dim.carbody_registry (
    vehicle_id         VARCHAR(14) PRIMARY KEY,
    first_seen_at      TIMESTAMP NOT NULL,      -- 首次过站时间
    last_seen_at       TIMESTAMP NOT NULL,      -- 末次过站时间
    first_rw_station   VARCHAR(64),             -- 首次过站位置
    last_rw_station    VARCHAR(64),             -- 末次过站位置
    first_body_type    VARCHAR(12),             -- 入口车身类型
    last_body_type     VARCHAR(12),             -- 出口车身类型
    station_pass_count INTEGER,                 -- 总过站次数
    body_type          VARCHAR(5),              -- MDS_DATA 45-49
    platform_code      VARCHAR(3),              -- MDS_DATA 51-53
    color_code         VARCHAR(4),              -- MDS_DATA 59-62
    black_roof_flag    VARCHAR(1),              -- MDS_DATA 137
    rework_flag        VARCHAR(1),              -- MDS_DATA 139
    reserved_1         VARCHAR(1),              -- MDS_DATA 138
    reserved_2         VARCHAR(1),              -- MDS_DATA 140
    etl_loaded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_dim_carbody_vp_first_seen   ON dim.carbody_registry(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_dim_carbody_vp_last_seen    ON dim.carbody_registry(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_dim_carbody_vp_first_station ON dim.carbody_registry(first_rw_station);
CREATE INDEX IF NOT EXISTS idx_dim_carbody_vp_last_station  ON dim.carbody_registry(last_rw_station);
```

如果表已存在（老版本升级），通过 ALTER TABLE 补齐 7 个 MDS 字段：

```sql
ALTER TABLE dim.carbody_registry ADD COLUMN IF NOT EXISTS body_type       VARCHAR(5);
ALTER TABLE dim.carbody_registry ADD COLUMN IF NOT EXISTS platform_code   VARCHAR(3);
ALTER TABLE dim.carbody_registry ADD COLUMN IF NOT EXISTS color_code      VARCHAR(4);
ALTER TABLE dim.carbody_registry ADD COLUMN IF NOT EXISTS black_roof_flag VARCHAR(1);
ALTER TABLE dim.carbody_registry ADD COLUMN IF NOT EXISTS rework_flag     VARCHAR(1);
ALTER TABLE dim.carbody_registry ADD COLUMN IF NOT EXISTS reserved_1      VARCHAR(1);
ALTER TABLE dim.carbody_registry ADD COLUMN IF NOT EXISTS reserved_2      VARCHAR(1);
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

  -- 刷新事实层物化视图
  REFRESH MATERIALIZED VIEW fct.fct_position_current_all;
  REFRESH MATERIALIZED VIEW fct.fct_vehicle_position_current;
  REFRESH MATERIALIZED VIEW fct.fct_vehicle_defect_detection;
  REFRESH MATERIALIZED VIEW fct.fct_vehicle_defect_enriched;
  REFRESH MATERIALIZED VIEW fct.fct_abnormal_vehicle_current;

  -- 更新维度表
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
  LEFT JOIN latest_tracking t ON t.vehicle_id = u.vehicle_id
  LEFT JOIN latest_defect d ON d.vehicle_id = u.vehicle_id
  LEFT JOIN ods.vehicle_body_types bt ON bt.body_type = t.body_type
  LEFT JOIN ods.vehicle_color_codes cc ON cc.color_code = COALESCE(t.color_code, d.defect_color_code)
  LEFT JOIN ods.vehicle_platforms vp ON vp.platform_code = t.platform_code;

  -- 刷新汇总层物化视图
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

### 7.2 carbody 刷新过程（增量 UPSERT）

不纳入 `refresh_analytics_all()`，原因是 carbody 数据量（101 万行）和刷新频率可能不同，出错时隔离影响面。

**增量策略**：ODS 纯增量（INSERT only，不 TRUNCATE）+ DIM 增量 UPSERT。水位基于 `max("ID")`（自增主键，无重复、无时区问题）。

```sql
CREATE OR REPLACE PROCEDURE meta.refresh_carbody()
LANGUAGE plpgsql
AS $$
DECLARE
  v_log_id    BIGINT;
  v_last_id   NUMERIC;
  v_new_count INTEGER;
BEGIN
  INSERT INTO meta.sync_job_log(job_name, status, message)
  VALUES ('refresh_carbody', 'running', 'start')
  RETURNING id INTO v_log_id;

  -- 1. 读取 ODS 水位
  SELECT COALESCE(watermark_value::numeric, 0)
  INTO v_last_id
  FROM meta.refresh_watermark
  WHERE source_name = 'ods.carbody_history.max_id';

  -- 2. ODS 增量插入
  INSERT INTO ods.carbody_history
  SELECT * FROM src_carbody.carbody_history
  WHERE "ID" > v_last_id;

  GET DIAGNOSTICS v_new_count = ROW_COUNT;

  -- 3. DIM UPSERT（仅处理增量批次中的车辆）
  IF v_new_count > 0 THEN
    WITH new_records AS (
        SELECT * FROM ods.carbody_history
        WHERE "ID" > v_last_id
          AND "BODY_ID" LIKE '78%'
    ),
    vehicle_agg AS (
        SELECT
            "BODY_ID" AS vehicle_id,
            MIN("DATE_EVT") AS first_seen_at,
            MAX("DATE_EVT") AS last_seen_at,
            (ARRAY_AGG("RW_STATION_ID" ORDER BY "DATE_EVT"))[1]      AS first_rw_station,
            (ARRAY_AGG("RW_STATION_ID" ORDER BY "DATE_EVT" DESC))[1] AS last_rw_station,
            (ARRAY_AGG("BODY_TYPE"    ORDER BY "DATE_EVT"))[1]      AS first_body_type,
            (ARRAY_AGG("BODY_TYPE"    ORDER BY "DATE_EVT" DESC))[1] AS last_body_type,
            count(*) AS station_pass_count
        FROM new_records
        GROUP BY "BODY_ID"
    ),
    last_mds AS (
        SELECT DISTINCT ON ("BODY_ID")
            "BODY_ID",
            substring("MDS_DATA", 45, 5)  AS mds_body_type,
            substring("MDS_DATA", 51, 3)  AS mds_platform_code,
            substring("MDS_DATA", 59, 4)  AS mds_color_code,
            substring("MDS_DATA", 137, 1) AS mds_black_roof_flag,
            substring("MDS_DATA", 139, 1) AS mds_rework_flag,
            substring("MDS_DATA", 138, 1) AS mds_reserved_1,
            substring("MDS_DATA", 140, 1) AS mds_reserved_2
        FROM new_records
        WHERE length("MDS_DATA") >= 140
        ORDER BY "BODY_ID", "DATE_EVT" DESC
    )
    INSERT INTO dim.carbody_registry (
        vehicle_id, first_seen_at, last_seen_at,
        first_rw_station, last_rw_station,
        first_body_type, last_body_type, station_pass_count,
        body_type, platform_code, color_code,
        black_roof_flag, rework_flag, reserved_1, reserved_2
    )
    SELECT
        va.vehicle_id,
        va.first_seen_at,
        va.last_seen_at,
        va.first_rw_station,
        va.last_rw_station,
        va.first_body_type,
        va.last_body_type,
        va.station_pass_count,
        lm.mds_body_type,
        lm.mds_platform_code,
        lm.mds_color_code,
        lm.mds_black_roof_flag,
        lm.mds_rework_flag,
        lm.mds_reserved_1,
        lm.mds_reserved_2
    FROM vehicle_agg va
    LEFT JOIN last_mds lm ON lm."BODY_ID" = va.vehicle_id
    ON CONFLICT (vehicle_id) DO UPDATE SET
        last_seen_at       = EXCLUDED.last_seen_at,
        last_rw_station    = EXCLUDED.last_rw_station,
        last_body_type     = EXCLUDED.last_body_type,
        station_pass_count = dim.carbody_registry.station_pass_count
                           + EXCLUDED.station_pass_count,
        body_type          = EXCLUDED.body_type,
        platform_code      = EXCLUDED.platform_code,
        color_code         = EXCLUDED.color_code,
        black_roof_flag    = EXCLUDED.black_roof_flag,
        rework_flag        = EXCLUDED.rework_flag,
        reserved_1         = EXCLUDED.reserved_1,
        reserved_2         = EXCLUDED.reserved_2;
  END IF;

  -- 4. 更新水位
  INSERT INTO meta.refresh_watermark(source_name, watermark_value, updated_at)
  VALUES
    ('ods.carbody_history.max_id',
     (SELECT COALESCE(MAX("ID")::text, v_last_id::text) FROM ods.carbody_history), now()),
    ('dim.carbody_registry.last_sync_at', now()::text, now())
  ON CONFLICT (source_name) DO UPDATE
  SET watermark_value = EXCLUDED.watermark_value,
      updated_at      = EXCLUDED.updated_at;

  -- 5. 权限
  GRANT SELECT ON ALL TABLES IN SCHEMA src_carbody TO agent_ro;
  GRANT SELECT ON ods.carbody_history TO agent_ro;
  GRANT SELECT ON dim.carbody_registry TO agent_ro;
  ALTER DEFAULT PRIVILEGES IN SCHEMA src_carbody GRANT SELECT ON TABLES TO agent_ro;

  UPDATE meta.sync_job_log
  SET finished_at = now(), status = 'success',
      message = format('ods_new: %s rows', v_new_count)
  WHERE id = v_log_id;
EXCEPTION WHEN OTHERS THEN
  UPDATE meta.sync_job_log
  SET finished_at = now(), status = 'failed', message = SQLERRM
  WHERE id = v_log_id;
  RAISE;
END;
$$;
```

**UPSERT 语义**：

| 字段 | INSERT（新车） | UPDATE（已有车） |
|------|---------------|------------------|
| `vehicle_id` | 写入 | 不变（PK） |
| `first_seen_at` / `first_rw_station` / `first_body_type` | 写入 | **不更新** |
| `last_seen_at` / `last_rw_station` / `last_body_type` | 写入 | **覆盖** |
| `station_pass_count` | 写入 | **累加**（旧值 + 批次计数） |
| MDS 7 字段 | 写入（末次 MDS_DATA） | **覆盖** |

**每周兜底**：ODS 纯增量不清理过期行。建议每周一次全量重刷以同步源库的 1 个月滚动窗口：

```sql
-- 重置水位为 0 + 清空 ODS/DIM + 调用增量过程（等价全量）
UPDATE meta.refresh_watermark SET watermark_value = '0'
WHERE source_name = 'ods.carbody_history.max_id';
TRUNCATE TABLE ods.carbody_history;
TRUNCATE TABLE dim.carbody_registry;
CALL meta.refresh_carbody();
```

## 8. 首次刷新

首次执行前，先初始化增量水位。根据环境选择：

```sql
-- 新环境（空库）：水位从 0 开始，首次调用即全量
INSERT INTO meta.refresh_watermark(source_name, watermark_value)
VALUES ('ods.carbody_history.max_id', '0')
ON CONFLICT (source_name) DO NOTHING;

-- 老环境（已有全量数据）：跳过全量重刷，从当前最大 ID 开始增量
-- INSERT INTO meta.refresh_watermark(source_name, watermark_value)
-- VALUES ('ods.carbody_history.max_id',
--         (SELECT COALESCE(MAX("ID")::text, '0') FROM ods.carbody_history))
-- ON CONFLICT (source_name) DO NOTHING;
```

```sql
-- analytics 主刷新
CALL meta.refresh_analytics_all();

-- carbody 首次刷新（新环境为全量，老环境为增量）
CALL meta.refresh_carbody();
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
SELECT count(*) FROM fct.fct_vehicle_defect_enriched;
SELECT count(*) FROM mart.mart_vehicle_quality_360;
SELECT count(*) FROM mart.mart_abnormal_vehicle_current;
SELECT count(*) FROM mart.mart_position_current_overview;

-- 验证：fct_vehicle_defect_enriched 漏检与重复检测验证
SELECT has_defect_record, count(*) 
FROM fct.fct_vehicle_defect_enriched 
GROUP BY has_defect_record;

-- 验证：属性一致性（同一车身的 carbody 属性不应冲突）
SELECT vehicle_id, count(DISTINCT body_type), count(DISTINCT color_code)
FROM fct.fct_vehicle_defect_enriched
WHERE has_defect_record
GROUP BY vehicle_id
HAVING count(DISTINCT body_type) > 1 OR count(DISTINCT color_code) > 1;
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
  has_table_privilege('agent_ro', 'fct.fct_position_current_all', 'SELECT') AS position_all_select,
  has_table_privilege('agent_ro', 'fct.fct_vehicle_defect_enriched', 'SELECT') AS defect_enriched_select;
```

### 9.6 验证 carbody 对象

```sql
-- 水位是否存在
SELECT * FROM meta.refresh_watermark
WHERE source_name IN ('ods.carbody_history.max_id', 'dim.carbody_registry.last_sync_at');

-- 对象存在性
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('src_carbody','ods') AND table_name LIKE '%carbody%'
UNION ALL
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'dim' AND table_name = 'carbody_registry';

-- 数据量（期待 ods ~101 万，dim ~1.3 万）
SELECT 'ods.carbody_history' AS tbl, count(*) AS rows FROM ods.carbody_history
UNION ALL
SELECT 'dim.carbody_registry' AS tbl, count(*) AS rows FROM dim.carbody_registry;

-- 首末时间合理性（应为 0）
SELECT count(*) AS invalid_count
FROM dim.carbody_registry
WHERE first_seen_at > last_seen_at;

-- 78 前缀一致性（应为 0）
SELECT count(*) AS non_78_prefix
FROM dim.carbody_registry
WHERE vehicle_id NOT LIKE '78%';

-- vehicle_id 唯一性（应为 0）
SELECT vehicle_id, count(*) AS dup
FROM dim.carbody_registry
GROUP BY vehicle_id HAVING count(*) > 1;

-- MDS 字段非 NULL 率
SELECT
    round(count(body_type)     * 100.0 / count(*), 1) AS body_type_pct,
    round(count(platform_code) * 100.0 / count(*), 1) AS platform_pct,
    round(count(color_code)    * 100.0 / count(*), 1) AS color_pct
FROM dim.carbody_registry;

-- 数据样本
SELECT * FROM dim.carbody_registry ORDER BY first_seen_at DESC LIMIT 10;

-- 刷新日志
SELECT * FROM meta.sync_job_log WHERE job_name = 'refresh_carbody' ORDER BY id DESC LIMIT 5;

-- 增量幂等性：连续执行两次 CALL meta.refresh_carbody()，第二次 ods_new 应为 0
```

## 10. 后续怎么执行

### 10.1 手工刷新

后续日常刷新执行：

```sql
-- analytics 主刷新
CALL meta.refresh_analytics_all();

-- carbody 刷新
CALL meta.refresh_carbody();
```

### 10.2 Windows 定时任务

推荐直接调用仓库中的 PowerShell 包装脚本：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\000_dev\Python\workplace\savedatabase-postgresql_v2\defect_database\scripts\refresh_analytics_db.ps1"
```

脚本说明：

- 默认执行 `CALL meta.refresh_analytics_all();`
- 日志写入宿主机 `logs/analytics_db_refresh.log`
- 默认优先从 PATH 查找 `psql`
- 如需显式指定 `psql.exe`，可追加：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\000_dev\Python\workplace\savedatabase-postgresql_v2\defect_database\scripts\refresh_analytics_db.ps1" -PsqlExe "C:\Program Files\PostgreSQL\17\bin\psql.exe"
```

- 如需显式传入连接信息，可追加：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\000_dev\Python\workplace\savedatabase-postgresql_v2\defect_database\scripts\refresh_analytics_db.ps1" -DbHost "localhost" -DbPort "5432" -DbName "analytics_db" -DbUser "root"
```

建议优先通过 `pgpass.conf` 提供密码；如仅用于临时排障，也可短期传入 `-DbPassword`。

`pgpass.conf` 推荐配置方式：

- Windows 路径：
  - `%APPDATA%\postgresql\pgpass.conf`
- 常见实际路径示例：
  - `C:\Users\你的用户名\AppData\Roaming\postgresql\pgpass.conf`
- 一行格式：
  - `hostname:port:database:username:password`
- 当前默认环境示例：

```txt
localhost:5432:analytics_db:root:root
```

补充说明：

- 如果数据库不在本机，请将 `localhost` 改成真实主机名或 IP
- 如果计划任务使用的不是当前登录用户，请把 `pgpass.conf` 放到“任务实际运行账号”的 `%APPDATA%\postgresql\` 下
- `refresh_analytics_db.ps1` 会优先复用 `pgpass.conf`；只有在你显式传入 `-DbPassword` 时，才会临时设置 `PGPASSWORD`

如果你不想使用包装脚本，而 `psql` 已经在 PATH 中，也可以直接使用：

```powershell
psql -U root -h localhost -p 5432 -d analytics_db -v ON_ERROR_STOP=1 -c "CALL meta.refresh_analytics_all();"
```

如果 `psql` 不在 PATH 中，请使用 PostgreSQL 安装目录下的完整路径，或者使用 pgAdmin / 其他 SQL 客户端执行。

### 10.3 建议频率

- `rb_position_data` 相关分析：每 `5` 分钟
- 缺陷汇总相关分析：每 `15` 到 `30` 分钟
- carbody 增量刷新：每 `5` 分钟（增量批次几十~几百条，开销低）
- carbody 每周兜底：全量重刷 ODS + DIM，清理源库已滚动删除的过期行

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
