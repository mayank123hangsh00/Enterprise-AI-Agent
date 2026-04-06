"""Session-based conversation memory manager."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_HISTORY_MESSAGES = 20  # Per session — oldest are trimmed when exceeded
SESSION_TTL_SECONDS = 1800  # 30 minutes of inactivity clears the session


class SessionMemory:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._store: Dict[str, List[dict]] = defaultdict(list)
        self._last_access: Dict[str, float] = {}
        self._lock = Lock()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session history."""
        with self._lock:
            self._store[session_id].append({"role": role, "content": content})
            self._last_access[session_id] = time.time()

            # Trim to latest MAX_HISTORY_MESSAGES (keep system prompt offset)
            if len(self._store[session_id]) > MAX_HISTORY_MESSAGES:
                self._store[session_id] = self._store[session_id][-MAX_HISTORY_MESSAGES:]
                logger.debug("Trimmed history for session %s to %d messages", session_id, MAX_HISTORY_MESSAGES)

    def get_history(self, session_id: str) -> List[dict]:
        """Return conversation history for the given session."""
        with self._lock:
            self._expire_idle_sessions()
            return list(self._store.get(session_id, []))

    def clear(self, session_id: str) -> None:
        """Clear history for a specific session."""
        with self._lock:
            self._store.pop(session_id, None)
            self._last_access.pop(session_id, None)
            logger.info("Cleared session: %s", session_id)

    def _expire_idle_sessions(self) -> None:
        """Remove sessions that have been idle longer than SESSION_TTL_SECONDS."""
        now = time.time()
        expired = [
            sid for sid, last in self._last_access.items()
            if now - last > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            self._store.pop(sid, None)
            self._last_access.pop(sid, None)
            logger.info("Expired idle session: %s", sid)


# Singleton instance shared across the app
memory = SessionMemory()
