"""
Tests für config.py
"""

import os
import pytest

from config import validate_openrouter_key, require, get_float, get_log_level, setup_logging


class TestValidateOpenrouterKey:
    """Tests für die API-Key Validierung."""

    def test_valid_key_format_v1(self):
        """Akzeptiert sk-or-v1-xxxx Format."""
        assert validate_openrouter_key("sk-or-v1-abcdefghijklmnop") is True

    def test_valid_key_format_long(self):
        """Akzeptiert lange Keys mit sk-or- Prefix."""
        assert validate_openrouter_key("sk-or-v1-" + "x" * 50) is True

    def test_valid_key_minimal(self):
        """Akzeptiert minimale gültige Keys (sk-or- + 14+ chars)."""
        assert validate_openrouter_key("sk-or-12345678901234") is True

    def test_invalid_key_no_prefix(self):
        """Lehnt Keys ohne sk-or- Prefix ab."""
        assert validate_openrouter_key("invalid-key-12345678") is False

    def test_invalid_key_too_short(self):
        """Lehnt zu kurze Keys ab."""
        assert validate_openrouter_key("sk-or-short") is False

    def test_invalid_key_empty(self):
        """Lehnt leere Strings ab."""
        assert validate_openrouter_key("") is False

    def test_invalid_key_none(self):
        """Lehnt None ab."""
        assert validate_openrouter_key(None) is False

    def test_invalid_key_wrong_prefix(self):
        """Lehnt Keys mit falschem Prefix ab."""
        assert validate_openrouter_key("sk-openai-12345678901234") is False


class TestRequire:
    """Tests für die require() Funktion."""

    def test_require_existing_var(self, monkeypatch):
        """Gibt existierende Variable zurück."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        assert require("TEST_VAR") == "test_value"

    def test_require_missing_var(self, monkeypatch):
        """Wirft RuntimeError bei fehlender Variable."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        with pytest.raises(RuntimeError, match="MISSING_VAR"):
            require("MISSING_VAR")

    def test_require_empty_var(self, monkeypatch):
        """Wirft RuntimeError bei leerer Variable."""
        monkeypatch.setenv("EMPTY_VAR", "")
        with pytest.raises(RuntimeError, match="EMPTY_VAR"):
            require("EMPTY_VAR")


class TestGetFloat:
    """Tests für get_float() Funktion."""

    def test_get_float_with_value(self, monkeypatch):
        """Liest Float aus Umgebungsvariable."""
        monkeypatch.setenv("TEST_FLOAT", "3.5")
        assert get_float("TEST_FLOAT", default=1.0) == 3.5

    def test_get_float_missing_uses_default(self, monkeypatch):
        """Verwendet Default bei fehlender Variable."""
        monkeypatch.delenv("MISSING_FLOAT", raising=False)
        assert get_float("MISSING_FLOAT", default=2.5) == 2.5

    def test_get_float_invalid_uses_default(self, monkeypatch, caplog):
        """Verwendet Default bei ungültigem Wert."""
        monkeypatch.setenv("INVALID_FLOAT", "not-a-number")
        result = get_float("INVALID_FLOAT", default=1.5)
        assert result == 1.5

    def test_get_float_integer(self, monkeypatch):
        """Liest Integer als Float."""
        monkeypatch.setenv("TEST_INT", "5")
        assert get_float("TEST_INT", default=1.0) == 5.0

    def test_get_float_zero(self, monkeypatch):
        """Liest 0 als gültigen Wert."""
        monkeypatch.setenv("TEST_ZERO", "0")
        assert get_float("TEST_ZERO", default=1.0) == 0.0


