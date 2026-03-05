"""
Tests für config.py
"""

import os
import pytest

from config import validate_openrouter_key, require, get_float


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
