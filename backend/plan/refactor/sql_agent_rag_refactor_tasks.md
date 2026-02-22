## 1. 接口与基础设施

- [ ] **1.1 定义检索与精排抽象接口**
  - [ ] 在 `app/agent/vector/base.py` 新建文件。
  - [ ] 定义 `BaseRetriever` 抽象类（`retrieve(query, k=5, score_threshold=None, doc_type="documentation", domain=None)`）。
  - [ ] 定义 `BaseReranker` 抽象类（`rerank(query, documents)`）。
  - [ ] 增加必要的类型注解（如 `Document`、返回值为带分数的列表）。

- [ ] **1.2 PgVector 检索实现**
  - [ ] 在 `app/agent/vector/pgvector_retriever.py` 新建 `PgVectorDocumentationRetriever`。
  - [ ] 复用现有 `PgVectorStoreWrapper` / pgvector 封装，适配到 `BaseRetriever` 接口。
  - [ ] 支持 `doc_type`、`k`、`score_threshold`、`domain` 参数透传/默认。
  - [ ] 添加基础日志（检索数量、分数范围），避免大量噪音。

- [ ] **1.3 Rerank 抽象适配**
  - [ ] 修改 `app/agent/utils/rerank_service.py`，让核心精排类实现 `BaseReranker`。
  - [ ] 保持对当前 NVIDIA NIM 调用逻辑的兼容（API Key、模型名从配置读取）。
  - [ ] 对空文本文档或异常情况进行降级处理（返回原顺序，分数置 0 或沿用原始分数）。
  - [ ] 支持 `top_n` 和 `score_threshold` 参数。

- [ ] **1.4 工厂方法封装**
  - [ ] 在 `app/agent/vector/factory.py` 新建 `create_business_retriever_and_reranker(settings)`。
  - [ ] 从 `settings` 中读取 `rag_backend`（默认 `"pgvector"`）、`rerank_enabled`、`rerank_model`、`rerank_top_n`、`rerank_score_threshold` 等。
  - [ ] 实现 `"pgvector"` 分支：返回 `PgVectorDocumentationRetriever` 和可选 `NvidiaRerankService`。
  - [ ] Reranker 初始化失败时写入 warning 日志并返回 `reranker=None`，不抛出。
  - [ ] 为未来 `"hybrid"` / 其他后端预留分支结构（暂不实现）。

## 2. 中间件改造

- [ ] **2.1 设计与签名调整**
  - [ ] 在 `app/agent/middleware/rag_middleware.py` 中定义/重构 `BusinessRagMiddleware`。
  - [ ] 构造函数接收：`retriever: BaseRetriever`、`reranker: Optional[BaseReranker] = None`、`doc_k: int = 5`、`score_threshold: Optional[float] = None`。
  - [ ] 移除对具体 pgvector / rerank 实现的直接依赖，只依赖抽象接口。

- [ ] **2.2 before_model 流程实现**
  - [ ] 从消息中提取当前轮的自然语言用户问题（忽略工具调用消息）。
  - [ ] 调用 `retriever.retrieve(...)` 获取候选文档列表，记录数量和分数区间。
  - [ ] 在存在 `reranker` 时调用 `reranker.rerank(query, documents)` 完成精排。
  - [ ] 对精排异常进行捕获与降级（回退到未精排结果）。
  - [ ] 将最终文档整理成统一的业务知识片段文本，插入/更新一个固定 `SystemMessage`（固定 `message_id`，避免重复堆叠）。

- [ ] **2.3 与其他中间件的集成**
  - [ ] 确认 `BusinessRagMiddleware` 只负责“知识注入”，不修改 SQL 工具调用和总结中间件行为。
  - [ ] 确保中间件执行顺序：RAG → 其他业务中间件（如技能、中间总结）。

## 3. 服务层集成（SQLAgentService）

- [ ] **3.1 引入工厂与中间件**
  - [ ] 在 `app/agent/service.py` 的 `_initialize_agent`（或等价初始化函数）中引入 `create_business_retriever_and_reranker`。
  - [ ] 根据返回的 `(retriever, reranker)` 实例化 `BusinessRagMiddleware`。
  - [ ] 将 `BusinessRagMiddleware` 插入到中间件列表靠前位置（在技能 / 总结中间件之前）。

- [ ] **3.2 配置驱动行为**
  - [ ] 根据 `settings.rerank_enabled` 动态调整 `doc_k`（例如：无精排时较小，有精排时适当放大召回）。
  - [ ] 只在开启 RAG / 配置完整时启用 `BusinessRagMiddleware`，否则跳过。
  - [ ] 保证现有 API 签名和主要行为不变（输入输出兼容）。

- [ ] **3.3 日志与错误处理**
  - [ ] 为关键路径添加适度日志（初始化成功/失败、RAG 开关状态），避免过多冗长输出。
  - [ ] 在初始化阶段对关键配置缺失给出明确错误或警告信息。

## 4. 配置与常量整理

- [ ] **4.1 settings 扩展**
  - [ ] 在配置模块中新增或确认存在以下字段：
    - [ ] `rag_backend: str = "pgvector"`
    - [ ] `rerank_enabled: bool`
    - [ ] `rerank_model: str`
    - [ ] `rerank_top_n: int`
    - [ ] `rerank_score_threshold: Optional[float]`
  - [ ] 为新字段提供合理默认值与注释说明。

- [ ] **4.2 常量与类型**
  - [ ] 将与 RAG / 精排相关的 magic number（默认 k、top_n、阈值）整理为常量或配置。
  - [ ] 确保公共类型（如 `Document` 定义）集中在合适位置复用。

## 5. 测试与验证

- [ ] **5.1 单元/集成测试覆盖**
  - [ ] 为 `PgVectorDocumentationRetriever` 添加基本单测（可用小样本或 mock vector store）。
  - [ ] 为 `NvidiaRerankService` 增补/更新单测，覆盖正常与降级路径（可通过 mock NIM 调用）。
  - [ ] 为 `BusinessRagMiddleware` 添加测试，验证：
    - [ ] 无结果时不会插入多余系统消息。
    - [ ] 有结果时系统消息内容格式正确。
    - [ ] 多轮对话时系统消息会被更新而非无限追加。

- [ ] **5.2 回归现有测试**
  - [ ] 运行现有 `test_rag*.py`、`test_rerank*.py`、`test_agent*.py`。
  - [ ] 修复因接口调整导致的断言/导入问题。
  - [ ] 确认 SQL Agent + RAG 主要使用场景行为与之前一致或更优。

## 6. 清理与文档

- [ ] **6.1 代码清理**
  - [ ] 删除或重构已被新结构替代的旧 RAG / pgvector 直接调用代码。
  - [ ] 统一命名（类名、文件名、日志 key），避免中英文混用不一致。
  - [ ] 确保不会留下未使用的 import、死代码。

- [ ] **6.2 文档同步**
  - [ ] 根据最终实现回看 `sql_agent_rag_refactor.md`，同步更新必要细节（如实际类名、文件名差异）。
  - [ ] 在项目更上层的开发文档中简单介绍新的 `vector/` 模块和切换点（可选）。

