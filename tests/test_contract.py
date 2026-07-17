"""Tier-2 agent-contract regression tests (envelope purity, exit codes, discovery, purity long tail)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import click  # noqa: F401
import httpx
import pytest
from click.testing import CliRunner

from kiwoom_cli import config  # noqa: F401
from kiwoom_cli.client import KiwoomAPIError
from kiwoom_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """config를 tmp로 격리하고 프로필/도메인 env를 제거한다."""
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


def _mock_kiwoom_client(request_fn):
    """conventions 패턴: context-manager를 지원하는 KiwoomClient MagicMock."""
    mc = MagicMock()
    mc.request = request_fn
    mc.__enter__ = lambda s: s
    mc.__exit__ = MagicMock(return_value=False)
    return mc


def _doc(result):
    """stdout에서 envelope 문서 파싱 (stderr 혼입 방지를 위해 stdout 사용)."""
    return json.loads(result.stdout)


# ── Task 1: KiwoomGroup contract fixes ───────────────────

def test_unknown_command_json_emits_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "nosuchcmd"])
    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_token_expired_8005_exits_3(runner, isolated_env):
    def raise_expired(api_id, body=None, **kwargs):
        raise KiwoomAPIError(8005, "Token 유효하지 않습니다")

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(raise_expired)
        result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 3
    doc = _doc(result)
    assert doc["error"]["code"] == "TOKEN_EXPIRED"


def test_api_error_still_exits_2(runner, isolated_env):
    def raise_api(api_id, body=None, **kwargs):
        raise KiwoomAPIError(1902, "종목 정보 없음")

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(raise_api)
        result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 2
    assert _doc(result)["error"]["code"] == "NOT_FOUND"


def test_read_timeout_emits_network_error_exit_2(runner, isolated_env):
    def raise_timeout(api_id, body=None, **kwargs):
        raise httpx.ReadTimeout("timed out")

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(raise_timeout)
        result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["error"]["code"] == "NETWORK_ERROR"
    assert doc["error"]["retryable"] is True


# ── Task 2: fail_input sweep (order paths) ───────────────

def test_kr_float_price_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                 "--price", "70000.5", "--type", "limit", "--dry-run"])
    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_us_partial_cancel_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "cancel", "0001", "NVDA",
                                 "--qty", "5", "--confirm"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_cond_price_on_us_symbol_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "buy", "NVDA", "10",
                                 "--cond-price", "100", "--confirm"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_fail_input_table_mode_stderr_only(runner, isolated_env):
    result = runner.invoke(cli, ["order", "buy", "005930", "10",
                                 "--price", "70000.5", "--type", "limit", "--dry-run"])
    assert result.exit_code == 1
    assert result.stdout.strip() == ""


# ── Task 3: fail_input sweep (query/config paths) ────────

def test_config_set_invalid_domain_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "config", "set", "domain", "staging"])
    assert result.exit_code == 1
    doc = _doc(result)          # 기존 버그: rich 텍스트가 stdout에 섞여 파싱 불가였음
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_config_use_unknown_profile_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "config", "use", "nope"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_krw_on_domestic_symbol_json_envelope(runner, isolated_env):
    # stock info has no --krw option; --krw lives on stock chart {tick,minute,day,week,month,year}.
    # chart tick is the first sweep-site command with --krw and no other required options.
    result = runner.invoke(cli, ["-f", "json", "stock", "chart", "tick", "005930", "--krw"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"
