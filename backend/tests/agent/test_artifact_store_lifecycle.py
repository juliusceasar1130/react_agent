# backend/tests/agent/test_artifact_store_lifecycle.py
"""
Ticket 01: 统一工件存储管理器 (ArtifactStore) 生命周期与 GC 测试。

验证内容:
1. 强类型模型序列化与反序列化 (ArtifactKind, ArtifactHandle, BaseArtifactRecord)
2. 图表 (chart_spec) 与文件 (file_export) 的持久化落盘与原子写 (temp + os.replace)
3. 路径防越权严格校验与非法 ID 拦截 (H1)
4. 临时 CSV 源文件清理机制 (H3)
5. 图表双 ID (artifact_id + chart_id) 契约兼容 (M1)
6. 惰性过期 (410 / TimeoutError) 判定
7. 周期性 GC (cleanup_expired) 垃圾回收机制与 Windows 占用容错
"""
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.app.artifacts.schemas import ArtifactKind, ArtifactHandle, BaseArtifactRecord
from backend.app.artifacts.store import ArtifactStore


@pytest.fixture
def temp_dir():
    """提供独立的临时工作目录，避免 Windows tmp_path 锁权限问题。"""
    d = tempfile.mkdtemp(prefix="test_artifact_store_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def temp_artifact_store(temp_dir: Path):
    """创建隔离的临时 ArtifactStore 实例。"""
    store = ArtifactStore(base_dir=temp_dir)
    return store


def test_artifact_store_save_and_get_chart(temp_artifact_store: ArtifactStore):
    """验证图表工件保存与读取，同时满足新旧 ID 契约 (M1)。"""
    payload = {
        "chart_type": "line",
        "title": "涂装在制车趋势",
        "description": "按小时统计",
        "x_field": "hour",
        "series": [{"field": "count", "label": "在制量"}],
        "rows": [{"hour": "08:00", "count": 10}, {"hour": "09:00", "count": 15}],
    }
    handle = temp_artifact_store.save_artifact(
        kind=ArtifactKind.CHART,
        payload=payload,
        ttl_hours=24,
        tool_call_id="call_chart_123",
        created_by="sql_domain_agent",
    )

    assert handle.artifact_id.startswith("cht_")
    assert handle.kind == ArtifactKind.CHART
    assert handle.tool_call_id == "call_chart_123"
    assert handle.created_by == "sql_domain_agent"
    assert handle.row_count == 2
    assert handle.columns == ["hour", "count"]

    # 读取工件
    record = temp_artifact_store.get_artifact(handle.artifact_id)
    assert record.artifact_id == handle.artifact_id
    assert record.kind == ArtifactKind.CHART
    assert record.payload["title"] == "涂装在制车趋势"
    assert record.payload["chart_id"] == handle.artifact_id  # 验证 M1
    assert len(record.payload["rows"]) == 2
    assert Path(record.stored_path).exists()


def test_artifact_store_save_and_get_export_file_and_cleanup_src(temp_artifact_store: ArtifactStore, temp_dir: Path):
    """验证 CSV 导出文件工件保存与读取，以及自动清理临时源文件 (H3)。"""
    # 模拟临时生成的 CSV 文件
    csv_file = temp_dir / "temp_export.csv"
    csv_file.write_text("vin,shop,status\nVIN001,PAINT,WIP\nVIN002,ASSY,DONE\n", encoding="utf-8")
    assert csv_file.exists()

    handle = temp_artifact_store.save_export_file(
        source_file_path=csv_file,
        filename="export_vehicles.csv",
        media_type="text/csv",
        row_count=2,
        col_count=3,
        columns=["vin", "shop", "status"],
        ttl_hours=24,
        tool_call_id="call_exp_456",
        created_by="main",
    )

    assert handle.artifact_id.startswith("exp_")
    assert handle.kind == ArtifactKind.FILE_EXPORT
    assert handle.tool_call_id == "call_exp_456"
    assert handle.created_by == "main"
    assert handle.row_count == 2

    # 验证 H3: 临时源文件已被自动删除，防止孤儿文件残留
    assert not csv_file.exists()

    # 读取工件
    record = temp_artifact_store.get_artifact(handle.artifact_id)
    assert record.artifact_id == handle.artifact_id
    assert record.kind == ArtifactKind.FILE_EXPORT
    assert record.payload["filename"] == "export_vehicles.csv"
    assert Path(record.stored_path).exists()
    assert Path(record.stored_path).read_text(encoding="utf-8").startswith("vin,shop")


def test_artifact_store_security_path_validation(temp_artifact_store: ArtifactStore, temp_dir: Path):
    """验证非法 ID 拦截与防越权严格校验 (H1)。"""
    with pytest.raises(ValueError, match="非法 artifact_id"):
        temp_artifact_store.get_artifact("../etc/passwd")

    with pytest.raises(ValueError, match="非法 artifact_id"):
        temp_artifact_store.get_artifact("invalid/id/with/slashes")

    with pytest.raises(FileNotFoundError):
        temp_artifact_store.get_artifact("cht_0123456789abcdef0123456789abcdef")

    # 验证 H1: 针对白名单目录外的越界路径严格抛出 PermissionError
    outside_file = Path(tempfile.gettempdir()) / "outside_sensitive_secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    try:
        with pytest.raises(PermissionError, match="工件文件路径超出允许的安全目录范围"):
            temp_artifact_store._resolve_managed_file(str(outside_file))
    finally:
        outside_file.unlink(missing_ok=True)


def test_artifact_store_expired_timeout(temp_artifact_store: ArtifactStore):
    """验证过期工件抛出 TimeoutError。"""
    payload = {"chart_type": "bar", "title": "过期图表", "rows": []}
    handle = temp_artifact_store.save_artifact(
        kind=ArtifactKind.CHART,
        payload=payload,
        ttl_hours=-1,  # 过去的时间
    )

    with pytest.raises(TimeoutError):
        temp_artifact_store.get_artifact(handle.artifact_id)


def test_artifact_store_cleanup_expired(temp_artifact_store: ArtifactStore, temp_dir: Path):
    """验证定期 GC 清理超期文件，保留未超期文件。"""
    # 1. 创建一个已过期的图表
    expired_handle = temp_artifact_store.save_artifact(
        kind=ArtifactKind.CHART,
        payload={"chart_type": "line", "title": "超期图表", "rows": []},
        ttl_hours=-2,
    )
    # 2. 创建一个有效的图表
    valid_handle = temp_artifact_store.save_artifact(
        kind=ArtifactKind.CHART,
        payload={"chart_type": "bar", "title": "有效图表", "rows": []},
        ttl_hours=24,
    )
    # 3. 创建一个已过期的 CSV 文件
    csv_file = temp_dir / "expired.csv"
    csv_file.write_text("a,b\n1,2\n", encoding="utf-8")
    expired_exp_handle = temp_artifact_store.save_export_file(
        source_file_path=csv_file,
        filename="expired.csv",
        media_type="text/csv",
        row_count=1,
        col_count=2,
        columns=["a", "b"],
        ttl_hours=-1,
    )

    meta_expired_chart = temp_artifact_store._metadata_path(expired_handle.artifact_id)
    meta_valid_chart = temp_artifact_store._metadata_path(valid_handle.artifact_id)
    meta_expired_exp = temp_artifact_store._metadata_path(expired_exp_handle.artifact_id)

    assert meta_expired_chart.exists()
    assert meta_valid_chart.exists()
    assert meta_expired_exp.exists()

    # 执行清理
    cleaned_count = temp_artifact_store.cleanup_expired()
    assert cleaned_count >= 2

    # 验证过期文件已被物理删除
    assert not meta_expired_chart.exists()
    assert not meta_expired_exp.exists()
    # 验证有效文件仍然存在
    assert meta_valid_chart.exists()
