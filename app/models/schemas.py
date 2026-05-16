from typing import Any

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    service: str = Field(default="unknown")
    environment: str = Field(default="prod")
    severity: str = Field(default="UNKNOWN")
    title: str = Field(default="")
    description: str = Field(default="")
    alert_type: str = Field(default="")
    source: str = Field(default="manual")
    external_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class IncidentResponse(BaseModel):
    id: int
    external_id: str | None = None
    status: str
    service: str
    environment: str
    severity: str
    title: str = ""
    description: str = ""
    alert_type: str = ""
    source: str = "manual"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
