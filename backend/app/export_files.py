"""
导出文件元数据管理

修改时间: 2026-04-01 00:00 Asia/Shanghai
主要修改内容:
- 新增 SQL 导出文件元数据落盘与读取能力
- 为前端下载接口提供 file_id -> 文件路径 的安全解析
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.config import settings

FILE_ID_PATTERN = re.compile(r"^exp_[a-f0-9]{32}$")


def get_export_dir() -> Path:
    """返回导出文件目录。"""
    export_dir = Path(settings.sql_export_dir).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _metadata_path(file_id: str) -> Path:
    return get_export_dir() / f"{file_id}.json"


def _validate_file_id(file_id: str) -> None:
    if not FILE_ID_PATTERN.fullmatch(file_id):
        raise ValueError(f"非法 file_id: {file_id}")


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
    export_dir = get_export_dir()
    path.relative_to(export_dir)
    return path


def create_export_record(
    *,
    file_path: str | Path,
    filename: str,
    media_type: str,
    row_count: int,
    col_count: int,
    columns: list[str],
) -> dict[str, Any]:
    """为已落盘的导出文件创建元数据记录，并返回前端可消费的结构化结果。"""
    managed_file = _resolve_managed_file(str(file_path))
    file_id = f"exp_{uuid4().hex}"
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(hours=settings.sql_export_ttl_hours)

    record = {
        "kind": "file_export",
        "file_id": file_id,
        "filename": filename,
        "stored_path": str(managed_file),
        "media_type": media_type,
        "size_bytes": managed_file.stat().st_size,
        "row_count": row_count,
        "col_count": col_count,
        "columns": columns,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    metadata_path = _metadata_path(file_id)
    metadata_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return record


def get_export_record(file_id: str) -> dict[str, Any]:
    """读取导出文件元数据，并校验文件路径与有效期。"""
    _validate_file_id(file_id)

    metadata_path = _metadata_path(file_id)
    if not metadata_path.exists():
        raise FileNotFoundError(file_id)

    record = json.loads(metadata_path.read_text(encoding="utf-8"))
    stored_path = record.get("stored_path")
    if not stored_path:
        raise ValueError(f"导出记录缺少 stored_path: {file_id}")

    managed_file = _resolve_managed_file(stored_path)
    if not managed_file.exists():
        raise FileNotFoundError(file_id)

    expires_at = _coerce_datetime(record.get("expires_at"))
    if expires_at is not None and datetime.now(timezone.utc) > expires_at:
        raise TimeoutError(file_id)

    record["stored_path"] = str(managed_file)
    return record
