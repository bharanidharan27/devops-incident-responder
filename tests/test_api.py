import pytest

from app.db import dal

fastapi_testclient = pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient


def test_api_creates_incident_and_preserves_idempotency(monkeypatch, tmp_path):
    monkeypatch.setattr(dal, "DB_FILE", str(tmp_path / "api.db"))

    from app.api import app

    dal.init_db()
    client = TestClient(app)
    payload = {
        "service": "payment-service",
        "environment": "prod",
        "severity": "CRITICAL",
        "title": "Checkout failures",
        "alert_type": "HTTP 500",
        "source": "pytest",
        "external_id": "api-alert-1",
        "payload": {"path": "/checkout"},
    }

    first = client.post("/api/incidents", json=payload)
    second = client.post("/api/incidents", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_api_reindex_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(dal, "DB_FILE", str(tmp_path / "api.db"))

    from app.api import app

    client = TestClient(app)
    response = client.post("/api/rag/reindex")

    assert response.status_code == 200
    assert response.json()["documents"] >= 1
