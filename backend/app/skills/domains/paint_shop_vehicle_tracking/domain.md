# 涂装车间车辆追踪系统架构

修改时间：2026-04-12 Asia/Shanghai

主要修改内容：

- 保留源库 `rb_position_data` 与字典表说明
- 新增 `analytics_db` 分析库查询入口说明
- 明确正式产品车、异常车、当前现场总览的推荐查询对象
- 补充当前分析口径下的易错点

## 推荐查询入口

当 Agent 默认连接 `analytics_db` 时，优先使用下面这些分析对象，而不是直接从底层表开始拼装查询。

### 查询优先级

1. 优先查询 `mart`
2. 其次查询 `fct`
3. 非必要不直接查询 `ods`

### 当前现场总览

- 推荐对象：`mart_position_current_overview`
- 描述：当前现场总览分析对象，一条记录表示一个当前有效占位
- 粒度：一条当前有效占位一行
- 适用问题：
  - 当前现场总共有多少占位
  - 当前正式产品车和异常车分别多少
  - 当前各区域车辆分布
  - 当前某个 `carrier_id` 或 `vehicle_id` 对应什么状态
- 关键字段：
  - `position_id`：当前占位唯一标识
  - `entity_type`：当前占位类型，区分正式产品车和异常车
  - `vehicle_status_code`：当前占位状态编码，如 `product_vehicle`、`non_product_prefix`
  - `vehicle_status_name`：当前占位状态中文说明
  - `process_area`：当前所在工艺区域
  - `carrier_id`：当前载体编号
  - `carrier_type` / `carrier_type_name_cn`：当前载体类型及中文说明
  - `vehicle_id`：当前车身 ID，异常车可能不是正式产品车 ID
  - `body_type` / `tracking_type_name`：车型代码与车型名称
  - `full_rb_code`：完整滚床编号，通常由 `plc + rb_index` 组成
  - `vehicle_updated_at`：车辆数据最后更新时间

### 正式产品车当前状态

- 推荐对象：`fct_vehicle_position_current`
- 语义：
  - 只表示正式产品车当前事实
  - 当前口径要求 `vehicle_id LIKE '782026%'`，且 `body_type != '-----'`，且 `carrier_id != 0`
- 粒度：一台正式产品车一行
- 适用问题：
  - 某台正式产品车当前在哪
  - 当前各区域正式产品车数量
  - 当前某车型正式产品车分布
- 关键字段：
  - `vehicle_id`：正式产品车车身 ID
  - `position_id`：当前位置记录 ID
  - `process_area`：当前所在工艺区域
  - `carrier_id`：当前载体编号
  - `carrier_type`：当前载体类型编码
  - `body_type`：车型代码
  - `color_code`：颜色代码
  - `platform_code`：平台代码
  - `full_rb_code`：完整滚床编号
  - `position_created_at`：位置记录创建时间
  - `vehicle_updated_at`：车辆数据最后更新时间

### 当前全部有效占位

- 推荐对象：`fct_position_current_all`
- 语义：
  - 表示当前每个有效占位一条记录
  - 不按 `vehicle_id` 去重
- 粒度：一条当前有效占位一行
- 适用问题：
  - 当前全部占位
  - 重复调试 `vehicle_id` 或特殊占位分析
- 关键字段：
  - `position_id`：当前占位唯一标识
  - `vehicle_id`：当前占位对应的车身 ID，可能为空或异常值
  - `entity_type`：占位类型，区分正式产品车和异常车
  - `abnormal_type`：异常类型编码，正式产品车通常为空
  - `process_area`：当前所在工艺区域
  - `carrier_id`：当前载体编号
  - `carrier_type`：当前载体类型编码
  - `full_rb_code`：完整滚床编号
  - `vehicle_updated_at`：车辆数据最后更新时间

### 当前异常车

- 推荐对象：`mart_abnormal_vehicle_current`
- 次选对象：`fct_abnormal_vehicle_current`
- 描述：当前异常车分析对象
- 粒度：一条当前异常占位一行
- 适用问题：
  - 当前异常车有多少
  - 异常车分布在哪些区域
  - 哪些 `carrier_id` 当前挂的是异常车
- 关键字段：
  - `position_id`：当前异常占位唯一标识
  - `vehicle_id`：异常车车身 ID 或占位值
  - `abnormal_type`：异常类型编码
  - `abnormal_reason`：异常类型说明
  - `process_area`：当前所在工艺区域
  - `carrier_id`：当前载体编号
  - `carrier_type` / `carrier_type_name_cn`：当前载体类型及中文说明
  - `body_type` / `tracking_type_name`：车型代码与车型名称
  - `full_rb_code`：完整滚床编号
  - `vehicle_updated_at`：车辆数据最后更新时间

## 业务逻辑

### 有效车辆判断规则

- 有效车辆：`vehicle_id` 前缀是 `782026`，且 `body_type != '-----'`，且 `carrier_id != 0`

### 空位/无车规则

- 空位/滚床上无车：`vehicle_id = '--------------'` 且 `body_type = '-----'` 且 `carrier_id = 0`

### 字典数据管理

- 预定义数据：`is_defined = TRUE`
- 自动发现数据：`is_defined = FALSE`

