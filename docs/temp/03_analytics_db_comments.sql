-- ==========================================
-- Analytics DB 表与字段中文注释注入脚本
-- ==========================================
-- 针对 schema: ods, dim, fct, mart, meta
-- 运行此脚本可将字段与表的中文业务含义写入 PostgreSQL 系统字典
--
-- 修改记录 (Modification History):
-- 2026-07-03 20:50 Asia/Shanghai - 补全 FCT 与 MART 层 8 个物化视图各个字段的中文注释 (COMMENT ON COLUMN)

-- ==========================================
-- 1. ODS 层 (贴源层表与字段注释)
-- ==========================================

-- ods.rb_position_data
COMMENT ON TABLE ods.rb_position_data IS '滚床当前位置跟踪贴源数据表';
COMMENT ON COLUMN ods.rb_position_data.id IS '唯一主键ID';
COMMENT ON COLUMN ods.rb_position_data.position_created_at IS '创建时间';
COMMENT ON COLUMN ods.rb_position_data.vehicle_updated_at IS '更新时间';
COMMENT ON COLUMN ods.rb_position_data.carrier_id IS '雪橇/吊架ID/载具编号';
COMMENT ON COLUMN ods.rb_position_data.carrier_type IS '雪橇/吊架/载具类型代码 (等同于 type_code，跨源一一对应)';
COMMENT ON COLUMN ods.rb_position_data.vehicle_id IS '车身唯一识别码 (等同于 serial_number 和 BODY_ID，跨源一一对应)';
COMMENT ON COLUMN ods.rb_position_data.body_type IS '车型代码 (五位车身类型码)';
COMMENT ON COLUMN ods.rb_position_data.color_code IS '车身颜色代码';
COMMENT ON COLUMN ods.rb_position_data.platform_code IS '车型平台';
COMMENT ON COLUMN ods.rb_position_data.black_roof_flag IS '黑顶标记 (1/Y表示黑顶)';
COMMENT ON COLUMN ods.rb_position_data.rework_flag IS '返修车标记 (1/Y表示返修车)';
COMMENT ON COLUMN ods.rb_position_data.reserved_1 IS '预留字段 1';
COMMENT ON COLUMN ods.rb_position_data.reserved_2 IS '预留字段 2';
COMMENT ON COLUMN ods.rb_position_data.raw_data IS '通信原始报文';
COMMENT ON COLUMN ods.rb_position_data.plc IS 'PLC标识名称';
COMMENT ON COLUMN ods.rb_position_data.tag IS 'RFID 点位编码';
COMMENT ON COLUMN ods.rb_position_data.rb_index IS '不完整滚床编号（唯一编号需要包含PLC）';
COMMENT ON COLUMN ods.rb_position_data.remark IS '备注未用';
COMMENT ON COLUMN ods.rb_position_data.process_area IS '工艺区域（等同area_name）';

-- ods.process_areas
COMMENT ON TABLE ods.process_areas IS '工艺区域配置源表';
COMMENT ON COLUMN ods.process_areas.id IS '唯一主键ID';
COMMENT ON COLUMN ods.process_areas.area_name IS '工艺区域代号 (如 L1面漆色漆喷房)';
COMMENT ON COLUMN ods.process_areas.description IS '工艺区域中文名称与描述';
COMMENT ON COLUMN ods.process_areas.sort_order IS '展示排序权重';
COMMENT ON COLUMN ods.process_areas.created_at IS '创建时间';
COMMENT ON COLUMN ods.process_areas.updated_at IS '更新时间';

-- ods.carrier_types
COMMENT ON TABLE ods.carrier_types IS '雪橇/吊架载具类型映射源表';
COMMENT ON COLUMN ods.carrier_types.id IS '唯一主键ID';
COMMENT ON COLUMN ods.carrier_types.type_code IS '雪橇/吊架/载具类型代码 (等同于 carrier_type，跨源一一对应)';
COMMENT ON COLUMN ods.carrier_types.type_name_cn IS '载具类型中文名称';
COMMENT ON COLUMN ods.carrier_types.description IS '载具类型描述说明';
COMMENT ON COLUMN ods.carrier_types.sort_order IS '排序权重';
COMMENT ON COLUMN ods.carrier_types.created_at IS '创建时间';
COMMENT ON COLUMN ods.carrier_types.updated_at IS '更新时间';

-- ods.vehicle_body_types
COMMENT ON TABLE ods.vehicle_body_types IS '车型/车身类型属性映射源表';
COMMENT ON COLUMN ods.vehicle_body_types.id IS '唯一主键ID';
COMMENT ON COLUMN ods.vehicle_body_types.body_type IS '车型代码 (对应 body_type)';
COMMENT ON COLUMN ods.vehicle_body_types.type_name IS '车型中文官方名称 (如 ID.3, 帕萨特)';
COMMENT ON COLUMN ods.vehicle_body_types.description IS '车型描述与备注';
COMMENT ON COLUMN ods.vehicle_body_types.is_defined IS '是否在系统定义中激活';
COMMENT ON COLUMN ods.vehicle_body_types.first_seen IS '首次识别时间';
COMMENT ON COLUMN ods.vehicle_body_types.created_at IS '创建时间';
COMMENT ON COLUMN ods.vehicle_body_types.updated_at IS '更新时间';

