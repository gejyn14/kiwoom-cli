"""Tests for keyring-direct credential storage and legacy-format detection."""

from __future__ import annotations

import keyring
import pytest

from kiwoom_cli import config


@pytest.fixture(autouse=True)
def mem_keyring(monkeypatch):
    """In-memory keyring backend, isolated per test."""
    data: dict[str, str] = {}
    monkeypatch.setattr(keyring, "get_password", lambda svc, key: data.get(f"{svc}:{key}"))
    monkeypatch.setattr(keyring, "set_password", lambda svc, key, val: data.__setitem__(f"{svc}:{key}", val))

    def _delete(svc, key):
        if f"{svc}:{key}" not in data:
            raise keyring.errors.PasswordDeleteError(key)
        del data[f"{svc}:{key}"]

    monkeypatch.setattr(keyring, "delete_password", _delete)
    return data


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    return tmp_path


def test_appkey_roundtrip_plain(isolated_config):
    """set_appkey stores the exact input value; get_appkey returns it."""
    config.set_appkey("my-app-key", profile="default")
    assert keyring.get_password(config.KEYRING_SERVICE, "default:appkey") == "my-app-key"
    assert config.get_appkey(profile="default") == "my-app-key"


def test_secretkey_roundtrip_plain(isolated_config):
    config.set_secretkey("my-secret", profile="default")
    assert keyring.get_password(config.KEYRING_SERVICE, "default:secretkey") == "my-secret"
    assert config.get_secretkey(profile="default") == "my-secret"


def test_get_appkey_unset_returns_empty(isolated_config):
    assert config.get_appkey(profile="default") == ""


def test_is_legacy_encrypted_detects_salt(isolated_config):
    assert config.is_legacy_encrypted() is False
    keyring.set_password(config.KEYRING_SERVICE, "_salt", "abc123")
    assert config.is_legacy_encrypted() is True


def test_is_legacy_encrypted_false_when_keyring_unavailable(isolated_config, monkeypatch):
    """Locked/absent keychain (headless, CI) must not crash — treat as not legacy."""

    def _raise(svc, key):
        raise RuntimeError("errSecInteractionNotAllowed")

    monkeypatch.setattr(keyring, "get_password", _raise)
    assert config.is_legacy_encrypted() is False


def test_get_appkey_returns_empty_under_legacy_format(isolated_config):
    """Fernet ciphertext must never be mistaken for a real key."""
    keyring.set_password(config.KEYRING_SERVICE, "_salt", "abc123")
    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "gAAAA-ciphertext")
    assert config.get_appkey(profile="default") == ""
    assert config.get_secretkey(profile="default") == ""


def test_is_configured(isolated_config):
    assert config.is_configured("default") is False
    config.set_appkey("k", profile="default")
    assert config.is_configured("default") is True


def test_is_configured_false_under_legacy_format(isolated_config):
    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "gAAAA-ciphertext")
    keyring.set_password(config.KEYRING_SERVICE, "_salt", "abc123")
    assert config.is_configured("default") is False


def test_clear_legacy_sentinels(isolated_config):
    keyring.set_password(config.KEYRING_SERVICE, "_salt", "s")
    keyring.set_password(config.KEYRING_SERVICE, "_verify", "v")
    config.clear_legacy_sentinels()
    assert keyring.get_password(config.KEYRING_SERVICE, "_salt") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "_verify") is None
    # Idempotent — no raise when already gone
    config.clear_legacy_sentinels()


def test_purge_legacy_credentials_deletes_all_profile_keys(isolated_config):
    (isolated_config / "config.toml").write_text(
        '[general]\ndefault_profile = "default"\n'
        '[profiles.default]\ndomain = "mock"\n'
        '[profiles.second]\ndomain = "prod"\n',
        encoding="utf-8",
    )
    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "cipher1")
    keyring.set_password(config.KEYRING_SERVICE, "default:secretkey", "cipher2")
    keyring.set_password(config.KEYRING_SERVICE, "second:appkey", "cipher3")
    keyring.set_password(config.KEYRING_SERVICE, "default:token", "tok")

    config.purge_legacy_credentials()

    assert keyring.get_password(config.KEYRING_SERVICE, "default:appkey") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "default:secretkey") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "second:appkey") is None
    # Tokens were always plaintext — untouched
    assert keyring.get_password(config.KEYRING_SERVICE, "default:token") == "tok"


# ── Keyring-unavailable resilience ───────────────────
# Locked/absent keychains (headless, CI, sandboxed shells) must degrade to
# "not configured" everywhere, never crash. (is_legacy_encrypted was fixed
# in v2.1; these cover the remaining read paths.)


@pytest.fixture
def broken_keyring(monkeypatch):
    def _raise(svc, key):
        raise keyring.errors.KeyringError("errSecInteractionNotAllowed (-25308)")

    monkeypatch.setattr(keyring, "get_password", _raise)


def test_is_configured_false_when_keyring_unavailable(isolated_config, broken_keyring):
    assert config.is_configured("default") is False


def test_get_appkey_empty_when_keyring_unavailable(isolated_config, broken_keyring):
    assert config.get_appkey(profile="default") == ""
    assert config.get_secretkey(profile="default") == ""


def test_load_token_none_when_keyring_unavailable(isolated_config, broken_keyring):
    from kiwoom_cli import auth

    assert auth.load_token(profile="default") is None
