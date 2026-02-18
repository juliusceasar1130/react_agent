# 方案一（PGVector）表结构说明

## 概述

使用方案一（`PGVector` 类）时，LangChain 会自动在 PostgreSQL 数据库中创建两个表来管理向量集合和文档数据。

**重要提示**：
- 表结构由 LangChain 自动创建，无需手动创建
- 表名是固定的，不能自定义
- 首次初始化 `PGVector` 时会自动创建表结构

---

## 快速问答

### ❓ 问题 1：不需要指定向量维度吗？

**答案**：✅ **不需要手动指定向量维度**

- LangChain PGVector 会根据 Embedding 模型的维度**自动设置** `VECTOR` 类型
- 首次创建表时，会根据第一个添加的文档的向量维度确定字段类型
- 你只需要指定 Embedding 模型（如 `baai/bge-m3`），LangChain 会自动处理向量维度
- 同一个 Collection 中的所有文档必须使用相同维度的向量（由同一个 Embedding 模型生成）

**示例**：
```python
# 只需要指定模型，不需要指定维度
embeddings = NVIDIAEmbeddings(
    model="baai/bge-m3",  # 自动使用 1024 维向量
    api_key=os.environ["NVIDIA_API_KEY"]
)

vector_store = PGVector(
    embeddings=embeddings,  # LangChain 会自动根据模型维度创建表
    collection_name="my_docs",
    connection=connection_string,
)
```

### ❓ 问题 2：cmetadata 中内容可以自定义吗？

**答案**：✅ **完全可自定义**

- `cmetadata` 是 **JSONB 类型**，可以存储任意 JSON 数据
- 在创建 `Document` 时，通过 `metadata` 参数传入自定义内容
- 支持任意键值对，没有固定格式限制
- 支持嵌套对象、数组等复杂数据结构

**示例**：
```python
# 简单元数据
Document(
    page_content="文档内容",
    metadata={"source": "file1.txt", "page": 1, "category": "programming"}
)

# 复杂元数据（支持嵌套）
Document(
    page_content="文档内容",
    metadata={
        "type": "sql_example",
        "table_name": "users",
        "domain": "用户管理",
        "tags": ["Python", "机器学习"],
        "custom_info": {
            "department": "技术部",
            "priority": "high"
        }
    }
)
```

**元数据过滤**：
```python
# 可以使用 filter 参数根据 cmetadata 中的字段进行过滤搜索
results = vector_store.similarity_search(
    query="查询内容",
    k=5,
    filter={"category": "programming", "page": {"$gte": 1}}
)
```

---

## 表结构详情

### 1. `langchain_pg_collection` 表

**用途**：存储向量集合（Collection）的元数据信息

**表结构**：

```sql
CREATE TABLE langchain_pg_collection (
    uuid UUID PRIMARY KEY,              -- Collection 的唯一标识符
    name VARCHAR UNIQUE NOT NULL,        -- Collection 名称（对应 PGVector 的 collection_name 参数）
    cmetadata JSONB                     -- Collection 级别的元数据（可选）
);
```

**字段说明**：

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `uuid` | UUID | Collection 的主键，自动生成 | `550e8400-e29b-41d4-a716-446655440000` |
| `name` | VARCHAR | Collection 名称，必须唯一 | `"my_docs"` |
| `cmetadata` | JSONB | Collection 级别的元数据（可选） | `{"description": "业务文档集合"}` |

**索引**：
- 主键索引：`uuid`（自动创建）
- 唯一索引：`name`（自动创建）

**示例数据**：

```sql
-- 当执行以下代码时：
vector_store = PGVector(
    embeddings=embeddings,
    collection_name="my_docs",
    connection=connection_string,
)

-- 会在 langchain_pg_collection 表中插入：
-- uuid: 550e8400-e29b-41d4-a716-446655440000
-- name: "my_docs"
-- cmetadata: NULL 或 {}
```

---

### 2. `langchain_pg_embedding` 表

**用途**：存储文档内容、向量嵌入和文档级别的元数据

**表结构**：

```sql
CREATE TABLE langchain_pg_embedding (
    uuid UUID PRIMARY KEY,              -- 文档记录的唯一标识符
    collection_id UUID NOT NULL,        -- 关联到 langchain_pg_collection.uuid
    embedding VECTOR,                   -- 向量嵌入（维度由 embedding 模型决定）
    document TEXT,                      -- 文档的原始文本内容
    cmetadata JSONB,                    -- 文档级别的元数据
    custom_id VARCHAR                   -- 自定义 ID（可选）
);
```

**字段说明**：

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `uuid` | UUID | 文档记录的主键，自动生成 | `660e8400-e29b-41d4-a716-446655440001` |
| `collection_id` | UUID | 关联到 `langchain_pg_collection.uuid` | `550e8400-e29b-41d4-a716-446655440000` |
| `embedding` | VECTOR | 向量嵌入数据（维度由模型决定） | `[0.1, 0.2, ..., 0.9]` (维度取决于模型) |
| `document` | TEXT | 文档的原始文本内容 | `"这是文档内容..."` |
| `cmetadata` | JSONB | 文档级别的元数据 | `{"source": "file.pdf", "page": 1}` |
| `custom_id` | VARCHAR | 自定义 ID（可选） | `"doc_001"` |

