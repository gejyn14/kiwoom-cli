"""Tests for config migration functions.

Covers migrate_from_plaintext() and migrate_to_profiles() in kiwoom_cli/config.py.
These functions touch module globals (CONFIG_DIR, CONFIG_FILE, store) and the
keyring backend, so we use monkeypatch to isolate file I/O.
"""

from __future__ import annotations

import keyring
import pytest

from kiwoom_cli import config


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect config.CONFIG_DIR/CONFIG_FILE to tmp_path and init store."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    # Reset store state and initialize with a fresh salt
    config.store._key = None
    config.store.setup("testpw")
    return tmp_path


def _write_toml(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ============================================================
#  migrate_from_plaintext
# ============================================================


def test_migrate_from_plaintext_moves_toml_auth_to_store(isolated_config):
    """config.toml [auth] section is encrypted into store and removed from TOML."""
    _write_toml(
        isolated_config / "config.toml",
        '[auth]\nappkey = "plain-key"\nsecretkey = "plain-secret"\n',
    )

    result = config.migrate_from_plaintext()

    assert result is True
    assert config.store.get("default:appkey") == "plain-key"
    assert config.store.get("default:secretkey") == "plain-secret"
    cfg = config.load_config()
    assert "auth" not in cfg


def test_migrate_from_plaintext_moves_plain_keyring_keys(isolated_config):
    """Plain (unencrypted) keyring entries are re-stored encrypted."""
    keyring.set_password(config.KEYRING_SERVICE, "appkey", "plain-xyz")

    result = config.migrate_from_plaintext()

    assert result is True
    assert config.store.get("default:appkey") == "plain-xyz"


def test_migrate_from_plaintext_moves_token_file(isolated_config):
    """~/.kiwoom/token file is moved into keyring and deleted."""
    token_file = isolated_config / "token"
    token_file.write_text("my-token-value\n")

    result = config.migrate_from_plaintext()

    assert result is True
    assert keyring.get_password(config.KEYRING_SERVICE, "default:token") == "my-token-value"
    assert not token_file.exists()


def test_migrate_from_plaintext_idempotent_returns_false(isolated_config):
    """Running migration twice with nothing to migrate returns False."""
    result = config.migrate_from_plaintext()

    assert result is False


def test_migrate_from_plaintext_skips_empty_config(isolated_config):
    """Empty config.toml without [auth] section is skipped."""
    _write_toml(isolated_config / "config.toml", "[general]\ndefault_profile = \"default\"\n")

    result = config.migrate_from_plaintext()

    assert result is False


# ============================================================
#  migrate_to_profiles
# ============================================================


def test_migrate_to_profiles_restructures_general_section(isolated_config):
    """[general] domain/account → [profiles.default]."""
    _write_toml(
        isolated_config / "config.toml",
        '[general]\ndomain = "prod"\naccount = "1234567"\n',
    )

    result = config.migrate_to_profiles()

    assert result is True
    cfg = config.load_config()
    assert cfg["profiles"]["default"]["domain"] == "prod"
    assert cfg["profiles"]["default"]["account"] == "1234567"
    assert cfg["general"]["default_profile"] == "default"
    assert "domain" not in cfg["general"]
    assert "account" not in cfg["general"]


def test_migrate_to_profiles_skips_if_profiles_exist(isolated_config):
    """If [profiles] section already exists, migration is skipped."""
    _write_toml(
        isolated_config / "config.toml",
        '[general]\ndefault_profile = "x"\n[profiles.x]\ndomain = "mock"\n',
    )

    result = config.migrate_to_profiles()

    assert result is False


def test_migrate_to_profiles_renames_bare_keyring_keys(isolated_config):
    """Bare keyring keys (appkey/secretkey/token) renamed to default:-prefixed."""
    # Write pre-profile config.toml (without [profiles] section) so migration runs
    _write_toml(
        isolated_config / "config.toml",
        '[general]\ndomain = "mock"\n',
    )
    keyring.set_password(config.KEYRING_SERVICE, "appkey", "A")
    keyring.set_password(config.KEYRING_SERVICE, "secretkey", "S")
    keyring.set_password(config.KEYRING_SERVICE, "token", "T")

    result = config.migrate_to_profiles()

    assert result is True
    assert keyring.get_password(config.KEYRING_SERVICE, "default:appkey") == "A"
    assert keyring.get_password(config.KEYRING_SERVICE, "default:secretkey") == "S"
    assert keyring.get_password(config.KEYRING_SERVICE, "default:token") == "T"
    assert keyring.get_password(config.KEYRING_SERVICE, "appkey") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "secretkey") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "token") is None
