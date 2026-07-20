"""Tests for order commands (kiwoom_cli/commands/order.py).

Strict coverage for all 23 order commands. Tests validate:
- Correct API ID per command
- API body field mapping (qty, price, type, exchange, etc.)
- --confirm flag behavior (prompt gating)
- ORDER_TYPES translation
- Error propagation
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from click.testing import CliRunner

from kiwoom_cli.client import KiwoomAPIError
from kiwoom_cli.commands.order import _MARKET_TYPES, KST
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject FakeKiwoomClient into order module."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.order.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


@pytest.fixture
def fake_everywhere(fake_client, monkeypatch):
    """Inject the same fake into stock/account modules (litmus loop 용)."""
    for mod in ("stock", "account"):
        monkeypatch.setattr(
            f"kiwoom_cli.commands.{mod}.KiwoomClient",
            lambda *args, **kwargs: fake_client,
        )
    return fake_client


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    """config/멱등성 원장을 tmp로 격리 (실제 ~/.kiwoom 오염 방지)."""
    monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr("kiwoom_cli.config.CONFIG_DIR", tmp_path)
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


@pytest.fixture
def market_open(monkeypatch):
    """validate의 market_open 휴리스틱을 '장중'으로 고정 (월요일 10:00 KST)."""
    monkeypatch.setattr(
        "kiwoom_cli.commands.order._now_kst",
        lambda: datetime(2020, 1, 6, 10, 0, tzinfo=KST),
    )


def _doc(result):
    """stdout은 단일 envelope 문서여야 한다."""
    doc = json.loads(result.stdout)
    assert doc["schema"] == "v1"
    return doc


# ============================================================
#  Stock Orders (kt10000 ~ kt10003)
# ============================================================


def test_buy_with_confirm_sends_correct_body(runner, fake_client):
    """--confirm skips prompt and sends full body to kt10000."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--price", "70000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt10000",
            {
                "dmst_stex_tp": "KRX",
                "stk_cd": "005930",
                "ord_qty": "10",
                "ord_uv": "70000",
                "trde_tp": "0",
                "cond_uv": "",
            },
        )
    ]


def test_buy_without_confirm_answering_no_aborts(runner, fake_client):
    """Without --confirm, answering 'n' aborts without sending request."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market"],
        input="n\n",
    )

    assert result.exit_code != 0
    assert fake_client.calls == []


def test_buy_without_confirm_answering_yes_sends_request(runner, fake_client):
    """Without --confirm, answering 'y' sends request."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0][0] == "kt10000"


def test_buy_market_order_omits_price(runner, fake_client):
    """Market order (no --price) sends empty string for ord_uv, not '0'."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["ord_uv"] == ""
    assert body["trde_tp"] == "3"  # market = "3"


def test_sell_sends_to_kt10001(runner, fake_client):
    """Sell command hits kt10001 with correct body."""
    result = runner.invoke(
        cli,
        ["order", "sell", "005930", "5", "--price", "72000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "kt10001"
    assert body["stk_cd"] == "005930"
    assert body["ord_qty"] == "5"
    assert body["ord_uv"] == "72000"


def test_modify_sends_to_kt10002_with_mdfy_fields(runner, fake_client):
    """Modify command hits kt10002 with mdfy_qty/mdfy_uv fields."""
    result = runner.invoke(
        cli,
        ["order", "modify", "0000139", "005930", "1", "70000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt10002",
            {
                "dmst_stex_tp": "KRX",
                "orig_ord_no": "0000139",
                "stk_cd": "005930",
                "mdfy_qty": "1",
                "mdfy_uv": "70000",
                "mdfy_cond_uv": "",
            },
        )
    ]


def test_cancel_sends_to_kt10003_with_cncl_qty(runner, fake_client):
    """Cancel command hits kt10003 with cncl_qty."""
    result = runner.invoke(
        cli,
        ["order", "cancel", "0000140", "005930", "--qty", "5", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt10003",
            {
                "dmst_stex_tp": "KRX",
                "orig_ord_no": "0000140",
                "stk_cd": "005930",
                "cncl_qty": "5",
            },
        )
    ]


def test_cancel_full_qty_defaults_to_zero(runner, fake_client):
    """Cancel without --qty sends cncl_qty='0' (full cancel)."""
    result = runner.invoke(
        cli,
        ["order", "cancel", "0000140", "005930", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["cncl_qty"] == "0"


# ============================================================
#  Exchange option propagation
# ============================================================


def test_buy_with_nxt_exchange(runner, fake_client):
    """--exchange NXT propagates to dmst_stex_tp."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market", "--exchange", "NXT", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dmst_stex_tp"] == "NXT"


# ============================================================
#  Credit Orders (kt10006 ~ kt10009)
# ============================================================


