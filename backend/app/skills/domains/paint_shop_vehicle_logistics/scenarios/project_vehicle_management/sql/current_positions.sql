SELECT
    fpc."project_vehicle_no",
    pvo."project_stage",
    pvo."block_no",
    fpc."vehicle_id",
    fpc."body_type",
    fpc."color_code",
    fpc."process_area",
    fpc."full_rb_code" AS current_rb_code,
    fpc."carrier_id",
    fpc."position_created_at",
    fpc."vehicle_updated_at"
FROM fct.fct_vehicle_position_current fpc
INNER JOIN ods.ods_fis_project_vehicle_orders pvo
        ON fpc.project_vehicle_no = pvo.project_vehicle_no
WHERE 1=1
    AND fpc."project_vehicle_no" IS NOT NULL
    {project_stage_filter}
    {project_vehicle_no_filter}
    {process_area_filter}
ORDER BY fpc."vehicle_updated_at" DESC;
