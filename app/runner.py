import argparse
import time
import traceback
from typing import Any

from app.agents.analyst_agent import analyze_logs
from app.agents.collector_agent import collector_run
from app.agents.supervisor import supervisor_orchestrate
from app.config import POLL_INTERVAL_SECONDS
from app.db.dal import (
    get_incident,
    get_open_incidents,
    init_db,
    mark_failed,
    mark_in_progress,
    record_step,
)


def process_incident(incident: dict[str, Any] | int) -> dict[str, Any] | None:
    init_db()
    inc = get_incident(int(incident)) if isinstance(incident, int) else incident
    if not inc:
        return None

    incident_id = int(inc["id"])
    try:
        mark_in_progress(incident_id)
        record_step(incident_id, "supervisor", "start", "Incident processing started", status="STARTED")
        collected = collector_run(inc)
        analysis = analyze_logs(inc, collected)
        report = supervisor_orchestrate(inc, analysis)
        return report
    except Exception as exc:
        record_step(
            incident_id,
            "supervisor",
            "error",
            str(exc),
            {"trace": traceback.format_exc()},
            status="ERROR",
        )
        mark_failed(incident_id)
        return None


def run_once(limit: int | None = None) -> int:
    init_db()
    count = 0
    for incident in get_open_incidents(limit=limit):
        print(f"[runner] processing incident {incident['id']}")
        process_incident(incident)
        count += 1
    return count


def run_forever() -> None:
    init_db()
    print(f"[runner] polling every {POLL_INTERVAL_SECONDS}s")
    while True:
        try:
            run_once()
        except Exception as exc:
            print("[runner] loop error:", exc)
        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="DevOps incident responder worker")
    parser.add_argument("--once", action="store_true", help="Process currently open incidents and exit")
    parser.add_argument("--limit", type=int, default=None, help="Maximum open incidents to process")
    parser.add_argument("--incident-id", type=int, default=None, help="Process one incident by id")
    args = parser.parse_args()

    if args.incident_id is not None:
        process_incident(args.incident_id)
        return
    if args.once:
        run_once(limit=args.limit)
        return
    run_forever()


if __name__ == "__main__":
    main()
