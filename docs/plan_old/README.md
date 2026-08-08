# 业务知识 RAG 中间件开发文档

本目录包含业务知识 RAG 中间件的完整方案设计和开发计划。

## 文档结构

- **方案设计.md**: 详细的技术方案设计文档，包括架构设计、实现细节、集成方案等
- **开发计划.md**: 详细的开发任务清单、时间估算、验收标准等
- **README.md**: 本文件，文档索引和快速参考

## 快速开始

### 查看方案设计
阅读 `方案设计.md` 了解：
- 技术架构
- 实现方案
- 集成方式
- 扩展方向

### 查看开发计划
阅读 `开发计划.md` 了解：
- 开发阶段划分
- 详细任务清单
- 时间估算
- 验收标准

## 核心功能

业务知识 RAG 中间件（BusinessRagMiddleware）提供以下功能：

1. **动态检索**: 根据用户查询自动检索相关业务知识
2. **自动注入**: 将检索结果作为系统消息注入到 Agent 上下文
3. **智能去重**: 自动处理重复的业务知识系统消息
4. **无缝集成**: 与现有中间件架构完美兼容

## 技术栈

- **LangChain**: AgentMiddleware 框架
- **Chroma**: 向量存储
- **DashScope**: Embedding 模型（text-embedding-v3）

## 文件位置

### 核心实现
- `backend/app/agent/middleware/rag_middleware.py` - RAG 中间件实现
- `backend/app/agent/utils/vector_store.py` - 向量存储工具函数
- `backend/app/agent/state.py` - 状态定义（需扩展）

### 集成点
- `backend/app/agent/service.py` - Agent 服务集成

### 测试文件
- `backend/app/agent/middleware/test_rag_middleware.py` - 单元测试
- `backend/app/test_rag_integration.py` - 集成测试

### 文档
- `docs/rag_middleware.md` - 使用文档

## 开发流程

1. **阶段 1**: 基础实现（6 小时）
   - 扩展状态定义
   - 实现 RAG 中间件
   - 创建向量存储工具
   - 集成到 Agent 服务

2. **阶段 2**: 测试与优化（6 小时）
   - 单元测试
   - 集成测试
   - 功能验证
   - 代码优化

3. **阶段 3**: 文档与配置（3 小时）
   - 配置管理
   - 文档编写
   - 示例代码
   - 更新主文档

## 关键设计决策

### 为什么使用 before_model 而不是 wrap_model_call？

- `before_model` 更符合 LangChain 的设计模式
- 可以直接修改 state，更灵活
- 避免修改 ModelRequest 的复杂性

### 为什么在 messages 中注入而不是修改系统提示词？

- 系统提示词在 Agent 创建时确定，难以动态修改
- 在 messages 中注入可以确保每次模型调用都能看到最新的业务知识
- 更容易实现去重和替换逻辑

### 为什么需要消息去重？

- 避免在多次工具调用后重复添加业务知识系统消息
- 保持 messages 列表的整洁
- 减少 Token 消耗

## 验收标准

### 功能验收
- ✅ RAG 中间件能够正确检测用户消息并执行检索
- ✅ 检索结果能够正确格式化和注入
- ✅ Agent 能够使用注入的业务知识回答问题

### 质量验收
- ✅ 所有测试通过
- ✅ 代码符合规范
- ✅ 文档完整

### 性能验收
- ✅ 检索延迟 < 500ms
- ✅ 不影响现有功能性能

## 后续优化

- 检索结果缓存
- 异步检索处理
- 多向量库支持
- 检索质量评估

## 相关文档

- [LangChain AgentMiddleware 文档](https://python.langchain.com/docs/modules/agents/middleware/)
- [Chroma 向量存储文档](https://docs.trychroma.com/)
- [DashScope Embeddings 文档](https://help.aliyun.com/zh/model-studio/developer-reference/text-embedding-api-details)

## 联系方式

如有问题或建议，请参考项目主文档或联系开发团队。
