# 涂装车间车身物流与追踪系统架构

修改时间：2026-05-13 Asia/Shanghai

主要修改内容：
- 重构领域知识，严格剥离缺陷/质量数据，专攻物流与追踪。
- 将对象划分为“实时在制层（WIP）”与“历史生命周期层（History）”。
- 新增 `ods.carbody_history` 和 `dim.carbody_registry` 的查询口径说明。
- 明确历史吞吐量计算与实时截面总览的边界。

## 领域定位与红线

**核心职责**：管“在哪儿（当前）”、“去过哪儿（历史）”、“数量多少（产能/吞吐/堆积）”。
**绝对红线**：
1. 本领域**禁止**包含任何与缺陷（defect）、检测工位（station）、缺陷率相关的查询。
2. 遇到需要查询质量/缺陷率的问题，请引导用户或切换至 `paint_shop_defect_analytics` 技能。
3. `carbody` 数据代表历史事件流水，而 `rb_position_data`（及其派生表）代表滚床当前的传感器截面。严禁在写 SQL 时混用两者的逻辑。

---

## 1. 实时在制层 (Current WIP - 基于滚床截面)

当用户询问“**现在/当前**”的状态时，只能使用以下表：

### 1.1 当前现场总览
- **推荐对象**：`mart.mart_position_current_overview`
- **描述**：当前现场总览分析对象，一条记录表示一个当前有效占位。
- **适用问题**：
  - 当前现场总共有多少占位？
  - 当前正式产品车和异常车分别多少？
  - 当前各区域车辆分布（产能负荷）？
- **关键字段**：
  - `position_id`：当前占位唯一标识
  - `entity_type`：当前占位类型（区分 `product_vehicle` 和 `abnormal_vehicle`）
  - `process_area`：当前所在工艺区域
  - `carrier_id` / `carrier_type_name_cn`：当前载体
  - `vehicle_id`：车身 ID
  - `vehicle_updated_at`：车辆数据最后更新时间

### 1.2 正式产品车当前精确定位
- **推荐对象**：`fct.fct_vehicle_position_current`
- **语义**：只表示正式产品车当前事实（已过滤异常车）。
- **适用问题**：
  - 某台具体正式产品车（如 `vehicle_id LIKE '782026%'`）当前确切位置在哪？
- **关键字段**：
  - `vehicle_id`, `process_area`, `carrier_id`, `full_rb_code`

### 1.3 异常车与空位实时监控
- **推荐对象**：`mart.mart_abnormal_vehicle_current`
- **语义**：专门用于现场异常排查（异常车仅在制阶段存在）。
- **适用问题**：
  - 当前车间内有哪些异常车（如空占位、非产品前缀的调试车）？
  - 哪些 `carrier_id` 挂载着异常数据？
- **关键字段**：
  - `abnormal_type`（异常类型编码）
  - `abnormal_reason`（异常原因中文描述）

---

## 2. 历史生命周期层 (Historical Lifecycle - 基于 Carbody)

当用户询问“**过去/历史/昨天/全生命周期**”以及**历史真实吞吐量**时，只能使用以下表：

### 2.1 全量车身字典
- **推荐对象**：`dim.carbody_registry`
- **语义**：基于车身生命周期的权威维度表，每辆车一行。
- **适用问题**：
  - 车身 782026xxx 是什么时候上线的（出生时间）？什么时候下线的（离线时间）？
  - 这辆车的车型、颜色是什么？
- **关键字段**：
  - `vehicle_id`：车身唯一标识
  - `first_seen_at`：首次过站时间
  - `last_seen_at`：末次过站时间
  - `first_rw_station` / `last_rw_station`：首/末次过站位置
  - `body_type`, `platform_code`, `color_code`：核心属性

### 2.2 真实历史过点流水与吞吐量
- **推荐对象**：`ods.carbody_history`
- **语义**：记录所有车辆历史移动轨迹的流水表。
- **适用问题**：
  - 重绘某辆车的完整车间移动轨迹（去过哪儿）。
  - 计算过去特定时间段（如昨天），各工段的实际通过量（真实吞吐量）。
- **关键字段**：
  - `BODY_ID`：车身号（对应 vehicle_id）
  - `DATE_EVT`：事件过站时间
  - `RW_STATION_ID`：工位/节点 ID

## 4. 底层表 Schema 与表关系 (用于回答随机问题)

为了应对用户的随机问题或临时分析，Agent 需要了解底层表的详细结构。

### 4.1 核心数据表 Schema

