# Verbesserungsplan für open-brain-mcp

**Erstellt:** 2026-03-05
**Status:** Entwurf

---

## Übersicht

Dieses Dokument enthält alle identifizierten Verbesserungsvorschläge für das open-brain-mcp Projekt, kategorisiert nach Priorität und geschätztzem Aufwand.

---

## 🔴 Kritische Verbesserungen

### 1. Fehlerbehandlung für API-Aufrufe

**Datei:** `ai.py`
**Aufwand:** Mittel (2-3h)
**Priorität:** Hoch

**Problem:**
Die API-Aufrufe an OpenRouter haben keine Retry-Logik. Bei temporären Netzwerkfehlern oder Rate-Limits schlägt die Anwendung sofort fehl.

**Lösung:**
```python
# Empfehlung: httpx mit Retry oder tenacity verwenden
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_embedding(text: str, client: httpx.AsyncClient | None = None) -> list[float]:
    # ... existing code
```

**Alternativ:** Eigene Retry-Logik mit exponential backoff implementieren.

---

### 2. SQL-Injection-Risiko

**Datei:** `db.py` (Zeile ~158 in `list_thoughts()`)
**Aufwand:** Gering (30min)
**Priorität:** Hoch

**Problem:**
Der `days`-Parameter wird ungefiltert in den SQL-String interpoliert:
```python
sql += f" AND created_at >= datetime('now', '-{int(days)} days')"
```

**Lösung:**
Parameter-Binding verwenden:
```python
sql += " AND created_at >= datetime('now', ? || ' days')"
params.append(f"-{int(days)}")
```

---

### 3. Thread-Safety der Datenbankverbindung

**Datei:** `server.py`
**Aufwand:** Mittel (2h)
**Priorität:** Hoch

**Problem:**
Die SQLite-Connection (`con`) wird im Server-Closure gehalten und bei allen Requests wiederverwendet. Bei concurrent HTTP-Requests kann das zu Race-Conditions führen.

**Lösung:**
Option A: Connection pro Request
```python
@mcp.tool()
async def add(thought: str) -> str:
    con = db.get_connection()  # Neue Connection pro Request
    try:
        # ... logic
    finally:
        con.close()
```

Option B: Thread-Pool mit Connection-Pooling (für höhere Last)

---

## 🟡 Mittlere Priorität

### 4. API-Key Validierung

**Datei:** `config.py`
**Aufwand:** Gering (30min)
**Priorität:** Mittel

**Problem:**
Der API-Key wird nur auf Existenz geprüft, nicht auf Plausibilität. Ein Tippfehler führt zu kryptischen Fehlern erst beim ersten API-Call.

**Lösung:**
```python
def require(name: str, validate: callable = None) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Umgebungsvariable '{name}' ist nicht gesetzt.")
    if validate and not validate(value):
        raise RuntimeError(f"Ungültiger Wert für '{name}'.")
    return value

def validate_openrouter_key(key: str) -> bool:
    return key.startswith("sk-or-") and len(key) > 20

OPENROUTER_API_KEY: str = require("OPENROUTER_API_KEY", validate_openrouter_key)
```

---

### 5. Modernes Projekt-Setup (pyproject.toml)

**Datei:** Neu: `pyproject.toml`, Entfällt: `requirements.txt`
**Aufwand:** Mittel (1-2h)
**Priorität:** Mittel

**Problem:**
- Keine Python-Versionsspezifikation
- Keine Entwicklungs-Abhängigkeiten definiert
- Veraltetes `requirements.txt` Format

**Lösung:**
`pyproject.toml` erstellen mit:
- Python-Version >= 3.11
- Alle Abhängigkeiten mit Versionen
- Entwicklungs-Abhängigkeiten (pytest, ruff, mypy)
- Entry-Points für CLI

---

### 6. Test-Abdeckung

**Datei:** Neu: `tests/`
**Aufwand:** Hoch (4-6h)
**Priorität:** Mittel

**Problem:**
Keine Tests vorhanden. Refactoring ist risikoreich.

**Lösung:**
Minimale Test-Suite erstellen:
```
tests/
├── test_db.py          # Datenbank-Operationen
├── test_ai.py          # API-Mocks für Embedding/Metadata
└── test_server.py      # MCP-Tool-Tests
```

---

### 7. Embedding-Dimension Konfigurierbarkeit

**Datei:** `config.py`, `db.py`
**Aufwand:** Mittel (1-2h)
**Priorität:** Mittel

**Problem:**
`EMBEDDING_DIM = 1536` ist hartkodiert. Wechsel des Embedding-Modells führt zu Inkompatibilität mit bestehenden Daten.

**Lösung:**
- Dimension als Environment-Variable konfigurierbar
- Bei Schema-Erstellung prüfen, ob Dimension zur Tabelle passt
- Migration-Path dokumentieren

---

### 8. Rate-Limiting für OpenRouter API

**Datei:** `ai.py`
**Aufwand:** Mittel (2h)
**Priorität:** Mittel

**Problem:**
Bei vielen schnellen Requests könnte das API-Limit erreicht werden.

**Lösung:**
```python
import asyncio
from contextlib import asynccontextmanager

class RateLimiter:
    def __init__(self, calls_per_second: float = 2.0):
        self._interval = 1.0 / calls_per_second
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._last_call + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = asyncio.get_event_loop().time()
```

---

## 🟢 Nice-to-have / Code Quality

### 9. Entwicklungs-Dateien bereinigen

**Dateien:** `prompt.md`, `run.sh`
**Aufwand:** Gering (15min)
**Priorität:** Niedrig

**Problem:**
- `prompt.md` ist ein Entwicklungs-Prompt, gehört nicht ins Repo
- `run.sh` ist ein lokales Start-Skript

