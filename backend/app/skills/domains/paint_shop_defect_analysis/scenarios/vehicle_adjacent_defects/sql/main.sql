WITH target_event AS (
    SELECT "BODY_ID", "DATE_EVT"
    FROM ods.carbody_history
    WHERE "BODY_ID" = '{{vehicle_id}}' 
      AND "RW_STATION_ID" = '{{station_id}}'
    ORDER BY "DATE_EVT" DESC
    LIMIT 1
),
adjacent_events AS (
    SELECT "BODY_ID", "DATE_EVT", 'target' AS car_role
    FROM target_event
    UNION ALL
    SELECT "BODY_ID", "DATE_EVT", 'before' AS car_role
    FROM (
        SELECT "BODY_ID", "DATE_EVT"
        FROM ods.carbody_history
        WHERE "RW_STATION_ID" = '{{station_id}}'
          AND "DATE_EVT" < (SELECT "DATE_EVT" FROM target_event)
        ORDER BY "DATE_EVT" DESC
        LIMIT {{n_adjacent}}
    ) b
    UNION ALL
    SELECT "BODY_ID", "DATE_EVT", 'after' AS car_role
    FROM (
        SELECT "BODY_ID", "DATE_EVT"
        FROM ods.carbody_history
        WHERE "RW_STATION_ID" = '{{station_id}}'
          AND "DATE_EVT" > (SELECT "DATE_EVT" FROM target_event)
        ORDER BY "DATE_EVT" ASC
        LIMIT {{n_adjacent}}
    ) a
),
defect_matches AS (
    SELECT 
        a.car_role,
        a."BODY_ID",
        a."DATE_EVT" AS pass_time,
        d.detect_time,
        ABS(EXTRACT(EPOCH FROM (d.detect_time - a."DATE_EVT"))) AS time_diff_sec,
        d.station_1_defect_count,
        d.station_2_defect_count,
        d.station_3_defect_count,
        d.station_4_defect_count,
        d.station_5_defect_count,
        ROW_NUMBER() OVER(PARTITION BY a."BODY_ID" ORDER BY ABS(EXTRACT(EPOCH FROM (d.detect_time - a."DATE_EVT"))) ASC) as rn
    FROM adjacent_events a
    LEFT JOIN fct.fct_vehicle_defect_enriched d 
      ON a."BODY_ID" = d.vehicle_id
)
SELECT 
    car_role,
    "BODY_ID",
    pass_time,
    detect_time,
    time_diff_sec,
    station_1_defect_count,
    station_2_defect_count,
    station_3_defect_count,
    station_4_defect_count,
    station_5_defect_count
FROM defect_matches
WHERE rn = 1
ORDER BY pass_time ASC;
