"""llama.cpp token 估算器。"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _estimate_fallback_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text))


def _extract_token_count(payload: Any) -> int | None:
    if isinstance(payload, dict):
        for key in ("token_count", "count", "n_tokens", "num_tokens"):
            value = payload.get(key)
            if isinstance(value, int):
                return value

        for key in ("tokens", "ids", "data"):
            value = payload.get(key)
            if isinstance(value, list) and all(isinstance(item, int) for item in value):
                return len(value)
            if isinstance(value, dict):
                token_count = _extract_token_count(value)
                if token_count is not None:
                    return token_count

    if isinstance(payload, list):
        if all(isinstance(item, int) for item in payload):
            return len(payload)
        if len(payload) == 1:
            return _extract_token_count(payload[0])

    if isinstance(payload, int):
        return payload

    return None


class LlamaCppTokenEstimator:
    """通过 llama.cpp `/tokenize` 端点统计 token。"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8089",
        timeout: float = 5.0,
        endpoint_path: str = "/tokenize",
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.timeout = float(timeout)
        self.endpoint_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
        )
        # 失败熔断：tokenize 端点首次不可用后不再重试，后续直接走保守估算
        self._unavailable = False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LlamaCppTokenEstimator":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _request_payload(self, text: str) -> dict[str, Any]:
        return {
            "content": text,
            "add_special": False,
            "parse_special": True,
            "with_pieces": False,
        }

    def _tokenize(self, text: str) -> int | None:
        if self._unavailable:
            return None
        try:
            response = self._client.post(
                self.endpoint_path,
                json=self._request_payload(text),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            if not self._unavailable:
                logger.info(
                    "tokenize 端点不可用（%s），已熔断，后续轮次将直接使用保守估算", exc,
                )
                self._unavailable = True
            return None

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning(
                "llama.cpp tokenize 返回了非 JSON 内容，使用保守估算: %s",
                exc,
            )
            return None

        token_count = _extract_token_count(payload)
        if token_count is None:
            logger.warning(
                "llama.cpp tokenize 返回了无法识别的响应结构，使用保守估算: %s",
                type(payload).__name__,
            )
        return token_count

    def count_text_tokens(self, text: str) -> int:
        if not text:
            return 0

        token_count = self._tokenize(text)
        if token_count is None or token_count <= 0:
            return _estimate_fallback_tokens(text)
        return token_count

    def count_json_like_tokens(self, value: Any) -> int:
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
            except (TypeError, ValueError):
                text = str(value)

        return self.count_text_tokens(text)
