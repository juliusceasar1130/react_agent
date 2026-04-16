SELECT
    mq.tunnel,
    mq.cycle,
    COUNT(*) AS detection_count,
    SUM(mq.total_defect_count) AS total_defect_count,
    AVG(mq.total_defect_count) AS avg_defect_per_detection
FROM mart_vehicle_quality_360 mq
GROUP BY mq.tunnel, mq.cycle
ORDER BY mq.tunnel, mq.cycle;
