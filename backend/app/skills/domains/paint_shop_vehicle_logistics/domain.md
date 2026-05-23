# 涂装车间车身物流与追踪系统架构

修改时间：2026-05-13 Asia/Shanghai

主要修改内容：
- 重构领域知识，严格剥离缺陷/质量数据，专攻物流与追踪。
- 将对象划分为“实时在制层（WIP）”与“历史生命周期层（History）”。
- 新增 `ods.carbody_history` 和 `dim.carbody_registry` 的查询口径说明。
- 明确历史吞吐量计算与实时截面总览的边界。

## 领域定位与红线

**核心职责**：管“在哪儿（当前）”、“去过哪儿（历史）”、“数量多少（产能/吞吐/堆积）”。
**技能切换**：
1. 包含任何与缺陷（defect）、检测工位（station）、缺陷率相关的查询推荐使用`paint_shop_defect_analysis`技能。
2. 遇到需要查询质量/缺陷率的问题，请引导用户或切换至 `paint_shop_defect_analytics` 技能。
3. `carbody` 数据代表历史事件流水，而 `rb_position_data`（及其派生表）代表滚床当前的传感器截面。严禁在写 SQL 时混用两者的逻辑。
4. 用户问车身顺序、前后车相关问题，推荐`paint_shop_defect_analysis`技能的`vehicle_adjacent_defects`。

---

## 1. 实时在制层 (Current WIP - 基于滚床截面)

当用户询问“**现在/当前**”的状态时，请根据场景选择以下对象（字段详情参见 Section 3）：

### 1.1 当前现场总览
- **推荐对象**：`mart.mart_position_current_overview`
- **语义**：当前现场总览分析对象，一条记录表示一个当前有效占位。
- **适用问题**：
  - 当前现场总共有多少占位？
  - 当前正式产品车和异常车分别多少？
  - 当前各区域车辆分布（产能负荷）？

### 1.2 正式产品车当前精确定位
- **推荐对象**：`fct.fct_vehicle_position_current`
- **语义**：专用于正式产品车的定位事实（已过滤异常车与空占位）。
- **适用问题**：
  - 某台具体正式产品车（如 `vehicle_id LIKE '782026%'`）当前确切位置在哪？

### 1.3 异常车与空位实时监控
- **推荐对象**：`mart.mart_abnormal_vehicle_current`
- **语义**：专门用于现场异常排查（异常车仅在制阶段存在）。
- **适用问题**：
  - 当前车间内有哪些异常车（如空占位、非产品前缀的调试车）？
  - 哪些 `carrier_id` 挂载着异常数据？

---

## 2. 历史生命周期层 (Historical Lifecycle - 基于 Carbody)

当用户询问“**过去/历史/昨天/全生命周期**”以及**历史真实吞吐量**时，请根据场景选择以下对象（字段详情参见 Section 3）：

### 2.1 全量车身字典
- **推荐对象**：`dim.carbody_registry`
- **语义**：基于车身生命周期的权威维度表，每辆车一行。
- **适用问题**：
  - 车身 782026xxx 是什么时候上线的（出生时间）？什么时候下线的（离线时间）？
  - 这辆车的车型、颜色是什么？

### 2.2 真实历史过点流水与吞吐量
- **推荐对象**：`ods.carbody_history`
- **语义**：记录所有车辆历史移动轨迹的流水表。
- **适用问题**：
  - 重绘某辆车的完整车间移动轨迹（去过哪儿）。
  - 计算过去特定时间段（如昨天），各工段的实际通过量（真实吞吐量）。

---

## 3. 技术参考：数据表 Schema 与关系

Agent 在编写查询时应参考本章节获取准确的字段名称和数据类型。

### 3.1 核心数据表 Schema

**1. `ods.rb_position_data` (实时采集原始流水)**
- **描述**：存储滚床/链条采集点的原始车辆状态信息。
- **字段说明**：
  - `"id"` (BIGINT): 自增主键
  - `"plc"`: 所属 PLC 设备名称
  - `"rb_index"`: 滚床/链条储存位编号（物理位置）
  - `"process_area"`: 生产工艺区域名称（如：前道电泳、面漆）
  - `"carrier_id"`: 载体唯一标识（滑橇/挂具号）
  - `"carrier_type"`: 载体类型代码（关联 `carrier_types`）
  - `"vehicle_id"`: 车身唯一标识 ID（14位长度）
  - `"body_type"`: 车身类型代码（关联 `vehicle_body_types`）
  - `"color_code"`: 颜色代码（关联 `vehicle_color_codes`）
  - `"platform_code"`: 车型平台代码
  - `"position_created_at"` (TIMESTAMPTZ): 该位置记录首次被创建的时间
  - `"vehicle_updated_at"` (TIMESTAMPTZ): 该位置上车辆数据最后更新的时间

