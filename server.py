"""
open-brain MCP-Server (FastMCP, HTTP).

Start:
    python open-brain/server.py [--port 4567] [--key GEHEIMWORT]

Ohne --key läuft der Server ohne Authentifizierung.
Mit --key wird der Header 'x-brain-key' oder der Query-Parameter '?key='
bei jedem MCP-Request geprüft.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sqlite3
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

# Damit Imports aus dem open-brain/-Verzeichnis funktionieren,
# unabhängig vom CWD beim Aufruf.
sys.path.insert(0, os.path.dirname(__file__))

# Config importieren (initialisiert Logging)
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

import ai
import config
import db

logger = logging.getLogger(__name__)

# Globale Referenz für Cleanup
_startup_connection: sqlite3.Connection | None = None


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def cleanup() -> None:
    """Führt Cleanup-Operationen vor dem Shutdown durch."""
    global _startup_connection
    if _startup_connection is not None:
        try:
            _startup_connection.close()
            logger.info("Startup-Connection geschlossen")
        except Exception as e:
            logger.error(f"Fehler beim Schließen der Connection: {e}")
        _startup_connection = None


# ---------------------------------------------------------------------------
# Auth-Middleware
# ---------------------------------------------------------------------------


class KeyAuthMiddleware(Middleware):
    """Einfache API-Key-Authentifizierung via Header oder Query-Parameter."""

    def __init__(self, key: str) -> None:
        """Initialisiert die Middleware.

        Args:
            key: Der erwartete API-Key
        """
        self.key = key

    async def __call__(
        self, context: MiddlewareContext, call_next: Any
    ) -> Any:
        """Prüft den API-Key und ruft den nächsten Handler auf.

        Args:
            context: Der Middleware-Kontext
            call_next: Der nächste Handler in der Kette

        Returns:
            Ergebnis des nächsten Handlers

        Raises:
            PermissionError: Wenn der API-Key fehlt oder ungültig ist
        """
        ctx = context.fastmcp_context
        request = None
        if ctx is not None:
            req_ctx = ctx.request_context
            if req_ctx is not None:
                req = req_ctx.request
                if req is not None:
                    request = req

        if request is not None:
            provided = request.headers.get("x-brain-key") or request.query_params.get(
                "key"
            )
            if provided != self.key:
                logger.warning("Ungültiger API-Key in Request")
                raise PermissionError(
                    "Ungültiger oder fehlender API-Key (x-brain-key)."
                )

        return await call_next(context)


# ---------------------------------------------------------------------------
# Database Context Manager
# ---------------------------------------------------------------------------


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context Manager für thread-sichere DB-Connections.

    Jeder Aufruf öffnet eine neue Connection, die nach der Nutzung
    automatisch geschlossen wird. Das verhindert Race-Conditions
    bei concurrent Requests.

    Yields:
        SQLite Connection

    Example:
        with get_db_connection() as con:
            db.insert_thought(con, "test", embedding, metadata)
    """
    con = db.init_db()
    try:
        yield con
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Server-Setup
# ---------------------------------------------------------------------------


