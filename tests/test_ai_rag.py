from app.rag.service import RagService
from app.services.ai_client import AIClient
from app.services.redaction import redact_text


def test_rag_retrieves_local_knowledge(monkeypatch, tmp_path):
    monkeypatch.setenv("RAG_PERSIST_DIR", str(tmp_path / "rag"))
    service = RagService(persist_dir=str(tmp_path / "rag"))

    result = service.reindex()
    matches = service.query("postgres connection refused", top_k=2)

    assert result["documents"] >= 1
    assert matches
    assert "connection refused" in matches[0]["text"].lower()


def test_ai_client_falls_back_without_litellm_or_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    client = AIClient(enabled=True)

    result = client.generate_rca(
        {"id": 1, "service": "payment-service"},
        {"logs": []},
        [],
        {
            "issue": "HTTP 500 application error",
            "root_cause": "Application bug",
            "mitigations": ["Rollback"],
            "evidence": ["Matched log pattern"],
            "confidence": 0.75,
        },
    )

    assert result["provider"] == "rules"
    assert result["issue"] == "HTTP 500 application error"
    assert result["fallback_reason"]


def test_redaction_masks_common_secret_shapes():
    text = "token=abc12345678901234567890 sk-abc123456789012345678901234"

    redacted = redact_text(text)

    assert "abc12345678901234567890" not in redacted
    assert "sk-abc" not in redacted
