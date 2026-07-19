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
    AMT_QTY_TP_0_1,
    ELW_BALANCE_RANK_SORT,
    ELW_CHANGE_RANK_SORT,
    ELW_RANK_RIGHT_TYPE_3DIGIT,
    ELW_RIGHT_TYPE_1DIGIT,
    ELW_RIGHT_TYPE_3DIGIT,
    ELW_SEARCH_SORT,
    ELW_SURGE_DIRECTION,
    ELW_SURGE_QTY_TYPE,
    ELW_SURGE_TIME_UNIT,
    ETF_ALL_NAV,
    ETF_ALL_TAX_TYPE,
    ETF_ALL_TAXABLE,
    ETF_RETURNS_PERIOD,
    EXCHANGE_TWO,
    EXCLUDE_ENDED_ELW,
    GOLD_PRICE_TYPE,
    MARKET_ALL,
    MARKET_KOSPI_KOSDAQ,
    MARKET_TWO,
    SECTOR_CODES_MARKET,
    SECTOR_PRICE_MARKET,
    THEME_LOOKUP_KIND,
    THEME_LOOKUP_SORT,
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
#  Rankings (순위정보) — ka10016~ka10023 HumanChoice 전환 (Task 31a)
#
#  각 커맨드마다 기본 호출 body를 통째로 고정한다.
#
#  trde_qty_tp(--vol-type)는 Task 31a-fix에서 뒤늦게 전환했다. 종전 기본값
#  raw "0"은 8개 API 어디에도 스펙 값으로 존재하지 않는 사전 결함이었고,
#  이번에 API별 스펙 최하단 값(= 필터를 가장 적게 거는 값)으로 교정했다.
#  8개 코드북의 자릿수가 전부 달라(5자리/4자리/무패딩) 여기 기대값도
#  커맨드마다 다르다 — 복붙 금지. task-31a-fix-report.md 참고.
# ============================================================


def test_rank_new_highlow_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "new-highlow"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10016", {
        "mrkt_tp": "000", "ntl_tp": "1", "high_low_close_tp": "1",
        "stk_cnd": "0", "trde_qty_tp": "00000", "crd_cnd": "0",
        "updown_incls": "0", "dt": "5", "stex_tp": "1",
    })


def test_rank_new_highlow_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "new-highlow", "--type", "new-low", "--basis", "close",
        "--stk-cnd", "exclude-preferred", "--credit", "b", "--include-limit", "yes",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["ntl_tp"] == "2"
    assert body["high_low_close_tp"] == "2"
    assert body["stk_cnd"] == "3"
    assert body["crd_cnd"] == "2"
    assert body["updown_incls"] == "1"


def test_rank_limit_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "limit"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10017", {
        "mrkt_tp": "000", "updown_tp": "1", "sort_tp": "2",
        "stk_cnd": "0", "trde_qty_tp": "00000", "crd_cnd": "0",
        "trde_gold_tp": "0", "stex_tp": "1",
    })


def test_rank_limit_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "limit", "--type", "prev-lower", "--sort", "change-rate",
        "--stk-cnd", "exclude-managed-preferred-alert", "--credit", "e",
        "--trade-gold", "over-1k",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["updown_tp"] == "7"
    assert body["sort_tp"] == "3"
    assert body["stk_cnd"] == "10"
    assert body["crd_cnd"] == "7"
    assert body["trde_gold_tp"] == "8"


def test_rank_near_highlow_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "near-highlow"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10018", {
        "high_low_tp": "1", "alacc_rt": "05", "mrkt_tp": "000",
        "trde_qty_tp": "00000", "stk_cnd": "0", "crd_cnd": "0", "stex_tp": "1",
    })


def test_rank_near_highlow_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "near-highlow", "--type", "low",
        "--stk-cnd", "only-margin-30", "--credit", "d",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["high_low_tp"] == "2"
    assert body["stk_cnd"] == "8"
    assert body["crd_cnd"] == "4"


def test_rank_surge_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "surge"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10019", {
        "mrkt_tp": "000", "flu_tp": "1", "tm_tp": "1", "tm": "5",
        "trde_qty_tp": "00000", "stk_cnd": "0", "crd_cnd": "0",
        "pric_cnd": "0", "updown_incls": "0", "stex_tp": "1",
    })


def test_rank_surge_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "surge", "--type", "fall", "--time-type", "day",
        "--stk-cnd", "only-margin-100", "--credit", "c",
        "--price-cnd", "5k-10k", "--include-limit", "yes",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["flu_tp"] == "2"
    assert body["tm_tp"] == "2"
    assert body["stk_cnd"] == "6"
    assert body["crd_cnd"] == "3"
    assert body["pric_cnd"] == "4"
    assert body["updown_incls"] == "1"


def test_rank_orderbook_top_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "orderbook-top"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10020", {
        "mrkt_tp": "001", "sort_tp": "1", "trde_qty_tp": "0000",
        "stk_cnd": "0", "crd_cnd": "0", "stex_tp": "1",
    })


def test_rank_orderbook_top_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "orderbook-top", "--sort", "sell-ratio",
        "--stk-cnd", "only-margin-20", "--credit", "all-financing",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["sort_tp"] == "4"
    assert body["stk_cnd"] == "9"
    assert body["crd_cnd"] == "9"


def test_rank_orderbook_surge_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "orderbook-surge"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10021", {
        "mrkt_tp": "001", "trde_tp": "1", "sort_tp": "1", "tm_tp": "5",
        "trde_qty_tp": "1", "stk_cnd": "0", "stex_tp": "1",
    })


def test_rank_orderbook_surge_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "orderbook-surge", "--type", "sell-balance",
        "--sort", "spike-rate", "--stk-cnd", "only-margin-40",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_tp"] == "2"
    assert body["sort_tp"] == "2"
    assert body["stk_cnd"] == "7"


def test_rank_balance_rate_surge_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "balance-rate-surge"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10022", {
        "mrkt_tp": "001", "rt_tp": "1", "tm_tp": "5",
        "trde_qty_tp": "5", "stk_cnd": "0", "stex_tp": "1",
    })


def test_rank_balance_rate_surge_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "balance-rate-surge", "--type", "sell-to-buy",
        "--stk-cnd", "exclude-margin-100",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["rt_tp"] == "2"
    assert body["stk_cnd"] == "5"


def test_rank_volume_surge_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "volume-surge"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10023", {
        "mrkt_tp": "000", "sort_tp": "1", "tm_tp": "1", "trde_qty_tp": "5",
        "tm": "", "stk_cnd": "0", "pric_tp": "0", "stex_tp": "1",
    })


def test_rank_volume_surge_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "volume-surge", "--sort", "drop-rate",
        "--time-type", "previous-day", "--stk-cnd", "exclude-etf-etn-spac",
        "--price-type", "over-100k",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["sort_tp"] == "4"
    assert body["tm_tp"] == "2"
    assert body["stk_cnd"] == "20"
    assert body["pric_tp"] == "9"


