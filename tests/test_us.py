"""Tests for US stock trading (kiwoom_cli/commands/us/)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.api_spec import API_REGISTRY
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


# ============================================================
#  Task 1: API registry
# ============================================================

US_API_URLS = {
    "ust20000": "/api/us/ordr", "ust20001": "/api/us/ordr",
    "ust20002": "/api/us/ordr", "ust20003": "/api/us/ordr",
    "ust31490": "/api/us/ordr",
    "ust21070": "/api/us/acnt", "ust21160": "/api/us/acnt",
    "ust21110": "/api/us/acnt", "ust21530": "/api/us/acnt",
    "ust21170": "/api/us/acnt", "ust21050": "/api/us/acnt",
    "ust21150": "/api/us/acnt", "ust21510": "/api/us/acnt",
    "ust21180": "/api/us/acnt", "ust21100": "/api/us/acnt",
    "usa10098": "/api/us/stkinfo", "usa10099": "/api/us/stkinfo",
    "usa10100": "/api/us/stkinfo",
    "usa20100": "/api/us/mrkcond", "usa20101": "/api/us/mrkcond",
    "usa06010": "/api/us/chart", "usa06011": "/api/us/chart",
    "usa06012": "/api/us/chart", "usa06013": "/api/us/chart",
    "usa06014": "/api/us/chart", "usa06015": "/api/us/chart",
    "ust31300": "/api/us/exchange", "ust31301": "/api/us/exchange",
    "ust31302": "/api/us/exchange",
}


def test_us_apis_registered():
    for api_id, url in US_API_URLS.items():
        assert api_id in API_REGISTRY, f"{api_id} missing"
        assert API_REGISTRY[api_id][0] == url, f"{api_id} wrong URL"


def test_us_apis_have_korean_descriptions():
    for api_id in US_API_URLS:
        desc = API_REGISTRY[api_id][1]
        assert desc, f"{api_id} has empty description"


# ============================================================
#  Task 2: constants + symbol detection
# ============================================================

from kiwoom_cli.commands.us._constants import (  # noqa: E402
    US_BUY_TYPES,
    US_EXCHANGE,
    US_ORDER_TYPES,
    US_SELL_TYPES,
    US_STOP_TYPES,
)
from kiwoom_cli.commands.us.detect import is_us_symbol  # noqa: E402


@pytest.mark.parametrize("code,exchange,expected", [
    ("005930", None, False),          # 6-digit numeric → KR
    ("NVDA", None, True),             # alpha ticker → US
    ("AAPL", None, True),
    ("BRK.B", None, True),            # dotted ticker → US
    ("12345", None, True),            # 5 digits → not KR shape → US
    ("005930", "nasdaq", True),       # explicit US override wins
    ("NVDA", "KRX", False),           # explicit KR override wins
    ("NVDA", "SOR", False),
    ("TSLA", "amex", True),
])
def test_is_us_symbol(code, exchange, expected):
    assert is_us_symbol(code, exchange) is expected


def test_us_order_type_codes():
    assert US_ORDER_TYPES == {
        "limit": "00", "market": "03",
        "vwap-limit": "26", "twap-limit": "27",
        "loc": "30", "moc": "33",
        "stop-limit": "34", "stop": "35",
        "vwap": "36", "twap": "37",
    }
    assert US_STOP_TYPES == frozenset({"stop", "stop-limit"})
    # buy has NO moc/stop/stop-limit
    assert US_BUY_TYPES == frozenset(
        {"limit", "market", "vwap-limit", "twap-limit", "loc", "vwap", "twap"}
    )
    assert US_SELL_TYPES == US_BUY_TYPES | frozenset({"moc", "stop", "stop-limit"})
    assert US_EXCHANGE == {"nasdaq": "ND", "nyse": "NY", "amex": "NA"}


# ============================================================
#  Task 3: exchange resolution + cache
# ============================================================

from kiwoom_cli.commands.us import detect  # noqa: E402


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """Point the exchange cache at a temp dir."""
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)
    return tmp_path / "us_exchanges.json"


def _fake_with_10098(entries):
    fake = FakeKiwoomClient()
    fake.set_response("usa10098", {"return_code": 0, "list": entries})
    return fake


def test_resolve_explicit_exchange_skips_api(tmp_cache):
    fake = FakeKiwoomClient()
    assert detect.resolve_us_exchange(fake, "NVDA", "nasdaq") == "ND"
    assert fake.calls == []  # no API hit


def test_resolve_via_usa10098_and_writes_cache(tmp_cache):
    fake = _fake_with_10098([{"stex_tp": "ND", "stk_cd": "NVDA"}])
    assert detect.resolve_us_exchange(fake, "NVDA") == "ND"
    assert fake.calls == [("usa10098", {"stk_cd": "NVDA"})]
    assert tmp_cache.exists()


def test_resolve_uses_cache_on_second_call(tmp_cache):
    fake = _fake_with_10098([{"stex_tp": "NY", "stk_cd": "KO"}])
    assert detect.resolve_us_exchange(fake, "KO") == "NY"
    fake2 = FakeKiwoomClient()  # would return default junk if called
    assert detect.resolve_us_exchange(fake2, "KO") == "NY"
    assert fake2.calls == []  # served from cache


def test_resolve_lowercases_nothing_uppercases_code(tmp_cache):
    fake = _fake_with_10098([{"stex_tp": "ND", "stk_cd": "NVDA"}])
    assert detect.resolve_us_exchange(fake, "nvda") == "ND"
    assert fake.calls[0][1] == {"stk_cd": "NVDA"}


def test_resolve_ambiguous_raises(tmp_cache):
    fake = _fake_with_10098([
        {"stex_tp": "ND", "stk_cd": "DUAL"},
        {"stex_tp": "NY", "stk_cd": "DUAL"},
    ])
    with pytest.raises(detect.UsExchangeError):
        detect.resolve_us_exchange(fake, "DUAL")


def test_resolve_not_found_raises(tmp_cache):
    fake = _fake_with_10098([])
    with pytest.raises(detect.UsExchangeError):
        detect.resolve_us_exchange(fake, "ZZZZ")


# ============================================================
#  Task 4: USD formatting
# ============================================================

from kiwoom_cli.formatters import _fmt_usd, _smart_fmt  # noqa: E402


@pytest.mark.parametrize("value,expected", [
    ("213.0400", "213.04"),
    ("0.0012", "0.0012"),
    ("1234.5000", "1,234.5"),
    ("70000", "70,000"),          # int stays int-formatted
    ("000001234", "1,234"),       # 0-padded
    ("+213.0400", "+213.04"),     # sign kept by default
    ("-0.5000", "-0.5"),
    ("", "-"),
    ("abc", "abc"),               # non-numeric passthrough
])
def test_fmt_usd(value, expected):
    assert _fmt_usd(value) == expected


def test_fmt_usd_strip_sign():
    assert _fmt_usd("+213.0400", strip_sign=True) == "213.04"
    assert _fmt_usd("-213.0400", strip_sign=True) == "213.04"


def test_smart_fmt_routes_usd_price_fields():
    # now_pric is a USD direction-indicator field: sign stripped, 4 decimals kept
    assert _smart_fmt("+213.0400", "now_pric") == "213.04"
    # pred_pre is signed USD
    assert _smart_fmt("-1.2500", "pred_pre") == "-1.25"
    # existing KR behavior unchanged for a non-USD field
    assert _smart_fmt("+70000", "cur_prc") == "70,000"


def test_generic_table_formats_usd_decimals(capsys):
    from kiwoom_cli.formatters import print_generic_table
    print_generic_table(
        [{"stk_cd": "NVDA", "now_pric": "+213.0400", "pl_amt": "-0.5000"}],
        title="t",
    )
    out = capsys.readouterr().out
    assert "213.04" in out and "213.0400" not in out
    assert "-0.5" in out and "0.5000" not in out


# ============================================================
#  Task 5: US buy/sell orders + dispatch
# ============================================================


@pytest.fixture
def us_fake(monkeypatch, tmp_cache):
    """FakeKiwoomClient injected into both order.py and us ops modules."""
    fake = FakeKiwoomClient()
    fake.set_response("usa10098", {"return_code": 0, "list": [{"stex_tp": "ND", "stk_cd": "NVDA"}]})
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", lambda *a, **k: fake)
    monkeypatch.setattr("kiwoom_cli.commands.us.order_ops.KiwoomClient", lambda *a, **k: fake)
    return fake


def _order_calls(fake, api_id):
    return [c for c in fake.calls if c[0] == api_id]


def test_us_buy_auto_detect_and_resolve(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "buy", "NVDA", "10", "--price", "213.04", "--type", "limit", "--confirm"]
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "ust20000") == [(
        "ust20000",
        {"stex_tp": "ND", "stk_cd": "NVDA", "ord_qty": "10", "ord_uv": "213.04", "trde_tp": "00"},
    )]


def test_us_buy_explicit_exchange_skips_resolution(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "buy", "TSLA", "1", "--exchange", "nasdaq", "--confirm"]
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "usa10098") == []
    body = _order_calls(us_fake, "ust20000")[0][1]
    assert body["stex_tp"] == "ND"
    assert body["trde_tp"] == "03"  # default market
    assert body["ord_uv"] == ""     # market order → empty price


def test_us_buy_rejects_sell_only_type(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "buy", "NVDA", "1", "--type", "moc", "--confirm"]
    )
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20000") == []


def test_us_sell_stop_limit_body(runner, us_fake):
    result = runner.invoke(
        cli,
        ["order", "sell", "NVDA", "5", "--type", "stop-limit",
         "--price", "200.5", "--stop", "199.9900", "--confirm"],
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "ust20001") == [(
        "ust20001",
        {"stex_tp": "ND", "stk_cd": "NVDA", "ord_qty": "5",
         "ord_uv": "200.5", "stop_pric": "199.99", "trde_tp": "34"},
    )]


def test_us_sell_stop_type_requires_stop_price(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "sell", "NVDA", "5", "--type", "stop", "--confirm"]
    )
    assert result.exit_code == 1


def test_kr_buy_unchanged_and_fractional_price_rejected(runner, us_fake):
    ok = runner.invoke(
        cli, ["order", "buy", "005930", "10", "--price", "70000", "--type", "limit", "--confirm"]
    )
    assert ok.exit_code == 0
    body = _order_calls(us_fake, "kt10000")[0][1]
    assert body["ord_uv"] == "70000" and body["dmst_stex_tp"] == "KRX"

    bad = runner.invoke(
        cli, ["order", "buy", "005930", "10", "--price", "70000.5", "--confirm"]
    )
    assert bad.exit_code == 1


def test_kr_sell_rejects_stop_option(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "sell", "005930", "1", "--stop", "100.0", "--confirm"]
    )
    assert result.exit_code == 1


def test_us_buy_kr_order_type_rejected(runner, us_fake):
    # KR-only type name on US path → exit 1
    result = runner.invoke(
        cli, ["order", "buy", "NVDA", "1", "--type", "fok", "--confirm"]
    )
    assert result.exit_code == 1


def test_us_buy_rejects_cond_price(runner, us_fake):
    result = runner.invoke(cli, ["order", "buy", "NVDA", "1", "--cond-price", "500", "--confirm"])
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20000") == []


def test_us_sell_rejects_cond_price(runner, us_fake):
    result = runner.invoke(cli, ["order", "sell", "NVDA", "1", "--cond-price", "500", "--confirm"])
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20001") == []


# ============================================================
#  Task 6: US modify/cancel/orderable
# ============================================================


def test_us_modify_price_only_no_qty_sent(runner, us_fake):
    result = runner.invoke(
        cli,
        ["order", "modify", "000000123", "NVDA", "5", "215.5", "--confirm"],
    )
    assert result.exit_code == 0
    assert "전량" in result.output  # 수량 변경 미지원 notice
    calls = _order_calls(us_fake, "ust20002")
    assert calls == [(
        "ust20002",
        {"orig_ord_no": "000000123", "stex_tp": "ND", "stk_cd": "NVDA", "mdfy_uv": "215.5"},
    )]


def test_us_modify_stop_limit_sends_stop_pric(runner, us_fake):
    result = runner.invoke(
        cli,
        ["order", "modify", "000000123", "NVDA", "5", "215.5", "--stop", "210.0", "--confirm"],
    )
    assert result.exit_code == 0
    body = _order_calls(us_fake, "ust20002")[0][1]
    assert body["stop_pric"] == "210"


def test_us_cancel_full_remaining(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "cancel", "000000123", "NVDA", "--confirm"]
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "ust20003") == [(
        "ust20003",
        {"orig_ord_no": "000000123", "stex_tp": "ND", "stk_cd": "NVDA"},
    )]


def test_us_cancel_rejects_partial_qty(runner, us_fake):
    # cancel's qty is passed via --qty (matches existing KR CLI shape); nonzero → exit 1 on US path
    result = runner.invoke(
        cli, ["order", "cancel", "000000123", "NVDA", "--qty", "3", "--confirm"]
    )
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20003") == []


def test_kr_modify_unchanged(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "modify", "0000139", "005930", "1", "70000", "--confirm"]
    )
    assert result.exit_code == 0
    assert len(_order_calls(us_fake, "kt10002")) == 1


def test_us_orderable_margin_qty(runner, us_fake, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.commands.account.KiwoomClient", lambda *a, **k: us_fake)
    result = runner.invoke(cli, ["account", "orderable", "margin-qty", "NVDA", "--price", "213.04"])
    assert result.exit_code == 0
    assert ("ust31490", {"stex_tp": "ND", "stk_cd": "NVDA", "uv": "213.04"}) in us_fake.calls


def test_us_orderable_margin_qty_requires_price(runner, us_fake, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.commands.account.KiwoomClient", lambda *a, **k: us_fake)
    result = runner.invoke(cli, ["account", "orderable", "margin-qty", "NVDA"])
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust31490") == []


def test_us_orderable_margin_qty_rejects_non_numeric_price(runner, us_fake, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.commands.account.KiwoomClient", lambda *a, **k: us_fake)
    result = runner.invoke(cli, ["account", "orderable", "margin-qty", "NVDA", "--price", "abc"])
    assert result.exit_code == 1
    # clean SystemExit, not a raw ValueError traceback
    assert isinstance(result.exception, SystemExit)
    assert _order_calls(us_fake, "ust31490") == []


def test_us_modify_rejects_cond_price(runner, us_fake):
    result = runner.invoke(cli, ["order", "modify", "000000123", "NVDA", "5", "215.5", "--cond-price", "500", "--confirm"])
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20002") == []


# ============================================================
#  Task 7: US stock info/price/orderbook/search
# ============================================================


@pytest.fixture
def us_stock_fake(monkeypatch, tmp_cache):
    fake = FakeKiwoomClient()
    fake.set_response("usa10098", {"return_code": 0, "list": [{"stex_tp": "ND", "stk_cd": "NVDA"}]})
    fake.set_response("usa10100", {"return_code": 0, "stk_cd": "NVDA", "stk_nm": "엔비디아", "mkgb": "NASDAQ"})
    fake.set_response("usa20100", {"return_code": 0, "stk_cd": "NVDA", "cur_prc": "+213.0400"})
    fake.set_response("usa20101", {"return_code": 0, "stk_cd": "NVDA", "sel_1bid": "+213.0500"})
    fake.set_response("usa10099", {"return_code": 0, "list": [
        {"stk_cd": "NVDA", "stk_nm": "엔비디아", "stk_enm": "NVIDIA Corp", "stex_tp": "ND"},
        {"stk_cd": "AAPL", "stk_nm": "애플", "stk_enm": "Apple Inc", "stex_tp": "ND"},
    ]})
    monkeypatch.setattr("kiwoom_cli.commands.stock.KiwoomClient", lambda *a, **k: fake)
    monkeypatch.setattr("kiwoom_cli.commands.us.stock_ops.KiwoomClient", lambda *a, **k: fake)
    return fake


def test_us_stock_info_dispatch(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "info", "NVDA"])
    assert result.exit_code == 0
    assert ("usa10100", {"stk_cd": "NVDA"}) in us_stock_fake.calls


def test_us_stock_price_resolves_exchange(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "price", "NVDA"])
    assert result.exit_code == 0
    assert ("usa20100", {"stex_tp": "ND", "stk_cd": "NVDA"}) in us_stock_fake.calls


def test_us_stock_orderbook(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "orderbook", "NVDA", "--exchange", "nasdaq"])
    assert result.exit_code == 0
    assert ("usa20101", {"stex_tp": "ND", "stk_cd": "NVDA"}) in us_stock_fake.calls


def test_kr_stock_info_unchanged(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "info", "005930"])
    assert result.exit_code == 0
    assert us_stock_fake.calls[0][0] == "ka10001"


def test_us_stock_search_filters_keyword(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "search", "apple", "--market", "us"])
    assert result.exit_code == 0
    assert ("usa10099", {"stex_tp": "%"}) in us_stock_fake.calls
    assert "AAPL" in result.output
    assert "NVDA" not in result.output


# ============================================================
#  Task 8: US charts
# ============================================================


def test_us_chart_day_dispatch(runner, us_stock_fake):
    us_stock_fake.set_response("usa06012", {"return_code": 0, "result_list": [
        {"dt": "20260714", "cur_prc": "213.0400", "open_pric": "210.0000",
         "high_pric": "214.0000", "low_pric": "209.5000", "acc_trde_qty": "1000"},
    ]})
    result = runner.invoke(
        cli, ["stock", "chart", "day", "NVDA", "--base-date", "20260714"]
    )
    assert result.exit_code == 0
    assert ("usa06012", {
        "stex_tp": "ND", "stk_cd": "NVDA", "strt_dt": "20260714",
        "upd_stkpc_tp": "0", "exrt_appl_tp": "0",
    }) in us_stock_fake.calls


def test_us_chart_tick_with_krw(runner, us_stock_fake):
    us_stock_fake.set_response("usa06010", {"return_code": 0, "result_list": []})
    result = runner.invoke(
        cli, ["stock", "chart", "tick", "NVDA", "--range", "5", "--krw"]
    )
    assert result.exit_code == 0
    assert ("usa06010", {
        "stex_tp": "ND", "stk_cd": "NVDA", "tic_scope": "5",
        "upd_stkpc_tp": "0", "exrt_appl_tp": "1",
    }) in us_stock_fake.calls


def test_us_chart_minute_sends_strt_dt(runner, us_stock_fake):
    us_stock_fake.set_response("usa06011", {"return_code": 0, "result_list": []})
    result = runner.invoke(
        cli, ["stock", "chart", "minute", "NVDA", "--interval", "5", "--base-date", "20260714"]
    )
    assert result.exit_code == 0
    body = [c for c in us_stock_fake.calls if c[0] == "usa06011"][0][1]
    assert body["strt_dt"] == "20260714" and body["tic_scope"] == "5"


def test_kr_chart_rejects_krw(runner, us_stock_fake):
    result = runner.invoke(
        cli, ["stock", "chart", "day", "005930", "--base-date", "20260714", "--krw"]
    )
    assert result.exit_code == 1


def test_kr_chart_day_unchanged(runner, us_stock_fake):
    result = runner.invoke(
        cli, ["stock", "chart", "day", "005930", "--base-date", "20260714"]
    )
    assert result.exit_code == 0
    assert us_stock_fake.calls[0] == ("ka10081", {
        "stk_cd": "005930", "base_dt": "20260714", "upd_stkpc_tp": "0",
    })
