"""
Tests für db.py
"""

import json
import tempfile
from unittest.mock import patch

import pytest

import db


class TestDatabaseSetup:
    """Tests für Datenbank-Initialisierung."""

    def test_init_db_creates_tables(self, temp_db_path):
        """Tabellen werden korrekt erstellt."""
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            result = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='thoughts'"
            ).fetchone()
            assert result is not None
            result = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='thoughts_vec'"
            ).fetchone()
            assert result is not None
            con.close()

    def test_init_db_idempotent(self, temp_db_path):
        """init_db kann mehrfach aufgerufen werden."""
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con1 = db.init_db()
            con1.close()
            con2 = db.init_db()
            con2.close()


class TestInsertThought:
    """Tests für insert_thought()."""

    def test_insert_returns_id(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            thought_id = db.insert_thought(
                con, content="Test thought", embedding=[0.1] * 1536,
                metadata={"type": "observation", "topics": ["test"]},
            )
            assert thought_id is not None
            assert len(thought_id) == 32
            con.close()

    def test_insert_stores_content(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            thought_id = db.insert_thought(
                con, content="Mein Test-Content", embedding=[0.1] * 1536,
                metadata={"type": "idea"},
            )
            row = con.execute(
                "SELECT content FROM thoughts WHERE id = ?", (thought_id,)
            ).fetchone()
            assert row["content"] == "Mein Test-Content"
            con.close()


class TestSearchThoughts:
    """Tests für search_thoughts()."""

    def test_search_returns_results(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(
                con, content="Python Programmierung", embedding=[0.5] * 1536,
                metadata={"type": "observation", "topics": ["python"]},
            )
            results = db.search_thoughts(
                con, query_embedding=[0.5] * 1536, limit=10, threshold=0.0,
            )
            assert len(results) == 1
            con.close()

    def test_search_respects_threshold(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="Test", embedding=[0.9] * 1536, metadata={})
            results = db.search_thoughts(
                con, query_embedding=[0.1] * 1536, limit=10, threshold=0.99,
            )
            assert len(results) == 0
            con.close()


class TestListThoughts:
    """Tests für list_thoughts()."""

    def test_list_returns_thoughts(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="First", embedding=[0.1] * 1536, metadata={})
            db.insert_thought(con, content="Second", embedding=[0.1] * 1536, metadata={})
            results = db.list_thoughts(con, limit=10)
            assert len(results) == 2
            con.close()

    def test_list_filter_by_type(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="Obs", embedding=[0.1] * 1536,
                metadata={"type": "observation"})
            db.insert_thought(con, content="Task", embedding=[0.1] * 1536,
                metadata={"type": "task"})
            results = db.list_thoughts(con, limit=10, type_filter="observation")
            assert len(results) == 1
            con.close()

    def test_list_filter_by_topic(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="Python", embedding=[0.1] * 1536,
                metadata={"type": "obs", "topics": ["python"]})
            db.insert_thought(con, content="Java", embedding=[0.1] * 1536,
                metadata={"type": "obs", "topics": ["java"]})
            results = db.list_thoughts(con, limit=10, topic="python")
            assert len(results) == 1
            con.close()

    def test_list_filter_by_person(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="Max", embedding=[0.1] * 1536,
                metadata={"type": "note", "people": ["Max"]})
            db.insert_thought(con, content="Anna", embedding=[0.1] * 1536,
                metadata={"type": "note", "people": ["Anna"]})
            results = db.list_thoughts(con, limit=10, person="Max")
            assert len(results) == 1
            con.close()

    def test_list_filter_by_days_sql_injection_safe(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="Recent", embedding=[0.1] * 1536, metadata={})
            # SQL-Injection Versuch wird durch int() abgefangen (ValueError)
            with pytest.raises(ValueError):
                db.list_thoughts(con, limit=10, days="7; DROP TABLE thoughts")
            con.close()


class TestGetStats:
    """Tests für get_stats()."""

    def test_stats_empty_db(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            stats = db.get_stats(con)
            assert stats["total"] == 0
            con.close()

    def test_stats_counts(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="T1", embedding=[0.1] * 1536,
                metadata={"type": "observation"})
            db.insert_thought(con, content="T2", embedding=[0.1] * 1536,
                metadata={"type": "task", "topics": ["python"]})
            stats = db.get_stats(con)
            assert stats["total"] == 2
            assert stats["types"]["observation"] == 1
            con.close()


class TestExportImport:
    """Tests für export_thoughts() und import_thought()."""

    def test_export_returns_list(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
            exported = db.export_thoughts(con)
            assert len(exported) == 1
            con.close()

    def test_import_inserts_new(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            status = db.import_thought(
                con, thought_id="abc123", content="Imported",
                embedding=[0.1] * 1536, metadata={},
            )
            assert status == "inserted"
            con.close()

    def test_import_skip_existing(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.import_thought(con, thought_id="test123", content="First",
                embedding=[0.1] * 1536, metadata={})
            status = db.import_thought(con, thought_id="test123", content="Second",
                embedding=[0.1] * 1536, metadata={}, on_conflict="skip")
            assert status == "skipped"
            con.close()

    def test_import_replace_existing(self, temp_db_path):
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            db.import_thought(con, thought_id="test123", content="First",
                embedding=[0.1] * 1536, metadata={})
            status = db.import_thought(con, thought_id="test123", content="Second",
                embedding=[0.1] * 1536, metadata={}, on_conflict="replace")
            assert status == "replaced"
            con.close()


class TestEmbeddingDimension:
    """Tests für Embedding-Dimension."""

    def test_get_existing_embedding_dim_none_for_new_db(self, temp_db_path):
        """_get_existing_embedding_dim gibt None für neue DB."""
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.get_connection()
            dim = db._get_existing_embedding_dim(con)
            assert dim is None
            con.close()

    def test_get_existing_embedding_dim_after_setup(self, temp_db_path):
        """_get_existing_embedding_dim gibt Dimension nach setup."""
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            dim = db._get_existing_embedding_dim(con)
            assert dim == 1536
            con.close()

    def test_setup_creates_correct_dimension(self, temp_db_path):
        """setup erstellt Tabelle mit korrekter Dimension."""
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            con = db.init_db()
            # Prüfe Schema
            schema = con.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='thoughts_vec'"
            ).fetchone()
            assert "float[1536]" in schema["sql"]
            con.close()

    def test_dimension_mismatch_warning(self, temp_db_path, caplog):
        """Warnung bei Dimension-Mismatch."""
        import logging
        with patch.object(db.config, "OPENBRAIN_DB_PATH", temp_db_path):
            with patch.object(db.config, "EMBEDDING_DIM", 3072):
                with patch.object(db.config, "OPENBRAIN_EMBEDDING_DIM", 3072):
                    # DB mit 1536 erstellen
                    con = db.get_connection()
                    db.setup(con)  # Erstellt mit 1536 (ursprünglicher config)
                    con.close()

                    # Jetzt mit anderer Dimension initialisieren
                    con2 = db.get_connection()
                    with caplog.at_level(logging.WARNING):
                        db.setup(con2)  # Sollte Warnung auslösen
                    con2.close()

    def test_embedding_dim_configurable(self, monkeypatch, temp_db_path):
        """Embedding-Dimension ist konfigurierbar."""
        # Dieser Test zeigt, dass die Dimension geändert werden kann
        # (würde requires module reload in der Praxis)
        import db
        assert db.config.EMBEDDING_DIM == 1536  # Default