def test_rank_new_highlow_legacy_numeric_code_still_accepted(runner, fake_client):
    """HumanChoice의 하위호환: raw API 코드도 그대로 통과해야 한다."""
    result = runner.invoke(cli, ["market", "rank", "new-highlow", "--type", "2"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["ntl_tp"] == "2"


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


# ── Task 31a-fix: --vol-type(trde_qty_tp) 8개 코드북 ───────────────
#
#  8개 API의 trde_qty_tp 값 집합은 자릿수까지 서로 다르다. 아래 테스트는
#  "human 이름 → 그 API의 wire 코드"를 API별로 각각 못 박는다. 한 곳의
#  기대값을 다른 곳에 복사하면 조용히 틀린다.


@pytest.mark.parametrize("command,api_id,human,wire", [
    # ka10016~ka10019: 5자리 zero-pad, "all"=00000이 존재한다.
    ("new-highlow", "ka10016", "all", "00000"),
    ("new-highlow", "ka10016", "10k", "00010"),
    ("new-highlow", "ka10016", "1000k", "01000"),
    ("limit", "ka10017", "all", "00000"),
    ("limit", "ka10017", "150k", "00150"),
    ("near-highlow", "ka10018", "all", "00000"),
    ("near-highlow", "ka10018", "500k", "00500"),
    ("surge", "ka10019", "all", "00000"),
    ("surge", "ka10019", "300k", "00300"),
    # ka10020: 4자리 zero-pad. "전체"가 없고 최하단이 preopen(장시작전).
    # 100k만 5자리 "00100"인 것은 스펙·kwcli가 모두 그렇게 적고 있다.
    ("orderbook-top", "ka10020", "preopen", "0000"),
    ("orderbook-top", "ka10020", "10k", "0010"),
    ("orderbook-top", "ka10020", "50k", "0050"),
    ("orderbook-top", "ka10020", "100k", "00100"),
    # ka10021~ka10023: 무패딩 정수. "전체" 개념이 아예 없다.
    ("orderbook-surge", "ka10021", "1k", "1"),
    ("orderbook-surge", "ka10021", "100k", "100"),
    ("balance-rate-surge", "ka10022", "5k", "5"),
    ("balance-rate-surge", "ka10022", "100k", "100"),
    ("volume-surge", "ka10023", "5k", "5"),
    ("volume-surge", "ka10023", "1000k", "1000"),
])
def test_rank_vol_type_human_name_maps_per_api(
    runner, fake_client, command, api_id, human, wire
):
    result = runner.invoke(cli, ["market", "rank", command, "--vol-type", human])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == api_id
    assert fake_client.calls[0][1]["trde_qty_tp"] == wire


@pytest.mark.parametrize("command,absent", [
    # 각 API에 "없는" human 이름은 거부돼야 한다 — 코드북이 합쳐지면
    # 이 테스트가 먼저 깨진다.
    ("orderbook-top", "all"),        # ka10020에는 전체가 없다
    ("orderbook-surge", "all"),      # ka10021에도 없다
    ("balance-rate-surge", "1k"),    # ka10022 최하단은 5k다
    ("volume-surge", "1k"),          # ka10023 최하단도 5k다
    ("new-highlow", "1k"),           # ka10016 사다리에 1k는 없다
])
def test_rank_vol_type_rejects_name_absent_from_that_api(
    runner, fake_client, command, absent
):
    result = runner.invoke(cli, ["market", "rank", command, "--vol-type", absent])

    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("command,wire", [
    ("new-highlow", "00050"),
    ("orderbook-top", "0050"),
    ("volume-surge", "50"),
])
def test_rank_vol_type_raw_wire_code_still_accepted(
    runner, fake_client, command, wire
):
    """HumanChoice는 원시 코드도 하위호환으로 통과시킨다."""
    result = runner.invoke(cli, ["market", "rank", command, "--vol-type", wire])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_qty_tp"] == wire


@pytest.mark.parametrize("command", [
    "new-highlow", "limit", "near-highlow", "surge",
    "orderbook-top", "orderbook-surge", "balance-rate-surge", "volume-surge",
])
def test_rank_vol_type_no_longer_sends_bare_zero(runner, fake_client, command):
    """종전 기본값 raw "0"은 8개 API 어디에도 스펙 값이 아니다 — 회귀 방지."""
    result = runner.invoke(cli, ["market", "rank", command])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_qty_tp"] != "0"


# ── Task 31a-fix: 형제 API 이름 거부(상위집합 오염 방지) ────────────
#
#  stk_cnd / sort_tp / 가격조건 코드북은 API마다 사다리가 다르다. 어떤
#  API의 상수를 형제 상수(특히 상위집합)로 바꿔치기해도 "정상 값이 맞게
#  나간다"는 테스트는 전부 통과한다. 그 API에 없는 이름이 거부되는지까지
#  봐야 잡힌다. 아래 이름들은 형제 API에는 있고 이 API에는 없는 값이다.
#  값 목록 출처: docs/미국 REST API 문서.xlsx 의 각 api_id 시트.


@pytest.mark.parametrize("command,absent", [
    # ka10016 stk_cnd = 0,1,3,5,6,7,8
    ("new-highlow", "exclude-managed-preferred"),          # 4: ka10017/ka10023
    ("new-highlow", "only-margin-20"),                     # 9: ka10017/20/21/22/23
    ("new-highlow", "exclude-etf"),                        # 14: ka10023
    # ka10017 stk_cnd = 0,1,3,4,5,6,7,8,9,10
    ("limit", "exclude-liquidation"),                      # 11: ka10023
    ("limit", "only-margin-50"),                           # 12: ka10023
    ("limit", "exclude-etf-etn-spac"),                     # 20: ka10023
    # ka10018 stk_cnd = 0,1,3,5,6,7,8
    ("near-highlow", "exclude-managed-preferred"),         # 4
    ("near-highlow", "only-margin-20"),                    # 9
    # ka10019 stk_cnd = 0,1,3,5,6,7,8
    ("surge", "exclude-managed-preferred"),                # 4
    ("surge", "only-margin-20"),                           # 9
    # ka10020 stk_cnd = 0,1,5,6,7,8,9 — 우선주제외(3)가 없다
    ("orderbook-top", "exclude-preferred"),                # 3: ka10016/17/18/19/23
    ("orderbook-top", "exclude-managed-preferred"),        # 4
    # ka10021 stk_cnd = ka10020과 동일
    ("orderbook-surge", "exclude-preferred"),              # 3
    ("orderbook-surge", "exclude-managed-preferred"),      # 4
    # ka10022 stk_cnd = ka10020과 동일
    ("balance-rate-surge", "exclude-preferred"),           # 3
    ("balance-rate-surge", "exclude-managed-preferred"),   # 4
    # ka10023 stk_cnd = 17개 사다리지만 10(우선주+관리+환기제외)은 없다
    ("volume-surge", "exclude-managed-preferred-alert"),   # 10: ka10017 전용
])
def test_rank_stk_cnd_rejects_name_absent_from_that_api(
    runner, fake_client, command, absent
):
    result = runner.invoke(cli, ["market", "rank", command, "--stk-cnd", absent])

    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("command,absent", [
    # ka10017 sort_tp = 종목코드순/연속횟수순/등락률순
    ("limit", "spike-quantity"),        # ka10021/ka10023
    ("limit", "net-buy-balance"),       # ka10020
    # ka10020 sort_tp = 순매수잔량/순매도잔량/매수비율/매도비율
    ("orderbook-top", "spike-quantity"),
    ("orderbook-top", "drop-rate"),     # ka10023
    ("orderbook-top", "code"),          # ka10017
    # ka10021 sort_tp = 급증량/급증률 뿐 — 급감 계열이 없다
    ("orderbook-surge", "drop-quantity"),   # ka10023
    ("orderbook-surge", "drop-rate"),       # ka10023
    ("orderbook-surge", "net-buy-balance"),
    # ka10023 sort_tp = 급증량/급증률/급감량/급감률
    ("volume-surge", "code"),
    ("volume-surge", "net-buy-balance"),
])
def test_rank_sort_tp_rejects_name_absent_from_that_api(
    runner, fake_client, command, absent
):
    result = runner.invoke(cli, ["market", "rank", command, "--sort", absent])

    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("command,option,absent", [
    # ka10017 trde_gold_tp / ka10019 pric_cnd = 구간형(1천원미만~1만원이상)
    ("limit", "--trade-gold", "over-50k"),      # ka10023 pric_tp
    ("limit", "--trade-gold", "over-5k"),       # ka10023 pric_tp
    ("limit", "--trade-gold", "over-100k"),     # ka10023 pric_tp
    ("surge", "--price-cnd", "over-50k"),
    ("surge", "--price-cnd", "over-5k"),
    ("surge", "--price-cnd", "over-100k"),
    # ka10023 pric_tp = 하한형(5천원이상/1만원이상/...) — 구간형이 없다
    ("volume-surge", "--price-type", "under-1k"),
    ("volume-surge", "--price-type", "1k-2k"),
    ("volume-surge", "--price-type", "5k-10k"),
])
def test_rank_price_cnd_rejects_name_absent_from_that_api(
    runner, fake_client, command, option, absent
):
    result = runner.invoke(cli, ["market", "rank", command, option, absent])

    assert result.exit_code != 0
    assert fake_client.calls == []


# ============================================================
#  Task 31b — market rank ka10027~ka10039 HumanChoice 전환
#
#  ka10030(rank volume)/ka10032(rank amount)/ka10038(broker-by-stock)는
#  Tranche B에서 이미 전환돼 있어 이 태스크는 건드리지 않았다(위
#  "task-14: ka10030/ka10032"와 "ka10038" 섹션의 기존 테스트 참고).
#
#  각 커맨드마다 기본 호출 body를 통째로 고정한 뒤 옵션을 전환한다
#  (브리프 요구사항). ka10027의 --vol-cnd(trde_qty_cnd)는 유일한 예외 —
#  종전 기본값 raw "0"이 4자리 스펙 어디에도 없던 결함이라 "0000"으로
#  전송 바이트 자체가 바뀌었다(CHANGELOG breaking 항목).
# ============================================================


def test_rank_change_default_body_wire_value_fixed(runner, fake_client):
    """ka10027 기본 호출: trde_qty_cnd가 "0"이 아니라 "0000"으로 나가야 한다.

    이건 표기 전환이 아니라 전송 바이트가 바뀌는 fix다 — 종전 raw "0"은
    4자리 zero-pad 스펙(0000~1000) 어디에도 없는 값이었다.
    """
    result = runner.invoke(cli, ["market", "rank", "change"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10027", {
        "mrkt_tp": "000", "sort_tp": "1", "trde_qty_cnd": "0000",
        "stk_cnd": "0", "crd_cnd": "0", "updown_incls": "0",
        "pric_cnd": "0", "trde_prica_cnd": "0", "stex_tp": "1",
    })


def test_rank_change_vol_cnd_raw_zero_no_longer_accepted(runner, fake_client):
    """Breaking: 종전에 통하던 raw "0"은 4자리 스펙에 없는 값이라 이제 거부된다."""
    result = runner.invoke(cli, ["market", "rank", "change", "--vol-cnd", "0"])
    assert result.exit_code != 0
    assert fake_client.calls == []


def test_rank_change_vol_cnd_raw_4digit_code_still_accepted(runner, fake_client):
    """HumanChoice 하위호환: 올바른 4자리 raw 코드는 그대로 통과한다."""
    result = runner.invoke(cli, ["market", "rank", "change", "--vol-cnd", "0150"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_qty_cnd"] == "0150"


def test_rank_change_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "change", "--sort", "fall-price",
        "--vol-cnd", "500k", "--stk-cnd", "exclude-etf", "--credit", "e",
        "--include-limit", "yes", "--price-cnd", "under-10k",
        "--amount-cnd", "10b",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["sort_tp"] == "4"
    assert body["trde_qty_cnd"] == "0500"
    assert body["stk_cnd"] == "14"
    assert body["crd_cnd"] == "7"
    assert body["updown_incls"] == "1"
    assert body["pric_cnd"] == "10"
    assert body["trde_prica_cnd"] == "1000"


def test_rank_expected_change_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "expected-change"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10029", {
        "mrkt_tp": "000", "sort_tp": "1", "trde_qty_cnd": "0",
        "stk_cnd": "0", "crd_cnd": "0", "pric_cnd": "0", "stex_tp": "1",
    })


def test_rank_expected_change_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "expected-change", "--sort", "volume",
        "--vol-cnd", "1k", "--stk-cnd", "exclude-liquidation",
        "--credit", "exclude-overlimit", "--price-cnd", "over-1k",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["sort_tp"] == "6"
    assert body["trde_qty_cnd"] == "1"
    assert body["stk_cnd"] == "11"
    assert body["crd_cnd"] == "5"
    assert body["pric_cnd"] == "8"


def test_rank_prev_volume_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "prev-volume"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10031", {
        "mrkt_tp": "000", "qry_tp": "1",
        "rank_strt": "1", "rank_end": "50", "stex_tp": "1",
    })


