"""Tests for US stock trading (kiwoom_cli/commands/us/)."""

from __future__ import annotations

import json

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
    US_MARKET_TYPES,
    US_ORDER_TYPES,
    US_SELL_ONLY_TYPES,
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


# test_us_market_types_reject_price (아래, Task 5 섹션)가 US_MARKET_TYPES의
# 각 멤버에 대해 실제 주문 명령을 실행해 --price 거부를 행동으로 검증한다 —
# 여기 있던 이전 버전(test_us_market_types_ignore_price)은 상수가 자기
# 리터럴과 같은지만 확인해 가드 유무와 무관하게 항상 통과했다(v2.9 audit
# finding 3, 위양성 위험 — 상수만 존재하면 가드가 실제로는 빠져 있어도 green).


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


def test_resolve_ignores_non_dict_cache_and_falls_back_to_api(tmp_cache):
    tmp_cache.write_text('["NVDA"]', encoding="utf-8")
    fake = _fake_with_10098([{"stex_tp": "ND", "stk_cd": "NVDA"}])
    assert detect.resolve_us_exchange(fake, "NVDA") == "ND"
    assert fake.calls == [("usa10098", {"stk_cd": "NVDA"})]


def test_resolve_ignores_invalid_cached_value(tmp_cache):
    tmp_cache.write_text('{"NVDA": "bogus"}', encoding="utf-8")
    fake = _fake_with_10098([{"stex_tp": "ND", "stk_cd": "NVDA"}])
    assert detect.resolve_us_exchange(fake, "NVDA") == "ND"
    assert fake.calls == [("usa10098", {"stk_cd": "NVDA"})]


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


# ── v2.9 task 7: US 시장가 계열(moc/vwap/twap/stop)도 --price를 거부한다
# (ust20000/ust20001 스펙: "그 외 시장가 거래유형 설정 시 입력 값은 빈 값 처리") ──


@pytest.mark.parametrize("otype,extra_args", [
    ("moc", []),
    ("stop", ["--stop", "199.99"]),
])
def test_us_sell_market_family_rejects_price(runner, us_fake, otype, extra_args):
    """매도전용 시장가 계열(moc/stop)은 --price와 함께 쓰면 exit 1.

    moc에는 --stop을 주지 않는다 — --stop은 stop/stop-limit 전용이라 moc과
    같이 쓰면 (이번에 고치는 가격 가드가 아니라) 그 검사가 먼저 걸려 exit 1의
    원인이 뒤바뀐다."""
    result = runner.invoke(
        cli,
        ["order", "sell", "NVDA", "5", "--type", otype, *extra_args,
         "--price", "200", "--confirm"],
    )
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20001") == []


@pytest.mark.parametrize("otype", ["vwap", "twap"])
def test_us_buy_market_family_rejects_price(runner, us_fake, otype):
    """매수/매도 공통 시장가 계열(vwap/twap)은 --price와 함께 쓰면 exit 1."""
    result = runner.invoke(
        cli, ["order", "buy", "NVDA", "10", "--type", otype, "--price", "200", "--confirm"]
    )
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20000") == []


def test_us_sell_stop_limit_still_accepts_price(runner, us_fake):
    """stop-limit(34)은 시장가 계열이 아니다 — 트리거 후 지정가로 체결되므로
    --price(정정지정가)를 계속 받아야 한다 (market-family 확장이 이름이 비슷한
    이 유형까지 잘못 삼키지 않는지 확인, 기존 test_us_sell_stop_limit_body와
    동일한 의도를 명시적으로 재확인)."""
    result = runner.invoke(
        cli,
        ["order", "sell", "NVDA", "5", "--type", "stop-limit",
         "--price", "200.5", "--stop", "199.99", "--confirm"],
    )
    assert result.exit_code == 0
    body = _order_calls(us_fake, "ust20001")[0][1]
    assert body["trde_tp"] == "34"
    assert body["ord_uv"] == "200.5"


