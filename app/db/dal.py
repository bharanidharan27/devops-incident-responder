import datetime
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.config import DATABASE_URL as CONFIG_DATABASE_URL
from app.config import DB_FILE as CONFIG_DB_FILE

DB_FILE = CONFIG_DB_FILE
DATABASE_URL = CONFIG_DATABASE_URL
DB_URL = CONFIG_DATABASE_URL

metadata = MetaData()

incidents = Table(
    "incidents",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("external_id", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("service", Text, nullable=False),
    Column("environment", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("title", Text, nullable=False, default=""),
    Column("description", Text, nullable=False, default=""),
    Column("alert_type", Text, nullable=False, default=""),
    Column("source", Text, nullable=False, default="manual"),
    Column("payload_json", Text, nullable=False, default="{}"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    CheckConstraint("status IN ('OPEN', 'IN_PROGRESS', 'DONE', 'FAILED')", name="ck_incidents_status"),
    UniqueConstraint("external_id", name="uq_incidents_external_id"),
)

agent_steps = Table(
    "agent_steps",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("incident_id", Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
    Column("agent", Text, nullable=False),
    Column("phase", Text, nullable=False),
    Column("message", Text, nullable=False),
    Column("data_json", Text, nullable=False, default="{}"),
    Column("ts", Text, nullable=False),
    Column("status", Text, nullable=True),
)

reports = Table(
    "reports",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("incident_id", Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
    Column("report_json", Text, nullable=False),
    Column("report_md", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

Index("idx_incidents_status", incidents.c.status, incidents.c.id)
Index("idx_incidents_external_id", incidents.c.external_id)
Index("idx_steps_inc_ts", agent_steps.c.incident_id, agent_steps.c.ts)
Index("idx_reports_inc_dt", reports.c.incident_id, reports.c.created_at)

_ENGINES: dict[str, Engine] = {}


def _now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sqlite_url_from_file(path: str) -> str:
    sqlite_path = Path(path)
    if not sqlite_path.is_absolute():
        sqlite_path = Path.cwd() / sqlite_path
    return f"sqlite:///{sqlite_path.as_posix()}"


def _normalize_database_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    if raw.startswith("sqlite:///"):
        sqlite_file = raw.removeprefix("sqlite:///")
        if sqlite_file and sqlite_file != ":memory:":
            return _sqlite_url_from_file(sqlite_file)
    return raw


def _database_url() -> str:
    env_database_url = os.getenv("DATABASE_URL")
    if env_database_url:
        return _normalize_database_url(env_database_url)

    if DB_FILE != CONFIG_DB_FILE:
        return _sqlite_url_from_file(str(DB_FILE))

    env_db_url = os.getenv("DB_URL")
    if env_db_url:
        return _normalize_database_url(env_db_url)

    if DATABASE_URL and not DATABASE_URL.startswith("sqlite:///"):
        return _normalize_database_url(DATABASE_URL)

    return _sqlite_url_from_file(DB_FILE)


def _engine() -> Engine:
    url = _database_url()
    engine = _ENGINES.get(url)
    if engine:
        return engine

    kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite:///"):
        db_path = Path(url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite:///"):
        _enable_sqlite_foreign_keys(engine)
    _ENGINES[url] = engine
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


def _json_loads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return default


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def init_db() -> None:
    metadata.create_all(_engine())


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
    values: dict[str, Any] = {
        "status": status,
        "service": service,
        "environment": environment,
        "severity": severity,
        "title": title,
        "description": description,
        "alert_type": alert_type,
        "source": source,
        "payload_json": json.dumps(payload or {}),
        "created_at": created_at or now,
        "updated_at": now,
    }
    if external_id:
        values["external_id"] = external_id
    if incident_id is not None:
        values["id"] = incident_id

    with _engine().begin() as con:
        if external_id:
            existing = con.execute(
                select(incidents.c.id).where(incidents.c.external_id == external_id)
            ).scalar_one_or_none()
            if existing is not None:
                return int(existing)

        try:
            result = con.execute(insert(incidents).values(**values))
        except IntegrityError:
            if not external_id:
                raise
            existing = con.execute(
                select(incidents.c.id).where(incidents.c.external_id == external_id)
            ).scalar_one()
            return int(existing)

        return int(incident_id if incident_id is not None else result.inserted_primary_key[0])


def record_step(
    incident_id: int,
    agent: str,
    phase: str,
    message: str,
    data: dict[str, Any] | None = None,
    status: str | None = None,
) -> None:
    with _engine().begin() as con:
        con.execute(
            insert(agent_steps).values(
                incident_id=incident_id,
                agent=agent,
                phase=phase,
                message=message,
                data_json=json.dumps(data or {}),
                ts=_now_iso(),
                status=status,
            )
        )


def save_report(incident_id: int, report_json: dict[str, Any], report_md: str) -> None:
    with _engine().begin() as con:
        con.execute(
            insert(reports).values(
                incident_id=incident_id,
                report_json=json.dumps(report_json),
                report_md=report_md,
                created_at=_now_iso(),
            )
        )


def list_incidents(limit: int = 200) -> list[dict[str, Any]]:
    statement = (
        select(
            incidents.c.id,
            incidents.c.external_id,
            incidents.c.status,
            incidents.c.service,
            incidents.c.environment,
            incidents.c.severity,
            incidents.c.title,
            incidents.c.alert_type,
            incidents.c.source,
            incidents.c.created_at,
            incidents.c.updated_at,
        )
        .order_by(incidents.c.id.desc())
        .limit(limit)
    )
    with _engine().connect() as con:
        rows = con.execute(statement).fetchall()
    return [_row_dict(row) for row in rows]


def get_incident(incident_id: int) -> dict[str, Any] | None:
    with _engine().connect() as con:
        row = con.execute(select(incidents).where(incidents.c.id == incident_id)).fetchone()
    if not row:
        return None
    incident = _row_dict(row)
    incident["payload"] = _json_loads(incident.pop("payload_json", "{}"), {})
    return incident


def list_steps(incident_id: int) -> list[dict[str, Any]]:
    statement = (
        select(
            agent_steps.c.id,
            agent_steps.c.agent,
            agent_steps.c.phase,
            agent_steps.c.status,
            agent_steps.c.message,
            agent_steps.c.ts,
            agent_steps.c.data_json,
        )
        .where(agent_steps.c.incident_id == incident_id)
        .order_by(agent_steps.c.id.asc())
    )
    with _engine().connect() as con:
        rows = con.execute(statement).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        item = _row_dict(row)
        item["data"] = _json_loads(item.pop("data_json", "{}"), {})
        output.append(item)
    return output


def get_latest_report(incident_id: int) -> dict[str, Any] | None:
    statement = (
        select(reports.c.id, reports.c.report_json, reports.c.report_md, reports.c.created_at)
        .where(reports.c.incident_id == incident_id)
        .order_by(reports.c.id.desc())
        .limit(1)
    )
    with _engine().connect() as con:
        row = con.execute(statement).fetchone()
    if not row:
        return None
    report = _row_dict(row)
    report["report"] = _json_loads(report.pop("report_json", "{}"), {})
    return report


def get_open_incidents(limit: int | None = None) -> list[dict[str, Any]]:
    statement = (
        select(incidents)
        .where(incidents.c.status == "OPEN")
        .order_by(incidents.c.id.asc())
    )
    if limit is not None:
        statement = statement.limit(limit)

    with _engine().connect() as con:
        rows = con.execute(statement).fetchall()

    output = []
    for row in rows:
        incident = _row_dict(row)
        incident["payload"] = _json_loads(incident.pop("payload_json", "{}"), {})
        output.append(incident)
    return output


def update_status(incident_id: int, status: str) -> None:
    with _engine().begin() as con:
        con.execute(
            update(incidents)
            .where(incidents.c.id == incident_id)
            .values(status=status, updated_at=_now_iso())
        )


def mark_open(incident_id: int) -> None:
    update_status(incident_id, "OPEN")


def mark_in_progress(incident_id: int) -> None:
    update_status(incident_id, "IN_PROGRESS")


def mark_done(incident_id: int) -> None:
    update_status(incident_id, "DONE")


def mark_failed(incident_id: int) -> None:
    update_status(incident_id, "FAILED")
