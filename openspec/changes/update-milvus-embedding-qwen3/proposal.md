# Change: Replace Milvus Embedding with local Qwen3-Embedding:0.6b

## Why
目前由于 Milvus 混合检索后端依赖云端的 NVIDIA `nv-embedqa-e5-v5` 来提供向量化支持，导致应用具有高昂的 API 调用成本、外网网络延迟以及潜在的业务数据泄露隐私风险。我们希望将其替换为通过本地 Ollama 框架运行的 `qwen3-embedding:0.6b`。更换后，系统能在保持同级别 1024 维度的前提下，充分利用本地 GPU（RTX 5090）的高容限上下文算力，从而实现真正的零延迟与降本增效。

## What Changes
- 在配置文件中增加本地 Ollama Embedding 的控制台变量支持。
- 替换由于 `factory.py` 中 `_configure_llama_index_settings` 和 `development/config.py` 引用的 `NVIDIAEmbedding`，转而使用 LlamaIndex 的 `OllamaEmbedding`。
- 保留 `baai/bge-m3` 在 PGVector 中通过直连挂载的能力，实现互不干扰。

## Impact
- Affected specs: `rag-backend`
- Affected code: `backend/app/config.py`, `backend/app/agent/development/config.py`, `backend/app/agent/vector/factory.py`.
