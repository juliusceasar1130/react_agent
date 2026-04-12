SELECT
    DATE(mq.detect_time) AS stat_date,
    COUNT(*) AS detection_count,
    SUM(mq.total_defect_count) AS total_defect_count
FROM mart_vehicle_quality_360 mq
GROUP BY DATE(mq.detect_time)
ORDER BY stat_date DESC;
