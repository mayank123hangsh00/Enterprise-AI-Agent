"""API routes — /ask, /stream, /upload, /history, /sessions, /health."""
from __future__ import annotations

import io
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.agent.core import agent
from app.api.auth import get_current_user
from app.models.schemas import (
    AskRequest, AskResponse, HealthResponse,
    UploadResponse, ChatHistoryResponse, ChatMessage,
    SessionsResponse, SessionSummary,
)
from app.rag.indexer import build_index
from app.rag.loader import Document
from app.services.chat_history import (
    save_message, get_session_messages, get_user_sessions
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check — no auth required, used by AWS ELB."""
    return HealthResponse(status="ok", version="2.0.0", index_loaded=True)


# ── Ask (non-streaming, saves to history) ─────────────────────────────────────

@router.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask(request: AskRequest, user: dict = Depends(get_current_user)):
    """Submit a query to the AI agent. Requires Bearer token."""
    logger.info("POST /ask | user=%s | session=%s | query='%s...'",
                user["email"], request.session_id, request.query[:80])

    try:
        result = agent.run(query=request.query, session_id=request.session_id)
    except Exception as exc:
        logger.exception("Agent error")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    # Persist to Supabase chat history
    await save_message(result.session_id, user["id"], "user", request.query)
    await save_message(result.session_id, user["id"], "assistant", result.answer, result.source)

    return AskResponse(
        answer=result.answer,
        source=result.source,
        session_id=result.session_id,
    )


# ── Streaming Ask (SSE) ───────────────────────────────────────────────────────

@router.post("/stream", tags=["Agent"])
async def stream_ask(request: AskRequest, user: dict = Depends(get_current_user)):
    """
    Streaming endpoint — runs the full RAG agent loop (tool calls + retrieval),
    then streams the final answer token-by-token via SSE.
    """
    from app.config import get_settings
    from openai import OpenAI
    from app.agent.memory import memory
    from app.agent.prompts import SYSTEM_PROMPT, RAG_CONTEXT_TEMPLATE
    from app.agent.core import ROUTING_INSTRUCTION
    from app.agent.tools import execute_tool
    import re, json

    settings = get_settings()
    client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")

    sid = request.session_id or str(uuid.uuid4())
    system = SYSTEM_PROMPT + ROUTING_INSTRUCTION
    messages = [{"role": "system", "content": system}]
    messages.extend(memory.get_history(sid))
    messages.append({"role": "user", "content": request.query})

    async def event_generator() -> AsyncGenerator[str, None]:
        full_answer = ""
        accumulated_sources = []

        try:
            yield f"data: {{\"session_id\": \"{sid}\"}}\n\n"

            # ── Phase 1: Run tool calls (non-streaming) ───────────────────────
            # Execute up to 3 tool call iterations to handle RAG retrieval
            MAX_ITERS = 3
            for _ in range(MAX_ITERS):
                resp = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=messages,
                    temperature=0.2,
                    stream=False,
                )
                reply = resp.choices[0].message.content or ""

                # Check for tool call
                match = re.match(r"TOOL_CALL:\s*(\{.*?\})", reply, re.DOTALL)
                if not match:
                    # No tool call — this is the final answer, break and stream it
                    final_text = re.sub(r"^TOOL_CALL:.*$", "", reply, flags=re.MULTILINE).strip()
                    break

                # Execute the tool
                try:
                    tool_data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    final_text = reply
                    break

                tool_query = tool_data.get("query", request.query)
                result_text, sources = execute_tool("search_documents", json.dumps({"query": tool_query}))
                accumulated_sources.extend(sources)

                # Inject context and loop again
                context_msg = RAG_CONTEXT_TEMPLATE.format(context=result_text)
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": context_msg})
            else:
                # Max iterations hit — ask for a direct answer
                messages.append({"role": "user", "content": "Please summarise your best answer based on the context above."})
                resp = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=messages,
                    temperature=0.2,
                    stream=False,
                )
                final_text = resp.choices[0].message.content or ""

            # ── Phase 2: Stream the clean final answer token-by-token ─────────
            stream = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "Restate the following answer fluently and completely, preserving all detail:"},
                    {"role": "user", "content": final_text},
                ],
                temperature=0.0,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_answer += delta
                    safe = delta.replace("\n", "\\n").replace('"', '\\"')
                    yield f"data: {{\"token\": \"{safe}\"}}\n\n"

            # Persist to memory + Supabase
            memory.add_message(sid, "user", request.query)
            memory.add_message(sid, "assistant", full_answer)
            await save_message(sid, user["id"], "user", request.query)
            await save_message(sid, user["id"], "assistant", full_answer, accumulated_sources)

            yield "data: [DONE]\n\n"

        except Exception as exc:
            logger.exception("Stream error")
            safe_err = str(exc).replace('"', '\\"')
            yield f"data: {{\"error\": \"{safe_err}\"}}\n\n"


            yield "data: [DONE]\n\n"

        except Exception as exc:
            logger.exception("Stream error")
            yield f"data: {{\"error\": \"{exc}\"}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── File Upload ───────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    Upload a .txt or .pdf file to be embedded and indexed into Supabase.
    No more running index_documents.py manually!
    """
    allowed = {".txt", ".pdf"}
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Only {allowed} files are supported.")

    content_bytes = await file.read()

    # Parse content
    if ext == ".pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}")
    else:
        text = content_bytes.decode("utf-8", errors="replace")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File appears to be empty.")

    doc = Document(content=text, source=file.filename)

    try:
        build_index([doc])
    except Exception as exc:
        logger.exception("Indexing failed for uploaded file")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {exc}")

    # Count chunks (rough estimate)
    from app.config import get_settings
    settings = get_settings()
    chunk_count = max(1, len(text) // settings.chunk_size)

    logger.info("Uploaded and indexed '%s' by user %s (%d approx chunks)",
                file.filename, user["email"], chunk_count)

    return UploadResponse(
        filename=file.filename,
        chunks_indexed=chunk_count,
        message=f"'{file.filename}' successfully indexed into Supabase. Your agent now knows this document!",
    )


# ── Chat History ──────────────────────────────────────────────────────────────

@router.get("/history/{session_id}", response_model=ChatHistoryResponse, tags=["History"])
async def get_history(session_id: str, user: dict = Depends(get_current_user)):
    """Fetch all messages for a specific session."""
    rows = await get_session_messages(session_id, user["id"])
    messages = [
        ChatMessage(
            role=r["role"],
            content=r["content"],
            sources=r.get("sources") or [],
            created_at=r.get("created_at"),
        )
        for r in rows
    ]
    return ChatHistoryResponse(session_id=session_id, messages=messages)


@router.get("/sessions", response_model=SessionsResponse, tags=["History"])
async def get_sessions(user: dict = Depends(get_current_user)):
    """List all past sessions for the logged-in user."""
    rows = await get_user_sessions(user["id"])
    sessions = [
        SessionSummary(
            session_id=r["session_id"],
            preview=r["content"][:60] + "..." if len(r["content"]) > 60 else r["content"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return SessionsResponse(sessions=sessions)
