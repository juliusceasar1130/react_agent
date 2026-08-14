import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.schemas import ChartArtifactResponse
from backend.app.chart_artifacts import get_chart_record
from backend.app.export_files import get_export_record

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/files/{file_id}")
def download_export_file(file_id: str):
    """下载由 export_to_csv 生成的导出文件。

    修改时间: 2026-04-01 00:00 Asia/Shanghai
    修改内容:
    - 新增基于 file_id 的安全下载接口
    - 避免前端暴露服务器绝对路径
    """
    try:
        record = get_export_record(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="导出文件不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="导出文件已过期，请重新导出") from exc

    return FileResponse(
        path=record["stored_path"],
        media_type=record.get("media_type", "application/octet-stream"),
        filename=record.get("filename") or file_id,
    )


@router.get("/charts/{chart_id}", response_model=ChartArtifactResponse)
def get_chart_artifact(chart_id: str):
    """读取图表 artifact，供前端按 chart_id 拉取完整图表配置。"""
    try:
        return get_chart_record(chart_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="图表不存在或已被清理") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=410, detail="图表已过期，请重新生成") from exc
