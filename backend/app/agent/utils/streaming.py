"""
流式事件辅助工具。

修改时间: 2026-03-27 17:10 Asia/Shanghai
主要修改内容:
- 新增 LangGraph custom stream 状态事件写入辅助函数
- 在无 stream writer 上下文时安全降级为空操作
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def emit_stream_event(event: dict[str, Any]) -> None:
    """向 LangGraph custom stream 写入事件；无上下文时静默跳过。"""
    try:
        from langgraph.config import get_stream_writer
    except Exception:
        return

    try:
        writer = get_stream_writer()
    except Exception:
        return

    if writer is None:
        return

    try:
        writer(event)
    except Exception as exc:
        logger.debug("写入 custom stream 事件失败: %s", exc)


def emit_stream_status(
    text: str,
    *,
    stage: str,
    source: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
) -> None:
    """写入标准化 status 事件。"""
    payload: dict[str, Any] = {"type": "status", "stage": stage, "text": text}
    if source:
        payload["source"] = source
    if detail:
        payload["detail"] = detail
    emit_stream_event(payload)
