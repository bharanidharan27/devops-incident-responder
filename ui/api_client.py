from typing import Any

import requests


class IncidentApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IncidentApiClient:
    def __init__(self, base_url: str, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def provider_status(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_incidents(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._request("GET", "/api/incidents", params={"limit": limit})

    def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/incidents", json=payload)

    def get_incident(self, incident_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/incidents/{incident_id}")

    def list_steps(self, incident_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/incidents/{incident_id}/steps")

    def get_report(self, incident_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/incidents/{incident_id}/report")

    def run_incident(self, incident_id: int) -> dict[str, Any]:
        return self._request("POST", f"/api/incidents/{incident_id}/run")

    def reindex_rag(self) -> dict[str, Any]:
        return self._request("POST", "/api/rag/reindex")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            **kwargs,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise IncidentApiError(self._error_message(response), status_code=response.status_code)
        return response.json()

    def _error_message(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict) and payload.get("detail"):
            return str(payload["detail"])
        return response.text or f"API request failed with HTTP {response.status_code}"