-- ods.vehicle_color_codes
COMMENT ON TABLE ods.vehicle_color_codes IS '车身颜色映射源表';
COMMENT ON COLUMN ods.vehicle_color_codes.id IS '唯一主键ID';
COMMENT ON COLUMN ods.vehicle_color_codes.color_code IS '颜色编码 (对应 color_code)';
COMMENT ON COLUMN ods.vehicle_color_codes.color_name IS '颜色名称 (如 极地白, 珠光黑)';
COMMENT ON COLUMN ods.vehicle_color_codes.color_description IS '颜色物理属性备注';
COMMENT ON COLUMN ods.vehicle_color_codes.is_defined IS '是否在系统定义中激活';
COMMENT ON COLUMN ods.vehicle_color_codes.first_seen IS '首次录入时间';
COMMENT ON COLUMN ods.vehicle_color_codes.created_at IS '创建时间';
COMMENT ON COLUMN ods.vehicle_color_codes.updated_at IS '更新时间';

-- ods.vehicle_platforms
COMMENT ON TABLE ods.vehicle_platforms IS '车型平台/底盘技术代号映射源表';
COMMENT ON COLUMN ods.vehicle_platforms.id IS '唯一主键ID';
COMMENT ON COLUMN ods.vehicle_platforms.platform_code IS '平台编码 (对应 platform_code)';
COMMENT ON COLUMN ods.vehicle_platforms.platform_name IS '平台名称 (如 MEB 电动平台, MQB 燃油平台)';
COMMENT ON COLUMN ods.vehicle_platforms.description IS '平台技术细节备注';
COMMENT ON COLUMN ods.vehicle_platforms.is_defined IS '是否激活';
COMMENT ON COLUMN ods.vehicle_platforms.first_seen IS '首次录入时间';
COMMENT ON COLUMN ods.vehicle_platforms.created_at IS '创建时间';
COMMENT ON COLUMN ods.vehicle_platforms.updated_at IS '更新时间';

-- ods.history_station_defect_summary
COMMENT ON TABLE ods.history_station_defect_summary IS '缺陷检测工位历史检测汇总源表';
COMMENT ON COLUMN ods.history_station_defect_summary.history_id IS '唯一主键ID';
COMMENT ON COLUMN ods.history_station_defect_summary.serial_number IS '车身唯一识别码 (等同于 vehicle_id 和 BODY_ID，跨源一一对应)。本表为一车多缺陷明细，统计车数时须 DISTINCT！';
COMMENT ON COLUMN ods.history_station_defect_summary.model IS 'eines检测程序代码';
COMMENT ON COLUMN ods.history_station_defect_summary.type_name IS '缺陷检测系统捕获的车型名称';
COMMENT ON COLUMN ods.history_station_defect_summary.black_roof IS '缺陷检测系统识别的黑顶类型描述';
COMMENT ON COLUMN ods.history_station_defect_summary.date_time IS '检测时间';
COMMENT ON COLUMN ods.history_station_defect_summary.color_code IS '缺陷检测系统识别的颜色代码';
COMMENT ON COLUMN ods.history_station_defect_summary.tunnel IS '检测设备通道编号，车间有三套';
COMMENT ON COLUMN ods.history_station_defect_summary.cycle IS '车身唯一识别码的检测次数';
COMMENT ON COLUMN ods.history_station_defect_summary.station_1_defect_count IS '右侧 检出的缺陷数量';
COMMENT ON COLUMN ods.history_station_defect_summary.station_2_defect_count IS '左侧 检出的缺陷数量';
COMMENT ON COLUMN ods.history_station_defect_summary.station_3_defect_count IS '车顶 检出的缺陷数量';
COMMENT ON COLUMN ods.history_station_defect_summary.station_4_defect_count IS '前盖 检出的缺陷数量';
COMMENT ON COLUMN ods.history_station_defect_summary.station_5_defect_count IS '尾门|后盖 检出的缺陷数量';
COMMENT ON COLUMN ods.history_station_defect_summary.total_defect_count IS '总缺陷数';

-- ods.carbody_history
COMMENT ON TABLE ods.carbody_history IS '车身历史过读写站明细流水表';
COMMENT ON COLUMN ods.carbody_history."ID" IS '唯一主键ID';
COMMENT ON COLUMN ods.carbody_history."DATE_EVT" IS '过读写站时间';
COMMENT ON COLUMN ods.carbody_history."SHIFT_NR" IS '过读写站当时的排班班次号';
COMMENT ON COLUMN ods.carbody_history."RW_STATION_ID" IS '读写站ID';
COMMENT ON COLUMN ods.carbody_history."RW_STATION_STATUS" IS '读写站状态代码';
COMMENT ON COLUMN ods.carbody_history."SKID_ID" IS '过读写站时绑定的雪橇/吊架载具ID';
COMMENT ON COLUMN ods.carbody_history."SKID_TYPE" IS '雪橇/吊架载具类型代码';
COMMENT ON COLUMN ods.carbody_history."SKID_IS_EMPTY" IS '是否为空雪橇/吊架 (1表示空雪橇/吊架, 0表示带车雪橇/吊架)';
COMMENT ON COLUMN ods.carbody_history."BODY_ID" IS '车身唯一识别码 (等同于 vehicle_id 和 serial_number，跨源一一对应)';
COMMENT ON COLUMN ods.carbody_history."BODY_TYPE" IS '车型代码 (对应 body_type)';
COMMENT ON COLUMN ods.carbody_history."MDS_DATA" IS '原始 MDS 电报电码';
COMMENT ON COLUMN ods.carbody_history."MDS_TELEGRAM_TYPE" IS 'MDS 电报格式分类代号';
COMMENT ON COLUMN ods.carbody_history."FK_ERP_HIST_ID" IS '关联 ERP 系统历史过读写站唯一ID';
COMMENT ON COLUMN ods.carbody_history."CYCLE_NUM" IS '生产循环号';
COMMENT ON COLUMN ods.carbody_history."PRODUCTION_SEGMENT_ID" IS '过读写站所在的具体生产路段/网格段 ID';
COMMENT ON COLUMN ods.carbody_history."ETL_MODIFY_DATE" IS 'ETL更新时间';
COMMENT ON COLUMN ods.carbody_history."ETL_SOURCE_ID" IS '数据来源的源头系统 ID';

