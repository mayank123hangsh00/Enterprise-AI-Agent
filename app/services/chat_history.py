"""Chat history persistence — saves and retrieves messages from Supabase."""
from __future__ import annotations

import logging
from typing import List

from app.services.supabase_client import supabase_insert, supabase_select

logger = logging.getLogger(__name__)


async def save_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    sources: List[str] | None = None,
) -> None:
    """Persist a single chat message to Supabase chat_sessions table."""
    try:
        await supabase_insert("chat_sessions", {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "sources": sources or [],
        })
    except Exception as exc:
        logger.warning("Failed to save chat message to Supabase: %s", exc)


async def get_session_messages(session_id: str, user_id: str) -> List[dict]:
    """Fetch all messages for a given session, ordered by creation time."""
    try:
        rows = await supabase_select("chat_sessions", {
            "session_id": f"eq.{session_id}",
            "user_id": f"eq.{user_id}",
            "order": "created_at.asc",
            "select": "role,content,sources,created_at",
        })
        return rows
    except Exception as exc:
        logger.warning("Failed to fetch session messages: %s", exc)
        return []


async def get_user_sessions(user_id: str) -> List[dict]:
    """Return a deduplicated list of sessions for the user (most recent first)."""
    try:
        rows = await supabase_select("chat_sessions", {
            "user_id": f"eq.{user_id}",
            "role": "eq.user",
            "order": "created_at.desc",
            "select": "session_id,content,created_at",
        })
        # Deduplicate: first message of each session
        seen = set()
        sessions = []
        for row in rows:
            sid = row["session_id"]
            if sid not in seen:
                seen.add(sid)
                sessions.append(row)
        return sessions
    except Exception as exc:
        logger.warning("Failed to fetch user sessions: %s", exc)
        return []