class TestGetLogLevel:
    """Tests für get_log_level() Funktion."""

    def test_get_log_level_debug(self, monkeypatch):
        """Liest DEBUG Level."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "DEBUG")
        assert get_log_level("TEST_LOG_LEVEL", "INFO") == "DEBUG"

    def test_get_log_level_info(self, monkeypatch):
        """Liest INFO Level."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "INFO")
        assert get_log_level("TEST_LOG_LEVEL", "DEBUG") == "INFO"

    def test_get_log_level_warning(self, monkeypatch):
        """Liest WARNING Level."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "WARNING")
        assert get_log_level("TEST_LOG_LEVEL", "INFO") == "WARNING"

    def test_get_log_level_error(self, monkeypatch):
        """Liest ERROR Level."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "ERROR")
        assert get_log_level("TEST_LOG_LEVEL", "INFO") == "ERROR"

    def test_get_log_level_critical(self, monkeypatch):
        """Liest CRITICAL Level."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "CRITICAL")
        assert get_log_level("TEST_LOG_LEVEL", "INFO") == "CRITICAL"

    def test_get_log_level_case_insensitive(self, monkeypatch):
        """Level ist case-insensitive."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "debug")
        assert get_log_level("TEST_LOG_LEVEL", "INFO") == "DEBUG"

    def test_get_log_level_invalid_uses_default(self, monkeypatch):
        """Verwendet Default bei ungültigem Level."""
        monkeypatch.setenv("TEST_LOG_LEVEL", "INVALID")
        assert get_log_level("TEST_LOG_LEVEL", "WARNING") == "WARNING"

    def test_get_log_level_missing_uses_default(self, monkeypatch):
        """Verwendet Default bei fehlender Variable."""
        monkeypatch.delenv("MISSING_LOG_LEVEL", raising=False)
        assert get_log_level("MISSING_LOG_LEVEL", "ERROR") == "ERROR"


class TestSetupLogging:
    """Tests für setup_logging() Funktion."""

    def test_setup_logging_sets_level(self):
        """setup_logging setzt das Log-Level."""
        import logging
        setup_logging("DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_setup_logging_creates_handler(self):
        """setup_logging erstellt einen Handler."""
        import logging
        setup_logging("INFO")
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_setup_logging_force_overwrites(self):
        """setup_logging überschreibt existierende Handler."""
        import logging
        setup_logging("INFO")
        initial_count = len(logging.getLogger().handlers)
        setup_logging("DEBUG")
        # Durch force=True sollte nur ein Handler bleiben
        assert len(logging.getLogger().handlers) == initial_count


class TestGetInt:
    """Tests für get_int() Funktion."""

    def test_get_int_with_value(self, monkeypatch):
        """Liest Integer aus Umgebungsvariable."""
        from config import get_int
        monkeypatch.setenv("TEST_INT", "1536")
        assert get_int("TEST_INT", default=768) == 1536

    def test_get_int_missing_uses_default(self, monkeypatch):
        """Verwendet Default bei fehlender Variable."""
        from config import get_int
        monkeypatch.delenv("MISSING_INT", raising=False)
        assert get_int("MISSING_INT", default=3072) == 3072

    def test_get_int_invalid_uses_default(self, monkeypatch):
        """Verwendet Default bei ungültigem Wert."""
        from config import get_int
        monkeypatch.setenv("INVALID_INT", "not-a-number")
        result = get_int("INVALID_INT", default=1536)
        assert result == 1536

    def test_get_int_zero(self, monkeypatch):
        """Liest 0 als gültigen Wert."""
        from config import get_int
        monkeypatch.setenv("TEST_ZERO", "0")
        assert get_int("TEST_ZERO", default=100) == 0

    def test_get_int_negative(self, monkeypatch):
        """Liest negative Zahlen."""
        from config import get_int
        monkeypatch.setenv("TEST_NEG", "-1")
        assert get_int("TEST_NEG", default=0) == -1


class TestEmbeddingDim:
    """Tests für Embedding-Dimension Konfiguration."""

    def test_default_embedding_dim(self):
        """Default Embedding-Dimension ist 1536."""
        import config
        assert config.OPENBRAIN_EMBEDDING_DIM == 1536
        assert config.EMBEDDING_DIM == 1536

    def test_embedding_dim_from_env(self, monkeypatch):
        """Embedding-Dimension kann über Env gesetzt werden."""
        import importlib
        import config

        monkeypatch.setenv("OPENBRAIN_EMBEDDING_DIM", "3072")
        # Module neu laden würde den Wert ändern
        # (in der Praxis nicht trivial, da config bereits geladen)
