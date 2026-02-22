# Milvus 混合检索索引初始化模块

本模块用于一次性初始化 Milvus 混合检索索引（向量 + BM25），将 JSON 格式的文档数据导入到 Milvus 数据库中。

## 功能特性

- ✅ 支持递归加载目录下的所有 JSON 文件
- ✅ 自动文档切分（可配置 chunk_size 和 chunk_overlap）
- ✅ 构建混合检索索引（向量检索 + BM25 全文检索）
- ✅ 使用 RRF（Reciprocal Rank Fusion）融合两种检索结果
- ✅ 支持覆盖已有 Collection 或增量添加

## 快速开始

### 1. 准备数据

在数据目录中放置 JSON 格式的文档文件，支持以下两种格式：

**列表格式（推荐）：**
```json
[
  {
    "document": "这是第一段文档内容...",
    "metadata": {"source": "doc1", "title": "文档1"}
  },
  {
    "document": "这是第二段文档内容...",
    "metadata": {"source": "doc2", "title": "文档2"}
  }
]
```

**单对象格式：**
```json
{
  "document": "文档内容...",
  "metadata": {"source": "doc1", "title": "文档1"}
}
```

> 注意：也支持使用 `"text"` 字段作为 `"document"` 的别名。

### 2. 配置环境变量

在 `.env` 文件中配置以下参数：

```env
# Milvus 服务配置
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION_NAME=rag_store
MILVUS_EMBED_DIM=1024
MILVUS_RRF_K=60

# 数据加载配置
MILVUS_DATA_DIR=./data/examples
MILVUS_CHUNK_SIZE=512
MILVUS_CHUNK_OVERLAP=50
MILVUS_OVERWRITE=true

# NVIDIA API Key（用于 Embedding）
NVIDIA_API_KEY=your_nvidia_api_key_here
```

### 3. 运行初始化脚本

> ⚠️ **重要**：项目使用 `backend.app` 作为包前缀，必须在 **backend 的父目录** 运行，否则会报 `ModuleNotFoundError: No module named 'backend'`。

**方式1：直接运行脚本**
```bash
# 切换到 backend 的父目录（.tree/features/agent）
cd .tree/features/agent
python -m backend.app.agent.milvus_init.init_milvus
```

**方式2：作为模块导入使用**
```python
from backend.app.agent.milvus_init.init_milvus import main
import asyncio

# 使用默认配置
asyncio.run(main())

# 或自定义参数
asyncio.run(main(
    data_dir="./data/my_docs",
    collection_name="my_collection",
    chunk_size=1024,
    overwrite=True
))
```

**方式3：使用命令行参数（需要修改脚本）**
```bash
python init_milvus.py --data-dir ./data/examples --overwrite true
```

## 配置参数说明

| 参数 | 环境变量 | 默认值 | 说明 |
|------|---------|--------|------|
| `data_dir` | `MILVUS_DATA_DIR` | `./data/examples` | JSON 数据文件所在目录 |
| `milvus_uri` | `MILVUS_URI` | `http://localhost:19530` | Milvus 服务地址 |
| `collection_name` | `MILVUS_COLLECTION_NAME` | `rag_store` | Milvus Collection 名称 |
| `embed_dim` | `MILVUS_EMBED_DIM` | `1024` | 向量维度（需与 Embedding 模型匹配） |
| `chunk_size` | `MILVUS_CHUNK_SIZE` | `512` | 文档分块大小（字符数） |
| `chunk_overlap` | `MILVUS_CHUNK_OVERLAP` | `50` | 分块重叠大小（字符数） |
| `overwrite` | `MILVUS_OVERWRITE` | `true` | 是否覆盖已有 Collection |
| `rrf_k` | `MILVUS_RRF_K` | `60` | RRF 融合参数（越大结果越均衡） |

## 模块结构

```
milvus_init/
├── __init__.py          # 模块导出
├── init_milvus.py       # 主入口脚本
├── data_loader.py       # 数据加载与切分
├── init_store.py        # Milvus 索引构建
└── README.md            # 本文档
```

## 使用示例

### 示例1：基本使用

```python
import asyncio
from app.agent.milvus_init.init_milvus import main

# 使用默认配置初始化
asyncio.run(main())
```

### 示例2：自定义参数

```python
import asyncio
from app.agent.milvus_init.init_milvus import main

asyncio.run(main(
    data_dir="./data/my_documents",
    collection_name="my_custom_collection",
    chunk_size=1024,
    chunk_overlap=100,
    overwrite=False,  # 增量添加，不覆盖
    rrf_k=80
))
```

### 示例3：分步骤使用

```python
from app.agent.milvus_init.data_loader import load_json_docs, split_nodes
from app.agent.milvus_init.init_store import init_hybrid_store

# 步骤1: 加载文档
docs = load_json_docs("./data/examples")

# 步骤2: 切分节点
nodes = split_nodes(docs, chunk_size=512, chunk_overlap=50)

# 步骤3: 构建索引
index = init_hybrid_store(
    nodes=nodes,
    uri="http://localhost:19530",
    collection_name="rag_store",
    embed_dim=1024,
    overwrite=True,
    rrf_k=60
)
```

## 常见问题

### Q1: 提示 "缺少 NVIDIA_API_KEY"
**A:** 需要在 `.env` 文件中设置 `NVIDIA_API_KEY`，或通过环境变量导出。

### Q2: 提示 "未找到 JSON 文件"
**A:** 检查 `MILVUS_DATA_DIR` 配置的路径是否正确，确保目录中存在 `.json` 文件。

### Q3: Milvus 连接失败
**A:** 确保 Milvus 服务正在运行，检查 `MILVUS_URI` 配置是否正确。

### Q4: 向量维度不匹配
**A:** 确保 `MILVUS_EMBED_DIM` 与使用的 Embedding 模型维度一致（当前使用 NVIDIA NV-EmbedQA-E5-V5，维度为 1024）。

### Q5: 如何增量添加数据？
**A:** 设置 `overwrite=False`，新数据会追加到现有 Collection 中。

## 注意事项

1. **一次性操作**：初始化脚本主要用于一次性构建索引，后续查询无需重复运行。
2. **覆盖模式**：首次运行建议设置 `overwrite=True`，后续增量添加时设置为 `False`。
3. **数据格式**：确保 JSON 文件格式正确，包含 `document` 或 `text` 字段。
4. **Milvus 版本**：需要 Milvus 版本 ≥ v2.6.11 以支持 BM25 混合检索。

## 相关文档

- [LlamaIndex Milvus 文档](https://docs.llamaindex.ai/en/stable/examples/vector_stores/MilvusIndexDemo/)
- [Milvus 官方文档](https://milvus.io/docs)
