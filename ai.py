"""
OpenRouter-Integration für open-brain.
Stellt Embedding- und Metadaten-Extraktion bereit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import config

logger = logging.getLogger(__name__)

METADATA_PROMPT: str = """Extract metadata from the user's captured thought. Return JSON with:
- "people": array of people mentioned (empty if none)
- "action_items": array of implied to-dos (empty if none)
- "dates_mentioned": array of dates YYYY-MM-DD (empty if none)
- "topics": array of 1-3 short topic tags (always at least one)
- "type": one of "observation", "task", "idea", "reference", "person_note"
Only extract what's explicitly there."""

# Timeout: connect 10s, read 90s (LLM-Antworten können länger dauern)
_TIMEOUT: httpx.Timeout = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=10.0)

# Retry-Konfiguration
_RETRY_CONFIG: dict[str, Any] = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type(
        (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException)
    ),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "reraise": True,
}


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Einfacher Rate-Limiter mit Token-Bucket-Algorithmus.

    Begrenzt die Anzahl der API-Calls pro Sekunde, um Rate-Limits
    des Providers zu respektieren.
    """

    def __init__(self, calls_per_second: float = 2.0) -> None:
        """Initialisiert den Rate-Limiter.

        Args:
            calls_per_second: Maximale Anzahl Calls pro Sekunde (default: 2.0)
        """
        self._interval: float = 1.0 / calls_per_second
        self._lock: asyncio.Lock = asyncio.Lock()
        self._last_call: float = 0.0

    async def acquire(self) -> None:
        """Wartet, bis ein Call erlaubt ist.

        Diese Methode ist thread-safe und kann von mehreren
        Coroutinen gleichzeitig aufgerufen werden.
        """
        async with self._lock:
            now = time.monotonic()
            wait_time = self._last_call + self._interval - now
            if wait_time > 0:
                logger.debug(f"Rate limiter: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self._last_call = time.monotonic()


# Globaler Rate-Limiter für OpenRouter API
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Gibt den globalen Rate-Limiter zurück (Singleton).

    Returns:
        RateLimiter Instanz
    """
    global _rate_limiter
    if _rate_limiter is None:
        calls_per_second = getattr(config, 'OPENROUTER_RATE_LIMIT', 2.0)
        _rate_limiter = RateLimiter(calls_per_second=calls_per_second)
        logger.info(f"Rate limiter initialized: {calls_per_second} calls/second")
    return _rate_limiter


def _headers() -> dict[str, str]:
    """Erstellt die HTTP-Header für OpenRouter API-Calls.

    Returns:
        Dictionary mit Authorization und Content-Type Headers
    """
    return {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


@retry(**_RETRY_CONFIG)
async def _get_embedding_call(client: httpx.AsyncClient, text: str) -> list[float]:
    """Ein einzelner Embedding-API-Call mit Retry-Schutz und Rate-Limiting.

    Args:
        client: HTTP Client für den Request
        text: Text für den das Embedding erzeugt werden soll

    Returns:
        1536-dimensionaler Embedding-Vektor

    Raises:
        httpx.HTTPStatusError: Bei API-Fehlern
        httpx.ConnectError: Bei Verbindungsproblemen
        httpx.TimeoutException: Bei Timeout
    """
    await get_rate_limiter().acquire()

    response = await client.post(
        f"{config.OPENROUTER_BASE}/embeddings",
        headers=_headers(),
        json={
            "model": config.EMBEDDING_MODEL,
            "input": text,
        },
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return list(data["data"][0]["embedding"])


@retry(**_RETRY_CONFIG)
async def _extract_metadata_call(client: httpx.AsyncClient, text: str) -> dict[str, Any]:
    """Ein einzelner Metadata-API-Call mit Retry-Schutz und Rate-Limiting.

    Args:
        client: HTTP Client für den Request
        text: Text aus dem Metadaten extrahiert werden sollen

    Returns:
        Dictionary mit extrahierten Metadaten

    Raises:
        httpx.HTTPStatusError: Bei API-Fehlern
        httpx.ConnectError: Bei Verbindungsproblemen
        httpx.TimeoutException: Bei Timeout
    """
    await get_rate_limiter().acquire()

    response = await client.post(
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
    data: dict[str, Any] = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return dict(json.loads(content))
        return {"topics": ["uncategorized"], "type": "observation"}
    except (KeyError, json.JSONDecodeError):
        return {"topics": ["uncategorized"], "type": "observation"}


async def get_embedding(
    text: str, client: httpx.AsyncClient | None = None
) -> list[float]:
    """Erzeugt einen Embedding-Vektor (1536 Dimensionen) via OpenRouter.

    Args:
        text: Text für den das Embedding erzeugt werden soll
        client: Optionaler HTTP Client (sonst wird ein neuer erstellt)

    Returns:
        1536-dimensionaler Embedding-Vektor
    """
    if client is not None:
        result: list[float] = await _get_embedding_call(client, text)
        return result
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        result2: list[float] = await _get_embedding_call(c, text)
        return result2


async def extract_metadata(
    text: str, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """Extrahiert strukturierte Metadaten aus einem Thought-Text via GPT-4o-mini.

    Args:
        text: Text aus dem Metadaten extrahiert werden sollen
        client: Optionaler HTTP Client (sonst wird ein neuer erstellt)

    Returns:
        Dictionary mit keys: type, topics, people, action_items, dates_mentioned
    """
    if client is not None:
        result: dict[str, Any] = await _extract_metadata_call(client, text)
        return result
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        result2: dict[str, Any] = await _extract_metadata_call(c, text)
        return result2


async def get_embedding_and_metadata(text: str) -> tuple[list[float], dict[str, Any]]:
    """Holt Embedding und Metadaten über einen gemeinsamen HTTP-Client.

    Die beiden Requests laufen sequenziell, um Connection-Timeouts
    bei parallelen Verbindungsaufbauten zu vermeiden.

    Args:
        text: Text für den Embedding und Metadaten erzeugt werden sollen

    Returns:
        Tuple aus (embedding, metadata)
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        metadata = await _extract_metadata_call(client, text)
        embedding = await _get_embedding_call(client, text)
        return embedding, metadata