**1. `ods.rb_position_data` (实时采集流水)**
- **描述**：存储所有采集点及当前位置的车辆状态信息的原始数据。
- **关键字段**：
  - `"id"` (BIGINT)：主键
  - `"plc"` (VARCHAR)：所属 PLC 设备名称
  - `"rb_index"` (VARCHAR)：滚床/链条储存位编号
  - `"process_area"` (VARCHAR)：生产工艺区域名称，对应 `dim_process_area.process_area_name`
  - `"carrier_id"` (VARCHAR)：载体唯一标识（如滑橇号）
  - `"carrier_type"` (VARCHAR)：载体类型代码，对应 `carrier_types.type_code`
  - `"vehicle_id"` (VARCHAR)：车身唯一标识 ID（14位）
  - `"body_type"` (VARCHAR)：车身类型代码（5位）
  - `"color_code"` (VARCHAR)：颜色代码（4位）
  - `"platform_code"` (VARCHAR)：车型平台代码（3位）
  - `"position_created_at"` (TIMESTAMPTZ)：该位置记录首次被创建的时间
  - `"vehicle_updated_at"` (TIMESTAMPTZ)：该位置上车辆数据最后更新的时间

**2. `ods.carbody_history` (历史生命周期流水)**
- **描述**：存储车间内所有历史过点的明细记录，是计算历史产量和轨迹的基石。
- **关键字段**：
  - `"ID"` (BIGINT)：主键
  - `"BODY_ID"` (VARCHAR)：车身号（对应 rb 的 vehicle_id）
  - `"DATE_EVT"` (TIMESTAMP)：事件发生/过站时间
  - `"RW_STATION_ID"` (VARCHAR)：工位或节点 ID

**3. `dim.carbody_registry` (全量车身字典)**
- **描述**：聚合自历史流水的全量车身维度表，用于查询车辆的出生、离线时间和静态属性。
- **关键字段**：
  - `"vehicle_id"` (VARCHAR)：车身号，主键
  - `"first_seen_at"` / `"last_seen_at"` (TIMESTAMP)：首次 / 末次过站时间
  - `"first_rw_station"` / `"last_rw_station"` (VARCHAR)：首次 / 末次过站位置
  - `"station_pass_count"` (INTEGER)：历史总过站次数
  - `"body_type"`, `"platform_code"`, `"color_code"` (VARCHAR)：从 MDS 提取的车型、平台、颜色代码

### 4.2 辅助维度表 Schema

- **`dim.dim_process_area`**：生产工艺区域字典
  - `process_area_name` (PK), `description` (区域中文说明), `sort_order` (工艺流程顺序)
- **`ods.carrier_types`**：载体类型字典
  - `type_code` (PK), `type_name_cn` (载体类型中文名称, 如挂具/滑橇)
- **`ods.vehicle_body_types`**：车型代码字典
  - `body_type` (PK), `type_name` (车型名称, 如 Tiguan、E7)
- **`ods.vehicle_color_codes`**：颜色字典
  - `color_code` (PK), `color_name` (颜色名称)

### 4.3 核心业务规则与数据解析

**1. 有效正式产品车判断规则**
- 必须同时满足：`vehicle_id LIKE '782026%'` 且 `body_type != '-----'` 且 `carrier_id != '0'`。
- *(注：fct_vehicle_position_current 已经内置了此规则)*

**2. 异常车与空位判定**
- 如果载体不为空 (`carrier_id != '0'`)，但车身号不符合产品车规则，即为异常车。
- 空占位/无车：`vehicle_id = '--------------'` 且 `body_type = '-----'` 且 `carrier_id = '0'`。

**3. 原始车身字符串解析 (针对 raw_data)**
- 第 0-13 位：车身唯一标识 ID (`vehicle_id`)
- 第 14-18 位：车身类型代码 (`body_type`)
- 第 19-22 位：颜色代码 (`color_code`)
- 第 23-25 位：车型平台代码 (`platform_code`)

### 4.4 表关系图谱 (JOIN 键)

在编写跨表查询时，请遵循以下 JOIN 关系：

```text
1. 基于实时采集的关联：
ods.rb_position_data (或 fct / mart)
 ├── process_area -> dim.dim_process_area.process_area_name
 ├── carrier_type -> ods.carrier_types.type_code
 ├── body_type    -> ods.vehicle_body_types.body_type
 ├── color_code   -> ods.vehicle_color_codes.color_code
 └── platform_code-> ods.vehicle_platforms.platform_code

2. 基于历史溯源的关联：
ods.carbody_history
 └── BODY_ID      -> dim.carbody_registry.vehicle_id
```

## 5. 查询易错点 (Gotchas)
- **不要混淆实时快照与历史流水**：计算“昨天某个区域的产量”，绝对不能用 `mart_position_current_overview`（因为那是当前快照），必须使用 `ods.carbody_history` 根据 `"DATE_EVT"` 统计。
- **强制使用双引号**：PostgreSQL 对大写列名敏感。对于 `ods.carbody_history` 和 `dim.carbody_registry` 中的大写字段（如 `"BODY_ID"`, `"DATE_EVT"`, `"RW_STATION_ID"`），**必须在 SQL 中使用双引号包裹**，否则会报 `UndefinedColumn` 错误。
- **异常车的边界**：异常车通常是传感器层面的采集问题或调试用空车身，因此查历史产量或历史轨迹时，应当专注于正式产品车（如 `"BODY_ID" LIKE '78%'`）。
