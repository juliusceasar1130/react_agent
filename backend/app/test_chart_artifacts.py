import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.chart_artifacts import create_chart_record, get_chart_record
from backend.app.config import settings


@pytest.fixture()
def chart_artifact_tmp_dir(monkeypatch):
    tmp_path = Path.cwd() / f".tmp_chart_artifacts_{uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    monkeypatch.setattr(settings, "chart_artifact_dir", str(tmp_path))
    monkeypatch.setattr(settings, "chart_artifact_ttl_hours", 24)
    try:
        yield tmp_path
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_create_chart_record_returns_chart_id(chart_artifact_tmp_dir: Path) -> None:
    record = create_chart_record(
        payload={
            "kind": "chart_spec",
            "chart_type": "line",
            "title": "demo",
            "x_field": "stat_date",
            "series": [
                {
                    "name": "count",
                    "field": "detection_count",
                    "y_axis": "left",
                }
            ],
            "rows": [{"stat_date": "2026-04-01", "detection_count": 1}],
        }
    )
    assert record["kind"] == "chart_artifact_ref"
    assert record["chart_id"].startswith("cht_")
    assert record["point_count"] == 1


def test_get_chart_record_returns_full_payload(chart_artifact_tmp_dir: Path) -> None:
    created = create_chart_record(
        payload={
            "kind": "chart_spec",
            "chart_type": "bar",
            "title": "demo",
            "x_field": "model",
            "series": [
                {
                    "name": "count",
                    "field": "detection_count",
                    "y_axis": "left",
                }
            ],
            "rows": [{"model": "A", "detection_count": 10}],
        }
    )
    payload = get_chart_record(created["chart_id"])
    assert payload["kind"] == "chart_spec"
    assert payload["rows"][0]["detection_count"] == 10
