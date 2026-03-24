"""Embedding provider 冒烟测试脚本。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from llama_index.core.base.embeddings.base import BaseEmbedding
from pydantic import PrivateAttr

from backend.app.agent.vector.embedding_provider import (
    LlamaCppEmbedding,
    QwenInstructionAwareEmbedding,
    build_llama_index_embed_model,
)


class FakeEmbedding(BaseEmbedding):
    """用于测试 instruction-aware 包装的最小 embedding 实现。"""

    _last_query: str = PrivateAttr(default="")
    _last_text: str = PrivateAttr(default="")

    def _get_query_embedding(self, query: str) -> list[float]:
        self._last_query = query
        return [1.0, 2.0]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        self._last_text = text
        return [3.0, 4.0]

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)


def test_llama_cpp_embedding_normalizes_response() -> None:
    embedding = LlamaCppEmbedding(
        model_name="Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0",
        base_url="http://127.0.0.1:8081",
        timeout=5.0,
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"embedding": [3.0, 4.0]}
    embedding._client = MagicMock()
    embedding._client.post.return_value = mock_response

    vector = embedding.get_text_embedding("hello")

    assert len(vector) == 2
    assert round(vector[0], 4) == 0.6
    assert round(vector[1], 4) == 0.8


def test_llama_cpp_embedding_accepts_nested_response_shape() -> None:
    embedding = LlamaCppEmbedding(
        model_name="Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0",
        base_url="http://127.0.0.1:8081",
        timeout=5.0,
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [
        {
            "index": 0,
            "embedding": [[3.0, 4.0]],
        }
    ]
    embedding._client = MagicMock()
    embedding._client.post.return_value = mock_response

    vector = embedding.get_text_embedding("hello")

    assert len(vector) == 2
    assert round(vector[0], 4) == 0.6
    assert round(vector[1], 4) == 0.8


def test_llama_cpp_embedding_invalid_response_raises_error() -> None:
    embedding = LlamaCppEmbedding(
        model_name="Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0",
        base_url="http://127.0.0.1:8081",
        timeout=5.0,
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"unexpected": "shape"}
    embedding._client = MagicMock()
    embedding._client.post.return_value = mock_response

    try:
        embedding.get_text_embedding("hello")
    except ValueError as exc:
        assert "embedding" in str(exc).lower()
    else:
        raise AssertionError("应当在返回格式非法时抛出 ValueError")


def test_qwen_instruction_aware_embedding_only_wraps_query() -> None:
    base_embedding = FakeEmbedding(model_name="fake-qwen")
    embedding = QwenInstructionAwareEmbedding(
        base_embedding=base_embedding,
        instruction="Given a web search query, retrieve relevant passages that answer the query",
    )

    query_vector = embedding.get_query_embedding("什么是 L3F13?")
    text_vector = embedding.get_text_embedding("L3F13 是一条业务术语。")

    assert query_vector == [1.0, 2.0]
    assert text_vector == [3.0, 4.0]
    assert base_embedding._last_query.startswith("Instruct:")
    assert "什么是 L3F13?" in base_embedding._last_query
    assert base_embedding._last_text == "L3F13 是一条业务术语。"


def test_build_model_dispatches_to_llama_cpp() -> None:
    config = SimpleNamespace(
        embedding_provider="llama_cpp",
        llama_cpp_embed_base_url="http://127.0.0.1:8081",
        llama_cpp_embed_model="Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0",
        llama_cpp_embed_timeout=10.0,
        qwen_query_instruction_enabled=True,
        qwen_query_instruction="Given a web search query, retrieve relevant passages that answer the query",
    )

    embedding = build_llama_index_embed_model(config)

    assert isinstance(embedding, QwenInstructionAwareEmbedding)
    assert embedding.model_name == "Qwen/Qwen3-Embedding-0.6B-GGUF:q8_0"


if __name__ == "__main__":
    test_llama_cpp_embedding_normalizes_response()
    test_llama_cpp_embedding_accepts_nested_response_shape()
    test_llama_cpp_embedding_invalid_response_raises_error()
    test_qwen_instruction_aware_embedding_only_wraps_query()
    test_build_model_dispatches_to_llama_cpp()
    print("Embedding provider tests passed")
