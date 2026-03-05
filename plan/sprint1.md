# Sprint 1: Sicherheit & Stabilität

**Zeitraum:** 2026-03-05
**Status:** ✅ Abgeschlossen

---

## Tasks

### Task 1: SQL-Injection Fix in `db.py` ✅

**Problem:**
```python
sql += f" AND created_at >= datetime('now', '-{int(days)} days')"
```

**Lösung:**
```python
sql += " AND created_at >= datetime('now', ? || ' days')"
params.append(f"-{int(days)}")
```

**Datei:** `db.py`, Funktion `list_thoughts()`
**Zeilen:** ~158

---

### Task 2: API Retry-Logik in `ai.py` ✅

**Problem:** Keine Retry-Logik bei temporären Fehlern

**Lösung:**
- `tenacity` Bibliothek hinzugefügt
- Retry-Decorator für API-Calls
- Exponential Backoff: 2s, 4s, 8s
- Max 3 Versuche
- Retry bei: `ConnectError`, `ReadError`, `TimeoutException`

**Dateien:**
- `requirements.txt` → `tenacity>=8.2.0`
- `ai.py` → `_get_embedding_call()` und `_extract_metadata_call()` mit `@retry`

---

### Task 3: API-Key Validierung in `config.py` ✅

**Problem:** Keine Validierung des API-Key Formats

**Lösung:**
```python
def validate_openrouter_key(key: str) -> bool:
    pattern = r"^sk-or-[a-zA-Z0-9_-]{14,}$"
    return bool(re.match(pattern, key)) or (key.startswith("sk-or-") and len(key) >= 20)
```

**Datei:** `config.py`

---

## Zusätzlich erledigt

- `.env.example` erstellt
- **Test-Suite erstellt** mit 64 Tests
- **Test-Coverage: 81%** (Ziel: > 80%)

---

## Test-Suite

```
tests/
├── __init__.py
├── conftest.py        # Fixtures
├── test_ai.py         # 8 Tests (API-Calls, Retry)
├── test_cli.py        # 21 Tests (Formatter, Commands)
├── test_config.py     # 11 Tests (Validierung)
├── test_db.py         # 18 Tests (Datenbank)
└── test_server.py     # 6 Tests (Server)
```

**Coverage pro Modul:**
| Modul | Coverage |
|-------|----------|
| ai.py | 88% |
| cli.py | 61% |
| config.py | 96% |
| db.py | 85% |
| server.py | 27% |
| **Total** | **81%** |

---

## Checklist

- [x] Task 1: SQL-Injection Fix
- [x] Task 2: tenacity zu requirements.txt
- [x] Task 2: Retry-Decorator in ai.py
- [x] Task 3: API-Key Validierung
- [x] .env.example erstellt
- [x] Test-Suite erstellt (64 Tests)
- [x] Test-Coverage > 80% erreicht
- [x] plan.md aktualisiert
