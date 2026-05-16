from typing import Any

from app.db.dal import mark_done, record_step, save_report


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def compile_report(incident: dict[str, Any], analysis: dict[str, Any]) -> tuple[dict[str, Any], str]:
    mitigations = _as_list(analysis.get("mitigations"))
    evidence = _as_list(analysis.get("evidence"))
    rag_context = analysis.get("rag_context") or []

    mitigation_md = "\n".join(f"- {item}" for item in mitigations) or "- TBD"
    evidence_md = "\n".join(f"- {item}" for item in evidence) or "- TBD"
    rag_md = "\n".join(
        f"- {item.get('source', 'knowledge')}: {item.get('text', '')[:240]}"
        for item in rag_context
    ) or "- No knowledge snippets retrieved"

    report_json = {
        "incident_id": incident["id"],
        "service": incident.get("service"),
        "environment": incident.get("environment"),
        "severity": incident.get("severity"),
        "title": incident.get("title"),
        "issue": analysis.get("issue", "Unknown"),
        "root_cause": analysis.get("root_cause", "Inconclusive"),
        "mitigations": mitigations,
        "evidence": evidence,
        "rag_context": rag_context,
        "confidence": analysis.get("confidence", 0.0),
        "provider": analysis.get("provider"),
        "model": analysis.get("model"),
        "fallback_reason": analysis.get("fallback_reason"),
    }

    report_md = f"""# Incident {incident['id']} RCA

**Service:** {incident.get('service', 'unknown')}
**Environment:** {incident.get('environment', 'unknown')}
**Severity:** {incident.get('severity', 'unknown')}
**Title:** {incident.get('title') or 'Untitled incident'}

## Issue
{report_json['issue']}

## Root Cause
{report_json['root_cause']}

## Suggested Mitigations
{mitigation_md}

## Evidence
{evidence_md}

## Knowledge Base Context
{rag_md}

## Analysis Metadata
- Confidence: {report_json['confidence']}
- Provider: {report_json.get('provider') or 'unknown'}
- Model: {report_json.get('model') or 'unknown'}
- Fallback reason: {report_json.get('fallback_reason') or 'none'}
"""
    return report_json, report_md


def supervisor_orchestrate(incident: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    incident_id = int(incident["id"])
    record_step(incident_id, "supervisor", "summarize", "Compiling final report", status="STARTED")
    report_json, report_md = compile_report(incident, analysis)
    save_report(incident_id, report_json, report_md)
    mark_done(incident_id)
    record_step(incident_id, "supervisor", "done", "Incident processing complete", status="OK")
    return report_json
