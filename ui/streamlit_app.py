import json

import pandas as pd
import streamlit as st

from app.db.dal import get_incident, get_latest_report, init_db, list_incidents, list_steps, record_incident
from app.rag.service import RagService
from app.runner import process_incident
from app.services.ai_client import AIClient


def parse_payload(raw: str) -> dict:
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError as exc:
        st.error(f"Payload JSON is invalid: {exc}")
        st.stop()


def create_incident_form() -> None:
    with st.expander("Create incident", expanded=True):
        with st.form("incident_form"):
            cols = st.columns(3)
            service = cols[0].text_input("Service", value="payment-service")
            environment = cols[1].text_input("Environment", value="prod")
            severity = cols[2].selectbox("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], index=0)
            title = st.text_input("Title", value="Checkout requests are failing")
            description = st.text_area("Description", value="HTTP 500 spike on checkout flow")
            alert_type = st.text_input("Alert type", value="HTTP 500")
            source = st.text_input("Source", value="manual")
            external_id = st.text_input("External ID", value="")
            payload_raw = st.text_area(
                "Payload JSON",
                value='{"details": "synthetic cloudwatch-like alert", "service": "payment-service"}',
                height=120,
            )
            submitted = st.form_submit_button("Create")

        if submitted:
            incident_id = record_incident(
                status="OPEN",
                service=service,
                environment=environment,
                severity=severity,
                title=title,
                description=description,
                alert_type=alert_type,
                source=source or "manual",
                external_id=external_id or None,
                payload=parse_payload(payload_raw),
            )
            st.success(f"Incident {incident_id} created")
            st.rerun()


def provider_panel() -> None:
    status = AIClient().provider_status()
    st.sidebar.subheader("AI Providers")
    st.sidebar.caption(f"Default: {status['default_model']}")
    rows = [
        {
            "provider": item["provider"],
            "model": item["model"],
            "configured": "yes" if item["configured"] else "no",
        }
        for item in status["models"]
    ]
    st.sidebar.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if st.sidebar.button("Rebuild knowledge base"):
        result = RagService().reindex()
        st.sidebar.success(f"Indexed {result['documents']} chunks with {result['backend']}")


def render_incident_detail(incident_id: int) -> None:
    incident = get_incident(incident_id)
    if not incident:
        st.warning("Incident not found")
        return

    header_cols = st.columns([2, 1, 1, 1])
    header_cols[0].subheader(f"Incident {incident['id']}: {incident.get('title') or incident['service']}")
    header_cols[1].metric("Status", incident["status"])
    header_cols[2].metric("Severity", incident["severity"])
    header_cols[3].metric("Service", incident["service"])
    st.caption(
        f"Environment: {incident['environment']} | Source: {incident['source']} | "
        f"Created: {incident['created_at']} | Updated: {incident['updated_at']}"
    )

    actions = st.columns([1, 1, 4])
    if actions[0].button("Run now", use_container_width=True):
        with st.spinner("Processing incident..."):
            process_incident(incident_id)
        st.rerun()
    if actions[1].button("Refresh", use_container_width=True):
        st.rerun()

    detail_tabs = st.tabs(["Timeline", "Report", "Evidence", "Payload"])
    steps = list_steps(incident_id)

    with detail_tabs[0]:
        if steps:
            steps_df = pd.DataFrame(
                [
                    {
                        "id": step["id"],
                        "agent": step["agent"],
                        "phase": step["phase"],
                        "status": step.get("status"),
                        "message": step["message"],
                        "ts": step["ts"],
                    }
                    for step in steps
                ]
            )
            st.dataframe(steps_df, use_container_width=True, hide_index=True, height=360)
        else:
            st.info("No agent steps yet.")

    with detail_tabs[1]:
        report = get_latest_report(incident_id)
        if report:
            st.markdown(report["report_md"])
            left, right = st.columns(2)
            left.download_button(
                "Download report.json",
                data=json.dumps(report["report"], indent=2),
                file_name=f"incident_{incident_id}_report.json",
                mime="application/json",
                use_container_width=True,
            )
            right.download_button(
                "Download report.md",
                data=report["report_md"],
                file_name=f"incident_{incident_id}_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        else:
            st.info("No report generated yet.")

    with detail_tabs[2]:
        collector_steps = [step for step in steps if step["agent"] == "collector" and step["phase"] == "done"]
        analyst_retrieval = [step for step in steps if step["agent"] == "analyst" and step["phase"] == "retrieve"]
        if collector_steps:
            st.markdown("#### Retrieved logs")
            logs = collector_steps[-1].get("data", {}).get("logs", [])
            st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
        if analyst_retrieval:
            st.markdown("#### Knowledge snippets")
            snippets = analyst_retrieval[-1].get("data", {}).get("snippets", [])
            st.dataframe(pd.DataFrame(snippets), use_container_width=True, hide_index=True)
        if not collector_steps and not analyst_retrieval:
            st.info("No evidence collected yet.")

    with detail_tabs[3]:
        st.json(incident.get("payload", {}))


def main() -> None:
    init_db()
    st.set_page_config(page_title="Incident Responder", layout="wide")
    st.title("DevOps Incident Responder")
    provider_panel()
    create_incident_form()

    incidents = list_incidents(limit=200)
    if not incidents:
        st.info("No incidents yet. Create one above or POST to /api/incidents.")
        return

    left, right = st.columns([1, 2], gap="large")
    with left:
        st.subheader("Incidents")
        incident_df = pd.DataFrame(incidents)
        st.dataframe(incident_df, use_container_width=True, hide_index=True, height=320)
        options = [f"{row['id']} - {row['service']} [{row['status']}]" for row in incidents]
        selected = st.selectbox("Select incident", options)
        selected_id = int(selected.split(" - ", 1)[0])

    with right:
        render_incident_detail(selected_id)


if __name__ == "__main__":
    main()
