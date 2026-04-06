"""FAISS indexer — chunks documents and builds a searchable vector index."""
from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np

from app.config import get_settings
from app.rag.embeddings import embed_texts
from app.rag.loader import Document

logger = logging.getLogger(__name__)

VECTORSTORE_DIR = Path(__file__).resolve().parents[2] / "vectorstore"
INDEX_FILE = VECTORSTORE_DIR / "index.faiss"
METADATA_FILE = VECTORSTORE_DIR / "metadata.pkl"


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
        # If adding this paragraph would exceed chunk_size, save current chunk
        if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
            chunks.append((current_chunk.strip(), source))
            # Keep the overlap portion
            words = current_chunk.split()
            overlap_words = words[-chunk_overlap // 5 :] if chunk_overlap else []
            current_chunk = " ".join(overlap_words) + "\n\n" + paragraph
        else:
            current_chunk = (current_chunk + "\n\n" + paragraph).strip() if current_chunk else paragraph

    if current_chunk.strip():
        chunks.append((current_chunk.strip(), source))

    return chunks


def build_index(documents: List[Document]) -> None:
    """Chunk all documents, embed them, and save FAISS index to disk."""
    settings = get_settings()
    VECTORSTORE_DIR.mkdir(exist_ok=True)

    all_chunks: List[str] = []
    all_metadata: List[dict] = []

    for doc in documents:
        chunks = chunk_document(doc, settings.chunk_size, settings.chunk_overlap)
        for chunk_text, source in chunks:
            all_chunks.append(chunk_text)
            all_metadata.append({"source": source, "text": chunk_text})

    logger.info("Total chunks: %d across %d documents", len(all_chunks), len(documents))

    # Generate embeddings
    logger.info("Generating embeddings (this may take a moment)...")
    embeddings = embed_texts(all_chunks)

    # Build FAISS index
    dim = len(embeddings[0])
    matrix = np.array(embeddings, dtype="float32")

    # Normalize for cosine similarity
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(dim)  # Inner product = cosine on normalized vectors
    index.add(matrix)

    # Persist to disk
    faiss.write_index(index, str(INDEX_FILE))
    with open(METADATA_FILE, "wb") as f:
        pickle.dump(all_metadata, f)

    logger.info("Index saved: %d vectors, dim=%d", index.ntotal, dim)


def load_index() -> Tuple[faiss.Index, List[dict]]:
    """Load the FAISS index and metadata from disk."""
    if not INDEX_FILE.exists() or not METADATA_FILE.exists():
        raise FileNotFoundError(
            "Vector index not found. Run: python scripts/index_documents.py"
        )

    index = faiss.read_index(str(INDEX_FILE))
    with open(METADATA_FILE, "rb") as f:
        metadata = pickle.load(f)

    logger.info("Index loaded: %d vectors", index.ntotal)
    return index, metadata
