SELECT
    cr."vehicle_id",
    cr."project_vehicle_no",
    cr."platform_code",
    cr."body_type",
    cr."color_code",
    cr."first_rw_station",
    cr."retention_checkpoint_station",
    cr."first_seen_at",
    cr."retention_checkpoint_pass_at",
    EXTRACT(epoch FROM (CURRENT_TIMESTAMP - cr."first_seen_at")) / 3600.0 AS stranded_hours,
    '在制滞留' AS stranded_type,
    fpc.process_area AS current_process_area,
    fpc.full_rb_code AS current_rb_code
FROM dim.carbody_registry cr
LEFT JOIN fct.fct_vehicle_position_current fpc 
       ON cr.vehicle_id = fpc.vehicle_id
WHERE 1=1
    AND cr."first_rw_station" IN ('1L360RB', '01IS045', '01IS205')
    AND (cr."retention_checkpoint_station" IS NULL OR cr."retention_checkpoint_station" NOT IN ('1J440RB', 'K3IS140', 'K2IS075', 'K1IS135'))
    {vehicle_type_filter}
    {platform_filter}
    {in_process_stranded_days}
ORDER BY stranded_hours DESC;
