# Development Module

`development/` 文件夹包含了 RAG 系统开发阶段的核心模块和测试脚本。

## 目录结构

### 核心基础设施
- **[config.py](file:///d:/Python/workplace/llamaindex/development/config.py)**: 全局模型配置中心
  - 加载 `.env` 环境变量。
  - 配置 LlamaIndex 的全局 LLM (DeepSeek) 和 Embedding (NVIDIA)。
  - 定义向量维度等核心常量。
- **[data_loader.py](file:///d:/Python/workplace/llamaindex/development/data_loader.py)**: 数据加载与处理
  - 递归加载指定目录下的 JSON 数据。
  - 执行语义分块 (SentenceSplitter) 将文档转换为节点。

### 检索实现
- **[vector/](file:///d:/Python/workplace/llamaindex/development/vector/)**: 纯向量检索模式
  - `vector_init.py`: 索引初始化脚本（一次性执行）。
  - `query_engine.py`: 查询引擎封装，支持 Top-K 检索。
  - `vector_query.py`: 快速测试查询脚本。
- **[hybrid/](file:///d:/Python/workplace/llamaindex/development/hybrid/)**: 混合检索模式 (Vector + BM25)
  - `hybrid_init.py`: 混合索引初始化脚本，集成 jieba 分词。
  - `query_engine.py`: 混合查询引擎封装，使用 RRF (Reciprocal Rank Fusion) 进行排序。
  - `hybrid_query.py`: 快速测试查询脚本。

## 快速开始

1. **环境准备**:
   确保 `.env` 中已配置 `DEEPSEEK_API_KEY` 和 `NVIDIA_API_KEY`。
2. **数据初始化**:
   - 运行 `python -m development.vector.vector_init` 或 `python -m development.hybrid.hybrid_init` 加载测试数据。
3. **执行查询**:
   - 运行对应的 `*_query.py` 脚本进行检索测试。

---
> [!NOTE]
> 开发此模块的目的是为了解耦检索逻辑与应用层，方便进行 RAG 性能对比和调优。