def test_credit_buy_sends_to_kt10006(runner, fake_client):
    """Credit buy hits kt10006 with body identical to stock buy."""
    result = runner.invoke(
        cli,
        ["order", "credit", "buy", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "kt10006"
    assert body["trde_tp"] == "3"
    assert body["stk_cd"] == "005930"


def test_credit_sell_sends_to_kt10007(runner, fake_client):
    """Credit sell hits kt10007."""
    result = runner.invoke(
        cli,
        ["order", "credit", "sell", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt10007"


def test_credit_modify_sends_to_kt10008(runner, fake_client):
    """Credit modify hits kt10008."""
    result = runner.invoke(
        cli,
        ["order", "credit", "modify", "0000139", "005930", "1", "70000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt10008"


def test_credit_cancel_sends_to_kt10009(runner, fake_client):
    """Credit cancel hits kt10009."""
    result = runner.invoke(
        cli,
        ["order", "credit", "cancel", "0000140", "005930", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt10009"


# ============================================================
#  Credit dry-run (kt10006/kt10007) — v2.9 audit fix 3: 신용주문도
#  _dry_run_kr을 공유하지만 이전에는 테스트 커버리지가 없었다.
# ============================================================


def test_credit_buy_dry_run_market_resolves_price_from_quote(runner, fake_client):
    """신용 매수 시장가 dry-run: ka10001 현재가로 예상비용 계산, 전송 없음."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "-70000", "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "credit", "buy", "005930", "10", "--dry-run"],
    )

    assert result.exit_code == 0
    assert [c[0] for c in fake_client.calls] == ["ka10001"]
    payload = _doc(result)["data"]
    assert payload["api_id"] == "kt10006"
    assert payload["price"] == 70000
    assert payload["price_source"] == "market_quote"
    assert payload["est_cost"] == 700000


def test_credit_sell_dry_run_unparseable_quote_fails_loudly(runner, fake_client):
    """신용 매도 dry-run도 시세 파싱 실패 시 QUOTE_UNAVAILABLE(exit 2)이어야 한다
    — kt10001/kt10000과 동일한 계약이 kt10007에도 적용되는지 확인."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "N/A", "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "credit", "sell", "005930", "10", "--dry-run"],
    )

    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["error"]["code"] == "QUOTE_UNAVAILABLE"
    assert [c[0] for c in fake_client.calls] == ["ka10001"]


# ============================================================
#  Gold Orders (kt50000 ~ kt50003)
# ============================================================


def test_gold_buy_sends_to_kt50000_without_cond_uv(runner, fake_client):
    """Gold buy hits kt50000 — note NO cond_uv field in body."""
    result = runner.invoke(
        cli,
        ["order", "gold", "buy", "M04020000", "1", "--price", "90000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt50000",
            {
                "stk_cd": "M04020000",
                "ord_qty": "1",
                "ord_uv": "90000",
                "trde_tp": "00",
            },
        )
    ]
    assert "cond_uv" not in fake_client.calls[0][1]


def test_gold_sell_sends_to_kt50001(runner, fake_client):
    """Gold sell hits kt50001."""
    result = runner.invoke(
        cli,
        ["order", "gold", "sell", "M04020000", "1", "--type", "limit", "--price", "90000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50001"


def test_gold_modify_sends_to_kt50002(runner, fake_client):
    """Gold modify hits kt50002."""
    result = runner.invoke(
        cli,
        ["order", "gold", "modify", "0000139", "M04020000", "1", "90000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50002"


def test_gold_cancel_sends_to_kt50003(runner, fake_client):
    """Gold cancel hits kt50003."""
    result = runner.invoke(
        cli,
        ["order", "gold", "cancel", "0000140", "M04020000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50003"


# ============================================================
#  Gold dry-run market-quote-resolution tests removed (Task 7b fix round 1):
#  gold has no market order (kt50000/kt50001 trde_tp accepts only 00/10/20,
#  all limit-style) so the price-from-ka50010-quote dry-run path they
#  exercised is a capability that must not exist. No-price safety is now
#  covered instead by test_gold_buy_missing_price_fails_cleanly and
#  test_gold_sell_no_type_no_price_fails_cleanly below.
# ============================================================


# ============================================================
#  Gold order-type restriction (Task 7b hotfix) — kt50000/kt50001's trde_tp
#  accepts exactly 3 values (00=보통, 10=보통IOC, 20=보통FOK), not the full
#  18-name domestic ORDER_TYPES. The pre-fix code sent ORDER_TYPES[order_type]
#  verbatim, so "limit" (the --price default) sent trde_tp="0" — a one-digit
#  code the gold API spec does not define at all.
# ============================================================


def test_gold_buy_limit_sends_trde_tp_00_not_0(runner, fake_client):
    """금현물 매수 limit은 trde_tp="00"을 보내야 한다 — 이전 버그는 "0"(한 자리,
    스펙에 없는 값)을 보냈다."""
    result = runner.invoke(
        cli,
        ["order", "gold", "buy", "M04020000", "1", "--price", "90000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt50000",
            {
                "stk_cd": "M04020000",
                "ord_qty": "1",
                "ord_uv": "90000",
                "trde_tp": "00",
            },
        )
    ]


def test_gold_buy_ioc_sends_trde_tp_10(runner, fake_client):
    result = runner.invoke(
        cli,
        ["order", "gold", "buy", "M04020000", "1", "--price", "90000", "--type", "ioc", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == "10"


def test_gold_buy_fok_sends_trde_tp_20(runner, fake_client):
    result = runner.invoke(
        cli,
        ["order", "gold", "buy", "M04020000", "1", "--price", "90000", "--type", "fok", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == "20"


def test_gold_sell_limit_sends_trde_tp_00_not_0(runner, fake_client):
    """금현물 매도 limit도 매수와 동일하게 trde_tp="00"이어야 한다."""
    result = runner.invoke(
        cli,
        ["order", "gold", "sell", "M04020000", "1", "--price", "90000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt50001",
            {
                "stk_cd": "M04020000",
                "ord_qty": "1",
                "ord_uv": "90000",
                "trde_tp": "00",
            },
        )
    ]


def test_gold_sell_ioc_sends_trde_tp_10(runner, fake_client):
    result = runner.invoke(
        cli,
        ["order", "gold", "sell", "M04020000", "1", "--price", "90000", "--type", "ioc", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == "10"


def test_gold_sell_fok_sends_trde_tp_20(runner, fake_client):
    result = runner.invoke(
        cli,
        ["order", "gold", "sell", "M04020000", "1", "--price", "90000", "--type", "fok", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == "20"


def test_gold_buy_rejects_market_type(runner, fake_client):
    """금현물은 시장가가 없다 — 국내주식에서는 유효한 "market"도 금현물에서는
    거부돼야 한다 (INVALID_INPUT, exit 1, 전송 없음)."""
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "gold", "buy", "M04020000", "1", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["error"]["code"] == "INVALID_INPUT"
    for allowed in ("limit", "ioc", "fok"):
        assert allowed in doc["error"]["message"]
    assert fake_client.calls == []


def test_gold_sell_rejects_conditional_type(runner, fake_client):
    """국내주식 18종 중 "conditional"(조건부지정가)도 금현물에서는 거부돼야 한다."""
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "gold", "sell", "M04020000", "1", "--price", "90000", "--type", "conditional", "--confirm"],
    )

    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["error"]["code"] == "INVALID_INPUT"
    assert fake_client.calls == []


def test_gold_buy_missing_price_fails_cleanly(runner, fake_client):
    """--type limit인데 --price를 생략하면 ord_uv=""로 조용히 전송하지 않고
    INVALID_INPUT으로 거부해야 한다 — 금현물은 전부 지정가 계열."""
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "gold", "buy", "M04020000", "1", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"
    assert fake_client.calls == []


def test_gold_sell_no_type_no_price_fails_cleanly(runner, fake_client):
    """--type과 --price를 둘 다 생략하면 공유 기본값 로직이 "market"으로
    해석하는데, 금현물엔 시장가가 없으므로 INVALID_INPUT이어야 한다."""
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "gold", "sell", "M04020000", "1", "--confirm"],
    )

    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"
    assert fake_client.calls == []


# ============================================================
#  Gold Queries (read-only, no --confirm)
# ============================================================


def test_gold_balance_sends_to_kt50020(runner, fake_client):
    """Gold balance query hits kt50020."""
    result = runner.invoke(cli, ["order", "gold", "balance"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50020"


def test_gold_deposit_sends_to_kt50021(runner, fake_client):
    """Gold deposit query hits kt50021."""
    result = runner.invoke(cli, ["order", "gold", "deposit"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50021"


def test_gold_executions_all_sends_to_kt50030(runner, fake_client):
    """Gold executions-all hits kt50030."""
    result = runner.invoke(cli, ["order", "gold", "executions-all"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50030"


def test_gold_executions_sends_to_kt50031(runner, fake_client):
    """Gold executions hits kt50031."""
    result = runner.invoke(cli, ["order", "gold", "executions"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50031"


def test_gold_history_sends_to_kt50032(runner, fake_client):
    """Gold history hits kt50032."""
    result = runner.invoke(cli, ["order", "gold", "history"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50032"


def test_gold_pending_sends_to_kt50075(runner, fake_client):
    """Gold pending hits kt50075."""
    result = runner.invoke(cli, ["order", "gold", "pending"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50075"


# ============================================================
#  Condition Search (ka10171 ~ ka10174)
# ============================================================


def test_condition_list_sends_trnm_cnsrlst(runner, fake_client):
    """condition list hits ka10171 with trnm=CNSRLST."""
    result = runner.invoke(cli, ["order", "condition", "list"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10171", {"trnm": "CNSRLST"})]


def test_condition_search_sends_search_type_0(runner, fake_client):
    """condition search hits ka10172 with search_type=0."""
    result = runner.invoke(
        cli,
        ["order", "condition", "search", "001", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10172",
            {
                "trnm": "CNSRREQ",
                "seq": "001",
                "search_type": "0",
                "stex_tp": "K",
            },
        )
    ]


def test_condition_realtime_sends_search_type_1(runner, fake_client):
    """condition realtime hits ka10173 with search_type=1."""
    result = runner.invoke(
        cli,
        ["order", "condition", "realtime", "001", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10173",
            {
                "trnm": "CNSRREQ",
                "seq": "001",
                "search_type": "1",
                "stex_tp": "K",
            },
        )
    ]


def test_condition_stop_sends_trnm_cnsrclr(runner, fake_client):
    """condition stop hits ka10174 with trnm=CNSRCLR."""
    result = runner.invoke(
        cli,
        ["order", "condition", "stop", "001", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("ka10174", {"trnm": "CNSRCLR", "seq": "001"})
    ]


# ============================================================
#  ORDER_TYPES translation (18 types parametrized)
# ============================================================


@pytest.mark.parametrize("type_name,api_code", [
    # kt10000 trde_tp. 기대값은 **리터럴**이다 — ORDER_TYPES에서 가져오면 안 된다.
    ("limit", "0"), ("market", "3"), ("conditional", "5"),
    ("after-hours", "81"), ("pre-market", "61"), ("single", "62"),
    ("best", "6"), ("first", "7"),
    ("ioc", "10"), ("market-ioc", "13"), ("best-ioc", "16"),
    ("fok", "20"), ("market-fok", "23"), ("best-fok", "26"),
    ("stop", "28"), ("mid", "29"), ("mid-ioc", "30"), ("mid-fok", "31"),
])
def test_order_type_translation(runner, fake_client, type_name, api_code):
    """18개 주문유형이 trde_tp로 정확히 번역되는지 — 값을 리터럴로 고정한다.

    예전에는 `parametrize(list(ORDER_TYPES.items()))`였다. 기대값을 검증 대상
    상수에서 가져오므로 상수를 어떻게 바꿔도 자기모순이 없어 항상 통과했다.
    실측: `ioc`("10")와 `fok`("20")를 맞바꿔도, `mid-ioc`/`mid-fok`를 맞바꿔도
    전체 1988개 스위트가 그대로 green이었다. 기본값 `limit`만 다른 테스트가
    우연히 지키고 있었다.

    IOC(체결 가능분만 체결 후 잔량 취소)와 FOK(전량 아니면 취소)는 실행 계약
    자체가 다르고, 맞바꿔도 둘 다 스펙상 유효한 코드라 서버가 정상 접수한다 —
    실주문 경로에서 조용히 다른 체결 방식으로 나가는 형태의 결함이다.

    시장가 계열(market/market-ioc/market-fok)은 --price와 함께 쓰면 모순으로
    거부되므로(Task 5), 이 파라미터들만 --price 없이 호출한다.
    """
    args = ["order", "buy", "005930", "10", "--type", type_name, "--confirm"]
    if type_name not in _MARKET_TYPES:
        args += ["--price", "70000"]
    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_code


# ============================================================
#  v2.9 task 7: 국내 최유리/최우선/중간가 계열도 시장가와 동일하게
#  --price를 거부한다 (kt10000 스펙에는 US ust20001처럼 "빈 값 처리" 문구가
#  없지만, 최유리/최우선/중간가는 체결가가 시스템이 정하는 호가로 자동
#  결정되는 유형이라 사용자가 넘긴 ord_uv는 조용히 버려진다 — 감사 발견
#  N2가 지적한 바로 그 실패 모드).
# ============================================================


@pytest.mark.parametrize("type_name", [
    "best", "best-ioc", "best-fok", "first", "mid", "mid-ioc", "mid-fok",
])
def test_market_family_kr_rejects_price(runner, fake_client, type_name):
    """국내 최유리/최우선/중간가 계열은 --price와 함께 쓰면 exit 1로 거부된다."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", type_name, "--price", "70000", "--confirm"],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_domestic_stop_type_still_accepts_price(runner, fake_client):
    """국내 스톱지정가(trde_tp=28)는 이름만 미국 stop(시장가)과 같을 뿐 별개
    개념(지정가 계열)이라 --price를 계속 받아야 한다 — market-family 확장이
    이름이 겹치는 이 유형까지 잘못 삼키지 않는지 확인."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "stop", "--price", "70000", "--confirm"],
    )

    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_tp"] == "28"
    assert body["ord_uv"] == "70000"


def test_credit_buy_rejects_market_family_price(runner, fake_client):
    """신용 매수(kt10006)도 buy/sell과 동일한 _resolve_order_type을 거치므로
    확장된 가드가 자동으로 전파된다 (감사가 지적한 '한 곳만 고치고 전파 안 됨'
    실패모드 재발 방지 확인)."""
    result = runner.invoke(
        cli,
        ["order", "credit", "buy", "005930", "10", "--type", "best", "--price", "70000", "--confirm"],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_gold_buy_rejects_market_family_price(runner, fake_client):
    """금현물 매수(kt50000)도 같은 공유 함수를 거치므로 가드가 전파된다."""
    result = runner.invoke(
        cli,
        ["order", "gold", "buy", "M04020000", "10", "--type", "mid", "--price", "90000", "--confirm"],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_price_without_type_still_infers_limit(runner, fake_client):
    """--price만 주고 --type을 생략하면 여전히 limit으로 추론된다 — market-family
    확장이 이 추론 분기에 영향을 주지 않는지 확인 (Related behavior 항목)."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--price", "70000", "--confirm"],
    )

    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["trde_tp"] == "0"      # limit
    assert body["ord_uv"] == "70000"


# ============================================================
#  Error propagation
# ============================================================


def test_api_error_returns_nonzero_exit(runner, monkeypatch):
    """KiwoomAPIError from request propagates to exit code 2."""

    class FailingClient(FakeKiwoomClient):
        def request(self, api_id, body=None, **kwargs):
            raise KiwoomAPIError(-1, "주문 실패")

    fake = FailingClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.order.KiwoomClient",
        lambda *args, **kwargs: fake,
    )

    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 2


# ============================================================
#  Confirmation contract (--yes alias, CONFIRMATION_REQUIRED)
# ============================================================


def test_json_without_confirm_emits_confirmation_required(runner, fake_client):
    """json 모드 + --confirm 없음 → 프롬프트 없이 CONFIRMATION_REQUIRED, exit 1, API 호출 0건."""
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10", "--type", "market"],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []
    doc = _doc(result)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert doc["error"]["retryable"] is False


def test_json_without_confirm_subgroups_also_gated(runner, fake_client):
    """credit/gold 하위그룹도 동일한 확인 계약을 따른다."""
    for args in (
        ["order", "credit", "buy", "005930", "10", "--type", "market"],
        ["order", "gold", "buy", "M04020000", "1", "--type", "limit", "--price", "90000"],
        ["order", "cancel", "0000140", "005930"],
    ):
        result = runner.invoke(cli, ["-f", "json", *args])
        assert result.exit_code == 1
        assert _doc(result)["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert fake_client.calls == []


def test_yes_is_alias_of_confirm(runner, fake_client):
    """--yes는 --confirm과 동일하게 프롬프트를 생략한다."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market", "--yes"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt10000"


# ============================================================
#  --dry-run
# ============================================================


def test_dry_run_limit_sends_nothing_and_body_matches_real_send(runner, fake_client):
    """지정가 dry-run: API 호출 0건, body는 실제 전송 시 body와 동일."""
    dry = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10",
         "--price", "70000", "--type", "limit", "--dry-run"],
    )

    assert dry.exit_code == 0
    assert fake_client.calls == []
    doc = _doc(dry)
    payload = doc["data"]
    assert payload["would_send"] is True
    assert payload["api_id"] == "kt10000"
    assert payload["side"] == "buy"
    assert payload["symbol"] == "005930"
    assert payload["qty"] == 10
    assert payload["price"] == 70000
    assert payload["est_cost"] == 700000
    assert payload["currency"] == "KRW"
    assert "price_source" not in payload

    real = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--price", "70000", "--type", "limit", "--confirm"],
    )
    assert real.exit_code == 0
    assert fake_client.calls == [("kt10000", payload["body"])]


def test_dry_run_market_resolves_price_from_quote(runner, fake_client):
    """시장가 dry-run: 현재가(ka10001)로 예상비용 계산, 주문 API는 호출하지 않음."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "-70000", "return_code": 0}
    )
    result = runner.invoke(
        cli,
        # --confirm과 함께 줘도 --dry-run이 우선한다
        ["-f", "json", "order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 0
    assert [c[0] for c in fake_client.calls] == ["ka10001"]
    payload = _doc(result)["data"]
    assert payload["price"] == 70000
    assert payload["price_source"] == "market_quote"
    assert payload["est_cost"] == 700000
    assert payload["body"]["ord_uv"] == ""  # 실제 전송 body는 시장가 그대로


def test_dry_run_market_unparseable_quote_fails_loudly(runner, fake_client):
    """cur_prc가 파싱 불가능한 값이면 est_cost=0을 price_source='market_quote'와
    함께 조용히 내보내지 않고 QUOTE_UNAVAILABLE(exit 2)로 실패해야 한다.

    현재가가 "N/A" 같은 값이면 이전에는 _strip_signed_int가 0으로 폴백해
    '실제 시세로 계산했다'는 거짓 주장(price_source=market_quote)과 함께
    est_cost=0인 미리보기를 보여줬다 — dry-run의 존재 목적을 무력화하는 버그.
    """
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "N/A", "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["error"]["code"] == "QUOTE_UNAVAILABLE"
    assert doc["data"] is None
    # 주문 API(kt10000)는 호출되지 않아야 한다 — 시세 조회(ka10001)만 있었어야 함.
    assert [c[0] for c in fake_client.calls] == ["ka10001"]


@pytest.mark.parametrize("cur_prc", ["0", "+0", "-0", "+00000000", "0.0000"])
def test_dry_run_market_zero_quote_fails_loudly(runner, fake_client, cur_prc):
    """cur_prc가 정확히 "0"(부호/자릿수 변형 포함)이어도 QUOTE_UNAVAILABLE이어야 한다.

    이 값은 원래 버그가 만들어내던 정확한 결과물이다 — "0"을 걸러내지 못하는
    수정은 이 버그 클래스를 하나도 못 잡는다. 실거래 종목에 가격 0은 없다
    (거래정지/상장전 등 "시세 없음"을 의미).
    """
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": cur_prc, "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["error"]["code"] == "QUOTE_UNAVAILABLE"
    assert doc["data"] is None
    assert [c[0] for c in fake_client.calls] == ["ka10001"]


@pytest.mark.parametrize("cur_prc", ["0.5", "+0.9", "0.0001"])
def test_dry_run_market_quote_truncating_to_zero_fails_loudly(runner, fake_client, cur_prc):
    """cur_prc가 (0, 1) 구간의 소수면 parse_quote_price는 통과하지만(f > 0),
    _quote_price_kr의 int() 절삭으로 price=0이 된다 — 이는 정확히 이 체인이
    막으려던 실패(price_source='market_quote' + est_cost=0)를 재현하므로
    QUOTE_UNAVAILABLE이어야 한다. KRX 정수 틱에서는 오늘 발생하지 않지만,
    parser와 preview 사이에 이를 막는 코드가 없었다(v2.9 audit finding 3)."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": cur_prc, "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["error"]["code"] == "QUOTE_UNAVAILABLE"
    assert doc["data"] is None
    assert [c[0] for c in fake_client.calls] == ["ka10001"]


def test_dry_run_market_quote_missing_key_fails_loudly(runner, fake_client):
    """응답에 cur_prc 키 자체가 없으면(None) QUOTE_UNAVAILABLE이어야 한다."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "return_code": 0}  # cur_prc 없음
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 2
    assert _doc(result)["error"]["code"] == "QUOTE_UNAVAILABLE"


def test_dry_run_market_quote_empty_string_fails_loudly(runner, fake_client):
    """cur_prc가 빈 문자열이면 QUOTE_UNAVAILABLE이어야 한다."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "", "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 2
    assert _doc(result)["error"]["code"] == "QUOTE_UNAVAILABLE"


def test_dry_run_market_quote_inf_fails_loudly_not_crash(runner, fake_client):
    """cur_prc가 "inf"여도 크래시 없이 QUOTE_UNAVAILABLE(exit 2)로 실패해야 한다."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "inf", "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 2
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert _doc(result)["error"]["code"] == "QUOTE_UNAVAILABLE"


def test_dry_run_market_unparseable_quote_table_mode(runner, fake_client):
    """table 모드에서도 QUOTE_UNAVAILABLE은 exit 2 + stderr 메시지로 실패해야 한다
    (fail_api의 table 분기 — 지금까지 json 모드만 커버됐었다)."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "N/A", "return_code": 0}
    )
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--dry-run", "--confirm"],
    )

    assert result.exit_code == 2
    assert "현재가 조회 결과를 해석할 수 없어" in result.output
    assert [c[0] for c in fake_client.calls] == ["ka10001"]


def test_dry_run_cancel_sends_nothing(runner, fake_client):
    """취소 dry-run: 호출 0건, est_cost 0."""
    result = runner.invoke(
        cli,
        ["-f", "json", "order", "cancel", "0000140", "005930", "--dry-run"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == []
    payload = _doc(result)["data"]
    assert payload["api_id"] == "kt10003"
    assert payload["side"] == "cancel"
    assert payload["est_cost"] == 0
    assert payload["body"]["cncl_qty"] == "0"


# ============================================================
#  Idempotency (--client-order-id)
# ============================================================


def test_idempotency_same_key_replays_without_sending(runner, fake_client, isolated_home):
    """같은 키 재실행 → 재전송 없이 같은 ord_no + idempotent_replay=true."""
    fake_client.set_response(
        "kt10000", {"return_code": 0, "ord_no": "0000777", "return_msg": "OK"}
    )
    args = ["-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit", "--confirm",
            "--client-order-id", "k1"]

    first = runner.invoke(cli, args)
    assert first.exit_code == 0
    assert len(fake_client.calls) == 1
    data1 = _doc(first)["data"]
    assert data1["order_no"] == "0000777"  # ord_no → order_no (정규화)
    assert "idempotent_replay" not in data1

    second = runner.invoke(cli, args)
    assert second.exit_code == 0
    assert len(fake_client.calls) == 1  # 전송 없음
    data2 = _doc(second)["data"]
    assert data2["idempotent_replay"] is True
    assert data2["order_no"] == data1["order_no"]

    ledger = isolated_home / "idempotency" / "default-mock.jsonl"
    assert ledger.exists()
    # in-flight 기록(전송 직전) + 완료 기록(전송 후) = 2줄. 재생(replay)은
    # 재전송하지 않으므로 두 번째 호출에서는 원장에 추가되지 않는다.
    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["status"] == "inflight"
    assert json.loads(lines[-1])["status"] == "done"
    assert json.loads(lines[-1])["ord_no"] == "0000777"


def test_idempotency_different_key_sends(runner, fake_client, isolated_home):
    """다른 키는 정상 전송된다."""
    base = ["-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit", "--confirm"]

    runner.invoke(cli, [*base, "--client-order-id", "k1"])
    result = runner.invoke(cli, [*base, "--client-order-id", "k2"])

    assert result.exit_code == 0
    assert len(fake_client.calls) == 2


# ============================================================
#  order validate (read-only preflight)
# ============================================================


def test_validate_buy_happy_path(runner, fake_client, market_open):
    """유효한 매수 사전점검: 주문 API 미호출, valid=true, exit 0."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "+70000", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "000001000000", "return_code": 0}
    )

    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10"])

    assert result.exit_code == 0
    assert [c[0] for c in fake_client.calls] == ["ka10001", "kt00001"]
    doc = _doc(result)
    assert doc["ok"] is True
    data = doc["data"]
    assert data["valid"] is True
    assert data["checks"] == {
        "symbol_ok": True, "market_open": True,
        "sufficient_balance": True, "qty_ok": True, "price_ok": True,
        "price_known": True,
    }
    assert data["est_cost"] == 700000
    assert data["heuristic"] is True


def test_validate_buy_insufficient_balance(runner, fake_client, market_open):
    """주문가능금액 부족 → VALIDATION_FAILED, 실패 체크가 details에 포함, exit 1."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "+70000", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "000000100000", "return_code": 0}  # 100,000 < 700,000
    )

    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10"])

    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "VALIDATION_FAILED"
    assert doc["error"]["details"] == {"sufficient_balance": False}
    assert doc["data"]["valid"] is False
    assert doc["data"]["checks"]["sufficient_balance"] is False


def test_validate_sell_checks_holdings(runner, fake_client, market_open):
    """매도 사전점검: 보유수량(kt00004 rmnd_qty)으로 판단."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "+70000", "return_code": 0}
    )
    fake_client.set_response(
        "kt00004",
        {"stk_acnt_evlt_prst": [{"stk_cd": "A005930", "rmnd_qty": "000000000005"}],
         "return_code": 0},
    )

    ok = runner.invoke(cli, ["-f", "json", "order", "validate", "sell", "005930", "5"])
    assert ok.exit_code == 0
    assert _doc(ok)["data"]["valid"] is True

    over = runner.invoke(cli, ["-f", "json", "order", "validate", "sell", "005930", "10"])
    assert over.exit_code == 1
    assert _doc(over)["error"]["details"] == {"sufficient_balance": False}


# ============================================================
#  order validate — 시세 조회 실패 (v2.9 audit fix 2)
# ============================================================


def test_validate_price_unavailable_is_not_valid(runner, fake_client, market_open):
    """--price 생략 + 현재가 파싱 실패 → price_known: false, valid: false,
    VALIDATION_FAILED(exit 1), est_cost: 0.

    이전 리뷰 리포트는 "symbol_ok가 false가 되어 이미 잡힌다"고 주장했지만
    틀렸다 — symbol_ok = bool(stk_nm or quote_price)이고 stk_nm만으로 참이
    된다. 아래 test_validate_symbol_ok_stays_true_when_price_unavailable가
    이를 직접 반증한다. price_known이 없으면 이 케이스는 valid: true로
    새 나간다.

    sufficient_balance도 price_known과 함께 false여야 한다(v2.9 audit finding 1)
    — est_cost가 신뢰할 수 없는 0이므로 "잔고 충분"을 주장할 근거가 없다.
    """
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "N/A", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "000001000000", "return_code": 0}
    )

    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10"])

    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["error"]["code"] == "VALIDATION_FAILED"
    assert doc["error"]["details"] == {"price_known": False, "sufficient_balance": False}
    data = doc["data"]
    assert data["valid"] is False
    assert data["checks"]["price_known"] is False
    assert data["checks"]["sufficient_balance"] is False
    assert data["est_cost"] == 0  # 가격을 확정하지 못했으므로 신뢰할 수 없는 0


def test_validate_buy_sufficient_balance_not_true_when_price_unknown_even_with_zero_balance(
    runner, fake_client, market_open
):
    """v2.9 audit finding 1 — price_known이 false면 est_cost가 0으로 붕괴해
    'ord_alow_amt >= 0'이 공허하게 참이 되므로, 잔고가 정확히 0인 계좌에서도
    sufficient_balance가 true로 보고됐다(리뷰가 ord_alow_amt: "0"으로 확인한
    probe). checks는 data에 실려 에이전트가 aggregate valid 없이 개별 필드만
    읽을 수 있으므로, sufficient_balance는 미수행 점검을 true로 주장해서는
    안 된다."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "N/A", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "0", "return_code": 0}
    )

    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10"])

    doc = _doc(result)
    assert doc["data"]["checks"]["price_known"] is False
    assert doc["data"]["checks"]["sufficient_balance"] is not True


def test_validate_symbol_ok_stays_true_when_price_unavailable(runner, fake_client, market_open):
    """종목명(stk_nm)이 있으면 현재가 파싱이 실패해도 symbol_ok는 true여야 한다
    — 이전 리뷰 리포트의 "symbol_ok가 false가 된다"는 근거가 틀렸음을 직접
    검증한다. 그럼에도 price_known이 false이므로 전체 valid는 false다.
    """
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "N/A", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "000001000000", "return_code": 0}
    )

    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10"])

    data = _doc(result)["data"]
    assert data["checks"]["symbol_ok"] is True
    assert data["checks"]["price_known"] is False
    assert data["valid"] is False


def test_validate_quote_inf_does_not_crash(runner, fake_client, market_open):
    """cur_prc가 "inf"여도 크래시(OverflowError traceback) 없이 구조화된
    VALIDATION_FAILED envelope로 응답해야 한다.

    수정 전에는 _strip_signed_int(quote.get("cur_prc"))가 int(float("inf"))에서
    OverflowError를 던졌고, main.py의 전역 핸들러(KiwoomAPIError/KiwoomAuthError/
    keyring.errors.KeyringError/httpx 계열/click.ClickException만 포착)가 이를
    잡지 못해 raw traceback + stdout 공백으로 이어졌다 — envelope-항상 계약 위반.
    """
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "inf", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "000001000000", "return_code": 0}
    )

    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10"])

    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["error"]["code"] == "VALIDATION_FAILED"
    assert doc["data"]["checks"]["price_known"] is False
    assert doc["data"]["est_cost"] == 0


def test_validate_explicit_price_overrides_unavailable_quote(runner, fake_client, market_open):
    """--price를 명시하면 현재가 조회가 실패해도 price_known은 true여야 한다
    (예상비용 계산에 조회된 시세가 필요 없으므로)."""
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "N/A", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "000001000000", "return_code": 0}
    )

    result = runner.invoke(
        cli, ["-f", "json", "order", "validate", "buy", "005930", "10", "--price", "70000"]
    )

    assert result.exit_code == 0
    doc = _doc(result)
    assert doc["data"]["valid"] is True
    assert doc["data"]["checks"]["price_known"] is True
    assert doc["data"]["est_cost"] == 700000


def test_validate_quote_truncating_to_zero_is_not_price_known(runner, fake_client, market_open):
    """cur_prc가 (0, 1) 구간의 소수(예: "0.5")면 parse_quote_price는 통과하지만
    validate의 est_price = int(quote_price) 절삭으로 0이 된다 — price_known을
    true로 주장하면 est_cost=0의 사전점검이 통과(valid: true)해버린다
    (v2.9 audit finding 3, dry-run과 동일한 절삭 취약점의 validate 경로).
    """
    fake_client.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "0.5", "return_code": 0}
    )
    fake_client.set_response(
        "kt00001", {"ord_alow_amt": "000001000000", "return_code": 0}
    )

    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10"])

    doc = _doc(result)
    assert doc["data"]["checks"]["price_known"] is False
    assert doc["data"]["est_cost"] == 0
    assert doc["data"]["valid"] is False


# ============================================================
#  Litmus loop — 전 단계를 stdout JSON 파싱만으로 구동
# ============================================================


def test_litmus_loop_json_driven(runner, fake_everywhere, isolated_home, market_open):
    """quote → validate → dry-run → buy(멱등키) → pending → balance.

    각 단계는 이전 단계의 stdout JSON만으로 구동되며, 사람 개입(프롬프트) 없이
    exit code로 성공을 판정한다 — 에이전트가 실제로 밟게 될 경로 그대로.
    """
    fake = fake_everywhere
    fake.set_response(
        "ka10001", {"stk_nm": "삼성전자", "cur_prc": "+70000", "return_code": 0}
    )
    fake.set_response("kt00001", {"ord_alow_amt": "000100000000", "return_code": 0})
    fake.set_response(
        "kt10000", {"return_code": 0, "ord_no": "0000777", "return_msg": "OK"}
    )

    # 1. 시세 조회 — 정규화된 타입 필드를 그대로 사용 (부호/문자열 파싱 불필요)
    r1 = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert r1.exit_code == 0
    quote = _doc(r1)["data"]
    price = quote["price"]
    assert price == 70000 and isinstance(price, int)
    assert quote["change_direction"] == "up"
    assert quote["raw"]["cur_prc"] == "+70000"

    # 2. 사전점검 (시세에서 얻은 가격 사용)
    r2 = runner.invoke(
        cli, ["-f", "json", "order", "validate", "buy", "005930", "10", "--price", str(price)]
    )
    assert r2.exit_code == 0
    v = _doc(r2)["data"]
    assert v["valid"] is True
    assert v["est_cost"] == price * 10

    # 3. dry-run (전송될 body 확보)
    r3 = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10",
         "--price", str(price), "--type", "limit", "--dry-run"],
    )
    assert r3.exit_code == 0
    dry = _doc(r3)["data"]
    assert dry["would_send"] is True

    # 4. 멱등키로 실제 매수 — dry-run이 예고한 body 그대로 전송됐는지 확인
    r4 = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10",
         "--price", str(price), "--type", "limit", "--confirm",
         "--client-order-id", "litmus-1"],
    )
    assert r4.exit_code == 0
    ord_no = _doc(r4)["data"]["order_no"]
    assert ("kt10000", dry["body"]) in fake.calls

    # 5. 미체결 조회 — 방금 주문번호가 보인다
    fake.set_response(
        "ka10075",
        {"oso": [{"ord_no": ord_no, "stk_cd": "005930", "ord_qty": "10"}],
         "return_code": 0},
    )
    r5 = runner.invoke(cli, ["-f", "json", "account", "orders", "pending", "--market", "kr"])
    assert r5.exit_code == 0
    pending = _doc(r5)["data"]["kr"]
    assert any(o["order_no"] == ord_no for o in pending["oso"])

    # 6. 잔고 조회
    fake.set_response(
        "kt00004",
        {"stk_acnt_evlt_prst": [{"stk_cd": "A005930", "rmnd_qty": "000000000010"}],
         "return_code": 0},
    )
    r6 = runner.invoke(cli, ["-f", "json", "account", "balance", "--market", "kr"])
    assert r6.exit_code == 0
    holdings = _doc(r6)["data"]["stk_acnt_evlt_prst"]
    assert holdings[0]["symbol"].removeprefix("A") == "005930"
    assert holdings[0]["qty"] == 10  # rmnd_qty "000000000010" → int

    # 재실행(같은 멱등키) → 재전송 없음
    calls_before = len(fake.calls)
    r7 = runner.invoke(
        cli,
        ["-f", "json", "order", "buy", "005930", "10",
         "--price", str(price), "--type", "limit", "--confirm",
         "--client-order-id", "litmus-1"],
    )
    assert r7.exit_code == 0
    assert _doc(r7)["data"]["idempotent_replay"] is True
    assert len(fake.calls) == calls_before


@pytest.mark.parametrize("side,api_id", [("buy", "kt10000"), ("sell", "kt10001")])
def test_prefixed_code_order_dry_run_strips_prefix(runner, fake_client, side, api_id):
    """주문 경로도 'A005930'을 국내로 보내고 접두사를 벗긴다.

    dry-run이라 전송은 없고 출력된 body만 본다 — 라우팅이 틀리면 미국
    주문 미리보기(ust2000x)가 나와 api_id가 달라진다.
    """
    result = runner.invoke(cli, [
        "-f", "json", "order", side, "A005930", "10",
        "--price", "70000", "--dry-run",
    ])
    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["data"]["api_id"] == api_id
    assert doc["data"]["body"]["stk_cd"] == "005930"
