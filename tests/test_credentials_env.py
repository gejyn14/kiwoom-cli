"""KIWOOM_APPKEY / KIWOOM_SECRETKEY 환경변수 자격증명 (v2.15.0).

키체인이 없는 컨테이너에서 토큰을 스스로 발급할 수 있어야 한다. 종전에는
appkey/secretkey가 키체인 전용이라 호스트에서 발급한 KIWOOM_TOKEN을 주입하는
것이 유일한 경로였고, 그 토큰이 만료되면 컨테이너는 복구할 수 없었다.

값 고정은 리터럴로 한다 (상수에서 기대값을 가져오면 상수를 바꿔도 통과한다).
"""

from __future__ import annotations

import click
import keyring
import keyring.errors
import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.main import cli

KEYCHAIN_APPKEY = "keychain-appkey-0001"
KEYCHAIN_SECRETKEY = "keychain-secretkey-0001"
ENV_APPKEY = "env-appkey-9999"
ENV_SECRETKEY = "env-secretkey-9999"

CRED_ENV_VARS = (
    "KIWOOM_APPKEY",
    "KIWOOM_APPKEY_FILE",
    "KIWOOM_SECRETKEY",
    "KIWOOM_SECRETKEY_FILE",
)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """실제 ~/.kiwoom과 개발자 셸의 KIWOOM_* 환경변수로부터 격리한다.

    CONFIG_FILE을 격리하지 않으면 resolve_profile()이 사용자의 실제 config.toml을
    읽어 프로필·도메인이 머신마다 달라진다 (test_client.py와 같은 이유).
    """
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    for name in (*CRED_ENV_VARS, "KIWOOM_DOMAIN", "KIWOOM_PROFILE", "KIWOOM_TOKEN", "KIWOOM_ACCOUNT"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def keychain_creds():
    """키체인에 자격증명을 넣는다 (InMemoryKeyring — conftest가 매 테스트 초기화)."""
    config.set_appkey(KEYCHAIN_APPKEY, profile="default")
    config.set_secretkey(KEYCHAIN_SECRETKEY, profile="default")


# ── 우선순위: env > 키체인 ────────────────────────────


def test_env_appkey_beats_keychain(monkeypatch, keychain_creds):
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    assert config.get_appkey(profile="default") == "env-appkey-9999"


def test_env_secretkey_beats_keychain(monkeypatch, keychain_creds):
    monkeypatch.setenv("KIWOOM_SECRETKEY", ENV_SECRETKEY)
    assert config.get_secretkey(profile="default") == "env-secretkey-9999"


def test_keychain_used_when_env_absent(keychain_creds):
    assert config.get_appkey(profile="default") == "keychain-appkey-0001"
    assert config.get_secretkey(profile="default") == "keychain-secretkey-0001"


def test_env_appkey_and_keychain_secretkey_mix(monkeypatch, keychain_creds):
    """한쪽만 env로 덮어도 나머지는 키체인에서 온다 (독립적으로 해석된다)."""
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    assert config.get_appkey(profile="default") == "env-appkey-9999"
    assert config.get_secretkey(profile="default") == "keychain-secretkey-0001"


def test_env_credentials_ignore_profile(monkeypatch):
    """env 자격증명은 프로필과 무관하다 — KIWOOM_TOKEN·KIWOOM_DOMAIN과 같은 방향."""
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    assert config.get_appkey(profile="default") == "env-appkey-9999"
    assert config.get_appkey(profile="other") == "env-appkey-9999"


# ── _FILE 변형 (도커/포드먼 시크릿) ──────────────────


def test_appkey_file_is_read(monkeypatch, tmp_path):
    secret = tmp_path / "appkey"
    secret.write_text(ENV_APPKEY, encoding="utf-8")
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(secret))
    assert config.get_appkey(profile="default") == "env-appkey-9999"


def test_appkey_file_trailing_newline_stripped(monkeypatch, tmp_path):
    """시크릿 파일은 거의 항상 개행으로 끝난다 — 그대로 쓰면 인증이 실패한다."""
    secret = tmp_path / "appkey"
    secret.write_text(f"{ENV_APPKEY}\n", encoding="utf-8")
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(secret))
    assert config.get_appkey(profile="default") == "env-appkey-9999"


