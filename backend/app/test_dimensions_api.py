"""Tests for GET /api/chat/dimensions/{table_name}

修改时间: 2026-05-20
修改内容: 移除 source 字段断言（已删除 Mock 降级），白名单从 .env DIMENSION_TABLES 读取
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_dimensions_whitelisted_table_returns_200():
    resp = client.get("/api/chat/dimensions/process_areas")
    assert resp.status_code == 200
    data = resp.json()
    assert data["table_name"] == "process_areas"
    assert isinstance(data["columns"], list)
    assert isinstance(data["rows"], list)
    assert "row_count" in data
    assert len(data["rows"]) > 0


def test_dimensions_non_whitelisted_table_returns_400():
    resp = client.get("/api/chat/dimensions/vehicle_tracking")
    assert resp.status_code == 400
    assert "not in the dimension whitelist" in resp.json()["detail"]


def test_dimensions_all_five_tables():
    for name in [
        "carrier_types", "process_areas", "vehicle_body_types",
        "vehicle_color_codes", "vehicle_platforms",
    ]:
        resp = client.get(f"/api/chat/dimensions/{name}")
        assert resp.status_code == 200, f"{name} failed: {resp.status_code}"
        data = resp.json()
        assert len(data["columns"]) > 0
