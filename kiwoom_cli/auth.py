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


def keychain_readable() -> bool:
    """키체인 읽기 가능 여부. 잠김/부재(샌드박스, CI, 에이전트) 환경이면 False.

    load_token은 키체인 오류를 '토큰 없음'으로 강등하므로, 안내 메시지를
    고를 때 이 함수로 원인을 구분한다 (auth login 안내 vs KIWOOM_TOKEN 안내).
    """
    try:
        keyring.get_password(KEYRING_SERVICE, "__probe__")
        return True
    except Exception:
        return False


def load_token(profile: str | None = None) -> str | None:
    env = os.environ.get("KIWOOM_TOKEN")
    if env:
        return env
    p = config.resolve_profile(profile)
    return config._keyring_get(f"{p}:token")


def load_keychain_token(profile: str | None = None) -> str | None:
    """KIWOOM_TOKEN을 무시하고 키체인에 저장된 토큰만 읽는다.

    load_token은 env를 우선하므로 "지금 쓰는 토큰"과 "키체인에 있는 토큰"을
    구분할 수 없다. 폐기(revoke)처럼 어느 쪽을 지울지 결정해야 하는 곳에서
    쓴다 — 폐기한 적 없는 토큰을 지워 폐기 불가능하게 만드는 것을 막는다.
    """
    p = config.resolve_profile(profile)
    return config._keyring_get(f"{p}:token")


def delete_token(profile: str | None = None) -> None:
    p = config.resolve_profile(profile)
    try:
        keyring.delete_password(KEYRING_SERVICE, f"{p}:token")
    except keyring.errors.PasswordDeleteError:
        pass
