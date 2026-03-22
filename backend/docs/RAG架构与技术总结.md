# RAG 架构与技术栈总结

本文档基于现有代码库中的配置和实现（特别是 `factory.py`、`query_engine.py` 和 `config.py` 等模块），对项目当前的检索增强生成 (RAG) 架构和技术选型进行梳理和总结。

## 1. 核心检索架构 (RAG Backend)

项目设计了一套灵活的解耦检索架构，代码层面通过 **工厂模式（Factory Pattern）** 实现了对不同检索后端的接管。通过配置环境变量 `RAG_BACKEND`，系统能够无缝切换底层的向量数据库和检索策略。

目前系统支持两套并行的向量检索架构（**生产及开发环境默认启用的是 Milvus 混合检索**）：

### 1.1 Milvus 混合检索架构（默认配置: `milvus_hybrid`）
- **底层框架**：基于 `LlamaIndex` 编排引擎 + `Milvus` 高性能向量数据库。
- **检索策略（Hybrid Search）**：双路混合召回。
  - **稠密检索（Dense Retrieval）**：通过传统的向量化相似度进行计算检索（度量方式采用 IP - 内积相似度）。
  - **稀疏检索（Sparse Retrieval）**：基于 `BM25` 稀疏算法。该支路专门集成了 `jieba` 分词器及其特定过滤器（如 `cnalphanumonly`），针对中文关键词和长词提供精准命中能力。
- **排序与策略融合**：
  - 基于 **RRF (Reciprocal Rank Fusion，倒数排序融合)** 算法将两路检索（稠密与稀疏）产生的结果进行重新评分排位。
  - 默认配置：`rrf_k=60`，最终向下游传递 `similarity_top_k`（默认为 5）个最具价值的参考分块数据。

### 1.2 PGVector 纯向量存储架构（备用 / 降级配置: `pgvector`）
- **底层框架**：基于关系型 PostgreSQL 数据库的 `pgvector` 插件方案。主要由自定义的 `PgVectorDocumentationRetriever` 来实现。
- **检索策略**：基于单纯的稠密向量检索来进行数据召回。相较于混合架构，更侧重于简便和轻量化。

---

## 2. 核心大模型与预训练模型选型

在不同的处理环节，架构引入了不同职责的模型来保障生成质量：

### 2.1 嵌入模型 (Embedding Model)
视 RAG Backend 不同，采用了不同的 Embedding 模型配置机制以确保检索能力：
- **Milvus 模式下 (默认)**：
  - **模型名称**：英伟达 `nvidia/nv-embedqa-e5-v5`
  - **向量维度**：1024 维
  - **调用方式**：通过 NVIDIA API 进行云端推理调用（由 `LlamaIndex` 引擎管理），保证高质量文本向量化。
- **PGVector 模式下**：
  - **模型名称**：智源研究院 `baai/bge-m3`
  - **调用方式**：在执行业务工厂（`create_business_vector_store`）初始化时挂载，侧重于多语言及综合能力支持。

### 2.2 重排序精排模型 (Reranker) - [可选链路]
系统前瞻性地设计并植入了可选的“二次精排”层，用来进一步矫正检索结果的优先级和准确度。
- **开关机制**：受控于环境变量 `RERANK_ENABLED` （默认为 False）。
- **模型名称**：英伟达 `nvidia/rerank-qa-mistral-4b`
- **主要作用**：当该层开启时，由基础引擎检出的 `Top-K` 节点会再次送给该模型，进行极其精细但算力消耗高的交叉注意力评分，并根据 `RERANK_SCORE_THRESHOLD` 截断剔除弱相关内容，最终返回 `RERANK_TOP_N`（默认 3）条最精华数据用于最终合成。

### 2.3 文本生成与合成大模型 (LLM)
负责最终整合 Reference Nodes 并对用户输出最终回答：
- **开发与云端常规基座**：`deepseek-chat` (DeepSeek V3 系列)，默认作为 `LlamaIndex` 的全局大模型 (`Settings.llm`) 进行推理，提供了极高的性价比与优秀的推理水平。
- **私有化与本地模型探索**：项目的配置文件中明确预留并部署了针对 RTX 5090 等终端优化的本地 Ollama 推理堆栈（默认挂载参数为 `qwen3:30b` 及 `32768` 上下文）。表明有在本地及离线环境下提供大模型支持的设计能力。

---

## 3. 工作流执行流向解析
标准的 RAG 查询执行链路上，目前引擎将表现出如下生命周期（以开发模块 `development/hybrid/query_engine.py` 为例）：
1. **系统加载与延迟连接**：为防止不必要的长连接，系统实现了向量存储的**延迟初始化**。只有在首次调用 `retrieve()` 时才会同后端服务器（如 Milvus / Postgres）建立连接池并加载配置。
2. **文本向量化**：获取 User Query 后，通过选定的 Embedding 模型进行在线向量化。
3. **节点召回与重排序**：
   - 如果启用混合模式，则自动切分 User Query 执行 BM25 相关性查库操作，并与向量化查库操作合并。
   - 使用 RRF 公式重打分聚合。
   - 判断 Reranker 配置项，如果开启则进一步调用 Mistral-4b 过滤节点列表。
4. **合成输出**：将最终存活下来的高质量文本提取出来包裹成上下文 Prompt，连同问题一起递交给 DeepSeek 等主力大语言模型进行 `synthesize`（合成输出）。
5. **记录观测**：支持接入完整的 `LangSmith` 监控追踪链路（如果 `LANGSMITH_TRACING=true`）。

## 总结
整套 RAG 系统立足于业务扩展性与高性能设计。支持低成本（PGVector）与高性能并行（Milvus+Nvidia V5+RRF混合搜索+Rerank精排）双轨架构，配合业界高水准开源生成模型（DeepSeek / Qwen），展现出了生产级别的稳健表现与设计模式。
