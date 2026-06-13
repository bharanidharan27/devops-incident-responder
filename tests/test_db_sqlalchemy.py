from app.db import dal


def test_database_url_env_overrides_legacy_db_file(monkeypatch, tmp_path):
    legacy_db = tmp_path / "legacy.db"
    database_url_db = tmp_path / "database-url.db"
    monkeypatch.setattr(dal, "DB_FILE", str(legacy_db))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_url_db.as_posix()}")

    incident_id = dal.record_incident(
        service="payment-service",
        environment="prod",
        severity="HIGH",
        title="DB URL smoke test",
        payload={"source": "database-url"},
    )

    incident = dal.get_incident(incident_id)
    assert incident["payload"] == {"source": "database-url"}
    assert database_url_db.exists()
    assert not legacy_db.exists()
