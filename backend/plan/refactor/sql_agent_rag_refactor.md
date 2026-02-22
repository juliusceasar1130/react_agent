## 目标

- **简化结构、提高可读性**：SQL Agent + RAG 相关代码职责清晰，文件布局稳定。
- **接口抽象**：上层只依赖统一接口（检索 / 精排），便于后续切换后端（pgvector → hybrid / milvus）。
- **最小改动落地**：在保留现有功能的前提下重构，优先不动 API 行为。

## 目录结构（backend 层）

- **`app/agent`**
  - `service.py`：SQL Agent 服务入口（创建 LLM、DB、工具、中间件）。
  - `middleware/`
    - `rag_middleware.py`：业务 RAG 中间件，只依赖通用检索 / 精排接口。
    - `skill_middleware.py`：技能注入中间件（保持现状，必要时小幅整理）。
  - `tools/`：SQL 工具和包装逻辑（`sql_db_query` 封装等）。
  - `utils/`
    - `rerank_service.py`：NVIDIA NIM 精排适配层（实现精排接口）。
    - 其他工具函数保持不动（日志、表注释、向量库封装等）。
  - `vector_init/`：向量数据导入和初始化脚本（保持独立）。
  - `vector/`（新）
    - `base.py`：统一接口定义。
      - `BaseRetriever`：只负责向量检索，返回 `(Document, score)`。
      - `BaseReranker`：只负责精排，输入 `(query, documents)`。
    - `pgvector_retriever.py`：基于现有 `PgVectorStoreWrapper` 的实现。
    - `factory.py`：根据配置创建检索器 / 精排器（pgvector，现在；hybrid，预留）。

## 接口与实现

- **BaseRetriever**
  - `retrieve(query, k=5, score_threshold=None, doc_type="documentation", domain=None) -> List[Tuple[Document, float]]`
  - 不关心底层向量库实现，只关心“按类型检索 + 打分”。

- **BaseReranker**
  - `rerank(query, documents) -> List[Tuple[Document, float]]`
  - 不关心召回逻辑，只对候选文档重新打分排序（可内建 Top-N / 阈值裁剪）。

- **PgVectorDocumentationRetriever**
  - 包装 `PgVectorStoreWrapper.similarity_search_by_type_with_score`。
  - 固定 `doc_type="documentation"` 为主用场景，保留参数透传能力。

- **NvidiaRerankService**
  - 继承 `BaseReranker`，保持现有实现，增加最小改动：
    - 只对非空文本文档调用 NIM。
    - 失败时降级为原始顺序（分数置 0）。
    - 支持 `top_n` 和 `score_threshold`。

- **Factory：`create_business_retriever_and_reranker()`**
  - 输入：读取 `settings`，包含：
    - `rag_backend`（默认 `"pgvector"`，预留 `"hybrid"`）。
    - `rerank_enabled`、`nvidia_api_key`、`rerank_model`、`rerank_top_n`、`rerank_score_threshold`。
  - 输出：`(BaseRetriever 实例, 可选 BaseReranker 实例)`。
  - 责任：
    - 对具体实现解耦（pgvector / hybrid）。
    - 对 Rerank 初始化失败做降级（记录 warning，返回 `reranker=None`）。

## 中间件与服务层改造

- **BusinessRagMiddleware（方案 B）**
  - 构造函数签名：
    - `BusinessRagMiddleware(retriever: BaseRetriever, reranker: Optional[BaseReranker] = None, doc_k: int = 5, score_threshold: Optional[float] = None)`
  - `before_model` 流程：
    1. 读取用户最新自然语言问题（不处理工具调用消息）。
    2. 调用 `retriever.retrieve`：
       - 固定 `doc_type="documentation"`。
       - 使用 `doc_k`、`score_threshold`。
       - 记录检索数量和分数范围。
    3. 如配置了 `reranker`：
       - 调用 `reranker.rerank(query, retrieved_docs)`。
       - 错误时捕获并降级为原始向量结果。
    4. 将最终文档列表格式化为业务知识片段，构造单一 `SystemMessage` 注入对话：
       - 使用固定 `message_id`，避免重复插入。
       - 只在当前轮有检索结果时更新 / 插入。

- **SQLAgentService**
  - `_initialize_agent` 中 RAG 部分逻辑调整为：
    1. 调用 `create_business_retriever_and_reranker()`。
    2. 根据是否存在 `reranker` 动态设置 `doc_k`（例如：纯向量 5，向量+精排 10）。
    3. 实例化 `BusinessRagMiddleware` 并加入中间件列表（位于最前，先注入业务知识，再做技能 / 总结）。
  - 其余部分（LLM、DB、工具包装、SummarizationMiddleware）保持不变，仅按需要小幅整理注释和日志。

## 配置与切换点

- 在 `settings` 中新增 / 明确：
  - `rag_backend: str = "pgvector"`  # 未来可支持 `"hybrid"`。
  - `rerank_enabled: bool`。
  - `rerank_model: str`、`rerank_top_n: int`、`rerank_score_threshold: Optional[float]`。
- 将所有 RAG 后端选择逻辑集中在 `vector/factory.py`：
  - 未来接入 llamaindex + milvus 时，只需：
    - 新增 `HybridRetriever` / 可选 `HybridReranker` 实现。
    - 在 factory 中增加 `"hybrid"` 分支。
    - 不改 `BusinessRagMiddleware` 和 `SQLAgentService` 的调用方式。

## 开发顺序（推荐）

1. **接口与工厂**
   - 新增 `vector/base.py`。
   - 新增 `vector/pgvector_retriever.py`。
   - 新增 `vector/factory.py`（仅实现 `"pgvector"` 分支）。
2. **适配现有实现**
   - 修改 `utils/rerank_service.py` 使其实现 `BaseReranker`。
   - 如有现成 `PgVectorStoreWrapper`，在 retriever 中直接复用。
3. **中间件与服务层改造**
   - 重构 `BusinessRagMiddleware` 构造参数与 `before_model`，改为依赖接口。
   - 在 `service.py` 的 `_initialize_agent` 中使用 factory + 新中间件构造方式。
4. **验证与清理**
   - 运行现有测试（`test_rag*`, `test_rerank*`, `test_agent*`），确认行为一致。
   - 统一命名与日志（中英文简短清晰），删除临时代码和重复注释。

## 设计原则回顾

- **单向依赖**：上层（`service` / `middleware`）依赖抽象接口，不反向引用具体实现。
- **稳定入口**：RAG 相关新能力统一通过 `vector/factory.py` 切入，避免在多处散落 pgvector / NIM 细节。
- **简洁优先**：文件粒度控制在“10 分钟可读完”，类和方法注释保持一句话说明责任即可。