-- ods.ods_fis_project_vehicle_orders
COMMENT ON TABLE ods.ods_fis_project_vehicle_orders IS '项目车生产订单明细数仓 ODS 物理贴源表';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.project_vehicle_no IS '项目车编号 (主键，如 PP2-EREV-VFF-56)';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.file_name IS '来源 Word 生产通知单文件名';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.project_stage IS '项目阶段 (如 VFF, PT)';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.block_no IS 'Block 编号';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.code_6bit IS '6位代码 (如 VA24CQ)';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.color_interior IS '外色内饰代码';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.kom_no IS 'KOM 订货号';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.knr_no IS 'KNR 生产流水号';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.pin_no IS 'PIN 识别码 (7位数字，如 1234567)';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.pin_prefix IS 'PIN 前缀 (如 782026)';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.composite_pin_no IS '合成 PIN 识别码 (13位 = 前缀 + pin_no)';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.created_at IS '首次入库时间';
COMMENT ON COLUMN ods.ods_fis_project_vehicle_orders.updated_at IS '最后更新时间';


-- ==========================================
-- 2. DIM 层 (维度表与字段注释)
-- ==========================================

-- dim.dim_process_area
COMMENT ON TABLE dim.dim_process_area IS '工艺区域维度表 (清洗与标准化的工艺区域)';
COMMENT ON COLUMN dim.dim_process_area.process_area_name IS '唯一主键';
COMMENT ON COLUMN dim.dim_process_area.source_area_id IS '源系统区域ID';
COMMENT ON COLUMN dim.dim_process_area.description IS '工艺区域的详细中文功能描述';
COMMENT ON COLUMN dim.dim_process_area.sort_order IS '工序流向排序序号 (数字越小在车间中越靠前)';
COMMENT ON COLUMN dim.dim_process_area.created_at IS '创建时间';
COMMENT ON COLUMN dim.dim_process_area.updated_at IS '更新时间';
COMMENT ON COLUMN dim.dim_process_area.etl_loaded_at IS 'ETL装载时间';

