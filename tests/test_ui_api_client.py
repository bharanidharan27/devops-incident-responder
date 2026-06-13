import pytest

from ui.api_client import IncidentApiClient, IncidentApiError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_api_client_uses_expected_fastapi_routes(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        if url.endswith("/health"):
            return FakeResponse(payload={"status": "ok", "ai": {"models": []}})
        if url.endswith("/api/incidents") and method == "GET":
            return FakeResponse(payload=[{"id": 7, "service": "payment-service"}])
        if url.endswith("/api/incidents") and method == "POST":
            return FakeResponse(payload={"id": 8, **kwargs["json"]})
        if url.endswith("/api/incidents/7/run"):
            return FakeResponse(payload={"status": "processed", "incident_id": 7})
        if url.endswith("/api/rag/reindex"):
            return FakeResponse(payload={"backend": "json-vector", "documents": 3})
        raise AssertionError(f"unexpected request: {method} {url}")

    client = IncidentApiClient("http://api.internal/base/")
    monkeypatch.setattr(client.session, "request", fake_request)

    assert client.provider_status()["status"] == "ok"
    assert client.list_incidents(limit=25)[0]["id"] == 7
    assert client.create_incident({"service": "payment-service"})["id"] == 8
    assert client.run_incident(7)["incident_id"] == 7
    assert client.reindex_rag()["documents"] == 3

    assert calls == [
        {"method": "GET", "url": "http://api.internal/base/health", "timeout": 15},
        {
            "method": "GET",
            "url": "http://api.internal/base/api/incidents",
            "params": {"limit": 25},
            "timeout": 15,
        },
        {
            "method": "POST",
            "url": "http://api.internal/base/api/incidents",
            "json": {"service": "payment-service"},
            "timeout": 15,
        },
        {"method": "POST", "url": "http://api.internal/base/api/incidents/7/run", "timeout": 15},
        {"method": "POST", "url": "http://api.internal/base/api/rag/reindex", "timeout": 15},
    ]


def test_api_client_raises_readable_error_for_api_failure(monkeypatch):
    client = IncidentApiClient("http://api.internal")
    monkeypatch.setattr(
        client.session,
        "request",
        lambda *args, **kwargs: FakeResponse(status_code=500, payload={"detail": "database unavailable"}),
    )

    with pytest.raises(IncidentApiError, match="database unavailable"):
        client.list_incidents()
