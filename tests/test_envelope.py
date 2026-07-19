"""Envelope v1 tests.

Every `-f json` response — success AND error — uses one stable envelope:
{"ok": bool, "schema": "v1", "data": ..., "meta": {...}, "error": ...}
csv/table modes are unchanged.
"""

from __future__ import annotations

import json

import httpx
import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.client import KiwoomAPIError
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)
    return tmp_path


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_stock(monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response(
        "ka10001",
        {"return_code": 0, "return_msg": "OK", "stk_nm": "삼성전자", "stk_cd": "005930", "cur_prc": "+70000"},
    )
    monkeypatch.setattr("kiwoom_cli.commands.stock.KiwoomClient", lambda *a, **k: fake)
    return fake


# ── 성공 envelope ─────────────────────────────────────


def test_success_envelope_shape(runner, fake_stock):
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert set(doc) == {"ok", "schema", "data", "meta", "error"}
    assert doc["ok"] is True
    assert doc["schema"] == "v1"
    assert doc["error"] is None
    assert doc["data"]["name"] == "삼성전자"
    assert doc["data"]["raw"]["stk_nm"] == "삼성전자"
    # return_code/return_msg는 기존처럼 제거 (raw에서도)
    assert "return_code" not in doc["data"]
    assert "return_code" not in doc["data"]["raw"]
    assert doc["meta"]["profile"] == "default"
    assert doc["meta"]["env"] == "mock"
    assert doc["meta"]["cont"] is None


# ── 에러 envelope ─────────────────────────────────────


def _patch_raising_client(monkeypatch, exc):
    fake = FakeKiwoomClient()

    def _raise(*a, **k):
        raise exc

    fake.request = _raise
    monkeypatch.setattr("kiwoom_cli.commands.stock.KiwoomClient", lambda *a, **k: fake)


def test_kiwoom_api_error_token_expired_envelope_exit_3(runner, monkeypatch):
    # 8005는 TOKEN_EXPIRED로 분류되므로 exit 3 (Tier-2 Task 1: auth-aware exit code).
    _patch_raising_client(monkeypatch, KiwoomAPIError(8005, "Token이 유효하지 않습니다"))
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 3
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["data"] is None
    err = doc["error"]
    assert err["upstream_code"] == 8005
    assert isinstance(err["code"], str) and err["code"] == err["code"].upper()
    assert err["retryable"] is False
    assert "유효하지" in err["message"]


def test_http_401_envelope_token_expired_exit_3(runner, monkeypatch):
    req = httpx.Request("POST", "https://mock.test/x")
    exc = httpx.HTTPStatusError("401", request=req, response=httpx.Response(401, request=req))
    _patch_raising_client(monkeypatch, exc)
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 3
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "TOKEN_EXPIRED"
    assert doc["error"]["retryable"] is False
    assert doc["error"]["upstream_code"] == 401


# ── classify ──────────────────────────────────────────


def test_classify_maps_and_defaults():
    from kiwoom_cli import envelope

    assert envelope.classify(upstream_code=8005) == ("TOKEN_EXPIRED", False)
    assert envelope.classify(upstream_code=1700) == ("RATE_LIMITED", True)
    assert envelope.classify(upstream_code=999999) == ("UPSTREAM_ERROR", False)
    assert envelope.classify(http_status=401) == ("TOKEN_EXPIRED", False)
    assert envelope.classify(http_status=429) == ("RATE_LIMITED", True)
    assert envelope.classify(http_status=503) == ("UPSTREAM_ERROR", True)


# ── csv / table은 envelope 미적용 ─────────────────────


def test_csv_output_unchanged(runner, fake_stock):
    result = runner.invoke(cli, ["-f", "csv", "stock", "info", "005930"])
    assert result.exit_code == 0, result.output
    assert "stk_nm" in result.stdout
    assert '"schema"' not in result.stdout
    assert '"ok"' not in result.stdout


def test_table_output_unchanged(runner, fake_stock):
    result = runner.invoke(cli, ["stock", "info", "005930"])
    assert result.exit_code == 0, result.output
    assert "삼성전자" in result.stdout
    assert '"schema"' not in result.stdout


# ── 페이지네이션: last_cont / --next-key ──────────────


def test_request_stashes_last_cont_in_ctx(httpx_mock):
    import click

    from kiwoom_cli.client import KiwoomClient

    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"return_code": 0, "stk_nm": "x"},
        headers={"cont-yn": "Y", "next-key": "NK123"},
    )
    ctx = click.Context(click.Command("x"), obj={})
    with ctx:
        with KiwoomClient(domain="https://mock.test", token="t") as c:
            c.request("ka10001", {"stk_cd": "005930"})
    assert ctx.obj["last_cont"] == {"next_key": "NK123"}


