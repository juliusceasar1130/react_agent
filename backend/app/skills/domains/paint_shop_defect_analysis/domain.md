# 涂装车间质量缺陷分析架构

修改时间：2026-07-04 Asia/Shanghai

主要修改内容：
- **新增漏检与未检测车辆监控场景**：设计并集成了 `leak_detection` 场景，支持基于过点读写站（`L3ACC21IS01`/`02`/`03`）过车事件对齐检测事实全局查询漏检及检测失败车辆。
- **重构架构体系以对齐物流追踪文档**：将质量缺陷领域知识重构为“WIP/实时质量关联层”与“历史/检测事件事实层”双层架构，统一技术参考 Schema、业务规则与关系图谱排版。
- **对齐画像表与集市字段升级**：同步 `dim.dim_vehicle_profile` 画像表与 `mart.mart_vehicle_quality_360` 视图字段，支持物理车身过站汇总属性 (如 `carbody_first_seen_at` 等) 联查。
- 历史修改（2026-07-04）：补充大模型关联缺陷明细表时防止车数翻倍统计（数据扇出效应）的防错军规与 SQL 示例；历史修改（2026-04-12）新增质量缺陷分析领域文档。

## 领域定位与红线

**核心职责**：分析车型缺陷趋势、部位分布、tunnel/cycle 对比和黑车顶对比等质量指标。
**技能切换**：
1. 本技能专攻缺陷/质量分析（WIP与历史检测事实）。
2. 如果问题仅涉及纯物流追踪（如“在哪儿”、“堆积数量”、“区域分布”、“过站产量计数”而不涉及缺陷/质量数据），推荐切换至 `paint_shop_vehicle_logistics` 技能。
3. 质量分析在统计车数与合格率时，必须提防因一车多检/一车多缺陷引发的“数据扇出效应”（车数翻倍）。

---

## 1. WIP / 实时质量关联层 (WIP & Current Quality)

当用户询问“**当前/在产/在制**”车辆的质量分布或关联位置时，请使用以下对象：

### 1.1 车辆 360 度质量与当前位置全景关联
- **推荐对象**：`mart.mart_vehicle_quality_360`
- **语义**：车辆 360 度质量与当前最新位置关联明细表，基于车身过站富集表驱动，包含在产未检车辆与漏检车辆。
- **注意**：该表是以“一次检测事件”或“一个车身号”为粒度的。如果与车辆维度表关联，请务必注意去重。
- **适用问题**：
  - 某个工艺区域在产车辆的缺陷分布如何？
  - 当前在产车辆中，哪些车身存在未检出或缺陷记录？
  - 黑车顶和非黑车顶缺陷对比？

---

## 2. 历史 / 检测事件事实层 (History & Events)

当用户询问“**过去/历史/某时间段**”的检测数据、缺陷趋势或事实流水时，请使用以下对象：

### 2.1 缺陷检测事件事实
- **推荐对象**：`fct.fct_vehicle_defect_detection`
- **语义**：缺陷检测事实表，一条记录代表一次检测，专用于分析历史检测事实。
- **适用问题**：
  - 某车型的历史缺陷检测趋势？
  - 某时间范围内各车型的平均单次检测缺陷数？
  - 不同 `tunnel` (检测通道) 的缺陷总量对比？

### 2.2 车身中心质量富集全量表
- **推荐对象**：`fct.fct_vehicle_defect_enriched`
- **语义**：以物理车身（carbody）为中心的质量富集全量表，LEFT JOIN 缺陷事件，保留物理车身过站与最新缺陷双源属性。支持识别在产未检车辆与漏检车辆。
- **适用问题**：
  - 统计有多少车辆通过了检测？有多少车辆漏检（未检测）？
  - 分析累计过站频次过高（返修）的车辆与缺陷记录的关系？

### 2.3 漏检与未检测车辆监控 (过检测口无检测事实)
- **推荐对象**：`ods.carbody_history` & `fct.fct_vehicle_defect_detection` 关联
- **语义**：通过面漆 3 个检测线入口读写站（`L3ACC21IS01`/`02`/`03`）锁定已到达检测口的车辆，与 `fct.fct_vehicle_defect_detection` 进行全局 `LEFT JOIN d.vehicle_id = h.BODY_ID`，筛选 `history_id IS NULL` 的车身以精准监控漏检。
- **适用问题**：
  - 分析指定过站时间范围内（比如昨天、今天上午等），通过了检测通道入口但未检测的漏检车。

---

## 3. 技术参考：数据表 Schema 与关系

Agent 在编写查询时应参考本章节获取准确的字段名称和数据类型。

### 3.1 核心数据表 Schema

