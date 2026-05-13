SELECT 
    carrier_id,
    process_area,
    abnormal_type,
    abnormal_reason,
    vehicle_id,
    vehicle_updated_at
FROM mart.mart_abnormal_vehicle_current
WHERE 1=1
-- {abnormal_type}
ORDER BY process_area, abnormal_type;
