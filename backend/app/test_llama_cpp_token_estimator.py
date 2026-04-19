from __future__ import annotations

import httpx
import importlib
from unittest.mock import MagicMock

from backend.app.agent.utils.llama_cpp_token_estimator import (
    LlamaCppTokenEstimator,
)


def test_estimator_supports_context_manager_and_close() -> None:
    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5.0,
    )
    estimator._client.close()
    estimator._client = MagicMock()

    with estimator as managed:
        assert managed is estimator

    estimator._client.close.assert_called_once()


def test_count_text_tokens_uses_llama_cpp_tokenize() -> None:
    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5.0,
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"tokens": [1, 2, 3, 4]}
    estimator._client.close()
    estimator._client = MagicMock()
    estimator._client.post.return_value = mock_response

    token_count = estimator.count_text_tokens("hello world")

    assert token_count == 4
    estimator._client.post.assert_called_once_with(
        "/tokenize",
        json={
            "content": "hello world",
            "add_special": False,
            "parse_special": True,
            "with_pieces": False,
        },
    )


def test_count_text_tokens_falls_back_when_tokenize_fails() -> None:
    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5.0,
    )
    estimator._client.close()
    estimator._client = MagicMock()
    estimator._client.post.side_effect = httpx.ConnectError("boom")

    token_count = estimator.count_text_tokens("hello")

    assert token_count == 5


def test_count_json_like_tokens_handles_dict_and_list() -> None:
    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5.0,
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"tokens": [1, 2, 3]}
    estimator._client.close()
    estimator._client = MagicMock()
    estimator._client.post.return_value = mock_response

    token_count = estimator.count_json_like_tokens(
        {
            "name": "agent",
            "items": [1, {"nested": True}],
        }
    )

    assert token_count > 0


def test_count_text_tokens_falls_back_for_unknown_list_shape(caplog) -> None:
    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5.0,
    )
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [{"unexpected": True}]
    estimator._client.close()
    estimator._client = MagicMock()
    estimator._client.post.return_value = mock_response

    with caplog.at_level("WARNING"):
        token_count = estimator.count_text_tokens("hello")

    assert token_count == 5
    assert any("无法识别的响应结构" in record.message for record in caplog.records)


def test_unexpected_runtime_error_is_not_swallowed() -> None:
    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5.0,
    )
    estimator._client.close()
    estimator._client = MagicMock()
    estimator._client.post.side_effect = RuntimeError("boom")

    try:
        estimator.count_text_tokens("hello")
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("unexpected RuntimeError should not be swallowed")


def test_settings_include_llama_cpp_token_estimator_options(monkeypatch) -> None:
    monkeypatch.setenv("LLM_CONTEXT_WARNING_ENABLED", "false")
    monkeypatch.setenv("LLM_CONTEXT_WINDOW", "16384")
    monkeypatch.setenv("LLM_CONTEXT_WARN_TOKENS", "12000")
    monkeypatch.setenv("LLM_CONTEXT_SAFETY_BUFFER", "512")
    monkeypatch.setenv("LLAMA_CPP_TOKENIZE_BASE_URL", "http://127.0.0.1:8089")
    monkeypatch.setenv("LLM_CONTEXT_TOKENIZER_TIMEOUT", "5")

    import backend.app.config as config_module

    config_module = importlib.reload(config_module)
    settings = config_module.Settings(_env_file=None)

    assert settings.llm_context_warning_enabled is False
    assert settings.llm_context_window == 16384
    assert settings.llm_context_warn_tokens == 12000
    assert settings.llm_context_safety_buffer == 512
    assert settings.llama_cpp_tokenize_base_url == "http://127.0.0.1:8089"
    assert settings.llm_context_tokenizer_timeout == 5.0


if __name__ == "__main__":
    test_estimator_supports_context_manager_and_close()
    test_count_text_tokens_uses_llama_cpp_tokenize()
    test_count_text_tokens_falls_back_when_tokenize_fails()
    test_count_json_like_tokens_handles_dict_and_list()
    test_count_text_tokens_falls_back_for_unknown_list_shape()
    test_unexpected_runtime_error_is_not_swallowed()
    test_settings_include_llama_cpp_token_estimator_options()
    print("llama.cpp token estimator tests passed")
