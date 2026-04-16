# Change: 为 SQL 导出结果提供前端可下载能力

## Why

当前 `export_to_csv` 只会把服务器本地绝对路径返回给 Agent。前端虽然能看到聊天结果，但无法安全、直接地从客户端下载导出的 CSV 文件。

## What Changes

- 新增导出文件元数据管理模块，为每个导出文件分配 `file_id`
- 新增 `/api/chat/files/{file_id}` 下载接口，由后端安全映射真实文件路径
- 调整 `export_to_csv` 返回结构化导出元数据，而非裸露服务器绝对路径
- 在前端聊天消息中识别 `export_to_csv` 结果并渲染“下载 CSV”卡片

## Impact

- Affected specs: `sql-agent`, `chat-ui`
- Affected code:
  - `backend/app/agent/tools/csv_export_tool.py`
  - `backend/app/api.py`
  - `backend/app/config.py`
  - `backend/app/export_files.py`
  - `frontend/src/components/MessageItem.vue`
  - `frontend/src/types/index.ts`
  - `frontend/src/api/exports.ts`
