## 1. Implementation
- [x] 1.1 在 `backend/app/config.py` 和 `.env`（可选）中添加 `ollama_embed_model` 相关设定。
- [x] 1.2 在 `backend/app/agent/development/config.py` 中，使用 `OllamaEmbedding` 替换 `NVIDIAEmbedding` 的注册，同时去除 `NVIDIA_API_KEY` 的依赖项。
- [x] 1.3 在 `backend/app/agent/vector/factory.py` 的重配置逻辑流中，实例化 `OllamaEmbedding` 处理 LlamaIndex 全局挂载。
- [x] 1.4 在集成终端运行相关检索程序的调用脚本并验证可用性。
