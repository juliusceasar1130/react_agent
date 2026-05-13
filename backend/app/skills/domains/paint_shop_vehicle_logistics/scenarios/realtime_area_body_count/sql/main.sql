-- 实时各区域车身数量统计 SQL 模板
--
-- 参数说明:
--   process_area: 可选，工艺区域名称列表（如 ['电泳', '面漆']）
--                 不传则查询所有区域
--
-- 使用示例:
--   1. 查询所有区域: 保持原 SQL 不变
--   2. 查询电泳区域: 在 WHERE 子句末尾添加 AND rp.process_area = '电泳'
--   3. 查询多区域: 在 WHERE 子句末尾添加 AND rp.process_area IN ('电泳', '面漆')

SELECT
    overview.process_area,
    COUNT(*) AS vehicle_count
FROM mart_position_current_overview overview
WHERE overview.entity_type = 'product_vehicle'
  -- 可选参数: process_area（当用户指定特定区域时取消注释并填充值）
  -- 单区域示例: AND overview.process_area = '电泳'
  -- 多区域示例: AND overview.process_area IN ('电泳', '面漆')
GROUP BY overview.process_area
ORDER BY vehicle_count DESC;
