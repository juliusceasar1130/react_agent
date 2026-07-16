# 涂装车间车身物流与追踪系统架构

修改时间：2026-07-04 Asia/Shanghai

主要修改内容：
- **画像表与物化视图字段同步**：对齐了 `dim.dim_vehicle_profile` 画像表扩展后的 9 个车身历史及状态新字段；同步对齐 `dim.carbody_registry` 的 MDS 列及其他属性字段。
- **注释术语统一**：将过站物理位置/工位的描述规范纠正对齐为“过站读写站”，以契合现场读写站（Read-Write Station）设备的实际业务术语。
- 历史修改（2026-05-13）：重构领域知识，严格剥离缺陷数据，专攻物流与追踪；新增 `ods.carbody_history` 和 `dim.carbody_registry` 查询口径说明。

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


**1. `ods.carbody_history` (历史生命周期流水)**
- **描述**：所有车辆历史过点/读写站/RW_STATION的明细记录，用于计算产量和轨迹。
- **字段说明**：
  - `"BODY_ID"` (VARCHAR): 车身号（对应实时表的 `vehicle_id`）
  - `"DATE_EVT"` (TIMESTAMP): 事件发生/过站的精确时间
  - `"RW_STATION_ID"` (VARCHAR): 过站的工位或逻辑节点 ID

**2. `dim.carbody_registry` (全量车身字典)**
- **描述**：聚合自历史流水ods.carbody_history的车身维度表，保留首次和末次读写站信息
- **字段说明**：
  - `"vehicle_id"` (PK): 车身号唯一标识
  - `"first_seen_at"`: 首次过站读写站时间（最先记录时间）
  - `"last_seen_at"`: 末次过站读写站时间（最后记录时间）
  - `"first_rw_station"`: 首次过站读写站编码
  - `"last_rw_station"`: 末次过站读写站编码
  - `"first_body_type"`: 入口车身类型
  - `"last_body_type"`: 出口车身类型
  - `"station_pass_count"` (INT): 历史累计过站总频次
  - `"body_type"`: 车型代码
  - `"platform_code"`: 平台代码
  - `"color_code"`: 颜色代码
  - `"black_roof_flag"`: 黑顶标记 (1/Y表示黑顶)
  - `"rework_flag"`: 返修车标记 (1/Y表示返修车)
  - `"reserved_1"`: 车身 MDS 备用字段 1
  - `"reserved_2"`: 车身 MDS 备用字段 2
  - `"SKID_ID"`: 雪橇号、载具，同carrier_id

**3. `mart.mart_position_current_overview` (基于位置的实时采集数据)**
- **描述**：包含异常车和载体类型属性。
- **字段说明**：
  - `position_id`: 位置唯一标识
  - `entity_type`: 实体类型（`product_vehicle`: 正式产品车, `abnormal_vehicle`: 异常车）
  - `process_area`: 生产工艺区域名称
  - `carrier_id`: 载体号
  - `carrier_type`: 载体类型
  - `carrier_type_name_cn`: 载体类型中文
  - `vehicle_id`: 当前车身号
  - `vehicle_updated_at`: 车辆在当前位置的最后更新时间
  - `"plc"`: 所属 PLC 设备名称
  - `"rb_index"`: 滚床/链条储存位编号（物理位置）


### 3.2 辅助及主维度表 Schema

- **`dim.dim_vehicle_profile` 车辆核心属性主维度表 (全量车辆的一车一档台账)**
  - `vehicle_id` (PK): 车辆唯一识别码
  - `body_type`: 车型代码（优先滚床，其次车身）
  - `tracking_type_name`: 车型中文名
  - `defect_model`: 缺陷检测代码
  - `defect_type_name`: 检测车型名称
  - `platform_code`, `platform_name`: 平台代码与中文名
  - `color_code`, `color_name`: 颜色代码与中文名
  - `is_black_roof`: 是否黑色车顶 (滚床黑顶或缺陷包含“黑”或车身黑顶)
  - `is_rework`: 是否重工车 (根据车身重工标记 rework_flag 计算)
  - `has_defect_record`: 是否存在缺陷检测记录 
  - `defect_last_seen_at`: 缺陷系统最后检测时间
  - `carbody_first_seen_at`, `carbody_last_seen_at`: 首次/末次过站读写站时间
  - `carbody_first_rw_station`, `carbody_last_rw_station`: 首次/末次过站读写站编码
  - `carbody_station_pass_count`: 累计过站读写站总频次
  - `current_position_id`, `current_carrier_id`, `current_process_area`, `current_full_rb_code`, `current_position_updated_at`: 当前最新在制位置追踪及载具快照信息

- **`ods.process_area` (区域字典)**
  - `area_name`: 区域名称(唯一)
  - `description`: 区域详细中文说明
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
  - `mart.mart_position_current_overview.process_area` -> `ods.process_area.area_name`
  - `mart.mart_position_current_overview.carrier_type` -> `ods.carrier_types.type_code`
  - `mart.mart_position_current_overview.body_type` -> `ods.vehicle_body_types.body_type`
  - `mart.mart_position_current_overview.color_code` -> `ods.vehicle_color_codes.color_code`
- **历史溯源流水线**：
  - `ods.carbody_history.BODY_ID` -> `dim.carbody_registry.vehicle_id`

---

## 4. 查询易错点 (Gotchas)
- **实时 vs 历史**：查“昨天产量”禁产用 `mart` 快照表，必须用 `ods.carbody_history`。
- **强制使用双引号**：对 `ods.carbody_history` 和 `dim.carbody_registry` 的大写列名（`"BODY_ID"`, `"DATE_EVT"`, `"RW_STATION_ID"`）**必须加双引号**。
- **正式车过滤**：统计历史产量或轨迹时，习惯性过滤 `"BODY_ID" LIKE '78%'` 以排除测试数据。
