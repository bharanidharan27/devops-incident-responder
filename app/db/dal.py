import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import DB_FILE

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _conn(rowdict: bool = False) -> sqlite3.Connection:
    Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON")
    if rowdict:
        con.row_factory = sqlite3.Row
    return con


def _json_loads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return default


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(con: sqlite3.Connection, table: str) -> dict[str, tuple[Any, ...]]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1]: row for row in rows}


def _needs_incident_migration(con: sqlite3.Connection) -> bool:
    if not _table_exists(con, "incidents"):
        return False
    columns = _table_columns(con, "incidents")
    required = {
        "id",
        "external_id",
        "status",
        "service",
        "environment",
        "severity",
        "title",
        "description",
        "alert_type",
        "source",
        "payload_json",
        "created_at",
        "updated_at",
    }
    if not required.issubset(columns):
        return True
    id_type = (columns["id"][2] or "").upper()
    return "INTEGER" not in id_type


def _rename_if_exists(con: sqlite3.Connection, table: str, suffix: str) -> str | None:
    if not _table_exists(con, table):
        return None
    legacy_name = f"{table}_{suffix}"
    con.execute(f"ALTER TABLE {table} RENAME TO {legacy_name}")
    return legacy_name


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _migrate_legacy_schema(con: sqlite3.Connection) -> None:
    suffix = "legacy_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    legacy_incidents = _rename_if_exists(con, "incidents", suffix)
    legacy_steps = _rename_if_exists(con, "agent_steps", suffix)
    legacy_reports = _rename_if_exists(con, "reports", suffix)

    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not legacy_incidents:
        return

    id_map: dict[str, int] = {}
    legacy_columns = list(_table_columns(con, legacy_incidents).keys())
    rows = con.execute(f"SELECT * FROM {legacy_incidents}").fetchall()
    for row in rows:
        row_map = dict(zip(legacy_columns, row))
        old_id = row_map.get("id")
        now = _now_iso()
        numeric_id = _safe_int(old_id)
        columns = [
            "status",
            "service",
            "environment",
            "severity",
            "title",
            "description",
            "alert_type",
            "source",
            "payload_json",
            "created_at",
            "updated_at",
        ]
        values: list[Any] = [
            row_map.get("status") or "OPEN",
            row_map.get("service") or "unknown",
            row_map.get("environment") or "unknown",
            row_map.get("severity") or "UNKNOWN",
            row_map.get("title") or "",
            row_map.get("description") or "",
            row_map.get("alert_type") or "",
            row_map.get("source") or "legacy",
            row_map.get("payload_json") or "{}",
            row_map.get("created_at") or now,
            row_map.get("updated_at") or now,
        ]
        if numeric_id is not None:
            columns.insert(0, "id")
            values.insert(0, numeric_id)
        placeholders = ",".join("?" for _ in columns)
        cur = con.execute(
            f"INSERT INTO incidents({','.join(columns)}) VALUES({placeholders})",
            values,
        )
        new_id = numeric_id if numeric_id is not None else int(cur.lastrowid)
        if old_id is not None:
            id_map[str(old_id)] = new_id

    if legacy_steps and id_map:
        step_columns = list(_table_columns(con, legacy_steps).keys())
        for row in con.execute(f"SELECT * FROM {legacy_steps}").fetchall():
            row_map = dict(zip(step_columns, row))
            new_incident_id = id_map.get(str(row_map.get("incident_id")))
            if not new_incident_id:
                continue
            con.execute(
                """INSERT INTO agent_steps(incident_id, agent, phase, message, data_json, ts, status)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    new_incident_id,
                    row_map.get("agent") or "legacy",
                    row_map.get("phase") or "unknown",
                    row_map.get("message") or "",
                    row_map.get("data_json") or "{}",
                    row_map.get("ts") or _now_iso(),
                    row_map.get("status"),
                ),
            )

    if legacy_reports and id_map:
        report_columns = list(_table_columns(con, legacy_reports).keys())
        for row in con.execute(f"SELECT * FROM {legacy_reports}").fetchall():
            row_map = dict(zip(report_columns, row))
            new_incident_id = id_map.get(str(row_map.get("incident_id")))
            if not new_incident_id:
                continue
            con.execute(
                """INSERT INTO reports(incident_id, report_json, report_md, created_at)
                   VALUES(?,?,?,?)""",
                (
                    new_incident_id,
                    row_map.get("report_json") or "{}",
                    row_map.get("report_md") or "",
                    row_map.get("created_at") or _now_iso(),
                ),
            )


def init_db() -> None:
    with _conn() as con:
        if _needs_incident_migration(con):
            _migrate_legacy_schema(con)
        else:
            con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def record_incident(
    status: str = "OPEN",
    service: str = "unknown",
    environment: str = "unknown",
    severity: str = "UNKNOWN",
    payload: dict[str, Any] | None = None,
    created_at: str | None = None,
    incident_id: int | None = None,
    external_id: str | None = None,
    title: str = "",
    description: str = "",
    alert_type: str = "",
    source: str = "manual",
) -> int:
    init_db()
    now = _now_iso()
    with _conn() as con:
        if external_id:
            existing = con.execute(
                "SELECT id FROM incidents WHERE external_id=?",
                (external_id,),
            ).fetchone()
            if existing:
                return int(existing[0])
        columns = [
            "status",
            "service",
            "environment",
            "severity",
            "title",
            "description",
            "alert_type",
            "source",
            "payload_json",
            "created_at",
            "updated_at",
        ]
        values: list[Any] = [
            status,
            service,
            environment,
            severity,
            title,
            description,
            alert_type,
            source,
            json.dumps(payload or {}),
            created_at or now,
            now,
        ]
        if external_id:
            columns.insert(0, "external_id")
            values.insert(0, external_id)
        if incident_id is not None:
            columns.insert(0, "id")
            values.insert(0, incident_id)
        placeholders = ",".join("?" for _ in columns)
        cur = con.execute(
            f"INSERT INTO incidents({','.join(columns)}) VALUES({placeholders})",
            values,
        )
        return int(incident_id if incident_id is not None else cur.lastrowid)


def record_step(
    incident_id: int,
    agent: str,
    phase: str,
    message: str,
    data: dict[str, Any] | None = None,
    status: str | None = None,
) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO agent_steps(incident_id, agent, phase, message, data_json, ts, status)
               VALUES(?,?,?,?,?,?,?)""",
            (incident_id, agent, phase, message, json.dumps(data or {}), _now_iso(), status),
        )


