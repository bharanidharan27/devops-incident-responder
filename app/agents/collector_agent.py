import glob
import json
import os
from pathlib import Path
from typing import Any

from app.config import LOGS_LOCAL_ROOT
from app.db.dal import record_step
from app.services.redaction import redact_text


def choose_log_folder(incident: dict[str, Any]) -> str:
    payload = incident.get("payload") or {}
    search_text = " ".join(
        [
            incident.get("alert_type") or "",
            incident.get("title") or "",
            incident.get("description") or "",
            incident.get("service") or "",
            json.dumps(payload),
        ]
    ).lower()
    if any(token in search_text for token in ["db", "postgres", "mysql", "connection refused", "database"]):
        return "db"
    if any(token in search_text for token in ["cpu", "oom", "memory", "infra", "kubelet", "pod"]):
        return "infra"
    return "web"


def fetch_logs(folder: str, limit: int = 5, max_chars: int = 5000) -> list[dict[str, str]]:
    path = Path(LOGS_LOCAL_ROOT) / folder
    logs: list[dict[str, str]] = []
    for file_path in sorted(glob.glob(str(path / "*.log")))[:limit]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            content = redact_text(handle.read()[:max_chars])
        logs.append(
            {
                "path": os.path.relpath(file_path, Path(LOGS_LOCAL_ROOT).parent),
                "content": content,
                "excerpt": content[:500],
            }
        )
    return logs


def collector_run(incident: dict[str, Any]) -> dict[str, Any]:
    incident_id = int(incident["id"])
    record_step(incident_id, "collector", "start", "Collector started", status="STARTED")
    folder = choose_log_folder(incident)
    record_step(
        incident_id,
        "collector",
        "retrieve",
        f"Selected logs folder: {folder}",
        {"folder": folder},
        status="OK",
    )
    logs = fetch_logs(folder)
    record_step(
        incident_id,
        "collector",
        "done",
        f"Fetched {len(logs)} log files",
        {"folder": folder, "logs": [{"path": item["path"], "excerpt": item["excerpt"]} for item in logs]},
        status="OK",
    )
    return {"folder": folder, "logs": logs}
