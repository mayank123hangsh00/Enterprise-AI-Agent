"""Auth endpoints — login, signup, logout, me.

The frontend has zero Supabase keys. All auth is proxied
through these FastAPI endpoints using the server-side service role key.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
auth_router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer()


# ── Schemas ────────────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    email: str
    user_id: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _supabase_auth_headers() -> dict:
    settings = get_settings()
    return {
        "apikey": settings.supabase_key,
        "Content-Type": "application/json",
    }


def _auth_url(path: str) -> str:
    settings = get_settings()
    return f"{settings.supabase_url.rstrip('/')}/auth/v1/{path}"


# ── Routes ─────────────────────────────────────────────────────────────────────

@auth_router.post("/login", response_model=AuthResponse)
async def login(body: AuthRequest):
    """Proxy login to Supabase Auth. Returns our own access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _auth_url("token?grant_type=password"),
            json={"email": body.email, "password": body.password},
            headers=_supabase_auth_headers(),
            timeout=10.0,
        )

    if resp.status_code != 200:
        detail = resp.json().get("error_description", "Invalid credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    data = resp.json()
    return AuthResponse(
        access_token=data["access_token"],
        email=data["user"]["email"],
        user_id=data["user"]["id"],
    )


@auth_router.post("/signup", response_model=AuthResponse)
async def signup(body: AuthRequest):
    """Proxy signup to Supabase Auth."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _auth_url("signup"),
            json={"email": body.email, "password": body.password},
            headers=_supabase_auth_headers(),
            timeout=10.0,
        )

    if resp.status_code not in (200, 201):
        detail = resp.json().get("error_description", "Signup failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    data = resp.json()

    # If email confirmation is required, session may be None
    if not data.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Account created. Please check your email to confirm before signing in.",
        )

    return AuthResponse(
        access_token=data["access_token"],
        email=data["user"]["email"],
        user_id=data["user"]["id"],
    )


@auth_router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Invalidate the Supabase session server-side."""
    async with httpx.AsyncClient() as client:
        await client.post(
            _auth_url("logout"),
            headers={
                **_supabase_auth_headers(),
                "Authorization": f"Bearer {credentials.credentials}",
            },
            timeout=5.0,
        )
    return {"message": "Logged out successfully"}


@auth_router.get("/me")
async def me(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Return current user info by verifying token with Supabase."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _auth_url("user"),
            headers={
                **_supabase_auth_headers(),
                "Authorization": f"Bearer {credentials.credentials}",
            },
            timeout=5.0,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    data = resp.json()
    return {"email": data.get("email"), "user_id": data.get("id")}
