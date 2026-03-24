# Change: Add switchable local Qwen3 embedding providers for Milvus RAG

## Why
当前 Milvus 混合检索已经切换到本地 `Ollama qwen3-embedding:0.6b`，但团队又新增了 `llama.cpp + Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0` 的本地部署方案。为了在不破坏原有 `ollama` 能力的前提下支持新的部署模式，需要将 Milvus 使用的 dense embedding 配置抽象为可切换 provider，并保证初始化入库与运行期查询复用同一套配置。

## What Changes
- 在配置文件中增加 `EMBEDDING_PROVIDER`、`LLAMA_CPP_EMBED_*`、`QWEN_QUERY_INSTRUCTION_*` 等变量支持。
- 新增共享的 LlamaIndex embedding provider 配置模块，在 `ollama` 和 `llama.cpp` 之间按 `.env` 切换。
- `factory.py` 与 `milvus_init/init_store.py` 统一复用共享 provider，保证 Milvus 建库与查询的一致性。
- 在 `llama.cpp` provider 路径中，为 query embedding 启用 Qwen 官方推荐的 instruction-aware 格式。
- 保留 PGVector 使用 `baai/bge-m3` 的既有行为，互不影响。

## Impact
- Affected specs: `rag-backend`
- Affected code: `backend/app/config.py`, `backend/app/agent/vector/embedding_provider.py`, `backend/app/agent/vector/factory.py`, `backend/app/agent/vector/milvus_init/init_store.py`.
