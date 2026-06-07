import argparse
import datetime
import random
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import AWS_PROFILE, AWS_REGION, CLOUDWATCH_SIMULATION_RETENTION_DAYS

SCENARIOS = {
    "http500": {
        "title": "Checkout HTTP 500 spike after deployment",
        "streams": {
            "payment-service": [
                (-120, "INFO deploy revision=payments-20260607.3 image=payment-service:1.42.0 status=started"),
                (-105, "INFO GET /healthz 200 latency_ms=12"),
                (-90, "INFO trace_id=chk-1001 GET /checkout user_id=842 plan=premium"),
                (-88, "ERROR trace_id=chk-1001 GET /checkout HTTP 500 java.lang.NullPointerException at com.app.Payments.charge(Payments.java:42)"),
                (-76, "WARN checkout_error_rate_5m=18.4 threshold=5.0 deployment=payments-20260607.3"),
                (-65, "ERROR trace_id=chk-1002 POST /payments/authorize HTTP 500 upstream=card-gateway cause=null payment_method"),
                (-50, "INFO circuit_breaker card-gateway state=half_open"),
                (-35, "ERROR trace_id=chk-1003 GET /checkout HTTP 500 java.lang.NullPointerException at com.app.Payments.charge(Payments.java:42)"),
                (-15, "WARN canary analysis failed metric=http_5xx_rate rollback_recommended=true"),
            ],
            "card-gateway": [
                (-92, "INFO trace_id=chk-1001 authorize request received"),
                (-87, "INFO trace_id=chk-1001 authorize response=approved latency_ms=81"),
                (-64, "INFO trace_id=chk-1002 authorize request received"),
                (-61, "INFO trace_id=chk-1002 authorize response=approved latency_ms=84"),
            ],
            "nginx": [
                (-84, "WARN path=/checkout status=500 upstream=payment-service request_id=chk-1001"),
                (-33, "WARN path=/checkout status=500 upstream=payment-service request_id=chk-1003"),
            ],
        },
    },
    "db": {
        "title": "Database connection refused during checkout",
        "streams": {
            "payment-service": [
                (-130, "INFO db_pool checkout-db max=30 active=25 idle=5"),
                (-100, "WARN db_pool checkout-db active=30 idle=0 waiters=42"),
                (-80, "ERROR trace_id=db-2001 db-conn: connection refused to postgres:5432 service=checkout-db"),
                (-60, "ERROR trace_id=db-2002 ECONNREFUSED postgres:5432 retries_exhausted=true"),
                (-45, "WARN checkout_error_rate_5m=22.9 cause=db_connection_refused"),
                (-25, "ERROR transaction failed order_id=ord-8841 reason=database unavailable"),
            ],
            "postgres": [
                (-120, "WARN checkpoint starting: time"),
                (-90, "ERROR could not accept SSL connection: too many clients already"),
                (-70, "FATAL remaining connection slots are reserved for non-replication superuser connections"),
                (-50, "WARN autovacuum worker launch skipped because of resource pressure"),
            ],
        },
    },
    "oom": {
        "title": "Payment service container OOMKilled",
        "streams": {
            "kubelet": [
                (-150, "INFO pod=payment-service-7b9c memory_usage_mb=710 memory_limit_mb=768"),
                (-105, "WARN pod=payment-service-7b9c memory_usage_mb=758 memory_limit_mb=768"),
                (-88, "ERROR kubelet: OOMKilled container payment-service pod=payment-service-7b9c exit_code=137"),
                (-70, "INFO pod=payment-service-7b9c restart_count=4 reason=OOMKilled"),
                (-40, "WARN readiness probe failed pod=payment-service-7b9c path=/healthz"),
            ],
            "payment-service": [
                (-140, "WARN heap_used_mb=612 heap_max_mb=640 gc_pause_ms=540"),
                (-112, "ERROR OutOfMemoryError Java heap space while rendering receipt pdf"),
                (-95, "WARN request_queue_depth=318 worker_threads=busy"),
            ],
        },
    },
    "latency": {
        "title": "Checkout latency and upstream timeout spike",
        "streams": {
            "payment-service": [
                (-150, "INFO p95_latency_ms=220 route=/checkout"),
                (-110, "WARN p95_latency_ms=1850 route=/checkout threshold_ms=1000"),
                (-95, "ERROR trace_id=lat-3001 upstream_timeout service=inventory timeout_ms=3000 route=/checkout"),
                (-70, "ERROR trace_id=lat-3002 HTTP 504 upstream=inventory latency_ms=3012"),
                (-45, "WARN retry_budget remaining=2 service=inventory"),
                (-20, "ERROR trace_id=lat-3003 checkout failed reason=upstream timeout"),
            ],
            "inventory": [
                (-100, "WARN query slow sku=sku-8821 duration_ms=2844 table=inventory_locks"),
                (-72, "WARN thread_pool saturated active=64 queued=220"),
                (-42, "ERROR request timed out operation=reserve_inventory duration_ms=5000"),
            ],
        },
    },
    "auth": {
        "title": "JWT validation failures causing authentication errors",
        "streams": {
            "user-service": [
                (-135, "INFO jwks refresh started issuer=https://idp.example.com"),
                (-100, "ERROR JWT validation failed kid=rotated-2026 reason=unknown signing key"),
                (-82, "WARN auth_failure_rate_5m=31.2 endpoint=/login"),
                (-65, "ERROR token rejected sub=user-842 reason=signature verification failed"),
                (-35, "WARN cached_jwks_age_seconds=86400 refresh_status=failed"),
            ],
            "api-gateway": [
                (-95, "WARN path=/checkout status=401 upstream=user-service reason=jwt_validation_failed"),
                (-55, "WARN path=/profile status=401 upstream=user-service reason=jwt_validation_failed"),
            ],
        },
    },
    "queue": {
        "title": "Order queue backlog and consumer lag",
        "streams": {
            "order-worker": [
                (-160, "INFO queue=orders visible_messages=900 oldest_age_seconds=120"),
                (-120, "WARN queue=orders visible_messages=4200 oldest_age_seconds=480 threshold=300"),
                (-95, "ERROR consumer lag high queue=orders processing_rate=12 enqueue_rate=180"),
                (-70, "WARN worker_pool saturated active=40 queued=3950"),
                (-38, "ERROR order fulfillment delayed reason=queue backlog oldest_age_seconds=760"),
            ],
            "payment-service": [
                (-90, "WARN publish retries queue=orders error=throttling"),
                (-52, "INFO payment authorized order_id=ord-9901 publish_status=retrying"),
            ],
        },
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a realistic incident scenario into CloudWatch Logs.")
    parser.add_argument("--log-group", default="/devops-incident-responder/payment-service")
    parser.add_argument("--stream-prefix", default="demo")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default=None, help="Defaults to a random scenario.")
    parser.add_argument("--region", default=AWS_REGION)
    parser.add_argument("--profile", default=AWS_PROFILE)
    parser.add_argument("--scenario-file", default=".demo_scenario", help="Writes the chosen scenario here for the alert simulator.")
    args = parser.parse_args()
    if args.scenario is None:
        args.scenario = random.choice(sorted(SCENARIOS))
    Path(args.scenario_file).write_text(args.scenario, encoding="utf-8")

    client = _client(args.profile, args.region)
    ensure_log_group(client, args.log_group)
    written = write_scenario(client, args.log_group, args.stream_prefix, args.scenario)

    print("Wrote CloudWatch demo logs.")
    print(f"Scenario: {args.scenario} - {SCENARIOS[args.scenario]['title']}")
    print(f"Events: {written['events']} across {written['streams']} streams")
    print(f"LOGS_MODE=cloudwatch")
    print(f"AWS_REGION={args.region}")
    print(f"AWS_PROFILE={args.profile or ''}")
    print(f"CLOUDWATCH_LOG_GROUPS={args.log_group}")
    print(f"CLOUDWATCH_STREAM_PREFIX={args.stream_prefix}")
    print(f"Scenario file: {args.scenario_file}")
    print("")
    print("Before the demo, rebuild RAG so the expanded runbooks are indexed:")
    print("python -m app.rag.build_index")
    print("")
    print("Use these Alertmanager simulator args:")
    print(
        " ".join(
            [
                "python",
                "scripts/simulate_alertmanager_alert.py",
                f"--log-group {args.log_group}",
                f"--stream-prefix {args.stream_prefix}",
                f"--scenario {args.scenario}",
            ]
        )
    )


def _client(profile: str, region: str) -> Any:
    import boto3

    kwargs = {"region_name": region}
    if profile:
        kwargs["profile_name"] = profile
    return boto3.Session(**kwargs).client("logs")


def ensure_log_group(client: Any, log_group: str) -> None:
    try:
        client.create_log_group(logGroupName=log_group)
    except client.exceptions.ResourceAlreadyExistsException:
        pass
    if CLOUDWATCH_SIMULATION_RETENTION_DAYS > 0:
        client.put_retention_policy(
            logGroupName=log_group,
            retentionInDays=CLOUDWATCH_SIMULATION_RETENTION_DAYS,
        )


def ensure_stream(client: Any, log_group: str, stream_name: str) -> None:
    try:
        client.create_log_stream(logGroupName=log_group, logStreamName=stream_name)
    except client.exceptions.ResourceAlreadyExistsException:
        pass


def write_scenario(client: Any, log_group: str, stream_prefix: str, scenario: str) -> dict[str, int]:
    scenario_def = SCENARIOS[scenario]
    suffix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    total_events = 0
    for component, events in scenario_def["streams"].items():
        stream_name = f"{stream_prefix}-{scenario}-{component}-{suffix}"
        ensure_stream(client, log_group, stream_name)
        put_events(client, log_group, stream_name, events)
        total_events += len(events)
    return {"streams": len(scenario_def["streams"]), "events": total_events}


def put_events(client: Any, log_group: str, stream_name: str, events: list[tuple[int, str]]) -> None:
    now_ms = int(time.time() * 1000)
    log_events = [
        {"timestamp": now_ms + offset_seconds * 1000, "message": message}
        for offset_seconds, message in events
    ]
    log_events.sort(key=lambda item: item["timestamp"])
    client.put_log_events(logGroupName=log_group, logStreamName=stream_name, logEvents=log_events)


if __name__ == "__main__":
    main()
