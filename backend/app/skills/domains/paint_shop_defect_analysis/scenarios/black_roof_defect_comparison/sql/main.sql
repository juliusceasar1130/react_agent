SELECT
    CASE
        WHEN COALESCE(mq.defect_black_roof, '') <> '' THEN 'black_roof'
        ELSE 'non_black_roof'
    END AS black_roof_group,
    COUNT(*) AS detection_count,
    SUM(mq.total_defect_count) AS total_defect_count,
    AVG(mq.total_defect_count) AS avg_defect_per_detection
FROM mart_vehicle_quality_360 mq
WHERE mq.history_id IS NOT NULL
GROUP BY
    CASE
        WHEN COALESCE(mq.defect_black_roof, '') <> '' THEN 'black_roof'
        ELSE 'non_black_roof'
    END
ORDER BY black_roof_group;
