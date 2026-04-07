"""FastAPI application entry point."""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pathlib import Path

from app.api.routes import router
from app.config import get_settings
from app.rag.retriever import init_retriever

# ── Logging ──────────────────────────────────────────────────────────────────
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Supabase retriever and dependencies at startup."""
    logger.info("Starting AcmeAssist API (env=%s)", settings.app_env)
    try:
        init_retriever()
        logger.info("Supabase cloud retriever initialized successfully.")
    except Exception as exc:
        logger.error("STARTUP ERROR: %s", exc)
        logger.error("Please verify your SUPABASE_URL and SUPABASE_KEY in .env")
    yield
    logger.info("Shutting down AcmeAssist API.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AcmeAssist — AI Agent API",
    description=(
        "An AI-powered internal assistant for Acme Corporation. "
        "Answers employee questions using RAG over company documents."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(router)

@app.get("/health", include_in_schema=False)
async def health_check():
    """Health check for AWS Load Balancer."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    """Serve the single-page application."""
    index_path = static_dir / "index.html"
    if not index_path.exists():
        return RedirectResponse(url="/docs")
    return FileResponse(index_path)


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
