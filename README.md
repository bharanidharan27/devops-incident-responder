# DevOps Incident Responder

Local-first incident triage product for DevOps/SRE workflows. It accepts manual or webhook incidents, collects related logs, retrieves local knowledge-base context, runs a provider-agnostic RCA analysis, and shows every step in Streamlit.

## What It Does

- Manual and webhook-style incident intake through FastAPI.
- Background worker that processes `OPEN` incidents end to end.
- Collector, analyst, and supervisor stages with persisted timeline rows.
- Local RAG by default using Chroma when installed, with a JSON vector fallback.
- Free-first AI adapter through LiteLLM: Gemini, Groq, Hugging Face, or Ollama can be swapped by `.env` only.
- Deterministic rule-based fallback when no AI provider is configured.
- Streamlit UI for incident creation, timeline, evidence, RCA reports, and provider status.

## Recommended Next Product Move

CloudWatch is the right next integration if the target customer is AWS-based SRE/DevOps teams. Keep it as a source adapter, not a hard dependency: the app should still support manual/webhook intake and local demo logs so it remains easy to evaluate without AWS credentials.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

python scripts/seed_logs.py
python scripts/seed_rag_examples.py
python scripts/seed_incidents.py

python -m app.runner --once
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
python -m streamlit run ui/streamlit_app.py --server.headless true
```

The app works without OpenAI credentials. If no free hosted or local provider is configured, the analyst uses the rule-based fallback and still produces a report.

On Windows PowerShell, the API command is expected to keep running. Wait for `Uvicorn running on http://127.0.0.1:8000`; press `Ctrl+C` only when you want to stop it.

## API

- `POST /api/incidents`
- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `GET /api/incidents/{id}/steps`
- `GET /api/incidents/{id}/report`
- `POST /api/incidents/{id}/run`
- `POST /api/rag/reindex`
- `POST /api/webhooks/alertmanager`

Example incident:

```json
{
  "service": "payment-service",
  "environment": "prod",
  "severity": "CRITICAL",
  "title": "Checkout HTTP 500 spike",
  "description": "HTTP 500 errors increased on checkout",
  "alert_type": "HTTP 500",
  "source": "webhook",
  "external_id": "alert-123",
  "payload": {"region": "us-east-1"}
}
```

## Provider Switching

Set `LLM_MODEL` and `LLM_FALLBACK_MODELS` in `.env`.

```env
LLM_MODEL=gemini/gemini-2.5-flash-lite
LLM_FALLBACK_MODELS=groq/qwen/qwen3-32b,ollama/gemma3
GEMINI_API_KEY=
GROQ_API_KEY=
OLLAMA_ENABLED=false
```

No code changes are required to switch providers. Hosted logs are redacted before they are sent to an AI provider.

## CloudWatch Logs Setup

Local seeded logs are still the default. To read from AWS CloudWatch Logs, configure `.env`:

```env
LOGS_MODE=cloudwatch
AWS_REGION=us-east-1
AWS_PROFILE=your-profile
CLOUDWATCH_LOG_GROUPS=/aws/lambda/payment-service,/aws/ecs/checkout
CLOUDWATCH_LOOKBACK_MINUTES=30
CLOUDWATCH_MAX_EVENTS=100
CLOUDWATCH_FALLBACK_TO_LOCAL=true
```

The AWS identity needs read-only CloudWatch Logs permissions:

```json
{
  "Effect": "Allow",
  "Action": [
    "logs:FilterLogEvents",
    "logs:DescribeLogGroups",
    "logs:DescribeLogStreams"
  ],
  "Resource": "*"
}
```

Webhook incidents can override the default log group:

```json
{
  "service": "payment-service",
  "severity": "CRITICAL",
  "alert_type": "HTTP 500",
  "payload": {
    "cloudwatch_log_groups": ["/aws/lambda/payment-service"],
    "cloudwatch_filter_pattern": "ERROR",
    "cloudwatch_log_stream_prefix": "2026/05/16"
  }
}
```

If CloudWatch credentials or log groups are missing and `CLOUDWATCH_FALLBACK_TO_LOCAL=true`, the collector records a warning step and falls back to local sample logs.

## Simulate Alertmanager + CloudWatch End-to-End

Prometheus Alertmanager is open source and supports generic webhook receivers, which makes it the best free first integration path. PagerDuty can be added later as another webhook parser, but Alertmanager gives us a no-license route for real or simulated alerts.

1. Configure `.env`:

```env
LOGS_MODE=cloudwatch
AWS_PROFILE=default
AWS_REGION=us-east-1
CLOUDWATCH_LOG_GROUPS=/devops-incident-responder/payment-service
CLOUDWATCH_STREAM_PREFIX=demo
WEBHOOK_AUTO_PROCESS=true
```

2. Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

3. Rebuild the local RAG index so the demo runbooks are available:

```powershell
.\.venv\Scripts\python.exe -m app.rag.build_index
```

4. In another terminal, write demo logs into CloudWatch:

```powershell
.\.venv\Scripts\python.exe scripts/simulate_cloudwatch_logs.py --scenario http500 --log-group /devops-incident-responder/payment-service --stream-prefix demo
```

5. Send an Alertmanager-compatible webhook:

```powershell
.\.venv\Scripts\python.exe scripts/simulate_alertmanager_alert.py --scenario http500 --log-group /devops-incident-responder/payment-service --stream-prefix demo
```

The webhook creates the incident automatically. With `WEBHOOK_AUTO_PROCESS=true`, the API immediately runs the collector/analyst/supervisor flow, retrieves matching CloudWatch events, and writes the report.

For a faster demo, omit `--scenario` to pick randomly:

```powershell
.\.venv\Scripts\python.exe scripts/simulate_cloudwatch_logs.py --log-group /devops-incident-responder/payment-service --stream-prefix demo
.\.venv\Scripts\python.exe scripts/simulate_alertmanager_alert.py --log-group /devops-incident-responder/payment-service --stream-prefix demo
```

The CloudWatch simulator writes the selected scenario to `.demo_scenario`, and the Alertmanager simulator reads that file by default, so the two commands still match even when the scenario is random.

Scenario options:

- `http500`
- `db`
- `oom`
- `latency`
- `auth`
- `queue`

CloudWatch ingestion may create small AWS charges. The simulator sets a short retention policy by default using `CLOUDWATCH_SIMULATION_RETENTION_DAYS=1`.