def test_rank_prev_volume_type_human_name(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "prev-volume", "--type", "amount"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["qry_tp"] == "2"


def test_rank_credit_ratio_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "credit-ratio"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10033", {
        "mrkt_tp": "000", "trde_qty_tp": "0", "stk_cnd": "0",
        "updown_incls": "0", "crd_cnd": "0", "stex_tp": "1",
    })


def test_rank_credit_ratio_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "credit-ratio", "--vol-type", "200k",
        "--stk-cnd", "only-margin-20", "--include-limit", "yes",
        "--credit", "d",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_qty_tp"] == "200"
    assert body["stk_cnd"] == "9"
    assert body["updown_incls"] == "1"
    assert body["crd_cnd"] == "4"


def test_rank_foreign_period_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "foreign-period"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10034", {
        "mrkt_tp": "000", "trde_tp": "2", "dt": "0", "stex_tp": "1",
    })


def test_rank_foreign_period_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "foreign-period", "--type", "net-trade", "--period", "20d",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_tp"] == "3"
    assert body["dt"] == "20"


def test_rank_foreign_consecutive_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "foreign-consecutive"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10035", {
        "mrkt_tp": "000", "trde_tp": "2", "base_dt_tp": "0", "stex_tp": "1",
    })


def test_rank_foreign_consecutive_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "foreign-consecutive", "--type", "net-sell",
        "--base-date", "previous",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_tp"] == "1"
    assert body["base_dt_tp"] == "1"


def test_rank_foreign_exhaust_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "foreign-exhaust"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10036", {
        "mrkt_tp": "000", "dt": "0", "stex_tp": "1",
    })


def test_rank_foreign_exhaust_period_human_name(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "foreign-exhaust", "--period", "60d"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "60"


def test_rank_foreign_broker_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "foreign-broker"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10037", {
        "mrkt_tp": "000", "dt": "0", "trde_tp": "1", "sort_tp": "1", "stex_tp": "1",
    })


def test_rank_foreign_broker_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "foreign-broker", "--period", "10d",
        "--type", "sell", "--sort", "quantity",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["dt"] == "10"
    assert body["trde_tp"] == "4"
    assert body["sort_tp"] == "2"


def test_rank_broker_top_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "broker-top", "001"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10039", {
        "mmcm_cd": "001", "trde_qty_tp": "0",
        "trde_tp": "1", "dt": "1", "stex_tp": "1",
    })


