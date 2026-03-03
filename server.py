"""
open-brain MCP-Server (FastMCP, HTTP).

Start:
    python open-brain/server.py [--port 4567] [--key GEHEIMWORT]

Ohne --key läuft der Server ohne Authentifizierung.
Mit --key wird der Header 'x-brain-key' oder der Query-Parameter '?key='
bei jedem MCP-Request geprüft.
"""

import argparse
import sys
import os

# Damit Imports aus dem open-brain/-Verzeichnis funktionieren,
# unabhängig vom CWD beim Aufruf.
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

import ai
import db

# ---------------------------------------------------------------------------
# Auth-Middleware
# ---------------------------------------------------------------------------


class KeyAuthMiddleware(Middleware):
    """Einfache API-Key-Authentifizierung via Header oder Query-Parameter."""

    def __init__(self, key: str) -> None:
        self.key = key

    async def __call__(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        request = None
        if ctx.request_context and ctx.request_context.request:
            request = ctx.request_context.request

        if request is not None:
            provided = request.headers.get("x-brain-key") or request.query_params.get(
                "key"
            )
            if provided != self.key:
                raise PermissionError(
                    "Ungültiger oder fehlender API-Key (x-brain-key)."
                )

        return await call_next(context)


# ---------------------------------------------------------------------------
# Server-Setup
# ---------------------------------------------------------------------------


def build_server(access_key: str | None) -> tuple:
    middleware = []
    if access_key:
        middleware.append(KeyAuthMiddleware(access_key))

    mcp = FastMCP(
        name="open-brain",
        version="1.0.0",
        instructions=(
            "Open Brain speichert deine Gedanken, Notizen und Ideen "
            "mit semantischer Vektorsuche. "
            "Nutze 'add' zum Speichern, 'search' zum Suchen, "
            "'list' zum Auflisten und 'stats' für eine Übersicht."
        ),
        middleware=middleware,
    )

    # DB einmalig öffnen und im Closure halten
    con = db.init_db()

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
        """Speichert einen Thought mit Embedding und Metadaten."""
        embedding, metadata = await ai.get_embedding_and_metadata(thought)
        thought_id = db.insert_thought(con, thought, embedding, metadata)

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
        """Semantische Suche über alle gespeicherten Thoughts."""
        embedding = await ai.get_embedding(text)
        results = db.search_thoughts(con, embedding, limit=limit, threshold=threshold)

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
    async def list(
        limit: int = 10,
        type: str | None = None,
        topic: str | None = None,
        person: str | None = None,
        days: int | None = None,
    ) -> str:
        """Listet Thoughts mit optionalen Filtern auf."""
        results = db.list_thoughts(
            con,
            limit=limit,
            type_filter=type,
            topic=topic,
            person=person,
            days=days,
        )

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
        """Statistiken über alle Thoughts."""
        s = db.get_stats(con)

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

    return mcp, con


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def main() -> None:
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
        print("[open-brain] Auth aktiv – Key gesetzt.")
    else:
        print(
            "[open-brain] Kein Auth-Key gesetzt – Server läuft ohne Authentifizierung."
        )

    mcp, con = build_server(access_key=args.key)
    print(f"[open-brain] Starte HTTP-Server auf {args.host}:{args.port} ...")
    try:
        mcp.run(transport="http", host=args.host, port=args.port)
    except KeyboardInterrupt:
        pass
    finally:
        con.close()
        print("\n[open-brain] Datenbankverbindung geschlossen. Auf Wiedersehen.")


if __name__ == "__main__":
    main()
