# backend/app/routers/artifacts.py
"""
统一工件 REST API 路由。

修改时间: 2026-08-20 Asia/Shanghai
主要修改内容:
- 接入统一 ArtifactStore 单例
- 提供统一的 /artifacts/{artifact_id} 与 /artifacts/{artifact_id}/download 端点
- 历史兼容路由 /charts/{chart_id} 与 /files/{file_id} 直接直连 ArtifactStore，彻底移除历史垫片
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.artifacts import get_artifact_store
from backend.app.schemas import ChartArtifactResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/artifacts/{artifact_id}")
def get_artifact_metadata(artifact_id: str):
    """
    统一工件元数据与内容查询端点。
    返回图表配置 (chart_spec) 或文件元数据 (file_export)，并脱敏剥离服务器物理路径 (stored_path)。
    """
    store = get_artifact_store()
    try:
        record = store.get_artifact(artifact_id)
        payload = dict(record.payload) if record.payload else {}
        payload.pop("stored_path", None)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="工件不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="工件已过期，请重新生成") from exc


@router.get("/artifacts/{artifact_id}/download")
def download_artifact_file(artifact_id: str):
    """
    统一工件物理文件下载端点。
    适用于 CSV、数据报表等流式文件下载。
    """
    store = get_artifact_store()
    try:
        record = store.get_artifact(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="导出文件不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="导出文件已过期，请重新导出") from exc

    payload = record.payload or {}
    filename = payload.get("filename") or f"{artifact_id}.csv"
    media_type = payload.get("media_type") or "application/octet-stream"

    return FileResponse(
        path=record.stored_path,
        media_type=media_type,
        filename=filename,
    )


# ==============================================================================
# 向下兼容历史路由 (Backward Compatibility)
# ==============================================================================

@router.get("/files/{file_id}")
def download_export_file(file_id: str):
    """向后兼容 /api/chat/files/{file_id} 历史端点，直连 ArtifactStore。"""
    store = get_artifact_store()
    try:
        record = store.get_artifact(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="导出文件不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="导出文件已过期，请重新导出") from exc

    payload = record.payload or {}
    filename = payload.get("filename") or file_id
    media_type = payload.get("media_type") or "application/octet-stream"

    return FileResponse(
        path=record.stored_path,
        media_type=media_type,
        filename=filename,
    )


@router.get("/charts/{chart_id}", response_model=ChartArtifactResponse)
def get_chart_artifact(chart_id: str):
    """向后兼容 /api/chat/charts/{chart_id} 历史端点，直连 ArtifactStore 并脱敏。"""
    store = get_artifact_store()
    try:
        record = store.get_artifact(chart_id)
        payload = dict(record.payload) if record.payload else {}
        payload.pop("stored_path", None)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="图表不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="图表已过期，请重新生成") from exc