**2. `ods.carbody_history` (历史生命周期流水)**
- **描述**：所有车辆历史过点的明细记录，用于计算产量和轨迹。
- **字段说明**：
  - `"ID"` (BIGINT): 自增主键
  - `"BODY_ID"` (VARCHAR): 车身号（对应实时表的 `vehicle_id`）
  - `"DATE_EVT"` (TIMESTAMP): 事件发生/过站的精确时间
  - `"RW_STATION_ID"` (VARCHAR): 过站的工位或逻辑节点 ID

**3. `dim.carbody_registry` (全量车身字典)**
- **描述**：聚合自历史流水的车身维度表，用于查询车辆静态属性和生命周期。
- **字段说明**：
  - `"vehicle_id"` (PK): 车身号唯一标识
  - `"first_seen_at"`: 首次进入车间的时间（出生时间）
  - `"last_seen_at"`: 最后离开车间的时间（离线时间）
  - `"first_rw_station"`: 首次过站的位置
  - `"last_rw_station"`: 最后过站的位置
  - `"station_pass_count"` (INT): 历史累计过站总次数
  - `"body_type"`, `"platform_code"`, `"color_code"`: 从底层同步的车辆属性

**4. `mart.mart_position_current_overview` (当前现场总览)**
- **描述**：经过清洗的实时快照，包含异常车和载体类型翻译。
- **字段说明**：
  - `position_id`: 位置唯一标识
  - `entity_type`: 实体类型（`product_vehicle`: 正式产品车, `abnormal_vehicle`: 异常车）
  - `process_area`: 生产工艺区域名称
  - `carrier_id`: 载体号
  - `carrier_type_name_cn`: 载体类型中文（如：滑橇、滑杠）
  - `vehicle_id`: 当前车身号
  - `vehicle_updated_at`: 车辆在当前位置的最后更新时间

**5. `fct.fct_vehicle_position_current` (正式车当前定位)**
- **描述**：仅包含正式产品车的实时定位，已排除干扰数据。
- **字段说明**：
  - `vehicle_id`: 车身号
  - `process_area`: 当前所属工艺区域
  - `carrier_id`: 当前载体号
  - `full_rb_code`: 完整的滚床编号（逻辑索引）

### 3.2 辅助维度表 Schema

- **`dim.dim_process_area` (区域字典)**
  - `process_area_name` (PK): 区域名称
  - `description`: 区域详细中文说明
  - `sort_order`: 在工艺流程中的先后顺序
- **`ods.carrier_types` (载体字典)**
  - `type_code` (PK): 类型代码
  - `type_name_cn`: 类型中文名称（如：撬、挂、杠）
- **`ods.vehicle_body_types` (车型字典)**
  - `body_type` (PK): 车型代码
  - `type_name`: 车型名称（如：Tiguan、Lavida）
- **`ods.vehicle_color_codes` (颜色字典)**
  - `color_code` (PK): 颜色代码
  - `color_name`: 颜色中文描述

### 3.3 核心业务规则

**1. 有效正式产品车判断**
- `vehicle_id LIKE '782026%'` AND `body_type != '-----'` AND `carrier_id != '0'`。

**2. 异常车与空位判定**
- 异常车：`carrier_id != '0'` AND 不符合产品车规则（通常是传感器误报或测试车）。
- 空位：`vehicle_id` 为空且 `carrier_id = '0'`。

**3. 原始车身字符串解析 (针对 raw_data)**
- 0-13: `vehicle_id`, 14-18: `body_type`, 19-22: `color_code`, 23-25: `platform_code`

### 3.4 表关系图谱 (JOIN 键)

- **实时关联流水线**：
  - `ods.rb_position_data.process_area` -> `dim.dim_process_area.process_area_name`
  - `ods.rb_position_data.carrier_type` -> `ods.carrier_types.type_code`
  - `ods.rb_position_data.body_type` -> `ods.vehicle_body_types.body_type`
  - `ods.rb_position_data.color_code` -> `ods.vehicle_color_codes.color_code`
- **历史溯源流水线**：
  - `ods.carbody_history.BODY_ID` -> `dim.carbody_registry.vehicle_id`

---

## 4. 查询易错点 (Gotchas)
- **实时 vs 历史**：查“昨天产量”禁产用 `mart` 快照表，必须用 `ods.carbody_history`。
- **强制使用双引号**：对 `ods.carbody_history` 和 `dim.carbody_registry` 的大写列名（`"BODY_ID"`, `"DATE_EVT"`, `"RW_STATION_ID"`）**必须加双引号**。
- **正式车过滤**：统计历史产量或轨迹时，习惯性过滤 `"BODY_ID" LIKE '78%'` 以排除测试数据。
