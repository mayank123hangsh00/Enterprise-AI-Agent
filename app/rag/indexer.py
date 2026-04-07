"""Supabase Indexer — chunks documents and pushes embeddings to Supabase Cloud using HTTPX."""
from __future__ import annotations

import logging
from typing import List, Tuple
import httpx

from app.config import get_settings
from app.rag.embeddings import embed_texts
from app.rag.loader import Document

logger = logging.getLogger(__name__)

def chunk_document(doc: Document, chunk_size: int, chunk_overlap: int) -> List[Tuple[str, str]]:
    """
    Split a document into overlapping text chunks.
    Returns list of (chunk_text, source_filename) tuples.
    """
    text = doc.content
    source = doc.source
    chunks: List[Tuple[str, str]] = []

    # Split by paragraphs first, then merge into chunks
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    current_chunk = ""
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
            chunks.append((current_chunk.strip(), source))
            words = current_chunk.split()
            overlap_words = words[-chunk_overlap // 5 :] if chunk_overlap else []
            current_chunk = " ".join(overlap_words) + "\n\n" + paragraph
        else:
            current_chunk = (current_chunk + "\n\n" + paragraph).strip() if current_chunk else paragraph

    if current_chunk.strip():
        chunks.append((current_chunk.strip(), source))

    return chunks


def build_index(documents: List[Document]) -> None:
    """Chunk all documents, embed them, and push to Supabase via REST API."""
    settings = get_settings()
    
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

    # REST URL for Supabase PostgREST
    # Example: https://xyz.supabase.co/rest/v1/document_chunks
    supabase_rest_url = f"{settings.supabase_url.rstrip('/')}/rest/v1/document_chunks"
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    all_chunks: List[str] = []
    all_metadata: List[dict] = []

    for doc in documents:
        chunks = chunk_document(doc, settings.chunk_size, settings.chunk_overlap)
        for chunk_text, source in chunks:
            all_chunks.append(chunk_text)
            all_metadata.append({"source": source, "content": chunk_text})

    logger.info("Total chunks: %d across %d documents", len(all_chunks), len(documents))

    # Generate embeddings
    logger.info("Generating embeddings (this may take a moment)...")
    embeddings = embed_texts(all_chunks)

    # Prepare data for Supabase
    data_to_insert = []
    for meta, emb in zip(all_metadata, embeddings):
        data_to_insert.append({
            "content": meta["content"],
            "source": meta["source"],
            "embedding": emb.tolist() if hasattr(emb, 'tolist') else list(emb)
        })

    # Bulk insert into Supabase via HTTPX
    logger.info("Pushing to Supabase Cloud...")
    batch_size = 100
    with httpx.Client() as client:
        for i in range(0, len(data_to_insert), batch_size):
            batch = data_to_insert[i : i + batch_size]
            response = client.post(supabase_rest_url, json=batch, headers=headers)
            response.raise_for_status()

    logger.info("Indexing complete! Successfully pushed to Supabase.")