**1. `mart.mart_vehicle_quality_360` (车辆 360 质量与当前位置关联)**
- **描述**：集成当前最新位置与历史缺陷记录的分析宽表，粒度为一检测事件一行（无缺陷车则一车一行）。
- **字段说明**：
  - `history_id`: 唯一主键ID (缺陷事件主键，未检测车辆则为NULL)
  - `vehicle_id`: 车身唯一识别码
  - `detect_time`: 缺陷检测时间
  - `defect_model`: 检测程序代码
  - `defect_type_name`: 缺陷检测类型名
  - `defect_black_roof`: 缺陷系统原始黑顶描述
  - `defect_color_code`: 缺陷系统颜色代码
  - `tunnel`: 检测通道
  - `cycle`: 检测次数
  - `station_1_defect_count` (右侧), `station_2_defect_count` (左侧), `station_3_defect_count` (车顶), `station_4_defect_count` (前盖), `station_5_defect_count` (尾门) 的缺陷数
  - `total_defect_count`: 总缺陷数
  - `has_defect_record`: 是否存在缺陷检测记录 (TRUE/FALSE)
  - `body_type`: 车型代码 (优先滚床，其次车身)
  - `tracking_type_name`: 车型中文名
  - `tracking_color_code`, `tracking_color_name`: 车辆当前所处的跟踪系统颜色代码与中文名
  - `platform_code`, `platform_name`: 平台代码与中文名
  - `black_roof_flag`, `rework_flag`: 滚床跟踪系统原始黑顶/返修车标记
  - `carbody_first_seen_at`, `carbody_last_seen_at`: 首次/末次过站读写站时间
  - `carbody_first_rw_station`, `carbody_last_rw_station`: 首次/末次过站读写站编码
  - `carbody_station_pass_count`: 累计过站读写站总频次
  - `process_area`: 车辆当前所在的工艺区域
  - `plc`, `rb_index`, `full_rb_code`: 车辆当前位置的PLC、滚床索引与完整滚床物理编码
  - `carrier_id`, `carrier_type`, `carrier_type_name_cn`: 载体 ID、类型代码与中文载具类型名
  - `position_created_at`, `vehicle_updated_at`: 位置创建时间与车辆当前位置刷新时间

**2. `fct.fct_vehicle_defect_detection` (缺陷检测事实层)**
- **描述**：缺陷检测记录事件流水。一车因多次检测可有多条记录。
- **字段说明**：
  - `history_id` (PK): 检测历史 ID
  - `vehicle_id`: 车辆唯一识别码 (等同于 ODS 中的 `serial_number`)
  - `model`: 检测程序代码
  - `type_name`: 缺陷检测系统记录的检测车型名称
  - `black_roof`: 缺陷系统原始黑顶描述
  - `detect_time`: 检测发生时间
  - `color_code`: 缺陷颜色代码
  - `tunnel`: 检测通道
  - `cycle`: 车身检测次数
  - `station_1_defect_count` 至 `station_5_defect_count`: 右侧、左侧、车顶、前盖、尾门的缺陷数
  - `total_defect_count`: 总缺陷数

**3. `fct.fct_vehicle_defect_enriched` (以车身为中心的质量富集全量表)**
- **描述**：物理车身维度与缺陷明细的富集表。
- **字段说明**：
  - `vehicle_id` (PK): 车身唯一识别码 (等同于 `BODY_ID`)
  - `body_type`, `platform_code`, `color_code`: 物理车身维度属性
  - `black_roof_flag`, `rework_flag`: 物理车身黑顶及返修标记
  - `first_seen_at`, `last_seen_at`: 首次/末次过站读写站时间
  - `first_rw_station`, `last_rw_station`: 首次/末次过站读写站编码
  - `station_pass_count`: 累计过站读写站总频次
  - `history_id`: 关联的缺陷历史ID
  - `defect_model`, `defect_type_name`, `defect_black_roof`, `defect_color_code`: 关联缺陷检测明细
  - `detect_time`: 检测发生时间
  - `tunnel`, `cycle`: 检测通道及次数
  - `station_1_defect_count` 至 `station_5_defect_count` 以及 `total_defect_count`: 缺陷数明细
  - `has_defect_record`: 是否存在缺陷检测记录 (TRUE/FALSE)

### 3.2 辅助及主维度表 Schema

- **`ods.history_station_defect_summary` (缺陷检测汇总贴源数据)**
  - 缺陷事件的原始流水数据。结构等同于 `fct_vehicle_defect_detection`。
- **`dim.dim_vehicle_profile` (车辆主画像表)**
  - 车辆特征的大宽表维度表。结构详见物流追踪技能文档。