def test_request_clears_last_cont_when_no_more_pages(httpx_mock):
    import click

    from kiwoom_cli.client import KiwoomClient

    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"return_code": 0, "stk_nm": "x"},
    )
    ctx = click.Context(click.Command("x"), obj={"last_cont": {"next_key": "stale"}})
    with ctx:
        with KiwoomClient(domain="https://mock.test", token="t") as c:
            c.request("ka10001", {"stk_cd": "005930"})
    assert ctx.obj["last_cont"] is None


def test_request_suppresses_last_cont_when_flagged(httpx_mock):
    """변이 호출(_mutation.suppress_pagination()이 세팅하는 ctx.obj["suppress_cont"])은
    업스트림이 cont-yn: Y/next-key를 보내더라도 last_cont를 기록하지 않는다.

    이 값이 그대로 기록되면 envelope의 meta.cont가 살아남아, AGENTS.md의 안내를
    따르는 에이전트가 --next-key로 "이어서" 실행 — 즉 주문/환전 등 실제 동작을
    한 번 더 실행하게 된다. suppress_pagination()이 이미 ctx.obj["all_pages"]를
    False로, next_key를 제거로 세팅하는 것과 같은 지점에서 이 플래그도 세팅하므로
    (client.py:112-118 참고), 새 변이 커맨드가 추가돼도 이 억제를 별도로 잊을 수
    없다."""
    import click

    from kiwoom_cli.client import KiwoomClient

    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"return_code": 0, "ord_no": "0000001"},
        headers={"cont-yn": "Y", "next-key": "NK123"},
    )
    ctx = click.Context(click.Command("x"), obj={"suppress_cont": True})
    with ctx:
        with KiwoomClient(domain="https://mock.test", token="t") as c:
            c.request("ka10001", {"stk_cd": "005930"})
    assert ctx.obj["last_cont"] is None


def test_request_without_suppress_flag_still_records_last_cont(httpx_mock):
    """대조군: suppress_cont 플래그가 없는 평범한 조회는 여전히 last_cont를
    정상적으로 기록해야 한다 — 변이 억제가 읽기 전용 페이지네이션까지 깨면 안 된다."""
    import click

    from kiwoom_cli.client import KiwoomClient

    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"return_code": 0, "stk_nm": "x"},
        headers={"cont-yn": "Y", "next-key": "NK123"},
    )
    ctx = click.Context(click.Command("x"), obj={})
    with ctx:
        with KiwoomClient(domain="https://mock.test", token="t") as c:
            c.request("ka10001", {"stk_cd": "005930"})
    assert ctx.obj["last_cont"] == {"next_key": "NK123"}


def test_success_meta_carries_cont(runner, monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response("ka10001", {"return_code": 0, "stk_nm": "삼성전자"})
    orig_request = fake.request

    def _request(api_id, body=None, **kw):
        import click

        ctx = click.get_current_context(silent=True)
        if ctx is not None and isinstance(ctx.obj, dict):
            ctx.obj["last_cont"] = {"next_key": "NK9"}
        return orig_request(api_id, body, **kw)

    fake.request = _request
    monkeypatch.setattr("kiwoom_cli.commands.stock.KiwoomClient", lambda *a, **k: fake)
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["meta"]["cont"] == {"next_key": "NK9"}


def test_api_command_next_key_option(runner, monkeypatch):
    fake = FakeKiwoomClient()
    captured: dict = {}
    orig_request = fake.request

    def _request(api_id, body=None, **kw):
        captured.update(kw)
        return orig_request(api_id, body)

    fake.request = _request
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda *a, **k: fake)
    result = runner.invoke(cli, ["-f", "json", "api", "ka10001", "{}", "--next-key", "NK1"])
    assert result.exit_code == 0, result.output
    assert captured.get("cont_yn") == "Y"
    assert captured.get("next_key") == "NK1"


# ── Gap 1: human-only 커맨드의 json 모드 envelope ─────


@pytest.fixture
def configured_default(monkeypatch):
    import keyring

    from kiwoom_cli import config as cfg_mod

    keyring.set_password(cfg_mod.KEYRING_SERVICE, "default:appkey", "ak")
    keyring.set_password(cfg_mod.KEYRING_SERVICE, "default:secretkey", "sk")


def _mock_issue(monkeypatch, token="issued-token-value-12345"):
    from kiwoom_cli import auth
    from kiwoom_cli.client import KiwoomClient as RealClient

    def _issue(self):
        auth.save_token(token, profile=self.profile)
        return token

    monkeypatch.setattr(RealClient, "issue_token", _issue)


