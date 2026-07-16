"""CLI-level tests: no password prompts anywhere after keychain-only change."""

from __future__ import annotations

import keyring
import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.main import cli


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


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    return tmp_path


def test_config_setup_no_password_prompt(mem_keyring):
    """setup succeeds with only appkey/secretkey/domain/account inputs."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["config", "setup"],
        input="my-appkey\nmy-secretkey\nmock\n\n",
    )
    assert result.exit_code == 0, result.output
    assert "비밀번호" not in result.output
    assert mem_keyring[f"{config.KEYRING_SERVICE}:default:appkey"] == "my-appkey"
    assert mem_keyring[f"{config.KEYRING_SERVICE}:default:secretkey"] == "my-secretkey"


def test_config_setup_purges_legacy_format(mem_keyring):
    """setup clears _salt/_verify and old ciphertext entries."""
    keyring.set_password(config.KEYRING_SERVICE, "_salt", "oldsalt")
    keyring.set_password(config.KEYRING_SERVICE, "_verify", "oldverify")
    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "gAAAA-cipher")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["config", "setup"],
        input="new-appkey\nnew-secretkey\nmock\n\n",
    )
    assert result.exit_code == 0, result.output
    assert keyring.get_password(config.KEYRING_SERVICE, "_salt") is None
    assert keyring.get_password(config.KEYRING_SERVICE, "_verify") is None
    assert config.get_appkey(profile="default") == "new-appkey"


def test_auth_login_no_password_prompt(monkeypatch, mem_keyring):
    """auth login issues a token without any interactive prompt."""
    from kiwoom_cli import client as client_mod

    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "ak")
    keyring.set_password(config.KEYRING_SERVICE, "default:secretkey", "sk")

    monkeypatch.setattr(
        client_mod.KiwoomClient, "issue_token", lambda self: "issued-token-value-12345"
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "login"], input="")
    assert result.exit_code == 0, result.output
    assert "비밀번호" not in result.output
    assert "토큰 발급 완료" in result.output


def test_auth_login_unconfigured_tells_user_to_setup(mem_keyring):
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "login"])
    assert result.exit_code != 0
    assert "config setup" in result.output


def test_legacy_format_shows_resetup_notice(mem_keyring):
    """Any command under legacy format prints the re-setup notice."""
    keyring.set_password(config.KEYRING_SERVICE, "_salt", "oldsalt")
    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "status"])
    assert "kiwoom config setup" in result.output or "config setup" in result.output


def test_readonly_commands_survive_broken_keyring(monkeypatch):
    """Locked/absent keychain (headless, CI): config show / auth status must
    exit 0 as "미설정" instead of crashing with a KeyringError traceback."""

    def _raise(svc, key):
        raise keyring.errors.KeyringError("errSecInteractionNotAllowed (-25308)")

    monkeypatch.setattr(keyring, "get_password", _raise)
    runner = CliRunner()

    for argv in (["config", "show"], ["auth", "status"], ["config", "profiles"]):
        result = runner.invoke(cli, argv)
        assert result.exit_code == 0, (argv, result.exception)


def test_auth_status_reflects_env_token_with_broken_keyring(monkeypatch):
    """샌드박스(잠긴 키체인) + KIWOOM_TOKEN: auth status가 토큰을 인식해야 한다."""
    import json as _json

    def _raise(svc, key):
        raise keyring.errors.KeyringError("errSecInteractionNotAllowed (-25308)")

    monkeypatch.setattr(keyring, "get_password", _raise)
    monkeypatch.setenv("KIWOOM_TOKEN", "env-token")
    runner = CliRunner()

    result = runner.invoke(cli, ["-f", "json", "auth", "status"])
    assert result.exit_code == 0
    doc = _json.loads(result.stdout)
    assert doc["has_token"] is True
    assert doc["token_source"] == "env"

    result = runner.invoke(cli, ["auth", "status"])
    assert result.exit_code == 0
    assert "KIWOOM_TOKEN" in result.output
