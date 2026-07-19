"""Tests for market commands (kiwoom_cli/commands/market.py).

Phase 2 refactor-confidence coverage for market data query commands.
market.py is ~1531 lines across ~28 rank commands plus sector/etf/elw/
gold/program subgroups. Most commands share the same enum mapping
pattern, so we test each enum dict ONCE (via parametrize) plus one
representative smoke per additional subgroup.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.commands._constants import (
    EXCHANGE_TWO,
    MARKET_ALL,
    MARKET_KOSPI_KOSDAQ,
    MARKET_TWO,
)
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject FakeKiwoomClient into market module."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.market.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


# ============================================================
#  Rankings (순위정보) — ka10030 당일거래량상위
# ============================================================


def test_rank_volume_sends_to_ka10030(runner, fake_client):
    """rank volume smoke: defaults map through to ka10030 body."""
    result = runner.invoke(cli, ["market", "rank", "volume"])

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "ka10030"
    assert body == {
        "mrkt_tp": "000",
        "sort_tp": "1",
        "mang_stk_incls": "0",
        "crd_tp": "0",
        "trde_qty_tp": "0",
        "pric_tp": "0",
        "trde_prica_tp": "0",
        "mrkt_open_tp": "0",
        "stex_tp": "1",
    }


@pytest.mark.parametrize("cli_value,api_value", list(MARKET_ALL.items()))
def test_rank_volume_market_enum_parametrized(
    runner, fake_client, cli_value, api_value
):
    """Each MARKET_ALL key maps to correct API value in mrkt_tp field."""
    result = runner.invoke(
        cli, ["market", "rank", "volume", "--market", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(EXCHANGE_TWO.items()))
def test_rank_volume_exchange_enum_parametrized(
    runner, fake_client, cli_value, api_value
):
    """Each EXCHANGE_TWO key maps to correct API value in stex_tp field."""
    result = runner.invoke(
        cli, ["market", "rank", "volume", "--exchange", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(MARKET_TWO.items()))
def test_rank_orderbook_top_market_two_enum(
    runner, fake_client, cli_value, api_value
):
    """Each MARKET_TWO key maps to correct API value in mrkt_tp field."""
    result = runner.invoke(
        cli, ["market", "rank", "orderbook-top", "--market", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value


# ============================================================
#  Sectors (업종)
# ============================================================


def test_sector_index_sends_correct_api(runner, fake_client):
    """sector index smoke: default --inds-cd=001 hits ka20003."""
    result = runner.invoke(cli, ["market", "sector", "index"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka20003", {"inds_cd": "001"})]


def test_sector_chart_tick(runner, fake_client):
    """sector chart tick smoke: positional inds_cd + default scope → ka20004."""
    result = runner.invoke(
        cli, ["market", "sector", "chart", "tick", "001"]
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("ka20004", {"inds_cd": "001", "tic_scope": "1"})
    ]


@pytest.mark.parametrize(
    "cli_value,api_value", list(MARKET_KOSPI_KOSDAQ.items())
)
def test_sector_investor_market_kospi_kosdaq_enum(
    runner, fake_client, cli_value, api_value
):
    """Each MARKET_KOSPI_KOSDAQ key maps to correct API value in mrkt_tp field."""
    result = runner.invoke(
        cli, ["market", "sector", "investor", "--market", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value


# ============================================================
#  Program trades (프로그램매매) — ka90005 time-trend / ka90010 daily-trend
#
#  mrkt_tp is a 10-char P-code keyed by BOTH the human market name AND the
#  selected exchange (stex_tp) — see PROGRAM_MARKET_BY_EXCHANGE in
#  _constants.py. This is distinct from the flat MARKET_PROGRAM mapping used
#  by the sibling ka90003/ka90004 commands.
# ============================================================


PROGRAM_MRKT_TP_CASES = [
    ("kospi", "KRX", "P00101", "1"),
    ("kospi", "NXT", "P001_NX01", "2"),
    ("kospi", "all", "P001_AL01", "3"),
    ("kosdaq", "KRX", "P10102", "1"),
    ("kosdaq", "NXT", "P101_NX02", "2"),
    ("kosdaq", "all", "P101_AL02", "3"),
]


@pytest.mark.parametrize(
    "subcommand,api_id",
    [("time-trend", "ka90005"), ("daily-trend", "ka90010")],
)
@pytest.mark.parametrize(
    "market,exchange,mrkt_tp,stex_tp", PROGRAM_MRKT_TP_CASES
)
def test_program_trend_market_exchange_linked(
    runner, fake_client, subcommand, api_id, market, exchange, mrkt_tp, stex_tp
):
    """mrkt_tp (10-char P-code) is linked to stex_tp, not a standalone flag.

    Regression guard for the old default `mrkt_tp="0"`, which was copy-pasted
    from the sibling ka90007 (0:코스피,1:코스닥) codebook and undefined at
    these two endpoints.
    """
    result = runner.invoke(
        cli,
        [
            "market", "program", subcommand,
            "--date", "20241101",
            "--market", market,
            "--exchange", exchange,
        ],
    )

    assert result.exit_code == 0
    sent_api_id, body = fake_client.calls[0]
    assert sent_api_id == api_id
    assert body["mrkt_tp"] == mrkt_tp
    assert body["stex_tp"] == stex_tp
