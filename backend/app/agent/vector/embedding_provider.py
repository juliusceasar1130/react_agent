"""LlamaIndex Embedding Provider 统一配置入口。

更新时间：2026-03-24 Asia/Shanghai

职责：
  - 根据 .env / settings 构建 Milvus 混合检索使用的 LlamaIndex embedding。
  - 在 Ollama 与 llama.cpp 之间切换，保证初始化入库与运行期检索共用同一套配置。
  - 在 llama.cpp + Qwen3 路径下，对 query 侧启用 instruction-aware 格式。
"""

from __future__ import annotations

import logging
import math
from typing import Any, List, Optional

import httpx
from pydantic import Field, PrivateAttr

from llama_index.core.base.embeddings.base import BaseEmbedding

from backend.app.config import settings

logger = logging.getLogger(__name__)


def _normalize_embedding(vector: List[float]) -> List[float]:
    """对 embedding 做 L2 归一化，便于与 Milvus IP 相似度保持一致。"""
    normalized = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in normalized))
    if norm <= 0:
        return normalized
    return [value / norm for value in normalized]


def _extract_embedding(payload: Any) -> Optional[List[float]]:
    """兼容解析 llama.cpp /embedding 的多种响应形态。"""
    if isinstance(payload, dict):
        if isinstance(payload.get("embedding"), list):
            embedding = payload["embedding"]
            if all(isinstance(item, (int, float)) for item in embedding):
                return [float(item) for item in embedding]
            nested_embedding = _extract_embedding(embedding)
            if nested_embedding is not None:
                return nested_embedding

        for key in ("data", "embeddings", "result"):
            embedding = _extract_embedding(payload.get(key))
            if embedding is not None:
                return embedding

    if isinstance(payload, list):
        if payload and all(isinstance(item, (int, float)) for item in payload):
            return [float(item) for item in payload]

        for item in payload:
            embedding = _extract_embedding(item)
            if embedding is not None:
                return embedding

    return None


def _format_qwen_query(instruction: str, query: str) -> str:
    """按 Qwen 官方推荐格式构造 instruction-aware query。"""
    return f"Instruct: {instruction}\nQuery: {query}"