def build_server(access_key: str | None) -> tuple[FastMCP, sqlite3.Connection]:
    """Erstellt und konfiguriert den FastMCP-Server.

    Args:
        access_key: Optionaler API-Key für Authentifizierung

    Returns:
        Tuple aus (FastMCP Instanz, Startup Connection)
    """
    logger.debug(f"Build server mit access_key={'***' if access_key else None}")

    middleware: list[Middleware] = []
    if access_key:
        middleware.append(KeyAuthMiddleware(access_key))
        logger.info("Auth-Middleware aktiviert")

    mcp = FastMCP(
        name="open-brain",
        version="1.0.0",
        instructions=(
            "Open Brain speichert deine Gedanken, Notizen und Ideen "
            "mit semantischer Vektorsuche. "
            "Nutze 'add' zum Speichern, 'search' zum Suchen, "
            "'list_thoughts' zum Auflisten, 'stats' für eine Übersicht "
            "und 'health' für Health-Checks."
        ),
        middleware=middleware,
    )

    # Connection für Startup-Checks (wird nach build_server geschlossen)
    startup_con = db.init_db()
    logger.info(f"Datenbank initialisiert: {config.OPENBRAIN_DB_PATH}")

    # -----------------------------------------------------------------------
    # Tool: health
    # -----------------------------------------------------------------------

    @mcp.tool(
        description=(
            "Prüft den Health-Status des Servers. "
            "Testet Datenbank-Connectivity und gibt Status zurück."
        )
    )
    async def health() -> str:
        """Health-Check für den Server.

        Returns:
            Health-Status mit DB-Connectivity Check
        """
        import time

        start = time.monotonic()
        status: dict[str, Any] = {
            "status": "healthy",
            "checks": {},
        }

        # DB-Connectivity Check
        try:
            with get_db_connection() as con:
                result = con.execute("SELECT COUNT(*) FROM thoughts").fetchone()
                thought_count = result[0] if result else 0
                status["checks"]["database"] = {
                    "status": "ok",
                    "thoughts": thought_count,
                }
                logger.debug(f"Health check: DB ok, {thought_count} thoughts")
        except Exception as e:
            status["status"] = "unhealthy"
            status["checks"]["database"] = {
                "status": "error",
                "error": str(e),
            }
            logger.error(f"Health check: DB error: {e}")

        # Response Time
        elapsed_ms = (time.monotonic() - start) * 1000
        status["response_time_ms"] = round(elapsed_ms, 2)

        # Status als formatierter String
        lines = [
            f"**Status:** {status['status'].upper()}",
            f"**Response Time:** {status['response_time_ms']}ms",
            "",
            "**Checks:**",
        ]
        for check_name, check_result in status["checks"].items():
            check_status = check_result.get("status", "unknown")
            emoji = "✅" if check_status == "ok" else "❌"
            lines.append(f"  - {emoji} {check_name}: {check_status}")
            if "thoughts" in check_result:
                lines.append(f"    Thoughts: {check_result['thoughts']}")
            if "error" in check_result:
                lines.append(f"    Error: {check_result['error']}")

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Tool: add
    # -----------------------------------------------------------------------

    @mcp.tool(
        description=(
            "Speichert einen neuen Gedanken. "
            "Extrahiert automatisch Metadaten und erzeugt ein Embedding."
        )
    )
    async def add(thought: str) -> str:
        """Speichert einen Thought mit Embedding und Metadaten.

        Args:
            thought: Der zu speichernde Gedanke

        Returns:
            Bestätigung mit Metadaten und ID
        """
        logger.debug(f"Add thought: {thought[:50]}...")
        embedding, metadata = await ai.get_embedding_and_metadata(thought)

        with get_db_connection() as con:
            thought_id = db.insert_thought(con, thought, embedding, metadata)

        logger.info(f"Thought gespeichert: {thought_id} ({metadata.get('type', 'unknown')})")

        lines = [f"Gespeichert als **{metadata.get('type', 'thought')}**"]
        if metadata.get("topics"):
            lines.append(f"Topics: {', '.join(metadata['topics'])}")
        if metadata.get("people"):
            lines.append(f"Personen: {', '.join(metadata['people'])}")
        if metadata.get("action_items"):
            lines.append(f"Action Items: {'; '.join(metadata['action_items'])}")
        lines.append(f"ID: `{thought_id}`")
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Tool: search
    # -----------------------------------------------------------------------

    @mcp.tool(
        description=(
            "Suche gespeicherte Gedanken nach Bedeutung. "
            "Verwende dieses Tool, wenn der Nutzer nach einem Thema, "
            "einer Person oder einer Idee fragt, die zuvor gespeichert wurde."
        )
    )
    async def search(
        text: str,
        limit: int = 10,
        threshold: float = 0.3,
    ) -> str:
        """Semantische Suche über alle gespeicherten Thoughts.

        Args:
            text: Suchbegriff oder -phrase
            limit: Maximale Anzahl Ergebnisse
            threshold: Minimale Similarity (0.0 - 1.0)

        Returns:
            Formatierter String mit Suchergebnissen
        """
        logger.debug(f"Search: '{text}' (limit={limit}, threshold={threshold})")
        embedding = await ai.get_embedding(text)

        with get_db_connection() as con:
            results = db.search_thoughts(con, embedding, limit=limit, threshold=threshold)

        logger.info(f"Search found {len(results)} results for '{text[:30]}'")

        if not results:
            return f'Keine Thoughts gefunden, die zu "{text}" passen.'

        parts = [f"{len(results)} Ergebnis(se) für **{text}**:\n"]
        for i, r in enumerate(results, 1):
            m = r["metadata"]
            lines = [
                f"### {i}. {r['created_at'][:10]} — {m.get('type', '?')} "
                f"({r['similarity'] * 100:.1f}%)",
                r["content"],
            ]
            if m.get("topics"):
                lines.append(f"*Topics:* {', '.join(m['topics'])}")
            if m.get("people"):
                lines.append(f"*Personen:* {', '.join(m['people'])}")
            if m.get("action_items"):
                lines.append(f"*Actions:* {'; '.join(m['action_items'])}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    # -----------------------------------------------------------------------
    # Tool: list
    # -----------------------------------------------------------------------

    @mcp.tool(
        description=(
            "Listet zuletzt gespeicherte Thoughts. "
            "Optionale Filter: type, topic, person, days."
        )
    )
    async def list_thoughts(
        limit: int = 10,
        type: str | None = None,
        topic: str | None = None,
        person: str | None = None,
        days: int | None = None,
    ) -> str:
        """Listet Thoughts mit optionalen Filtern auf.

        Args:
            limit: Maximale Anzahl Ergebnisse
            type: Filter nach Thought-Type
            topic: Filter nach Topic
            person: Filter nach Person
            days: Filter nach Alter in Tagen

        Returns:
            Formatierter String mit aufgelisteten Thoughts
        """
        logger.debug(f"List thoughts: limit={limit}, type={type}, topic={topic}, person={person}, days={days}")

        with get_db_connection() as con:
            results = db.list_thoughts(
                con,
                limit=limit,
                type_filter=type,
                topic=topic,
                person=person,
                days=days,
            )

        logger.info(f"List returned {len(results)} thoughts")

        if not results:
            return "Keine Thoughts gefunden."

        parts = [f"{len(results)} Thought(s):\n"]
        for i, r in enumerate(results, 1):
            m = r["metadata"]
            tags = ", ".join(m.get("topics", []))
            header = f"{i}. **{r['created_at'][:10]}** — {m.get('type', '?')}"
            if tags:
                header += f" | {tags}"
            parts.append(f"{header}\n{r['content']}")

        return "\n\n".join(parts)

    # -----------------------------------------------------------------------
    # Tool: stats
    # -----------------------------------------------------------------------

    @mcp.tool(
        description=(
            "Gibt eine Zusammenfassung aller gespeicherten Thoughts: "
            "Anzahl, Typen, Top-Topics und Personen."
        )
    )
    async def stats() -> str:
        """Statistiken über alle Thoughts.

        Returns:
            Formatierter String mit Statistiken
        """
        with get_db_connection() as con:
            s = db.get_stats(con)

        logger.debug(f"Stats: {s['total']} thoughts total")

        lines = [
            f"**Gesamt:** {s['total']} Thought(s)",
            f"**Zeitraum:** {s['oldest'] or 'N/A'} → {s['newest'] or 'N/A'}",
            "",
            "**Typen:**",
        ]
        for k, v in (s["types"] or {}).items():
            lines.append(f"  - {k}: {v}")

        if s["top_topics"]:
            lines.append("")
            lines.append("**Top-Topics:**")
            for k, v in s["top_topics"].items():
                lines.append(f"  - {k}: {v}")

        if s["top_people"]:
            lines.append("")
            lines.append("**Personen:**")
            for k, v in s["top_people"].items():
                lines.append(f"  - {k}: {v}")

        return "\n".join(lines)

    return mcp, startup_con


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def main() -> None:
    """Haupteinstiegspunkt für den Server."""
    global _startup_connection

    parser = argparse.ArgumentParser(description="open-brain MCP-Server")
    parser.add_argument(
        "--port", type=int, default=4567, help="HTTP-Port (default: 4567)"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind-Adresse (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--key", default=None, help="API-Key für einfache Authentifizierung (optional)"
    )
    args = parser.parse_args()

    if args.key:
        logger.info("Auth aktiv – API-Key gesetzt")
    else:
        logger.warning("Kein Auth-Key gesetzt – Server läuft ohne Authentifizierung")

    mcp, con = build_server(access_key=args.key)
    _startup_connection = con

    logger.info(f"Starte HTTP-Server auf {args.host}:{args.port}")
    logger.info(f"Log-Level: {config.OPENBRAIN_LOG_LEVEL}")

    try:
        mcp.run(transport="http", host=args.host, port=args.port)
    except KeyboardInterrupt:
        pass  # Sauberer Shutdown via Ctrl-C
    except asyncio.CancelledError:
        pass  # Sauberer Shutdown durch Uvicorn
    finally:
        cleanup()
        logger.info("Server beendet. Auf Wiedersehen.")


if __name__ == "__main__":
    main()
