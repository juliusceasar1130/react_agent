# 车辆分类规则与 LLM 提示词规范指南

修改时间：2026-07-29 Asia/Shanghai

主要修改内容：
- **简化字段设计（复用 `entity_type`）**：取消新增 `sub_entity_type` 冗余字段，直接复用并升级既有 `entity_type` 字段（取值：`project_vehicle` / `product_vehicle` / `abnormal_vehicle`）。
- **确定 FIS 项目车订单关联算法**：基于 `ods.rb_position_data.vehicle_id` 前 13 位与 `ods.ods_fis_project_vehicle_orders.composite_pin_no` 关联获取 `project_vehicle_no`。
- **消解异常类型逻辑冲突**：以 `entity_type` 为主防线，正常车 (`project_vehicle` / `product_vehicle`) 的 `abnormal_type` 恒为 NULL，彻底消解旧逻辑中 `undefined_body_type` 与新产品车定义的潜在逻辑冲突。
- **生成极致精简的 LLM 提示词模板**：便于 Agent / LLM 准确理解领域语义并生成正确 SQL。

---

## 1. 车辆分类判定规则（零冲突设计）

基于滚床位置表 `ods.rb_position_data`（别名 `rb`）与 FIS 项目车订单表 `ods.ods_fis_project_vehicle_orders`（别名 `pvo`），按以下关联方式进行判定：

- **关联条件**：`LEFT(trim(rb.vehicle_id), 13) = pvo.composite_pin_no`

### 1.1 一级分类规则表

| 序号 | 车辆类型 | 实体类型代码 (`entity_type`) | 大类属性 | 核心判定条件 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **项目车** | `project_vehicle` | 正常车 | `project_vehicle_no` 非空非 NULL | **1 (最高)** |
| 2 | **产品车 (量产车)** | `product_vehicle` | 正常车 | `vehicle_id` 以 `782026` 开头 **且** `project_vehicle_no` 为空/NULL | **2** |
| 3 | **异常车** | `abnormal_vehicle` | 异常车 | **兜底**：不属于项目车且不属于产品车的所有记录 | **3** |

### 1.2 异常车细分类型与原因 (`abnormal_type` & `abnormal_reason`)
仅当判定为 `entity_type = 'abnormal_vehicle'` 时才评估异常细分类型（正常车恒为 `NULL`，防止矛盾冲突）：

- **`empty_vehicle_id_with_carrier`**：`vehicle_id = '--------------'` (占位虚线)。
- **`blank_vehicle_id_with_carrier`**：`vehicle_id` 为 NULL 或空字符串。
- **`non_product_prefix`**：`vehicle_id NOT LIKE '782026%'` 且未匹配到项目车编号的所有异常车。

---

## 2. 标准 SQL 分类表达式 (CASE WHEN)

```sql
SELECT
  rb.position_id,
  rb.vehicle_id,
  rb.carrier_id,
  pvo.project_vehicle_no,

  -- 1. 车辆类型分类代码 (entity_type)
  CASE
    WHEN NULLIF(trim(pvo.project_vehicle_no), '') IS NOT NULL THEN 'project_vehicle'
    WHEN NULLIF(trim(rb.vehicle_id), '') LIKE '782026%' 
     AND NULLIF(trim(pvo.project_vehicle_no), '') IS NULL THEN 'product_vehicle'
    ELSE 'abnormal_vehicle'
  END AS entity_type,

  -- 2. 车辆类型中文名称 (entity_type_cn)
  CASE
    WHEN NULLIF(trim(pvo.project_vehicle_no), '') IS NOT NULL THEN '项目车'
    WHEN NULLIF(trim(rb.vehicle_id), '') LIKE '782026%' 
     AND NULLIF(trim(pvo.project_vehicle_no), '') IS NULL THEN '产品车(量产车)'
    ELSE '异常车'
  END AS entity_type_cn,

  -- 3. 异常类型代码 (abnormal_type) - 仅异常车有值，正常车恒为 NULL 避免逻辑冲突
  CASE
    WHEN NULLIF(trim(pvo.project_vehicle_no), '') IS NOT NULL THEN NULL
    WHEN NULLIF(trim(rb.vehicle_id), '') LIKE '782026%' THEN NULL
    WHEN NULLIF(trim(rb.vehicle_id), '') = '--------------' THEN 'empty_vehicle_id_with_carrier'
    WHEN NULLIF(trim(rb.vehicle_id), '') IS NULL THEN 'blank_vehicle_id_with_carrier'
    ELSE 'non_product_prefix'
  END AS abnormal_type,

  -- 4. 异常说明 (abnormal_reason)
  CASE
    WHEN NULLIF(trim(pvo.project_vehicle_no), '') IS NOT NULL THEN NULL
    WHEN NULLIF(trim(rb.vehicle_id), '') LIKE '782026%' THEN NULL
    WHEN NULLIF(trim(rb.vehicle_id), '') = '--------------' THEN 'carrier_id 非 0，但 vehicle_id 为 --------------。'
    WHEN NULLIF(trim(rb.vehicle_id), '') IS NULL THEN 'carrier_id 非 0，但 vehicle_id 为空。'
    ELSE 'carrier_id 非 0，但 vehicle_id 前缀不是 782026 且无项目车编号。'
  END AS abnormal_reason

FROM ods.rb_position_data rb
LEFT JOIN ods.ods_fis_project_vehicle_orders pvo
  ON pvo.composite_pin_no IS NOT NULL 
 AND pvo.composite_pin_no <> ''
 AND LEFT(trim(rb.vehicle_id), 13) = pvo.composite_pin_no;
```

---

## 3. 给 LLM 的提示词 (Prompt System Instruction)

```markdown
### 车辆分类与状态语义规则 (Vehicle Classification Knowledge)

查询车辆及工位占位数据时，车辆统一通过 `entity_type` 字段进行分类与过滤：

#### 1. 字段代码与取值说明：
- `entity_type` 取值枚举：
  - `'project_vehicle'`：项目车 (属于正常车)
  - `'product_vehicle'`：产品车 / 量产车 (属于正常车)
  - `'abnormal_vehicle'`：异常车

#### 2. 分类判定逻辑：
1. **项目车 (`project_vehicle`)**：`project_vehicle_no` 字段非空非 NULL，**优先级最高**（即使 VIN 为 782026 也优先算作项目车）。
2. **产品车/量产车 (`product_vehicle`)**：`project_vehicle_no` 为空，且 `vehicle_id` 以 `'782026'` 开头。
3. **异常车 (`abnormal_vehicle`)**：既不是项目车，也不是产品车的所有其余记录。可结合 `abnormal_type` 或 `abnormal_reason` 查看具体异常原因（正常车对应的 abnormal_type 恒为 NULL）。

#### 3. 自然语言查询映射示例 (Few-Shot)：
- “查所有项目车/试验车” -> `WHERE entity_type = 'project_vehicle'`
- “查所有量产车/产品车” -> `WHERE entity_type = 'product_vehicle'`
- “正常车有多少辆？” -> `WHERE entity_type IN ('project_vehicle', 'product_vehicle')` (或 `WHERE entity_type <> 'abnormal_vehicle'`)
- “有哪些异常车？是什么原因？” -> `SELECT vehicle_id, abnormal_type, abnormal_reason FROM fct.fct_abnormal_vehicle_current`
```
