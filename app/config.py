import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _sqlite_file_from_url(db_url: str) -> str | None:
    if not db_url.startswith("sqlite:///"):
        return None
    raw = db_url.removeprefix("sqlite:///")
    return raw or "dev.db"


def _resolve_path(raw: str) -> str:
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


ENV = os.getenv("ENV", "dev")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

_db_url = os.getenv("DB_URL", "sqlite:///dev.db")
DB_FILE = _resolve_path(os.getenv("DB_FILE") or _sqlite_file_from_url(_db_url) or "dev.db")
DB_URL = f"sqlite:///{DB_FILE}"

VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "chroma")
RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "incident_playbooks")
RAG_PERSIST_DIR = _resolve_path(os.getenv("RAG_PERSIST_DIR", ".chromadb"))
RAG_DATA_DIR = _resolve_path(os.getenv("RAG_DATA_DIR", "app/rag/data"))

AI_ENABLED = _bool_env("AI_ENABLED", True)
ALLOW_PAID_PROVIDERS = _bool_env("ALLOW_PAID_PROVIDERS", False)
FREE_FIRST_LLM_MODEL = "gemini/gemini-2.5-flash-lite"
_configured_llm_model = os.getenv("LLM_MODEL", FREE_FIRST_LLM_MODEL)
if not ALLOW_PAID_PROVIDERS and (
    _configured_llm_model.startswith("gpt-") or _configured_llm_model.startswith("openai/")
):
    LLM_MODEL = FREE_FIRST_LLM_MODEL
else:
    LLM_MODEL = _configured_llm_model
LLM_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv("LLM_FALLBACK_MODELS", "groq/qwen/qwen3-32b,ollama/gemma3").split(",")
    if model.strip()
]
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

LOGS_MODE = os.getenv("LOGS_MODE", "local")
LOGS_LOCAL_ROOT = _resolve_path(os.getenv("LOGS_LOCAL_ROOT", "app/logs"))

USE_REAL_CLOUDWATCH = _bool_env("USE_REAL_CLOUDWATCH", False)
CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP", "/aws/lambda/demo")

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_BASE_URL = os.getenv("API_BASE_URL", f"http://{API_HOST}:{API_PORT}")
