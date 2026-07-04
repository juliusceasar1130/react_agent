SELECT
    DATE(mq.detect_time) AS stat_date,
    COUNT(*) AS detection_count,
    SUM(mq.total_defect_count) AS total_defect_count,
    AVG(mq.total_defect_count) AS avg_defect_per_detection
FROM mart_vehicle_quality_360 mq
WHERE mq.history_id IS NOT NULL
GROUP BY DATE(mq.detect_time)
ORDER BY stat_date DESC;
