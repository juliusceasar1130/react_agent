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
  - rb_index (VARCHAR(20)) - Robot位置索引（标识物理位置）
  - vehicle_id (VARCHAR(14)) - 车身唯一标识ID (0-13位)
  - body_type (VARCHAR(5)) - 车身类型代码 (14-18位)，外键关联vehicle_body_types表
  - color_code (VARCHAR(4)) - 颜色代码 (19-22位)，外键关联vehicle_color_codes表
  - platform_code (VARCHAR(3)) - 车型平台代码 (23-25位)，外键关联vehicle_platforms表
  - black_roof_flag (CHAR(1)) - 黑色车顶标志位 (26位)
  - rework_flag (CHAR(1)) - 返工车标志位 (27位)
  - raw_data (VARCHAR(30)) - 原始30字符完整数据
  - position_created_at (TIMESTAMP) - 位置创建时间
  - vehicle_updated_at (TIMESTAMP) - 车辆数据最后更新时间

### vehicle_body_types（车型代码字典表）
- **描述**：车型代码映射字典
- **主键**：id (INTEGER)
- **关键字段**：
  - body_type (VARCHAR(5)) - 车身类型代码，如 VS21J
  - type_name (VARCHAR(100)) - 车型名称，如 "奥迪A4L"
  - is_defined (BOOLEAN) - 是否预定义 (TRUE: 已知, FALSE: 自动发现)
  - first_seen (TIMESTAMP) - 首次出现时间

### vehicle_color_codes（颜色代码字典表）
- **描述**：颜色代码映射字典
- **主键**：id (INTEGER)
- **关键字段**：
  - color_code (VARCHAR(4)) - 颜色代码，如 2LA1
  - color_name (VARCHAR(50)) - 颜色名称，如 "珍珠白"
  - is_defined (BOOLEAN) - 是否预定义
  - first_seen (TIMESTAMP) - 首次出现时间

### vehicle_platforms（车型平台字典表）
- **描述**：车型平台映射字典
- **主键**：id (INTEGER)
- **关键字段**：
  - platform_code (VARCHAR(3)) - 平台代码，如 MLB
  - platform_name (VARCHAR(50)) - 平台名称，如 "MLB Evo"
  - is_defined (BOOLEAN) - 是否预定义
  - first_seen (TIMESTAMP) - 首次出现时间

## 业务逻辑

**车辆数据解析**：
- vehicle_id字段：0-13位为车身唯一标识ID
- body_type字段：14-18位为车身类型代码
- color_code字段：19-22位为颜色代码
- platform_code字段：23-25位为车型平台代码
- black_roof_flag字段：26位为黑色车顶标志位
- rework_flag字段：27位为返工车标志位

**有效车辆判断**：
- 有效车辆：vehicle_id != '--------------' 且 body_type != '-----'
- 空位车辆：vehicle_id = '--------------' 且 body_type = '-----'

**字典数据管理**：
- 预定义数据：is_defined = TRUE，表示已知的标准代码
- 自动发现数据：is_defined = FALSE，表示系统自动识别的新代码

**实时监控逻辑**：
- 位置创建时间：position_created_at 表示该采集点位置创建时间
- 车辆更新时间：vehicle_updated_at 表示车辆数据最后更新时间
- 最新状态：按vehicle_updated_at降序排列获取车辆最新状态

## 表关系图
rb_position_data
├── body_type → vehicle_body_types.body_type
├── color_code → vehicle_color_codes.color_code
└── platform_code → vehicle_platforms.platform_code


## 示例查询

-- 获取当前涂装车间所有有效车辆的最新状态
SELECT 
    rp.vehicle_id,
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
WHERE rp.vehicle_id != '--------------'
  AND rp.body_type != '-----'
ORDER BY rp.vehicle_updated_at DESC
LIMIT 100;

-- 统计各车型在涂装车间的分布情况
SELECT 
    vbt.type_name as vehicle_model,
    COUNT(*) as vehicle_count,
    STRING_AGG(DISTINCT vcc.color_name, ', ') as colors_available
FROM rb_position_data rp
JOIN vehicle_body_types vbt ON rp.body_type = vbt.body_type
JOIN vehicle_color_codes vcc ON rp.color_code = vcc.color_code
WHERE rp.vehicle_id != '--------------'
  AND rp.body_type != '-----'
GROUP BY vbt.type_name
ORDER BY vehicle_count DESC;

-- 查找特定PLC设备下的车辆信息
SELECT 
    rp.plc,
    rp.rb_index,
    rp.vehicle_id,
    vbt.type_name,
    vcc.color_name,
    rp.vehicle_updated_at
FROM rb_position_data rp
LEFT JOIN vehicle_body_types vbt ON rp.body_type = vbt.body_type
LEFT JOIN vehicle_color_codes vcc ON rp.color_code = vcc.color_code
WHERE rp.plc = 'L3F13'
  AND rp.vehicle_id != '--------------'
ORDER BY rp.rb_index;
"""
},
]