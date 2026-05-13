SELECT 
    "DATE_EVT",
    "RW_STATION_ID",
    "BODY_ID"
FROM ods.carbody_history
WHERE 1=1
-- {vehicle_id}
ORDER BY "DATE_EVT" ASC;