def test_rank_broker_top_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "broker-top", "001", "--vol-type", "500k",
        "--type", "net-sell", "--period", "today",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_qty_tp"] == "500"
    assert body["trde_tp"] == "2"
    assert body["dt"] == "0"


def test_rank_credit_ratio_legacy_numeric_code_still_accepted(runner, fake_client):
    """HumanChoice의 하위호환: raw API 코드도 그대로 통과해야 한다."""
    result = runner.invoke(cli, ["market", "rank", "credit-ratio", "--stk-cnd", "5"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stk_cnd"] == "5"


# ── Task 31b: 형제 API 이름 거부(상위집합 오염 방지) ────────────────
#
#  형제 상수로 바꿔치기해도 기본 호출/정상 human 옵션 테스트는 전부 통과
#  한다 — 값 집합이 실제로 다른 상수 쌍만, 상대 API에는 있고 이 API에는
#  없는 이름을 거부하는지로 구분할 수 있다. 값이 100%로 동일한 쌍(예:
#  RANK_CHANGE_STK_CND/EXPECTED_CHANGE_STK_CND)은 어떤 테스트로도 구분이
#  안 돼 여기 없다 — task-31b-report.md "구분 불가" 절 참고.


def test_rank_credit_ratio_stk_cnd_rejects_name_absent_from_ka10033(runner, fake_client):
    """exclude-preferred(3)는 ka10027 RANK_CHANGE_STK_CND엔 있지만 ka10033엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "credit-ratio", "--stk-cnd", "exclude-preferred"])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["150k", "200k", "300k", "500k", "1000k"])
def test_rank_expected_change_vol_cnd_rejects_name_absent_from_ka10029(runner, fake_client, absent):
    """ka10027 RANK_CHANGE_QTY_CND에만 있는 큰 임계값은 ka10029엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "expected-change", "--vol-cnd", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["1k", "3k"])
def test_rank_change_vol_cnd_rejects_name_absent_from_ka10027(runner, fake_client, absent):
    """ka10029 EXPECTED_CHANGE_QTY_CND에만 있는 무패딩 소형 임계값은 ka10027엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "change", "--vol-cnd", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


def test_rank_foreign_consecutive_type_rejects_net_trade(runner, fake_client):
    """net-trade(3)는 ka10034 FOREIGN_PERIOD_SIDE엔 있지만 ka10035엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "foreign-consecutive", "--type", "net-trade"])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["buy", "sell"])
def test_rank_broker_top_type_rejects_name_absent_from_ka10039(runner, fake_client, absent):
    """buy/sell 단독값은 ka10037 FOREIGN_BROKER_SIDE엔 있지만 ka10039엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "broker-top", "001", "--type", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


def test_rank_broker_top_period_rejects_20d(runner, fake_client):
    """20d는 ka10034/36/37의 PERIOD_TODAY_PREV_5_60엔 있지만 ka10039엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "broker-top", "001", "--period", "20d"])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["exclude-overlimit", "short"])
def test_rank_change_credit_rejects_name_absent_from_ka10027(runner, fake_client, absent):
    """exclude-overlimit/short는 ka10029 EXPECTED_CHANGE_CREDIT_CND엔 있지만 ka10027엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "change", "--credit", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["exclude-overlimit", "short"])
def test_rank_credit_ratio_credit_rejects_name_absent_from_ka10033(runner, fake_client, absent):
    """exclude-overlimit/short는 ka10029 EXPECTED_CHANGE_CREDIT_CND엔 있지만 ka10033 CREDIT_RATIO_CREDIT_CND엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "credit-ratio", "--credit", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["5d", "20d"])
def test_rank_foreign_consecutive_base_date_rejects_name_absent_from_ka10035(runner, fake_client, absent):
    """5d/20d는 PERIOD_TODAY_PREV_5_60(ka10034/36/37)엔 있지만 ka10035 FOREIGN_CONSECUTIVE_BASE_DATE엔
    없다. 5d는 BROKER_TOP_PERIOD(ka10039)에도 있어 두 형제 상수 바꿔치기를 모두 잡아낸다."""
    result = runner.invoke(cli, ["market", "rank", "foreign-consecutive", "--base-date", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


def test_rank_credit_ratio_vol_type_rejects_5k(runner, fake_client):
    """5k는 ka10039 BROKER_TOP_QTY_TYPE엔 있지만 ka10033 CREDIT_RATIO_QTY_TYPE엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "credit-ratio", "--vol-type", "5k"])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["200k", "300k"])
def test_rank_broker_top_vol_type_rejects_name_absent_from_ka10039(runner, fake_client, absent):
    """200k/300k는 ka10033 CREDIT_RATIO_QTY_TYPE엔 있지만 ka10039 BROKER_TOP_QTY_TYPE엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "broker-top", "001", "--vol-type", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["volume", "upper-limit", "lower-limit"])
def test_rank_change_sort_rejects_name_absent_from_ka10027(runner, fake_client, absent):
    """volume/upper-limit/lower-limit은 ka10029 EXPECTED_CHANGE_SORT엔 있지만 ka10027엔 없다."""
    result = runner.invoke(cli, ["market", "rank", "change", "--sort", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


# ============================================================
#  Task 31c — market rank ka10042/ka10062/ka10065/ka10098/ka90009
#  HumanChoice 전환
#
#  각 커맨드마다 기본 호출 body를 통째로 고정한 뒤 옵션을 전환한다
#  (브리프 요구사항). 이번 청크는 순수 표기 전환뿐 — 전송 바이트가
#  바뀌는 wire-value fix는 없다.
# ============================================================


def test_rank_net_buyer_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "net-buyer", "005930"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10042", {
        "stk_cd": "005930", "strt_dt": "", "end_dt": "",
        "qry_dt_tp": "0", "pot_tp": "0", "dt": "5", "sort_base": "1",
    })


def test_rank_net_buyer_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "net-buyer", "005930",
        "--date-type", "start-end", "--pot-type", "previous", "--sort", "date",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["qry_dt_tp"] == "1"
    assert body["pot_tp"] == "1"
    assert body["sort_base"] == "2"


def test_rank_net_buyer_period_stays_raw_numeric(runner, fake_client):
    """dt(--period)는 I2 규칙(단위접미사만으로 라벨 유도 가능)에 따라 전환하지 않는다."""
    result = runner.invoke(cli, ["market", "rank", "net-buyer", "005930", "--period", "120"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "120"


def test_rank_same_net_trade_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "same-net-trade", "--from", "20241106"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10062", {
        "strt_dt": "20241106", "end_dt": "", "mrkt_tp": "000",
        "trde_tp": "1", "sort_cnd": "1", "unit_tp": "1", "stex_tp": "1",
    })


def test_rank_same_net_trade_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "same-net-trade", "--from", "20241106",
        "--type", "net-sell", "--sort", "amount", "--unit", "thousand",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_tp"] == "2"
    assert body["sort_cnd"] == "2"
    assert body["unit_tp"] == "1000"


def test_rank_investor_top_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "investor-top"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10065", {
        "trde_tp": "1", "mrkt_tp": "000", "orgn_tp": "9000", "amt_qty_tp": "1",
    })


def test_rank_investor_top_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "investor-top", "--type", "net-sell",
        "--investor", "pension", "--unit", "quantity",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_tp"] == "2"
    assert body["orgn_tp"] == "6000"
    assert body["amt_qty_tp"] == "2"


