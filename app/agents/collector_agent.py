import glob
import json
import os
from pathlib import Path
from typing import Any

from app.config import CLOUDWATCH_FALLBACK_TO_LOCAL, LOGS_LOCAL_ROOT, LOGS_MODE
from app.db.dal import record_step
from app.middleware.cloudwatch_boto import fetch_cloudwatch_logs
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


def fetch_local_logs(folder: str, limit: int = 5, max_chars: int = 5000) -> list[dict[str, Any]]:
    path = Path(LOGS_LOCAL_ROOT) / folder
    logs: list[dict[str, Any]] = []
    for file_path in sorted(glob.glob(str(path / "*.log")))[:limit]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            content = redact_text(handle.read()[:max_chars])
        logs.append(
            {
                "path": os.path.relpath(file_path, Path(LOGS_LOCAL_ROOT).parent),
                "content": content,
                "excerpt": content[:500],
                "source": "local",
            }
        )
    return logs


def fetch_logs(incident: dict[str, Any], folder: str, limit: int = 5, max_chars: int = 5000) -> list[dict[str, Any]]:
    if LOGS_MODE.lower() in {"cloudwatch", "aws", "aws_cloudwatch"}:
        return fetch_cloudwatch_logs(incident, limit=limit, max_chars=max_chars)
    return fetch_local_logs(folder, limit=limit, max_chars=max_chars)


def collector_run(incident: dict[str, Any]) -> dict[str, Any]:
    incident_id = int(incident["id"])
    record_step(incident_id, "collector", "start", "Collector started", status="STARTED")
    folder = choose_log_folder(incident)
    mode = LOGS_MODE.lower()
    record_step(
        incident_id,
        "collector",
        "retrieve",
        f"Selected log source: {mode}",
        {"mode": mode, "local_folder": folder},
        status="OK",
    )
    try:
        logs = fetch_logs(incident, folder)
        fallback_reason = None
    except Exception as exc:
        if not CLOUDWATCH_FALLBACK_TO_LOCAL:
            raise
        fallback_reason = str(exc)
        record_step(
            incident_id,
            "collector",
            "retrieve",
            "CloudWatch collection failed; falling back to local sample logs",
            {"error": fallback_reason, "local_folder": folder},
            status="WARN",
        )
        logs = fetch_local_logs(folder)
    record_step(
        incident_id,
        "collector",
        "done",
        f"Fetched {len(logs)} log files",
        {
            "mode": mode,
            "folder": folder,
            "fallback_reason": fallback_reason,
            "logs": [{"path": item["path"], "source": item.get("source"), "excerpt": item["excerpt"]} for item in logs],
        },
        status="WARN" if fallback_reason else "OK",
    )
    return {"mode": mode, "folder": folder, "fallback_reason": fallback_reason, "logs": logs}
