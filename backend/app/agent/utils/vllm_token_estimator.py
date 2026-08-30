"""vLLM token 估算器。"""

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
    return max(1, len(text) // 2)


class VllmTokenEstimator:
    """通过 vLLM `/tokenize` 端点统计 token。"""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        timeout: float = 5.0,
        endpoint_path: str = "/tokenize",
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.model_name = model_name
        self.timeout = float(timeout)
        self.endpoint_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
        )
        # 失败熔断：tokenize 端点首次不可用（如部署为 nInfer 无 /tokenize）后不再重试，
        # 后续直接走保守估算，避免每轮多次无效同步 HTTP 往返
        self._unavailable = False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VllmTokenEstimator":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _tokenize(self, payload_kwargs: dict[str, Any]) -> int | None:
        if self._unavailable:
            return None
        try:
            payload = {"model": self.model_name}
            payload.update(payload_kwargs)
            response = self._client.post(
                self.endpoint_path,
                json=payload,
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
            logger.warning("vLLM tokenize 返回了非 JSON 内容，使用保守估算: %s", exc)
            return None

        token_count = payload.get("count")
        if not isinstance(token_count, int):
            logger.warning("vLLM tokenize 返回了无法识别的 count 字段: %s", token_count)
            return None

        return token_count

    def count_text_tokens(self, text: str) -> int:
        if not text:
            return 0

        token_count = self._tokenize({"prompt": text})
        if token_count is None or token_count <= 0:
            return _estimate_fallback_tokens(text)
        return token_count

    def count_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        if not messages:
            return 0

        token_count = self._tokenize({"messages": messages})
        if token_count is None or token_count <= 0:
            return _estimate_fallback_tokens(str(messages))
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
