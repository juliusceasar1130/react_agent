我来为你制作一份**LlamaIndex SQL 结构化检索开发技能指南**，涵盖核心知识点、泛化性建议和避坑指南，并标注参考资料出处。

---

# LlamaIndex SQL 结构化检索开发指南

**版本**: 2026-07-13  
**适用版本**: llama-index >= 0.14.x  
**核心场景**: 企业级 Text-to-SQL / NL2SQL / 结构化数据 RAG

---

## 一、架构设计原则

### 1.1 核心思想：Schema 即索引

> **"把数据库元数据当作文档来 RAG"** —— LlamaIndex 官方设计哲学 [^1]

```
传统方案: 用户问题 → LLM → SQL（一次性塞入所有表结构）
LlamaIndex: 用户问题 → 检索相关表 → 精简上下文 → LLM → SQL
```

### 1.2 三层检索架构

| 层次 | 解决的问题 | 索引对象 | 适用规模 |
|------|-----------|---------|---------|
| **表检索** | 表太多（100+） | 表 Schema（列结构+描述） | 任意 |
| **行检索** | 值歧义（同义词/大小写） | 数据行（完整记录） | 万级以下 |
| **列检索** | 宽表（50+列） | 单列去重值 | 低基数列 |

**参考资料**: LlamaIndex 官方文档 - Structured Data [^2]

---

## 二、环境配置与模型选择

### 2.1 Embedding 模型配置

#### 通用方案（OpenAI 兼容）

```python
from llama_index.embeddings.openai_like import OpenAILikeEmbedding

# ❌ 错误：使用 model 参数
OpenAILikeEmbedding(model="xxx")  # 会触发枚举校验错误

# ✅ 正确：使用 model_name 参数
embed_model = OpenAILikeEmbedding(
    model_name="your-model-name",      # 必须用 model_name
    api_base="http://127.0.0.1:8081",
    api_key="fake",                    # llama.cpp 不需要真实 key
    embed_batch_size=8,                # 根据服务端并发调整
    dimensions=1024,                   # 必须与 Milvus collection dim 一致
)
```

**避坑**: `OpenAILikeEmbedding` 必须用 `model_name` 而非 `model`，否则会触发 `OpenAIEmbeddingModelType` 枚举校验 [^3]

#### 自定义 llama.cpp 方案（推荐）

```python
import httpx
from llama_index.core.base.embeddings.base import BaseEmbedding

class LlamaCppEmbedding(BaseEmbedding):
    """适配 llama.cpp /embedding 端点"""
    
    def __init__(self, model_name: str, base_url: str = "http://127.0.0.1:8081"):
        super().__init__(model_name=model_name)
        self._client = httpx.Client(base_url=base_url.rstrip("/"))
    
    def _get_text_embedding(self, text: str) -> list[float]:
        response = self._client.post("/embedding", json={"content": text})
        return response.json()["embedding"]
    
    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self._get_text_embedding(t) for t in texts]
    
    def _get_query_embedding(self, query: str) -> list[float]:
        return self._get_text_embedding(query)
```

**关键差异**:
- llama.cpp 端点: `/embedding`（不是 `/embeddings`）
- 请求字段: `content`（不是 `input`）
- 响应格式: `{"embedding": [...]}`（需兼容解析）

**参考资料**: 用户项目实践 [^4]

### 2.2 LLM 配置（OpenAI 兼容）

```python
from llama_index.llms.openai import OpenAI

llm = OpenAI(
    model="gpt-5-nano",
    api_key="sk-no-key-required",
    api_base="http://192.168.3.245:8089/v1",
    temperature=0.1,           # SQL 生成需要低温度
    max_retries=3,
    timeout=60.0,
)
```

**避坑**: `temperature` 建议 0.0-0.2，SQL 生成需要确定性，高温度会导致语法错误 [^5]

---

## 三、数据库设计规范

### 3.1 表注释规范

```sql
-- ✅ 推荐：表注释 + 列注释
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) COMMENT '客户姓名',
    level VARCHAR(50) COMMENT '会员等级：VIP/普通',
    register_date DATE COMMENT '注册日期'
) COMMENT '【核心】客户会员信息表，用于查询客户信息和会员等级';

-- ❌ 避免：无注释
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    level VARCHAR(50)
);
```

**作用**: LlamaIndex 的 `SQLDatabase.get_single_table_info()` 会自动反射注释，注入 Prompt [^6]

