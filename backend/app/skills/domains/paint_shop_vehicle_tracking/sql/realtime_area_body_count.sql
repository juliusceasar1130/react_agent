SELECT
    rp.process_area,
    COUNT(*) AS vehicle_count
FROM rb_position_data rp
WHERE rp.vehicle_id LIKE '782026%'
  AND rp.body_type != '-----'
  AND rp.carrier_id <> '0'
GROUP BY rp.process_area
ORDER BY vehicle_count DESC;