**Lösung:**
- `prompt.md` löschen oder nach `docs/` verschieben
- `run.sh` in README.md als Beispiel dokumentieren und löschen

---

### 10. `.env.example` erstellen

**Datei:** Neu: `.env.example`
**Aufwand:** Gering (10min)
**Priorität:** Niedrig

**Lösung:**
```bash
# Pflicht
OPENROUTER_API_KEY=sk-or-your-key-here

# Optional
OPENBRAIN_DB_PATH=/path/to/brain.db
```

---

### 11. Typannotationen vervollständigen

**Datei:** Alle `.py`-Dateien
**Aufwand:** Mittel (2h)
**Priorität:** Niedrig

**Problem:**
Viele Funktionen haben unvollständige Type-Hints.

**Lösung:**
- `mypy` für statische Typprüfung hinzufügen
- Alle `dict` durch `dict[str, Any]` ersetzen
- Rückgabe-Typen ergänzen

---

### 12. Logging-Infrastruktur

**Datei:** Alle Module
**Aufwand:** Mittel (1-2h)
**Priorität:** Niedrig

**Problem:**
Nur `print()` Statements. Keine konfigurierbare Log-Ausgabe.

**Lösung:**
```python
import logging

logger = logging.getLogger(__name__)

# In server.py:
logging.basicConfig(
    level=logging.INFO,
    format="[open-brain] %(levelname)s: %(message)s"
)
```

---

### 13. Health-Check Endpoint

**Datei:** `server.py`
**Aufwand:** Gering (30min)
**Priorität:** Niedrig

**Problem:**
Keine Möglichkeit, Server-Health zu prüfen (für Load-Balancer, Kubernetes, etc.)

**Lösung:**
FastMCP erlaubt zusätzliche Routes. Minimal-Lösung:
```python
# Separate Health-Route via Starlette/FastAPI
# oder separater `/health`-Endpunkt
```

---

### 14. Authentifizierung verbessern

**Datei:** `server.py`
**Aufwand:** Mittel (2-3h)
**Priorität:** Niedrig

**Problem:**
Key wird im Klartext verglichen. Für Produktion nicht ausreichend.

**Lösung:**
- Bearer-Token-Auth (RFC 6750)
- Oder: HMAC-basierte Signatur
- Oder: OAuth2-Integration

---

### 15. Graceful Shutdown

**Datei:** `server.py`
**Aufwand:** Gering (30min)
**Priorität:** Niedrig

**Problem:**
Nur `KeyboardInterrupt` wird abgefangen. Kein sauberer Shutdown bei SIGTERM.

**Lösung:**
```python
import signal

def shutdown_handler(signum, frame):
    print("\n[open-brain] Shutdown signal received...")
    # cleanup
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
```

---

## 📁 Vorgeschlagene Projektstruktur

```
open-brain-mcp/
├── pyproject.toml              # Statt requirements.txt
├── .env.example                # Neu
├── .gitignore                  # Erweitern
├── README.md                   # Aktualisieren
├── plan.md                     # Dieses Dokument
├── src/
│   └── open_brain/
│       ├── __init__.py          # Neu
│       ├── config.py
│       ├── db.py
│       ├── ai.py
│       ├── server.py
│       └── cli.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Fixtures
│   ├── test_db.py
│   ├── test_ai.py
│   └── test_server.py
└── docs/
    ├── ARCHITECTURE.md          # Architektur-Doku
    └── DEPLOYMENT.md            # Deployment-Guide
```

---

## 📊 Priorisierung

| # | Verbesserung | Aufwand | Priorität | Status |
|---|-------------|---------|-----------|--------|
| 2 | SQL-Injection fix | Gering | Hoch | ✅ Done |
| 1 | API Retry-Logik | Mittel | Hoch | ✅ Done |
| 3 | Thread-Safety DB | Mittel | Hoch | ✅ Done |
| 4 | API-Key Validierung | Gering | Mittel | ✅ Done |
| 5 | pyproject.toml | Mittel | Mittel | ⬜ Todo |
| 6 | Tests (>80% Coverage) | Hoch | Mittel | ✅ Done |
| 7 | Embedding-Dimension | Mittel | Mittel | ⬜ Todo |
| 8 | Rate-Limiter | Mittel | Mittel | ✅ Done |
| 10 | .env.example | Gering | Niedrig | ✅ Done |
| 9 | Dateien bereinigen | Gering | Niedrig | ⬜ Todo |
| 11 | Type-Hints | Mittel | Niedrig | ⬜ Todo |
| 12 | Logging | Mittel | Niedrig | ⬜ Todo |
| 13 | Health-Check | Gering | Niedrig | ⬜ Todo |
| 15 | Graceful Shutdown | Gering | Niedrig | ⬜ Todo |
| 14 | Auth verbessern | Mittel | Niedrig | ⬜ Todo |

---

## 🚀 Empfohlene Reihenfolge

1. **Sprint 1 (Sicherheit)**: #2 SQL-Injection, #1 Retry-Logik, #4 API-Key Validierung
2. **Sprint 2 (Stabilität)**: #3 Thread-Safety, #8 Rate-Limiter
3. **Sprint 3 (Qualität)**: #5 pyproject.toml, #6 Tests, #11 Type-Hints
4. **Sprint 4 (Ops)**: #10 .env.example, #12 Logging, #13 Health-Check, #15 Graceful Shutdown
5. **Sprint 5 (Cleanup)**: #9 Dateien bereinigen, #14 Auth (optional)

---

*Dieses Dokument sollte nach der Implementierung einzelner Punkte aktualisiert werden.*