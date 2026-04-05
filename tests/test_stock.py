"""Tests for stock commands (kiwoom_cli/commands/stock.py).

Phase 2 refactor-confidence coverage for read-only stock query commands.
stock.py is ~1684 lines with many subgroups (credit/analysis/investor/
chart/lending). One representative smoke per subgroup plus enum
parametrization for non-trivial CLI -> API mappings.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.commands._constants import MARKET_ALL
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject FakeKiwoomClient into stock module."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.stock.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


# ============================================================
#  Top-level stock commands
# ============================================================


def test_info_sends_code_to_ka10001(runner, fake_client):
    """info smoke: positional code -> stk_cd body, hits ka10001."""
    result = runner.invoke(cli, ["stock", "info", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10001", {"stk_cd": "005930"})]


def test_price_echoes_name_and_cur_prc(runner, fake_client):
    """price command prints stk_nm and cur_prc from API response."""
    fake_client.set_response(
        "ka10001",
        {
            "stk_nm": "삼성전자",
            "cur_prc": "70000",
            "pred_pre": "+500",
            "flu_rt": "+0.71",
        },
    )
    result = runner.invoke(cli, ["stock", "price", "005930"])

    assert result.exit_code == 0
    assert "삼성전자 (005930): 70000원 (+500, +0.71%)" in result.output


def test_orderbook_sends_to_ka10004(runner, fake_client):
    """orderbook smoke: positional code -> stk_cd body, hits ka10004."""
    result = runner.invoke(cli, ["stock", "orderbook", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10004", {"stk_cd": "005930"})]


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("day", "1"), ("week", "2"), ("month", "3")],
)
def test_daily_qry_type_enum_parametrized(
    runner, fake_client, cli_value, api_value
):
    """daily --type day/week/month maps to qry_tp 1/2/3."""
    result = runner.invoke(
        cli, ["stock", "daily", "005930", "--type", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("ka10005", {"stk_cd": "005930", "qry_tp": api_value})
    ]


def test_watchlist_passes_pipe_delimited_codes(runner, fake_client):
    """watchlist sends pipe-delimited codes to stk_cd as-is."""
    result = runner.invoke(cli, ["stock", "watchlist", "005930|000660"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10095", {"stk_cd": "005930|000660"})]


def test_daily_price_required_date(runner, fake_client):
    """daily-price without --date fails nonzero and makes no request."""
    result = runner.invoke(cli, ["stock", "daily-price", "005930"])

    assert result.exit_code != 0
    assert fake_client.calls == []


# ============================================================
#  Credit subgroup
# ============================================================


def test_credit_trend_sends_correct_api(runner, fake_client):
    """credit trend smoke: hits ka10013 with stk_cd/dt/qry_tp body."""
    result = runner.invoke(
        cli,
        ["stock", "credit", "trend", "005930", "--date", "20260101"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10013",
            {"stk_cd": "005930", "dt": "20260101", "qry_tp": "1"},
        )
    ]


# ============================================================
#  Analysis subgroup
# ============================================================


@pytest.mark.parametrize("cli_value,api_value", list(MARKET_ALL.items()))
def test_analysis_volume_renewal_market_enum(
    runner, fake_client, cli_value, api_value
):
    """Each MARKET_ALL key maps to correct API value in mrkt_tp field."""
    result = runner.invoke(
        cli,
        ["stock", "analysis", "volume-renewal", "--market", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "ka10024"
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value
    assert fake_client.calls[0][1]["stex_tp"] == "3"  # EXCHANGE_ALL["all"] default
