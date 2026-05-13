SELECT 
    h."RW_STATION_ID" as station_id,
    COUNT(DISTINCT h."BODY_ID") AS throughput_count
FROM ods.carbody_history h
WHERE 1=1
-- {date_filter}
GROUP BY h."RW_STATION_ID"
ORDER BY throughput_count DESC;
