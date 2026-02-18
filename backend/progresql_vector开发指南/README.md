# 向量集合创建示例

本目录包含使用 `langchain-postgres` 创建向量集合的示例代码。

## 文件说明

- `create_vector_collection_example.py` - 完整的示例，包含两种创建方式和各种操作演示
- `simple_vector_collection_example.py` - 最简化的示例，快速上手

## 前置条件

### 1. 安装依赖

```bash
pip install langchain-postgres langchain-nvidia-ai-endpoints
```

### 2. 数据库准备

确保 PostgreSQL 数据库已安装并运行，然后：

```sql
-- 连接到数据库
psql -U root -d agent_memory

-- 创建 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. 环境变量

设置 NVIDIA API Key（用于 Embeddings）：

```bash
# Windows
set NVIDIA_API_KEY=your_api_key_here

# Linux/Mac
export NVIDIA_API_KEY=your_api_key_here
```

或者在代码中直接设置（不推荐用于生产环境）。

## 数据库连接字符串格式

langchain-postgres 要求使用 `postgresql+psycopg://` 格式：

```
postgresql+psycopg://用户名:密码@主机:端口/数据库名
```

示例：
```
postgresql+psycopg://root:root@localhost:5432/agent_memory
```

## 使用方法

### 方法1: 使用 PGVector（推荐，当前可用）

```python
from langchain_postgres import PGVector
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

embeddings = NVIDIAEmbeddings(model="nvidia/nv-embedqa-e5-v5")
vector_store = PGVector(
    embeddings=embeddings,
    collection_name="my_docs",
    connection="postgresql+psycopg://root:root@localhost:5432/agent_memory",
)
```

**特点：**
- ✅ 简单易用，直接传入连接字符串
- ✅ 自动创建表结构
- ✅ 当前稳定可用

### 方法2: 使用 PGEngine + PGVectorStore（暂不可用）

⚠️ **注意：此方法目前存在已知问题，暂时无法使用。**

**已知问题：**
- 错误信息：`Id column, langchain_id, does not exist`
- 原因：PGVectorStore 在创建表时可能存在列名映射问题
- 状态：等待后续版本修复

```python
# 暂时注释，等待修复
# from langchain_postgres import PGEngine, PGVectorStore
# from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
#
# embeddings = NVIDIAEmbeddings(model="nvidia/nv-embedqa-e5-v5")
# pg_engine = PGEngine.from_connection_string(
#     url="postgresql+psycopg://root:root@localhost:5432/agent_memory"
# )
# vector_store = PGVectorStore.create_sync(
#     engine=pg_engine,
#     table_name="test_table",
#     embedding_service=embeddings,
# )
```

**计划：**
- 后续版本会修复此问题
- 修复后，此方法将提供更多底层控制选项

## 运行示例

### 运行完整示例

```bash
cd .tree/features/agent/backend/test
python create_vector_collection_example.py
```

### 运行简化示例

```bash
cd .tree/features/agent/backend/test
python simple_vector_collection_example.py
```

## 常见操作

### 添加文档

```python
from langchain_core.documents import Document

documents = [
    Document(page_content="文档内容", metadata={"key": "value"}),
]
ids = vector_store.add_documents(documents)
```

### 搜索文档

```python
# 相似度搜索
results = vector_store.similarity_search("查询文本", k=5)

# 带分数的搜索
results = vector_store.similarity_search_with_score("查询文本", k=5)
```

### 过滤搜索

```python
results = vector_store.similarity_search(
    "查询文本",
    k=5,
    filter={"category": "programming"}
)
```

### 删除文档

```python
vector_store.delete(ids=["document_id_1", "document_id_2"])
```

## Windows 注意事项

在 Windows 上，psycopg3 需要 SelectorEventLoop。确保在代码开头添加：

```python
import asyncio
import platform

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

## 参考文档

- [LangChain PGVector 文档](https://docs.langchain.com/oss/python/integrations/vectorstores/index)
- [langchain-postgres GitHub](https://github.com/langchain-ai/langchain-postgres)
