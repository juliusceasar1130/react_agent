SELECT
    vde."project_vehicle_no",
    vde."vehicle_id",
    vde."body_type",
    vde."color_code",
    vde."defect_model",
    vde."detect_time",
    vde."tunnel",
    vde."total_defect_count",
    vde."station_1_defect_count" AS right_side_defects,
    vde."station_2_defect_count" AS left_side_defects,
    vde."station_3_defect_count" AS roof_defects,
    vde."station_4_defect_count" AS hood_defects,
    vde."station_5_defect_count" AS tailgate_defects
FROM fct.fct_vehicle_defect_enriched vde
WHERE 1=1
    AND vde."project_vehicle_no" IS NOT NULL
    {project_vehicle_no_filter}
    {body_type_filter}
    {has_defect_only_filter}
ORDER BY vde."detect_time" DESC;
