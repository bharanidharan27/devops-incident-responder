import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from app.config import RAG_COLLECTION_NAME, RAG_PERSIST_DIR, VECTOR_BACKEND
from app.rag.loader import load_knowledge_documents
from app.services.redaction import redact_text

FALLBACK_INDEX = "fallback_index.json"


class RagService:
    def __init__(self, persist_dir: str = RAG_PERSIST_DIR, collection_name: str = RAG_COLLECTION_NAME) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    def reindex(self) -> dict[str, Any]:
        docs = self._chunk_documents(load_knowledge_documents())
        if VECTOR_BACKEND.lower() == "chroma" and self._chroma_available():
            return self._reindex_chroma(docs)
        self._write_fallback(docs)
        return {"backend": "json-vector", "documents": len(docs)}

    def query(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        clean_query = redact_text(query)
        if VECTOR_BACKEND.lower() == "chroma" and self._chroma_available():
            try:
                results = self._query_chroma(clean_query, top_k)
                if results:
                    return results
            except Exception:
                pass

        docs = self._read_fallback()
        if not docs:
            docs = self._chunk_documents(load_knowledge_documents())
            self._write_fallback(docs)
        query_vector = self._embed(clean_query)
        scored = []
        for doc in docs:
            score = self._cosine(query_vector, doc["embedding"])
            scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "source": item["source"],
                "text": item["text"],
                "score": round(score, 4),
            }
            for score, item in scored[:top_k]
            if score > 0
        ]

    def _chunk_documents(self, docs: list[dict[str, Any]], chunk_size: int = 1200, overlap: int = 160) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for doc in docs:
            text = re.sub(r"\s+", " ", doc.get("text", "")).strip()
            if not text:
                continue
            start = 0
            index = 0
            while start < len(text):
                chunk = text[start : start + chunk_size]
                chunks.append(
                    {
                        "id": self._stable_id(f"{doc.get('source')}:{index}:{chunk[:80]}"),
                        "source": doc.get("source", "knowledge"),
                        "text": chunk,
                        "embedding": self._embed(chunk),
                    }
                )
                index += 1
                start += max(1, chunk_size - overlap)
        return chunks

    def _reindex_chroma(self, docs: list[dict[str, Any]]) -> dict[str, Any]:
        import chromadb

        client = chromadb.PersistentClient(path=str(self.persist_dir))
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        collection = client.get_or_create_collection(self.collection_name)
        if docs:
            collection.add(
                ids=[doc["id"] for doc in docs],
                documents=[doc["text"] for doc in docs],
                metadatas=[{"source": doc["source"]} for doc in docs],
                embeddings=[doc["embedding"] for doc in docs],
            )
        self._write_fallback(docs)
        return {"backend": "chroma", "documents": len(docs)}

    def _query_chroma(self, query: str, top_k: int) -> list[dict[str, Any]]:
        import chromadb

        client = chromadb.PersistentClient(path=str(self.persist_dir))
        collection = client.get_or_create_collection(self.collection_name)
        if collection.count() == 0:
            self.reindex()
        result = collection.query(query_embeddings=[self._embed(query)], n_results=top_k)
        docs = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        output = []
        for idx, text in enumerate(docs):
            distance = distances[idx] if idx < len(distances) else None
            output.append(
                {
                    "source": (metadatas[idx] or {}).get("source", "knowledge") if idx < len(metadatas) else "knowledge",
                    "text": text,
                    "score": round(1 - float(distance), 4) if distance is not None else None,
                }
            )
        return output

    def _write_fallback(self, docs: list[dict[str, Any]]) -> None:
        serializable = [
            {"id": doc["id"], "source": doc["source"], "text": doc["text"], "embedding": doc["embedding"]}
            for doc in docs
        ]
        (self.persist_dir / FALLBACK_INDEX).write_text(json.dumps(serializable), encoding="utf-8")

    def _read_fallback(self) -> list[dict[str, Any]]:
        path = self.persist_dir / FALLBACK_INDEX
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _chroma_available(self) -> bool:
        try:
            import chromadb  # noqa: F401
        except Exception:
            return False
        return True

    def _embed(self, text: str, dimensions: int = 384) -> list[float]:
        vector = [0.0] * dimensions
        for token in re.findall(r"[a-zA-Z0-9_./:-]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _cosine(self, left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    def _stable_id(self, value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()
