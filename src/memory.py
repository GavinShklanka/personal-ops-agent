"""
Memory — Personal Ops Agent
Vector memory using ChromaDB so Klara remembers past context across sessions.
Stores every conversation turn and surfaces relevant history when answering questions.

Gracefully degrades to no-op if ChromaDB is unavailable.
"""

import datetime
import uuid
from pathlib import Path

CHROMA_DIR = Path(__file__).parent.parent / "db" / "chroma"
COLLECTION_NAME = "klara_memory"

_client = None
_collection = None


def _get_collection():
    """Lazy-init the ChromaDB client and collection. Returns None on failure."""
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        return _collection
    except Exception:
        return None


def store_turn(session_id: str, role: str, content: str) -> bool:
    """
    Persist a single conversation turn to ChromaDB.
    role: 'user' or 'assistant'
    Returns True on success, False if ChromaDB is unavailable.
    """
    collection = _get_collection()
    if collection is None:
        return False

    # Skip very short or tool-plumbing messages
    if len(content.strip()) < 20:
        return False

    try:
        collection.add(
            documents=[content],
            metadatas=[
                {
                    "session_id": session_id,
                    "role": role,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
            ],
            ids=[str(uuid.uuid4())],
        )
        return True
    except Exception:
        return False


def query_relevant(query_text: str, n_results: int = 4, exclude_session: str = "") -> list[dict]:
    """
    Return the most semantically relevant past turns for a given query.
    Each result: {"role": ..., "content": ..., "timestamp": ..., "session_id": ...}

    exclude_session: pass the current session_id to avoid returning turns from
    the active conversation (they're already in the context window).
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        total = collection.count()
        if total == 0:
            return []

        fetch = min(n_results + 4, total)
        results = collection.query(
            query_texts=[query_text],
            n_results=fetch,
            include=["documents", "metadatas"],
        )

        items = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            if exclude_session and meta.get("session_id") == exclude_session:
                continue
            items.append(
                {
                    "role": meta.get("role", "unknown"),
                    "content": doc,
                    "timestamp": meta.get("timestamp", ""),
                    "session_id": meta.get("session_id", ""),
                }
            )
            if len(items) >= n_results:
                break

        return items
    except Exception:
        return []


def format_memories_for_prompt(memories: list[dict]) -> str:
    """Format retrieved memories into a compact block for the system prompt."""
    if not memories:
        return ""
    lines = ["Relevant context from past conversations:"]
    for m in memories:
        ts = m["timestamp"][:10] if m["timestamp"] else "?"
        role_label = "Gavin" if m["role"] == "user" else "Klara"
        lines.append(f"  [{ts}] {role_label}: {m['content'][:200].strip()}")
    return "\n".join(lines)


def is_available() -> bool:
    """Return True if ChromaDB is installed and functional."""
    return _get_collection() is not None
