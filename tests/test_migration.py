"""Tests for config migration functions.

Covers migrate_from_plaintext() and migrate_to_profiles() in kiwoom_cli/config.py.
These functions touch module globals (CONFIG_DIR, CONFIG_FILE) and the keyring
backend, so we use monkeypatch to isolate file I/O.
"""

from __future__ import annotations

import keyring
import pytest

from kiwoom_cli import config


@pytest.fixture(autouse=True)
def mem_keyring(monkeypatch):
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
    """Redirect config.CONFIG_DIR/CONFIG_FILE to tmp_path."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    return tmp_path


def _write_toml(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ============================================================
#  migrate_from_plaintext
# ============================================================


def test_migrate_from_plaintext_moves_toml_auth_to_keyring(isolated_config):
    """config.toml [auth] section moves into keyring and is removed from TOML."""
    _write_toml(
        isolated_config / "config.toml",
        '[auth]\nappkey = "plain-key"\nsecretkey = "plain-secret"\n',
    )

    result = config.migrate_from_plaintext()

    assert result is True
    assert keyring.get_password(config.KEYRING_SERVICE, "default:appkey") == "plain-key"
    assert keyring.get_password(config.KEYRING_SERVICE, "default:secretkey") == "plain-secret"
    cfg = config.load_config()
    assert "auth" not in cfg


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


# ── migrate_to_profiles: 부분 실패 후 재시도 ─────────────────────────
#
# save_config가 keyring 이전보다 먼저 일어나면, keyring 도중 예외가 났을 때
# config.toml에는 이미 [profiles]가 박힌다. 다음 실행은 `if "profiles" in cfg:
# return False` 가드에 걸려 keyring 이전을 영영 재시도하지 않는다 —
# bare appkey/secretkey/token이 고아로 남는다.


def _fail_first_default_write(monkeypatch):
    """default: 접두 키에 대한 첫 set_password만 실패시킨다 (키체인 잠김 모사)."""
    original = keyring.set_password
    state = {"failed": False}

    def _flaky(svc, key, val):
        if key.startswith("default:") and not state["failed"]:
            state["failed"] = True
            raise RuntimeError("keychain locked")
        return original(svc, key, val)

    monkeypatch.setattr(keyring, "set_password", _flaky)
    return original


def test_migrate_to_profiles_retries_keyring_after_partial_failure(
    isolated_config, monkeypatch,
):
    """keyring 이전이 실패한 뒤 재실행하면 이전이 완료되어야 한다."""
    _write_toml(
        isolated_config / "config.toml",
        '[general]\ndomain = "prod"\naccount = "1234567"\n',
    )
    keyring.set_password(config.KEYRING_SERVICE, "appkey", "A")
    keyring.set_password(config.KEYRING_SERVICE, "secretkey", "S")
    keyring.set_password(config.KEYRING_SERVICE, "token", "T")

    original = _fail_first_default_write(monkeypatch)
    with pytest.raises(RuntimeError):
        config.migrate_to_profiles()

    # 키체인 복구 후 재실행
    monkeypatch.setattr(keyring, "set_password", original)
    config.migrate_to_profiles()

    # 판별 기준: 재실행이 실제로 keyring을 옮겼는가.
    # 수정 전에는 1회차가 config에 [profiles]를 써버려 가드에 걸렸다.
    assert keyring.get_password(config.KEYRING_SERVICE, "default:appkey") == "A"
    assert keyring.get_password(config.KEYRING_SERVICE, "default:secretkey") == "S"
    assert keyring.get_password(config.KEYRING_SERVICE, "default:token") == "T"
    assert keyring.get_password(config.KEYRING_SERVICE, "appkey") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "secretkey") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "token") is None
    # config 이전도 최종적으로 완료되어야 한다
    cfg = config.load_config()
    assert cfg["profiles"]["default"]["domain"] == "prod"


def test_migrate_to_profiles_does_not_mark_config_before_keyring_moves(
    isolated_config, monkeypatch,
):
    """keyring이 실패한 시점에 config.toml은 아직 '이전됨'으로 표시되면 안 된다.

    [profiles]가 곧 마이그레이션 완료 표식이므로, 자격증명이 실제로 옮겨가기
    전에 표식이 찍히면 되돌릴 방법이 없다."""
    _write_toml(
        isolated_config / "config.toml",
        '[general]\ndomain = "prod"\naccount = "1234567"\n',
    )
    keyring.set_password(config.KEYRING_SERVICE, "appkey", "A")

    _fail_first_default_write(monkeypatch)
    with pytest.raises(RuntimeError):
        config.migrate_to_profiles()

    cfg = config.load_config()
    assert "profiles" not in cfg, "자격증명 이전 전에 마이그레이션 표식이 찍혔다"
    # 원본 정보도 그대로 남아 재시도가 가능해야 한다
    assert cfg["general"]["domain"] == "prod"
    assert cfg["general"]["account"] == "1234567"


def test_migrate_to_profiles_idempotent_after_crash_between_set_and_delete(
    isolated_config,
):
    """set_password 성공 후 delete_password 전에 죽은 경우.

    bare 키와 default: 키가 동시에 존재한다. 재실행이 깨지지 않고 정리해야
    한다 (이 루프의 멱등성이 위 재시도 설계의 전제다)."""
    _write_toml(isolated_config / "config.toml", '[general]\ndomain = "mock"\n')
    keyring.set_password(config.KEYRING_SERVICE, "appkey", "A")
    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "A")

    config.migrate_to_profiles()

    assert keyring.get_password(config.KEYRING_SERVICE, "default:appkey") == "A"
    assert keyring.get_password(config.KEYRING_SERVICE, "appkey") is None
