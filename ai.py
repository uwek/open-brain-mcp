"""
OpenRouter-Integration für open-brain.
Stellt Embedding- und Metadaten-Extraktion bereit.
"""

import json
from typing import Any

import httpx

import config

METADATA_PROMPT = """Extract metadata from the user's captured thought. Return JSON with:
- "people": array of people mentioned (empty if none)
- "action_items": array of implied to-dos (empty if none)
- "dates_mentioned": array of dates YYYY-MM-DD (empty if none)
- "topics": array of 1-3 short topic tags (always at least one)
- "type": one of "observation", "task", "idea", "reference", "person_note"
Only extract what's explicitly there."""

# Timeout: connect 10s, read 90s (LLM-Antworten können länger dauern)
_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=10.0)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def get_embedding(
    text: str, client: httpx.AsyncClient | None = None
) -> list[float]:
    """Erzeugt einen Embedding-Vektor (1536 Dimensionen) via OpenRouter."""

    async def _call(c: httpx.AsyncClient) -> list[float]:
        response = await c.post(
            f"{config.OPENROUTER_BASE}/embeddings",
            headers=_headers(),
            json={
                "model": config.EMBEDDING_MODEL,
                "input": text,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    if client is not None:
        return await _call(client)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        return await _call(c)


async def extract_metadata(
    text: str, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """Extrahiert strukturierte Metadaten aus einem Thought-Text via GPT-4o-mini."""

    async def _call(c: httpx.AsyncClient) -> dict[str, Any]:
        response = await c.post(
            f"{config.OPENROUTER_BASE}/chat/completions",
            headers=_headers(),
            json={
                "model": config.METADATA_MODEL,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": METADATA_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        try:
            return json.loads(data["choices"][0]["message"]["content"])
        except (KeyError, json.JSONDecodeError):
            return {"topics": ["uncategorized"], "type": "observation"}

    if client is not None:
        return await _call(client)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        return await _call(c)


async def get_embedding_and_metadata(text: str) -> tuple[list[float], dict[str, Any]]:
    """
    Holt Embedding und Metadaten über einen gemeinsamen HTTP-Client.
    Die beiden Requests laufen sequenziell, um Connection-Timeouts
    bei parallelen Verbindungsaufbauten zu vermeiden.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        metadata = await extract_metadata(text, client)
        embedding = await get_embedding(text, client)
        return embedding, metadata
