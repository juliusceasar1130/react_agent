SELECT
    overview.process_area,
    COUNT(*) AS vehicle_count
FROM mart_position_current_overview overview
WHERE overview.entity_type = 'product_vehicle'
GROUP BY overview.process_area
ORDER BY vehicle_count DESC;
