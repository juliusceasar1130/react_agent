---
type: 领域
title: "RAG 与数据库词典检索"
description: "双后端检索（pgvector / Milvus 混合），支持可选 NVIDIA 重排序、三层数据库词典（表 DDL、去重列值、行实体）以及反馈驱动的黄金用例流水线。"
tags: [domain, rag, milvus, pgvector, lexicon]
openwiki:
  roles: [domain, integration]
  change_kinds: [retrieval, data]
  source_paths: [backend/app/agent/vector/factory.py, backend/app/agent/vector/base.py, backend/app/agent/vector/embedding_provider.py, backend/app/agent/vector/sql_lexicon/retriever.py, backend/app/agent/vector/sql_lexicon/tasks.py, backend/app/agent/vector/rule_extractor.py, backend/app/agent/vector/llm_refiner.py]
  symbols: [create_business_retriever_and_reranker, add_document_to_store, DatabaseLexiconRetriever, DEFAULT_EXTRACTOR_PIPELINE, refine_sql_case_with_llm]
  test_paths: [backend/tests/agent/vector/sql_lexicon/test_retriever.py, backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py, backend/tests/agent/test_retriever_async_contract.py]
  invariants:
    - Retriever choice is config-driven (settings.rag_backend) and unknown values fall back to pgvector.
    - Milvus retrievers use lazy initialization to avoid creating connections at import time.
    - The lexicon retriever's three-way retrieve_all isolates per-layer exceptions so one failure never blocks the round.
  validation_commands: ["cd backend && python -m pytest tests/agent/vector tests/agent/test_retriever_async_contract.py -q"]
---

# RAG 与数据库词典检索

`backend/app/agent/vector/` 为智能体实现检索增强生成，并通过 [BusinessRagMiddleware](../architecture/middleware-pipeline.md) 接入。包文档：`backend/app/agent/vector/readme.md`；更深入的设计说明见 `docs/llamaindex_rag/` 和 `docs/RAG开发包development/`。

## 后端（工厂）

`create_business_retriever_and_reranker()`（位于 `backend/app/agent/vector/factory.py`）是唯一接缝：

| `settings.rag_backend` | 检索器 | 备注 |
|---|---|---|
| `pgvector`（默认） | `PgVectorDocumentationRetriever`（基于 `rag_store`；`DATABASE_URL` 上的集合，使用 `baai/bge-m3`） | 同步存储 |
| `milvus_hybrid` | `MilvusHybridRetriever`（LlamaIndex + 稠密 + BM25 + RRF，通过 `MILVUS_RRF_K` 设置 RRF k） | 延迟连接；嵌入提供器通过 `embedding_provider.py`（`EMBEDDING_PROVIDER` = `ollama` 或 `llama_cpp` Qwen3） |
| 未知值 | 回退到 pgvector | 记录警告 |

- 可选重排序器：当 `RERANK_ENABLED=true` 时，使用 `NvidiaReranker`（`backend/app/agent/vector/rerank/`），默认模型为 `nvidia/rerank-qa-mistral-4b`。
- `add_document_to_store(text, metadata)` 将黄金 SQL 用例写入当前激活的后端——这是下文反馈流水线的落点。
- 异步契约：`BaseRetriever` 定义默认回退到 `retrieve` 的 `aretrieve`；具体检索器必须实现它——由 `backend/tests/agent/test_retriever_async_contract.py`（`test_milvus_hybrid_retriever_has_aretrieve`、`test_pgvector_retriever_has_aretrieve`）验证。

## 三层数据库词典

`DatabaseLexiconRetriever`（`backend/app/agent/vector/sql_lexicon/retriever.py`）持有三个 Milvus 集合，每个都是混合 LlamaIndex 索引：

1. `table_schema_store` — 表 DDL 骨架（从实时 schema 填充，参见 `sql_lexicon/pipeline/`）。
2. `db_value_lexicon` — 去重后的列值。
3. `db_row_lexicon` — 行级物理值对齐。

`retrieve_all(query)` 并发执行三个查找，并按层隔离异常，返回 `{"tables": [...], "values": [...], "rows": [...]}`。`BusinessRagMiddleware` 在文档检索的同一轮中调用它，并将结果写入 `RequestContext.lexicon_context`（参见 [state-and-context](../architecture/state-and-context.md)）；面向 LLM 的词典工具（[subagent-sql](../architecture/subagent-sql.md)）按需使用同一检索器。

启动同步：当 `settings.db_lexicon_sync_on_startup` 为 true 时，`backend/app/main.py` 在应用生命周期期间触发 `start_metadata_lexicon_sync_async`（来自 `sql_lexicon/tasks.py`）。

## 反馈驱动的黄金用例流水线

这是“自进化少样本”循环：

1. **收集** — 前端 👍/👎/⭐ 按钮通过 `POST /api/chat/messages/{id}/feedback` 提交反馈（`backend/app/routers/sessions.py`）；`refined_payload` 列存储草稿（`backend/app/models.py`）。
2. **提取** — `DEFAULT_EXTRACTOR_PIPELINE`（`backend/app/agent/vector/rule_extractor.py`）过滤候选用例：`SafetyWarningFilter`（被阻止关键词 + `X-SQL-LINTER` 标记）、空结果过滤、单步/多步 SQL 提取、澄清轮次拓扑回溯、领域隔离。
3. **精炼** — `refine_sql_case_with_llm`（`backend/app/agent/vector/llm_refiner.py`）重写意图，并对 SQL 参数化/脱敏；结果存储到 `refined_payload`。
4. **批准** — `POST /api/chat/admin/messages/{id}/approve`（`backend/app/routers/admin.py`）允许管理员编辑用例，然后调用 `add_document_to_store` 并传入 `type="sql_example"`；`GET /api/chat/admin/messages/pending` 列出已收集条目。前端：`AdminReviewPanel.vue`。
5. **复用** — `search_saved_correct_tool_uses`（位于 [subagent-sql](../architecture/subagent-sql.md)）检索 `doc_type="sql_example"` 文档，并按当前激活技能限定领域范围。

## 不变量与测试

- `backend/tests/agent/vector/sql_lexicon/test_retriever.py::test_database_lexicon_retriever_retrieve_all`（涵盖所有三层，使用模拟存储）。
- `backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py` — 围绕该检索器的 RAG 中间件集成测试。
- `backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py::test_metadata_lexicon_synchronization` — 词典同步任务。
- `backend/tests/agent/vector/test_skills_meta_whitelists.py` — 词典提取使用的领域 `meta.py` 白名单。

## 变更配方：切换或新增 RAG 后端

1. 在 `backend/app/agent/vector/<backend>/` 中实现 `BaseRetriever`；实现 `retrieve` 和 `aretrieve`。
2. 在 `create_business_retriever_and_reranker`（`factory.py`）中注册后端字符串；保留未知值 → pgvector 的回退。
3. 如果使用 LlamaIndex，请在创建存储之前通过 `embedding_provider.configure_llama_index_settings(settings)` 配置嵌入。
4. 验证：`cd backend && python -m pytest tests/agent/test_retriever_async_contract.py tests/agent/vector -q`。