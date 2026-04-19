SELECT
    DATE(mq.detect_time) AS stat_date,
    mq.defect_type_name,
    COUNT(*) AS detection_count,
    AVG(mq.total_defect_count) AS avg_defect_per_detection
FROM mart_vehicle_quality_360 mq
GROUP BY DATE(mq.detect_time), mq.defect_type_name
ORDER BY stat_date DESC, avg_defect_per_detection DESC;