**索引**：
- 主键索引：`uuid`（自动创建）
- 外键索引：`collection_id`（自动创建，关联到 `langchain_pg_collection`）
- 向量索引：`embedding`（使用 pgvector 的 HNSW 或 IVFFlat 索引，自动创建）

**示例数据**：

```sql
-- 当执行以下代码时：
documents = [
    Document(
        page_content="这是第一个文档",
        metadata={"source": "file1.txt", "page": 1}
    )
]
vector_store.add_documents(documents)

-- 会在 langchain_pg_embedding 表中插入：
-- uuid: 660e8400-e29b-41d4-a716-446655440001
-- collection_id: 550e8400-e29b-41d4-a716-446655440000 (关联到 "my_docs" collection)
-- embedding: [0.1, 0.2, ..., 0.9] (向量数据)
-- document: "这是第一个文档"
-- cmetadata: {"source": "file1.txt", "page": 1}
-- custom_id: NULL 或自定义值
```

**cmetadata 自定义说明**：

1. **完全可自定义**：
   - ✅ `cmetadata` 是 **JSONB 类型**，可以存储任意 JSON 数据
   - ✅ 在创建 `Document` 时，通过 `metadata` 参数传入自定义内容
   - ✅ 支持任意键值对，没有固定格式限制
   - ✅ 支持嵌套对象、数组等复杂数据结构

2. **自定义示例**：
   ```python
   # 示例 1：简单键值对
   Document(
       page_content="文档内容",
       metadata={"source": "file1.txt", "page": 1}
   )
   
   # 示例 2：复杂元数据
   Document(
       page_content="文档内容",
       metadata={
           "source": "file1.txt",
           "page": 1,
           "author": "张三",
           "tags": ["Python", "机器学习"],
           "category": "programming",
           "created_at": "2025-02-15",
           "custom_info": {
               "department": "技术部",
               "priority": "high"
           }
       }
   )
   
   # 示例 3：业务特定元数据（根据项目需求）
   Document(
       page_content="SQL 查询示例",
       metadata={
           "type": "sql_example",
           "table_name": "users",
           "domain": "用户管理",
           "complexity": "medium"
       }
   )
   ```

3. **元数据过滤**：
   - ✅ 可以使用 `filter` 参数根据 `cmetadata` 中的字段进行过滤搜索
   - ✅ 支持精确匹配、范围查询等
   ```python
   # 按元数据过滤搜索
   results = vector_store.similarity_search(
       query="查询内容",
       k=5,
       filter={"category": "programming", "page": {"$gte": 1}}
   )
   ```

---

## 表关系图

```
langchain_pg_collection (1) ──< (N) langchain_pg_embedding
     │                                    │
     │ uuid (PK)                          │ collection_id (FK)
     │ name (UNIQUE)                      │ uuid (PK)
     │ cmetadata                          │ embedding (VECTOR)
                                          │ document (TEXT)
                                          │ cmetadata (JSONB)
                                          │ custom_id (VARCHAR)
```

**关系说明**：
- 一个 Collection 可以包含多个文档（一对多关系）
- `langchain_pg_embedding.collection_id` 外键关联到 `langchain_pg_collection.uuid`
- 删除 Collection 时，关联的文档也会被删除（CASCADE）

---

## 向量维度说明

**重要**：`embedding` 字段的维度取决于你使用的 Embedding 模型：

| Embedding 模型 | 向量维度 | 说明 |
|---------------|---------|------|
| `text-embedding-ada-002` | 1536 | OpenAI 模型 |
| `text-embedding-3-small` | 1536 | OpenAI 模型 |
| `text-embedding-3-large` | 3072 | OpenAI 模型 |
| `baai/bge-m3` | 1024 | BGE 模型（NVIDIA） |
| 其他模型 | 根据模型而定 | 查看模型文档 |

**重要说明**：

1. **不需要手动指定向量维度**：
   - ✅ LangChain PGVector 会根据 Embedding 模型的维度**自动设置** `VECTOR` 类型
   - ✅ 首次创建表时，会根据第一个添加的文档的向量维度确定字段类型
   - ✅ 你只需要指定 Embedding 模型（如 `baai/bge-m3`），LangChain 会自动处理向量维度
   - ✅ 同一个 Collection 中的所有文档必须使用相同维度的向量（由同一个 Embedding 模型生成）

2. **示例**：
   ```python
   # 只需要指定模型，不需要指定维度
   embeddings = NVIDIAEmbeddings(
       model="baai/bge-m3",  # 自动使用 1024 维向量
       api_key=os.environ["NVIDIA_API_KEY"]
   )
   
   vector_store = PGVector(
       embeddings=embeddings,  # LangChain 会自动根据模型维度创建表
       collection_name="my_docs",
       connection=connection_string,
   )
   ```