def test_rank_afterhours_change_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "afterhours-change"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10098", {
        "mrkt_tp": "000", "sort_base": "1", "stk_cnd": "0",
        "trde_qty_cnd": "0", "crd_cnd": "0", "trde_prica": "0",
    })


def test_rank_afterhours_change_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "afterhours-change", "--sort", "fall-price",
        "--stk-cnd", "exclude-liquidation", "--vol-cnd", "5k+",
        "--credit", "short", "--amount", "1b",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["sort_base"] == "4"
    assert body["stk_cnd"] == "2"
    assert body["trde_qty_cnd"] == "500"
    assert body["crd_cnd"] == "8"
    assert body["trde_prica"] == "1000"


def test_rank_foreign_inst_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "rank", "foreign-inst"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka90009", {
        "mrkt_tp": "000", "amt_qty_tp": "1", "qry_dt_tp": "0",
        "date": "", "stex_tp": "1",
    })


def test_rank_foreign_inst_human_options(runner, fake_client):
    result = runner.invoke(cli, [
        "market", "rank", "foreign-inst", "--unit", "quantity", "--date-type", "yes",
    ])
    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["amt_qty_tp"] == "2"
    assert body["qry_dt_tp"] == "1"


def test_rank_net_buyer_legacy_numeric_code_still_accepted(runner, fake_client):
    """HumanChoice의 하위호환: raw API 코드도 그대로 통과해야 한다."""
    result = runner.invoke(cli, ["market", "rank", "net-buyer", "005930", "--sort", "2"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["sort_base"] == "2"


# ── Task 31c: 형제 상수 이름 거부(상위집합 오염 방지) ───────────────
#
#  값 집합이 실제로 다른 상수 쌍만, 상대 API에는 있고 이 API에는 없는
#  이름을 거부하는지로 구분할 수 있다. byte-identical 쌍(구분 불가)은
#  아래 목록에 없다 — 보고서 "구분 불가" 절 참고.


@pytest.mark.parametrize("absent", ["buy", "sell"])
def test_rank_same_net_trade_type_rejects_name_absent_from_ka10062(runner, fake_client, absent):
    """buy/sell(단독값)은 ka10037 FOREIGN_BROKER_SIDE엔 있지만 ka10062 SAME_NET_TRADE_SIDE엔 없다.
    (superset-closure 스크립트: SAME_NET_TRADE_SIDE는 FOREIGN_BROKER_SIDE의 진짜 부분집합)"""
    result = runner.invoke(cli, [
        "market", "rank", "same-net-trade", "--from", "20241106", "--type", absent,
    ])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["buy", "sell"])
def test_rank_investor_top_type_rejects_name_absent_from_ka10065(runner, fake_client, absent):
    """buy/sell(단독값)은 ka10037 FOREIGN_BROKER_SIDE엔 있지만 ka10065 INVESTOR_TOP_SIDE엔 없다.
    (superset-closure 스크립트: INVESTOR_TOP_SIDE는 FOREIGN_BROKER_SIDE의 진짜 부분집합)"""
    result = runner.invoke(cli, ["market", "rank", "investor-top", "--type", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["5d", "20d"])
def test_rank_net_buyer_pot_type_rejects_name_absent_from_ka10042(runner, fake_client, absent):
    """5d/20d는 PERIOD_TODAY_PREV_5_60(ka10034/36/37)·BROKER_TOP_PERIOD(ka10039)엔 있지만
    ka10042의 --pot-type이 쓰는 TRADER_ANALYSIS_POSITION(today/previous만)엔 없다.
    cross-field 해저드: pot_tp(시점구분) 필드가 dt(기간) 필드의 today/previous 키와
    이름이 겹쳐 "today/previous 통합" 리팩터가 잘못 흡수하기 쉬운 자리
    (FOREIGN_CONSECUTIVE_BASE_DATE와 동일한 해저드 패턴, superset-closure 스크립트로 확인).
    """
    result = runner.invoke(cli, [
        "market", "rank", "net-buyer", "005930", "--pot-type", absent,
    ])
    assert result.exit_code != 0
    assert fake_client.calls == []


# ============================================================
#  Task 32 — market sector · theme (ka10051/ka20001/ka20002/ka20009/
#  ka10101/ka90001) HumanChoice 전환
#
#  각 커맨드마다 기본 호출 body를 통째로 고정한 뒤 옵션을 전환한다
#  (브리프 요구사항). 이번 청크는 순수 표기 전환뿐 — 전송 바이트가
#  바뀌는 wire-value fix는 없다(기존 raw 기본값이 전부 새 매핑의
#  values()에 포함됨을 확인했다).
# ============================================================


def test_sector_investor_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "sector", "investor"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10051", {
        "mrkt_tp": "0", "amt_qty_tp": "0", "base_dt": "", "stex_tp": "1",
    })


