"""
pytest fixtures für open-brain Tests.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# GLOBALE TEST-KONFIGURATION
# =============================================================================

# Test-DB Pfad - wird einmalig für die gesamte Session erstellt
_TEST_DB_PATH: str | None = None


def pytest_configure(config):
    """Wird aufgerufen bevor Tests gesammelt werden.
    
    Setzt Umgebungsvariablen für Tests, bevor Module importiert werden.
    Stellt sicher, dass NIEMALS die produktive brain.db verwendet wird.
    """
    global _TEST_DB_PATH
    
    # Erstelle temporäre Test-DB
    test_db = tempfile.NamedTemporaryFile(suffix="_test.db", prefix="brain_", delete=False)
    _TEST_DB_PATH = test_db.name
    test_db.close()
    
    # Setze Umgebungsvariablen VOR dem Import der Module
    os.environ["OPENROUTER_API_KEY"] = "sk-or-test-key-12345678"
    os.environ["OPENBRAIN_DB_PATH"] = _TEST_DB_PATH
    os.environ["OPENROUTER_RATE_LIMIT"] = "100.0"  # Kein Rate-Limit beim Testen


def pytest_unconfigure(config):
    """Wird aufgerufen nach allen Tests.
    
    Löscht die temporäre Test-DB.
    """
    global _TEST_DB_PATH
    if _TEST_DB_PATH and os.path.exists(_TEST_DB_PATH):
        os.unlink(_TEST_DB_PATH)
        _TEST_DB_PATH = None


@pytest.fixture(scope="session")
def test_db_path():
    """Pfad zur globalen Test-Datenbank (Session-weit).
    
    Diese DB wird automatisch beim Test-Start erstellt und nach allen Tests gelöscht.
    Sie wird verwendet, wenn OPENBRAIN_DB_PATH nicht pro Test überschrieben wird.
    """
    return _TEST_DB_PATH


@pytest.fixture
def temp_db_path():
    """Erstellt eine isolierte temporäre Datenbankdatei für Tests.
    
    Für Tests, die eine komplett frische, isolierte DB brauchen.
    Die Datei wird nach dem Test automatisch gelöscht.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def mock_db():
    """Erstellt eine frische Datenbank für jeden Test mit clean state.
    
    Verwendet die globale Test-DB, leert aber alle Tabellen vor jedem Test.
    """
    import db
    
    # Verwende die globale Test-DB
    con = db.init_db()
    
    # Clean state: Alle Tabellen leeren
    con.execute("DELETE FROM thoughts")
    con.commit()
    
    yield con
    
    con.close()


@pytest.fixture
def sample_embedding():
    """Ein 1536-dimensionaler Embedding-Vektor zum Testen."""
    return [0.1] * 1536


@pytest.fixture
def sample_metadata():
    """Beispiel-Metadaten für einen Thought."""
    return {
        "type": "observation",
        "topics": ["python", "testing"],
        "people": ["Max"],
        "action_items": [],
        "dates_mentioned": [],
    }


@pytest.fixture
def sample_thought():
    """Ein Beispielsatz für Tests."""
    return "Ich sollte mehr Python-Tests schreiben."


@pytest.fixture
def mock_httpx_response():
    """Erstellt einen Mock für httpx.Response."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_embedding_response(mock_httpx_response):
    """Mock für Embedding-API-Response."""
    mock_httpx_response.json.return_value = {
        "data": [{"embedding": [0.1] * 1536}]
    }
    return mock_httpx_response


@pytest.fixture
def mock_metadata_response(mock_httpx_response):
    """Mock für Metadata-API-Response."""
    mock_httpx_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "type": "observation",
                        "topics": ["test"],
                        "people": [],
                        "action_items": [],
                        "dates_mentioned": [],
                    })
                }
            }
        ]
    }
    return mock_httpx_response


@pytest.fixture
def mock_async_client(mock_embedding_response, mock_metadata_response):
    """Erstellt einen Mock für httpx.AsyncClient."""
    client = MagicMock()
    client.post = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client