-- dim.dim_vehicle_profile
COMMENT ON TABLE dim.dim_vehicle_profile IS '车辆核心属性主维度表 (全量车辆的一车一档台账)';
COMMENT ON COLUMN dim.dim_vehicle_profile.vehicle_id IS '唯一主键，由贴源层 vehicle_id、serial_number、BODY_ID 统一汇聚而来';
COMMENT ON COLUMN dim.dim_vehicle_profile.body_type IS '车型代码 (如2N54Y)';
COMMENT ON COLUMN dim.dim_vehicle_profile.tracking_type_name IS '车辆跟踪系统转换得出的车型中文名';
COMMENT ON COLUMN dim.dim_vehicle_profile.defect_model IS '缺陷检测系统模编号';
COMMENT ON COLUMN dim.dim_vehicle_profile.defect_type_name IS '缺陷检测系统记录的检测程序代码';
COMMENT ON COLUMN dim.dim_vehicle_profile.platform_code IS '平台代码 (如 MEB, MQB)';
COMMENT ON COLUMN dim.dim_vehicle_profile.platform_name IS '平台名称';
COMMENT ON COLUMN dim.dim_vehicle_profile.color_code IS '颜色代码';
COMMENT ON COLUMN dim.dim_vehicle_profile.color_name IS '车辆颜色中文标准名';
COMMENT ON COLUMN dim.dim_vehicle_profile.is_black_roof IS '是否为黑顶车型 (依据跟踪及缺陷数据综合判定)';
COMMENT ON COLUMN dim.dim_vehicle_profile.black_roof_raw_tracking IS '跟踪系统记录的黑顶原始标志 (1/0/Y/N)';
COMMENT ON COLUMN dim.dim_vehicle_profile.black_roof_raw_defect IS '缺陷检测系统捕获的黑顶属性原始文字';
COMMENT ON COLUMN dim.dim_vehicle_profile.tracking_last_seen_at IS '跟踪最后可见时间';
COMMENT ON COLUMN dim.dim_vehicle_profile.defect_last_seen_at IS '检测最后可见时间';
COMMENT ON COLUMN dim.dim_vehicle_profile.current_position_id IS '车辆当前所处滚床位置记录ID (产品车当前绑定)';
COMMENT ON COLUMN dim.dim_vehicle_profile.current_carrier_id IS '车辆当前所处的雪橇/吊架载具 ID';
COMMENT ON COLUMN dim.dim_vehicle_profile.current_carrier_type IS '车辆当前所处雪橇/吊架的类型';
COMMENT ON COLUMN dim.dim_vehicle_profile.current_process_area IS '车辆当前所在的工艺区域';
COMMENT ON COLUMN dim.dim_vehicle_profile.current_full_rb_code IS '车辆当前所在的滚床完整物理编码 (PLC + 索引)';
COMMENT ON COLUMN dim.dim_vehicle_profile.current_position_updated_at IS '当前位置刷新时间';
COMMENT ON COLUMN dim.dim_vehicle_profile.etl_loaded_at IS 'ETL装载时间';
COMMENT ON COLUMN dim.dim_vehicle_profile.is_rework IS '是否为重工车 (基于 MES 车身过站特殊配置标志计算)';
COMMENT ON COLUMN dim.dim_vehicle_profile.has_defect_record IS '是否有关联 of 缺陷检测记录 (TRUE/FALSE)';
COMMENT ON COLUMN dim.dim_vehicle_profile.carbody_first_seen_at IS '首次过站读写站时间';
COMMENT ON COLUMN dim.dim_vehicle_profile.carbody_last_seen_at IS '末次过站读写站时间';
COMMENT ON COLUMN dim.dim_vehicle_profile.carbody_first_rw_station IS '首次过站读写站编码';
COMMENT ON COLUMN dim.dim_vehicle_profile.carbody_last_rw_station IS '末次过站读写站编码';
COMMENT ON COLUMN dim.dim_vehicle_profile.carbody_station_pass_count IS '在工艺段内累计过站读写站总频次';
COMMENT ON COLUMN dim.dim_vehicle_profile.carbody_reserved_1 IS '车身 MDS 备用字段 1';
COMMENT ON COLUMN dim.dim_vehicle_profile.carbody_reserved_2 IS '车身 MDS 备用字段 2';
COMMENT ON COLUMN dim.dim_vehicle_profile.retention_checkpoint_station IS '滞留监控关键读写站编码 (取自 1J440RB, K3IS140, K2IS075, K1IS135 中最新经过的节点)';
COMMENT ON COLUMN dim.dim_vehicle_profile.retention_checkpoint_pass_at IS '滞留监控关键读写站过站时间';
COMMENT ON COLUMN dim.dim_vehicle_profile.project_vehicle_no IS '项目车编号 (外键关联项目车生产订单明细)';


-- dim.carbody_registry
COMMENT ON TABLE dim.carbody_registry IS '车身过站读写站历史统计与注册维度表 (从明细流水中按车辆聚合)';
COMMENT ON COLUMN dim.carbody_registry.vehicle_id IS '唯一主键';
COMMENT ON COLUMN dim.carbody_registry.first_seen_at IS '首次过站读写站时间';
COMMENT ON COLUMN dim.carbody_registry.last_seen_at IS '末次过站读写站时间';
COMMENT ON COLUMN dim.carbody_registry.first_rw_station IS '首次被记录的过站读写站';
COMMENT ON COLUMN dim.carbody_registry.last_rw_station IS '最近被记录的过站读写站';
COMMENT ON COLUMN dim.carbody_registry.first_body_type IS '首次过站读写站时的车身类型';
COMMENT ON COLUMN dim.carbody_registry.last_body_type IS '最近一次过站读写站时的车身类型';
COMMENT ON COLUMN dim.carbody_registry.station_pass_count IS '该车身在生产线中累计过站读写站的次数';
COMMENT ON COLUMN dim.carbody_registry.body_type IS '电报 MDS 数据中截取的车身类型 (45-49位)';
COMMENT ON COLUMN dim.carbody_registry.platform_code IS '电报 MDS 数据中截取的车型平台代码 (51-53位)';
COMMENT ON COLUMN dim.carbody_registry.color_code IS '电报 MDS 数据中截取的车身颜色代码 (59-62位)';
COMMENT ON COLUMN dim.carbody_registry.black_roof_flag IS '电报 MDS 数据中截取的黑顶特殊配置位 (137位)';
COMMENT ON COLUMN dim.carbody_registry.rework_flag IS '电报 MDS 数据中截取的返修特殊配置位 (139位)';
COMMENT ON COLUMN dim.carbody_registry.reserved_1 IS '电报 MDS 数据预留特殊配置位 1 (138位)';
COMMENT ON COLUMN dim.carbody_registry.reserved_2 IS '电报 MDS 数据预留特殊配置位 2 (140位)';
COMMENT ON COLUMN dim.carbody_registry.retention_checkpoint_station IS '滞留监控关键读写站编码 (取自 1J440RB, K3IS140, K2IS075, K1IS135 中最新经过的节点)';
COMMENT ON COLUMN dim.carbody_registry.retention_checkpoint_pass_at IS '滞留监控关键读写站过站时间';
COMMENT ON COLUMN dim.carbody_registry.project_vehicle_no IS '项目车编号 (外键关联项目车生产订单明细)';
COMMENT ON COLUMN dim.carbody_registry.etl_loaded_at IS 'ETL装载时间';


-- ==========================================
-- 3. FCT 层 (事实层物化视图与字段注释)
-- ==========================================

