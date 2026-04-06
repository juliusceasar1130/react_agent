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
    rp.process_area,
    COUNT(*) AS vehicle_count
FROM rb_position_data rp
WHERE rp.vehicle_id LIKE '782026%'
  AND rp.body_type != '-----'
  AND rp.carrier_id <> '0'
  -- 可选参数: process_area（当用户指定特定区域时取消注释并填充值）
  -- 单区域示例: AND rp.process_area = '电泳'
  -- 多区域示例: AND rp.process_area IN ('电泳', '面漆')
GROUP BY rp.process_area
ORDER BY vehicle_count DESC;
