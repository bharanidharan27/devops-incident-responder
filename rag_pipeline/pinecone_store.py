import json
from pathlib import Path

from app.config import RAG_PERSIST_DIR


class PineconeStore:
    """Legacy-compatible local vector store.

    The old hackathon pipeline used Pinecone here. The product now defaults to
    local, no-cost storage, so this class preserves the old call shape while
    writing vectors to disk.
    """

    def __init__(self, index_name: str | None = None) -> None:
        self.index_name = index_name or "legacy_pipeline"
        self.path = Path(RAG_PERSIST_DIR) / f"{self.index_name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, embeddings: list[list[float]], chunks: list[str]) -> None:
        payload = [
            {"id": f"chunk-{idx}", "embedding": embedding, "text": chunk}
            for idx, (embedding, chunk) in enumerate(zip(embeddings, chunks))
        ]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        print(f"Upserted {len(payload)} chunks into local index {self.path}")

    def query(self, query_embedding: list[float], top_k: int = 5) -> list[str]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        scored = [
            (sum(a * b for a, b in zip(query_embedding, item["embedding"])), item["text"])
            for item in payload
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [text for score, text in scored[:top_k] if score > 0]