-- fct.fct_position_current_all
COMMENT ON MATERIALIZED VIEW fct.fct_position_current_all IS '物化视图 - 现场所有占位当前事实表 (包含正常车、异常占位、空橇点等全量快照)';
COMMENT ON COLUMN fct.fct_position_current_all.position_id IS '设备位置ID (ods.rb_position_data 主键)';
COMMENT ON COLUMN fct.fct_position_current_all.plc IS 'PLC标识名称';
COMMENT ON COLUMN fct.fct_position_current_all.tag IS 'RFID 点位编码';
COMMENT ON COLUMN fct.fct_position_current_all.rb_index IS '不完整滚床编号';
COMMENT ON COLUMN fct.fct_position_current_all.full_rb_code IS '滚床完整物理编码 (PLC + 索引)';
COMMENT ON COLUMN fct.fct_position_current_all.remark IS '备注未用';
COMMENT ON COLUMN fct.fct_position_current_all.process_area IS '工艺区域 (等同 area_name)';
COMMENT ON COLUMN fct.fct_position_current_all.carrier_id IS '雪橇/吊架ID/载具编号';
COMMENT ON COLUMN fct.fct_position_current_all.carrier_type IS '雪橇/吊架/载具类型代码';
COMMENT ON COLUMN fct.fct_position_current_all.vehicle_id IS '车身唯一识别码';
COMMENT ON COLUMN fct.fct_position_current_all.project_vehicle_no IS '项目车编号 (关联项目车生产订单明细)';
COMMENT ON COLUMN fct.fct_position_current_all.body_type IS '车型代码 (五位车身类型码)';
COMMENT ON COLUMN fct.fct_position_current_all.color_code IS '车身颜色代码';
COMMENT ON COLUMN fct.fct_position_current_all.platform_code IS '车型平台';
COMMENT ON COLUMN fct.fct_position_current_all.black_roof_flag IS '黑顶标记 (1/Y表示黑顶)';
COMMENT ON COLUMN fct.fct_position_current_all.rework_flag IS '返修车标记 (1/Y表示返修车)';
COMMENT ON COLUMN fct.fct_position_current_all.raw_data IS '通信原始报文';
COMMENT ON COLUMN fct.fct_position_current_all.position_created_at IS '位置创建时间';
COMMENT ON COLUMN fct.fct_position_current_all.vehicle_updated_at IS '车辆位置刷新时间';
COMMENT ON COLUMN fct.fct_position_current_all.entity_type IS '占位实体类型 (project_vehicle-项目车, product_vehicle-产品车/量产车, abnormal_vehicle-异常车)';
COMMENT ON COLUMN fct.fct_position_current_all.abnormal_type IS '异常占位分类 (如 empty_vehicle_id_with_carrier, non_product_prefix 等)';

-- fct.fct_vehicle_position_current
COMMENT ON MATERIALIZED VIEW fct.fct_vehicle_position_current IS '物化视图 - 仅限正常车(项目车与产品车)当前位置最新事实表 (过滤异常且按车辆去重)';
COMMENT ON COLUMN fct.fct_vehicle_position_current.vehicle_id IS '车身唯一识别码 (主键)';
COMMENT ON COLUMN fct.fct_vehicle_position_current.project_vehicle_no IS '项目车编号 (关联项目车生产订单明细)';
COMMENT ON COLUMN fct.fct_vehicle_position_current.position_id IS '设备位置ID';
COMMENT ON COLUMN fct.fct_vehicle_position_current.plc IS 'PLC标识名称';
COMMENT ON COLUMN fct.fct_vehicle_position_current.tag IS 'RFID 点位编码';
COMMENT ON COLUMN fct.fct_vehicle_position_current.rb_index IS '不完整滚床编号';
COMMENT ON COLUMN fct.fct_vehicle_position_current.full_rb_code IS '滚床完整物理编码 (PLC + 索引)';
COMMENT ON COLUMN fct.fct_vehicle_position_current.remark IS '备注未用';
COMMENT ON COLUMN fct.fct_vehicle_position_current.process_area IS '工艺区域';
COMMENT ON COLUMN fct.fct_vehicle_position_current.carrier_id IS '雪橇/吊架ID/载具编号';
COMMENT ON COLUMN fct.fct_vehicle_position_current.carrier_type IS '雪橇/吊架/载具类型代码';
COMMENT ON COLUMN fct.fct_vehicle_position_current.body_type IS '车型代码 (五位车身类型码)';
COMMENT ON COLUMN fct.fct_vehicle_position_current.color_code IS '车身颜色代码';
COMMENT ON COLUMN fct.fct_vehicle_position_current.platform_code IS '车型平台';
COMMENT ON COLUMN fct.fct_vehicle_position_current.black_roof_flag IS '黑顶标记 (1/Y表示黑顶)';
COMMENT ON COLUMN fct.fct_vehicle_position_current.rework_flag IS '返修车标记 (1/Y表示返修车)';
COMMENT ON COLUMN fct.fct_vehicle_position_current.raw_data IS '通信原始报文';
COMMENT ON COLUMN fct.fct_vehicle_position_current.position_created_at IS '位置创建时间';
COMMENT ON COLUMN fct.fct_vehicle_position_current.vehicle_updated_at IS '车辆位置刷新时间';

