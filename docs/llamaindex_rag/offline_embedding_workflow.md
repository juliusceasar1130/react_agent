# 离线嵌入同步管道 (Ingestion Pipeline) 工作手册

本手册详述了本项目中 **SQL 元数据三层 RAG 检索系统** 的离线嵌入同步管道的架构设计、数据源约束、提取机制以及物理存储设计。

---

## 一、 核心架构设计与分工解耦

离线同步任务的核心心智是将**关系型数据库结构 (PostgreSQL)** 经过加工清洗后，灌入**向量数据库 (Milvus)** 缓存。我们在此实现了静态骨架与向量检索的彻底解耦：

1.  **associated_tables (表级静态骨架)**：
    *   **职责**：仅作为 SQL 编写时的物理表结构骨架，用于提供给写 SQL 时的 Schema 反射。
    *   **离线关联**：**完全不参与**任何向量数据库离线同步过程（不建立 DDL 向量、不抽取列值/行实体），避免大事实表造成语义噪声。
2.  **lexicon_enabled_tables (表级向量白名单)**：
    *   **职责**：作为向量检索库的第一层（DDL库）、第二层（行记录库）、第三层（列值库）三层检索集合的**唯一向量化嵌入来源**。
    *   **离线关联**：所有的离线向量提取、Embedding 计算、以及 Milvus 灌入操作，**全部且仅**依据该白名单进行准入拦截。

---

## 二、 技能元数据自治配置约束

在每个领域技能的 `meta.py` 内部，通过声明白名单进行数据同步拦截。配置文件采用**由宏观到微观 (表级 $\rightarrow$ 行级 $\rightarrow$ 列级)** 的属性排版规则：

```python
{
    # 1. 表级静态关联骨架（仅供 SQL 组织）
    "associated_tables": [
        "fct.fct_vehicle_position_current",
        "dim.carbody_registry",
        "dim.dim_process_area"
    ],
    
    # 2. 向量嵌入白名单（三层向量库唯一数据源）
    "lexicon_enabled_tables": [
        "dim.dim_process_area"
    ],
    
    # 3. 行级实体向量化范围
    "rows_lexicon_whitelist": {
        "dim.dim_process_area": {
            "pk": "process_area_name",             # 物理主键
            "semantic_cols": ["description"],      # 拼接用于计算 Embedding 的语义列
            "limit": 1000                          # 行数据同步上限
        }
    },
    
    # 4. 列级字典向量化范围（支持两种结构）
    "columns_lexicon_whitelist": {
        "dim.dim_process_area": {
            "cols": ["process_area_name", "description"],
            "limit": 1000                          # 列去重值同步上限
        }
    }
}
```

> **列白名单兼容规则**：
> *   **高级字典格式** (推荐)：可显式指定 `"cols"` 及 `"limit"`。
> *   **传统简易列表格式**：如 `["process_area_name", "description"]`。同步管道在解析时会自动向下兼容，默认使用 `1000` 作为 fallback 限额上限。

---

## 三、 三层数据提取与加工清洗 (ETL)

管道采用原生 SQLAlchemy 从 PostgreSQL 中并行抽取并加工三层不同的数据节点：

```
                              [PostgreSQL 关系型源数据]
                                         │
                 ┌───────────────────────┼──────────────────────┐
                 ▼                       ▼                      ▼
         [表级 DDL 同步]           [行实体描述同步]        [列去重值字典同步]
                 │                       │                      │
   - 表/字段中文批注提取    - PK + 语义列字段拼接    - 白名单内每列分别执行
   - 反射 Primary/Unique 约束  - text="col1=val1..."    - SELECT DISTINCT col
   - LIMIT 3 真实样本采样注入  - metadata 强注入表名/PK  - 动态 LIMIT 控制
                 │                       │                      │
                 └───────────────────────┼──────────────────────┘
                                         ▼
                            [封装为 LlamaIndex Document]
```

### 1. 表级 DDL (table_schema_store)
*   **物理 SQL**：直接利用 SQLAlchemy 的 `inspect` 进行表结构和约束反射。
*   **富集加工**：自动抓取物理数据库中表和列的**中文 Comments 注释**。
*   **样本注入**：执行 `SELECT * FROM table LIMIT 3` 获取三行真实数据样本，以 `--` 形式追加在 DDL 尾部，帮助大模型认知字段值范例。

