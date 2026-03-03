# open-brain

Persönlicher Gedankenspeicher mit semantischer Vektorsuche.  
MCP-Server (HTTP) + CLI, gebaut mit Python, FastMCP, SQLite und sqlite-vec.

---

## Voraussetzungen

- Python 3.11+
- Ein [OpenRouter](https://openrouter.ai)-API-Key

---

## Installation

```bash
pip install -r open-brain/requirements.txt
```

Das installiert:

| Paket | Zweck |
|---|---|
| `fastmcp` | MCP-Server-Framework |
| `httpx` | Async HTTP-Client für OpenRouter |
| `sqlite-vec` | SQLite-Erweiterung für Vektorsuche (bringt `.so`/`.dylib` mit) |

> **Hinweis:** `sqlite-vec` wird als Python-Package installiert und lädt die
> native Extension automatisch. Kein manuelles Kompilieren oder Setzen von
> Pfad-Variablen nötig.

---

## Konfiguration

Lege eine `.env`-Datei an (oder setze die Variablen in der Shell):

```bash
# Pflicht
export OPENROUTER_API_KEY="sk-or-..."

# Optional – Pfad zur Datenbankdatei (default: open-brain/brain.db)
export OPENBRAIN_DB_PATH="/pfad/zu/brain.db"
```

Die Datenbank wird beim ersten Start automatisch angelegt.

---

## MCP-Server starten

```bash
python open-brain/server.py
```

### Optionen

| Option | Default | Beschreibung |
|---|---|---|
| `--port` | `4567` | HTTP-Port |
| `--host` | `0.0.0.0` | Bind-Adresse |
| `--key` | _(kein)_ | API-Key für Authentifizierung |

### Mit Authentifizierung

```bash
python open-brain/server.py --port 4567 --key meingeheimespasswort
```

Clients müssen dann bei jedem Request entweder:
- den Header `x-brain-key: meingeheimespasswort` mitsenden, **oder**
- den Query-Parameter `?key=meingeheimespasswort` anhängen.

---

## CLI

```bash
# Thought speichern
python open-brain/cli.py add "Ich sollte nächste Woche das Deployment automatisieren."

# Semantisch suchen
python open-brain/cli.py search "Deployment automatisieren"

# Auflisten (mit Filtern)
python open-brain/cli.py list --limit 20
python open-brain/cli.py list --type task --days 7
python open-brain/cli.py list --topic python --person "Max Mustermann"

# Statistiken
python open-brain/cli.py stats

# JSON-Ausgabe (statt Markdown)
python open-brain/cli.py stats --json
python open-brain/cli.py search "Projekt" --json

# Export
python open-brain/cli.py export backup.json          # nur content + metadata
python open-brain/cli.py export backup_full.json --full  # inkl. Embeddings

# Import
python open-brain/cli.py import backup.json          # Embeddings werden neu generiert
python open-brain/cli.py import backup_full.json     # Embeddings aus Datei übernommen
python open-brain/cli.py import backup.json --reembed            # Embeddings immer neu
python open-brain/cli.py import backup.json --on-conflict replace  # Duplikate überschreiben
```

### Filter für `list`

| Flag | Beschreibung |
|---|---|
| `--type` | `observation`, `task`, `idea`, `reference`, `person_note` |
| `--topic` | Topic-Tag (z. B. `python`) |
| `--person` | Name einer erwähnten Person |
| `--days N` | Nur Thoughts der letzten N Tage |
| `--limit N` | Max. Anzahl Ergebnisse (default: 10) |

### Optionen für `export`

| Flag | Beschreibung |
|---|---|
| `DATEI` | Zieldatei (optional, default: stdout) |
| `--full` | Embeddings mit exportieren – nötig für verlustfreien Import ohne Re-Embedding |

### Optionen für `import`

| Flag | Beschreibung |
|---|---|
| `DATEI` | Quelldatei (JSON, Pflicht) |
| `--reembed` | Embeddings aus Datei ignorieren, immer neu via API generieren |
| `--on-conflict` | `skip` (default) oder `replace` – Verhalten bei bereits vorhandener ID |

Das Import-Format ist der direkte Export-Output (`{"version":1, "thoughts":[...]}`) oder eine rohe JSON-Liste.

---

## MCP-Client-Konfiguration (Claude Desktop)

In `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "open-brain": {
      "url": "http://localhost:4567/mcp",
      "headers": {
        "x-brain-key": "meingeheimespasswort"
      }
    }
  }
}
```

Ohne Auth (kein `--key`):

```json
{
  "mcpServers": {
    "open-brain": {
      "url": "http://localhost:4567/mcp"
    }
  }
}
```

---

## Verfügbare MCP-Tools

| Tool | Beschreibung |
|---|---|
| `add(thought)` | Thought speichern – extrahiert Metadaten & Embedding automatisch |
| `search(text, limit?, threshold?)` | Semantische Suche nach Bedeutung |
| `list(limit?, type?, topic?, person?, days?)` | Thoughts auflisten mit Filtern |
| `stats()` | Übersicht: Anzahl, Typen, Topics, Personen |

---

## Datenbankstruktur

```
thoughts            – Haupt-Tabelle (id, content, metadata JSON, created_at, updated_at)
thoughts_vec        – Virtuelle sqlite-vec Tabelle (rowid → embedding float[1536])
```

Verknüpfung über `rowid`. Vektorsuche ist Brute-Force Cosine KNN – ausreichend
für persönliche Nutzung (bis ~100k Thoughts).

---

## Projektstruktur

```
open-brain/
├── config.py        # Umgebungsvariablen
├── db.py            # Datenbankschema & Queries
├── ai.py            # OpenRouter: Embeddings & Metadata
├── server.py        # FastMCP HTTP-Server
├── cli.py           # CLI-Anwendung
├── requirements.txt
└── README.md
```
