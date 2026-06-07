from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from app.config import WEBHOOK_AUTO_PROCESS
from app.db.dal import (
    get_incident,
    get_latest_report,
    init_db,
    list_incidents,
    list_steps,
    mark_open,
    record_incident,
)
from app.models import IncidentCreate, IncidentResponse
from app.rag.service import RagService
from app.runner import process_incident
from app.services.ai_client import AIClient

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="DevOps Incident Responder", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "ai": AIClient().provider_status()}


@app.post("/api/incidents", response_model=IncidentResponse)
def create_incident(request: IncidentCreate) -> dict[str, object]:
    incident_id = record_incident(
        status="OPEN",
        service=request.service,
        environment=request.environment,
        severity=request.severity,
        title=request.title,
        description=request.description,
        alert_type=request.alert_type,
        source=request.source,
        external_id=request.external_id,
        payload=request.payload,
    )
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=500, detail="Incident was not created")
    return incident


@app.get("/api/incidents")
def incidents(limit: int = 200) -> list[dict[str, object]]:
    return list_incidents(limit=limit)


@app.get("/api/incidents/{incident_id}", response_model=IncidentResponse)
def incident_detail(incident_id: int) -> dict[str, object]:
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/api/incidents/{incident_id}/steps")
def incident_steps(incident_id: int) -> list[dict[str, object]]:
    if not get_incident(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    return list_steps(incident_id)


@app.get("/api/incidents/{incident_id}/report")
def incident_report(incident_id: int) -> dict[str, object]:
    if not get_incident(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    report = get_latest_report(incident_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.post("/api/incidents/{incident_id}/run")
def run_incident(incident_id: int) -> dict[str, object]:
    if not get_incident(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    mark_open(incident_id)
    report = process_incident(incident_id)
    if not report:
        raise HTTPException(status_code=500, detail="Incident processing failed")
    return {"status": "processed", "incident_id": incident_id, "report": report}


@app.post("/api/rag/reindex")
def reindex_rag() -> dict[str, object]:
    return RagService().reindex()


@app.post("/api/webhooks/alertmanager")
def alertmanager_webhook(payload: dict[str, Any]) -> dict[str, object]:
    alerts = payload.get("alerts") or []
    if not isinstance(alerts, list):
        raise HTTPException(status_code=400, detail="Alertmanager payload must include alerts[]")

    created: list[dict[str, object]] = []
    for index, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            continue
        if (alert.get("status") or payload.get("status")) == "resolved":
            continue

        incident_id = _record_alertmanager_alert(payload, alert, index)
        report = process_incident(incident_id) if WEBHOOK_AUTO_PROCESS else None
        created.append(
            {
                "incident_id": incident_id,
                "auto_processed": WEBHOOK_AUTO_PROCESS,
                "report_generated": report is not None,
            }
        )

    return {"status": "accepted", "created": created, "count": len(created)}


def _record_alertmanager_alert(payload: dict[str, Any], alert: dict[str, Any], index: int) -> int:
    labels = {
        **_dict(payload.get("commonLabels")),
        **_dict(alert.get("labels")),
    }
    annotations = {
        **_dict(payload.get("commonAnnotations")),
        **_dict(alert.get("annotations")),
    }
    payload_details = {
        "alertmanager": {
            "receiver": payload.get("receiver"),
            "groupKey": payload.get("groupKey"),
            "externalURL": payload.get("externalURL"),
            "alert": alert,
        },
        **_cloudwatch_overrides(labels, annotations),
    }
    severity = str(labels.get("severity") or "UNKNOWN").upper()
    external_id = (
        alert.get("fingerprint")
        or labels.get("fingerprint")
        or f"alertmanager:{payload.get('groupKey', 'group')}:{labels.get('alertname', 'alert')}:{alert.get('startsAt', index)}"
    )
    return record_incident(
        status="OPEN",
        service=labels.get("service") or labels.get("job") or labels.get("app") or "unknown",
        environment=labels.get("environment") or labels.get("namespace") or "prod",
        severity=severity,
        title=annotations.get("summary") or labels.get("alertname") or "Alertmanager alert",
        description=annotations.get("description") or "",
        alert_type=labels.get("alertname") or "alertmanager",
        source="alertmanager",
        external_id=str(external_id),
        payload=payload_details,
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _cloudwatch_overrides(labels: dict[str, Any], annotations: dict[str, Any]) -> dict[str, Any]:
    merged = {**annotations, **labels}
    keys = [
        "cloudwatch_log_group",
        "cloudwatch_log_groups",
        "cloudwatch_log_stream_prefix",
        "cloudwatch_filter_pattern",
        "cloudwatch_start_time",
        "cloudwatch_end_time",
    ]
    return {key: merged[key] for key in keys if merged.get(key)}