@pytest.mark.parametrize("otype", sorted(US_MARKET_TYPES))
def test_us_market_types_reject_price(runner, us_fake, otype):
    """US_MARKET_TYPES의 모든 멤버가 --price와 함께 쓰이면 실제로 거부되는지
    행동으로 검증한다 (v2.9 audit finding 3 — 이전에는 상수가 자기 리터럴과
    같은지만 확인해 가드 유무와 무관하게 항상 통과하는 테스트가 있었다).

    moc/stop은 매도 전용(US_SELL_ONLY_TYPES)이라 side=sell로 보낸다. stop은
    --stop 트리거 가격도 함께 줘야 한다 — 안 그러면 (이번에 검증하려는 가격
    가드가 아니라) '--stop 필요' 가드가 먼저 걸려 exit 1의 원인이 뒤바뀐다
    (test_us_sell_market_family_rejects_price와 동일한 주의사항)."""
    side = "sell" if otype in US_SELL_ONLY_TYPES else "buy"
    args = ["order", side, "NVDA", "5", "--type", otype, "--price", "200", "--confirm"]
    if otype in US_STOP_TYPES:
        args += ["--stop", "199.99"]
    result = runner.invoke(cli, args)
    assert result.exit_code == 1
    api_id = "ust20001" if side == "sell" else "ust20000"
    assert _order_calls(us_fake, api_id) == []


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
#  v2.9 audit fix: US dry-run est_cost must use real quote (cur_prc)
# ============================================================


def test_us_market_dry_run_uses_real_quote(runner, us_fake):
    """US 시장가 dry-run의 est_cost는 usa20100의 cur_prc에서 계산된다 (now_pric 아님).

    usa20100 스펙 응답 예시: "cur_prc": "+201.4700". 필드명이 틀리면 quote lookup이
    항상 미스해 est_cost가 조용히 0으로 렌더링된다 — dry-run의 목적(주문 전 안전
    점검)을 정확히 무력화하는 버그.
    """
    us_fake.set_response(
        "usa20100", {"return_code": 0, "stk_cd": "NVDA", "cur_prc": "+201.4700"}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "NVDA", "10", "--type", "market", "--dry-run"],
    )
    assert result.exit_code == 0
    doc = json.loads(result.output)
    payload = doc["data"]
    assert payload["price"] == pytest.approx(201.47)
    assert payload["est_cost"] == pytest.approx(2014.70)
    assert payload["price_source"] == "market_quote"
    assert _order_calls(us_fake, "ust20000") == []  # dry-run이므로 실제 주문 미전송


def test_us_market_dry_run_unparseable_quote_fails_loudly(runner, us_fake):
    """cur_prc가 파싱 불가능하면 est_cost=0 + price_source='market_quote'인 거짓
    미리보기 대신 QUOTE_UNAVAILABLE(exit 2)로 실패해야 한다 (KR과 동일한 계약).

    스펙상 cur_prc는 항상 포매팅된 숫자 문자열이지만, 업스트림이 예상 밖의 값을
    주는 경우까지 대비한다 — dry-run이 "실제 시세로 계산했다"고 주장하면서
    가격 0을 보여주는 것이 최악의 결과다.
    """
    us_fake.set_response(
        "usa20100", {"return_code": 0, "stk_cd": "NVDA", "cur_prc": "N/A"}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "NVDA", "10", "--type", "market", "--dry-run"],
    )
    assert result.exit_code == 2
    doc = json.loads(result.output)
    assert doc["error"]["code"] == "QUOTE_UNAVAILABLE"
    assert doc["data"] is None
    assert _order_calls(us_fake, "ust20000") == []


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
    """--exchange 없이도 자동판별된 stex_tp가 채워진다 (usa10100은 stex_tp 필수)."""
    result = runner.invoke(cli, ["stock", "info", "NVDA"])
    assert result.exit_code == 0
    assert ("usa10100", {"stk_cd": "NVDA", "stex_tp": "ND"}) in us_stock_fake.calls


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


def test_us_stock_search_empty_result_emits_json_envelope(runner, us_stock_fake):
    """검색 결과가 없을 때도 -f json은 파싱 가능한 envelope을 출력해야 한다.

    기존에는 err_console.print + return으로 끝나 stdout이 완전히 비었다
    (exit 0인데 파싱할 게 없는, 계약 위반 중 가장 나쁜 케이스).
    """
    result = runner.invoke(
        cli, ["-f", "json", "stock", "search", "존재하지않는티커", "--market", "us"]
    )

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["ok"] is True
    assert doc["data"]["items"] == []


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
