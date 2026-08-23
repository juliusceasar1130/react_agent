---
type: Domain
title: "RAG & DB Lexicon Retrieval"
description: "Dual-backend retrieval (pgvector / Milvus hybrid) with optional NVIDIA rerank, the three-layer database lexicon (table DDL, dedup column values, row entities), and the feedback-driven golden-case pipeline."
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

# RAG & DB Lexicon Retrieval

`backend/app/agent/vector/` implements retrieval-augmented generation for the agent, wired through [BusinessRagMiddleware](../architecture/middleware-pipeline.md). Package docs: `backend/app/agent/vector/readme.md`; deeper design notes in `docs/llamaindex_rag/` and `docs/RAG开发包development/`.

## Backends (factory)

`create_business_retriever_and_reranker()` in `backend/app/agent/vector/factory.py` is the single seam:

| `settings.rag_backend` | Retriever | Notes |
|---|---|---|
| `pgvector` (default) | `PgVectorDocumentationRetriever` over `rag_store` (collection on `DATABASE_URL`, `baai/bge-m3`) | Synchronous store |
| `milvus_hybrid` | `MilvusHybridRetriever` (LlamaIndex + Dense + BM25 + RRF, RRF k via `MILVUS_RRF_K`) | Lazy connection; embedding provider via `embedding_provider.py` (`EMBEDDING_PROVIDER` = `ollama` or `llama_cpp` Qwen3) |
| unknown value | falls back to pgvector | logged warning |

- Optional reranker: `NvidiaReranker` (`backend/app/agent/vector/rerank/`) when `RERANK_ENABLED=true` (`nvidia/rerank-qa-mistral-4b` by default).
- `add_document_to_store(text, metadata)` writes golden SQL cases into whichever backend is active — this is the sink for the feedback pipeline below.
- Async contract: `BaseRetriever` defines `aretrieve` defaulting to `retrieve`; concrete retrievers must implement it — verified by `backend/tests/agent/test_retriever_async_contract.py` (`test_milvus_hybrid_retriever_has_aretrieve`, `test_pgvector_retriever_has_aretrieve`).

## Three-layer DB lexicon

`DatabaseLexiconRetriever` (`backend/app/agent/vector/sql_lexicon/retriever.py`) holds three Milvus collections, each a hybrid LlamaIndex index:

1. `table_schema_store` — table DDL skeletons (populated from the live schema, see `sql_lexicon/pipeline/`).
2. `db_value_lexicon` — deduplicated column values.
3. `db_row_lexicon` — row-level physical value alignment.

`retrieve_all(query)` runs the three lookups concurrently with per-layer exception isolation, returning `{"tables": [...], "values": [...], "rows": [...]}`. `BusinessRagMiddleware` calls it in the same round as document retrieval and writes the result into `RequestContext.lexicon_context` (see [state-and-context](../architecture/state-and-context.md)); the LLM-facing lexicon tools ([subagent-sql](../architecture/subagent-sql.md)) use the same retriever on demand.

Startup sync: when `settings.db_lexicon_sync_on_startup` is true, `backend/app/main.py` triggers `start_metadata_lexicon_sync_async` (from `sql_lexicon/tasks.py`) during app lifespan.

## Feedback-driven golden-case pipeline

This is the "self-evolving few-shot" loop:

1. **Collect** — frontend 👍/👎/⭐ buttons submit feedback via `POST /api/chat/messages/{id}/feedback` (`backend/app/routers/sessions.py`); `refined_payload` column stores drafts (`backend/app/models.py`).
2. **Extract** — `DEFAULT_EXTRACTOR_PIPELINE` (`backend/app/agent/vector/rule_extractor.py`) filters candidate cases: `SafetyWarningFilter` (blocked keywords + `X-SQL-LINTER` markers), empty-result filtering, single/multi-step SQL extraction, clarification-turn topology back-tracing, domain isolation.
3. **Refine** — `refine_sql_case_with_llm` (`backend/app/agent/vector/llm_refiner.py`) rewrites the intent and parameterizes/desensitizes the SQL; result stored to `refined_payload`.
4. **Approve** — `POST /api/chat/admin/messages/{id}/approve` (`backend/app/routers/admin.py`) lets an admin edit the case, then calls `add_document_to_store` with `type="sql_example"`; `GET /api/chat/admin/messages/pending` lists collected items. Frontend: `AdminReviewPanel.vue`.
5. **Reuse** — `search_saved_correct_tool_uses` (in [subagent-sql](../architecture/subagent-sql.md)) retrieves `doc_type="sql_example"` documents, domain-scoped by the active skill.

## Invariants & tests

- `backend/tests/agent/vector/sql_lexicon/test_retriever.py::test_database_lexicon_retriever_retrieve_all` (all three layers, mocked store).
- `backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py` — RAG middleware integration around this retriever.
- `backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py::test_metadata_lexicon_synchronization` — lexicon sync task.
- `backend/tests/agent/vector/test_skills_meta_whitelists.py` — domain `meta.py` whitelists used by lexicon extraction.

## Change recipe: switch or add a RAG backend

1. Implement `BaseRetriever` in `backend/app/agent/vector/<backend>/`; implement both `retrieve` and `aretrieve`.
2. Register the backend string in `create_business_retriever_and_reranker` (`factory.py`); keep the unknown-value → pgvector fallback.
3. If it uses LlamaIndex, configure embeddings through `embedding_provider.configure_llama_index_settings(settings)` before store creation.
4. Validate: `cd backend && python -m pytest tests/agent/test_retriever_async_contract.py tests/agent/vector -q`.
