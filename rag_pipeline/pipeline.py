from chunker import chunk_text
from clean_text import clean_text
from embedder import embed_chunks
from loader import load_pdf
from pinecone_store import PineconeStore

def build_rag_index(pdf_path: str):
    text = load_pdf(pdf_path)
    text = clean_text(text) 
    chunks = chunk_text(text, chunk_size=500)
    embeddings, chunks = embed_chunks(chunks)   # aligned lists

    store = PineconeStore()
    store.upsert(embeddings, chunks)

if __name__ == "__main__":
    build_rag_index("RAG Document.pdf")
