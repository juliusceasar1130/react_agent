SELECT
    cr."vehicle_id",
    cr."first_seen_at",
    cr."last_seen_at",
    cr."first_rw_station",
    cr."last_rw_station",
    cr."platform_code",
    cr."body_type",
    cr."color_code",
    EXTRACT(epoch FROM (cr."last_seen_at" - cr."first_seen_at")) / 3600.0 AS stranded_hours,
    '历史滞留' AS stranded_type,
    NULL AS current_process_area,
    NULL AS current_rb_code
FROM dim.carbody_registry cr
WHERE 1=1
    AND cr."first_rw_station" IN ('1L360RB', '01IS045', '01IS205')
    AND cr."last_rw_station" IN ('1J440RB', '09IS360', '09IS350')
    -- {platform_filter}
    -- {stranded_days}
ORDER BY stranded_hours DESC;
