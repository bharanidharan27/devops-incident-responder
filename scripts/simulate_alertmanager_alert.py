import argparse
import datetime
import json
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCENARIOS = {
    "http500": {
        "alertname": "CheckoutHighErrorRate",
        "service": "payment-service",
        "summary": "Checkout HTTP 500 spike",
        "description": "Prometheus detected a sustained HTTP 500 spike on checkout after deployment payments-20260607.3.",
        "filter": "ERROR",
        "runbook": "checkout-http-500",
    },
    "db": {
        "alertname": "DatabaseConnectionRefused",
        "service": "payment-service",
        "summary": "Database connection refused",
        "description": "Application logs show postgres connection refused errors and pool exhaustion.",
        "filter": "ERROR",
        "runbook": "database-connection-refused",
    },
    "oom": {
        "alertname": "ContainerOOMKilled",
        "service": "payment-service",
        "summary": "Container OOMKilled",
        "description": "Kubelet reported repeated OOMKilled restarts for the payment service.",
        "filter": "ERROR",
        "runbook": "container-oomkilled",
    },
    "latency": {
        "alertname": "CheckoutLatencySLOViolation",
        "service": "checkout",
        "summary": "Checkout latency SLO violation",
        "description": "Checkout p95 latency and HTTP 504s increased because inventory calls are timing out.",
        "filter": "timeout",
        "runbook": "latency-timeouts",
    },
    "auth": {
        "alertname": "JWTValidationFailures",
        "service": "user-service",
        "summary": "JWT validation failures",
        "description": "Authentication failures increased after signing key rotation.",
        "filter": "JWT",
        "runbook": "jwt-validation-failures",
    },
    "queue": {
        "alertname": "OrderQueueBacklog",
        "service": "order-worker",
        "summary": "Order queue backlog",
        "description": "Order queue oldest message age and consumer lag exceeded the production threshold.",
        "filter": "queue",
        "runbook": "queue-backlog",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an Alertmanager-compatible webhook to the local API.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--service", default=None)
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--severity", default="critical")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default=None, help="Defaults to the scenario file, then random.")
    parser.add_argument("--scenario-file", default=".demo_scenario", help="Reads the scenario written by the CloudWatch simulator.")
    parser.add_argument("--log-group", default="/devops-incident-responder/payment-service")
    parser.add_argument("--stream-prefix", default="demo")
    args = parser.parse_args()
    if args.scenario is None:
        args.scenario = read_scenario_file(args.scenario_file) or random.choice(sorted(SCENARIOS))
        print(f"Selected scenario: {args.scenario}", file=sys.stderr)

    payload = build_payload(args)
    request = urllib.request.Request(
        f"{args.api_url.rstrip('/')}/api/webhooks/alertmanager",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 404:
            print(
                "Alertmanager webhook returned 404. Restart the API server so it loads "
                "/api/webhooks/alertmanager, then rerun this simulator.",
                file=sys.stderr,
            )
        print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(body)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    scenario = SCENARIOS[args.scenario]
    service = args.service or scenario["service"]
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    fingerprint_prefix = args.stream_prefix or "alertmanager"
    fingerprint = f"{fingerprint_prefix}-{args.scenario}-{now.strftime('%Y%m%d%H%M%S')}"
    labels = {
        "alertname": scenario["alertname"],
        "service": service,
        "environment": args.environment,
        "severity": args.severity,
        "runbook": scenario["runbook"],
        "cloudwatch_log_group": args.log_group,
        "cloudwatch_log_stream_prefix": args.stream_prefix,
        "cloudwatch_filter_pattern": scenario["filter"],
    }
    annotations = {
        "summary": scenario["summary"],
        "description": scenario["description"],
        "runbook_url": f"local://runbooks/{scenario['runbook']}",
    }
    alert = {
        "status": "firing",
        "labels": labels,
        "annotations": annotations,
        "startsAt": now.isoformat().replace("+00:00", "Z"),
        "endsAt": "0001-01-01T00:00:00Z",
        "generatorURL": "local-simulator",
        "fingerprint": fingerprint,
    }
    return {
        "version": "4",
        "groupKey": f"{{}}:{{alertname='{scenario['alertname']}'}}",
        "status": "firing",
        "receiver": "devops-incident-responder",
        "groupLabels": {"alertname": scenario["alertname"]},
        "commonLabels": labels,
        "commonAnnotations": annotations,
        "externalURL": "http://localhost:9093",
        "alerts": [alert],
    }


def read_scenario_file(path: str) -> str | None:
    scenario_path = Path(path)
    if not scenario_path.exists():
        return None
    scenario = scenario_path.read_text(encoding="utf-8").strip()
    return scenario if scenario in SCENARIOS else None


if __name__ == "__main__":
    main()
