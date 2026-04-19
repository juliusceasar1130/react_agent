"""图表 artifact 元数据管理。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.config import settings

CHART_ID_PATTERN = re.compile(r"^cht_[a-f0-9]{32}$")


def get_chart_artifact_dir() -> Path:
    """返回图表 artifact 目录。"""
    artifact_dir = Path(settings.chart_artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _metadata_path(chart_id: str) -> Path:
    return get_chart_artifact_dir() / f"{chart_id}.json"


def _validate_chart_id(chart_id: str) -> None:
    if not CHART_ID_PATTERN.fullmatch(chart_id):
        raise ValueError(f"非法 chart_id: {chart_id}")


def _coerce_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _resolve_managed_file(path_str: str) -> Path:
    path = Path(path_str).resolve()
    artifact_dir = get_chart_artifact_dir()
    path.relative_to(artifact_dir)
    return path


def create_chart_record(*, payload: dict[str, Any]) -> dict[str, Any]:
    """为图表 payload 创建 artifact 记录，并返回前端可消费的轻量 ref。"""
    chart_id = f"cht_{uuid4().hex}"
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(hours=settings.chart_artifact_ttl_hours)
    stored_path = _metadata_path(chart_id).resolve()

    record = {
        **payload,
        "chart_id": chart_id,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "stored_path": str(stored_path),
    }

    stored_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "kind": "chart_artifact_ref",
        "chart_id": chart_id,
        "chart_type": payload["chart_type"],
        "title": payload["title"],
        "point_count": len(payload.get("rows", [])),
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "message": "图表已生成，前端可使用 chart_id 拉取完整图表。",
    }


def get_chart_record(chart_id: str) -> dict[str, Any]:
    """读取图表 artifact，并校验路径与有效期。"""
    _validate_chart_id(chart_id)

    metadata_path = _metadata_path(chart_id)
    if not metadata_path.exists():
        raise FileNotFoundError(chart_id)

    record = json.loads(metadata_path.read_text(encoding="utf-8"))
    stored_path = record.get("stored_path")
    if not stored_path:
        raise ValueError(f"图表记录缺少 stored_path: {chart_id}")

    managed_file = _resolve_managed_file(stored_path)
    if not managed_file.exists():
        raise FileNotFoundError(chart_id)

    expires_at = _coerce_datetime(record.get("expires_at"))
    if expires_at is not None and datetime.now(timezone.utc) > expires_at:
        raise TimeoutError(chart_id)

    record["stored_path"] = str(managed_file)
    return record
