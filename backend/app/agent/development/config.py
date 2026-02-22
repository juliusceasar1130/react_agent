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
from llama_index.embeddings.nvidia import NVIDIAEmbedding

# ──────────────────────────────────────────────
# 1. 加载 .env（override=True 确保本地 .env 优先）
# ──────────────────────────────────────────────
load_dotenv(override=True)

# ──────────────────────────────────────────────
# 2. 环境变量校验（缺 Key 立即报错，避免运行中途崩溃）
# ──────────────────────────────────────────────
_REQUIRED_KEYS = {
    "DEEPSEEK_API_KEY": "DeepSeek LLM",
    "NVIDIA_API_KEY": "NVIDIA Embedding",
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

Settings.embed_model = NVIDIAEmbedding(
    model="nvidia/nv-embedqa-e5-v5",
    api_key=os.getenv("NVIDIA_API_KEY"),
)
print("✅ [config] Embedding 配置完成：nvidia/nv-embedqa-e5-v5")

# ──────────────────────────────────────────────
# 4. 导出常量
# ──────────────────────────────────────────────
EMBED_DIM: int = 1024
"""nvidia/nv-embedqa-e5-v5 的向量维度，创建 Milvus Collection 时需要指定。"""