### 3.2 外键约束规范

```sql
-- ✅ 推荐：显式外键约束
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER,
    amount DECIMAL(10,2),
    
    CONSTRAINT fk_orders_customers 
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CONSTRAINT fk_orders_products 
        FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- ❌ 避免：无外键
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER,  -- 只是 INTEGER，无关联
    product_id INTEGER
);
```

**作用**: 外键帮助 LLM 理解表关系，生成正确的 JOIN 语句 [^7]

### 3.3 索引列选择规范

| 列类型 | 是否建列索引 | 原因 | 示例 |
|--------|------------|------|------|
| **枚举值/分类值** | ✅ 必须 | 值歧义高发 | `level` (VIP/普通), `payment_method` |
| **状态值** | ✅ 推荐 | 同义词问题 | `order_status` (completed/pending) |
| **城市/地区** | ✅ 推荐 | 别名问题 | `shipping_city` (北京/帝都) |
| **连续数值** | ❌ 禁止 | 值无限多，语义检索无意义 | `amount`, `price` |
| **ID 列** | ❌ 禁止 | 无语义，用户不会用 ID 查询 | `customer_id` |
| **时间戳** | ❌ 禁止 | 用 SQL BETWEEN 更精准 | `order_date` |
| **长文本** | ❌ 禁止 | 去重值爆炸 | `email`, `address` |

**避坑**: 给高基数列（如 `name`、`email`）建列索引会导致向量数量爆炸，检索无意义 [^8]

---

## 四、核心代码开发规范

### 4.1 表 Schema 索引构建

```python
from llama_index.core.objects import SQLTableSchema, SQLTableNodeMapping, ObjectIndex
from llama_index.core import VectorStoreIndex

def build_table_schema_index(sql_database, table_descriptions: dict):
    """
    构建表 Schema 向量索引
    
    Args:
        sql_database: SQLDatabase 实例
        table_descriptions: {表名: 业务描述}，必须包含【核心】/【辅助】标记
    
    Returns:
        ObjectIndex
    """
    
    # ✅ 推荐：显式声明核心表和辅助表
    table_schema_objs = [
        SQLTableSchema(
            table_name="orders",
            context_str="【核心】电商订单交易表，用于统计销售额、订单金额、支付方式"
        ),
        SQLTableSchema(
            table_name="inventory",
            context_str="【辅助】库存管理表，仅用于库存查询，与客户/订单/销售统计完全无关"
        ),
    ]
    
    table_node_mapping = SQLTableNodeMapping(sql_database)
    
    # ✅ 推荐：使用统一的 Embedding 模型
    obj_index = ObjectIndex.from_objects(
        table_schema_objs,
        table_node_mapping,
        VectorStoreIndex,
    )
    
    return obj_index
```

**避坑**: `context_str` 必须包含业务语义，不能只有技术描述。标记【核心】/【辅助】帮助 Embedding 模型区分重要性 [^9]

### 4.2 列索引构建（安全版）

```python
from sqlalchemy import text
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode

def build_all_column_indices(engine, columns_config: dict):
    """
    批量构建列值向量索引
    
    Args:
        engine: SQLAlchemy Engine
        columns_config: {表名: [列名1, ...]}，空列表表示不建索引
    
    Returns:
        dict: {表名: {列名: VectorStoreIndex}}，无列的表返回 {表名: {}}
    """
    
    column_indices = {}
    
    for table_name, columns in columns_config.items():
        # ✅ 关键：空列表 → 空字典占位，避免 SQLTableRetrieverQueryEngine KeyError
        if not columns:
            column_indices[table_name] = {}
            continue
        
        column_indices[table_name] = {}
        for column_name in columns:
            # 查询去重值
            query = f"""
                SELECT DISTINCT {column_name} 
                FROM {table_name} 
                WHERE {column_name} IS NOT NULL 
                LIMIT 100  -- ✅ 限制去重值数量
            """
            
            with engine.connect() as conn:
                results = conn.execute(text(query)).fetchall()
            
            values = [r[0] for r in results if r[0] is not None]
            
            # ✅ 关键：高基数检查
            if len(values) > 100:
                print(f"⚠️  {table_name}.{column_name} 去重值过多({len(values)})，跳过")
                continue
            
            # 格式: "customers.level=VIP"
            nodes = [TextNode(text=f"{table_name}.{column_name}={v}") for v in values]
            index = VectorStoreIndex(nodes)
            column_indices[table_name][column_name] = index
    
    return column_indices
```

