SELECT
    SUM(mq.station_1_defect_count) AS right_side_defect_count,
    SUM(mq.station_2_defect_count) AS left_side_defect_count,
    SUM(mq.station_3_defect_count) AS roof_defect_count,
    SUM(mq.station_4_defect_count) AS hood_defect_count,
    SUM(mq.station_5_defect_count) AS tailgate_defect_count,
    SUM(mq.total_defect_count) AS total_defect_count
FROM mart_vehicle_quality_360 mq
WHERE mq.history_id IS NOT NULL;
