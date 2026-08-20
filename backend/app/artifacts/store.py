# backend/app/artifacts/store.py
"""
统一工件存储与生命周期管理服务 (ArtifactStore)。
整合图表 JSON 配置、CSV 导出文件等物理落盘资源，提供原子写入、TTL 回收、防越权校验与单例生命周期。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from backend.app.config import settings
from backend.app.artifacts.schemas import (
    ArtifactKind,
    ArtifactHandle,
    BaseArtifactRecord,
)

logger = logging.getLogger(__name__)

ARTIFACT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _coerce_datetime(dt_val: Any) -> Optional[datetime]:
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)
    if not isinstance(dt_val, str) or not dt_val.strip():
        return None
    normalized = dt_val.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ArtifactStore:
    """
    统一工件存储服务类。
    管理图表 JSON 配置、CSV 导出文件等物理工件的落盘、检索与生命周期。
    """

    def __init__(self, base_dir: Optional[Path | str] = None) -> None:
        if base_dir is not None:
            self.base_dir = Path(base_dir).resolve()
        else:
            configured_dir = getattr(settings, "artifacts_dir", None)
            if configured_dir:
                self.base_dir = Path(configured_dir).resolve()
            else:
                self.base_dir = Path(tempfile.gettempdir()).resolve() / "sql_agent_artifacts"

        self.charts_dir = self.base_dir / "charts"
        self.exports_dir = self.base_dir / "exports"

        # 维护安全白名单根目录列表（包含主目录及历史配置的兼容目录）
        allowed = [self.base_dir]
        legacy_chart_dir = getattr(settings, "chart_artifact_dir", None)
        if legacy_chart_dir:
            allowed.append(Path(legacy_chart_dir).resolve())
        legacy_export_dir = getattr(settings, "sql_export_dir", None)
        if legacy_export_dir:
            allowed.append(Path(legacy_export_dir).resolve())
        self.allowed_base_dirs: list[Path] = allowed

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保工件各子目录存在。"""
        for d in (self.base_dir, self.charts_dir, self.exports_dir):
            d.mkdir(parents=True, exist_ok=True)

    def _validate_artifact_id(self, artifact_id: str) -> str:
        """校验工件 ID 格式，防御非法字符与路径穿越。"""
        if not ARTIFACT_ID_PATTERN.fullmatch(artifact_id):
            raise ValueError(f"非法 artifact_id: {artifact_id}")
        return artifact_id

    def _metadata_path(self, artifact_id: str) -> Path:
        self._validate_artifact_id(artifact_id)
        if artifact_id.startswith("cht_"):
            primary = self.charts_dir / f"{artifact_id}.json"
            if primary.exists():
                return primary
            # 兼容查找历史 chart 目录
            legacy_chart_dir = getattr(settings, "chart_artifact_dir", None)
            if legacy_chart_dir:
                legacy_p = Path(legacy_chart_dir).resolve() / f"{artifact_id}.json"
                if legacy_p.exists():
                    return legacy_p
            return primary
        elif artifact_id.startswith("exp_"):
            primary = self.exports_dir / f"{artifact_id}.json"
            if primary.exists():
                return primary
            # 兼容查找历史 export 目录
            legacy_export_dir = getattr(settings, "sql_export_dir", None)
            if legacy_export_dir:
                legacy_p = Path(legacy_export_dir).resolve() / f"{artifact_id}.json"
                if legacy_p.exists():
                    return legacy_p
            return primary

        # 兼容无前缀历史工件查找
        cht_path = self.charts_dir / f"{artifact_id}.json"
        if cht_path.exists():
            return cht_path
        exp_path = self.exports_dir / f"{artifact_id}.json"
        if exp_path.exists():
            return exp_path
        return self.charts_dir / f"{artifact_id}.json"

    def _resolve_managed_file(self, path_str: str) -> Path:
        """
        解析并校验文件路径，严格约束在允许的安全工件白名单根目录范围内。
        若路径超出白名单范围，立即抛出 PermissionError 阻止路径越界。
        """
        resolved = Path(path_str).resolve()
        is_safe = False
        for allowed_dir in self.allowed_base_dirs:
            try:
                resolved.relative_to(allowed_dir)
                is_safe = True
                break
            except ValueError:
                continue

        if not is_safe:
            raise PermissionError(f"工件文件路径超出允许的安全目录范围: {resolved}")
        return resolved

    def _atomic_write_text(self, target_path: Path, content: str) -> None:
        """原子写入文本文件 (同卷临时文件 + os.replace)。"""
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = target_dir / f".tmp_{uuid4().hex}_{target_path.name}"
        try:
            tmp_file.write_text(content, encoding="utf-8")
            os.replace(str(tmp_file), str(target_path))
        finally:
            if tmp_file.exists():
                try:
                    tmp_file.unlink(missing_ok=True)
                except Exception:
                    pass

    def save_artifact(
        self,
        *,
        kind: ArtifactKind | str,
        payload: dict[str, Any],
        ttl_hours: Optional[int] = None,
        tool_call_id: Optional[str] = None,
        created_by: Optional[str] = "main",
    ) -> ArtifactHandle:
        """
        保存图表或通用 JSON 工件并返回轻量引用 Handle。
        """
        kind_enum = ArtifactKind(kind) if isinstance(kind, str) else kind
        prefix = "cht" if kind_enum == ArtifactKind.CHART else "art"
        artifact_id = f"{prefix}_{uuid4().hex}"

        ttl = (
            ttl_hours
            if ttl_hours is not None
            else getattr(settings, "artifacts_ttl_hours", getattr(settings, "chart_artifact_ttl_hours", 24))
        )
        created_at_dt = datetime.now(timezone.utc)
        expires_at_dt = created_at_dt + timedelta(hours=ttl)

        metadata_path = self._metadata_path(artifact_id)

        # 同时注入 artifact_id 与 chart_id（兼容旧路由模型校验）
        record_data = {
            **payload,
            "artifact_id": artifact_id,
            "chart_id": artifact_id,
            "kind": kind_enum.value,
            "tool_call_id": tool_call_id,
            "created_by": created_by or "main",
            "created_at": created_at_dt.isoformat(),
            "expires_at": expires_at_dt.isoformat(),
            "stored_path": str(metadata_path.resolve()),
        }

        # 原子写落盘
        self._atomic_write_text(
            metadata_path,
            json.dumps(record_data, ensure_ascii=False, indent=2),
        )

        rows = payload.get("rows", [])
        row_count = len(rows) if isinstance(rows, list) else 0

        columns: list[str] = []
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            columns = list(rows[0].keys())

        return ArtifactHandle(
            artifact_id=artifact_id,
            kind=kind_enum,
            tool_call_id=tool_call_id,
            created_by=created_by or "main",
            summary=f"已生成图表工件 {artifact_id} ({payload.get('chart_type', 'chart')})",
            row_count=row_count,
            col_count=len(columns),
            columns=columns,
            created_at=created_at_dt.isoformat(),
            expires_at=expires_at_dt.isoformat(),
            download_url=f"/api/chat/artifacts/{artifact_id}",
            extra={"chart_type": payload.get("chart_type"), "title": payload.get("title")},
        )

    def save_export_file(
        self,
        *,
        source_file_path: Path | str,
        filename: str,
        media_type: str = "text/csv",
        row_count: int = 0,
        col_count: int = 0,
        columns: Optional[list[str]] = None,
        ttl_hours: Optional[int] = None,
        tool_call_id: Optional[str] = None,
        created_by: Optional[str] = "main",
    ) -> ArtifactHandle:
        """
        保存文件导出工件（复制原始 CSV 文件到托管目录并生成元数据），并清理临时源文件。
        """
        file_id = f"exp_{uuid4().hex}"

        ttl = (
            ttl_hours
            if ttl_hours is not None
            else getattr(settings, "artifacts_ttl_hours", getattr(settings, "sql_export_ttl_hours", 24))
        )
        created_at_dt = datetime.now(timezone.utc)
        expires_at_dt = created_at_dt + timedelta(hours=ttl)

        ext = Path(filename).suffix or ".csv"
        target_file_path = self.exports_dir / f"{file_id}{ext}"

        src_path = Path(source_file_path).resolve()
        if src_path != target_file_path:
            shutil.copy2(src_path, target_file_path)
            # H3: 成功复制后主动删除临时源文件，防止孤儿文件磁盘泄露
            if src_path.exists():
                try:
                    src_path.unlink(missing_ok=True)
                except OSError:
                    pass

        metadata_path = self._metadata_path(file_id)
        size_bytes = target_file_path.stat().st_size if target_file_path.exists() else 0

        record_data = {
            "artifact_id": file_id,
            "kind": ArtifactKind.FILE_EXPORT.value,
            "filename": filename,
            "stored_path": str(target_file_path.resolve()),
            "media_type": media_type,
            "size_bytes": size_bytes,
            "row_count": row_count,
            "col_count": col_count,
            "columns": columns or [],
            "tool_call_id": tool_call_id,
            "created_by": created_by or "main",
            "created_at": created_at_dt.isoformat(),
            "expires_at": expires_at_dt.isoformat(),
        }

        self._atomic_write_text(
            metadata_path,
            json.dumps(record_data, ensure_ascii=False, indent=2),
        )

        return ArtifactHandle(
            artifact_id=file_id,
            kind=ArtifactKind.FILE_EXPORT,
            tool_call_id=tool_call_id,
            created_by=created_by or "main",
            summary=f"已导出文件 {filename} ({row_count} 行)",
            row_count=row_count,
            col_count=col_count,
            columns=columns or [],
            created_at=created_at_dt.isoformat(),
            expires_at=expires_at_dt.isoformat(),
            download_url=f"/api/chat/artifacts/{file_id}/download",
            extra={"size_bytes": size_bytes, "filename": filename},
        )

    def get_artifact(self, artifact_id: str) -> BaseArtifactRecord:
        """
        读取工件元数据，校验存在性、防越权与有效时间 (TTL)。
        """
        self._validate_artifact_id(artifact_id)
        metadata_path = self._metadata_path(artifact_id)

        if not metadata_path.exists():
            raise FileNotFoundError(f"工件元数据不存在: {artifact_id}")

        record_raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        stored_path = record_raw.get("stored_path")
        if not stored_path:
            raise ValueError(f"工件记录缺少 stored_path: {artifact_id}")

        managed_file = self._resolve_managed_file(stored_path)
        if not managed_file.exists():
            raise FileNotFoundError(f"工件物理文件不存在: {artifact_id}")

        expires_at = _coerce_datetime(record_raw.get("expires_at"))
        if expires_at is not None and datetime.now(timezone.utc) > expires_at:
            raise TimeoutError(f"工件已过期: {artifact_id}")

        record_raw["stored_path"] = str(managed_file)
        kind = ArtifactKind(record_raw.get("kind", "chart_spec" if artifact_id.startswith("cht_") else "file_export"))

        return BaseArtifactRecord(
            artifact_id=artifact_id,
            kind=kind,
            tool_call_id=record_raw.get("tool_call_id"),
            created_by=record_raw.get("created_by", "main"),
            created_at=record_raw.get("created_at", datetime.now(timezone.utc).isoformat()),
            expires_at=record_raw.get("expires_at", datetime.now(timezone.utc).isoformat()),
            stored_path=str(managed_file),
            payload=record_raw,
        )

    def cleanup_expired(self) -> int:
        """
        扫描 charts/ 与 exports/ 目录下的所有工件元数据，清理过期及孤儿物理文件。
        针对 Windows 文件占用锁具备容错保护。
        """
        now = datetime.now(timezone.utc)
        cleaned_count = 0

        # 清理残留的 .tmp_* 临时文件 (> 10 分钟前创建)
        for d in (self.charts_dir, self.exports_dir):
            if not d.exists():
                continue
            for tmp_path in d.glob(".tmp_*"):
                try:
                    if tmp_path.is_file() and (now.timestamp() - tmp_path.stat().st_mtime > 600):
                        tmp_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug("清理临时残留文件跳过 %s: %s", tmp_path, e)

        # 清理元数据及关联物理文件
        for d in (self.charts_dir, self.exports_dir):
            if not d.exists():
                continue
            for meta_path in d.glob("*.json"):
                try:
                    meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
                    expires_at = _coerce_datetime(meta_raw.get("expires_at"))
                    if expires_at and now > expires_at:
                        # 删除关联物理文件
                        stored_path = meta_raw.get("stored_path")
                        if stored_path:
                            try:
                                managed_f = self._resolve_managed_file(stored_path)
                                if managed_f.exists() and managed_f != meta_path:
                                    managed_f.unlink(missing_ok=True)
                            except Exception as e:
                                logger.debug("GC 物理文件跳过 %s: %s", stored_path, e)

                        # 删除元数据自身
                        meta_path.unlink(missing_ok=True)
                        cleaned_count += 1
                except Exception as e:
                    logger.debug("GC 扫描元数据失败 %s: %s", meta_path, e)

        return cleaned_count


_global_artifact_store: Optional[ArtifactStore] = None


def get_artifact_store() -> ArtifactStore:
    """获取 ArtifactStore 全局单例。"""
    global _global_artifact_store
    if _global_artifact_store is None:
        _global_artifact_store = ArtifactStore()
    return _global_artifact_store
