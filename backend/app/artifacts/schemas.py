# backend/app/artifacts/schemas.py
"""
强类型工件数据模型与 Claim-Check 契约声明。

修改时间: 2026-08-18 Asia/Shanghai
主要修改内容:
- 声明统一 ArtifactKind 枚举 (chart_spec, file_export, query_result)
- 声明轻量 ArtifactHandle 句柄与服务端完整 BaseArtifactRecord 存储模型
"""
from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ArtifactKind(str, Enum):
    """工件类型枚举。"""
    CHART = "chart_spec"
    FILE_EXPORT = "file_export"
    QUERY_RESULT = "query_result"


class ArtifactHandle(BaseModel):
    """
    返回给大模型、State 侧信道与前端轻量渲染的统一 Claim-Check 句柄。
    """
    model_config = ConfigDict(from_attributes=True)

    artifact_id: str = Field(..., description="唯一工件ID (如 cht_*, exp_*)")
    kind: ArtifactKind = Field(..., description="工件类型")
    tool_call_id: Optional[str] = Field(None, description="触发生成的工具调用ID")
    created_by: Optional[str] = Field("main", description="产出角色: main 或 subagent_name")
    summary: str = Field("", description="工件业务摘要")
    row_count: int = Field(0, description="数据行数")
    col_count: int = Field(0, description="数据列数")
    columns: List[str] = Field(default_factory=list, description="字段列表")
    created_at: str = Field(..., description="创建时间 (ISO 8601 UTC)")
    expires_at: str = Field(..., description="过期时间 (ISO 8601 UTC)")
    download_url: Optional[str] = Field(None, description="下载或异步拉取相对路径")
    extra: Optional[dict[str, Any]] = Field(None, description="附加轻量元数据")


class BaseArtifactRecord(BaseModel):
    """
    服务端落盘持久化的完整工件记录模型。
    """
    model_config = ConfigDict(from_attributes=True)

    artifact_id: str
    kind: ArtifactKind
    tool_call_id: Optional[str] = None
    created_by: Optional[str] = "main"
    created_at: str
    expires_at: str
    stored_path: str
    payload: dict[str, Any]
