"""OAuth token management for Kiwoom REST API.

Tokens are stored in the OS keychain (plain, not encrypted).
Tokens are short-lived and can be re-issued, so the security risk
of plain keychain storage is low compared to appkey/secretkey.
"""

from __future__ import annotations

import keyring

from . import config

KEYRING_SERVICE = config.KEYRING_SERVICE


def save_token(token: str, profile: str | None = None) -> None:
    p = config.resolve_profile(profile)
    keyring.set_password(KEYRING_SERVICE, f"{p}:token", token)


def load_token(profile: str | None = None) -> str | None:
    p = config.resolve_profile(profile)
    return keyring.get_password(KEYRING_SERVICE, f"{p}:token")


def delete_token(profile: str | None = None) -> None:
    p = config.resolve_profile(profile)
    try:
        keyring.delete_password(KEYRING_SERVICE, f"{p}:token")
    except keyring.errors.PasswordDeleteError:
        pass
