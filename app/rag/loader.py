import json
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, RAG_DATA_DIR


def load_knowledge_documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    data_dir = Path(RAG_DATA_DIR)
    if data_dir.exists():
        for path in sorted(data_dir.rglob("*")):
            if path.suffix.lower() == ".jsonl":
                docs.extend(_load_jsonl(path))
            elif path.suffix.lower() in {".md", ".txt"}:
                docs.append({"source": str(path), "text": path.read_text(encoding="utf-8", errors="ignore")})
            elif path.suffix.lower() == ".pdf":
                text = _load_pdf(path)
                if text:
                    docs.append({"source": str(path), "text": text})

    legacy_pdf = BASE_DIR / "rag_pipeline" / "RAG Document.pdf"
    if legacy_pdf.exists():
        text = _load_pdf(legacy_pdf)
        if text:
            docs.append({"source": str(legacy_pdf), "text": text})
    return [doc for doc in docs if doc.get("text")]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = item.get("text")
        if not text:
            text = "\n".join(
                [
                    f"Pattern: {item.get('pattern', '')}",
                    f"Root cause: {item.get('root_cause', '')}",
                    "Mitigation: " + ", ".join(item.get("mitigation") or item.get("mitigations") or []),
                ]
            )
        docs.append({"source": f"{path}:{line_no}", "text": text, "metadata": item})
    return docs


def _load_pdf(path: Path) -> str:
    try:
        import PyPDF2
    except Exception:
        return ""

    text_parts: list[str] = []
    try:
        with path.open("rb") as handle:
            reader = PyPDF2.PdfReader(handle)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
    except Exception:
        return ""
    return "\n".join(text_parts)
