"""Embeddings wrapper — using free local sentence-transformers."""
from __future__ import annotations

import logging
from typing import List

from app.config import get_settings

logger = logging.getLogger(__name__)

# Cache model at module level so it only loads into memory once
_embedding_model = None

def _get_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        logger.info("Loading local embedding model: %s", settings.embedding_model)
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts using the local sentence-transformer model."""
    if not texts:
        return []
    
    model = _get_model()
    # encode() returns a numpy array, we convert to lists of floats
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()

def embed_query(text: str) -> List[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]