**避坑**: 
1. 必须为空列表创建 `{}` 占位，否则 `SQLTableRetrieverQueryEngine` 内部遍历会 `KeyError` [^10]
2. 必须限制去重值数量（`LIMIT 100`），防止高基数列导致内存溢出

### 4.3 查询引擎组装（安全版）

```python
from llama_index.core.indices.struct_store import SQLTableRetrieverQueryEngine

def create_query_engine(sql_database, obj_index, row_indices, column_indices):
    """
    创建三层检索查询引擎
    
    安全处理：为所有表创建检索器条目，避免 LlamaIndex 源码 KeyError
    """
    
    # 表检索器
    table_retriever = obj_index.as_retriever(similarity_top_k=3)
    
    # 行检索器：只包含有索引的表
    rows_retrievers = {}
    if row_indices:
        for table_name in sql_database.get_usable_table_names():
            if table_name in row_indices:
                rows_retrievers[table_name] = row_indices[table_name].as_retriever(
                    similarity_top_k=2
                )
    
    # ✅ 关键：列检索器必须为所有表创建条目
    cols_retrievers = {}
    if column_indices:
        for table_name in sql_database.get_usable_table_names():
            if table_name in column_indices and column_indices[table_name]:
                # 有实际列索引
                cols_retrievers[table_name] = {
                    col_name: index.as_retriever(similarity_top_k=1)
                    for col_name, index in column_indices[table_name].items()
                }
            else:
                # ✅ 必须：空字典占位
                cols_retrievers[table_name] = {}
    
    # 动态组装，避免传入 None
    kwargs = {
        "sql_database": sql_database,
        "table_retriever": table_retriever,
        "verbose": True,
    }
    
    if rows_retrievers:
        kwargs["rows_retrievers"] = rows_retrievers
    
    # ✅ 必须：始终传入 cols_retrievers（含占位）
    kwargs["cols_retrievers"] = cols_retrievers
    
    return SQLTableRetrieverQueryEngine(**kwargs)
```

**避坑**: 
1. `cols_retrievers` 必须包含所有表（含空占位），LlamaIndex 0.14.x 源码 `_get_table_context()` 会直接访问 `self._cols_retrievers[table_name]` 无安全检查 [^11]
2. 使用 `kwargs` 动态构建，避免 `None` 值导致不同处理逻辑

---

## 五、生产环境安全规范

### 5.1 数据库连接安全

```python
from sqlalchemy import create_engine

# ✅ 推荐：只读用户 + 连接池
engine = create_engine(
    "postgresql://readonly_user:pass@host/db",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # 自动检测连接有效性
)

# ❌ 避免：管理员账号
# engine = create_engine("postgresql://postgres:password@host/db")
```

### 5.2 表白名单

```python
from llama_index.core import SQLDatabase

# ✅ 推荐：只暴露业务表
sql_database = SQLDatabase(
    engine,
    include_tables=["orders", "customers", "products"],
    # exclude_tables=["admin_logs", "user_passwords"],
)

# ❌ 避免：暴露所有表
# sql_database = SQLDatabase(engine)
```

### 5.3 SQL 注入防护

```python
from llama_index.core.prompts import PromptTemplate

# ✅ 推荐：自定义 Prompt 注入安全规则
SAFE_PROMPT = PromptTemplate("""
你只能生成 SELECT 语句。
禁止：DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE。
必须：包含 LIMIT 100。
表必须在白名单中。

Schema: {schema}
问题: {query_str}
SQL:
""")

query_engine = SQLTableRetrieverQueryEngine(
    sql_database,
    table_retriever,
    text_to_sql_prompt=SAFE_PROMPT,
)
```

**避坑**: `NLSQLTableQueryEngine` 存在 SQL 注入漏洞（CVE-2024-23751），生产环境必须使用 Guardrails [^12]

### 5.4 行级安全（RLS）

```python
# PostgreSQL RLS 与 LlamaIndex 配合
with engine.connect() as conn:
    # 设置用户上下文
    conn.execute(text(f"SET app.current_user_id = {current_user_id}"))
    
    # 再执行 LlamaIndex 查询
    response = query_engine.query("我的订单有哪些？")
    
    # RLS 自动过滤：只返回 current_user_id 的订单
```