def test_direct_env_value_is_stripped(monkeypatch):
    monkeypatch.setenv("KIWOOM_SECRETKEY", f"  {ENV_SECRETKEY}\n")
    assert config.get_secretkey(profile="default") == "env-secretkey-9999"


def test_empty_file_falls_back_to_keychain(monkeypatch, tmp_path, keychain_creds):
    """빈 값은 '미설정'으로 취급한다 (빈 문자열 환경변수와 동일)."""
    secret = tmp_path / "appkey"
    secret.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(secret))
    assert config.get_appkey(profile="default") == "keychain-appkey-0001"


def test_both_env_and_file_is_an_error(monkeypatch, tmp_path):
    """어느 쪽이 이겼는지 조용히 달라지는 것보다 즉시 실패가 낫다."""
    secret = tmp_path / "appkey"
    secret.write_text(ENV_APPKEY, encoding="utf-8")
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(secret))
    with pytest.raises(click.ClickException) as exc:
        config.get_appkey(profile="default")
    assert exc.value.code == "INVALID_INPUT"


def test_unreadable_file_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(tmp_path / "does-not-exist"))
    with pytest.raises(click.ClickException) as exc:
        config.get_appkey(profile="default")
    assert exc.value.code == "INVALID_INPUT"


# ── is_configured ────────────────────────────────────


def test_is_configured_true_with_env_only(monkeypatch):
    """키체인도 config.toml도 없는 컨테이너에서 True여야 auth login이 돈다."""
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    assert config.is_configured(profile="default") is True


def test_is_configured_false_with_nothing():
    assert config.is_configured(profile="default") is False


# ── appkey_source (감사용) ───────────────────────────


def test_appkey_source_env(monkeypatch, keychain_creds):
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    assert config.appkey_source(profile="default") == "env"


def test_appkey_source_env_file(monkeypatch, tmp_path):
    secret = tmp_path / "appkey"
    secret.write_text(ENV_APPKEY, encoding="utf-8")
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(secret))
    assert config.appkey_source(profile="default") == "env_file"


def test_appkey_source_keychain(keychain_creds):
    assert config.appkey_source(profile="default") == "keychain"


def test_appkey_source_none():
    assert config.appkey_source(profile="default") is None


# ── CLI 표면: auth status / config show ──────────────


def _json(result):
    import json
    return json.loads(result.stdout)


def test_auth_status_reports_env_source(monkeypatch):
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    result = CliRunner().invoke(cli, ["-f", "json", "auth", "status"])
    assert result.exit_code == 0
    data = _json(result)["data"]
    assert data["appkey_source"] == "env"
    assert data["configured"] is True


def test_auth_status_reports_keychain_source(keychain_creds):
    result = CliRunner().invoke(cli, ["-f", "json", "auth", "status"])
    assert result.exit_code == 0
    assert _json(result)["data"]["appkey_source"] == "keychain"


def test_auth_status_reports_null_source_when_unset():
    result = CliRunner().invoke(cli, ["-f", "json", "auth", "status"])
    assert result.exit_code == 0
    assert _json(result)["data"]["appkey_source"] is None


def test_config_show_reports_env_file_source(monkeypatch, tmp_path):
    secret = tmp_path / "appkey"
    secret.write_text(ENV_APPKEY, encoding="utf-8")
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(secret))
    result = CliRunner().invoke(cli, ["-f", "json", "config", "show"])
    assert result.exit_code == 0
    data = _json(result)["data"]
    assert data["appkey_source"] == "env_file"
    assert data["configured"] is True


def test_conflicting_env_vars_produce_envelope_error(monkeypatch, tmp_path):
    """ClickException.code가 envelope으로 흘러 exit 1이 되는지 — CLI 표면 확인."""
    secret = tmp_path / "appkey"
    secret.write_text(ENV_APPKEY, encoding="utf-8")
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    monkeypatch.setenv("KIWOOM_APPKEY_FILE", str(secret))
    result = CliRunner().invoke(cli, ["-f", "json", "auth", "status"])
    assert result.exit_code == 1
    body = _json(result)
    assert body["ok"] is False
    assert body["error"]["code"] == "INVALID_INPUT"


# ── KIWOOM_TOKEN_STORAGE ─────────────────────────────


def test_token_storage_env_var_wins(monkeypatch):
    monkeypatch.setenv("KIWOOM_TOKEN_STORAGE", "env")
    assert config.get_token_storage(profile="default") == "env"


