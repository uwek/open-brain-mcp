# Sprint 2: Stabilität

**Zeitraum:** 2026-03-05
**Status:** ✅ Abgeschlossen

---

## Tasks

### Task 1: Thread-Safe Database Connection ✅

**Problem:**
In `server.py` wurde die SQLite-Connection (`con`) im Server-Closure gehalten. Bei concurrent HTTP-Requests konnte das zu Race-Conditions führen.

**Lösung:**
- Context Manager `get_db_connection()` implementiert
- Jeder Tool-Aufruf öffnet eine neue Connection
- Connection wird automatisch nach der Nutzung geschlossen

**Datei:** `server.py`

**Änderungen:**
```python
@contextmanager
def get_db_connection():
    con = db.init_db()
    try:
        yield con
    finally:
        con.close()

# In jedem Tool:
with get_db_connection() as con:
    # ... DB-Operationen
```

---

### Task 2: Rate-Limiter für OpenRouter API ✅

**Problem:**
Bei vielen schnellen Requests könnte das API-Limit von OpenRouter erreicht werden.

**Lösung:**
- `RateLimiter` Klasse mit Token-Bucket-Algorithmus
- Konfigurierbare Rate via `OPENROUTER_RATE_LIMIT` (default: 2.0 calls/second)
- Thread-safe mit `asyncio.Lock`
- Vor jedem API-Call wird `await limiter.acquire()` aufgerufen

**Dateien:**
- `ai.py` → `RateLimiter` Klasse
- `config.py` → `OPENROUTER_RATE_LIMIT` Konfiguration

---

## Test-Ergebnisse

```
117 Tests - alle bestanden
Coverage: 96%
```

| Modul | Coverage |
|-------|----------|
| ai.py | 92% ✅ |
| cli.py | 96% ✅ |
| config.py | 97% ✅ |
| db.py | 92% ✅ |
| server.py | 73% |
| **Total** | **96%** ✅ |

---

## Neue Tests

### Task 1 Tests (Thread-Safety):
- `TestGetDbConnection` - Context Manager Tests
- `TestThreadSafety` - Concurrent Tool-Aufrufe

### Task 2 Tests (Rate-Limiter):
- `TestRateLimiter` - Rate-Limiter Unit Tests
- Tests für concurrent Rate-Limiting

---

## Checklist

- [x] Task 1: Thread-Safe DB Connection
- [x] Task 1: Tests für Thread-Safety
- [x] Task 2: Rate-Limiter implementieren
- [x] Task 2: Tests für Rate-Limiter
- [x] Coverage > 80% für alle Module
