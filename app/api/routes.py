"""API routes — POST /ask and GET /health."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.agent.core import agent
from app.models.schemas import AskRequest, AskResponse, HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint — used by Azure App Service and load balancers."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        index_loaded=True,  # Supabase is always cloud-ready
    )


@router.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask(request: AskRequest):
    """
    Submit a query to the AI agent.

    The agent will:
    - Search internal documents if the query relates to company policies or products.
    - Answer directly using LLM for general knowledge questions.
    - Maintain conversation context across calls with the same session_id.
    """
    logger.info("POST /ask | session=%s | query='%s...'", request.session_id, request.query[:80])

    try:
        result = agent.run(query=request.query, session_id=request.session_id)
    except Exception as exc:
        logger.exception("Agent error for query: %s", request.query)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    return AskResponse(
        answer=result.answer,
        source=result.source,
        session_id=result.session_id,
    )
