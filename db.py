"""
Datenbankschicht für open-brain.
Nutzt SQLite + sqlite-vec (via Python-Package) für Vektorsuche.
"""

from __future__ import annotations

import json
import sqlite3
import struct
import uuid
from typing import Any

import sqlite_vec

import config


def _serialize_vec(v: list[float]) -> bytes:
    """Serialisiert einen Float-Vektor als Little-Endian bytes für sqlite-vec.

    Args:
        v: Liste von Float-Werten

    Returns:
        Bytes-Repräsentation für sqlite-vec
    """
    return struct.pack(f"{len(v)}f", *v)


def get_connection() -> sqlite3.Connection:
    """Öffnet eine SQLite-Verbindung und lädt sqlite-vec.

    Returns:
        SQLite Connection mit geladenem sqlite-vec Extension
    """
    con = sqlite3.connect(config.OPENBRAIN_DB_PATH)
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    con.row_factory = sqlite3.Row
    return con


def setup(con: sqlite3.Connection) -> None:
    """Erstellt alle Tabellen, Trigger und Indizes, falls noch nicht vorhanden.

    Args:
        con: Aktive SQLite Connection
    """
    con.executescript(f"""
        CREATE TABLE IF NOT EXISTS thoughts (
            id         TEXT PRIMARY KEY
                           DEFAULT (lower(hex(randomblob(16)))),
            content    TEXT NOT NULL,
            metadata   TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at TEXT NOT NULL
                           DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );

        CREATE TRIGGER IF NOT EXISTS thoughts_updated_at
            BEFORE UPDATE ON thoughts
            FOR EACH ROW
        BEGIN
            UPDATE thoughts
               SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
             WHERE id = OLD.id;
        END;

        CREATE INDEX IF NOT EXISTS idx_thoughts_created_at
            ON thoughts (created_at DESC);

        CREATE VIRTUAL TABLE IF NOT EXISTS thoughts_vec USING vec0(
            rowid INTEGER PRIMARY KEY,
            embedding float[{config.EMBEDDING_DIM}]
        );
    """)
    con.commit()


def init_db() -> sqlite3.Connection:
    """Öffnet die Verbindung und initialisiert das Schema.

    Returns:
        Initialisierte SQLite Connection
    """
    con = get_connection()
    setup(con)
    return con


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------


def insert_thought(
    con: sqlite3.Connection,
    content: str,
    embedding: list[float],
    metadata: dict[str, Any],
) -> str:
    """Speichert einen Thought + Vektor und gibt die neue ID zurück.

    Args:
        con: Aktive SQLite Connection
        content: Text des Thoughts
        embedding: 1536-dimensionaler Embedding-Vektor
        metadata: Metadaten als Dictionary

    Returns:
        UUID des neu erstellten Thoughts
    """
    thought_id = str(uuid.uuid4()).replace("-", "")
    meta_json = json.dumps(metadata, ensure_ascii=False)
    vec_bytes = _serialize_vec(embedding)

    cur = con.execute(
        "INSERT INTO thoughts (id, content, metadata) VALUES (?, ?, ?)",
        (thought_id, content, meta_json),
    )
    rowid = cur.lastrowid

    con.execute(
        "INSERT INTO thoughts_vec (rowid, embedding) VALUES (?, ?)",
        (rowid, vec_bytes),
    )
    con.commit()
    return thought_id


# ---------------------------------------------------------------------------
# Suche
# ---------------------------------------------------------------------------


