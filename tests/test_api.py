"""Integration tests for the FastAPI endpoints."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# Patch the retriever init so tests don't need a real index
@pytest.fixture(autouse=True)
def mock_retriever():
    with patch("app.main.init_retriever") as mock_init, \
         patch("app.api.routes._index", MagicMock()):
        yield mock_init


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_root_redirects_to_docs(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (302, 307)


class TestAskEndpoint:
    @patch("app.api.routes.agent")
    def test_ask_returns_structured_response(self, mock_agent, client):
        mock_agent.run.return_value = MagicMock(
            answer="You get 18 days of annual leave.",
            source=["company_leave_policy.txt"],
            session_id="test-session-1",
        )
        response = client.post("/ask", json={"query": "How many leave days do I get?"})
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "source" in data
        assert "session_id" in data
        assert isinstance(data["source"], list)

    @patch("app.api.routes.agent")
    def test_ask_with_session_id(self, mock_agent, client):
        mock_agent.run.return_value = MagicMock(
            answer="VPN is required for remote access.",
            source=["it_security_guidelines.txt"],
            session_id="my-session",
        )
        response = client.post(
            "/ask",
            json={"query": "Do I need VPN?", "session_id": "my-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "my-session"

    def test_ask_empty_query_fails_validation(self, client):
        response = client.post("/ask", json={"query": ""})
        assert response.status_code == 422  # Pydantic validation error

    def test_ask_missing_query_fails_validation(self, client):
        response = client.post("/ask", json={})
        assert response.status_code == 422
