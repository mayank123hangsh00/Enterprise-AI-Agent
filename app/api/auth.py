"""JWT authentication using Supabase tokens.

Supabase issues standard HS256 JWTs signed with the project JWT secret.
We verify the token locally — no round-trip to Supabase.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency — validates the Supabase JWT and returns the user payload.
    Raises 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    settings = get_settings()

    # Verify the JWT by calling Supabase /auth/v1/user endpoint
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_key,
                    "Authorization": f"Bearer {token}",
                },
                timeout=5.0,
            )
    except httpx.RequestError as exc:
        logger.error("Auth verification request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unreachable",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = resp.json()
    return {
        "id": user_data.get("id"),
        "email": user_data.get("email"),
    }
