## 1. Implementation

- [x] 1.1 新增导出文件元数据管理模块，生成并解析 `file_id`
- [x] 1.2 为后端增加导出文件下载接口
- [x] 1.3 调整 `export_to_csv` 返回结构化导出结果
- [x] 1.4 在前端消息卡片中展示下载入口
- [x] 1.5 更新 README 与 changelog 说明

## 2. Verification

- [x] 2.1 检查前后端导出结果字段是否一致
- [x] 2.2 运行后端 Python 语法检查
- [x] 2.3 运行前端构建验证（`vite build` 通过；`vue-tsc` 在当前 Node 24 环境下存在兼容性报错）
