"""
pytest fixtures für open-brain Tests.
"""

import json
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Setze Test-Umgebungsvariablen VOR dem Import der Module
os.environ["OPENROUTER_API_KEY"] = "sk-or-test-key-12345678"
os.environ["OPENBRAIN_DB_PATH"] = ":memory:"


@pytest.fixture
def temp_db_path():
    """Erstellt eine temporäre Datenbankdatei für Tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def mock_db(temp_db_path):
    """Erstellt eine frische In-Memory-Datenbank für jeden Test."""
    import db

    # Patch den DB-Pfad
    with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
        con = db.init_db()
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
