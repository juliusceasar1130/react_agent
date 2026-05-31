# 数据字典设计约定

> 从 memory.md 迁出，在修改数据字典功能时读取。

## 约定

- **方案 B 定案 (Variant B)**：正式选用 Bento 网格仪表盘 + 侧滑毛玻璃 Drawer 抽屉作为数据字典交互架构。A/C 变体及 PrototypeSwitcher 已物理清理。
- **白名单来源**：维度表白名单从 `.env` 的 `DIMENSION_TABLES` 配置读取（逗号分隔），由 `settings.dimension_tables` 提供。不在代码中硬编码。
- **连接失败直接报错**：数据库未配置或连接/查询失败直接返回 503/500，不做降级，便于人员排查。
- **双击联动注入 (Cell Double-Click Injection)**：双击维度表单元格或列名直接提取内容并注入到聊天输入框当前光标处，搭配 `.input-glow` 输入框呼吸聚焦蓝色微光动效及毛玻璃 Transition Toast。
