"""Tests for kiwoom_cli.auth — keyring-backed token storage."""

import keyring

from kiwoom_cli import auth


def test_save_token_stores_in_keyring():
    auth.save_token("abc123", profile="test-profile")
    assert keyring.get_password(auth.KEYRING_SERVICE, "test-profile:token") == "abc123"


def test_load_token_returns_stored_value():
    auth.save_token("xyz789", profile="test-profile")
    assert auth.load_token(profile="test-profile") == "xyz789"


def test_load_token_returns_none_when_missing():
    assert auth.load_token(profile="nonexistent") is None


def test_delete_token_removes_stored_value():
    auth.save_token("to-delete", profile="test-profile")
    assert auth.load_token(profile="test-profile") == "to-delete"
    auth.delete_token(profile="test-profile")
    assert auth.load_token(profile="test-profile") is None


def test_delete_token_missing_key_is_noop():
    auth.delete_token(profile="never-existed")  # must not raise


# ── KIWOOM_TOKEN 환경변수 ────────────────────────────
# 키체인에 접근할 수 없는 샌드박스/CI/AI 에이전트 환경용 통로.
# appkey/secretkey는 여전히 환경변수 미지원.


def test_load_token_env_var_takes_precedence(monkeypatch):
    auth.save_token("keyring-token", profile="test-profile")
    monkeypatch.setenv("KIWOOM_TOKEN", "env-token")
    assert auth.load_token(profile="test-profile") == "env-token"


def test_load_token_env_var_works_without_keyring(monkeypatch):
    """잠긴 키체인에서도 KIWOOM_TOKEN이면 토큰 확보."""

    def _raise(svc, key):
        raise keyring.errors.KeyringError("errSecInteractionNotAllowed (-25308)")

    monkeypatch.setattr(keyring, "get_password", _raise)
    monkeypatch.setenv("KIWOOM_TOKEN", "env-token")
    assert auth.load_token(profile="default") == "env-token"


def test_load_token_falls_back_to_keyring_when_env_unset(monkeypatch):
    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)
    auth.save_token("keyring-token", profile="test-profile")
    assert auth.load_token(profile="test-profile") == "keyring-token"


def test_load_token_empty_env_var_is_ignored(monkeypatch):
    monkeypatch.setenv("KIWOOM_TOKEN", "")
    auth.save_token("keyring-token", profile="test-profile")
    assert auth.load_token(profile="test-profile") == "keyring-token"
