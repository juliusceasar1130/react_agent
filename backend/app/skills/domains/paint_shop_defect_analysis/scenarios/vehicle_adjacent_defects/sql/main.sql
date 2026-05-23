-- 步骤1：定位目标车辆在指定读写站的最近一次过点时间
WITH target_event AS (
    SELECT "BODY_ID", "DATE_EVT", "BODY_TYPE"
    FROM ods.carbody_history
    WHERE "BODY_ID" = '{{vehicle_id}}' 
      AND "RW_STATION_ID" = '{{station_id}}'
    ORDER BY "DATE_EVT" DESC
    LIMIT 1
),
-- 步骤2：根据目标车的过点时间，向前推和向后推，找到前后各 N 辆车，并将目标车一起合并输出
adjacent_events AS (
    SELECT "BODY_ID", "DATE_EVT", "BODY_TYPE", 'target' AS car_role
    FROM target_event
    UNION ALL
    SELECT "BODY_ID", "DATE_EVT", "BODY_TYPE", 'before' AS car_role
    FROM (
        SELECT "BODY_ID", "DATE_EVT", "BODY_TYPE"
        FROM ods.carbody_history
        WHERE "RW_STATION_ID" = '{{station_id}}'
          AND "DATE_EVT" < (SELECT "DATE_EVT" FROM target_event)
        ORDER BY "DATE_EVT" DESC
        LIMIT {{n_adjacent}}
    ) b
    UNION ALL
    SELECT "BODY_ID", "DATE_EVT", "BODY_TYPE", 'after' AS car_role
    FROM (
        SELECT "BODY_ID", "DATE_EVT", "BODY_TYPE"
        FROM ods.carbody_history
        WHERE "RW_STATION_ID" = '{{station_id}}'
          AND "DATE_EVT" > (SELECT "DATE_EVT" FROM target_event)
        ORDER BY "DATE_EVT" ASC
        LIMIT {{n_adjacent}}
    ) a
),
-- 步骤3：将这批相邻车辆（含目标车）与缺陷汇总表关联，并计算缺陷检测时间与过点时间的差值绝对值
defect_matches AS (
    SELECT 
        a.car_role,
        a."BODY_ID",
        a."BODY_TYPE" AS body_type,
        a."DATE_EVT" AS pass_time,
        d.date_time AS detect_time,
        ABS(EXTRACT(EPOCH FROM (d.date_time - a."DATE_EVT"))) AS time_diff_sec,
        d.station_1_defect_count,
        d.station_2_defect_count,
        d.station_3_defect_count,
        d.station_4_defect_count,
        d.station_5_defect_count,
        d.total_defect_count,
        d.color_code,
        d.black_roof,
        ROW_NUMBER() OVER(PARTITION BY a."BODY_ID" ORDER BY ABS(EXTRACT(EPOCH FROM (d.date_time - a."DATE_EVT"))) ASC) as rn
    FROM adjacent_events a
    LEFT JOIN ods.history_station_defect_summary d 
      ON a."BODY_ID" = d.serial_number
)
-- 步骤4：每辆车只保留离过点时间最近的一条缺陷记录（rn = 1），并关联车型字典获取名称
SELECT 
    dm.car_role,
    dm."BODY_ID",
    dm.body_type,
    dm.color_code,
    dm.black_roof,
    vbt.type_name,
    dm.pass_time,
    dm.detect_time,
    dm.time_diff_sec,
    dm.station_1_defect_count,
    dm.station_2_defect_count,
    dm.station_3_defect_count,
    dm.station_4_defect_count,
    dm.station_5_defect_count,
    dm.total_defect_count
FROM defect_matches dm
LEFT JOIN ods.vehicle_body_types vbt 
  ON dm.body_type = vbt.body_type
WHERE dm.rn = 1
ORDER BY dm.pass_time ASC;
