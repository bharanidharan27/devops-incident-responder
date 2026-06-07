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


def test_alertmanager_webhook_creates_incident(monkeypatch, tmp_path):
    monkeypatch.setattr(dal, "DB_FILE", str(tmp_path / "api.db"))

    import app.api as api_module
    from app.api import app

    monkeypatch.setattr(api_module, "WEBHOOK_AUTO_PROCESS", False)
    dal.init_db()
    client = TestClient(app)
    payload = {
        "version": "4",
        "groupKey": "{}:{alertname='CheckoutHighErrorRate'}",
        "status": "firing",
        "receiver": "devops-incident-responder",
        "commonLabels": {
            "alertname": "CheckoutHighErrorRate",
            "service": "payment-service",
            "environment": "prod",
            "severity": "critical",
            "cloudwatch_log_group": "/devops-incident-responder/payment-service",
            "cloudwatch_log_stream_prefix": "demo",
        },
        "commonAnnotations": {
            "summary": "Checkout HTTP 500 spike",
            "description": "Prometheus detected checkout errors.",
        },
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "CheckoutHighErrorRate"},
                "annotations": {},
                "startsAt": "2026-06-07T10:00:00Z",
                "fingerprint": "alertmanager-test-1",
            }
        ],
    }

    response = client.post("/api/webhooks/alertmanager", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    incident = dal.get_incident(body["created"][0]["incident_id"])
    assert incident["source"] == "alertmanager"
    assert incident["payload"]["cloudwatch_log_group"] == "/devops-incident-responder/payment-service"