### 实时监控逻辑

- `position_created_at` 表示该采集点位置创建时间
- `vehicle_updated_at` 表示车辆数据最后更新时间
- 最新状态通常按 `vehicle_updated_at` 降序获取

### 车辆数据解析

- `vehicle_id`：0-13 位为车身唯一标识 ID
- `body_type`：14-18 位为车身类型代码
- `color_code`：19-22 位为颜色代码
- `platform_code`：23-25 位为车型平台代码
- `black_roof_flag`：26 位为黑色车顶标志位
- `rework_flag`：27 位为返工车标志位
- `reserved_1`：28 位为预留字段 1
- `reserved_2`：29 位为预留字段 2

## 当前易错点

### 不要把 `fct_vehicle_position_current` 当成全部当前占位

- `fct_vehicle_position_current` 现在只面向正式产品车
- 如果问题涉及异常车、调试车或全部当前占位，应优先使用：
  - `mart_position_current_overview`
  - `fct_position_current_all`
  - `mart_abnormal_vehicle_current`

### 异常车不适合只按 `vehicle_id` 建模

- 异常车可能存在：
  - `vehicle_id` 前缀不是 `782026`
  - `vehicle_id = '--------------'`
  - 多个位置共用相同调试 `vehicle_id`
- 这类问题不应只依赖 `vehicle_id` 唯一去重后的结果

### 当前缺陷关联口径不是检测时位置

- `mart_vehicle_quality_360` 当前使用的是“缺陷检测 + 当前最新位置”
- 如果后续要分析检测发生时位置或停留时长，需要新增位置历史快照层，而不是继续依赖当前这张表

## 源表与底层数据表

### rb_position_data（车辆位置数据表）

- 描述：存储采集点及当前位置的车辆状态信息
- 主键：id (BIGINT)
- 关键字段：
  - plc (VARCHAR(20))：所属 PLC 设备名称
  - tag (VARCHAR(200))：WebSocket 订阅 Tag，唯一标识采集点
  - rb_index (VARCHAR(20))：滚床/链条储存位编号
  - remark (VARCHAR(100))：位置说明
  - process_area (VARCHAR(50))：生产工艺区域名称，值与 `process_areas.area_name` 对应
  - carrier_id (VARCHAR(50))：载体唯一标识，如挂具编号或滑橇编号
  - carrier_type (VARCHAR(20))：载体类型，值与 `carrier_types.type_code` 对应
  - vehicle_id (VARCHAR(14))：车身唯一标识 ID
  - body_type (VARCHAR(5))：车身类型代码，关联 `vehicle_body_types`
  - color_code (VARCHAR(4))：颜色代码，关联 `vehicle_color_codes`
  - platform_code (VARCHAR(3))：车型平台代码，关联 `vehicle_platforms`
  - black_roof_flag (CHAR(1))：黑色车顶标志位
  - rework_flag (CHAR(1))：返工车标志位
  - reserved_1 / reserved_2：预留字段
  - raw_data (VARCHAR(30))：原始 30 字符完整数据
  - position_created_at (TIMESTAMPTZ)：位置创建时间
  - vehicle_updated_at (TIMESTAMPTZ)：车辆数据最后更新时间

### process_areas（生产工艺区域字典表）

- 描述：生产工艺区域字典表，管理工艺段名称
- 关键字段：
  - area_name (VARCHAR(50))：工艺区域中文名称（唯一键）
  - description (VARCHAR(200))：区域说明
  - sort_order (INT)：工艺流程顺序

### carrier_types（载体类型字典表）

- 描述：定义输送载体的分类枚举
- 关键字段：
  - type_code (VARCHAR(20))：载体类型英文代码
  - type_name_cn (VARCHAR(50))：载体类型中文名称
  - description (VARCHAR(200))：载体类型说明

### vehicle_body_types（车型代码字典表）

- 描述：车型代码映射字典
- 关键字段：
  - body_type (VARCHAR(5))：车身类型代码，5位由数字或者字母组成
  - type_name (VARCHAR(100))：车型名称,如Tiguan、E7等
  - is_defined (BOOLEAN)：是否预定义
  - first_seen (TIMESTAMPTZ)：首次出现时间

### vehicle_color_codes（颜色代码字典表）

- 描述：颜色代码映射字典
- 关键字段：
  - color_code (VARCHAR(4))：颜色代码
  - color_name (VARCHAR(50))：颜色名称
  - is_defined (BOOLEAN)：是否预定义
  - first_seen (TIMESTAMPTZ)：首次出现时间

### vehicle_platforms（车型平台字典表）

- 描述：车型平台映射字典
- 关键字段：
  - platform_code (VARCHAR(3))：平台代码
  - platform_name (VARCHAR(50))：平台名称
  - is_defined (BOOLEAN)：是否预定义
  - first_seen (TIMESTAMPTZ)：首次出现时间

## 表关系图

rb_position_data
├── process_area -> process_areas.area_name
├── carrier_type -> carrier_types.type_code
├── body_type -> vehicle_body_types.body_type
├── color_code -> vehicle_color_codes.color_code
└── platform_code -> vehicle_platforms.platform_code
