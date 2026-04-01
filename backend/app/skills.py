from typing import TypedDict


class Skill(TypedDict):
    """A skill that can be progressively disclosed to the agent."""

    name: str  # Unique identifier for the skill
    description: str  # 1-2 sentence description to show in system prompt
    content: str  # Full skill content with detailed instructions


SKILLS: list[Skill] = [
    {
        "name": "paint_shop_vehicle_tracking",
        "description": "涂装车间车辆追踪系统数据库架构，用于实时监控车辆在涂装车间的状态、位置和属性信息，包括车型、颜色、平台等维度的数据管理。",
        "content": """# 涂装车间车辆追踪系统架构

## 数据表

### rb_position_data（车辆位置数据表）
- **描述**：存储采集点及当前位置的车辆状态信息
- **主键**：id (BIGINT)
- **关键字段**：
  - plc (VARCHAR(20)) - 所属PLC设备名称
  - tag (VARCHAR(200)) - WebSocket订阅Tag，唯一标识采集点
  - rb_index (VARCHAR(20)) - 滚床/链条储存位编号(标识物理位置)
  - remark (VARCHAR(100)) - 备用/位置说明
  - process_area (VARCHAR(50)) - 生产工艺区域名称，值与 process_areas.area_name 对应
  - carrier_id (VARCHAR(50)) - 载体唯一标识，如挂具编号或滑橇编号
  - carrier_type (VARCHAR(20)) - 载体类型 (hanger/skid)，值与 carrier_types.type_code 对应
  - vehicle_id (VARCHAR(14)) - 车身唯一标识ID (0-13位),如：78202681067513
  - body_type (VARCHAR(5)) - 车身类型代码 (14-18位)，关联vehicle_body_types表
  - color_code (VARCHAR(4)) - 颜色代码 (19-22位)，关联vehicle_color_codes表
  - platform_code (VARCHAR(3)) - 车型平台代码 (23-25位)，关联vehicle_platforms表
  - black_roof_flag (CHAR(1)) - 黑色车顶标志位 (26位)
  - rework_flag (CHAR(1)) - 返工车标志位 (27位)
  - reserved_1 (CHAR(1)) - 预留字段1 (28位)
  - reserved_2 (CHAR(1)) - 预留字段2 (29位)
  - raw_data (VARCHAR(30)) - 原始30字符完整数据
  - position_created_at (TIMESTAMPTZ) - 位置创建时间
  - vehicle_updated_at (TIMESTAMPTZ) - 车辆数据最后更新时间

### process_areas（生产工艺区域字典表）
- **描述**：生产工艺区域字典表，管理所有已知的工艺段名称，如"L2面漆存储线"
- **关键字段**：
  - area_name (VARCHAR(50)) - 工艺区域中文名称（唯一键）
  - description (VARCHAR(200)) - 区域详细说明
  - sort_order (INT) - 工艺流程先后顺序

### carrier_types（载体类型字典表）
- **描述**：载体类型字典表，定义输送载体的分类枚举
- **关键字段**：
  - type_code (VARCHAR(20)) - 载体类型英文代码 (hanger/skid/slat)
  - type_name_cn (VARCHAR(50)) - 载体类型中文名称
  - description (VARCHAR(200)) - 载体类型详细说明

### vehicle_body_types（车型代码字典表）
- **描述**：车型代码映射字典
- **关键字段**：
  - body_type (VARCHAR(5)) - 车身类型代码，如 VS21J
  - type_name (VARCHAR(100)) - 车型名称，如 "奥迪A4L"
  - is_defined (BOOLEAN) - 是否预定义 (TRUE: 已知, FALSE: 自动发现)
  - first_seen (TIMESTAMPTZ) - 首次出现时间

### vehicle_color_codes（颜色代码字典表）
- **描述**：颜色代码映射字典
- **关键字段**：
  - color_code (VARCHAR(4)) - 颜色代码，如 2LA1
  - color_name (VARCHAR(50)) - 颜色名称，如 "珍珠白"
  - is_defined (BOOLEAN) - 是否预定义
  - first_seen (TIMESTAMPTZ) - 首次出现时间

### vehicle_platforms（车型平台字典表）
- **描述**：车型平台映射字典
- **关键字段**：
  - platform_code (VARCHAR(3)) - 平台代码，如 MLB
  - platform_name (VARCHAR(50)) - 平台名称，如 "MLB Evo"
  - is_defined (BOOLEAN) - 是否预定义
  - first_seen (TIMESTAMPTZ) - 首次出现时间

## 业务逻辑

**车辆数据解析**：
- vehicle_id字段：0-13位为车身唯一标识ID
- body_type字段：14-18位为车身类型代码
- color_code字段：19-22位为颜色代码
- platform_code字段：23-25位为车型平台代码
- black_roof_flag字段：26位为黑色车顶标志位
- rework_flag字段 : 27位为返工车标志位
- reserved_1字段 : 28位为预留字段1
- reserved_2字段 : 29位为预留字段2

**有效车辆判断规则**：
- 有效车辆：vehicle_id 的前缀是 '782026' 且 body_type != '-----' 且 carrier_id != 0
**空位/无车规则**：
- 空位/滚床上无车：vehicle_id = '--------------' 且 body_type = '-----' 且 carrier_id = 0


**字典数据管理**：
- 预定义数据：is_defined = TRUE，表示已知的标准代码
- 自动发现数据：is_defined = FALSE，表示系统自动识别的新代码

**实时监控逻辑**：
- 位置创建时间：position_created_at 表示该采集点位置创建时间
- 车辆更新时间：vehicle_updated_at 表示车辆数据最后更新时间
- 最新状态：按vehicle_updated_at降序排列获取车辆最新状态

## 表关系图
rb_position_data
├── process_area → process_areas.area_name
├── carrier_type → carrier_types.type_code
├── body_type → vehicle_body_types.body_type
├── color_code → vehicle_color_codes.color_code
└── platform_code → vehicle_platforms.platform_code


## 示例查询

-- 获取当前涂装车间所有有效车辆的最新状态（含工艺区域和载体信息）
SELECT 
    rp.vehicle_id,
    rp.process_area,
    rp.carrier_id,
    ct.type_name_cn as carrier_type_name,
    rp.rb_index,
    rp.remark as position_name,
    vbt.type_name as vehicle_model,
    vcc.color_name as vehicle_color,
    vp.platform_name as vehicle_platform,
    CASE WHEN rp.black_roof_flag = '1' THEN '是' ELSE '否' END as has_black_roof,
    CASE WHEN rp.rework_flag = '1' THEN '是' ELSE '否' END as is_rework_vehicle,
    rp.vehicle_updated_at as last_update_time
FROM rb_position_data rp
LEFT JOIN vehicle_body_types vbt ON rp.body_type = vbt.body_type
LEFT JOIN vehicle_color_codes vcc ON rp.color_code = vcc.color_code
LEFT JOIN vehicle_platforms vp ON rp.platform_code = vp.platform_code
LEFT JOIN carrier_types ct ON rp.carrier_type = ct.type_code
WHERE rp.vehicle_id != '--------------'
  AND rp.body_type != '-----'
ORDER BY rp.vehicle_updated_at DESC
LIMIT 100;

-- 按工艺区域统计车辆分布情况
SELECT 
    rp.process_area,
    COUNT(*) as vehicle_count,
    STRING_AGG(DISTINCT vbt.type_name, ', ') as models_in_area
FROM rb_position_data rp
JOIN vehicle_body_types vbt ON rp.body_type = vbt.body_type
WHERE rp.vehicle_id != '--------------'
GROUP BY rp.process_area
ORDER BY vehicle_count DESC;

-- 查找特定工艺区域下的载体和车辆信息
SELECT 
    rp.process_area,
    rp.carrier_id,
    ct.type_name_cn as carrier_type,
    rp.vehicle_id,
    vbt.type_name,
    rp.vehicle_updated_at
FROM rb_position_data rp
LEFT JOIN carrier_types ct ON rp.carrier_type = ct.type_code
LEFT JOIN vehicle_body_types vbt ON rp.body_type = vbt.body_type
WHERE rp.process_area = 'L2面漆存储线'
  AND rp.vehicle_id != '--------------'
ORDER BY rp.rb_index;
""",
    },
]
