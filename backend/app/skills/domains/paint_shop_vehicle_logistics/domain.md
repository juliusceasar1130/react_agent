# 涂装车间车身物流与追踪系统架构

修改时间：2026-07-29 Asia/Shanghai

## 领域定位与红线

**核心职责**：管“在哪儿（当前）”、“去过哪儿（历史）”、“数量多少（产能/吞吐/堆积）、车身类型分类”。
**技能切换**：
1. 包含任何与缺陷（defect）、检测工位（station）、缺陷率相关的查询推荐使用 `paint_shop_defect_analysis` 技能。
2. 遇到需要查询质量/缺陷率的问题，请引导用户或切换至 `paint_shop_defect_analysis` 技能。
3. `carbody` 数据代表历史事件流水，而 `rb_position_data`（及其派生表）代表滚床当前的传感器截面。严禁在写 SQL 时混用两者的逻辑。
4. 用户问车身顺序、前后车相关问题，推荐 `paint_shop_defect_analysis` 技能的 `vehicle_adjacent_defects`。

---

## 1. 实时在制层 (Current WIP - 基于滚床截面)

当用户询问“**现在/当前**”的状态时，请根据场景选择以下对象（字段详情参见 Section 3）：

### 1.1 当前现场总览
- **推荐对象**：`mart.mart_position_current_overview`
- **语义**：当前现场总览分析对象，一条记录表示一个当前有效占位。
- **实体类型包含**：`project_vehicle`（项目车）、`product_vehicle`（产品车/量产车）、`abnormal_vehicle`（异常车）。
- **适用问题**：
  - 当前现场总共有多少占位？
  - 当前项目车、量产车和异常车分别有多少？
  - 当前各区域车辆分布（产能负荷）？

### 1.2 正常车（项目车与量产车）当前精确定位
- **推荐对象**：`fct.fct_vehicle_position_current`
- **语义**：专用于正常车（包括项目车与量产车）的定位事实（已自动过滤异常车与空占位）。
- **适用问题**：
  - 某台具体正常车（如 VIN 或指定项目车编号 `project_vehicle_no`）当前确切位置在哪？

### 1.3 异常车与空位实时监控
- **推荐对象**：`mart.mart_abnormal_vehicle_current` 或 `fct.fct_abnormal_vehicle_current`
- **语义**：专门用于现场异常排查（异常车仅在制阶段存在）。
- **适用问题**：
  - 当前车间内有哪些异常车？
  - 哪些 `carrier_id` 挂载着异常数据？

---

## 2. 历史生命周期层 (Historical Lifecycle - 基于 Carbody)

当用户询问“**过去/历史/昨天/全生命周期**”以及**历史真实吞吐量**时，请根据场景选择以下对象（字段详情参见 Section 3）：

### 2.1 全量车身字典
- **推荐对象**：`dim.carbody_registry`
- **语义**：基于车身生命周期的权威维度表，每辆车一行（透传 `project_vehicle_no` 项目车编号）。
- **适用问题**：
  - 车身 782026xxx 是什么时候上线的（出生时间）？什么时候下线的（离线时间）？
  - 这辆车的车型、颜色、项目车编号是什么？

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
- **关键字段**：`"BODY_ID"` (车身号), `"DATE_EVT"` (过站时间), `"RW_STATION_ID"` (读写站ID)

**2. `dim.carbody_registry` (全量车身字典)**
- **描述**：聚合自历史流水的车身维度表，保留首次/末次过站读写站及滞留节点信息。
- **关键字段**：
  - `"vehicle_id"` (PK): 车身号唯一标识
  - `"project_vehicle_no"`: 项目车编号 (外键关联项目车订单表)
  - `"first_seen_at"`, `"last_seen_at"`: 首次/末次过站读写站时间
  - `"first_rw_station"`, `"last_rw_station"`: 首次/末次过站读写站编码
  - `"retention_checkpoint_station"`: 滞留监控关键读写站编码 (1J440RB, K3IS140, K2IS075, K1IS135 中最新经过的节点)
  - `"retention_checkpoint_pass_at"`: 滞留监控关键读写站过站时间
  - `"station_pass_count"`: 历史累计过站总频次
  - `"body_type"`, `"platform_code"`, `"color_code"`, `"black_roof_flag"`, `"rework_flag"`

**3. `mart.mart_position_current_overview` (当前滚床占位全景总览)**
- **描述**：当前现场所有占位全景视图（含项目车、量产车、异常车）。
- **关键字段**：
  - `position_id`: 位置唯一标识
  - `entity_type`: 占位实体类型 (`project_vehicle`: 项目车, `product_vehicle`: 产品车/量产车, `abnormal_vehicle`: 异常车)
  - `entity_type_name`: 占位实体类型中文名 ('项目车', '产品车(量产车)', '异常车')
  - `vehicle_status_code`, `vehicle_status_name`: 车辆状态分类代码与中文名
  - `abnormal_type`: 异常占位分类 (正常车恒为 NULL)
  - `abnormal_reason`: 异常原因说明 (正常车恒为 NULL)
  - `project_vehicle_no`: 项目车编号 (若匹配到项目车)
  - `process_area`: 生产工艺区域名称
  - `carrier_id`, `carrier_type`, `carrier_type_name_cn`: 载体及中文名
  - `vehicle_id`: 当前车身号
  - `is_black_roof`, `is_rework`: 是否黑顶、是否返修车
  - `plc`, `rb_index`, `full_rb_code`: 所属 PLC 及完整滚床物理编码