class LlamaCppEmbedding(BaseEmbedding):
    """基于 llama.cpp `/embedding` 端点的轻量 LlamaIndex embedding 适配器。"""

    base_url: str = Field(description="llama.cpp embedding 服务地址")
    endpoint_path: str = Field(default="/embedding", description="Embedding 接口路径")
    timeout: float = Field(default=30.0, description="请求超时时间（秒）", gt=0)

    _client: httpx.Client = PrivateAttr()
    _async_client: httpx.AsyncClient = PrivateAttr()

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://127.0.0.1:8081",
        endpoint_path: str = "/embedding",
        timeout: float = 30.0,
        embed_batch_size: int = 10,
        callback_manager: Any = None,
        **kwargs: Any,
    ) -> None:
        normalized_base_url = base_url.rstrip("/")
        normalized_endpoint = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"

        super().__init__(
            model_name=model_name,
            base_url=normalized_base_url,
            endpoint_path=normalized_endpoint,
            timeout=float(timeout),
            embed_batch_size=embed_batch_size,
            callback_manager=callback_manager,
            **kwargs,
        )
        timeout_config = httpx.Timeout(self.timeout)
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout_config)
        self._async_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_config,
        )

    @classmethod
    def class_name(cls) -> str:
        return "LlamaCppEmbedding"

    def _request_payload(self, text: str) -> dict[str, Any]:
        return {"content": text}

    def _parse_embedding_response(self, payload: Any) -> List[float]:
        embedding = _extract_embedding(payload)
        if embedding is None:
            raise ValueError(
                "llama.cpp /embedding 返回格式无法识别，未找到 embedding 向量字段"
            )
        return _normalize_embedding(embedding)

    def _post_embedding(self, text: str) -> List[float]:
        try:
            response = self._client.post(
                self.endpoint_path,
                json=self._request_payload(text),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"调用 llama.cpp embedding 接口失败: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("llama.cpp embedding 接口返回了非 JSON 内容") from exc

        return self._parse_embedding_response(payload)

    async def _apost_embedding(self, text: str) -> List[float]:
        try:
            response = await self._async_client.post(
                self.endpoint_path,
                json=self._request_payload(text),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"调用 llama.cpp embedding 接口失败: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("llama.cpp embedding 接口返回了非 JSON 内容") from exc

        return self._parse_embedding_response(payload)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._post_embedding(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return await self._apost_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._post_embedding(text)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await self._apost_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self._post_embedding(text) for text in texts]

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [await self._apost_embedding(text) for text in texts]


class QwenInstructionAwareEmbedding(BaseEmbedding):
    """为 Qwen embedding 提供 query instruction 包装，不影响文档入库文本。"""

    instruction: str = Field(description="Qwen query instruction")

    _base_embedding: BaseEmbedding = PrivateAttr()

    def __init__(
        self,
        base_embedding: BaseEmbedding,
        instruction: str,
        callback_manager: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model_name=base_embedding.model_name,
            embed_batch_size=base_embedding.embed_batch_size,
            callback_manager=callback_manager or base_embedding.callback_manager,
            instruction=instruction,
            **kwargs,
        )
        self._base_embedding = base_embedding

    @classmethod
    def class_name(cls) -> str:
        return "QwenInstructionAwareEmbedding"

    def _get_query_embedding(self, query: str) -> List[float]:
        formatted_query = _format_qwen_query(self.instruction, query)
        return self._base_embedding._get_query_embedding(formatted_query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        formatted_query = _format_qwen_query(self.instruction, query)
        return await self._base_embedding._aget_query_embedding(formatted_query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._base_embedding._get_text_embedding(text)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await self._base_embedding._aget_text_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._base_embedding._get_text_embeddings(texts)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return await self._base_embedding._aget_text_embeddings(texts)


def build_llama_index_embed_model(config: Any = None) -> BaseEmbedding:
    """按配置构建 LlamaIndex embedding 模型实例。"""
    active_config = config or settings
    provider = (getattr(active_config, "embedding_provider", "ollama") or "ollama").strip().lower()

    if provider == "ollama":
        from llama_index.embeddings.ollama import OllamaEmbedding

        model = OllamaEmbedding(
            model_name=getattr(active_config, "ollama_embed_model", "qwen3-embedding:0.6b"),
            base_url=getattr(active_config, "ollama_base_url", "http://localhost:11434"),
            keep_alive=getattr(active_config, "ollama_keep_alive", None),
        )
        logger.info(
            "LlamaIndex Embedding 已构建: provider=ollama, model=%s",
            model.model_name,
        )
        return model

    if provider == "llama_cpp":
        base_embedding = LlamaCppEmbedding(
            model_name=getattr(
                active_config,
                "llama_cpp_embed_model",
                "Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0",
            ),
            base_url=getattr(
                active_config,
                "llama_cpp_embed_base_url",
                "http://127.0.0.1:8081",
            ),
            timeout=getattr(active_config, "llama_cpp_embed_timeout", 30.0),
        )

        if getattr(active_config, "qwen_query_instruction_enabled", True):
            wrapped_embedding = QwenInstructionAwareEmbedding(
                base_embedding=base_embedding,
                instruction=getattr(
                    active_config,
                    "qwen_query_instruction",
                    "Given a web search query, retrieve relevant passages that answer the query",
                ),
            )
            logger.info(
                "LlamaIndex Embedding 已构建: provider=llama_cpp, model=%s, instruction_aware=true",
                base_embedding.model_name,
            )
            return wrapped_embedding

        logger.info(
            "LlamaIndex Embedding 已构建: provider=llama_cpp, model=%s, instruction_aware=false",
            base_embedding.model_name,
        )
        return base_embedding

    raise ValueError(
        f"不支持的 EMBEDDING_PROVIDER='{provider}'，仅支持 ollama | llama_cpp"
    )


def configure_llama_index_settings(config: Any = None) -> BaseEmbedding:
    """统一配置 LlamaIndex 全局 Settings.embed_model。"""
    from llama_index.core import Settings as LISettings

    embed_model = build_llama_index_embed_model(config=config)
    LISettings.embed_model = embed_model

    provider = (
        getattr(config or settings, "embedding_provider", "ollama") or "ollama"
    ).strip().lower()
    logger.info(
        "LlamaIndex Settings.embed_model 配置完成: provider=%s, model=%s",
        provider,
        getattr(embed_model, "model_name", "unknown"),
    )
    return embed_model
