import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import router
from backend.app.chart_artifacts import create_chart_record
from backend.app.config import settings


@pytest.fixture()
def chart_api_tmp_dir(monkeypatch):
    tmp_path = Path.cwd() / f".tmp_chart_api_{uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    monkeypatch.setattr(settings, "chart_artifact_dir", str(tmp_path))
    monkeypatch.setattr(settings, "chart_artifact_ttl_hours", 24)
    try:
        yield tmp_path
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def chart_record(chart_api_tmp_dir: Path):
    return create_chart_record(
        payload={
            "kind": "chart_spec",
            "chart_type": "line",
            "title": "demo",
            "description": "demo",
            "x_field": "stat_date",
            "series": [{"name": "count", "field": "detection_count", "y_axis": "left"}],
            "rows": [{"stat_date": "2026-04-01", "detection_count": 1}],
        }
    )


def test_get_chart_endpoint_returns_chart_payload(
    client: TestClient,
    chart_record: dict,
) -> None:
    response = client.get(f"/api/chat/charts/{chart_record['chart_id']}")
    assert response.status_code == 200
    assert response.json()["kind"] == "chart_spec"
    assert response.json()["chart_id"] == chart_record["chart_id"]
