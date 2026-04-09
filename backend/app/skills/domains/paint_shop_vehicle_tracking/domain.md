# 涂装车间车辆追踪系统架构

## 数据表

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

## 业务逻辑

### 车辆数据解析

- `vehicle_id`：0-13 位为车身唯一标识 ID
- `body_type`：14-18 位为车身类型代码
- `color_code`：19-22 位为颜色代码
- `platform_code`：23-25 位为车型平台代码
- `black_roof_flag`：26 位为黑色车顶标志位
- `rework_flag`：27 位为返工车标志位
- `reserved_1`：28 位为预留字段 1
- `reserved_2`：29 位为预留字段 2

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

## 表关系图

rb_position_data
├── process_area -> process_areas.area_name
├── carrier_type -> carrier_types.type_code
├── body_type -> vehicle_body_types.body_type
├── color_code -> vehicle_color_codes.color_code
└── platform_code -> vehicle_platforms.platform_code
