## 1. Implementation
- [x] 1.1 在 `backend/app/config.py` 和 `.env` 中添加 `EMBEDDING_PROVIDER`、`LLAMA_CPP_EMBED_*`、`QWEN_QUERY_INSTRUCTION_*` 设定。
- [x] 1.2 新增共享 embedding provider 模块，支持 `ollama` 与 `llama.cpp` 两种本地 provider。
- [x] 1.3 在 `backend/app/agent/vector/factory.py` 中统一通过共享 provider 配置 LlamaIndex 全局 embedding。
- [x] 1.4 在 `backend/app/agent/vector/milvus_init/init_store.py` 中复用同一 provider，保证建库与查询一致。
- [x] 1.5 补充测试脚本，验证 provider 分发、`llama.cpp` 解析归一化以及 Milvus 延迟初始化路径。
- [x] 1.6 更新 README、changelog 与 `llama.cpp` 部署文档，说明切换配置和重建索引要求。
