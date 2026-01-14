# Change: 替换研究助手为生产数据查询 SQL Agent

## Why

现有的 `ResearchAgentService` 用于 arXiv 论文搜索，现在需要替换为生产数据查询 SQL Agent，提供自然语言转 SQL 查询功能。

## What Changes

- **移除** `ResearchAgentService` 类（arXiv 论文搜索功能）
- **新增** `SQLAgentService` 类（SQL 数据库查询功能）
- **更新** API 端点 `/api/chat` 和 `/api/stream` 使用新的 SQL Agent
- **更新** 系统提示词为 SQL 数据库交互专用
- **更新** 工具集：`SQLDatabaseToolkit` 替代 `arxiv` 工具
- **保留** `PostgresSaver` 状态管理（会话历史持久化）

## Impact

- Affected specs: `sql-agent`（替代原有的 `research-agent`）
- Affected code:
  - `backend/app/services.py`（完全重写 Agent 服务）
  - `backend/app/api.py`（更新端点使用新服务）
  - `backend/app/config.py`（新增 MySQL 配置）
- 移除依赖: `arxiv` 工具相关
- 新增依赖: `langchain-community`, `pymysql`
