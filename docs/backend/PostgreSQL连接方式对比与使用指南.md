# PostgreSQL 连接方式对比与使用指南

**文档版本**: 1.0  
**创建日期**: 2025-02-15  
**相关文件**: 
- `backend/app/agent/service.py` - SQLDatabase 连接方式
- `backend/app/agent/utils/pgvector_wrapper.py` - PGEngine + PGVectorStore 连接方式

---

## 目录

1. [概述](#1-概述)
2. [两种连接方式对比](#2-两种连接方式对比)
3. [方式一：SQLDatabase (langchain-community)](#3-方式一-sqldatabase-langchain-community)
4. [方式二：PGEngine + PGVectorStore (langchain-postgres)](#4-方式二-pgengine--pgvectorstore-langchain-postgres)
5. [使用场景选择](#5-使用场景选择)
6. [注意事项与最佳实践](#6-注意事项与最佳实践)
7. [常见问题](#7-常见问题)

---

## 1. 概述

项目中使用了两种不同的 PostgreSQL 连接方式，分别服务于不同的功能模块：

- **SQLDatabase**: 用于 SQL Agent 工具包，执行 SQL 查询和数据库操作
- **PGEngine + PGVectorStore**: 用于向量存储和相似度搜索（RAG 功能）

这两种方式在底层驱动、连接字符串格式、使用场景等方面存在显著差异。

---

## 2. 两种连接方式对比

| 特性 | SQLDatabase | PGEngine + PGVectorStore |
|------|------------|-------------------------|
| **来源包** | `langchain-community` | `langchain-postgres` |
| **连接字符串格式** | `postgresql://...` | `postgresql+psycopg://...` |
| **底层驱动** | SQLAlchemy (默认 psycopg2) | psycopg3 |
| **连接类型** | 同步 | 同步（通过 `create_sync`） |
| **主要用途** | SQL 查询、数据库工具包 | 向量存储、相似度搜索 |
| **Windows 兼容性** | 良好 | 需要特殊配置（事件循环） |
| **依赖** | `langchain-community` | `langchain-postgres`, `psycopg[binary]` |

---

## 3. 方式一：SQLDatabase (langchain-community)

### 3.1 概述

`SQLDatabase` 是 LangChain 社区提供的数据库工具类，主要用于 SQL Agent 场景，提供数据库查询和操作功能。

### 3.2 代码示例

**位置**: `backend/app/agent/service.py`

```python
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

def _create_database_connection() -> tuple[SQLDatabase, dict]:
    """
    创建数据库连接和获取表定义
    
    Returns:
        tuple: (SQLDatabase 实例, 表定义字典)
    """
    # 提取表结构和注释
    custom_table_info = fetch_table_definitions_with_comments(
        settings.rollerbed_database_url
    )
    
    # 创建 SQLDatabase 实例
    # 连接字符串格式: postgresql://user:password@host:port/database
    db = SQLDatabase.from_uri(
        settings.rollerbed_database_url,  # 例如: postgresql://root:root@localhost:5432/rollerbed_tracking_db
        view_support=True,                  # 支持视图
        custom_table_info=custom_table_info if custom_table_info else None,
        sample_rows_in_table_info=2,        # 在表信息中包含 2 行示例数据
    )
    
    return db, custom_table_info

# 使用 SQLDatabase 创建工具包
def _prepare_tools(db: SQLDatabase, llm: Any) -> list:
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    raw_tools = toolkit.get_tools()
    # ... 工具包装和处理
    return tools
```

### 3.3 连接字符串格式

```python
# 标准格式
postgresql://username:password@host:port/database

# 示例
postgresql://root:root@localhost:5432/rollerbed_tracking_db
```

### 3.4 特点

- ✅ **简单易用**: 直接使用 `from_uri()` 方法创建连接
- ✅ **功能完整**: 支持 SQL 查询、表结构获取、工具包集成
- ✅ **跨平台**: Windows/Linux/Mac 都无需特殊配置
- ✅ **自定义表信息**: 支持注入自定义表注释和元数据
- ⚠️ **同步连接**: 底层使用 SQLAlchemy 同步引擎

### 3.5 适用场景

- SQL Agent 工具包
- 数据库查询和操作
- 需要表结构元数据的场景
- 与 LangChain SQL 工具集成

---

## 4. 方式二：PGEngine + PGVectorStore (langchain-postgres)

### 4.1 概述

`PGEngine` 和 `PGVectorStore` 是 LangChain 官方提供的 PostgreSQL 向量存储实现，专门用于向量相似度搜索和 RAG 功能。

### 4.2 代码示例

**位置**: `backend/app/agent/utils/pgvector_wrapper.py`

```python
from langchain_postgres import PGEngine, PGVectorStore
from langchain_core.embeddings import Embeddings

class PgVectorStoreWrapper:
    def __init__(
        self,
        connection_string: str,
        embedding_service: Embeddings,
        table_name: str = "vector_documents",
        **kwargs
    ):
        """
        初始化向量存储包装器
        
        Args:
            connection_string: PostgreSQL 连接字符串
                - 支持 postgresql:// 格式（会自动转换为 postgresql+psycopg://）
                - 推荐使用 postgresql+psycopg:// 格式（使用 psycopg3）
            embedding_service: Embedding 模型实例
            table_name: 表名称
        """
        # 修复 Windows 事件循环问题
        _fix_windows_event_loop()
        
        # 转换连接字符串格式
        # langchain-postgres 要求使用 postgresql+psycopg:// 格式（psycopg3）
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        
        # 创建 PGEngine（使用 psycopg3）
        self._engine = PGEngine.from_connection_string(
            url=connection_string
        )
        
        # 创建同步版本的 PGVectorStore
        self._vector_store = PGVectorStore.create_sync(
            engine=self._engine,
            table_name=table_name,
            embedding_service=embedding_service,
            **kwargs
        )
    
    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Document]:
        """相似度搜索"""
        return self._vector_store.similarity_search(
            query=query, k=k, filter=filter, **kwargs
        )
```

### 4.3 连接字符串格式

```python
# 推荐格式（psycopg3）
postgresql+psycopg://username:password@host:port/database

# 标准格式（会自动转换）
postgresql://username:password@host:port/database

# 示例
postgresql+psycopg://root:root@localhost:5432/rollerbed_tracking_db
```

### 4.4 Windows 事件循环配置

**重要**: 在 Windows 上使用 psycopg3 需要特殊配置！

```python
import asyncio
import platform

# 在程序启动时（在任何异步代码之前）设置
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

**原因**: psycopg3 在 Windows 上不能使用 `ProactorEventLoop`，必须使用 `SelectorEventLoop`。

### 4.5 特点

- ✅ **向量存储专用**: 专门为向量相似度搜索优化
- ✅ **psycopg3 驱动**: 使用最新的 psycopg3 驱动，性能更好
- ✅ **同步/异步支持**: 可以通过 `create_sync` 或 `create_async` 选择
- ⚠️ **Windows 配置**: 需要设置事件循环策略
- ⚠️ **依赖要求**: 需要安装 `langchain-postgres` 和 `psycopg[binary]`

### 4.6 适用场景

- 向量存储和检索
- RAG（检索增强生成）功能
- 文档相似度搜索
- 需要 pgvector 扩展的场景

---

## 5. 使用场景选择

### 5.1 选择 SQLDatabase 的场景

✅ 需要执行 SQL 查询  
✅ 需要与 SQL Agent 工具包集成  
✅ 需要获取表结构和元数据  
✅ 需要数据库操作（查询、分析等）  
✅ 不需要向量存储功能  

**示例**:
```python
# SQL Agent 服务
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

db = SQLDatabase.from_uri("postgresql://...")
toolkit = SQLDatabaseToolkit(db=db, llm=llm)
```

### 5.2 选择 PGEngine + PGVectorStore 的场景

✅ 需要向量存储和检索  
✅ 需要相似度搜索  
✅ 需要 RAG 功能  
✅ 需要文档嵌入和检索  
✅ 需要 pgvector 扩展功能  

**示例**:
```python
# 向量存储服务
from langchain_postgres import PGEngine, PGVectorStore

engine = PGEngine.from_connection_string("postgresql+psycopg://...")
vector_store = PGVectorStore.create_sync(
    engine=engine,
    embedding_service=embeddings
)
```

### 5.3 同时使用两种方式

在同一个项目中可以同时使用两种连接方式，它们互不干扰：

```python
# 在 service.py 中
# 1. SQLDatabase 用于 SQL Agent
db = SQLDatabase.from_uri(settings.rollerbed_database_url)
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

# 2. PGVectorStore 用于 RAG
vector_store = create_business_vector_store()  # 内部使用 PGEngine
rag_middleware = BusinessRagMiddleware(vector_store=vector_store)
```

---

## 6. 注意事项与最佳实践

### 6.1 连接字符串管理

**推荐做法**: 在配置文件中统一管理连接字符串

```python
# config.py
class Settings:
    rollerbed_database_url: str = Field(
        default="postgresql://root:root@localhost:5432/rollerbed_tracking_db"
    )
```

**注意**: 
- `SQLDatabase` 使用 `postgresql://` 格式
- `PGEngine` 会自动将 `postgresql://` 转换为 `postgresql+psycopg://`

### 6.2 Windows 开发环境配置

如果使用 `PGEngine + PGVectorStore`，必须在程序启动时配置事件循环：

```python
# main.py 或应用入口
import asyncio
import platform

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 然后才导入其他模块
from backend.app.agent.service import SQLAgentService
```

### 6.3 依赖管理

确保安装正确的依赖包：

```txt
# requirements.txt
langchain-community>=0.0.20  # SQLDatabase
langchain-postgres>=0.0.1    # PGEngine, PGVectorStore
psycopg[binary]>=3.1.0       # psycopg3 驱动
```

### 6.4 连接池管理

- **SQLDatabase**: 由 SQLAlchemy 自动管理连接池
- **PGEngine**: 由 psycopg3 管理连接，支持连接池配置

### 6.5 错误处理

```python
# SQLDatabase 错误处理
try:
    db = SQLDatabase.from_uri(connection_string)
except Exception as e:
    logger.error(f"数据库连接失败: {e}")

# PGEngine 错误处理
try:
    engine = PGEngine.from_connection_string(connection_string)
except RuntimeError as e:
    if "ProactorEventLoop" in str(e):
        # Windows 事件循环错误
        logger.error("需要设置 WindowsSelectorEventLoopPolicy")
    raise
```

---

## 7. 常见问题

### Q1: 为什么需要两种不同的连接方式？

**A**: 两种方式服务于不同的功能：
- `SQLDatabase` 用于 SQL 查询和数据库操作
- `PGEngine + PGVectorStore` 用于向量存储和相似度搜索

它们使用不同的底层驱动和优化策略，因此需要不同的连接方式。

### Q2: 可以在同一个连接字符串上使用两种方式吗？

**A**: 可以！只要连接到同一个数据库，两种方式可以共享连接字符串（格式会自动转换）。

### Q3: Windows 上使用 PGEngine 报错怎么办？

**A**: 确保在程序启动时（任何异步代码之前）设置事件循环策略：

```python
import asyncio
import platform

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

### Q4: 连接字符串格式可以混用吗？

**A**: 
- `SQLDatabase` 只接受 `postgresql://` 格式
- `PGEngine` 会自动将 `postgresql://` 转换为 `postgresql+psycopg://`
- 推荐：`PGEngine` 直接使用 `postgresql+psycopg://` 格式

### Q5: 两种方式哪个性能更好？

**A**: 
- **SQL 查询**: `SQLDatabase` 更合适，因为它针对 SQL 操作优化
- **向量搜索**: `PGVectorStore` 更合适，因为它使用 pgvector 扩展和专门的向量索引

### Q6: 如何选择同步还是异步？

**A**: 
- `SQLDatabase`: 只支持同步
- `PGVectorStore`: 
  - 使用 `create_sync()` 创建同步版本
  - 使用 `create_async()` 创建异步版本（需要异步上下文）

---

## 8. 总结

| 特性 | SQLDatabase | PGEngine + PGVectorStore |
|------|------------|-------------------------|
| **最佳用途** | SQL 查询、数据库操作 | 向量存储、相似度搜索 |
| **连接格式** | `postgresql://` | `postgresql+psycopg://` |
| **Windows 配置** | 无需特殊配置 | 需要事件循环策略 |
| **推荐场景** | SQL Agent 工具包 | RAG、向量检索 |

**关键要点**:
1. 两种方式可以共存，服务于不同功能
2. Windows 上使用 `PGEngine` 需要配置事件循环
3. 连接字符串格式会自动转换，但推荐使用正确的格式
4. 根据功能需求选择合适的连接方式

---

## 参考资源

- [LangChain SQLDatabase 文档](https://python.langchain.com/docs/integrations/tools/sql_database)
- [LangChain PGVectorStore 文档](https://docs.langchain.com/oss/python/integrations/vectorstores/index)
- [psycopg3 文档](https://www.psycopg.org/psycopg3/docs/)
- [pgvector 扩展](https://github.com/pgvector/pgvector)

---

**文档维护**: 如有更新，请及时同步修改此文档。
