"""
Konfiguration für open-brain.
Liest alle benötigten Umgebungsvariablen.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Literal

# =============================================================================
# Logging-Konfiguration (muss vor anderen Imports erfolgen)
# =============================================================================

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def get_log_level(name: str, default: LogLevel = "INFO") -> LogLevel:
    """Liest das Log-Level aus einer Umgebungsvariable.

    Args:
        name: Name der Umgebungsvariable
        default: Default-Level wenn nicht gesetzt oder ungültig

    Returns:
        Validiertes Log-Level
    """
    value = os.environ.get(name, default).upper()
    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if value in valid_levels:
        return value  # type: ignore[return-value]
    return default


def setup_logging(level: LogLevel = "INFO") -> None:
    """Konfiguriert das Logging für alle Module.

    Args:
        level: Log-Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Format mit Timestamp, Level, Module und Message
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Root Logger konfigurieren
    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stderr),
        ],
        force=True,  # Überschreibt existierende Handler
    )


# Log-Level lesen und Logging initialisieren
OPENBRAIN_LOG_LEVEL: LogLevel = get_log_level("OPENBRAIN_LOG_LEVEL", default="INFO")
setup_logging(OPENBRAIN_LOG_LEVEL)

logger = logging.getLogger(__name__)


# =============================================================================
# Umgebungsvariablen
# =============================================================================


def require(name: str) -> str:
    """Liest eine Pflicht-Umgebungsvariable.

    Args:
        name: Name der Umgebungsvariable

    Returns:
        Wert der Umgebungsvariable

    Raises:
        RuntimeError: Wenn die Variable nicht gesetzt oder leer ist
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Umgebungsvariable '{name}' ist nicht gesetzt. "
            "Bitte in .env oder Shell-Umgebung definieren."
        )
    return value


def get_float(name: str, default: float) -> float:
    """Liest eine Float-Umgebungsvariable mit Default-Wert.

    Args:
        name: Name der Umgebungsvariable
        default: Default-Wert wenn nicht gesetzt oder ungültig

    Returns:
        Float-Wert der Umgebungsvariable oder Default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning(f"Ungültiger Wert für {name}: '{value}', verwende Default: {default}")
        return default


def validate_openrouter_key(key: str | None) -> bool:
    """Validiert das Format eines OpenRouter API-Keys.

    Args:
        key: Der zu prüfende API-Key

    Returns:
        True wenn der Key gültig aussieht, sonst False

    Note:
        Erwartet Format: sk-or-v1-xxxxx... (mindestens 20 Zeichen)
    """
    if not key:
        return False
    # OpenRouter Keys beginnen mit 'sk-or-' und haben mindestens 20 Zeichen
    pattern = r"^sk-or-[a-zA-Z0-9_-]{14,}$"
    if re.match(pattern, key):
        return True
    # Fallback: Mindestlänge und Präfix-Check
    return key.startswith("sk-or-") and len(key) >= 20


# =============================================================================
# Konfigurationswerte
# =============================================================================

# Pflichtfelder
_api_key: str = require("OPENROUTER_API_KEY")
if not validate_openrouter_key(_api_key):
    logger.warning(
        "OPENROUTER_API_KEY hat ein ungewöhnliches Format. "
        "Erwartet: 'sk-or-...' mit mindestens 20 Zeichen."
    )

OPENROUTER_API_KEY: str = _api_key
OPENBRAIN_DB_PATH: str = os.environ.get(
    "OPENBRAIN_DB_PATH",
    os.path.join(os.path.dirname(__file__), "brain.db"),
)
OPENROUTER_RATE_LIMIT: float = get_float("OPENROUTER_RATE_LIMIT", default=2.0)

# API-Konfiguration
OPENROUTER_BASE: str = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL: str = "openai/text-embedding-3-small"
METADATA_MODEL: str = "openai/gpt-4o-mini"
EMBEDDING_DIM: int = 1536
