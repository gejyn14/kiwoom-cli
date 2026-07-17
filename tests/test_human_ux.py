"""Tier-3 human-UX regression tests (price formatting, --no-color, truncation, discovery, human options)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.client import KiwoomAPIError  # noqa: F401  (used from Task 8 on)
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


# ── Task 1: stock price ──────────────────────────────────

_PRICE_RESPONSE = {
    "stk_nm": "삼성전자", "cur_prc": "-70000", "pred_pre": "-1000",
    "flu_rt": "-1.41", "return_code": 0,
}


def _price_client():
    def fake(api_id, body=None, **kwargs):
        return dict(_PRICE_RESPONSE), {}
    return _mock_kiwoom_client(fake)


def test_stock_price_table_strips_direction_sign(runner, isolated_env):
    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _price_client()
        result = runner.invoke(cli, ["stock", "price", "005930"])
    assert result.exit_code == 0
    assert "-70,000" not in result.output          # 방향지시자 부호 제거
    assert "70,000원" in result.output
    assert "-1,000" in result.output               # 전일대비는 부호 유지


def test_stock_price_json_emits_envelope(runner, isolated_env):
    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _price_client()
        result = runner.invoke(cli, ["-f", "json", "stock", "price", "005930"])
    assert result.exit_code == 0
    doc = _doc(result)
    assert doc["ok"] is True and doc["schema"] == "v1"
    assert doc["data"]["raw"]["cur_prc"] == "-70000"


# ── Task 2: --no-color ───────────────────────────────────

@pytest.fixture
def reset_no_color():
    yield
    from kiwoom_cli import output
    output.console.no_color = False
    output.err_console.no_color = False


def test_no_color_mutates_shared_console_instances(runner, isolated_env, reset_no_color):
    from kiwoom_cli import output
    from kiwoom_cli.formatters import console as fmt_console
    before_out, before_err = output.console, output.err_console
    assert fmt_console is before_out       # import-time 바인딩이 같은 객체를 봐야 함
    result = runner.invoke(cli, ["--no-color", "describe", "--paths"])
    assert result.exit_code == 0
    assert output.console is before_out and output.err_console is before_err
    assert output.console.no_color is True
    assert output.err_console.no_color is True
    assert fmt_console.no_color is True    # 실제 회귀: 재바인딩은 이 단언에서 실패
