import os

from app.db import dal
from app.runner import process_incident


def use_temp_db(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(dal, "DB_FILE", str(db_file))
    dal.init_db()
    return db_file


def test_incident_creation_is_idempotent_by_external_id(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)

    first = dal.record_incident(
        service="payment-service",
        environment="prod",
        severity="CRITICAL",
        title="Checkout failed",
        alert_type="HTTP 500",
        source="test",
        external_id="alert-1",
        payload={"path": "/checkout"},
    )
    second = dal.record_incident(
        service="payment-service",
        environment="prod",
        severity="CRITICAL",
        external_id="alert-1",
    )

    assert first == second
    incident = dal.get_incident(first)
    assert incident["status"] == "OPEN"
    assert incident["payload"]["path"] == "/checkout"


def test_worker_processes_incident_with_rule_fallback(monkeypatch, tmp_path):
    use_temp_db(monkeypatch, tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "false")

    incident_id = dal.record_incident(
        service="payment-service",
        environment="prod",
        severity="CRITICAL",
        title="Checkout HTTP 500 spike",
        description="HTTP 500 spike on checkout",
        alert_type="HTTP 500",
        source="test",
    )

    report = process_incident(incident_id)

    assert report is not None
    assert dal.get_incident(incident_id)["status"] == "DONE"
    assert dal.get_latest_report(incident_id) is not None
    assert any(step["agent"] == "analyst" for step in dal.list_steps(incident_id))
