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


# ============================================================
#  task-14: ka10030 rank volume / ka10032 rank amount —
#  mang_stk_incls polarity inversion + --stock-condition rename
# ============================================================


def test_rank_volume_default_mang_stk_incls_unchanged(runner, fake_client):
    """Default send value for mang_stk_incls must stay '0' (unchanged behavior)."""
    result = runner.invoke(cli, ["market", "rank", "volume"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mang_stk_incls"] == "0"


def test_rank_volume_stock_condition_human_name(runner, fake_client):
    result = runner.invoke(
        cli, ["market", "rank", "volume", "--stock-condition", "exclude-etf"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mang_stk_incls"] == "14"


def test_rank_volume_stock_condition_raw_code_backcompat(runner, fake_client):
    """HumanChoice accepts raw API codes too — --stock-condition 14 must keep working."""
    result = runner.invoke(
        cli, ["market", "rank", "volume", "--stock-condition", "14"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mang_stk_incls"] == "14"


def test_rank_volume_include_managed_removed(runner, fake_client):
    """--include-managed no longer exists on rank volume (renamed to --stock-condition)."""
    result = runner.invoke(
        cli, ["market", "rank", "volume", "--include-managed", "1"]
    )

    assert result.exit_code == 1


def test_rank_amount_default_mang_stk_incls_unchanged(runner, fake_client):
    """Default send value for ka10032 mang_stk_incls must stay '0' (unchanged behavior)."""
    result = runner.invoke(cli, ["market", "rank", "amount"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mang_stk_incls"] == "0"


def test_rank_amount_include_managed_yes_is_polarity_opposite_of_volume(runner, fake_client):
    """ka10032's --include-managed yes -> '1', the OPPOSITE polarity of ka10030's 0=include."""
    result = runner.invoke(
        cli, ["market", "rank", "amount", "--include-managed", "yes"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mang_stk_incls"] == "1"


def test_rank_amount_exchange_widened_to_all(runner, fake_client):
    """rank amount --exchange all is a pure widening (EXCHANGE_ALL, stex_tp=3)."""
    result = runner.invoke(
        cli, ["market", "rank", "amount", "--exchange", "all"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "3"


def test_rank_volume_defaults_unchanged_full_body(runner, fake_client):
    """Full smoke: converting free-text options to HumanChoice must not change any
    default wire value sent to ka10030."""
    result = runner.invoke(cli, ["market", "rank", "volume"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1] == {
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


@pytest.mark.parametrize("option,cli_value,field,api_value", [
    ("--sort", "turnover", "sort_tp", "2"),
    ("--credit-type", "short", "crd_tp", "8"),
    ("--vol-type", "500k", "trde_qty_tp", "500"),
    ("--price-type", "over-100k", "pric_tp", "9"),
    ("--amount-type", "50m", "trde_prica_tp", "4"),
    ("--session", "after-hours", "mrkt_open_tp", "3"),
])
def test_rank_volume_other_options_converted(runner, fake_client, option, cli_value, field, api_value):
    """The other free-text ka10030 options are also narrowed to HumanChoice enums."""
    result = runner.invoke(cli, ["market", "rank", "volume", option, cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1][field] == api_value


def test_rank_volume_invalid_stock_condition_exits_1(runner, fake_client):
    result = runner.invoke(
        cli, ["market", "rank", "volume", "--stock-condition", "bogus"]
    )
    assert result.exit_code == 1


# ============================================================
#  task-14: ka10038 rank broker-by-stock — dt/--period + --from/--to
# ============================================================


def test_broker_by_stock_default_dt_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "broker-by-stock", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "1"


def test_broker_by_stock_from_to_drops_dt_key(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "broker-by-stock", "005930",
        "--from", "20260101", "--to", "20260107",
    ])

    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert "dt" not in body
    assert body["strt_dt"] == "20260101"
    assert body["end_dt"] == "20260107"


def test_broker_by_stock_period_off_by_one(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "broker-by-stock", "005930", "--period", "5d",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "4"


def test_broker_by_stock_period_and_from_to_conflict_exits_1(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "broker-by-stock", "005930",
        "--period", "5d", "--from", "20260101", "--to", "20260107",
    ])

    assert result.exit_code == 1


def test_broker_by_stock_from_without_to_exits_1(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "broker-by-stock", "005930", "--from", "20260101",
    ])

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_broker_by_stock_to_without_from_exits_1(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "broker-by-stock", "005930", "--to", "20260107",
    ])

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_broker_by_stock_side_human_name(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "broker-by-stock", "005930", "--type", "net-buy",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["qry_tp"] == "2"


# ============================================================
#  task-14: ka30002 elw broker-top — required --issuer + HumanChoice
# ============================================================


def test_elw_broker_top_issuer_required(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "broker-top"])
    assert result.exit_code == 1


def test_elw_broker_top_sends_issuer_code(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "broker-top", "--issuer", "001"])

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "ka30002"
    assert body["isscomp_cd"] == "001"


def test_elw_broker_top_default_values_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "broker-top", "--issuer", "001"])

    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_qty_tp"] == "0"
    assert body["trde_tp"] == "1"
    assert body["dt"] == "1"
    assert body["trde_end_elwskip"] == "1"


def test_elw_broker_top_side_net_buy_net_sell(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "elw", "broker-top", "--issuer", "001", "--type", "net-sell",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == "2"


@pytest.mark.parametrize("human,code", [("200k", "200"), ("300k", "300")])
def test_rank_volume_vol_type_has_200k_300k(runner, fake_client, human, code):
    """ka10030의 trde_qty_tp에만 있는 200/300 — ELW_BROKER_QTY_TYPE에는 없다."""
    result = runner.invoke(
        cli, ["market", "rank", "volume", "--vol-type", human]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_qty_tp"] == code


@pytest.mark.parametrize("human", ["200k", "300k"])
def test_elw_broker_top_vol_type_rejects_200k_300k(runner, fake_client, human):
    """ka30002에 VOLUME_RANK_QTY_TYPE를 잘못 물리면 통과해 버리는 것을 막는다.

    두 맵은 공유 키의 전송값이 전부 같아서 서로 바꿔 끼워도 잘못된 값이
    나가지는 않는다 — 유일하게 드러나는 차이가 ka10030에만 있는 200/300이다.
    그래서 이 두 값으로만 분리를 고정할 수 있다.
    """
    result = runner.invoke(cli, [
        "market", "elw", "broker-top", "--issuer", "001", "--vol-type", human,
    ])

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_elw_broker_top_period_not_off_by_one(runner, fake_client):
    """ka30002's dt is 5d=5 (NOT the ka10038 off-by-one codebook)."""
    result = runner.invoke(cli, [
        "market", "elw", "broker-top", "--issuer", "001", "--period", "5d",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "5"


def test_elw_broker_top_exclude_expired_human_name(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "elw", "broker-top", "--issuer", "001", "--exclude-expired", "include",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_end_elwskip"] == "0"
