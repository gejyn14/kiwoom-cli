"""OAuth token management for Kiwoom REST API.

Tokens are stored in ~/.kiwoom/token and loaded automatically by the client.
"""

from __future__ import annotations

import sys

from . import config

TOKEN_FILE = config.CONFIG_DIR / "token"


def save_token(token: str) -> None:
    config.ensure_config_dir()
    TOKEN_FILE.write_text(token)
    if sys.platform != "win32":
        TOKEN_FILE.chmod(0o600)


def load_token() -> str | None:
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text().strip()
        return t if t else None
    return None


def delete_token() -> None:
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