-- fct.fct_vehicle_defect_detection
COMMENT ON MATERIALIZED VIEW fct.fct_vehicle_defect_detection IS '物化视图 - 车辆缺陷检测事件事实表 (去除无用占位数据后的检测结果事实)';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.history_id IS '唯一主键ID (ods.history_station_defect_summary 主键)';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.vehicle_id IS '车身唯一识别码';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.model IS 'eines检测程序代码';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.type_name IS '缺陷检测系统捕获的车型名称';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.black_roof IS '缺陷检测系统识别的黑顶类型描述';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.detect_time IS '缺陷检测时间';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.color_code IS '缺陷检测系统识别的颜色代码';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.tunnel IS '检测设备通道编号';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.cycle IS '车身唯一识别码的检测次数';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.station_1_defect_count IS '右侧检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.station_2_defect_count IS '左侧检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.station_3_defect_count IS '车顶检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.station_4_defect_count IS '前盖检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.station_5_defect_count IS '尾门|后盖检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_detection.total_defect_count IS '总缺陷数';

-- fct.fct_vehicle_defect_enriched
COMMENT ON MATERIALIZED VIEW fct.fct_vehicle_defect_enriched IS '物化视图 - 车身缺陷与过读写站全量富集事实宽表。粒度：一缺陷事件一行（一车可能多行）。统计车数必须用 DISTINCT vehicle_id 去重！';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.vehicle_id IS '车身唯一识别码 (主键前部)。本表为一车多缺陷明细，统计车数时须 DISTINCT！';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.body_type IS '车型代码 (对应 body_type)';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.platform_code IS '车型平台/底盘技术代号';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.color_code IS '车身颜色代码';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.black_roof_flag IS '电报 MDS 数据截取的黑顶特殊配置位 (137位)';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.rework_flag IS '电报 MDS 数据截取的返修特殊配置位 (139位)';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.reserved_1 IS '电报 MDS 数据预留特殊配置位 1 (138位)';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.reserved_2 IS '电报 MDS 数据预留特殊配置位 2 (140位)';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.first_seen_at IS '首次过读写站时间';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.last_seen_at IS '末次过读写站时间';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.first_rw_station IS '首次被记录的过读写站';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.last_rw_station IS '最近被记录的过读写站';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.first_body_type IS '首次过读写站时的车身类型';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.last_body_type IS '最近一次过读写站时的车身类型';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.station_pass_count IS '该车身在生产线中累计过读写站的次数';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.history_id IS '唯一主键ID (缺陷事件主键，主键后部)';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.defect_model IS 'eines检测程序代码';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.defect_type_name IS '缺陷检测系统记录的检测程序代码';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.defect_black_roof IS '缺陷检测系统识别的黑顶属性原始文字';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.defect_color_code IS '缺陷检测系统识别的颜色代码';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.detect_time IS '缺陷检测时间';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.tunnel IS '检测设备通道编号';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.cycle IS '车身唯一识别码的检测次数';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.station_1_defect_count IS '右侧检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.station_2_defect_count IS '左侧检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.station_3_defect_count IS '车顶检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.station_4_defect_count IS '前盖检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.station_5_defect_count IS '尾门|后盖检出的缺陷数量';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.total_defect_count IS '总缺陷数';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.has_defect_record IS '是否拥有缺陷检测记录标志';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.retention_checkpoint_station IS '滞留监控关键读写站编码 (取自 1J440RB, K3IS140, K2IS075, K1IS135 中最新经过的节点)';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.retention_checkpoint_pass_at IS '滞留监控关键读写站过站时间';
COMMENT ON COLUMN fct.fct_vehicle_defect_enriched.project_vehicle_no IS '项目车编号 (透传自 carbody 物理维表)';

-- fct.fct_abnormal_vehicle_current
COMMENT ON MATERIALIZED VIEW fct.fct_abnormal_vehicle_current IS '物化视图 - 现场当前异常占位及载具事实表';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.position_id IS '设备位置ID (主键)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.plc IS 'PLC标识名称';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.tag IS 'RFID 点位编码';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.rb_index IS '不完整滚床编号';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.full_rb_code IS '滚床完整物理编码 (PLC + 索引)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.remark IS '备注未用';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.process_area IS '工艺区域';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.carrier_id IS '雪橇/吊架ID/载具编号';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.carrier_type IS '雪橇/吊架载具类型代码';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.vehicle_id IS '车辆唯一识别码 (异常占位中的车身码)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.project_vehicle_no IS '项目车编号 (透传自基础占位事实表)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.body_type IS '车型代码 (五位车身类型码)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.color_code IS '车身颜色代码';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.platform_code IS '车型平台';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.black_roof_flag IS '黑顶标记 (1/Y表示黑顶)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.rework_flag IS '返修车标记 (1/Y表示返修车)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.raw_data IS '通信原始报文';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.position_created_at IS '位置创建时间';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.vehicle_updated_at IS '车辆位置刷新时间';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.entity_type IS '占位实体类型 (abnormal_vehicle)';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.abnormal_type IS '异常占位分类';
COMMENT ON COLUMN fct.fct_abnormal_vehicle_current.abnormal_reason IS '异常原因文字描述说明';


-- ==========================================
-- 4. MART 层 (分析集市物化视图与字段注释)
-- ==========================================