@pytest.mark.parametrize("cli_value,api_value", list(AMT_QTY_TP_0_1.items()))
def test_sector_investor_unit_human_options(runner, fake_client, cli_value, api_value):
    """AMT_QTY_TP_0_1의 각 이름이 정확한 amt_qty_tp 값으로 매핑되는지 고정.

    quantity가 "1"(0/1 극성)임을 못 박아 둔다 — AMT_QTY_TP_1_2/FOREIGN_BROKER_SORT/
    SAME_NET_TRADE_SORT(전부 quantity="2")로 바꿔치기해도 기본 body 테스트만으로는
    안 잡힌다(superset-closure 스크립트: 셋 다 AMT_QTY_TP_0_1과 polarity hazard).
    """
    result = runner.invoke(cli, ["market", "sector", "investor", "--unit", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


def test_sector_current_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "sector", "current", "001"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka20001", {"mrkt_tp": "0", "inds_cd": "001"})


def test_sector_stocks_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "sector", "stocks", "001"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == (
        "ka20002", {"mrkt_tp": "0", "inds_cd": "001", "stex_tp": "1"}
    )


def test_sector_daily_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "sector", "daily", "001"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka20009", {"mrkt_tp": "0", "inds_cd": "001"})


@pytest.mark.parametrize(
    "subcommand,api_id",
    [("current", "ka20001"), ("stocks", "ka20002"), ("daily", "ka20009")],
)
@pytest.mark.parametrize("cli_value,api_value", list(SECTOR_PRICE_MARKET.items()))
def test_sector_price_family_market_human_options(
    runner, fake_client, subcommand, api_id, cli_value, api_value
):
    """SECTOR_PRICE_MARKET(kospi/kosdaq/kospi200)이 3개 API(ka20001/02/09) 전부에서
    동일한 mrkt_tp 값으로 매핑되는지 고정. kospi200="2"까지 포함해 기존
    MARKET_KOSPI_KOSDAQ(kospi/kosdaq 2값)의 진짜 상위집합임을 값으로 못 박는다."""
    result = runner.invoke(
        cli, ["market", "sector", subcommand, "001", "--market", cli_value]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][0] == api_id
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value


def test_sector_codes_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "sector", "codes"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka10101", {"mrkt_tp": "0"})


@pytest.mark.parametrize("cli_value,api_value", list(SECTOR_CODES_MARKET.items()))
def test_sector_codes_market_human_options(runner, fake_client, cli_value, api_value):
    """SECTOR_CODES_MARKET(ka10101)의 5개 값 전부 고정 — kospi100(4)/krx100(7)까지
    포함해 SECTOR_PRICE_MARKET(3값)의 진짜 상위집합임을 못 박는다."""
    result = runner.invoke(cli, ["market", "sector", "codes", "--market", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value


def test_theme_groups_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "theme", "groups"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka90001", {
        "qry_tp": "0", "stk_cd": "", "date_tp": "1",
        "thema_nm": "", "flu_pl_amt_tp": "1", "stex_tp": "1",
    })


@pytest.mark.parametrize("cli_value,api_value", list(THEME_LOOKUP_KIND.items()))
def test_theme_groups_type_human_options(runner, fake_client, cli_value, api_value):
    """THEME_LOOKUP_KIND의 각 이름이 정확한 qry_tp 값으로 매핑되는지 고정.

    stock="2"임을 못 박아 둔다 — ALL_STOCK_QRY/PRODUCT_TYPE(둘 다 stock="1")로
    바꿔치기해도 all="0"이 겹쳐 기본 body 테스트만으로는 안 잡힌다
    (superset-closure 스크립트: 둘 다 THEME_LOOKUP_KIND와 polarity hazard).
    """
    result = runner.invoke(cli, ["market", "theme", "groups", "--type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["qry_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(THEME_LOOKUP_SORT.items()))
def test_theme_groups_sort_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "theme", "groups", "--sort", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["flu_pl_amt_tp"] == api_value


def test_sector_investor_legacy_numeric_code_still_accepted(runner, fake_client):
    """HumanChoice의 하위호환: raw API 코드도 그대로 통과해야 한다."""
    result = runner.invoke(cli, ["market", "sector", "investor", "--unit", "1"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == "1"


# ── Task 32: 형제 상수 이름 거부(상위집합 오염 방지) ────────────────
#
#  값 집합이 실제로 다른 상수 쌍만, 상대 API에는 있고 이 API에는 없는
#  이름을 거부하는지로 구분할 수 있다.


@pytest.mark.parametrize("absent", ["kospi100", "krx100"])
@pytest.mark.parametrize("subcommand", ["current", "stocks", "daily"])
def test_sector_price_family_rejects_name_absent_from_sector_price_market(
    runner, fake_client, subcommand, absent
):
    """kospi100/krx100은 ka10101 SECTOR_CODES_MARKET엔 있지만 ka20001/02/09가 쓰는
    SECTOR_PRICE_MARKET엔 없다(superset-closure 스크립트: SECTOR_PRICE_MARKET은
    SECTOR_CODES_MARKET의 진짜 부분집합)."""
    result = runner.invoke(
        cli, ["market", "sector", subcommand, "001", "--market", absent]
    )
    assert result.exit_code != 0
    assert fake_client.calls == []


# ============================================================
#  Task 33: market etf / elw / gold / program HumanChoice 전환
#  + --exchange 3자리(ka10030/ka90006/ka90007) EXCHANGE_ALL 확대
# ============================================================


# ── --exchange 3자리 정리 (v2.11.0에서 미룬 항목, ka10030/ka90006/ka90007) ──


def test_rank_volume_exchange_widened_to_all(runner, fake_client):
    """rank volume --exchange all은 순수 확대(widening) — ka10032(rank amount)와
    같은 모양(EXCHANGE_ALL, stex_tp=3)으로 맞춘다."""
    result = runner.invoke(cli, ["market", "rank", "volume", "--exchange", "all"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "3"


def test_rank_volume_exchange_default_still_krx(runner, fake_client):
    """widening 후에도 기본값은 그대로 KRX(1)를 보내야 한다."""
    result = runner.invoke(cli, ["market", "rank", "volume"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "1"


def test_program_arbitrage_balance_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "program", "arbitrage-balance", "--date", "20241125"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka90006", {"date": "20241125", "stex_tp": "1"})


def test_program_arbitrage_balance_exchange_widened_to_all(runner, fake_client):
    result = runner.invoke(
        cli, ["market", "program", "arbitrage-balance", "--date", "20241125", "--exchange", "all"]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "3"


def test_program_cumulative_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "program", "cumulative", "--date", "20241125"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka90007", {
        "date": "20241125", "amt_qty_tp": "1", "mrkt_tp": "0", "stex_tp": "1",
    })


def test_program_cumulative_exchange_widened_to_all(runner, fake_client):
    result = runner.invoke(
        cli, ["market", "program", "cumulative", "--date", "20241125", "--exchange", "all"]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "3"


@pytest.mark.parametrize("cli_value,api_value", [("amount", "1"), ("quantity", "2")])
def test_program_cumulative_unit_human_options(runner, fake_client, cli_value, api_value):
    """기대값을 AMT_QTY_TP_1_2 참조가 아니라 리터럴로 못 박는다.

    ka90007은 Task 33에서 AMT_QTY_TP_1_2 공유 사이트로 새로 편입됐는데, 이
    상수는 AMT_QTY_TP_0_1(amount=0,quantity=1)·SAME_NET_TRADE_SORT
    (quantity=1,amount=2)와 키가 같고 값만 다른 극성 해저드를 갖는다.
    parametrize가 상수를 참조하면 상수를 형제로 바꿔치기해도 수집 시점에
    바뀐 값을 그대로 가져와 자기참조로 통과한다.
    """
    result = runner.invoke(
        cli, ["market", "program", "cumulative", "--date", "20241125", "--unit", cli_value]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


def test_program_stock_time_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "program", "stock-time", "005930"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka90008", {
        "amt_qty_tp": "1", "stk_cd": "005930", "date": "",
    })


@pytest.mark.parametrize("cli_value,api_value", [("amount", "1"), ("quantity", "2")])
def test_program_stock_time_unit_human_options(runner, fake_client, cli_value, api_value):
    """ka90008도 ka90007과 같은 이유로 리터럴 고정 — 위 테스트 주석 참고."""
    result = runner.invoke(
        cli, ["market", "program", "stock-time", "005930", "--unit", cli_value]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


def test_program_stock_daily_unit_still_raw_text(runner, fake_client):
    """ka90013(stock-daily)의 --unit은 Required=N + 기존 기본값이 빈 문자열이라
    이번 태스크에서 HumanChoice로 전환하지 않았다 — raw 텍스트 그대로 통과해야 한다."""
    result = runner.invoke(cli, ["market", "program", "stock-daily", "005930", "--unit", "1"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka90013", {
        "amt_qty_tp": "1", "stk_cd": "005930", "date": "",
    })


# ── ka40001 ETF수익율 / ka40004 ETF전체시세 ──────────────────────────


def test_etf_returns_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "etf", "returns", "069500"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka40001", {
        "stk_cd": "069500", "etfobjt_idex_cd": "", "dt": "0",
    })


@pytest.mark.parametrize("cli_value,api_value", list(ETF_RETURNS_PERIOD.items()))
def test_etf_returns_period_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(
        cli, ["market", "etf", "returns", "069500", "--period", cli_value]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == api_value


def test_etf_all_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "etf", "all"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka40004", {
        "txon_type": "0", "navpre": "0", "mngmcomp": "0000",
        "txon_yn": "0", "trace_idex": "0", "stex_tp": "1",
    })


def test_etf_all_exchange_widened_to_all(runner, fake_client):
    """ka40004의 stex_tp도 스펙이 1:KRX,2:NXT,3:통합이라 ka10030/ka90006/ka90007과
    같이 all을 받도록 넓혔다. 기존 KRX/NXT와 기본값은 그대로 동작해야 한다."""
    result = runner.invoke(cli, ["market", "etf", "all", "--exchange", "all"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "3"


@pytest.mark.parametrize("cli_value,exchange_code", [("KRX", "1"), ("NXT", "2")])
def test_etf_all_exchange_existing_values_unchanged(
    runner, fake_client, cli_value, exchange_code
):
    """확대(widening)이므로 종전 두 값의 전송 바이트는 변하지 않아야 한다."""
    result = runner.invoke(cli, ["market", "etf", "all", "--exchange", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == exchange_code


@pytest.mark.parametrize("cli_value,api_value", list(ETF_ALL_TAX_TYPE.items()))
def test_etf_all_tax_type_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "etf", "all", "--tax-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["txon_type"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ETF_ALL_NAV.items()))
def test_etf_all_nav_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "etf", "all", "--nav", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["navpre"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ETF_ALL_TAXABLE.items()))
def test_etf_all_taxable_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "etf", "all", "--taxable", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["txon_yn"] == api_value


def test_etf_all_company_and_index_still_raw_text(runner, fake_client):
    """mngmcomp(운용사)/trace_idex(추적지수)는 개방형 코드북(미확인)이라
    이번 태스크에서 전환하지 않았다 — raw 코드가 그대로 통과해야 한다."""
    result = runner.invoke(
        cli, ["market", "etf", "all", "--company", "3020", "--index", "207"]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mngmcomp"] == "3020"
    assert fake_client.calls[0][1]["trace_idex"] == "207"


# ── ka30001 ELW가격급등락 ────────────────────────────────────────────


def test_elw_surge_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "surge"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka30001", {
        "flu_tp": "1", "tm_tp": "1", "tm": "5", "trde_qty_tp": "0",
        "isscomp_cd": "000000000000", "bsis_aset_cd": "000000000000",
        "rght_tp": "000", "lpcd": "000000000000", "trde_end_elwskip": "1",
    })


@pytest.mark.parametrize("cli_value,api_value", list(ELW_SURGE_DIRECTION.items()))
def test_elw_surge_direction_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "surge", "--type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["flu_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ELW_SURGE_TIME_UNIT.items()))
def test_elw_surge_time_unit_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "surge", "--time-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["tm_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ELW_SURGE_QTY_TYPE.items()))
def test_elw_surge_vol_type_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "surge", "--vol-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_qty_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ELW_RIGHT_TYPE_3DIGIT.items()))
def test_elw_surge_right_type_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "surge", "--right-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["rght_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(EXCLUDE_ENDED_ELW.items()))
def test_elw_surge_exclude_expired_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "surge", "--exclude-expired", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_end_elwskip"] == api_value


# ── ka30002 거래원별ELW순매매상위 (Tranche B에서 이미 전환 — 이름만 갱신) ──


def test_elw_broker_top_default_values_still_unchanged_after_rename(runner, fake_client):
    """ELW_BROKER_END_SKIP → EXCLUDE_ENDED_ELW로 상수 이름만 바뀌었을 뿐
    전송값은 그대로여야 한다."""
    result = runner.invoke(cli, ["market", "elw", "broker-top", "--issuer", "003"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_end_elwskip"] == "1"


@pytest.mark.parametrize("cli_value,api_value", list(EXCLUDE_ENDED_ELW.items()))
def test_elw_broker_top_exclude_expired_still_works_after_rename(runner, fake_client, cli_value, api_value):
    result = runner.invoke(
        cli, ["market", "elw", "broker-top", "--issuer", "003", "--exclude-expired", cli_value]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_end_elwskip"] == api_value


# ── ka30004 ELW괴리율 ────────────────────────────────────────────────


def test_elw_disparity_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "disparity"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka30004", {
        "isscomp_cd": "000000000000", "bsis_aset_cd": "000000000000",
        "rght_tp": "000", "lpcd": "000000000000", "trde_end_elwskip": "1",
    })


@pytest.mark.parametrize("cli_value,api_value", list(ELW_RIGHT_TYPE_3DIGIT.items()))
def test_elw_disparity_right_type_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "disparity", "--right-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["rght_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(EXCLUDE_ENDED_ELW.items()))
def test_elw_disparity_exclude_expired_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "disparity", "--exclude-expired", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_end_elwskip"] == api_value


# ── ka30005 ELW조건검색 ──────────────────────────────────────────────


def test_elw_search_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "search"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka30005", {
        "isscomp_cd": "000000000000", "bsis_aset_cd": "000000000000",
        "rght_tp": "0", "lpcd": "000000000000", "sort_tp": "0",
    })


@pytest.mark.parametrize("cli_value,api_value", list(ELW_RIGHT_TYPE_1DIGIT.items()))
def test_elw_search_right_type_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "search", "--right-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["rght_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ELW_SEARCH_SORT.items()))
def test_elw_search_sort_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "search", "--sort", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["sort_tp"] == api_value


