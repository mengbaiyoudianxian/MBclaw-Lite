import json
import os
import chromadb
from chromadb.config import Settings
from app.config import DATA_DIR

CHROMA_PATH = os.path.join(DATA_DIR, "chroma")
_collections = {}


def _get_client() -> chromadb.PersistentClient:
    os.makedirs(CHROMA_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False))


def get_collection(name: str) -> chromadb.Collection:
    if name not in _collections:
        client = _get_client()
        _collections[name] = client.get_or_create_collection(name=name)
    return _collections[name]


def index_text(collection_name: str, doc_id: str, text: str, metadata: dict | None = None):
    """Index text into a ChromaDB collection. doc_id must be unique."""
    col = get_collection(collection_name)
    col.upsert(documents=[text], ids=[doc_id], metadatas=[metadata] if metadata else None)


def search_similar(collection_name: str, query: str, top_k: int = 5) -> list[dict]:
    """Search for similar documents. Returns [{id, distance, metadata, document}]."""
    col = get_collection(collection_name)
    results = col.query(query_texts=[query], n_results=top_k)
    items = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            items.append({
                "id": doc_id,
                "distance": results["distances"][0][i] if results["distances"] else None,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else None,
                "document": results["documents"][0][i] if results["documents"] else None,
            })
    return items


def delete_text(collection_name: str, doc_id: str):
    col = get_collection(collection_name)
    col.delete(ids=[doc_id])