---

## 索引说明

### 自动创建的索引

1. **主键索引**：
   - `langchain_pg_collection.uuid` (PRIMARY KEY)
   - `langchain_pg_embedding.uuid` (PRIMARY KEY)

2. **唯一索引**：
   - `langchain_pg_collection.name` (UNIQUE)

3. **外键索引**：
   - `langchain_pg_embedding.collection_id` (FOREIGN KEY)

4. **向量索引**（pgvector）：
   - `langchain_pg_embedding.embedding` (HNSW 或 IVFFlat 索引)
   - 用于加速向量相似度搜索

### 向量索引类型

PGVector 支持两种向量索引类型：

1. **HNSW 索引**（推荐）：
   - 适合高维向量
   - 查询速度快
   - 索引构建时间较长

2. **IVFFlat 索引**：
   - 适合大规模数据
   - 索引构建时间较短
   - 查询速度相对较慢

**注意**：索引类型由 LangChain 自动选择，通常使用 HNSW。

---

## 使用示例

### 创建向量集合

```python
from langchain_postgres import PGVector
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

# 初始化 Embedding 模型
embeddings = NVIDIAEmbeddings(
    model="baai/bge-m3",
    api_key=os.environ["NVIDIA_API_KEY"]
)

# 创建向量存储（会自动创建表）
vector_store = PGVector(
    embeddings=embeddings,
    collection_name="my_docs",  # 对应 langchain_pg_collection.name
    connection="postgresql+psycopg://root:root@localhost:5432/agent_memory",
)
```

**执行后**：
- 自动创建 `langchain_pg_collection` 表（如果不存在）
- 自动创建 `langchain_pg_embedding` 表（如果不存在）
- 在 `langchain_pg_collection` 中插入一条记录：`name="my_docs"`

### 添加文档

```python
from langchain_core.documents import Document

documents = [
    Document(
        page_content="这是文档内容",
        metadata={"source": "file1.txt", "page": 1}
    )
]

# 添加文档（会自动生成向量并插入数据库）
vector_store.add_documents(documents)
```

**执行后**：
- 在 `langchain_pg_embedding` 表中插入文档记录
- `collection_id` 自动关联到对应的 Collection
- `embedding` 字段存储向量数据
- `document` 字段存储原始文本
- `cmetadata` 字段存储元数据

---

## 查询示例

### 查看所有 Collections

```sql
SELECT uuid, name, cmetadata 
FROM langchain_pg_collection;
```

### 查看某个 Collection 的所有文档

```sql
SELECT 
    e.uuid,
    e.document,
    e.cmetadata,
    e.custom_id,
    c.name as collection_name
FROM langchain_pg_embedding e
JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = 'my_docs';
```

### 查看向量维度

```sql
SELECT 
    c.name as collection_name,
    array_length(e.embedding::float[], 1) as embedding_dimension,
    COUNT(*) as document_count
FROM langchain_pg_embedding e
JOIN langchain_pg_collection c ON e.collection_id = c.uuid
GROUP BY c.name, array_length(e.embedding::float[], 1);
```

---

## 注意事项

1. **表名固定**：
   - 表名 `langchain_pg_collection` 和 `langchain_pg_embedding` 是固定的
   - 不能自定义表名
   - 所有 Collection 共享这两个表

2. **Collection 隔离**：
   - 通过 `collection_id` 字段区分不同的 Collection
   - 不同 Collection 的文档存储在同一个 `langchain_pg_embedding` 表中

3. **自动管理**：
   - 表结构由 LangChain 自动创建和管理
   - 不要手动修改表结构
   - 不要手动删除或修改索引

4. **pgvector 扩展**：
   - 必须先在数据库中启用 pgvector 扩展：
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     ```

5. **向量维度一致性**：
   - 同一个 Collection 中的所有文档必须使用相同维度的向量
   - 不同 Collection 可以使用不同维度的向量

---

## 与方案二的区别

| 特性 | 方案一（PGVector） | 方案二（PGVectorStore） |
|------|------------------|----------------------|
| 表名 | 固定：`langchain_pg_collection`、`langchain_pg_embedding` | 可自定义：`table_name` 参数 |
| Collection 管理 | 通过 `collection_name` 参数 | 通过 `table_name` 参数（每个表一个 Collection） |
| 表结构 | 由 LangChain 自动创建 | 由 LangChain 自动创建 |
| 多 Collection | 支持（共享表，通过 `collection_id` 区分） | 不支持（每个表一个 Collection） |
| 当前状态 | ✅ 推荐使用 | ⚠️ 存在已知问题，暂不可用 |

---

## 参考资源

- [LangChain PGVector 官方文档](https://docs.langchain.com/oss/python/integrations/vectorstores/index)
- [pgvector 扩展文档](https://github.com/pgvector/pgvector)
- [项目迁移文档](../migrations/README.md)

---

**文档版本**: 1.0  
**创建日期**: 2025-02-15  
**最后更新**: 2025-02-15