-- mart.mart_vehicle_quality_360
COMMENT ON MATERIALIZED VIEW mart.mart_vehicle_quality_360 IS '物化视图 - 车辆360度质量与当前位置全景关联明细表（基于车身过站富集表驱动，包含在产未检车辆与漏检车辆）。粒度：一缺陷事件或一车身一行。统计车数必须用 DISTINCT vehicle_id 去重！';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.history_id IS '唯一主键ID (缺陷事件主键，未检测车辆则为NULL)';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.vehicle_id IS '车身唯一识别码。统计车数时须 DISTINCT！';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.detect_time IS '缺陷检测时间';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.defect_model IS 'eines检测程序代码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.defect_type_name IS '缺陷检测系统记录的检测程序代码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.defect_black_roof IS '缺陷检测系统识别的黑顶属性原始文字';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.defect_color_code IS '缺陷检测系统识别的颜色代码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.tunnel IS '检测设备通道编号';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.cycle IS '车身唯一识别码的检测次数';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.station_1_defect_count IS '右侧检出的缺陷数量';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.station_2_defect_count IS '左侧检出的缺陷数量';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.station_3_defect_count IS '车顶检出的缺陷数量';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.station_4_defect_count IS '前盖检出的缺陷数量';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.station_5_defect_count IS '尾门|后盖检出的缺陷数量';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.total_defect_count IS '总缺陷数';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.has_defect_record IS '是否存在缺陷检测记录 (TRUE/FALSE)';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.body_type IS '车辆当前所处车型代码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.tracking_type_name IS '车辆跟踪系统转换得出的车型中文名';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.tracking_color_code IS '车辆当前所处的跟踪系统颜色代码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.tracking_color_name IS '车辆当前所处的跟踪系统颜色中文名';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.platform_code IS '车辆当前的平台代码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.platform_name IS '车辆当前的平台中文名';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.black_roof_flag IS '车辆当前的黑顶标记 (1/Y表示黑顶)';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.rework_flag IS '车辆当前的返修车标记 (1/Y表示返修车)';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carbody_first_seen_at IS '首次过站读写站时间';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carbody_last_seen_at IS '末次过站读写站时间';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carbody_first_rw_station IS '首次过站读写站编码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carbody_last_rw_station IS '末次过站读写站编码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carbody_station_pass_count IS '在工艺段内累计过站读写站总频次';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carbody_retention_checkpoint_station IS '滞留监控关键读写站编码';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carbody_retention_checkpoint_pass_at IS '滞留监控关键读写站过站时间';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.project_vehicle_no IS '项目车编号 (透传自缺陷富集宽表)';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.process_area IS '车辆当前所在的工艺区域';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.plc IS '车辆当前所处位置PLC标识名称';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.rb_index IS '车辆当前所处不完整滚床编号';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.full_rb_code IS '车辆当前所在的滚床完整物理编码 (PLC + 索引)';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carrier_id IS '车辆当前所在的雪橇/吊架载具 ID';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carrier_type IS '车辆当前所处雪橇/吊架的类型';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.carrier_type_name_cn IS '雪橇/吊架载具中文类型名称';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.position_created_at IS '车辆位置创建时间';
COMMENT ON COLUMN mart.mart_vehicle_quality_360.vehicle_updated_at IS '车辆当前位置刷新时间';

-- mart.mart_abnormal_vehicle_current
COMMENT ON MATERIALIZED VIEW mart.mart_abnormal_vehicle_current IS '物化视图 - 现场当前异常车辆的工艺分布与警报信息看板表';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.position_id IS '设备位置ID (主键)';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.vehicle_id IS '车辆唯一识别码 (异常占位中的车身码)';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.project_vehicle_no IS '项目车编号 (透传自异常事实视图)';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.abnormal_type IS '异常占位分类';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.abnormal_reason IS '异常原因文字描述说明';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.process_area IS '车辆当前所在的工艺区域';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.process_area_description IS '工艺区域中文名称与描述';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.process_area_sort_order IS '工序流向排序序号';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.carrier_id IS '车辆当前所在的雪橇/吊架载具 ID';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.carrier_type IS '车辆当前所处雪橇/吊架的类型';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.carrier_type_name_cn IS '雪橇/吊架载具中文类型名称';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.plc IS '车辆当前所处位置PLC标识名称';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.rb_index IS '车辆当前所处不完整滚床编号';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.full_rb_code IS '车辆当前所在的滚床完整物理编码 (PLC + 索引)';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.remark IS '备注未用';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.body_type IS '车辆当前所处车型代码';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.tracking_type_name IS '车辆跟踪系统转换得出的车型中文名';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.color_code IS '车辆当前所处颜色代码';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.tracking_color_name IS '车辆当前所处的跟踪系统颜色中文名';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.platform_code IS '车辆当前的平台代码';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.platform_name IS '车辆当前的平台中文名';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.black_roof_flag IS '车辆当前的黑顶标记 (1/Y表示黑顶)';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.rework_flag IS '车辆当前的返修车标记 (1/Y表示返修车)';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.position_created_at IS '车辆位置创建时间';
COMMENT ON COLUMN mart.mart_abnormal_vehicle_current.vehicle_updated_at IS '车辆当前位置刷新时间';

