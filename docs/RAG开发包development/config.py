"""
development/config.py
=====================
全局模型配置模块（import 即生效）

职责：
  1. 加载 .env 环境变量
  2. 校验必要的 API Key，缺失时快速失败
  3. 配置 LlamaIndex 全局 Settings（LLM + Embedding）
  4. 导出常量（EMBED_DIM）

使用方式：
    import development.config          # 在任何模块顶部 import，确保 Settings 已配置
    from development.config import EMBED_DIM
"""

import os
from dotenv import load_dotenv

from llama_index.core import Settings
from llama_index.llms.deepseek import DeepSeek
from llama_index.embeddings.ollama import OllamaEmbedding

# ──────────────────────────────────────────────
# 1. 加载 .env（override=True 确保本地 .env 优先）
# ──────────────────────────────────────────────
load_dotenv(override=True)

# ──────────────────────────────────────────────
# 2. 环境变量校验（缺 Key 立即报错，避免运行中途崩溃）
# ──────────────────────────────────────────────
_REQUIRED_KEYS = {
    "DEEPSEEK_API_KEY": "DeepSeek LLM",
}
_missing = [f"{k} ({desc})" for k, desc in _REQUIRED_KEYS.items() if not os.getenv(k)]
if _missing:
    raise EnvironmentError(
        "\n❌ 缺少必要的 API Key，请检查 .env 文件：\n  - " + "\n  - ".join(_missing)
    )
print("✅ [config] API Key 校验通过")

# ──────────────────────────────────────────────
# 3. 全局模型配置（LlamaIndex Settings 为全局单例）
# ──────────────────────────────────────────────
Settings.llm = DeepSeek(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
)
print("✅ [config] LLM 配置完成：deepseek-chat")

Settings.embed_model = OllamaEmbedding(
    model_name=os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
)
print(f"✅ [config] Embedding 配置完成：{Settings.embed_model.model_name}")

# ──────────────────────────────────────────────
# 4. 导出常量
# ──────────────────────────────────────────────
EMBED_DIM: int = 1024
"""Ollama qwen3-embedding:0.6b 的向量维度，创建 Milvus Collection 时需要指定。"""
