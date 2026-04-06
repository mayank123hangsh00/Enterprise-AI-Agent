"""Tests for the AI agent logic."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestSessionMemory:
    def test_add_and_retrieve(self):
        from app.agent.memory import SessionMemory

        mem = SessionMemory()
        mem.add_message("s1", "user", "Hello")
        mem.add_message("s1", "assistant", "Hi there!")
        history = mem.get_history("s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "Hi there!"

    def test_different_sessions_isolated(self):
        from app.agent.memory import SessionMemory

        mem = SessionMemory()
        mem.add_message("a", "user", "Session A message")
        mem.add_message("b", "user", "Session B message")
        assert len(mem.get_history("a")) == 1
        assert len(mem.get_history("b")) == 1
        assert mem.get_history("a")[0]["content"] == "Session A message"

    def test_clear_session(self):
        from app.agent.memory import SessionMemory

        mem = SessionMemory()
        mem.add_message("c", "user", "Hello")
        mem.clear("c")
        assert mem.get_history("c") == []

    def test_history_trimming(self):
        from app.agent.memory import MAX_HISTORY_MESSAGES, SessionMemory

        mem = SessionMemory()
        for i in range(MAX_HISTORY_MESSAGES + 10):
            mem.add_message("trim-test", "user", f"msg {i}")
        history = mem.get_history("trim-test")
        assert len(history) <= MAX_HISTORY_MESSAGES


class TestToolExecution:
    @patch("app.agent.tools.retrieve")
    def test_search_documents_tool(self, mock_retrieve):
        from app.agent.tools import execute_tool
        from app.rag.retriever import RetrievedChunk

        mock_retrieve.return_value = [
            MagicMock(text="Annual leave is 18 days.", source="company_leave_policy.txt", score=0.95)
        ]

        import json
        result_text, sources = execute_tool(
            "search_documents",
            json.dumps({"query": "annual leave days"}),
        )
        assert "leave_policy" in sources[0] or "policy" in sources[0].lower()
        assert len(result_text) > 0

    def test_unknown_tool_returns_error(self):
        from app.agent.tools import execute_tool

        result_text, sources = execute_tool("nonexistent_tool", "{}")
        assert "Unknown tool" in result_text
        assert sources == []

    def test_invalid_json_arguments(self):
        from app.agent.tools import execute_tool

        result_text, sources = execute_tool("search_documents", "not-valid-json")
        assert "Error" in result_text