def test_token_storage_defaults_to_keychain():
    assert config.get_token_storage(profile="default") == "keychain"


def test_token_storage_invalid_env_forced_to_keychain(monkeypatch):
    """잘못된 값은 안전한 기본값으로 — KIWOOM_DOMAIN의 mock 강제와 같은 방향."""
    monkeypatch.setenv("KIWOOM_TOKEN_STORAGE", "s3")
    assert config.get_token_storage(profile="default") == "keychain"


# ── 키체인 없는 컨테이너 전 구간 ─────────────────────


class _NoKeyringBackend:
    """리눅스 컨테이너(secretservice 없음): 읽기·쓰기 모두 예외."""

    def get_password(self, service, username):
        raise keyring.errors.NoKeyringError("no backend")

    def set_password(self, service, username, password):
        raise keyring.errors.NoKeyringError("no backend")

    def delete_password(self, service, username):
        raise keyring.errors.NoKeyringError("no backend")


@pytest.fixture
def keychainless(monkeypatch):
    backend = _NoKeyringBackend()
    monkeypatch.setattr(keyring, "get_password", backend.get_password)
    monkeypatch.setattr(keyring, "set_password", backend.set_password)
    monkeypatch.setattr(keyring, "delete_password", backend.delete_password)


def test_container_auth_login_succeeds(monkeypatch, keychainless, httpx_mock):
    """컨테이너 전 구간: 키체인 없음 + env 자격증명 + token_storage=env → 발급 성공.

    v2.14.0까지 불가능했던 경로다 — 주입한 토큰이 만료되면 복구할 수 없었다.
    """
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    monkeypatch.setenv("KIWOOM_SECRETKEY", ENV_SECRETKEY)
    monkeypatch.setenv("KIWOOM_TOKEN_STORAGE", "env")
    httpx_mock.add_response(
        url="https://mockapi.kiwoom.com/oauth2/token",
        json={"return_code": 0, "token": "container-token-xyz"},
    )
    result = CliRunner().invoke(cli, ["-f", "json", "auth", "login"])
    assert result.exit_code == 0
    data = _json(result)["data"]
    assert data["token"] == "container-token-xyz"
    # 키체인에 쓰지 못했다는 사실을 그대로 보고한다 (성공으로 위장하지 않는다)
    assert data["saved"] is False
    assert data["token_storage"] == "env"


def test_container_auth_login_without_token_storage_fails(monkeypatch, keychainless, httpx_mock):
    """token_storage=env가 없으면 save_token이 키체인에 쓰려다 실패한다.

    문서가 KIWOOM_TOKEN_STORAGE=env를 요구사항으로 적는 이유를 고정한다 —
    env 자격증명만으로는 부족하다.
    """
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    monkeypatch.setenv("KIWOOM_SECRETKEY", ENV_SECRETKEY)
    httpx_mock.add_response(
        url="https://mockapi.kiwoom.com/oauth2/token",
        json={"return_code": 0, "token": "container-token-xyz"},
    )
    result = CliRunner().invoke(cli, ["-f", "json", "auth", "login"])
    assert result.exit_code == 1
    assert _json(result)["error"]["code"] == "KEYCHAIN_UNAVAILABLE"


# ── 토큰 발급이 env 자격증명을 싣는지 ────────────────


def test_issue_token_sends_env_credentials(monkeypatch, httpx_mock):
    """키체인 없는 컨테이너의 핵심 경로: env 자격증명으로 au10001을 호출한다."""
    monkeypatch.setenv("KIWOOM_APPKEY", ENV_APPKEY)
    monkeypatch.setenv("KIWOOM_SECRETKEY", ENV_SECRETKEY)
    httpx_mock.add_response(
        url="https://mockapi.kiwoom.com/oauth2/token",
        json={"return_code": 0, "token": "minted-token-abc"},
    )
    from kiwoom_cli.client import KiwoomClient

    with KiwoomClient(profile="default") as c:
        token = c.issue_token()

    assert token == "minted-token-abc"
    request = httpx_mock.get_requests()[0]
    import json as _json_mod
    body = _json_mod.loads(request.content)
    assert body["appkey"] == "env-appkey-9999"
    assert body["secretkey"] == "env-secretkey-9999"
