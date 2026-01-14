## 1. 后端实现

### 1.1 配置更新
- [ ] 1.1.1 在 `config.py` 中添加 MySQL 数据库连接配置
- [ ] 1.1.2 添加 SQL Agent 相关的配置项（top_k、查询限制等）

### 1.2 服务重写
- [ ] 1.2.1 重写 `services.py`，移除 `ResearchAgentService`
- [ ] 1.2.2 新增 `SQLAgentService` 类
- [ ] 1.2.3 实现 `SQLDatabase` 数据库连接
- [ ] 1.2.4 实现 `SQLDatabaseToolkit` 工具加载
- [ ] 1.2.5 实现 `process_message` 方法（非流式查询）
- [ ] 1.2.6 实现 `process_stream` 方法（流式查询）

### 1.3 API 端点更新
- [ ] 1.3.1 确保 `api.py` 中的 `/api/chat` 端点使用新的 `SQLAgentService`
- [ ] 1.3.2 确保 `api.py` 中的 `/api/stream` 端点使用新的 `SQLAgentService`

## 2. 依赖安装
- [ ] 2.1 安装 `langchain-community`（如未安装）
- [ ] 2.2 安装 `pymysql`（MySQL 连接驱动）

## 3. 测试验证
- [ ] 3.1 验证数据库连接正常
- [ ] 3.2 验证非流式查询功能
- [ ] 3.3 验证流式查询功能
- [ ] 3.4 验证错误处理（无效查询、安全限制等）
- [ ] 3.5 确认原有的 arXiv 功能已移除

## 4. 文档更新
- [ ] 4.1 更新 `CLAUDE.md` 中的技术栈说明
- [ ] 4.2 更新 `AGENTS.md` 中的架构设计文档
- [ ] 4.3 更新 API 端点文档（移除 arXiv 相关描述）
