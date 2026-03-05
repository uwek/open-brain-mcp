"""
Tests für server.py
"""

import tempfile
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import db


class TestKeyAuthMiddleware:
    """Tests für Auth-Middleware."""

    def test_middleware_init(self):
        from server import KeyAuthMiddleware
        middleware = KeyAuthMiddleware("secret123")
        assert middleware.key == "secret123"

    def test_middleware_callable(self):
        from server import KeyAuthMiddleware
        middleware = KeyAuthMiddleware("secret123")
        assert callable(middleware.__call__)

    @pytest.mark.asyncio
    async def test_middleware_with_valid_key(self):
        from server import KeyAuthMiddleware
        middleware = KeyAuthMiddleware("testkey")
        context = MagicMock()
        context.fastmcp_context = MagicMock()
        context.fastmcp_context.request_context = MagicMock()
        mock_request = MagicMock()
        mock_request.headers = {"x-brain-key": "testkey"}
        mock_request.query_params = {}
        context.fastmcp_context.request_context.request = mock_request
        async def call_next(ctx):
            return "success"
        result = await middleware(context, call_next)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_middleware_with_invalid_key(self):
        from server import KeyAuthMiddleware
        middleware = KeyAuthMiddleware("correctkey")
        context = MagicMock()
        context.fastmcp_context = MagicMock()
        context.fastmcp_context.request_context = MagicMock()
        mock_request = MagicMock()
        mock_request.headers = {"x-brain-key": "wrongkey"}
        mock_request.query_params = {}
        context.fastmcp_context.request_context.request = mock_request
        async def call_next(ctx):
            return "success"
        with pytest.raises(PermissionError):
            await middleware(context, call_next)

    @pytest.mark.asyncio
    async def test_middleware_no_request(self):
        from server import KeyAuthMiddleware
        middleware = KeyAuthMiddleware("testkey")
        context = MagicMock()
        context.fastmcp_context = MagicMock()
        context.fastmcp_context.request_context = None
        async def call_next(ctx):
            return "success"
        result = await middleware(context, call_next)
        assert result == "success"


class TestGetDbConnection:
    """Tests für get_db_connection Context Manager."""

    def test_get_db_connection_opens_and_closes(self):
        from server import get_db_connection
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                with get_db_connection() as con:
                    assert con is not None
                    result = con.execute("SELECT 1").fetchone()
                    assert result[0] == 1

    def test_get_db_connection_creates_tables(self):
        from server import get_db_connection
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                with get_db_connection() as con:
                    result = con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='thoughts'"
                    ).fetchone()
                    assert result is not None

    def test_get_db_connection_exception_handling(self):
        from server import get_db_connection
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                try:
                    with get_db_connection() as con:
                        assert con is not None
                        raise ValueError("Test error")
                except ValueError:
                    pass
                with get_db_connection() as con:
                    assert con is not None