### 3.2 辅助及主维度表 Schema

- **`ods.ods_fis_project_vehicle_orders` (项目车生产订单贴源表)**
  - `project_vehicle_no` (PK): 项目车编号 (如 PP2-EREV-VFF-56)
  - `composite_pin_no`: 合成 PIN 识别码 (13位，关联条件：`LEFT(trim(rb.vehicle_id), 13) = pvo.composite_pin_no`)
  - `project_stage`: 项目阶段 (如 VFF, PT)
  - `kom_no`: KOM 订货号
  - `knr_no`: KNR 生产流水号

- **`dim.dim_vehicle_profile` (车辆核心属性主维度表 - 一车一档台账)**
  - `vehicle_id` (PK): 车辆唯一识别码
  - `project_vehicle_no`: 项目车编号 (关联 FIS 订单表)
  - `body_type`, `tracking_type_name`: 车型代码与中文名
  - `platform_code`, `platform_name`: 平台代码与中文名
  - `color_code`, `color_name`: 颜色代码与中文名
  - `is_black_roof`, `is_rework`, `has_defect_record`: 综合判定标记
  - `retention_checkpoint_station`, `retention_checkpoint_pass_at`: 滞留监控关键节点及过站时间
  - `current_position_id`, `current_carrier_id`, `current_process_area`, `current_full_rb_code`: 当前最新在制位置与载具快照

- **基础字典表**：`ods.process_areas` (区域字典), `ods.carrier_types` (载体字典), `ods.vehicle_body_types` (车型字典), `ods.vehicle_color_codes` (颜色字典)。

### 3.3 核心业务规则与判定算法

#### 1. 车辆分类三元组规则 (`entity_type`)
基于滚床位置与 FIS 项目车订单表关联 (`LEFT(trim(rb.vehicle_id), 13) = pvo.composite_pin_no`)，按以下优先级判定：
1. **项目车 (`project_vehicle`)**：`project_vehicle_no` 非空非 NULL（**优先级最高**，即使 VIN 为 782026 开头也优先算作项目车）。
2. **产品车/量产车 (`product_vehicle`)**：`project_vehicle_no` 为空，且 `vehicle_id` 以 `'782026'` 开头。
3. **异常车 (`abnormal_vehicle`)**：不属于项目车且不属于产品车的所有其余记录（**兜底**）。

#### 2. 正常车与异常车过滤原则
- **正常车 (Normal Vehicles)**：包含项目车和产品车。查询正常车时使用 `WHERE entity_type IN ('project_vehicle', 'product_vehicle')` 或 `WHERE entity_type <> 'abnormal_vehicle'`。正常车的 `abnormal_type` 和 `abnormal_reason` 恒为 `NULL`。
- **异常车 (Abnormal Vehicles)**：仅当 `entity_type = 'abnormal_vehicle'` 时才评估 `abnormal_type` 细分：
  - `empty_vehicle_id_with_carrier`：`vehicle_id = '--------------'`
  - `blank_vehicle_id_with_carrier`：`vehicle_id` 为 NULL 或空
  - `non_product_prefix`：前缀不是 782026 且无项目车编号

---

## 4. 查询易错点 (Gotchas)

- **实时 vs 历史**：查“昨天产量”禁止用 `mart` 快照表，必须用 `ods.carbody_history`。
- **强制使用双引号**：对 `ods.carbody_history` 和 `dim.carbody_registry` 的大写列名（`"BODY_ID"`, `"DATE_EVT"`, `"RW_STATION_ID"`）**必须加双引号**。
- **正常车包含项目车**：统计正常车数量或分布时，切勿忽略 `project_vehicle`。

---

## 5. LLM 提示词与自然语言映射规范 (System Instruction & Few-Shot)

在处理用户自然语言查询时，按以下映射关系构建 SQL `WHERE` 条件：

| 自然语言查询词 | 标准 SQL 条件 / 查询表指引 |
| :--- | :--- |
| “查所有项目车 / 试验车 / VFF车” | `WHERE entity_type = 'project_vehicle'` |
| “查所有量产车 / 正式产品车” | `WHERE entity_type = 'product_vehicle'` |
| “正常车有多少辆？” | `WHERE entity_type IN ('project_vehicle', 'product_vehicle')` |
| “有哪些异常车？是什么原因？” | `SELECT vehicle_id, abnormal_type, abnormal_reason FROM fct.fct_abnormal_vehicle_current` |
| “查项目车订单 / KOM号 / PIN码” | `SELECT * FROM ods.ods_fis_project_vehicle_orders WHERE project_vehicle_no = ...` |
