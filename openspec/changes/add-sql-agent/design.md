## Context

将现有的研究助手 Agent（arXiv 论文搜索）完全替换为生产数据查询 SQL Agent。

### 约束条件
- 替换而非新增，保持代码简洁
- 保留现有的 PostgresSaver 状态管理机制
- 使用 MySQL 数据库（mds）
- 禁止 DML 操作，保证查询安全

## Goals / Non-Goals

### Goals
- 提供自然语言转 SQL 查询功能
- 支持流式和非流式两种查询模式
- 安全的查询机制（禁止 DML）
- 会话历史持久化

### Non-Goals
- 不实现 Human-in-the-Loop 审核机制
- 不支持 arXiv 论文搜索
- 不支持多数据库切换

## Decisions

### 1. 替换策略
- **决策**: 直接替换 `ResearchAgentService` 为 `SQLAgentService`
- **理由**: 用户明确要求不再使用原有服务
- **影响**: API 端点保持不变，服务逻辑完全重写

### 2. 数据库连接管理
- **决策**: 使用 `SQLDatabase.from_uri()` 连接 MySQL
- **配置**: 从 `config.py` 读取数据库连接字符串

### 3. 状态管理
- **决策**: 继续使用 `PostgresSaver`
- **理由**: 保持架构一致性，支持会话历史持久化

### 4. 系统提示词
- **决策**: 使用需求文档中的标准 SQL Agent 提示词
- **关键约束**: `top_k=10`，禁止 DML，查询前检查表结构

## Migration Plan

1. 部署前：
   - 安装新依赖（`langchain-community`, `pymysql`）
   - 配置 MySQL 数据库连接信息

2. 部署后：
   - 验证 `/api/chat` 端点正常工作
   - 验证流式查询功能正常
   - 确认旧的研究助手功能已移除

3. 回滚方案：
   - 恢复 `ResearchAgentService` 代码
   - 恢复原有 API 端点逻辑

## Open Questions

- [已解决] 是否需要 Human-in-the-Loop 审核？ → **不需要**
- [已解决] 是新增还是替换？ → **替换**
