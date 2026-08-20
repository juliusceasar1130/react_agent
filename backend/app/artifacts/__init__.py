"""工件统一管理模块 (Artifacts Package)。"""
from backend.app.artifacts.schemas import ArtifactKind, ArtifactHandle, BaseArtifactRecord
from backend.app.artifacts.store import ArtifactStore, get_artifact_store

__all__ = [
    "ArtifactKind",
    "ArtifactHandle",
    "BaseArtifactRecord",
    "ArtifactStore",
    "get_artifact_store",
]
