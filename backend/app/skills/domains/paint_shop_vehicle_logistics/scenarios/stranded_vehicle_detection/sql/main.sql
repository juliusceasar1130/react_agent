SELECT
    "vehicle_id",
    "first_seen_at",
    "last_seen_at",
    "first_rw_station",
    "last_rw_station",
    "platform_code",
    "body_type",
    "color_code",
    EXTRACT(epoch FROM ("last_seen_at" - "first_seen_at")) / 3600.0 AS stranded_hours,
    CASE
        WHEN "last_rw_station" IN ('1J440RB', 'K1IS135', 'K2IS075', 'K3IS140')
        THEN '历史滞留'
        ELSE '在制滞留'
    END AS stranded_type
FROM dim.carbody_registry
WHERE 1=1
    AND "first_rw_station" IN ('1L360RB', '01IS045', '01IS205')
    -- {exit_condition}
    -- {platform_filter}
    -- {stranded_days}
ORDER BY stranded_hours DESC;
