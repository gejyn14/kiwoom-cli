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


# ── auth logout: 폐기한 토큰과 지운 토큰이 일치하는가 ──────────────────


@pytest.fixture
def logout_ready(monkeypatch):
    """logout이 필요한 최소 설정 + revoke HTTP 응답 mock."""
    from kiwoom_cli import client as client_mod

    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "ak")
    keyring.set_password(config.KEYRING_SERVICE, "default:secretkey", "sk")
    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)

    posted: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"return_code": 0}

        def raise_for_status(self):
            return None

    def _post(self, url, **kwargs):
        posted.update(kwargs.get("json") or {})
        return _Resp()

    monkeypatch.setattr(client_mod.httpx.Client, "post", _post)
    return posted


def test_logout_with_env_token_does_not_delete_keychain_token(
    logout_ready, monkeypatch,
):
    """KIWOOM_TOKEN이 있으면 그 토큰이 폐기된다. 키체인의 별개 토큰까지
    지워버리면 그 토큰은 영영 폐기할 수 없다."""
    monkeypatch.setenv("KIWOOM_TOKEN", "env-token")
    keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")

    result = CliRunner().invoke(cli, ["auth", "logout"])

    assert result.exit_code == 0, result.output
    assert logout_ready["token"] == "env-token"
    assert (
        keyring.get_password(config.KEYRING_SERVICE, "default:token")
        == "keychain-token"
    ), "폐기하지 않은 키체인 토큰이 삭제됐다"
    # 메시지가 실제로 한 일과 일치해야 한다
    assert "삭제하지 않았습니다" in result.output
    assert "unset KIWOOM_TOKEN" in result.output


def test_logout_json_reports_which_token_was_revoked(logout_ready, monkeypatch):
    import json as _json

    monkeypatch.setenv("KIWOOM_TOKEN", "env-token")
    keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")

    result = CliRunner().invoke(cli, ["-f", "json", "auth", "logout"])

    assert result.exit_code == 0, result.output
    doc = _json.loads(result.stdout)
    assert doc["ok"] is True
    assert doc["data"]["token_source"] == "env"
    assert doc["data"]["keychain_token_deleted"] is False


def test_logout_without_env_token_deletes_keychain_token(logout_ready):
    keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")

    result = CliRunner().invoke(cli, ["auth", "logout"])

    assert result.exit_code == 0, result.output
    assert logout_ready["token"] == "keychain-token"
    assert keyring.get_password(config.KEYRING_SERVICE, "default:token") is None
    assert "키체인" in result.output


@pytest.fixture
def revoke_fails(monkeypatch):
    """revoke 응답이 상단 실패(return_code 8015)를 돌려주도록 만든다.

    logout_ready가 돌려주는 dict는 '전송된 body'라는 뜻이므로 거기에 응답
    스텁을 섞지 않고, 여기서 post를 따로 갈아끼운다.
    """
    from kiwoom_cli import client as client_mod

    class _FailResp:
        status_code = 200

        def json(self):
            return {"return_code": 8015, "return_msg": "폐기 실패"}

        def raise_for_status(self):
            return None

    monkeypatch.setattr(client_mod.httpx.Client, "post", lambda self, url, **kw: _FailResp())


class TestLogoutVerifiesRevoke:
    """revoke 응답을 확인하지 않고 revoked:true를 보고한 뒤 로컬 토큰을
    지웠다. 서버에는 토큰이 살아 있는데 로컬 사본이 없어 두 번 다시 폐기할 수
    없는 상태가 된다."""

    def test_upstream_failure_exits_2_and_keeps_token(self, logout_ready, revoke_fails):
        import json as _json

        keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")
        result = CliRunner().invoke(cli, ["-f", "json", "auth", "logout"])
        assert result.exit_code == 2, result.output
        doc = _json.loads(result.stdout)
        assert doc["ok"] is False
        assert keyring.get_password(config.KEYRING_SERVICE, "default:token") is not None, \
            "폐기에 실패했는데 로컬 토큰을 지웠다 — 재시도가 영영 불가능해진다"

    def test_force_deletes_local_token_despite_failure(self, logout_ready, revoke_fails):
        """서버 도달 불가로 영영 로컬 정리를 못 하는 상황의 탈출구."""
        keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")
        result = CliRunner().invoke(cli, ["auth", "logout", "--force"])
        assert result.exit_code == 0, result.output
        assert keyring.get_password(config.KEYRING_SERVICE, "default:token") is None

    def test_http_error_also_blocks_deletion(self, logout_ready, monkeypatch):
        """return_code뿐 아니라 HTTP 4xx/5xx도 성공으로 보고되면 안 된다."""
        import httpx

        from kiwoom_cli import client as client_mod

        class _HttpErrResp:
            status_code = 500

            def json(self):
                return {}

            def raise_for_status(self):
                raise httpx.HTTPStatusError("500", request=None, response=None)

        monkeypatch.setattr(client_mod.httpx.Client, "post",
                            lambda self, url, **kw: _HttpErrResp())
        keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")
        result = CliRunner().invoke(cli, ["auth", "logout"])
        assert result.exit_code != 0
        assert keyring.get_password(config.KEYRING_SERVICE, "default:token") is not None

    def test_success_path_unchanged(self, logout_ready):
        import json as _json

        keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")
        result = CliRunner().invoke(cli, ["-f", "json", "auth", "logout"])
        assert result.exit_code == 0, result.output
        doc = _json.loads(result.stdout)
        assert doc["data"]["revoked"] is True
