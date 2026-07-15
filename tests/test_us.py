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
