-- 更新时间：2026-04-09 22:11 Asia/Shanghai
-- 主要内容：
-- 1. 新增 model_attribute_map 映射表，用于按 model 补充 type_name 与 black_roof
-- 2. 新增 history_station_defect_summary 汇总表，用于按 history_id 汇总 station 1~5 的缺陷数量
-- 3. 提供 COMMENT、初始化装载与刷新 SQL，便于后续给 LLM 做结构化分析

BEGIN;

DROP TABLE IF EXISTS history_station_defect_summary;
DROP TABLE IF EXISTS model_attribute_map;

CREATE TABLE model_attribute_map (
    model INTEGER PRIMARY KEY,
    type_name VARCHAR(100) NOT NULL,
    black_roof VARCHAR(100)
);

COMMENT ON TABLE model_attribute_map IS
'车型属性映射表。根据 history.model 映射出 type_name 和 black_roof，用于汇总表生成与 LLM 字段理解。';

COMMENT ON COLUMN model_attribute_map.model IS
'history.model 的车型编码，作为映射主键。';

COMMENT ON COLUMN model_attribute_map.type_name IS
'由 model 映射得到的车型名称，如 A7、Tiguan。';

COMMENT ON COLUMN model_attribute_map.black_roof IS
'由 model 映射得到的黑车顶标记。可为空；例如 黑车顶。';

-- 将 defect_database/model_map.json 中的映射同步到这里维护。
INSERT INTO model_attribute_map (model, type_name, black_roof)
VALUES
    (4, 'TiguanL', NULL),
    (7, 'A7', NULL),
    (19, 'Tiguan Pro', NULL),
    (20, 'A5', NULL),
    (21, 'A5', NULL),
    (22, 'A5', '黑车顶'),
    (23, 'E5', NULL),
    (25, 'TiguanL', '黑车顶'),
    (26, 'Tiguan Pro', '黑车顶'),
    (27, 'E7', NULL),
    (28, 'TiguanL PHEV', NULL),
    (77, 'A7', '黑车顶')
ON CONFLICT (model) DO UPDATE
SET
    type_name = EXCLUDED.type_name,
    black_roof = EXCLUDED.black_roof;

CREATE TABLE history_station_defect_summary (
    history_id INTEGER PRIMARY KEY,
    model INTEGER NOT NULL,
    type_name VARCHAR(100),
    black_roof VARCHAR(100),
    serial_number VARCHAR(255),
    date_time TIMESTAMP NOT NULL,
    color_code VARCHAR(255),
    tunnel INTEGER,
    cycle INTEGER,
    station_1_defect_count INTEGER NOT NULL DEFAULT 0,
    station_2_defect_count INTEGER NOT NULL DEFAULT 0,
    station_3_defect_count INTEGER NOT NULL DEFAULT 0,
    station_4_defect_count INTEGER NOT NULL DEFAULT 0,
    station_5_defect_count INTEGER NOT NULL DEFAULT 0,
    total_defect_count INTEGER NOT NULL DEFAULT 0
);

COMMENT ON TABLE history_station_defect_summary IS
'缺陷检测汇总表。每个 history_id 对应一次检测记录，按 station=1~5 且 diameter>0 统计缺陷数量，并补充车型与黑车顶属性，供统计分析与 LLM 理解使用。';

COMMENT ON COLUMN history_station_defect_summary.history_id IS
'检测编号，主键，对应 history.history_id。一次检测生成一个唯一 history_id。';

COMMENT ON COLUMN history_station_defect_summary.model IS
'车型编码，对应 history.model。';

COMMENT ON COLUMN history_station_defect_summary.type_name IS
'由 model_attribute_map 根据 model 映射得到的车型名称。';

COMMENT ON COLUMN history_station_defect_summary.black_roof IS
'由 model_attribute_map 根据 model 映射得到的黑车顶标记。';

COMMENT ON COLUMN history_station_defect_summary.serial_number IS
'检测对象编号，对应 history.serial_number。';

COMMENT ON COLUMN history_station_defect_summary.date_time IS
'检测时间，对应 history.date_time。';

COMMENT ON COLUMN history_station_defect_summary.color_code IS
'颜色代码，对应 history.color_code。';

COMMENT ON COLUMN history_station_defect_summary.tunnel IS
'检测通道，对应 history.tunnel。';

COMMENT ON COLUMN history_station_defect_summary.cycle IS
'检测循环号，对应 history."CYCLE"。在汇总表中统一命名为小写 cycle，便于 SQL 使用与 LLM 理解。';

COMMENT ON COLUMN history_station_defect_summary.station_1_defect_count IS
'当前 history_id 下，history_detail 中 station=1 且 diameter>0 的记录数量。';

COMMENT ON COLUMN history_station_defect_summary.station_2_defect_count IS
'当前 history_id 下，history_detail 中 station=2 且 diameter>0 的记录数量。';

COMMENT ON COLUMN history_station_defect_summary.station_3_defect_count IS
'当前 history_id 下，history_detail 中 station=3 且 diameter>0 的记录数量。';

COMMENT ON COLUMN history_station_defect_summary.station_4_defect_count IS
'当前 history_id 下，history_detail 中 station=4 且 diameter>0 的记录数量。';

COMMENT ON COLUMN history_station_defect_summary.station_5_defect_count IS
'当前 history_id 下，history_detail 中 station=5 且 diameter>0 的记录数量。';

COMMENT ON COLUMN history_station_defect_summary.total_defect_count IS
'当前 history_id 下，station=1~5 且 diameter>0 的缺陷记录总数，等于 station_1_defect_count 到 station_5_defect_count 之和。';

-- 初始化或全量刷新时，可直接执行以下逻辑。
TRUNCATE TABLE history_station_defect_summary;

INSERT INTO history_station_defect_summary (
    history_id,
    model,
    type_name,
    black_roof,
    serial_number,
    date_time,
    color_code,
    tunnel,
    cycle,
    station_1_defect_count,
    station_2_defect_count,
    station_3_defect_count,
    station_4_defect_count,
    station_5_defect_count,
    total_defect_count
)
SELECT
    h.history_id,
    h.model,
    mam.type_name,
    mam.black_roof,
    h.serial_number,
    h.date_time,
    h.color_code,
    h.tunnel,
    h."CYCLE" AS cycle,
    COUNT(*) FILTER (WHERE hd.station = 1 AND hd.diameter > 0) AS station_1_defect_count,
    COUNT(*) FILTER (WHERE hd.station = 2 AND hd.diameter > 0) AS station_2_defect_count,
    COUNT(*) FILTER (WHERE hd.station = 3 AND hd.diameter > 0) AS station_3_defect_count,
    COUNT(*) FILTER (WHERE hd.station = 4 AND hd.diameter > 0) AS station_4_defect_count,
    COUNT(*) FILTER (WHERE hd.station = 5 AND hd.diameter > 0) AS station_5_defect_count,
    COUNT(*) FILTER (WHERE hd.station BETWEEN 1 AND 5 AND hd.diameter > 0) AS total_defect_count
FROM history AS h
LEFT JOIN history_detail AS hd
    ON hd.history_id = h.history_id
LEFT JOIN model_attribute_map AS mam
    ON mam.model = h.model
GROUP BY
    h.history_id,
    h.model,
    mam.type_name,
    mam.black_roof,
    h.serial_number,
    h.date_time,
    h.color_code,
    h.tunnel,
    h."CYCLE";

COMMIT;
