-- ============================================
-- 数据库改造 SQL 脚本 (PostgreSQL 版本)
-- 创建日期: 2026-01-20
-- 更新日期: 2026-03-18  新增 process_area 工艺区域字段
-- 更新日期: 2026-03-18  新增 carrier_id 载体标识 / carrier_type 载体类型字段（hanger/skid/slat）
-- 说明: 基于 RB位置状态版 设计方案
-- ============================================

-- 删除旧表(如果存在)
DROP TABLE IF EXISTS rb_position_data CASCADE;
DROP TABLE IF EXISTS vehicle_body_types CASCADE;
DROP TABLE IF EXISTS vehicle_color_codes CASCADE;
DROP TABLE IF EXISTS vehicle_platforms CASCADE;
DROP TABLE IF EXISTS process_areas CASCADE;
DROP TABLE IF EXISTS carrier_types CASCADE;


-- ============================================
-- 公共函数: updated_at 自动更新触发器
-- (必须先于所有触发器创建)
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';


-- ============================================
-- 0. 辅助表: process_areas (生产工艺区域字典表)
-- 说明: 先建此表，rb_position_data.process_area 字段逻辑上关联此表的 area_name
-- ============================================
CREATE TABLE process_areas (
    id SERIAL PRIMARY KEY,
    area_name VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(200),
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE process_areas IS '生产工艺区域字典表，管理所有已知的工艺段名称，如"L2面漆存储线"';
COMMENT ON COLUMN process_areas.area_name IS '工艺区域中文名称（唯一键），与 rb_position_data.process_area 字段值保持一致';
COMMENT ON COLUMN process_areas.description IS '区域详细说明，例如该区域的工艺流程描述、所含工位范围等';
COMMENT ON COLUMN process_areas.sort_order IS '工艺流程先后顺序，数字越小越靠前，便于按工艺顺序排序查询';

CREATE TRIGGER update_process_areas_updated_at
    BEFORE UPDATE ON process_areas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 预置已知工艺区域数据
INSERT INTO process_areas (area_name, description, sort_order) VALUES
    ('L2面漆存储线', 'L2车间面漆工艺段存储输送线，负责面漆完成后车身的缓存与转运', 10);


-- ============================================
-- 0.5 辅助表: carrier_types (载体类型字典表)
-- 说明: 定义物理载体的类型枚举，rb_position_data.carrier_type 与此表 type_code 软关联
-- ============================================
CREATE TABLE carrier_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(20) UNIQUE NOT NULL,
    type_name_cn VARCHAR(50),
    description VARCHAR(200),
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE carrier_types IS '载体类型字典表，定义输送载体的分类枚举，如挂具、滑橇等';
COMMENT ON COLUMN carrier_types.type_code IS '载体类型英文代码（唯一键）如hanger/skid，与 rb_position_data.carrier_type 字段值对应';
COMMENT ON COLUMN carrier_types.type_name_cn IS '载体类型中文名称，便于报表展示';
COMMENT ON COLUMN carrier_types.description IS '载体类型详细说明，包含典型应用场景';
COMMENT ON COLUMN carrier_types.sort_order IS '显示顺序';

CREATE TRIGGER update_carrier_types_updated_at
    BEFORE UPDATE ON carrier_types
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 预置已知载体类型
INSERT INTO carrier_types (type_code, type_name_cn, description, sort_order) VALUES
    ('hanger', '挂具', '输送载体，车身悬挂在挂具上随线体运动', 1000),
    ('Topcoat Skid', '面漆雪橇', '输送载体，车身放置于滑橇上随线体移动', 2000);



-- ============================================
-- 1. 主表: rb_position_data (RB位置车辆数据表)
-- ============================================
CREATE TABLE rb_position_data (
    -- 位置静态属性 (初始化填充)
    id BIGSERIAL PRIMARY KEY,
    plc VARCHAR(20) NOT NULL,
    tag VARCHAR(200) NOT NULL UNIQUE,
    rb_index VARCHAR(20) NOT NULL,
    remark VARCHAR(100),
    process_area VARCHAR(50),
    carrier_id VARCHAR(50),
    carrier_type VARCHAR(20),

    -- 车辆动态属性 (实时更新, 初始为 NULL)
    vehicle_id VARCHAR(14),
    body_type VARCHAR(5),
    color_code VARCHAR(4),
    platform_code VARCHAR(3),
    black_roof_flag CHAR(1),
    rework_flag CHAR(1),
    reserved_1 CHAR(1),
    reserved_2 CHAR(1),
    raw_data VARCHAR(30),

    -- 时间戳
    position_created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    vehicle_updated_at TIMESTAMPTZ
);

-- 添加注释
COMMENT ON TABLE rb_position_data IS '存储采集点及当前位置的车辆状态信息';
COMMENT ON COLUMN rb_position_data.id IS '主键ID';
COMMENT ON COLUMN rb_position_data.plc IS '所属PLC设备名称';
COMMENT ON COLUMN rb_position_data.tag IS 'WebSocket订阅Tag,唯一标识采集点';
COMMENT ON COLUMN rb_position_data.rb_index IS '滚床/链条储存位编号(标识物理位置)';
COMMENT ON COLUMN rb_position_data.remark IS '备用';
COMMENT ON COLUMN rb_position_data.process_area IS '生产工艺区域名称（静态属性，初始化时从deviceConfig.json的process_area键读取），例如"L2面漆存储线"；值与 process_areas.area_name 对应，可JOIN查询区域描述和排序信息';
COMMENT ON COLUMN rb_position_data.vehicle_id IS '车身唯一标识ID (0-13位)';
COMMENT ON COLUMN rb_position_data.body_type IS '车身类型代码 (14-18位), 关联vehicle_body_types表';
COMMENT ON COLUMN rb_position_data.color_code IS '颜色代码 (19-22位), 关联vehicle_color_codes表';
COMMENT ON COLUMN rb_position_data.platform_code IS '车型平台代码 (23-25位), 关联vehicle_platforms表';
COMMENT ON COLUMN rb_position_data.black_roof_flag IS '黑色车顶标志位 (26位)';
COMMENT ON COLUMN rb_position_data.rework_flag IS '返工车标志位 (27位)';
COMMENT ON COLUMN rb_position_data.reserved_1 IS '预留字段1 (28位)';
COMMENT ON COLUMN rb_position_data.reserved_2 IS '预留字段2 (29位)';
COMMENT ON COLUMN rb_position_data.raw_data IS '原始30字符完整数据';
COMMENT ON COLUMN rb_position_data.carrier_id IS '载体唯一标识（静态属性，初始化时填充），如挂具编号 H-001、滑橇编号 SK-042；与具体线体的载体台账对应';
COMMENT ON COLUMN rb_position_data.carrier_type IS '载体类型（静态属性），枚举值：hanger（吊架）/ skid（滑橇）；值与 carrier_types.type_code 对应，可 JOIN 查询中文名称和描述';
COMMENT ON COLUMN rb_position_data.position_created_at IS '位置创建时间';
COMMENT ON COLUMN rb_position_data.vehicle_updated_at IS '车辆数据最后更新时间';

-- 创建索引
CREATE INDEX idx_rb_position_plc ON rb_position_data(plc);
CREATE INDEX idx_rb_position_vehicle_id ON rb_position_data(vehicle_id);
CREATE INDEX idx_rb_position_body_type ON rb_position_data(body_type);
CREATE INDEX idx_rb_position_vehicle_updated ON rb_position_data(vehicle_updated_at);
CREATE INDEX idx_rb_position_process_area ON rb_position_data(process_area);
CREATE INDEX idx_rb_position_carrier_id   ON rb_position_data(carrier_id);
CREATE INDEX idx_rb_position_carrier_type ON rb_position_data(carrier_type);


-- ============================================
-- 2. 辅助表: vehicle_body_types (车身类型字典表)
-- ============================================
CREATE TABLE vehicle_body_types (
    id SERIAL PRIMARY KEY,
    body_type VARCHAR(5) UNIQUE NOT NULL,
    type_name VARCHAR(100),
    description VARCHAR(200),
    is_defined BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE vehicle_body_types IS '车型代码映射字典';
COMMENT ON COLUMN vehicle_body_types.body_type IS '车身类型代码, 如 VS21J';
COMMENT ON COLUMN vehicle_body_types.type_name IS '车型名称, 如 "奥迪A4L"';
COMMENT ON COLUMN vehicle_body_types.is_defined IS '是否预定义 (TRUE: 已知, FALSE: 自动发现)';

CREATE INDEX idx_body_types_is_defined ON vehicle_body_types(is_defined);

CREATE TRIGGER update_vehicle_body_types_updated_at
    BEFORE UPDATE ON vehicle_body_types
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================
-- 3. 辅助表: vehicle_color_codes (颜色代码字典表)
-- ============================================
CREATE TABLE vehicle_color_codes (
    id SERIAL PRIMARY KEY,
    color_code VARCHAR(4) UNIQUE NOT NULL,
    color_name VARCHAR(50),
    color_description VARCHAR(100),
    is_defined BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE vehicle_color_codes IS '颜色代码映射字典';
COMMENT ON COLUMN vehicle_color_codes.color_code IS '颜色代码, 如 2LA1';
COMMENT ON COLUMN vehicle_color_codes.color_name IS '颜色名称, 如 "珍珠白"';

CREATE INDEX idx_color_codes_is_defined ON vehicle_color_codes(is_defined);

CREATE TRIGGER update_vehicle_color_codes_updated_at
    BEFORE UPDATE ON vehicle_color_codes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================
-- 4. 辅助表: vehicle_platforms (车型平台字典表)
-- ============================================
CREATE TABLE vehicle_platforms (
    id SERIAL PRIMARY KEY,
    platform_code VARCHAR(3) UNIQUE NOT NULL,
    platform_name VARCHAR(50),
    description VARCHAR(200),
    is_defined BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE vehicle_platforms IS '车型平台映射字典';
COMMENT ON COLUMN vehicle_platforms.platform_code IS '平台代码, 如 MLB';
COMMENT ON COLUMN vehicle_platforms.platform_name IS '平台名称, 如 "MLB Evo"';

CREATE INDEX idx_platforms_is_defined ON vehicle_platforms(is_defined);

CREATE TRIGGER update_vehicle_platforms_updated_at
    BEFORE UPDATE ON vehicle_platforms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================
-- 创建完成提示
-- ============================================
SELECT 'PostgreSQL tables created successfully!' AS status;