- **`ods.vehicle_body_types` (车型字典)**
  - `body_type`: 车型代码，`type_name`: 车型中文名。

### 3.3 核心业务规则与口径

**1. 检测事件与次数统计**
- 一条检测事实代表一次检测，通过 `history_id` 唯一标识。
- `cycle` 表示同一辆车的检测序列号，数值越大表示检测越靠后。

**2. 指标聚合统计核心军规（大模型编写 SQL 时必须严格遵守）：**
- **默认统计口径**：除非用户显式要求统计“缺陷总数”、“缺陷总量”或“累计缺陷数”（要求 `SUM`），否则所有缺陷分析与趋势默认**必须且只能**计算以下两个指标：
  - **检测次数 (detection_count)**: `COUNT(*)`，即检测事件的频次。
  - **平均单次检测缺陷数 (avg_defect_per_detection)**: `AVG(total_defect_count)`。
- **“单车”业务概念澄清**：在此领域中，“单车缺陷”通常指“平均每次检测的缺陷数（`AVG`）”。计算公式 = 检测缺陷总数 / 检测次数。严禁使用唯一车身数（`COUNT(DISTINCT vehicle_id)`）来除总数，除非用户特别指明。

**3. 车数与合格率统计（去重防翻倍军规）：**
- **去重计数**：在任何需要返回“有多少辆车”、“车辆分布”、“合格车数及合格率”的关联 SQL 中，统计车辆数必须使用 `COUNT(DISTINCT vehicle_id)`。直接 `COUNT(*)` 会触发**数据扇出效应 (Fan-out Effect)**，导致车辆数翻倍虚高。
- **CTE 预聚合写法**：对于复杂联合查询，先在子查询中对缺陷表执行 `GROUP BY vehicle_id` 压缩为一车一行，再与维度表做外连，严禁直接外连后对车数进行普通聚合。

**4. 5个检测部位与字段对应关系**
- `station_1_defect_count` -> 右侧
- `station_2_defect_count` -> 左侧
- `station_3_defect_count` -> 车顶
- `station_4_defect_count` -> 前盖
- `station_5_defect_count` -> 尾门
- `total_defect_count` = 五个部位缺陷数之和。

**5. 检测通道 (Tunnel) 澄清**
- `tunnel` 表示检测设备通道号（1、2、3）。用户提问“x线”检测相关问题时，Agent 需主动澄清是否对应“x通道”，未指定时默认分 `tunnel` 展现。

**6. 重复检测处理规则**：
- 一车多检场景（如复检、返修后复检）在缺陷统计中很常见。
- **默认按最新检测记录统计**：查询"总缺陷数"时，取每辆车最新一次检测的 `total_defect_count` 求和。
- **累计统计需明确声明**：仅在用户明确要求"累计缺陷"或"历史缺陷总和"时，才对同一车辆的所有检测记录求和。
- 回答中应主动标注是否涉及重复检测及累计差额。

### 3.4 表关系图谱 (JOIN 键)

- **缺陷事实关联**：
  - `mart.mart_vehicle_quality_360.vehicle_id` -> `dim.dim_vehicle_profile.vehicle_id`
  - `fct.fct_vehicle_defect_detection.vehicle_id` -> `dim.dim_vehicle_profile.vehicle_id`
  - `fct.fct_vehicle_defect_enriched.vehicle_id` -> `dim.carbody_registry.vehicle_id`

---

## 4. 查询易错点 (Gotchas)

- **车数统计虚高**：在做车辆数与缺陷关联分析时，直接 `COUNT(*)` 会因一车多检导致数据膨胀。**必须使用 `COUNT(DISTINCT vehicle_id)`**。
- **`black_roof` 缺陷判定**：`black_roof` 不是严格布尔值，而是缺陷系统对车顶单独检测的描述。
- **`type_name` 与 `model` 区分**：`model`（如 1, 2）是检测程序代码，`type_name`（如 Tiguan）是可读车型名称。
- **关联位置口径限制**：`mart_vehicle_quality_360` 关联的是车身**当前最新在制位置**，而非检测当时的物理位置。

---

## 5. 推荐回答策略 (Recommended Answer Strategies)

- **趋势分析**：优先按 `DATE(detect_time)` 聚合展示每日趋势。
- **车型缺陷分析**：优先使用 `defect_type_name` (车型中文名)，必要时补充 `defect_model`。
- **部位差异**：将 `station_1` - `station_5` 翻译为“右侧、左侧、车顶、前盖、尾门”呈现。
- **对比问题**：明确说明数据是按“检测次数”汇总还是“唯一车身”汇总。
