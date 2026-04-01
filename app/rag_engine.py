"""
RAG Engine — ChromaDB vector store for remedy retrieval.

Embeds all remedy records using sentence-transformers and stores them in a
persistent ChromaDB collection.  At query time, returns the top-k most
similar records along with a relevance score so the caller can decide
whether to answer locally (Ollama) or fall back to Gemini.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
CHROMA_DIR = Path(__file__).resolve().parent.parent / "vectorstore"
COLLECTION_NAME = "remedies"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "raw_data" / "merged_dataset.json"
RELEVANCE_THRESHOLD = 1.0  # L2 distance — lower is better; ≤1.0 = "good match"


def _build_document(row: dict) -> str:
    """Concatenate meaningful fields into a single searchable document."""
    parts = []
    for key in ("problem", "symptoms", "possible_causes", "remedy", "ingredients", "preparation"):
        val = str(row.get(key, "")).strip()
        if val:
            parts.append(f"{key}: {val}")
    return "\n".join(parts)


def _build_metadata(row: dict) -> dict:
    """Extract lightweight metadata stored alongside each vector."""
    return {
        "id": str(row.get("id", "")),
        "problem": str(row.get("problem", ""))[:200],
        "source": str(row.get("source", "")),
        "traditional_system": str(row.get("traditional_system", "")),
        "severity_level": str(row.get("severity_level", "")),
        "doctor_consult": str(row.get("doctor_consult", False)),
        "completeness_score": float(row.get("completeness_score", 0)),
    }


class RAGEngine:
    """Thin wrapper around ChromaDB for remedy retrieval."""

    def __init__(
        self,
        persist_dir: str | Path = CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        # Lazy-load the embedding function so import stays fast
        self._ef: Optional[object] = None
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[object] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_ef(self):
        if self._ef is None:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            self._ef = SentenceTransformerEmbeddingFunction(model_name=self.embedding_model)
        return self._ef

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._get_ef(),
                metadata={"hnsw:space": "l2"},
            )
        return self._collection

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def index_dataset(self, dataset_path: str | Path = DEFAULT_DATASET, batch_size: int = 128) -> int:
        """Read the JSON dataset and upsert all records into ChromaDB.

        Returns the number of records indexed.
        """
        data = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
        rows = [r for r in data if isinstance(r, dict)]
        if not rows:
            return 0

        collection = self._get_collection()

        # Process in batches
        indexed = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            ids = [str(r.get("id", f"row_{start + i}")) for i, r in enumerate(batch)]
            documents = [_build_document(r) for r in batch]
            metadatas = [_build_metadata(r) for r in batch]
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            indexed += len(batch)

        return indexed

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def query(
        self,
        text: str,
        top_k: int = 5,
    ) -> List[Tuple[Dict, float]]:
        """Return up to *top_k* results as (metadata_dict, distance) pairs.

        Lower distance = more relevant.
        """
        collection = self._get_collection()
        results = collection.query(query_texts=[text], n_results=top_k, include=["documents", "metadatas", "distances"])

        hits: List[Tuple[Dict, float]] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return hits

        for idx in range(len(results["ids"][0])):
            meta = results["metadatas"][0][idx] if results["metadatas"] else {}
            doc = results["documents"][0][idx] if results["documents"] else ""
            dist = results["distances"][0][idx] if results["distances"] else 999.0
            meta["_document"] = doc
            hits.append((meta, dist))
        return hits

    def retrieve_context(
        self,
        query_text: str,
        top_k: int = 3,
        threshold: float = RELEVANCE_THRESHOLD,
    ) -> Tuple[str, bool]:
        """High-level helper: returns (context_string, is_relevant).

        *is_relevant* is True when at least one hit is within *threshold*,
        meaning the answer can likely come from the local dataset + Ollama.
        """
        hits = self.query(query_text, top_k=top_k)
        if not hits:
            return "", False

        best_distance = hits[0][1]
        is_relevant = best_distance <= threshold

        blocks = []
        for i, (meta, dist) in enumerate(hits, 1):
            doc = meta.pop("_document", "")
            # Trim long documents
            trimmed = " ".join(doc.split())[:600]
            blocks.append(f"[Match {i}  dist={dist:.3f}]\n{trimmed}")

        context = "\n\n".join(blocks)
        return context, is_relevant

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def count(self) -> int:
        """Return the number of vectors currently stored."""
        return self._get_collection().count()

    def reset(self):
        """Delete and recreate the collection (useful for re-indexing)."""
        client = self._get_client()
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = None


# ---------------------------------------------------------------------------
# Standalone: build the index from CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build / rebuild the RAG vector index.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to merged_dataset.json")
    parser.add_argument("--persist-dir", default=str(CHROMA_DIR), help="ChromaDB storage directory")
    parser.add_argument("--reset", action="store_true", help="Wipe existing index before rebuilding")
    args = parser.parse_args()

    engine = RAGEngine(persist_dir=args.persist_dir)
    if args.reset:
        print("[rag] Resetting existing index …")
        engine.reset()

    print(f"[rag] Indexing dataset: {args.dataset}")
    n = engine.index_dataset(args.dataset)
    print(f"[rag] Indexed {n} records.  Total in store: {engine.count()}")
