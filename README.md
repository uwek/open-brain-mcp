# open-brain-mcp

Ein MCP-Server und CLI-Anwendung zum Speichern von Informationen mit semantischer Vektorsuche. Gedanken, Notizen und Ideen werden gespeichert und auf Anfrage als Kontext zur Verfügung gestellt.

Der MCP-Server ist im Produktionsbetrieb per HTTP erreichbar und kann mit Claude Desktop oder anderen MCP-Clients genutzt werden.

---

## Features

- **Semantische Suche**: Finde Gedanken nach Bedeutung, nicht nur nach Keywords
- **Automatische Metadaten**: Extrahiert Typ, Topics, Personen und Action Items via GPT-4o-mini
- **MCP-Server**: Integration mit Claude Desktop und anderen MCP-Clients
- **CLI**: Komfortables Kommandozeilen-Interface
- **Export/Import**: Backup und Restore aller Daten

---

## Tech-Stack

| Komponente | Technologie |
|------------|-------------|
| Sprache | Python 3.11+ |
| MCP-Framework | FastMCP |
| Datenbank | SQLite + sqlite-vec |
| LLM/Embeddings | OpenRouter (GPT-4o-mini, text-embedding-3-small) |

---

## Voraussetzungen

- Python 3.11+
- Ein [OpenRouter](https://openrouter.ai)-API-Key

---

## Installation

### Mit pip

```bash
# Repository klonen
git clone https://github.com/user/open-brain-mcp.git
cd open-brain-mcp

# Virtuelle Umgebung erstellen
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# oder: .venv\Scripts\activate  # Windows

# Installieren
pip install -e .

# Mit Entwicklungs-Dependencies (Tests, Linting)
pip install -e ".[dev]"
```

### sqlite-vec Installation

`sqlite-vec` wird automatisch als Python-Package installiert und bringt die native Extension mit. Keine manuelle Installation nötig!

Falls dennoch Probleme auftreten:

**macOS:**
```bash
pip install sqlite-vec
```

**Linux:**
```bash
pip install sqlite-vec
```

**Hinweis:** Die native Bibliothek wird automatisch heruntergeladen. Bei Architektur-Problemen kann die Umgebungsvariable `SQLITE_VEC_PATH` gesetzt werden, um einen alternativen Pfad zur Bibliothek anzugeben.

### Konfiguration

Kopiere `.env.example` zu `.env` und fülle die Werte aus:

```bash
# Pflicht
OPENROUTER_API_KEY=sk-or-your-key-here

# Optional
OPENBRAIN_DB_PATH=./brain.db
OPENROUTER_RATE_LIMIT=2.0
OPENBRAIN_EMBEDDING_DIM=1536
OPENBRAIN_LOG_LEVEL=INFO
```

Die Datenbank wird beim ersten Start automatisch erstellt.

---

## Schnellstart

### Server starten

```bash
open-brain --port 4567
# oder: python server.py
```

### Gedanken speichern (CLI)

```bash
open-brain add "Ich sollte das Deployment mit GitHub Actions automatisieren."
```

### Suchen (CLI)

```bash
open-brain search "Deployment"
```

### Mit Claude Desktop nutzen

Füge zu `~/Library/Application Support/Claude/claude_desktop_config.json` hinzu:

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

## Funktionsweise

### add(thought)

Speichert einen neuen Gedanken mit automatisch extrahierten Metadaten:

1. **Metadaten-Extraktion**: Via `openai/gpt-4o-mini` werden extrahiert:
   - `people`: Erwähnte Personen
   - `action_items`: Implizite To-Dos
   - `dates_mentioned`: Erwähnte Daten (YYYY-MM-DD)
   - `topics`: 1-3 kurze Topic-Tags
   - `type`: `observation`, `task`, `idea`, `reference` oder `person_note`

2. **Embedding-Erzeugung**: Via `openai/text-embedding-3-small` wird ein 1536-dimensionaler Vektor erzeugt.

3. **Speicherung**: Gedanke, Embedding und Metadaten werden in SQLite gespeichert.

### search(text)

Semantische Suche nach Bedeutung. Nutzt Vektorähnlichkeit, um relevante Gedanken zu finden.

### list_thoughts()

Listet gespeicherte Gedanken mit optionalen Filtern:
- `type`: Nach Typ filtern
- `topic`: Nach Topic filtern
- `person`: Nach Person filtern
- `days`: Nach Zeitraum filtern

### stats()

Zeigt Statistiken: Gesamtanzahl, Typen, Top-Topics und Personen.

### health()

Health-Check mit Datenbank-Connectivity-Test für Monitoring.

---

## CLI-Referenz

### Gedanken speichern

```bash
# Direkt
open-brain add "Mein Gedanke..."

# Aus Datei
open-brain add --file notes.txt

# JSON-Ausgabe
open-brain add "Test" --json
```

### Suchen

```bash
# Semantische Suche
open-brain search "Suchbegriff"

# Mit Optionen
open-brain search "python" --limit 20 --threshold 0.5
open-brain search "meeting" --json
```

### Auflisten

```bash
# Alle Gedanken
open-brain list

# Mit Filtern
open-brain list --type task --days 7
open-brain list --topic python --person "Max"
open-brain list --limit 20 --json
```

### Statistiken

```bash
open-brain stats
open-brain stats --json
```

### Export/Import

```bash
# Export
open-brain export backup.json
open-brain export backup_full.json --full  # inkl. Embeddings

# Import
open-brain import backup.json
open-brain import backup.json --on-conflict replace
```

---

## MCP-Server

### Startoptionen

| Option | Default | Beschreibung |
|--------|---------|--------------|
| `--port` | 4567 | HTTP-Port |
| `--host` | 0.0.0.0 | Bind-Adresse |
| `--key` | - | API-Key für Authentifizierung |

### Mit Authentifizierung

```bash
open-brain --key mein-geheimes-passwort
```

Clients müssen dann `x-brain-key` Header oder `?key=` Parameter senden.

### Verfügbare Tools

| Tool | Beschreibung |
|------|--------------|
| `add(thought)` | Gedanke speichern mit automatischen Metadaten |
| `search(text, limit?, threshold?)` | Semantische Suche |
| `list_thoughts(limit?, type?, topic?, person?, days?)` | Auflisten mit Filtern |
| `stats()` | Statistiken |
| `health()` | Health-Check mit DB-Connectivity |

---

## Datenbankstruktur

```sql
-- Haupttabelle
CREATE TABLE thoughts (
  id TEXT PRIMARY KEY,
  content TEXT NOT NULL,
  metadata TEXT DEFAULT '{}',
  created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Vektor-Tabelle (virtuell)
CREATE VIRTUAL TABLE thoughts_vec USING vec0(
  rowid INTEGER PRIMARY KEY,
  embedding float[1536]
);
```

Verknüpfung über `rowid`. Vektorsuche via sqlite-vec (Cosine KNN).

---

## Konfiguration

### Umgebungsvariablen

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `OPENROUTER_API_KEY` | - | **Pflicht**: OpenRouter API-Key |
| `OPENBRAIN_DB_PATH` | `./brain.db` | Pfad zur SQLite-Datenbank |
| `OPENROUTER_RATE_LIMIT` | 2.0 | API-Calls pro Sekunde |
| `OPENBRAIN_EMBEDDING_DIM` | 1536 | Embedding-Dimension |
| `OPENBRAIN_LOG_LEVEL` | INFO | Log-Level (DEBUG, INFO, WARNING, ERROR) |

### Embedding-Modelle

| Modell | Dimension | Empfehlung |
|--------|-----------|------------|
| `text-embedding-3-small` | 1536 | Default, guter Kompromiss |
| `text-embedding-3-large` | 3072 | Höhere Qualität, mehr Kosten |
| `text-embedding-ada-002` | 1536 | Älteres Modell |

**Wichtig:** Bei Wechsel der Dimension müssen bestehende Embeddings neu generiert werden!

---

## Entwicklung

### Tests ausführen

```bash
# Alle Tests
pytest tests/ -v

# Mit Coverage
pytest tests/ -v --cov=. --cov-report=term-missing
```

### Code-Qualität

```bash
# Type-Check
mypy *.py

# Linting
ruff check *.py

# Formatierung
ruff format *.py
```

### Projektstruktur

```
open-brain-mcp/
├── config.py        # Konfiguration & Logging
├── db.py            # Datenbankschicht
├── ai.py            # OpenRouter Integration
├── server.py        # MCP-Server
├── cli.py           # CLI-Anwendung
├── pyproject.toml   # Projekt-Konfiguration
├── tests/           # Test-Suite
│   ├── test_ai.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_db.py
│   └── test_server.py
└── README.md
```

---

## Technologie-Stack

- **[FastMCP](https://github.com/anthropics/fastmcp)**: MCP-Server Framework
- **[sqlite-vec](https://github.com/asg017/sqlite-vec)**: Vektorsuche in SQLite
- **[OpenRouter](https://openrouter.ai)**: API für Embeddings und LLM
- **[tenacity](https://github.com/jd/tenacity)**: Retry-Logik

---

## Lizenz

MIT

---

## Beitragen

Issues und Pull Requests sind willkommen!

1. Fork erstellen
2. Feature-Branch: `git checkout -b feature/mein-feature`
3. Commit: `git commit -m 'Add feature'`
4. Push: `git push origin feature/mein-feature`
5. Pull Request öffnen