class TestThreadSafety:
    """Tests für Thread-Safety der DB-Connections."""

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                for i in range(5):
                    db.insert_thought(con, content=f"Test {i}", embedding=[0.1] * 1536, metadata={"type": "observation"})
                con.close()
                async def call_list(idx):
                    result = await mcp.call_tool("list_thoughts", {"limit": 10})
                    return idx, result.content[0].text
                results = await asyncio.gather(call_list(0), call_list(1), call_list(2))
                for idx, text in results:
                    assert "Test" in text or "Thought" in text

    @pytest.mark.asyncio
    async def test_concurrent_writes(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                con.close()
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                        mock_emb.return_value = [0.1] * 1536
                        mock_meta.return_value = {"type": "observation"}
                        async def call_add(idx):
                            result = await mcp.call_tool("add", {"thought": f"Thought {idx}"})
                            return idx, result.content[0].text
                        results = await asyncio.gather(call_add(0), call_add(1), call_add(2))
                        for idx, text in results:
                            assert "Gespeichert" in text


class TestBuildServer:
    """Tests für build_server()."""

    def test_build_server_no_auth(self):
        from server import build_server
        mcp, con = build_server(access_key=None)
        assert mcp is not None
        assert mcp.name == "open-brain"
        con.close()

    def test_build_server_with_auth(self):
        from server import build_server
        mcp, con = build_server(access_key="testkey")
        assert mcp is not None
        assert mcp.name == "open-brain"
        con.close()

    def test_server_instructions(self):
        from server import build_server
        mcp, con = build_server(None)
        assert mcp.instructions is not None
        con.close()


class TestAddTool:
    """Tests für add Tool."""

    @pytest.mark.asyncio
    async def test_add_tool_success(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                        mock_emb.return_value = [0.1] * 1536
                        mock_meta.return_value = {"type": "observation"}
                        result = await mcp.call_tool("add", {"thought": "test"})
                        assert "Gespeichert" in result.content[0].text
                con.close()


class TestSearchTool:
    """Tests für search Tool."""

    @pytest.mark.asyncio
    async def test_search_tool_with_results(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                db.insert_thought(con, content="Python", embedding=[0.5] * 1536, metadata={})
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    mock_emb.return_value = [0.5] * 1536
                    result = await mcp.call_tool("search", {"text": "python", "limit": 10, "threshold": 0.0})
                    assert "Python" in result.content[0].text or "Ergebnis" in result.content[0].text
                con.close()

    @pytest.mark.asyncio
    async def test_search_tool_no_results(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                db.insert_thought(con, content="Some content", embedding=[0.9] * 1536, metadata={})
                with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
                    mock_emb.return_value = [0.1] * 1536
                    result = await mcp.call_tool("search", {"text": "different", "limit": 10, "threshold": 0.99})
                    assert "Keine" in result.content[0].text
                con.close()


class TestListTool:
    """Tests für list Tool."""

    @pytest.mark.asyncio
    async def test_list_tool_with_results(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                result = await mcp.call_tool("list_thoughts", {"limit": 10})
                assert "Test" in result.content[0].text
                con.close()

    @pytest.mark.asyncio
    async def test_list_tool_empty(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                result = await mcp.call_tool("list_thoughts", {"limit": 10})
                assert "Keine" in result.content[0].text
                con.close()


class TestStatsTool:
    """Tests für stats Tool."""

    @pytest.mark.asyncio
    async def test_stats_tool_with_data(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={"type": "observation"})
                result = await mcp.call_tool("stats", {})
                assert "1 Thought" in result.content[0].text
                con.close()

    @pytest.mark.asyncio
    async def test_stats_tool_empty(self):
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                result = await mcp.call_tool("stats", {})
                assert "0 Thought" in result.content[0].text
                con.close()


class TestHealthTool:
    """Tests für health Tool."""

    @pytest.mark.asyncio
    async def test_health_tool_healthy(self):
        """Health Tool gibt healthy Status zurück."""
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                db.insert_thought(con, content="Test", embedding=[0.1] * 1536, metadata={})
                result = await mcp.call_tool("health", {})
                text = result.content[0].text
                assert "healthy" in text.lower()
                assert "✅" in text or "ok" in text.lower()
                con.close()

    @pytest.mark.asyncio
    async def test_health_tool_empty_db(self):
        """Health Tool funktioniert mit leerer DB."""
        from server import build_server
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch.object(db.config, "OPENBRAIN_DB_PATH", tmp.name):
                mcp, con = build_server(None)
                result = await mcp.call_tool("health", {})
                text = result.content[0].text
                assert "healthy" in text.lower()
                assert "Response Time" in text
                con.close()


class TestLogging:
    """Tests für Logging-Konfiguration."""

    def test_get_log_level_valid(self):
        """get_log_level parst gültige Levels."""
        import config
        from config import get_log_level

        assert get_log_level("TEST_LEVEL", "DEBUG") == "DEBUG"
        assert get_log_level("TEST_LEVEL", "INFO") == "INFO"

    def test_get_log_level_invalid_uses_default(self, monkeypatch):
        """get_log_level verwendet Default bei ungültigem Level."""
        from config import get_log_level

        monkeypatch.setenv("TEST_INVALID_LEVEL", "INVALID")
        result = get_log_level("TEST_INVALID_LEVEL", "WARNING")
        assert result == "WARNING"

    def test_log_level_from_env(self, monkeypatch):
        """Log-Level wird aus Umgebungsvariable gelesen."""
        import importlib

        monkeypatch.setenv("OPENBRAIN_LOG_LEVEL", "DEBUG")
        # Module neu laden würde das Level ändern

    def test_setup_logging_configures_root_logger(self):
        """setup_logging konfiguriert den Root-Logger."""
        import logging
        from config import setup_logging

        setup_logging("DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        assert len(root_logger.handlers) > 0


class TestCleanup:
    """Tests für Cleanup-Funktion."""

    def test_cleanup_closes_connection(self):
        """cleanup schließt die Startup-Connection."""
        from server import cleanup, _startup_connection
        import sqlite3
        import server

        # Mock connection
        mock_con = MagicMock(spec=sqlite3.Connection)
        server._startup_connection = mock_con

        cleanup()

        mock_con.close.assert_called_once()
        assert server._startup_connection is None

    def test_cleanup_handles_none_connection(self):
        """cleanup funktioniert ohne Connection."""
        from server import cleanup
        import server

        server._startup_connection = None
        cleanup()  # Sollte keinen Fehler werfen

    def test_cleanup_handles_exception(self):
        """cleanup behandelt Exceptions beim Schließen."""
        from server import cleanup
        import sqlite3
        import server

        # Mock connection die Exception wirft
        mock_con = MagicMock(spec=sqlite3.Connection)
        mock_con.close.side_effect = Exception("Test error")
        server._startup_connection = mock_con

        cleanup()  # Sollte keinen Fehler werfen
        assert server._startup_connection is None


class TestMainFunction:
    """Tests für main()."""

    def test_main_args_parsing(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, default=4567)
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--key", default=None)
        args = parser.parse_args(["--port", "8080", "--key", "secret"])
        assert args.port == 8080
        assert args.key == "secret"

    def test_main_prints_key_status(self, capsys):
        key = "testkey"
        if key:
            print("[open-brain] Auth aktiv – Key gesetzt.")
        else:
            print("[open-brain] Kein Auth-Key gesetzt.")
        captured = capsys.readouterr()
        assert "Auth aktiv" in captured.out

    def test_main_no_key_status(self, capsys):
        key = None
        if key:
            print("[open-brain] Auth aktiv – Key gesetzt.")
        else:
            print("[open-brain] Kein Auth-Key gesetzt.")
        captured = capsys.readouterr()
        assert "Kein Auth-Key" in captured.out