-- mart.mart_position_current_overview
COMMENT ON MATERIALIZED VIEW mart.mart_position_current_overview IS '物化视图 - 当前滚床现场所有占位全景汇总总览表 (含车辆实体名称、状态说明等)';
COMMENT ON COLUMN mart.mart_position_current_overview.position_id IS '设备位置ID (主键)';
COMMENT ON COLUMN mart.mart_position_current_overview.entity_type IS '占位实体类型 (project_vehicle-项目车, product_vehicle-产品车/量产车, abnormal_vehicle-异常车)';
COMMENT ON COLUMN mart.mart_position_current_overview.entity_type_name IS '占位实体类型中文名称';
COMMENT ON COLUMN mart.mart_position_current_overview.vehicle_status_code IS '车辆状态分类代码';
COMMENT ON COLUMN mart.mart_position_current_overview.vehicle_status_name IS '车辆状态分类中文名称';
COMMENT ON COLUMN mart.mart_position_current_overview.abnormal_type IS '异常占位分类';
COMMENT ON COLUMN mart.mart_position_current_overview.abnormal_reason IS '异常原因文字描述说明';
COMMENT ON COLUMN mart.mart_position_current_overview.process_area IS '车辆当前所在的工艺区域';
COMMENT ON COLUMN mart.mart_position_current_overview.process_area_description IS '工艺区域中文名称与描述';
COMMENT ON COLUMN mart.mart_position_current_overview.process_area_sort_order IS '工序流向排序序号';
COMMENT ON COLUMN mart.mart_position_current_overview.carrier_id IS '雪橇/吊架载具ID/载具编号';
COMMENT ON COLUMN mart.mart_position_current_overview.carrier_type IS '雪橇/吊架/载具类型代码';
COMMENT ON COLUMN mart.mart_position_current_overview.carrier_type_name_cn IS '载具类型中文名称';
COMMENT ON COLUMN mart.mart_position_current_overview.plc IS 'PLC标识名称';
COMMENT ON COLUMN mart.mart_position_current_overview.tag IS 'RFID 点位编码';
COMMENT ON COLUMN mart.mart_position_current_overview.rb_index IS '不完整滚床编号';
COMMENT ON COLUMN mart.mart_position_current_overview.full_rb_code IS '滚床完整物理编码 (PLC + 索引)';
COMMENT ON COLUMN mart.mart_position_current_overview.remark IS '备注未用';
COMMENT ON COLUMN mart.mart_position_current_overview.vehicle_id IS '车身唯一识别码';
COMMENT ON COLUMN mart.mart_position_current_overview.project_vehicle_no IS '项目车编号 (关联项目车生产订单明细)';
COMMENT ON COLUMN mart.mart_position_current_overview.body_type IS '车型代码 (五位车身类型码)';
COMMENT ON COLUMN mart.mart_position_current_overview.tracking_type_name IS '车型中文官方名称 (如 ID.3, 帕萨特)';
COMMENT ON COLUMN mart.mart_position_current_overview.color_code IS '车身颜色代码';
COMMENT ON COLUMN mart.mart_position_current_overview.tracking_color_name IS '车辆颜色中文标准名';
COMMENT ON COLUMN mart.mart_position_current_overview.platform_code IS '车型平台';
COMMENT ON COLUMN mart.mart_position_current_overview.platform_name IS '平台名称';
COMMENT ON COLUMN mart.mart_position_current_overview.black_roof_flag IS '跟踪原始黑顶特殊配置位';
COMMENT ON COLUMN mart.mart_position_current_overview.rework_flag IS '跟踪原始返修车标记';
COMMENT ON COLUMN mart.mart_position_current_overview.is_black_roof IS '是否为黑顶车型';
COMMENT ON COLUMN mart.mart_position_current_overview.is_rework IS '是否为返修车';
COMMENT ON COLUMN mart.mart_position_current_overview.position_created_at IS '位置创建时间';
COMMENT ON COLUMN mart.mart_position_current_overview.vehicle_updated_at IS '车辆位置刷新时间';


-- ==========================================


-- ==========================================
-- 5. META 层 (元数据表与字段注释)
-- ==========================================

-- meta.sync_job_log
COMMENT ON TABLE meta.sync_job_log IS '同步与刷新任务的审计日志记录表';
COMMENT ON COLUMN meta.sync_job_log.id IS '唯一主键ID';
COMMENT ON COLUMN meta.sync_job_log.job_name IS '调用的刷新或计算过程任务名称 (如 refresh_analytics_all)';
COMMENT ON COLUMN meta.sync_job_log.started_at IS '开始时间';
COMMENT ON COLUMN meta.sync_job_log.finished_at IS '结束时间';
COMMENT ON COLUMN meta.sync_job_log.status IS '任务最终状态 (running-运行中, success-成功, failed-失败)';
COMMENT ON COLUMN meta.sync_job_log.message IS '任务执行情况输出消息 (如成功刷新行数或错误详细报错)';

-- meta.refresh_watermark
COMMENT ON TABLE meta.refresh_watermark IS '分析库抽取与计算增量同步水位标记表';
COMMENT ON COLUMN meta.refresh_watermark.source_name IS '唯一主键';
COMMENT ON COLUMN meta.refresh_watermark.watermark_value IS '记录的最大同步水位线值 (ID或时间戳)';
COMMENT ON COLUMN meta.refresh_watermark.updated_at IS '更新时间';