# ── ka30009 ELW등락율순위 ────────────────────────────────────────────


def test_elw_change_rank_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "change-rank"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka30009", {
        "sort_tp": "1", "rght_tp": "000", "trde_end_skip": "1",
    })


@pytest.mark.parametrize("cli_value,api_value", list(ELW_CHANGE_RANK_SORT.items()))
def test_elw_change_rank_sort_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "change-rank", "--sort", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["sort_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ELW_RANK_RIGHT_TYPE_3DIGIT.items()))
def test_elw_change_rank_right_type_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "change-rank", "--right-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["rght_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(EXCLUDE_ENDED_ELW.items()))
def test_elw_change_rank_exclude_expired_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "change-rank", "--exclude-expired", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_end_skip"] == api_value


# ── ka30010 ELW잔량순위 ──────────────────────────────────────────────


def test_elw_balance_rank_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "elw", "balance-rank"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka30010", {
        "sort_tp": "1", "rght_tp": "000", "trde_end_skip": "1",
    })


@pytest.mark.parametrize("cli_value,api_value", list(ELW_BALANCE_RANK_SORT.items()))
def test_elw_balance_rank_sort_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "balance-rank", "--sort", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["sort_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(ELW_RANK_RIGHT_TYPE_3DIGIT.items()))
def test_elw_balance_rank_right_type_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "balance-rank", "--right-type", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["rght_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", list(EXCLUDE_ENDED_ELW.items()))
def test_elw_balance_rank_exclude_expired_human_options(runner, fake_client, cli_value, api_value):
    result = runner.invoke(cli, ["market", "elw", "balance-rank", "--exclude-expired", cli_value])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_end_skip"] == api_value


# ── ka50079/81/82/83 금현물 틱·일·주·월봉차트 ────────────────────────


def test_gold_chart_tick_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "gold", "chart-tick"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka50079", {
        "stk_cd": "M04020000", "tic_scope": "1", "upd_stkpc_tp": "0",
    })


@pytest.mark.parametrize(
    "subcommand,api_id,extra_args",
    [
        ("chart-tick", "ka50079", []),
        ("chart-day", "ka50081", ["--date", "20250826"]),
        ("chart-week", "ka50082", ["--date", "20250826"]),
        ("chart-month", "ka50083", ["--date", "20250826"]),
    ],
)
@pytest.mark.parametrize("cli_value,api_value", list(GOLD_PRICE_TYPE.items()))
def test_gold_chart_price_type_human_options(
    runner, fake_client, subcommand, api_id, extra_args, cli_value, api_value
):
    result = runner.invoke(
        cli, ["market", "gold", subcommand, *extra_args, "--price-type", cli_value]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][0] == api_id
    assert fake_client.calls[0][1]["upd_stkpc_tp"] == api_value


def test_gold_chart_day_default_body_unchanged(runner, fake_client):
    result = runner.invoke(cli, ["market", "gold", "chart-day", "--date", "20250826"])
    assert result.exit_code == 0
    assert fake_client.calls[0] == ("ka50081", {
        "stk_cd": "M04020000", "base_dt": "20250826", "upd_stkpc_tp": "0",
    })