def save_report(incident_id: int, report_json: dict[str, Any], report_md: str) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO reports(incident_id, report_json, report_md, created_at)
               VALUES(?,?,?,?)""",
            (incident_id, json.dumps(report_json), report_md, _now_iso()),
        )


def list_incidents(limit: int = 200) -> list[dict[str, Any]]:
    sql = """SELECT id, external_id, status, service, environment, severity, title,
                    alert_type, source, created_at, updated_at
             FROM incidents ORDER BY id DESC LIMIT ?"""
    with _conn(rowdict=True) as con:
        rows = con.execute(sql, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_incident(incident_id: int) -> dict[str, Any] | None:
    with _conn(rowdict=True) as con:
        row = con.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
    if not row:
        return None
    incident = dict(row)
    incident["payload"] = _json_loads(incident.pop("payload_json", "{}"), {})
    return incident


def list_steps(incident_id: int) -> list[dict[str, Any]]:
    sql = """SELECT id, agent, phase, status, message, ts, data_json
             FROM agent_steps WHERE incident_id=? ORDER BY id ASC"""
    with _conn(rowdict=True) as con:
        rows = con.execute(sql, (incident_id,)).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["data"] = _json_loads(item.pop("data_json", "{}"), {})
        out.append(item)
    return out


def get_latest_report(incident_id: int) -> dict[str, Any] | None:
    sql = """SELECT id, report_json, report_md, created_at
             FROM reports WHERE incident_id=? ORDER BY id DESC LIMIT 1"""
    with _conn(rowdict=True) as con:
        row = con.execute(sql, (incident_id,)).fetchone()
    if not row:
        return None
    report = dict(row)
    report["report"] = _json_loads(report.pop("report_json", "{}"), {})
    return report


def get_open_incidents(limit: int | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM incidents WHERE status='OPEN' ORDER BY id ASC"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    with _conn(rowdict=True) as con:
        rows = con.execute(sql, params).fetchall()
    incidents = []
    for row in rows:
        incident = dict(row)
        incident["payload"] = _json_loads(incident.pop("payload_json", "{}"), {})
        incidents.append(incident)
    return incidents


def update_status(incident_id: int, status: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE incidents SET status=?, updated_at=? WHERE id=?",
            (status, _now_iso(), incident_id),
        )


def mark_open(incident_id: int) -> None:
    update_status(incident_id, "OPEN")


def mark_in_progress(incident_id: int) -> None:
    update_status(incident_id, "IN_PROGRESS")


def mark_done(incident_id: int) -> None:
    update_status(incident_id, "DONE")


def mark_failed(incident_id: int) -> None:
    update_status(incident_id, "FAILED")
