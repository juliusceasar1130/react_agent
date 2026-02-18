# 迁移到官方 PGVector 指南

## 概述

为了精简代码并减少维护成本，建议从自定义 `PgVectorStore` 迁移到基于官方 LangChain PGVector 的轻量包装 `PgVectorStoreWrapper`。

## 迁移优势

### 代码精简
- **减少 ~300 行自定义代码**：核心功能由官方维护
- **自动获得官方更新**：bug 修复、性能优化、新功能
- **更好的社区支持**：官方文档、示例、最佳实践

### 功能增强
- ✅ 官方 metadata 筛选（支持复杂查询）
- ✅ 官方 collection 管理机制
- ✅ 更好的错误处理和日志
- ✅ 异步支持（如需要）

### 保持业务便利性
- ✅ 保留 `similarity_search_by_type()` 方法
- ✅ 保留 `layered_retrieval()` 方法
- ✅ API 完全兼容，无需修改调用代码

## 迁移步骤

### 步骤 1: 安装依赖

确保已安装官方 PGVector 依赖：

```bash
pip install langchain-community
```

### 步骤 2: 更新导入

**旧代码** (`vector_store.py`):
```python
from backend.app.agent.utils.pgvector_store import PgVectorStore
```

**新代码**:
```python
from backend.app.agent.utils.pgvector_wrapper import PgVectorStoreWrapper as PgVectorStore
```

或者直接使用新名称：
```python
from backend.app.agent.utils.pgvector_wrapper import PgVectorStoreWrapper
```

### 步骤 3: 更新初始化代码

**旧代码**:
```python
vector_store = PgVectorStore(
    connection_string=pg_connection_string,
    embedding_function=embeddings,
    table_name="vector_documents",
    collection_name=collection_name,
)
```

**新代码**:
```python
vector_store = PgVectorStoreWrapper(
    connection_string=pg_connection_string,
    embedding_function=embeddings,
    collection_name=collection_name,
    # 注意：不再需要 table_name，官方使用 collection 机制
)
```

### 步骤 4: 数据库迁移（可选）

官方 PGVector 使用不同的表结构。有两种选择：

#### 选项 A: 使用官方表结构（推荐）

官方 PGVector 会自动创建表，表结构为：
- `langchain_pg_embedding` 表
- 使用 `collection_id` 关联到 `langchain_pg_collection` 表

**迁移数据**:
```sql
-- 将现有数据迁移到官方表结构
INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata)
SELECT 
    (SELECT uuid FROM langchain_pg_collection WHERE name = 'your_collection_name'),
    embedding,
    document,
    metadata
FROM vector_documents
WHERE metadata->>'collection_name' = 'your_collection_name';
```

#### 选项 B: 保持现有表结构（需要自定义）

如果必须保持现有表结构，可以：
1. 继续使用自定义实现
2. 或修改官方 PGVector 的表名配置（如果支持）

### 步骤 5: 测试验证

1. **功能测试**：确保所有检索功能正常
2. **性能测试**：验证查询性能
3. **数据完整性**：确认数据迁移正确

## API 兼容性

### 完全兼容的方法

以下方法调用方式不变：

```python
# 基础检索
docs = vector_store.similarity_search("query", k=5)

# 带分数检索
docs_with_score = vector_store.similarity_search_with_score("query", k=5)

# 按类型检索（业务方法）
docs = vector_store.similarity_search_by_type(
    query="query",
    doc_type="documentation",
    k=5
)

# 分层检索（业务方法）
results = vector_store.layered_retrieval(
    query="query",
    ddl_k=10,
    doc_k=5,
    sql_k=3
)

# 添加文档
ids = vector_store.add_documents(documents)

# 删除文档
vector_store.delete(ids)
```

### Metadata 筛选增强

官方实现支持更复杂的筛选：

```python
# 简单筛选（兼容）
docs = vector_store.similarity_search(
    "query", 
    k=5, 
    filter={"type": "documentation"}
)

# 复杂筛选（新功能）
docs = vector_store.similarity_search(
    "query",
    k=5,
    filter={
        "type": {"$in": ["documentation", "ddl"]},
        "domain": "sales"
    }
)
```

## 回滚方案

如果迁移后发现问题，可以快速回滚：

1. 恢复 `vector_store.py` 中的导入
2. 使用原有的 `PgVectorStore` 类
3. 数据无需回滚（如果使用选项 B）

## 注意事项

1. **表结构差异**：官方 PGVector 使用不同的表结构，需要数据迁移
2. **Collection 机制**：官方使用 `collection_id` 而非 metadata 中的 `collection_name`
3. **索引**：官方会自动创建索引，但可能需要调整现有索引
4. **连接池**：官方使用 SQLAlchemy，连接池配置可能不同

## 推荐方案

**建议采用渐进式迁移**：

1. **阶段 1**：创建 `PgVectorStoreWrapper`，与现有实现并行
2. **阶段 2**：在测试环境验证新实现
3. **阶段 3**：逐步迁移调用代码
4. **阶段 4**：完全切换到新实现，移除旧代码

这样可以最小化风险，确保平滑迁移。
