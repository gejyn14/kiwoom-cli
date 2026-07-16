"""OAuth token management for Kiwoom REST API.

Tokens are stored in the OS keychain (plain, not encrypted).
Tokens are short-lived and can be re-issued, so the security risk
of plain keychain storage is low compared to appkey/secretkey.

KIWOOM_TOKEN 환경변수가 설정되어 있으면 키체인보다 우선합니다. 키체인에
접근할 수 없는 샌드박스/CI/AI 에이전트 환경을 위한 통로로, 만료되는
토큰만 허용됩니다 — appkey/secretkey는 여전히 환경변수를 지원하지 않습니다.

프로필의 token_storage가 "env"이면 save_token은 키체인에 쓰지 않습니다.
auth login이 토큰을 출력하고, 사용자가 KIWOOM_TOKEN으로 직접 관리합니다.
"""

from __future__ import annotations

import os

import keyring

from . import config

KEYRING_SERVICE = config.KEYRING_SERVICE


def save_token(token: str, profile: str | None = None) -> None:
    p = config.resolve_profile(profile)
    if config.get_token_storage(p) == "env":
        return
    keyring.set_password(KEYRING_SERVICE, f"{p}:token", token)


def load_token(profile: str | None = None) -> str | None:
    env = os.environ.get("KIWOOM_TOKEN")
    if env:
        return env
    p = config.resolve_profile(profile)
    return config._keyring_get(f"{p}:token")


def delete_token(profile: str | None = None) -> None:
    p = config.resolve_profile(profile)
    try:
        keyring.delete_password(KEYRING_SERVICE, f"{p}:token")
    except keyring.errors.PasswordDeleteError:
        pass
