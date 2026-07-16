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
        input="my-appkey\nmy-secretkey\nmock\n\n\n",
    )
    assert result.exit_code == 0, result.output
    assert "비밀번호" not in result.output
    assert mem_keyring[f"{config.KEYRING_SERVICE}:default:appkey"] == "my-appkey"
    assert mem_keyring[f"{config.KEYRING_SERVICE}:default:secretkey"] == "my-secretkey"
    # Enter만 치면 기본값 keychain
    assert config.get_token_storage("default") == "keychain"


def test_config_setup_purges_legacy_format(mem_keyring):
    """setup clears _salt/_verify and old ciphertext entries."""
    keyring.set_password(config.KEYRING_SERVICE, "_salt", "oldsalt")
    keyring.set_password(config.KEYRING_SERVICE, "_verify", "oldverify")
    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "gAAAA-cipher")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["config", "setup"],
        input="new-appkey\nnew-secretkey\nmock\n\n\n",
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


# ── token_storage: keychain vs env (config setup에서 선택) ──────────


def test_config_setup_env_storage_choice(mem_keyring):
    """setup에서 env를 고르면 token_storage=env가 프로필에 저장된다."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["config", "setup"],
        input="my-appkey\nmy-secretkey\nmock\n\nenv\n",
    )
    assert result.exit_code == 0, result.output
    assert config.get_token_storage("default") == "env"
    assert "KIWOOM_TOKEN" in result.output


def test_auth_login_env_storage_prints_export_and_skips_keyring(monkeypatch, mem_keyring):
    """env 모드: 토큰을 키체인에 저장하지 않고 export 안내를 출력한다."""
    from kiwoom_cli import auth
    from kiwoom_cli.client import KiwoomClient as RealClient

    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "ak")
    keyring.set_password(config.KEYRING_SERVICE, "default:secretkey", "sk")
    cfg = config.load_config()
    cfg.setdefault("profiles", {}).setdefault("default", {})["token_storage"] = "env"
    config.save_config(cfg)

    def _issue(self):
        auth.save_token("issued-token-value-12345", profile=self.profile)
        return "issued-token-value-12345"

    monkeypatch.setattr(RealClient, "issue_token", _issue)

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "login"])
    assert result.exit_code == 0, result.output
    assert "export KIWOOM_TOKEN='issued-token-value-12345'" in result.output
    assert f"{config.KEYRING_SERVICE}:default:token" not in mem_keyring


def test_auth_login_keychain_storage_saves_to_keyring(monkeypatch, mem_keyring):
    """keychain 모드(기본): 토큰이 키체인에 저장되고 마스킹되어 출력된다."""
    from kiwoom_cli import auth
    from kiwoom_cli.client import KiwoomClient as RealClient

    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "ak")
    keyring.set_password(config.KEYRING_SERVICE, "default:secretkey", "sk")

    def _issue(self):
        auth.save_token("issued-token-value-12345", profile=self.profile)
        return "issued-token-value-12345"

    monkeypatch.setattr(RealClient, "issue_token", _issue)

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "login"])
    assert result.exit_code == 0, result.output
    assert "issued-token-value-12345" not in result.output  # full token never shown
    assert mem_keyring[f"{config.KEYRING_SERVICE}:default:token"] == "issued-token-value-12345"


def test_config_set_token_storage(mem_keyring):
    """config set token_storage env/keychain 으로 전환 가능."""
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "token_storage", "env"])
    assert result.exit_code == 0, result.output
    assert config.get_token_storage("default") == "env"

    result = runner.invoke(cli, ["config", "set", "token_storage", "keychain"])
    assert result.exit_code == 0, result.output
    assert config.get_token_storage("default") == "keychain"


def test_config_set_token_storage_rejects_bad_value(mem_keyring):
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "set", "token_storage", "file"])
    assert result.exit_code == 1


def test_auth_status_shows_env_storage_mode(mem_keyring):
    """env 모드 + 토큰 없음: status가 export 안내를 보여준다."""
    import json as _json

    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "ak")
    cfg = config.load_config()
    cfg.setdefault("profiles", {}).setdefault("default", {})["token_storage"] = "env"
    config.save_config(cfg)

    runner = CliRunner()
    result = runner.invoke(cli, ["-f", "json", "auth", "status"])
    assert result.exit_code == 0
    doc = _json.loads(result.stdout)
    assert doc["data"]["token_storage"] == "env"
    assert doc["data"]["has_token"] is False

    result = runner.invoke(cli, ["auth", "status"])
    assert result.exit_code == 0
    assert "KIWOOM_TOKEN" in result.output


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
    assert doc["data"]["has_token"] is True
    assert doc["data"]["token_source"] == "env"

    result = runner.invoke(cli, ["auth", "status"])
    assert result.exit_code == 0
    assert "KIWOOM_TOKEN" in result.output


# ── 키체인 쓰기 실패 / 토큰 부재 처리 ─────────────────────


def test_config_setup_keychain_write_failure_friendly_error(monkeypatch, mem_keyring):
    """키체인 쓰기 불가(-25308 등): traceback 대신 친절한 안내 + exit 1."""

    def _locked(svc, key, val):
        raise keyring.errors.KeyringError("errSecInteractionNotAllowed (-25308)")

    monkeypatch.setattr(keyring, "set_password", _locked)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["config", "setup"], input="ak\nsk\nmock\n\n\n"
    )
    assert result.exit_code == 1, result.output
    # 예외가 새어나오지 않고 CLI가 스스로 종료해야 한다
    assert result.exception is None or isinstance(result.exception, SystemExit)
    combined = result.output + result.stderr
    assert "키체인" in combined
    assert "KIWOOM_TOKEN" in combined


def test_missing_token_exits_3_before_any_request(monkeypatch, mem_keyring):
    """토큰이 전혀 없으면 요청을 보내지 않고 exit 3 + auth login 힌트."""
    import httpx

    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("token 없이 HTTP 요청이 나가면 안 된다")

    monkeypatch.setattr(httpx.Client, "post", _no_network)
    runner = CliRunner()
    result = runner.invoke(cli, ["stock", "info", "005930"])
    assert result.exit_code == 3, result.output
    assert "auth login" in result.output + result.stderr


def test_missing_token_json_mode_single_json_error_doc(monkeypatch, mem_keyring):
    """-f json + 토큰 부재: stdout은 단일 JSON 에러 문서, exit 3."""
    import json as _json

    import httpx

    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)
    monkeypatch.setattr(
        httpx.Client, "post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request expected")),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 3, result.output
    doc = _json.loads(result.stdout)
    assert "error" in doc


def test_auth_required_message_hints_env_token_when_keychain_unreadable(monkeypatch):
    """키체인 접근 불가 + 토큰 부재: AUTH_REQUIRED 메시지가 KIWOOM_TOKEN을 안내한다."""
    import json as _json

    import httpx

    def _locked(svc, key):
        raise keyring.errors.KeyringError("locked keychain")

    monkeypatch.setattr(keyring, "get_password", _locked)
    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)
    monkeypatch.setattr(
        httpx.Client, "post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request expected")),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 3, result.output
    doc = _json.loads(result.stdout)
    assert doc["error"]["code"] == "AUTH_REQUIRED"
    assert "KIWOOM_TOKEN" in doc["error"]["message"]


def test_auth_required_message_defaults_to_login_when_keychain_readable(monkeypatch):
    """키체인 정상 + 토큰 부재: 기존 'auth login' 안내 유지."""
    import json as _json

    import httpx

    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)
    monkeypatch.setattr(
        httpx.Client, "post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no request expected")),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 3, result.output
    doc = _json.loads(result.stdout)
    assert doc["error"]["code"] == "AUTH_REQUIRED"
    assert "auth login" in doc["error"]["message"]
    assert "KIWOOM_TOKEN" not in doc["error"]["message"]
