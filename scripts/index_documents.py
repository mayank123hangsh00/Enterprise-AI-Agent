#!/usr/bin/env python
"""
Build the FAISS vector index from documents in the documents/ directory.

Usage:
    python scripts/index_documents.py

Run this once before starting the server, and again whenever documents change.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Make the project root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.indexer import build_index
from app.rag.loader import load_documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=" * 60)
    logger.info("AcmeAssist — Document Indexing Script")
    logger.info("=" * 60)

    documents = load_documents()
    if not documents:
        logger.error("No documents found! Make sure the documents/ directory contains .txt or .pdf files.")
        sys.exit(1)

    logger.info("Loaded %d document(s):", len(documents))
    for doc in documents:
        logger.info("  • %s (%d chars)", doc.source, len(doc.content))

    logger.info("Building FAISS index...")
    build_index(documents)

    logger.info("=" * 60)
    logger.info("Indexing complete! You can now start the server:")
    logger.info("  uvicorn app.main:app --reload")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
