"""Tests for the RAG pipeline."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestDocumentLoader:
    def test_load_txt_document(self, tmp_path):
        from app.rag.loader import Document, load_txt

        sample = tmp_path / "sample.txt"
        sample.write_text("Hello world test content", encoding="utf-8")
        content = load_txt(sample)
        assert "Hello world" in content

    def test_load_documents_from_directory(self, tmp_path):
        from app.rag.loader import load_documents

        (tmp_path / "policy.txt").write_text("Leave policy: 18 days.", encoding="utf-8")
        (tmp_path / "handbook.txt").write_text("Code of conduct section.", encoding="utf-8")
        docs = load_documents(tmp_path)
        assert len(docs) == 2
        sources = [d.source for d in docs]
        assert "policy.txt" in sources
        assert "handbook.txt" in sources

    def test_skips_empty_documents(self, tmp_path):
        from app.rag.loader import load_documents

        (tmp_path / "empty.txt").write_text("   \n\n  ", encoding="utf-8")
        (tmp_path / "valid.txt").write_text("Valid content here.", encoding="utf-8")
        docs = load_documents(tmp_path)
        assert len(docs) == 1
        assert docs[0].source == "valid.txt"


class TestChunking:
    def test_chunk_produces_multiple_chunks(self):
        from app.rag.indexer import chunk_document
        from app.rag.loader import Document

        long_content = "\n\n".join([f"paragraph {i} " * 30 for i in range(20)])
        doc = Document(content=long_content, source="test.txt")
        chunks = chunk_document(doc, chunk_size=500, chunk_overlap=50)
        assert len(chunks) > 1

    def test_chunk_preserves_source(self):
        from app.rag.indexer import chunk_document
        from app.rag.loader import Document

        doc = Document(content="Some test content.\n\nMore content here.", source="source.txt")
        chunks = chunk_document(doc, chunk_size=500, chunk_overlap=50)
        for _, source in chunks:
            assert source == "source.txt"


class TestRetriever:
    def test_format_context(self):
        from app.rag.retriever import RetrievedChunk, format_context

        chunks = [
            RetrievedChunk(text="Leave is 18 days.", source="company_leave_policy.txt", score=0.92),
            RetrievedChunk(text="Remote work requires VPN.", source="remote_work_policy.txt", score=0.81),
        ]
        context = format_context(chunks)
        assert "Source 1:" in context
        assert "Source 2:" in context
        assert "Leave is 18 days." in context
        assert "Remote work requires VPN." in context