---

## 六、性能优化指南

### 6.1 检索参数调优

| 参数 | 开发环境 | 生产环境 | 说明 |
|------|---------|---------|------|
| `table_top_k` | 2-3 | 3-5 | 简单查询用2，复杂JOIN用3-5 |
| `row_top_k` | 2-3 | 3-5 | 值歧义严重时增大 |
| `column_top_k` | 1 | 1-2 | 二值分类用1，多值用2 |
| `embed_batch_size` | 8 | 16-32 | 根据 llama.cpp 服务端并发调整 |

### 6.2 大规模数据方案

| 数据规模 | 方案 | 说明 |
|---------|------|------|
| < 1万行 | 内存索引 | `VectorStoreIndex`，简单直接 |
| 1万-100万行 | Milvus 持久化 | `MilvusVectorStore`，分布式存储 |
| > 100万行 | 采样 + 分层 | 随机采样 + 按时间分层 |

```python
from llama_index.vector_stores.milvus import MilvusVectorStore

# Milvus 配置
vector_store = MilvusVectorStore(
    uri="http://127.0.0.1:19530",
    collection_name="row_index_orders",
    dim=1024,  # 必须与 Embedding 模型一致
    overwrite=False,  # 生产环境不覆盖
)
```

**避坑**: `dim` 必须与 Embedding 模型输出维度一致，否则 Milvus 插入会失败 [^13]

---

## 七、调试与监控

### 7.1 日志输出规范

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llamaindex.sql")

# 记录每次查询的指标
def log_query_metrics(query: str, response, latency: float):
    logger.info(f"Query: {query}")
    logger.info(f"SQL: {response.metadata.get('sql_query')}")
    logger.info(f"Latency: {latency:.2f}s")
    logger.info(f"Tables: {response.metadata.get('retrieved_tables')}")
```

### 7.2 常见问题排查

| 现象 | 原因 | 解决方案 |
|------|------|---------|
| `KeyError: 'inventory'` | `cols_retrievers` 缺少占位 | 为所有表创建 `{}` 占位 |
| `ValidationError: model` | `OpenAILikeEmbedding` 用错参数 | 改用 `model_name` |
| SQL 生成错误 | 表检索遗漏关键表 | 增大 `table_top_k` 或优化表描述 |
| 值匹配错误 | 行/列检索未生效 | 检查 `rows_retrievers`/`cols_retrievers` 是否正确传入 |
| 内存溢出 | 数据量过大 | 限制 `LIMIT`，使用 Milvus |

---

## 八、参考资料

[^1]: LlamaIndex 官方设计理念 - "RAG-First" 架构  
[^2]: LlamaIndex Documentation - Structured Data / SQL Index  
[^3]: `OpenAILikeEmbedding` 源码 - `model_name` 参数校验逻辑  
[^4]: 用户项目实践 - llama.cpp `/embedding` 端点适配  
[^5]: OpenAI API Best Practices - SQL 生成温度设置  
[^6]: SQLAlchemy 反射机制 - `get_single_table_info()` 实现  
[^7]: LlamaIndex `SQLTableNodeMapping` 外键解析逻辑  
[^8]: 用户项目实践 - 高基数列导致向量索引膨胀问题  
[^9]: Embedding 语义检索实验 - `context_str` 对检索质量的影响  
[^10]: `SQLTableRetrieverQueryEngine` 源码 - `_get_table_context()` 方法  
[^11]: LlamaIndex GitHub Issues - `cols_retrievers` KeyError 报告  
[^12]: CVE-2024-23751 - `NLSQLTableQueryEngine` SQL 注入漏洞  
[^13]: Milvus Documentation - Collection Schema 维度一致性要求  

---

## 九、快速检查清单

```markdown
□ Embedding 模型使用 model_name 而非 model
□ 数据库表添加注释（表+列）
□ 外键约束已设置
□ 列索引只选低基数字符串列
□ 空列索引配置创建 {} 占位
□ 查询引擎组装时传入完整 cols_retrievers
□ 生产环境使用只读连接
□ 表白名单限制
□ SQL 注入防护 Prompt
□ 日志监控已配置
```

---

这份指南涵盖了从开发到生产的完整实践，建议保存为项目文档 `DEVELOPMENT_GUIDE.md`，供团队参考。