def test_gold_chart_minute_price_type_still_raw_text(runner, fake_client):
    """ka50080(chart-minute)의 --price-type은 Required=N + 기존 기본값이 빈
    문자열이라 이번 태스크에서 전환하지 않았다 — raw 코드가 그대로 통과하고,
    기본 호출은 빈 문자열을 그대로 보내야 한다."""
    result = runner.invoke(cli, ["market", "gold", "chart-minute"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["upd_stkpc_tp"] == ""

    result2 = runner.invoke(cli, ["market", "gold", "chart-minute", "--price-type", "1"])
    assert result2.exit_code == 0
    assert fake_client.calls[-1][1]["upd_stkpc_tp"] == "1"


# ── Task 33: 형제 상수 이름 거부(상위집합 오염 방지) ─────────────────
#
#  superset-closure 스크립트(양쪽 predicate)로 찾은 진짜 부분집합 관계만
#  거부 테스트로 고정한다. 값이 완전히 동일한 쌍(ELW_SURGE_DIRECTION==
#  SURGE_DIRECTION, ELW_SURGE_TIME_UNIT==SURGE_TIME_UNIT, ELW_BALANCE_RANK_SORT
#  ==ORDERBOOK_SURGE_SIDE)은 어떤 테스트로도 구분할 수 없어 이름 규약과
#  _constants.py 주석만으로 방어한다(task-33-report.md 참고).


@pytest.mark.parametrize("absent", ["5k", "200k"])
def test_elw_surge_vol_type_rejects_name_absent_from_ka30001(runner, fake_client, absent):
    """5k/200k는 VOLUME_RANK_QTY_TYPE(ka10030)/CREDIT_RATIO_QTY_TYPE(ka10033)엔
    있지만 ELW_SURGE_QTY_TYPE(ka30001)엔 없다(superset-closure: 진짜 부분집합)."""
    result = runner.invoke(cli, ["market", "elw", "surge", "--vol-type", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("subcommand", ["change-rank", "balance-rank"])
def test_elw_rank_right_type_rejects_ex_absent_from_ka30009_ka30010(runner, fake_client, subcommand):
    """ex(005)는 ELW_RIGHT_TYPE_3DIGIT(ka30001/ka30004)엔 있지만
    ELW_RANK_RIGHT_TYPE_3DIGIT(ka30009/ka30010)엔 없다(superset-closure:
    진짜 부분집합 — 두 API 스펙 모두 005 코드 자체가 없다)."""
    result = runner.invoke(cli, ["market", "elw", subcommand, "--right-type", "ex"])
    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize("absent", ["flat", "volume"])
def test_elw_change_rank_sort_rejects_name_absent_from_ka30009(runner, fake_client, absent):
    """flat은 RANK_CHANGE_SORT(ka10027)/AFTERHOURS_CHANGE_SORT(ka10098)엔,
    volume은 ELW_SEARCH_SORT(ka30005)엔 있지만 ELW_CHANGE_RANK_SORT(ka30009)엔
    없다(superset-closure: 둘 다 진짜 상위집합)."""
    result = runner.invoke(cli, ["market", "elw", "change-rank", "--sort", absent])
    assert result.exit_code != 0
    assert fake_client.calls == []


# ── Task 33: polarity 해저드 — 기본값이 아닌 이름까지 wire 값을 고정
#  (predicate 2: keys ⊆ but values differ) ───────────────────────────


def test_elw_surge_direction_fall_pinned_against_limit_move_direction():
    """ELW_SURGE_DIRECTION의 키 집합은 LIMIT_MOVE_DIRECTION(ka10017)의 부분집합
    이지만 값이 다르다(fall: ELW_SURGE_DIRECTION=2, LIMIT_MOVE_DIRECTION=5).
    fall은 elw_surge의 기본값이 아니므로 기본 body 테스트로는 안 잡힌다."""
    assert ELW_SURGE_DIRECTION["fall"] == "2"


def test_elw_surge_qty_type_300k_unpadded_against_5digit_siblings():
    """ELW_SURGE_QTY_TYPE(무패딩)의 키 집합은 여러 5자리 zero-pad 상수
    (LIMIT_MOVE_QTY_TYPE_5DIGIT 등)의 부분집합이지만 값이 다르다
    (300k: ELW_SURGE_QTY_TYPE="300" vs 5자리류="00300"). 300k는 elw_surge의
    기본값이 아니므로 기본 body 테스트로는 안 잡힌다."""
    assert ELW_SURGE_QTY_TYPE["300k"] == "300"


@pytest.mark.parametrize(
    "subcommand,api_id,expected_code",
    [
        # 하드코딩된 리터럴 — mapping[...]을 참조하면 ELW_RIGHT_TYPE_3DIGIT을
        # 바꿔치기했을 때 parametrize 값도 같이 바뀌어 자기참조가 되므로
        # (실측: dict(ELW_RIGHT_TYPE_1DIGIT)로 치환해도 이 형태면 통과해
        # 버림) 반드시 고정된 문자열로 적는다.
        ("surge", "ka30001", "005"),
        ("search", "ka30005", "5"),
    ],
)
def test_elw_right_type_ex_padding_pinned(
    runner, fake_client, subcommand, api_id, expected_code
):
    """ELW_RIGHT_TYPE_3DIGIT(zero-pad)과 ELW_RIGHT_TYPE_1DIGIT(무패딩)은 키
    집합이 완전히 같지만 값이 다르다("ex": 3자리는 "005", 1자리는 "5").
    자릿수가 바뀌면 같은 human 이름이 다른 API에 잘못된 폭의 코드를 보내게
    되므로 각 API에서 정확한 폭으로 전송되는지 못 박는다."""
    result = runner.invoke(
        cli, ["market", "elw", subcommand, "--right-type", "ex"]
    )
    assert result.exit_code == 0
    assert fake_client.calls[0][0] == api_id
    assert fake_client.calls[0][1]["rght_tp"] == expected_code


def test_elw_change_rank_sort_fall_rate_pinned_against_expected_change_sort(runner, fake_client):
    """ELW_CHANGE_RANK_SORT의 키 집합은 EXPECTED_CHANGE_SORT(ka10029)의
    부분집합처럼 보이지만 값이 다르다(fall-rate: ELW_CHANGE_RANK_SORT="3",
    EXPECTED_CHANGE_SORT="4"). fall-rate는 ka30009 change-rank의 기본값이
    아니므로(기본은 rise-rate) 기본 body 테스트로는 안 잡힌다."""
    result = runner.invoke(cli, ["market", "elw", "change-rank", "--sort", "fall-rate"])
    assert result.exit_code == 0
    assert fake_client.calls[0][1]["sort_tp"] == "3"


def test_elw_rank_right_type_call_padding_pinned_against_1digit_sibling():
    """ELW_RANK_RIGHT_TYPE_3DIGIT(zero-pad)의 키 집합은 ELW_RIGHT_TYPE_1DIGIT
    (무패딩)의 부분집합이지만 값이 다르다(call: 3자리는 "001", 1자리는 "1").
    call은 ka30009/ka30010의 기본값이 아니므로(기본은 all) 기본 body
    테스트로는 안 잡힌다."""
    assert ELW_RANK_RIGHT_TYPE_3DIGIT["call"] == "001"
    assert ELW_RIGHT_TYPE_1DIGIT["call"] == "1"