def test_auth_login_json_keychain_envelope(runner, monkeypatch, configured_default):
    """-f json auth login (keychain): envelope, 토큰 원문 미노출."""
    _mock_issue(monkeypatch)
    result = runner.invoke(cli, ["-f", "json", "auth", "login"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    assert doc["data"]["token_storage"] == "keychain"
    assert doc["data"]["saved"] is True
    assert "issued-token-value-12345" not in result.stdout


def test_auth_login_json_env_mode_includes_token(runner, monkeypatch, configured_default):
    """-f json auth login (env): 사용자가 직접 관리해야 하므로 토큰 포함."""
    from kiwoom_cli import config as cfg_mod

    cfg = cfg_mod.load_config()
    cfg.setdefault("profiles", {}).setdefault("default", {})["token_storage"] = "env"
    cfg_mod.save_config(cfg)
    _mock_issue(monkeypatch)
    result = runner.invoke(cli, ["-f", "json", "auth", "login"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["data"]["saved"] is False
    assert doc["data"]["token"] == "issued-token-value-12345"


def test_auth_login_failure_exits_2_with_envelope(runner, monkeypatch, configured_default):
    """토큰 발급 실패가 더 이상 삼켜지지 않는다: json envelope + exit 2."""
    from kiwoom_cli.client import KiwoomClient as RealClient

    def _fail(self):
        raise KiwoomAPIError(8001, "App Key와 Secret Key 검증에 실패했습니다")

    monkeypatch.setattr(RealClient, "issue_token", _fail)
    result = runner.invoke(cli, ["-f", "json", "auth", "login"])
    assert result.exit_code == 2, result.output
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_CREDENTIALS"
    assert doc["error"]["upstream_code"] == 8001


def test_auth_login_failure_table_mode_exits_2(runner, monkeypatch, configured_default):
    """table 모드에서도 발급 실패는 exit 2 (기존: 삼켜져서 0)."""
    from kiwoom_cli.client import KiwoomClient as RealClient

    def _fail(self):
        raise KiwoomAPIError(8001, "검증 실패")

    monkeypatch.setattr(RealClient, "issue_token", _fail)
    result = runner.invoke(cli, ["auth", "login"])
    assert result.exit_code == 2, result.output


def test_auth_logout_json_envelope(runner, monkeypatch, configured_default):
    from kiwoom_cli.client import KiwoomClient as RealClient

    monkeypatch.setattr(RealClient, "revoke_token", lambda self: None)
    result = runner.invoke(cli, ["-f", "json", "auth", "logout"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    assert doc["data"]["revoked"] is True


def test_config_profiles_json_envelope(runner, configured_default):
    from kiwoom_cli import config as cfg_mod

    cfg = cfg_mod.load_config()
    cfg.setdefault("profiles", {})["default"] = {"domain": "mock"}
    cfg["profiles"]["isa"] = {"domain": "prod", "account": "123"}
    cfg.setdefault("general", {})["default_profile"] = "default"
    cfg_mod.save_config(cfg)
    result = runner.invoke(cli, ["-f", "json", "config", "profiles"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    names = {p["name"] for p in doc["data"]}
    assert names == {"default", "isa"}
    default_flags = {p["name"]: p["default"] for p in doc["data"]}
    assert default_flags["default"] is True
    assert default_flags["isa"] is False


def test_auth_login_unconfigured_json_envelope(runner):
    result = runner.invoke(cli, ["-f", "json", "auth", "login"])
    assert result.exit_code == 1
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "NOT_CONFIGURED"


# ── Gap 2: Click 입력 오류의 json envelope ────────────


def test_usage_error_json_envelope(runner):
    """인자 누락(UsageError): json 모드에서 envelope + exit 1."""
    result = runner.invoke(cli, ["-f", "json", "stock", "info"])
    assert result.exit_code == 1
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"
    assert doc["error"]["upstream_code"] is None


def test_usage_error_table_mode_unchanged(runner):
    """table 모드 UsageError는 기존 Click 출력 그대로 (envelope 없음)."""
    result = runner.invoke(cli, ["stock", "info"])
    assert result.exit_code == 1
    combined = result.output + result.stderr
    assert "Usage" in combined or "Error" in combined
    assert '"schema"' not in combined


def test_click_exception_json_envelope(runner):
    """커맨드 내부 ClickException(잘못된 JSON body): envelope + exit 1."""
    result = runner.invoke(cli, ["-f", "json", "api", "ka10001", "not-json"])
    assert result.exit_code == 1
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"
    assert "JSON" in doc["error"]["message"]


# ── Gap 3: api --raw + json 모드 ──────────────────────


def test_api_raw_json_mode_enveloped_unstripped(runner, monkeypatch):
    """--raw + -f json: envelope로 감싸되 data는 원본 그대로(return_code 포함)."""
    fake = FakeKiwoomClient()
    fake.set_response("ka10001", {"return_code": 0, "return_msg": "OK", "stk_nm": "삼성전자"})
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda *a, **k: fake)
    result = runner.invoke(cli, ["-f", "json", "api", "ka10001", "{}", "--raw"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    assert doc["data"]["return_code"] == 0
    assert doc["data"]["stk_nm"] == "삼성전자"
