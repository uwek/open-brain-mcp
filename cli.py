"""
open-brain CLI

Verwendung:
    python open-brain/cli.py add "Mein Gedanke..."
    python open-brain/cli.py search "Suche" [--limit N] [--threshold 0.5] [--json]
    python open-brain/cli.py list [--type TYPE] [--topic TOPIC] [--person NAME]
                                  [--days N] [--limit N] [--json]
    python open-brain/cli.py stats [--json]
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json as json_mod
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import ai
import db


# ---------------------------------------------------------------------------
# Markdown-Formatter
# ---------------------------------------------------------------------------


def fmt_thought_list(results: list[dict], title: str) -> str:
    if not results:
        return f"*{title}: Keine Einträge gefunden.*"
    lines = [f"# {title}", ""]
    for i, r in enumerate(results, 1):
        m = r["metadata"]
        tags = ", ".join(m.get("topics", []))
        header = f"## {i}. {r['created_at'][:10]} — {m.get('type', '?')}"
        if tags:
            header += f"  |  {tags}"
        lines.append(header)
        lines.append("")
        lines.append(r["content"])
        if m.get("people"):
            lines.append(f"*Personen:* {', '.join(m['people'])}")
        if m.get("action_items"):
            lines.append(f"*Actions:* {'; '.join(m['action_items'])}")
        lines.append("")
    return "\n".join(lines)


def fmt_search_results(results: list[dict], query: str) -> str:
    if not results:
        return f'*Keine Thoughts gefunden für: "{query}"*'
    lines = [f'# Suchergebnisse: "{query}"', ""]
    for i, r in enumerate(results, 1):
        m = r["metadata"]
        sim = f"{r['similarity'] * 100:.1f}%"
        lines.append(f"## {i}. {r['created_at'][:10]} — {m.get('type', '?')} ({sim})")
        lines.append("")
        lines.append(r["content"])
        if m.get("topics"):
            lines.append(f"*Topics:* {', '.join(m['topics'])}")
        if m.get("people"):
            lines.append(f"*Personen:* {', '.join(m['people'])}")
        if m.get("action_items"):
            lines.append(f"*Actions:* {'; '.join(m['action_items'])}")
        lines.append("")
    return "\n".join(lines)


def fmt_stats(s: dict) -> str:
    lines = [
        "# open-brain Statistiken",
        "",
        f"**Gesamt:** {s['total']} Thought(s)",
        f"**Zeitraum:** {s['oldest'] or 'N/A'} → {s['newest'] or 'N/A'}",
        "",
        "## Typen",
    ]
    for k, v in (s["types"] or {}).items():
        lines.append(f"- {k}: {v}")

    if s["top_topics"]:
        lines.append("")
        lines.append("## Top-Topics")
        for k, v in s["top_topics"].items():
            lines.append(f"- {k}: {v}")

    if s["top_people"]:
        lines.append("")
        lines.append("## Personen")
        for k, v in s["top_people"].items():
            lines.append(f"- {k}: {v}")

    return "\n".join(lines)


def fmt_add_result(thought_id: str, metadata: dict, content: str | None = None) -> str:
    lines = [
        "# Thought gespeichert",
        "",
        f"**Typ:** {metadata.get('type', 'thought')}",
    ]
    if metadata.get("topics"):
        lines.append(f"**Topics:** {', '.join(metadata['topics'])}")
    if metadata.get("people"):
        lines.append(f"**Personen:** {', '.join(metadata['people'])}")
    if metadata.get("action_items"):
        lines.append(f"**Actions:** {'; '.join(metadata['action_items'])}")
    lines.append(f"**ID:** `{thought_id}`")
    if content is not None:
        lines.append("")
        lines.append(f"> {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def cmd_add(args) -> None:
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                thought = f.read().strip()
        except OSError as e:
            print(f"Fehler beim Lesen von '{args.file}': {e}", file=sys.stderr)
            sys.exit(1)
        if not thought:
            print(f"Datei '{args.file}' ist leer.", file=sys.stderr)
            sys.exit(1)
    elif args.thought:
        thought = args.thought
    else:
        print(
            "Fehler: entweder einen Gedanken angeben oder --file nutzen.",
            file=sys.stderr,
        )
        sys.exit(1)

    con = db.init_db()
    embedding, metadata = await ai.get_embedding_and_metadata(thought)
    thought_id = db.insert_thought(con, thought, embedding, metadata)
    con.close()

    if args.json:
        print(
            json_mod.dumps(
                {"id": thought_id, "metadata": metadata, "content": thought},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(
            fmt_add_result(thought_id, metadata, content=None if args.file else thought)
        )


async def cmd_search(args) -> None:
    con = db.init_db()
    embedding = await ai.get_embedding(args.text)  # search braucht nur Embedding
    results = db.search_thoughts(
        con, embedding, limit=args.limit, threshold=args.threshold
    )
    con.close()

    if args.json:
        print(json_mod.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(fmt_search_results(results, args.text))


def cmd_list(args) -> None:
    con = db.init_db()
    results = db.list_thoughts(
        con,
        limit=args.limit,
        type_filter=args.type,
        topic=args.topic,
        person=args.person,
        days=args.days,
    )
    con.close()

    if args.json:
        print(json_mod.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(fmt_thought_list(results, "Thoughts"))


def cmd_stats(args) -> None:
    con = db.init_db()
    s = db.get_stats(con)
    con.close()

    if args.json:
        print(json_mod.dumps(s, ensure_ascii=False, indent=2))
    else:
        print(fmt_stats(s))


def cmd_export(args) -> None:
    con = db.init_db()
    thoughts = db.export_thoughts(con, include_embeddings=args.full)
    con.close()

    payload = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "count": len(thoughts),
        "include_embeddings": args.full,
        "thoughts": thoughts,
    }
    data = json_mod.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(data)
        print(
            f"Export abgeschlossen: {len(thoughts)} Thought(s) → {args.output}"
            + (" (inkl. Embeddings)" if args.full else "")
        )
    else:
        print(data)


async def cmd_import(args) -> None:
    try:
        with open(args.file, encoding="utf-8") as f:
            payload = json_mod.load(f)
    except (OSError, json_mod.JSONDecodeError) as e:
        print(f"Fehler beim Lesen von '{args.file}': {e}", file=sys.stderr)
        sys.exit(1)

    # Unterstützt sowohl Export-Payload {"thoughts": [...]} als auch rohe Liste [...]
    if isinstance(payload, list):
        thoughts = payload
    elif isinstance(payload, dict) and "thoughts" in payload:
        thoughts = payload["thoughts"]
    else:
        print(
            "Ungültiges Format: erwartet JSON-Objekt mit 'thoughts'-Array oder JSON-Array.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not thoughts:
        print("Keine Thoughts in der Datei gefunden.")
        return

    has_embeddings = all(
        "embedding" in t and t["embedding"] is not None for t in thoughts
    )
    reembed = args.reembed

    if reembed:
        print(
            f"Starte Import mit Neu-Generierung der Embeddings ({len(thoughts)} Thought(s)) ..."
        )
    elif not has_embeddings:
        print(
            "Warnung: Datei enthält keine Embeddings. Embeddings werden via API neu generiert.",
            file=sys.stderr,
        )
        reembed = True
    else:
        print(f"Starte Import aus Datei ({len(thoughts)} Thought(s)) ...")

    con = db.init_db()
    inserted = replaced = skipped = errors = 0

    for i, t in enumerate(thoughts, 1):
        thought_id = t.get("id") or __import__("uuid").uuid4().hex
        content = t.get("content", "").strip()
        if not content:
            print(f"  [{i}] Übersprungen: kein Inhalt.", file=sys.stderr)
            errors += 1
            continue

        metadata = t.get("metadata") or {}
        created_at = t.get("created_at")
        updated_at = t.get("updated_at")

        try:
            if reembed:
                embedding, metadata_new = await ai.get_embedding_and_metadata(content)
                # Metadaten aus Datei bevorzugen, falls vorhanden
                if not metadata:
                    metadata = metadata_new
            else:
                embedding = t["embedding"]

            status = db.import_thought(
                con,
                thought_id=thought_id,
                content=content,
                embedding=embedding,
                metadata=metadata,
                created_at=created_at,
                updated_at=updated_at,
                on_conflict=args.on_conflict,
            )
        except Exception as e:
            print(f"  [{i}] Fehler bei '{content[:60]}...': {e}", file=sys.stderr)
            errors += 1
            continue

        symbol = {"inserted": "+", "replaced": "~", "skipped": "="}[status]
        print(f"  [{i}/{len(thoughts)}] {symbol} {status}: {content[:70]}")
        if status == "inserted":
            inserted += 1
        elif status == "replaced":
            replaced += 1
        else:
            skipped += 1

    con.close()
    print(
        f"\nImport abgeschlossen: {inserted} neu, {replaced} ersetzt, "
        f"{skipped} übersprungen, {errors} Fehler."
    )


# ---------------------------------------------------------------------------
# Argument-Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openbrain",
        description="open-brain – Gedankenspeicher mit semantischer Suche",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Thought speichern")
    p_add.add_argument(
        "thought", nargs="?", default=None, help="Der zu speichernde Gedanke"
    )
    p_add.add_argument("--file", metavar="DATEI", help="Thought aus Textdatei lesen")
    p_add.add_argument("--json", action="store_true", help="JSON-Ausgabe")

    # search
    p_search = sub.add_parser("search", help="Semantische Suche")
    p_search.add_argument("text", help="Suchtext")
    p_search.add_argument(
        "--limit", type=int, default=10, help="Max. Ergebnisse (default: 10)"
    )
    p_search.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Min. Ähnlichkeit 0–1 (default: 0.3)",
    )
    p_search.add_argument("--json", action="store_true", help="JSON-Ausgabe")

    # list
    p_list = sub.add_parser("list", help="Thoughts auflisten")
    p_list.add_argument(
        "--limit", type=int, default=10, help="Max. Einträge (default: 10)"
    )
    p_list.add_argument(
        "--type",
        dest="type",
        help="Filter: observation|task|idea|reference|person_note",
    )
    p_list.add_argument("--topic", help="Filter nach Topic-Tag")
    p_list.add_argument("--person", help="Filter nach Person")
    p_list.add_argument("--days", type=int, help="Nur Thoughts der letzten N Tage")
    p_list.add_argument("--json", action="store_true", help="JSON-Ausgabe")

    # stats
    p_stats = sub.add_parser("stats", help="Statistiken anzeigen")
    p_stats.add_argument("--json", action="store_true", help="JSON-Ausgabe")

    # export
    p_export = sub.add_parser("export", help="Alle Thoughts als JSON exportieren")
    p_export.add_argument(
        "output",
        nargs="?",
        default=None,
        metavar="DATEI",
        help="Zieldatei (default: stdout)",
    )
    p_export.add_argument(
        "--full",
        action="store_true",
        help="Embeddings mit exportieren (größere Datei, kein Re-Embedding beim Import nötig)",
    )

    # import
    p_import = sub.add_parser("import", help="Thoughts aus JSON-Datei importieren")
    p_import.add_argument("file", metavar="DATEI", help="Quelldatei (JSON)")
    p_import.add_argument(
        "--reembed",
        action="store_true",
        help="Embeddings ignorieren und via API neu generieren",
    )
    p_import.add_argument(
        "--on-conflict",
        dest="on_conflict",
        choices=["skip", "replace"],
        default="skip",
        help="Verhalten bei bereits vorhandener ID: skip (default) oder replace",
    )

    return parser


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "add":
        asyncio.run(cmd_add(args))
    elif args.command == "search":
        asyncio.run(cmd_search(args))
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "import":
        asyncio.run(cmd_import(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
