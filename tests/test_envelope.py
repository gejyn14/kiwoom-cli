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
    assert doc["data"]["stk_nm"] == "삼성전자"
    # return_code/return_msg는 기존처럼 제거
    assert "return_code" not in doc["data"]
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


def test_kiwoom_api_error_envelope_exit_2(runner, monkeypatch):
    _patch_raising_client(monkeypatch, KiwoomAPIError(8005, "Token이 유효하지 않습니다"))
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 2
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
