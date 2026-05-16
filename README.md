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
