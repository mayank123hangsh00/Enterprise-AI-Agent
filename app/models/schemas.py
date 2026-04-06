"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for conversation continuity. A new one is created if omitted.",
    )

    model_config = {"json_schema_extra": {"example": {"query": "What is our leave policy?", "session_id": "user-abc-123"}}}


class AskResponse(BaseModel):
    answer: str = Field(..., description="Agent's response")
    source: List[str] = Field(default_factory=list, description="Source document filenames used")
    session_id: str = Field(..., description="Session ID for follow-up questions")

    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "According to the Leave Policy, employees with 0–2 years of service receive 18 working days of annual leave per year.",
                "source": ["company_leave_policy.txt"],
                "session_id": "user-abc-123",
            }
        }
    }


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    index_loaded: bool = False
