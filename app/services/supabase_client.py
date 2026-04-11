"""Shared async Supabase REST client using HTTPX."""
from __future__ import annotations

import httpx
from app.config import get_settings


def get_headers() -> dict:
    settings = get_settings()
    return {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
    }


def get_rest_url(table: str) -> str:
    settings = get_settings()
    return f"{settings.supabase_url.rstrip('/')}/rest/v1/{table}"


async def supabase_insert(table: str, data: list | dict) -> None:
    """Insert one or many rows into a Supabase table."""
    headers = {**get_headers(), "Prefer": "return=minimal"}
    payload = data if isinstance(data, list) else [data]
    async with httpx.AsyncClient() as client:
        resp = await client.post(get_rest_url(table), json=payload, headers=headers)
        resp.raise_for_status()


async def supabase_select(table: str, params: dict) -> list:
    """Select rows from a Supabase table with filter params."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(get_rest_url(table), params=params, headers=get_headers())
        resp.raise_for_status()
        return resp.json()
