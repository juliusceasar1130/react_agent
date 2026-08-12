SELECT
    pvo."project_vehicle_no",
    pvo."project_stage",
    pvo."block_no",
    pvo."composite_pin_no",
    pvo."pin_no",
    pvo."kom_no",
    pvo."knr_no",
    pvo."code_6bit",
    pvo."color_interior",
    pvo."file_name" AS source_order_doc,
    vp."current_process_area",
    vp."current_full_rb_code",
    pvo."created_at" AS order_created_at
FROM ods.ods_fis_project_vehicle_orders pvo
LEFT JOIN dim.dim_vehicle_profile vp
       ON pvo.project_vehicle_no = vp.project_vehicle_no
WHERE 1=1
    {project_stage_filter}
    {project_vehicle_no_filter}
    {has_defect_only_filter}
ORDER BY pvo."created_at" DESC;