### 2. 行记录实体 (db_row_lexicon)
*   **物理 SQL**：根据行配置中的 `pk` 和 `semantic_cols`，拼接执行 `SELECT {pk}, {semantic_cols} FROM {table} LIMIT {limit}`。
*   **语义拼接 (Text)**：将多列属性拼接为一句话（例如：`process_area_name=前道电泳二区, description=用于物流二期...`）作为向量计算的载体。*不直接拼入物理表名以防止语义噪音干扰检索。*
*   **元数据注入 (Metadata)**：在 Document 元数据中强注入 `table_name` 和 `primary_key_val`，保证召回时能准确解析出所属的物理位置。

### 3. 去重列值字典 (db_value_lexicon)
*   **物理 SQL**：针对配置的每一列，分别执行：
    ```sql
    SELECT DISTINCT {col_name} FROM {table} WHERE {col_name} IS NOT NULL LIMIT {limit};
    ```
*   **语义拼接 (Text)**：每个节点拼装为 `"表: {table}, 列: {col_name}, 列值: {val}"` 进行向量化，供在线做模糊名词翻译。

---

## 四、 物理存储设计与向量索引

抽取出来的 Document 被送入 LlamaIndex 的 Ingestion Pipeline 进行分布式物理存储加载：

1.  **混合向量存储 (Hybrid Search)**：
    *   **密集向量 (Dense Vector)**：利用本地 GGUF 引擎驱动的密集向量模型（`Qwen3-Embedding-0.6B`），生成符合语义相似度召回的密集向量。
    *   **稀疏向量 (Sparse Vector)**：利用 Milvus 内置的 Jieba 中文分词分析器，自动提取文本的词频构建稀疏矩阵向量，实现精准关键字词的 BM25 召回。
2.  **Milvus 三个 Collection Schema 规范**：
    所有三个集合统一由 [store.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/vector/sql_lexicon/store.py) 连接工厂进行物理集合结构创建：
    *   `table_schema_store`：缓存 `lexicon_enabled_tables` 范围内的表级 DDL。
    *   `db_row_lexicon`：缓存表行级语义描述。
    *   `db_value_lexicon`：缓存列去重文本。
3.  **持久化刷盘 (Flush)**：
    数据加载完毕后，管道自动触发 Milvus 底层集合的 `flush()` 操作，强制让内存段数据下盘落镜，保障首次检索和重启时均是就绪状态。

---

## 五、 多线程与 Lifespan 的子循环无死锁调度

在多线程的事件循环（FastAPI lifespan 等）中执行同步时，极易因在异步线程中阻塞同步调用导致 loop死锁挂起。本项目在调度设计上完成了双端闭环：

1.  **多线程事件循环自适应检测**：
    在 [tasks.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/vector/sql_lexicon/tasks.py) 内部，通过对 `asyncio.get_running_loop()` 进行嗅探判定：
    *   如果处于异步 Lifespan 框架调度下（存在活跃的 `running loop`），通过**操作系统子线程 (`threading.Thread`)** 独立拉起同步，并在子线程内使用 `asyncio.run(_async_wrapper())` 自主开启一个干净、不受干扰的底层 Running Loop，彻底杜绝主 HTTP 线程阻塞发生死锁。
    *   如果在纯同步环境或测试用例下，则直接调用 `_main_sync()`。
2.  **单元/集成测试的对称对齐**：
    通过将 [test_sync_metadata.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py) 改造为非 `async def`（普通的同步测试），测试环境同样走通 `asyncio.run` 子循环分支，确保单元测试机制与 FastAPI 物理生产环境 100% 对齐。

---

## 六、 核心代码文件映射

*   **配置层** $\rightarrow$ [paint_shop_vehicle_logistics/meta.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/skills/domains/paint_shop_vehicle_logistics/meta.py)
*   **连接层** $\rightarrow$ [sql_lexicon/store.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/vector/sql_lexicon/store.py)
*   **抽取节点** $\rightarrow$ [sql_lexicon/pipeline/extractor_nodes.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py)
*   **载入节点** $\rightarrow$ [sql_lexicon/pipeline/milvus_load_node.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py)
*   **物理建表** $\rightarrow$ [sql_lexicon/init_script.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/vector/sql_lexicon/init_script.py)
*   **后台守护调度** $\rightarrow$ [sql_lexicon/tasks.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/app/agent/vector/sql_lexicon/tasks.py)
