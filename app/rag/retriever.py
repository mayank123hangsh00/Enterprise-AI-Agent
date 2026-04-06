"""Retriever — searches FAISS index for relevant document chunks."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import faiss
import numpy as np

from app.config import get_settings
from app.rag.embeddings import embed_query
from app.rag.indexer import load_index

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float  # cosine similarity, 0–1


# Module-level cache so the index is loaded once at startup
_index: faiss.Index | None = None
_metadata: List[dict] | None = None


def init_retriever() -> None:
    """Load the vector index into memory (called at app startup)."""
    global _index, _metadata
    _index, _metadata = load_index()
    logger.info("Retriever ready — %d indexed chunks", _index.ntotal)


def retrieve(query: str, top_k: int | None = None) -> List[RetrievedChunk]:
    """
    Search the index for chunks most relevant to *query*.
    Returns a list of RetrievedChunk ordered by descending similarity.
    """
    if _index is None or _metadata is None:
        raise RuntimeError("Retriever not initialised. Call init_retriever() first.")

    settings = get_settings()
    k = top_k or settings.top_k_results

    # Embed query and normalize for cosine similarity
    query_vec = np.array([embed_query(query)], dtype="float32")
    faiss.normalize_L2(query_vec)

    scores, indices = _index.search(query_vec, k)

    results: List[RetrievedChunk] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue  # FAISS returns -1 for empty slots
        meta = _metadata[idx]
        results.append(
            RetrievedChunk(
                text=meta["text"],
                source=meta["source"],
                score=float(score),
            )
        )

    logger.debug(
        "Retrieved %d chunks for query: '%s...' (top score: %.3f)",
        len(results),
        query[:60],
        results[0].score if results else 0,
    )
    return results


def format_context(chunks: List[RetrievedChunk]) -> str:
    """Format retrieved chunks into a context string for the LLM prompt."""
    parts: List[str] = []
    for i, chunk in enumerate(chunks, 1):
        source_label = chunk.source.replace("_", " ").replace(".txt", "").replace(".pdf", "").title()
        parts.append(f"[Source {i}: {source_label}]\n{chunk.text}")
    return "\n\n---\n\n".join(parts)
