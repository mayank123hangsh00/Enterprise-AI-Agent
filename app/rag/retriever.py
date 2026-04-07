"""Supabase Retriever — searches Supabase Cloud vector index for relevant document chunks via HTTPX."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List
import httpx

from app.config import get_settings
from app.rag.embeddings import embed_query

logger = logging.getLogger(__name__)

@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float  # similarity, 0–1

def init_retriever() -> None:
    """Check Supabase configuration existence."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    logger.info("Supabase settings verified.")


def retrieve(query: str, top_k: int | None = None) -> List[RetrievedChunk]:
    """
    Search Supabase Cloud via RPC call using HTTPX.
    Returns a list of RetrievedChunk ordered by descending similarity.
    """
    settings = get_settings()
    k = top_k or settings.top_k_results

    # RPC URL for Supabase
    # Example: https://xyz.supabase.co/rest/v1/rpc/match_documents
    supabase_rpc_url = f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/match_documents"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json"
    }

    # Embed query and convert to list for SQL vector math
    query_emb = embed_query(query)
    query_vector = query_emb.tolist() if hasattr(query_emb, 'tolist') else list(query_emb)

    try:
        with httpx.Client() as client:
            payload = {
                "query_embedding": query_vector,
                "match_threshold": 0.5,
                "match_count": k,
            }
            response = client.post(supabase_rpc_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        results: List[RetrievedChunk] = []
        for row in data:
            results.append(
                RetrievedChunk(
                    text=row["content"],
                    source=row["source"],
                    score=float(row["similarity"]),
                )
            )

        if results:
            logger.debug(
                "Retrieved %d chunks from Supabase for query: '%s...' (top score: %.3f)",
                len(results),
                query[:60],
                results[0].score,
            )
        return results

    except Exception as e:
        logger.error(f"Error retrieving from Supabase: {e}")
        return []


def format_context(chunks: List[RetrievedChunk]) -> str:
    """Format retrieved chunks into a context string for the LLM prompt."""
    parts: List[str] = []
    for i, chunk in enumerate(chunks, 1):
        source_label = chunk.source.replace("_", " ").replace(".txt", "").replace(".pdf", "").title()
        parts.append(f"[Source {i}: {source_label}]\n{chunk.text}")
    return "\n\n---\n\n".join(parts)
