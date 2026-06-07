import datetime
import os
from typing import Any

from app.config import (
    AWS_PROFILE,
    AWS_REGION,
    CLOUDWATCH_FALLBACK_TO_LOCAL,
    CLOUDWATCH_FILTER_PATTERN,
    CLOUDWATCH_LOG_GROUP,
    CLOUDWATCH_LOG_GROUPS,
    CLOUDWATCH_LOOKBACK_MINUTES,
    CLOUDWATCH_MAX_EVENTS,
    CLOUDWATCH_STREAM_PREFIX,
)
from app.services.redaction import redact_text


def fetch_cloudwatch_logs(
    incident: dict[str, Any],
    limit: int = CLOUDWATCH_MAX_EVENTS,
    max_chars: int = 5000,
) -> list[dict[str, Any]]:
    """Fetch recent CloudWatch log events for an incident.

    Incident payload may override env defaults with:
    - cloudwatch_log_group or cloudwatch_log_groups
    - cloudwatch_log_stream_prefix
    - cloudwatch_filter_pattern
    - cloudwatch_start_time and cloudwatch_end_time as epoch ms/sec or ISO strings
    """

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except Exception as exc:
        raise RuntimeError("boto3 is not installed; install requirements.txt to enable CloudWatch") from exc

    payload = incident.get("payload") or {}
    groups = _log_groups(payload)
    if not groups:
        raise RuntimeError("No CloudWatch log group configured")

    client = _logs_client(boto3)
    start_ms, end_ms = _time_window_ms(incident, payload)
    filter_pattern = payload.get("cloudwatch_filter_pattern") or CLOUDWATCH_FILTER_PATTERN
    stream_prefix = payload.get("cloudwatch_log_stream_prefix") or CLOUDWATCH_STREAM_PREFIX

    logs: list[dict[str, Any]] = []
    remaining = limit
    for group in groups:
        if remaining <= 0:
            break
        params: dict[str, Any] = {
            "logGroupName": group,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": remaining,
            "interleaved": True,
        }
        if filter_pattern:
            params["filterPattern"] = filter_pattern
        if stream_prefix:
            params["logStreamNamePrefix"] = stream_prefix
        try:
            response = client.filter_log_events(**params)
        except (BotoCoreError, ClientError) as exc:
            if CLOUDWATCH_FALLBACK_TO_LOCAL:
                raise RuntimeError(f"CloudWatch read failed for {group}: {exc}") from exc
            raise

        events = response.get("events", [])
        if not events:
            continue

        lines = []
        for event in events:
            timestamp = _from_epoch_ms(event.get("timestamp"))
            stream = event.get("logStreamName") or "unknown-stream"
            message = redact_text(str(event.get("message", "")).strip())
            lines.append(f"{timestamp} {stream} {message}")

        content = "\n".join(lines)[:max_chars]
        logs.append(
            {
                "path": f"cloudwatch://{group}",
                "content": content,
                "excerpt": content[:500],
                "source": "cloudwatch",
                "log_group": group,
                "event_count": len(events),
                "start_time": _from_epoch_ms(start_ms),
                "end_time": _from_epoch_ms(end_ms),
            }
        )
        remaining -= len(events)
    return logs


def _logs_client(boto3_module: Any) -> Any:
    session_kwargs: dict[str, Any] = {}
    if AWS_PROFILE:
        session_kwargs["profile_name"] = AWS_PROFILE
    if AWS_REGION:
        session_kwargs["region_name"] = AWS_REGION
    session = boto3_module.Session(**session_kwargs)
    return session.client("logs")


def _log_groups(payload: dict[str, Any]) -> list[str]:
    raw = (
        payload.get("cloudwatch_log_groups")
        or payload.get("cloudwatch_log_group")
        or payload.get("log_groups")
        or payload.get("log_group")
        or CLOUDWATCH_LOG_GROUPS
        or CLOUDWATCH_LOG_GROUP
    )
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _time_window_ms(incident: dict[str, Any], payload: dict[str, Any]) -> tuple[int, int]:
    end = _parse_time(payload.get("cloudwatch_end_time")) or datetime.datetime.now(datetime.timezone.utc)
    start = _parse_time(payload.get("cloudwatch_start_time"))
    if start is None:
        created = _parse_time(incident.get("created_at"))
        anchor = created or end
        start = anchor - datetime.timedelta(minutes=CLOUDWATCH_LOOKBACK_MINUTES)
        if created and end < created:
            end = created + datetime.timedelta(minutes=5)
    return _to_epoch_ms(start), _to_epoch_ms(end)


def _parse_time(value: Any) -> datetime.datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000
        return datetime.datetime.fromtimestamp(number, tz=datetime.timezone.utc)
    text = str(value).strip()
    if text.isdigit():
        return _parse_time(int(text))
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(datetime.timezone.utc)
    except ValueError:
        return None


def _to_epoch_ms(value: datetime.datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return int(value.timestamp() * 1000)


def _from_epoch_ms(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = _to_epoch_ms(datetime.datetime.now(datetime.timezone.utc))
    return datetime.datetime.fromtimestamp(number / 1000, tz=datetime.timezone.utc).isoformat().replace("+00:00", "Z")
