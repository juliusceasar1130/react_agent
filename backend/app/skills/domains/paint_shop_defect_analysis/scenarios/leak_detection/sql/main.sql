WITH passed_vehicles AS (
    -- 步骤1：获取在指定过车时间内，通过3个检测入口读写站的车辆
    SELECT 
        h."BODY_ID" AS vehicle_id,
        h."RW_STATION_ID" AS pass_station,
        h."DATE_EVT" AS pass_time,
        CASE
            WHEN h."RW_STATION_ID" = 'L3ACC21IS01' THEN '面漆1线'
            WHEN h."RW_STATION_ID" = 'L3ACC21IS02' THEN '面漆2线'
            WHEN h."RW_STATION_ID" = 'L3ACC21IS03' THEN '面漆3线'
        END AS expected_line
    FROM ods.carbody_history h
    WHERE h."RW_STATION_ID" IN ('L3ACC21IS01', 'L3ACC21IS02', 'L3ACC21IS03')
      AND h."DATE_EVT" >= '{{start_time}}'                      -- 限制过站时间范围
      AND h."DATE_EVT" <= '{{end_time}}'
      {% if station_id %}
      AND h."RW_STATION_ID" = '{{station_id}}'
      {% endif %}
)
-- 步骤2：左关联缺陷事实表，全局未匹配到任何检测流水 (history_id IS NULL) 判定为真正的漏检
SELECT
    pv.vehicle_id AS "BODY_ID",
    pv.pass_station,
    pv.expected_line,
    pv.pass_time,
    vbt.type_name,
    vp.current_process_area,
    vp.current_carrier_id
FROM passed_vehicles pv
LEFT JOIN fct.fct_vehicle_defect_detection d 
  ON pv.vehicle_id = d.vehicle_id                              -- 核心：全局关联防误报
LEFT JOIN dim.dim_vehicle_profile vp 
  ON pv.vehicle_id = vp.vehicle_id
LEFT JOIN ods.vehicle_body_types vbt 
  ON vp.body_type = vbt.body_type
WHERE d.history_id IS NULL                                      -- 核心：无检测事实
ORDER BY pv.pass_time ASC;
