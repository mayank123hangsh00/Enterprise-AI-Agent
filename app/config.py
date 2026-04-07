from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Groq API ───────────────────────────────────────────────────────────────
    groq_api_key: str = ""

    # ── Models ─────────────────────────────────────────────────────────────────
    llm_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── RAG ────────────────────────────────────────────────────────────────────
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k_results: int = 5

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""

    # ── App ────────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