def search_thoughts(
    con: sqlite3.Connection,
    query_embedding: list[float],
    limit: int = 10,
    threshold: float = 0.3,
) -> list[dict[str, Any]]:
    """Vektorähnlichkeitssuche via sqlite-vec (L2-Distanz → Similarity).

    sqlite-vec liefert die euklidische L2-Distanz zwischen den Vektoren.
    Für normalisierte Vektoren (wie text-embedding-3-small sie liefert) gilt:
        similarity = 1 - distance / 2
    Dabei ist similarity=1.0 ein exakter Match, similarity=0.0 orthogonal.

    Args:
        con: Aktive SQLite Connection
        query_embedding: Embedding-Vektor für die Suchanfrage
        limit: Maximale Anzahl Ergebnisse
        threshold: Minimale Similarity (0.0 - 1.0)

    Returns:
        Liste von gefundenen Thoughts mit Similarity-Score
    """
    vec_bytes = _serialize_vec(query_embedding)

    rows = con.execute(
        """
        SELECT
            t.id,
            t.content,
            t.metadata,
            t.created_at,
            v.distance
        FROM thoughts_vec v
        JOIN thoughts t ON t.rowid = v.rowid
        WHERE v.embedding MATCH ?
          AND k = ?
        ORDER BY v.distance
        """,
        (vec_bytes, limit),
    ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        # L2-Distanz → Cosine-Similarity (nur für normalisierte Vektoren korrekt)
        dist = row["distance"]
        similarity = max(0.0, 1.0 - dist / 2.0)
        if similarity < threshold:
            continue
        results.append(
            {
                "id": row["id"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"],
                "similarity": similarity,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Auflisten
# ---------------------------------------------------------------------------


def list_thoughts(
    con: sqlite3.Connection,
    limit: int = 10,
    type_filter: str | None = None,
    topic: str | None = None,
    person: str | None = None,
    days: int | None = None,
) -> list[dict[str, Any]]:
    """Listet Thoughts mit optionalen Filtern.

    Args:
        con: Aktive SQLite Connection
        limit: Maximale Anzahl Ergebnisse
        type_filter: Filter nach Thought-Type
        topic: Filter nach Topic
        person: Filter nach Person
        days: Filter nach Alter in Tagen

    Returns:
        Liste von Thoughts
    """
    params: list[Any] = []

    if topic and person:
        sql = """
            SELECT DISTINCT t.id, t.content, t.metadata, t.created_at
              FROM thoughts t
             WHERE EXISTS (
                   SELECT 1 FROM json_each(json_extract(t.metadata, '$.topics')) je
                    WHERE je.value = ?
                   )
               AND EXISTS (
                   SELECT 1 FROM json_each(json_extract(t.metadata, '$.people')) jp
                    WHERE jp.value = ?
                   )
        """
        params = [topic, person]
        if type_filter:
            sql += " AND json_extract(t.metadata, '$.type') = ?"
            params.append(type_filter)
    elif topic:
        sql = """
            SELECT DISTINCT t.id, t.content, t.metadata, t.created_at
              FROM thoughts t, json_each(json_extract(t.metadata, '$.topics')) je
             WHERE je.value = ?
        """
        params = [topic]
        if type_filter:
            sql += " AND json_extract(t.metadata, '$.type') = ?"
            params.append(type_filter)
    elif person:
        sql = """
            SELECT DISTINCT t.id, t.content, t.metadata, t.created_at
              FROM thoughts t, json_each(json_extract(t.metadata, '$.people')) je
             WHERE je.value = ?
        """
        params = [person]
        if type_filter:
            sql += " AND json_extract(t.metadata, '$.type') = ?"
            params.append(type_filter)
    else:
        sql = "SELECT id, content, metadata, created_at FROM thoughts WHERE 1=1"
        if type_filter:
            sql += " AND json_extract(metadata, '$.type') = ?"
            params.append(type_filter)

    if days:
        sql += " AND created_at >= datetime('now', ? || ' days')"
        params.append(f"-{int(days)}")

    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    return [
        {
            "id": row["id"],
            "content": row["content"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Statistiken
# ---------------------------------------------------------------------------


def get_stats(con: sqlite3.Connection) -> dict[str, Any]:
    """Aggregiert Statistiken über alle Thoughts.

    Args:
        con: Aktive SQLite Connection

    Returns:
        Dictionary mit total, oldest, newest, types, top_topics, top_people
    """
    total = con.execute("SELECT COUNT(*) FROM thoughts").fetchone()[0]

    date_row = con.execute(
        "SELECT MIN(created_at) AS oldest, MAX(created_at) AS newest FROM thoughts"
    ).fetchone()

    rows = con.execute("SELECT metadata FROM thoughts").fetchall()

    types: dict[str, int] = {}
    topics: dict[str, int] = {}
    people: dict[str, int] = {}

    for row in rows:
        m = json.loads(row["metadata"])
        t = m.get("type")
        if t:
            types[t] = types.get(t, 0) + 1
        for topic in m.get("topics", []):
            topics[topic] = topics.get(topic, 0) + 1
        for person in m.get("people", []):
            people[person] = people.get(person, 0) + 1

    def top(d: dict[str, int], n: int = 10) -> list[tuple[str, int]]:
        return sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]

    return {
        "total": total,
        "oldest": date_row["oldest"] if date_row else None,
        "newest": date_row["newest"] if date_row else None,
        "types": dict(top(types)),
        "top_topics": dict(top(topics)),
        "top_people": dict(top(people)),
    }


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


def export_thoughts(
    con: sqlite3.Connection,
    include_embeddings: bool = False,
) -> list[dict[str, Any]]:
    """Exportiert alle Thoughts als Liste von Dicts.

    Args:
        con: Aktive SQLite Connection
        include_embeddings: Ob Embeddings mit exportiert werden sollen

    Returns:
        Liste aller Thoughts als Dictionaries
    """
    rows = con.execute(
        "SELECT rowid, id, content, metadata, created_at, updated_at FROM thoughts"
    ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = {
            "id": row["id"],
            "content": row["content"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_embeddings:
            vec_row = con.execute(
                "SELECT embedding FROM thoughts_vec WHERE rowid = ?", (row["rowid"],)
            ).fetchone()
            if vec_row:
                raw: bytes = vec_row["embedding"]
                n = len(raw) // 4
                entry["embedding"] = list(struct.unpack(f"{n}f", raw))
            else:
                entry["embedding"] = None
        results.append(entry)
    return results


def import_thought(
    con: sqlite3.Connection,
    thought_id: str,
    content: str,
    embedding: list[float],
    metadata: dict[str, Any],
    created_at: str | None = None,
    updated_at: str | None = None,
    on_conflict: str = "skip",
) -> str:
    """Importiert einen einzelnen Thought mit vorgegebener ID.

    Args:
        con: Aktive SQLite Connection
        thought_id: UUID des Thoughts
        content: Text des Thoughts
        embedding: 1536-dimensionaler Embedding-Vektor
        metadata: Metadaten als Dictionary
        created_at: Optionaler Zeitstempel
        updated_at: Optionaler Zeitstempel
        on_conflict: 'skip' oder 'replace' bei existierender ID

    Returns:
        Status: 'inserted', 'replaced' oder 'skipped'
    """
    existing = con.execute(
        "SELECT rowid FROM thoughts WHERE id = ?", (thought_id,)
    ).fetchone()

    if existing:
        if on_conflict == "skip":
            return "skipped"
        # replace: alte Zeilen löschen
        con.execute("DELETE FROM thoughts_vec WHERE rowid = ?", (existing["rowid"],))
        con.execute("DELETE FROM thoughts WHERE id = ?", (thought_id,))

    meta_json = json.dumps(metadata, ensure_ascii=False)
    vec_bytes = _serialize_vec(embedding)

    ts_fields = ""
    ts_values: tuple = ()
    if created_at and updated_at:
        ts_fields = ", created_at, updated_at"
        ts_values = (thought_id, content, meta_json, created_at, updated_at)
    elif created_at:
        ts_fields = ", created_at"
        ts_values = (thought_id, content, meta_json, created_at)
    else:
        ts_values = (thought_id, content, meta_json)

    cur = con.execute(
        f"INSERT INTO thoughts (id, content, metadata{ts_fields}) VALUES (?, ?, ?{', ?' * (len(ts_values) - 3)})",
        ts_values,
    )
    rowid = cur.lastrowid
    con.execute(
        "INSERT INTO thoughts_vec (rowid, embedding) VALUES (?, ?)",
        (rowid, vec_bytes),
    )
    con.commit()
    return "replaced" if existing else "inserted"
