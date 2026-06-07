import re
from typing import Any

from app.db.dal import record_step
from app.rag.service import RagService
from app.services.ai_client import AIClient

RULES = [
    {
        "pattern": r"connection refused|ECONNREFUSED|postgres:5432",
        "issue": "Database connection errors",
        "root_cause": "Database service is refusing connections or is not ready",
        "fix": ["Restart or reschedule the DB workload", "Check readiness probes", "Verify network policy and service DNS"],
        "confidence": 0.82,
    },
    {
        "pattern": r"OOMKilled|OutOfMemoryError|memory pressure",
        "issue": "Service out of memory",
        "root_cause": "Container memory pressure or application memory leak",
        "fix": ["Increase container memory limit", "Inspect recent memory growth", "Scale horizontally while investigating"],
        "confidence": 0.8,
    },
    {
        "pattern": r"HTTP 500|NullPointerException|null deref",
        "issue": "HTTP 500 application error",
        "root_cause": "Application bug or unsafe null handling in the request path",
        "fix": ["Rollback the latest risky deploy", "Add null checks", "Improve input validation and regression tests"],
        "confidence": 0.76,
    },
    {
        "pattern": r"upstream_timeout|HTTP 504|p95_latency_ms|thread_pool saturated|request timed out",
        "issue": "Latency and upstream timeout spike",
        "root_cause": "A slow or saturated upstream dependency is causing checkout requests to time out",
        "fix": ["Identify and scale the slow dependency", "Reduce retries and enable circuit breaker", "Temporarily bypass non-critical dependency calls"],
        "confidence": 0.78,
    },
    {
        "pattern": r"JWT validation failed|unknown signing key|signature verification failed|cached_jwks",
        "issue": "JWT validation failures",
        "root_cause": "Stale or invalid signing key material after identity provider key rotation",
        "fix": ["Refresh JWKS cache", "Verify issuer/audience/key ID configuration", "Roll back key rotation if blast radius is high"],
        "confidence": 0.8,
    },
    {
        "pattern": r"queue backlog|visible_messages|oldest_age_seconds|consumer lag|worker_pool saturated",
        "issue": "Queue backlog and consumer lag",
        "root_cause": "Consumers are processing slower than producers are enqueueing work",
        "fix": ["Scale consumer workers", "Check downstream throttling or deadlocks", "Pause non-critical producers until backlog drains"],
        "confidence": 0.77,
    },
]


def log_corpus(collected: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in collected.get("logs", []):
        if isinstance(item, dict):
            parts.append(item.get("content", ""))
        else:
            parts.append(str(item))
    return "\n".join(parts)[:20000]


def heuristic_analysis(corpus: str) -> dict[str, Any]:
    for rule in RULES:
        if re.search(rule["pattern"], corpus, flags=re.I):
            return {
                "issue": rule["issue"],
                "root_cause": rule["root_cause"],
                "mitigations": rule["fix"],
                "evidence": [f"Matched log pattern: {rule['pattern']}"],
                "confidence": rule["confidence"],
            }
    return {
        "issue": "Unknown incident pattern",
        "root_cause": "Inconclusive from available logs",
        "mitigations": ["Escalate to on-call", "Gather more logs", "Increase diagnostic logging"],
        "evidence": ["No rule matched the collected logs"],
        "confidence": 0.25,
    }


def analyze_logs(
    incident: dict[str, Any],
    collected: dict[str, Any],
    ai_client: AIClient | None = None,
    rag_service: RagService | None = None,
) -> dict[str, Any]:
    incident_id = int(incident["id"])
    record_step(incident_id, "analyst", "start", "Analyzing logs and knowledge base", status="STARTED")

    corpus = log_corpus(collected)
    heuristic = heuristic_analysis(corpus)
    record_step(
        incident_id,
        "analyst",
        "analyze",
        heuristic["evidence"][0],
        {"issue": heuristic["issue"], "confidence": heuristic["confidence"]},
        status="OK" if heuristic["confidence"] >= 0.5 else "WARN",
    )

    query = "\n".join(
        [
            incident.get("title") or "",
            incident.get("description") or "",
            incident.get("alert_type") or "",
            incident.get("service") or "",
            corpus[:4000],
        ]
    )
    rag = rag_service or RagService()
    rag_context = rag.query(query, top_k=5)
    record_step(
        incident_id,
        "analyst",
        "retrieve",
        f"Retrieved {len(rag_context)} knowledge snippets",
        {"snippets": rag_context},
        status="OK" if rag_context else "WARN",
    )

    client = ai_client or AIClient()
    analysis = client.generate_rca(incident, collected, rag_context, heuristic)
    record_step(
        incident_id,
        "analyst",
        "summarize",
        f"Drafted RCA via {analysis.get('provider')}:{analysis.get('model')}",
        {
            "issue": analysis.get("issue"),
            "provider": analysis.get("provider"),
            "model": analysis.get("model"),
            "fallback_reason": analysis.get("fallback_reason"),
        },
        status="OK" if not analysis.get("fallback_reason") else "WARN",
    )
    return analysis
