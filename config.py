"""
Konfiguration für open-brain.
Liest alle benötigten Umgebungsvariablen.
"""

import os


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Umgebungsvariable '{name}' ist nicht gesetzt. "
            "Bitte in .env oder Shell-Umgebung definieren."
        )
    return value


# Pflichtfelder
OPENROUTER_API_KEY: str = require("OPENROUTER_API_KEY")

# Optionale Felder
OPENBRAIN_DB_PATH: str = os.environ.get(
    "OPENBRAIN_DB_PATH",
    os.path.join(os.path.dirname(__file__), "brain.db"),
)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL = "openai/text-embedding-3-small"
METADATA_MODEL = "openai/gpt-4o-mini"
EMBEDDING_DIM = 1536
