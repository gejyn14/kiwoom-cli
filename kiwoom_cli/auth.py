"""OAuth token management for Kiwoom REST API.

Tokens are stored in the OS keychain via the `keyring` library.
"""

from __future__ import annotations

import keyring

from . import config

KEYRING_SERVICE = config.KEYRING_SERVICE


def save_token(token: str) -> None:
    keyring.set_password(KEYRING_SERVICE, "token", token)


def load_token() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, "token")


def delete_token() -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, "token")
    except keyring.errors.PasswordDeleteError:
        pass
