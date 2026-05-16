from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

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
