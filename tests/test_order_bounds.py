"""주문/환전 수량·가격 경계값 가드 (Task 28-1/28-2/28-3).

이 파일의 모든 테스트는 **전송된 body**를 캡처해 단언한다. exit code만 보는
단언은 confirm 게이트·인증 실패 등 다른 이유로도 통과하므로 가드를 검증하지
못한다. 모든 거부 케이스는 `--confirm`을 붙여 confirm 게이트를 먼저 통과시킨
뒤 가드만 남긴다 — 그래야 "게이트가 막았다"와 "가드가 막았다"가 구분된다.

근거(키움 자체 배포 코드): kwcli 0.1.1 `maps/arguments.csv`가 주문 수량을
`quantity`(=`positive_int_string`, `<= 0` 거부), 취소 수량을
`cancel_quantity`(=`nonnegative_int_string`, 0 허용)로, 가격을
`price`(=`price_string`, `^\\d+$` — 음수/NaN/Inf 거부)로 선언한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.main import cli

KR = "kiwoom_cli.commands.order.KiwoomClient"
US = "kiwoom_cli.commands.us.order_ops.KiwoomClient"
EX = "kiwoom_cli.commands.us.exchange.KiwoomClient"


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """config/원장을 tmp로 격리 — 실제 ~/.kiwoom을 절대 건드리지 않는다."""
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


def _invoke(runner, args, target):
    """CLI 실행 + 전송된 (api_id, body) 목록 캡처."""
    sent: list[tuple[str, dict]] = []

    def capture(api_id, body=None, **kwargs):
        sent.append((api_id, body))
        return {"ord_no": "1", "return_code": 0, "cur_prc": "+70000"}, {}

    mc = MagicMock()
    mc.request = capture
    mc.__enter__ = lambda s: s
    mc.__exit__ = MagicMock(return_value=False)
    with patch(target) as cls:
        cls.return_value = mc
        result = runner.invoke(cli, args)
    return result, sent


def _err_code(result) -> str:
    return json.loads(result.stdout)["error"]["code"]


# ── Task 28-1: 환전 금액 하한 ────────────────────────────

def test_exchange_apply_rejects_negative_amount(runner):
    """음수 환전금액이 ust31302로 전송되던 결함 (fc_exmn_amt='-500000')."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "account", "exchange", "apply", "--confirm", "--", "-500000"],
        EX,
    )
    assert sent == [], f"환전 요청이 전송되었다: {sent}"
    assert result.exit_code == 1
    assert _err_code(result) == "INVALID_INPUT"


def test_exchange_apply_rejects_zero_amount(runner):
    result, sent = _invoke(
        runner, ["-f", "json", "account", "exchange", "apply", "--confirm", "0"], EX)
    assert sent == []
    assert result.exit_code == 1


def test_exchange_estimate_rejects_negative_amount(runner):
    result, sent = _invoke(
        runner,
        ["-f", "json", "account", "exchange", "estimate", "--", "-500000"], EX)
    assert sent == []
    assert result.exit_code == 1


def test_exchange_apply_still_accepts_positive_amount(runner):
    """대조군: 가드가 정상 금액까지 막지 않는지 — 하한이 과도하게 넓어지는 것을 잡는다."""
    result, sent = _invoke(
        runner, ["-f", "json", "account", "exchange", "apply", "--confirm", "500000"], EX)
    assert result.exit_code == 0
    assert sent == [("ust31302", {"exch_tp": "1", "fc_exmn_amt": "500000"})]


# ── Task 28-2: 수량 하한 ─────────────────────────────────

def test_buy_rejects_zero_qty(runner):
    """qty=0이 ord_qty='0'으로 전송되던 결함. --confirm으로 게이트를 먼저 통과시켜
    거부가 confirm이 아니라 수량 가드에서 나왔음을 보장한다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "buy", "005930", "0", "--price", "70000", "--confirm"],
        KR,
    )
    assert sent == [], f"수량 0 주문이 전송되었다: {sent}"
    assert result.exit_code == 1
    assert _err_code(result) == "INVALID_INPUT"


def test_credit_buy_rejects_zero_qty(runner):
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "credit", "buy", "005930", "0",
         "--price", "70000", "--confirm"],
        KR,
    )
    assert sent == []
    assert result.exit_code == 1


def test_gold_buy_rejects_zero_qty(runner):
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "gold", "buy", "M04020000", "0",
         "--price", "100000", "--type", "limit", "--confirm"],
        KR,
    )
    assert sent == []
    assert result.exit_code == 1


def test_modify_rejects_zero_qty(runner):
    """국내 정정 수량 0 — kwcli는 mdfy_qty를 `quantity`(양수)로 선언한다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "modify", "0000139", "005930", "0", "70000", "--confirm"],
        KR,
    )
    assert sent == []
    assert result.exit_code == 1


def test_cancel_rejects_negative_qty(runner):
    """`--qty -5`는 실제로 도달 가능한 경로다 (위치인자와 달리 Click이 옵션 값으로
    받는다). 이전에는 cncl_qty='-5'가 그대로 전송됐다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "cancel", "0000140", "005930", "--qty", "-5", "--confirm"],
        KR,
    )
    assert sent == [], f"음수 취소수량이 전송되었다: {sent}"
    assert result.exit_code == 1
    assert _err_code(result) == "INVALID_INPUT"


def test_cancel_zero_qty_still_means_full_cancel(runner):
    """문서화된 계약: `--qty 0`(기본값) = 전량취소. 수량 가드가 취소 경로까지
    양수 강제로 넓어지면 이 테스트가 깨진다."""
    result, sent = _invoke(
        runner, ["-f", "json", "order", "cancel", "0000140", "005930", "--confirm"], KR)
    assert result.exit_code == 0
    assert sent == [("kt10003", {
        "dmst_stex_tp": "KRX", "orig_ord_no": "0000140",
        "stk_cd": "005930", "cncl_qty": "0",
    })]


def test_gold_cancel_zero_qty_still_means_full_cancel(runner):
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "gold", "cancel", "0000140", "M04020000", "--confirm"], KR)
    assert result.exit_code == 0
    assert sent[0][1]["cncl_qty"] == "0"


# ── Task 28-2: 가격 하한 / 유한성 ────────────────────────

def test_domestic_negative_price_rejected(runner):
    """이전에는 ord_uv='-70000'이 그대로 전송됐다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "buy", "005930", "10", "--price", "-70000", "--confirm"],
        KR,
    )
    assert sent == [], f"음수 가격이 전송되었다: {sent}"
    assert result.exit_code == 1
    assert _err_code(result) == "INVALID_INPUT"


def test_domestic_nan_price_yields_envelope_not_traceback(runner):
    """이전에는 int(float('nan'))이 ValueError를 던져 envelope 없이 죽었다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "buy", "005930", "10", "--price", "nan", "--confirm"],
        KR,
    )
    assert sent == []
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"처리되지 않은 예외: {result.exception!r}")
    assert _err_code(result) == "INVALID_INPUT"


def test_domestic_inf_price_yields_envelope_not_traceback(runner):
    """nan의 형제 결함: int(float('inf'))는 OverflowError를 던졌다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "buy", "005930", "10", "--price", "inf", "--confirm"],
        KR,
    )
    assert sent == []
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"처리되지 않은 예외: {result.exception!r}")
    assert _err_code(result) == "INVALID_INPUT"


def test_us_nan_price_not_transmitted(runner):
    """fmt_us_price는 nan을 truthy로 보아 ord_uv='nan'을 전송했다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "buy", "NVDA", "10", "--price", "nan",
         "--type", "limit", "--exchange", "nasdaq", "--confirm"],
        US,
    )
    assert sent == [], f"NaN 가격이 전송되었다: {sent}"
    assert result.exit_code == 1
    assert _err_code(result) == "INVALID_INPUT"


def test_us_negative_price_rejected(runner):
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "buy", "NVDA", "10", "--price", "-5",
         "--type", "limit", "--exchange", "nasdaq", "--confirm"],
        US,
    )
    assert sent == []
    assert result.exit_code == 1


def test_market_order_zero_price_still_allowed(runner):
    """대조군: price=0은 시장가 센티널이다. 가격 가드가 `> 0`으로 넓어지면
    시장가 주문 전체가 막히므로 이 테스트가 깨진다."""
    result, sent = _invoke(
        runner, ["-f", "json", "order", "buy", "005930", "10", "--confirm"], KR)
    assert result.exit_code == 0
    assert sent[0][1]["ord_uv"] == ""
    assert sent[0][1]["trde_tp"] == "3"  # market


# ── Task 28-3: 미국 정정 ─────────────────────────────────

def test_us_modify_rejects_nonzero_qty(runner):
    """ust20002 요청 스펙에는 수량 필드가 아예 없다(mdfy_ord_qty는 응답 필드).
    이전에는 사용자가 준 수량이 조용히 버려지고 stderr 경고만 나갔다 —
    json 소비자는 그 경고를 볼 수 없다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "modify", "000000123", "NVDA", "5", "210",
         "--exchange", "nasdaq", "--confirm"],
        US,
    )
    assert sent == [], f"버려질 수량과 함께 정정이 전송되었다: {sent}"
    assert result.exit_code == 1
    assert _err_code(result) == "INVALID_INPUT"


def test_us_modify_zero_qty_sends_price_only(runner):
    """대조군: qty=0(수량 미지정)은 계속 동작하고, body에 수량 필드가 없어야 한다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "modify", "000000123", "NVDA", "0", "210",
         "--exchange", "nasdaq", "--confirm"],
        US,
    )
    assert result.exit_code == 0
    assert sent == [("ust20002", {
        "orig_ord_no": "000000123", "stex_tp": "ND",
        "stk_cd": "NVDA", "mdfy_uv": "210",
    })]


def test_us_modify_rejects_zero_price(runner):
    """이전에는 mdfy_uv=''(시장가 인코딩)로 전송됐다 — 정정에 시장가는 없다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "modify", "000000123", "NVDA", "0", "0",
         "--exchange", "nasdaq", "--confirm"],
        US,
    )
    assert sent == [], f"가격 0 정정이 전송되었다: {sent}"
    assert result.exit_code == 1
    assert _err_code(result) == "INVALID_INPUT"


def test_us_modify_rejects_negative_price(runner):
    """이전에는 mdfy_uv='-5'가 전송됐다."""
    result, sent = _invoke(
        runner,
        ["-f", "json", "order", "modify", "000000123", "NVDA", "0",
         "--exchange", "nasdaq", "--confirm", "--", "-5"],
        US,
    )
    assert sent == []
    assert result.exit_code == 1


# ════════════════════════════════════════════════════════
#  D5b — order validate가 실주문 경로와 같은 하한을 쓰는가
# ════════════════════════════════════════════════════════
#
# validate는 실주문이 무엇을 할지 예측하는 read-only 프리플라이트다. D5가 주문
# 경로에 하한을 넣으면서 둘이 어긋났다 — validate는 qty=0/음수 가격에 대해
# valid: true를 보고하는데 실주문은 거부한다. 프리플라이트를 믿은 에이전트가
# 자금 이동 직전에 거부당한다.
#
# 실패는 기존 계약대로 나타나야 한다: 해당 check가 false → VALIDATION_FAILED
# → exit 1. 새 오류 코드를 만들거나 fail_input으로 빠지지 않는다.

_KST = timezone(timedelta(hours=9))


@pytest.fixture
def validate_env(monkeypatch):
    """validate의 qty/price 외 모든 체크를 통과시킨다 — 그래야 실패가
    qty/price 때문임이 확정된다 (market_open은 시계 휴리스틱이라 고정 필수)."""
    monkeypatch.setattr(
        "kiwoom_cli.commands.order._now_kst",
        lambda: datetime(2020, 1, 6, 10, 0, tzinfo=_KST),  # 월요일 10:00 장중
    )


def _validate(runner, args):
    """validate 실행 → (exit_code, doc). 요청은 전부 read-only(ka10001/kt00001/kt00004)."""
    def capture(api_id, body=None, **kwargs):
        return {
            "stk_nm": "삼성전자", "cur_prc": "+70000",
            "ord_alow_amt": "999999999999",
            "stk_acnt_evlt_prst": [{"stk_cd": "A005930", "rmnd_qty": "1000"}],
            "return_code": 0,
        }, {}

    mc = MagicMock()
    mc.request = capture
    mc.__enter__ = lambda s: s
    mc.__exit__ = MagicMock(return_value=False)
    with patch(KR) as cls:
        cls.return_value = mc
        result = runner.invoke(cli, args)
    return result


def test_validate_rejects_zero_qty(runner, validate_env):
    """이전에는 qty=0에 valid: true + 전체 체크 통과를 보고했다."""
    result = _validate(runner, ["-f", "json", "order", "validate", "buy",
                                "005930", "0", "--price", "70000"])
    doc = json.loads(result.stdout)
    # exit code와 payload를 함께 단언한다 — exit 1만 보면 VALIDATION_FAILED와
    # 입력 파싱 오류를 구분할 수 없다.
    assert result.exit_code == 1
    assert doc["error"]["code"] == "VALIDATION_FAILED"
    assert doc["data"]["valid"] is False
    assert doc["data"]["checks"]["qty_ok"] is False
    assert doc["error"]["details"] == {"qty_ok": False}


def test_validate_sell_rejects_zero_qty(runner, validate_env):
    """매도 경로도 같다 — held >= 0이 공허하게 참이 되어 통과하던 자리."""
    result = _validate(runner, ["-f", "json", "order", "validate", "sell",
                                "005930", "0", "--price", "70000"])
    doc = json.loads(result.stdout)
    assert result.exit_code == 1
    assert doc["error"]["code"] == "VALIDATION_FAILED"
    assert doc["data"]["checks"]["qty_ok"] is False


def test_validate_rejects_negative_price(runner, validate_env):
    """이전에는 price=-70000에 valid: true를 보고했다."""
    result = _validate(runner, ["-f", "json", "order", "validate", "buy",
                                "005930", "10", "--price", "-70000"])
    doc = json.loads(result.stdout)
    assert result.exit_code == 1
    assert doc["error"]["code"] == "VALIDATION_FAILED"
    assert doc["data"]["checks"]["price_ok"] is False
    assert doc["data"]["checks"]["qty_ok"] is True   # qty는 멀쩡하다


@pytest.mark.parametrize("bad", ["nan", "inf"])
def test_validate_nonfinite_price_is_envelope_not_traceback(runner, validate_env, bad):
    """이전에는 `price == int(price)`가 ValueError/OverflowError를 던져 stdout이
    비었다 — envelope-항상 계약 위반. 실주문 경로는 이미 envelope를 냈으므로
    프리플라이트만 더 나쁜 상태였다."""
    result = _validate(runner, ["-f", "json", "order", "validate", "buy",
                                "005930", "10", "--price", bad])
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"처리되지 않은 예외: {result.exception!r}")
    doc = json.loads(result.stdout)
    assert result.exit_code == 1
    assert doc["error"]["code"] == "VALIDATION_FAILED"
    assert doc["data"]["checks"]["price_ok"] is False


def test_validate_still_passes_good_input(runner, validate_env):
    """대조군: 가드가 정상 입력까지 막지 않는지 + payload 형태가 그대로인지."""
    result = _validate(runner, ["-f", "json", "order", "validate", "buy",
                                "005930", "10", "--price", "70000"])
    doc = json.loads(result.stdout)
    assert result.exit_code == 0
    assert doc["data"]["valid"] is True
    assert doc["data"]["checks"] == {
        "symbol_ok": True, "market_open": True, "sufficient_balance": True,
        "qty_ok": True, "price_ok": True, "price_known": True,
    }
    assert doc["data"]["est_cost"] == 700000
    assert doc["data"]["heuristic"] is True


def test_validate_market_order_zero_price_still_allowed(runner, validate_env):
    """대조군: price=0은 시장가 센티널 — validate도 계속 통과시켜야 한다."""
    result = _validate(runner, ["-f", "json", "order", "validate", "buy",
                                "005930", "10"])
    doc = json.loads(result.stdout)
    assert result.exit_code == 0
    assert doc["data"]["checks"]["price_ok"] is True
    assert doc["data"]["checks"]["qty_ok"] is True


# ── 드리프트 방지: validate와 실주문이 같은 입력에 같은 판정을 내는가 ──

_AGREEMENT_GRID = [
    ("0", "70000"),        # qty 0
    ("-5", "70000"),       # qty 음수 (--qty 형태가 아니라 위치인자라 Click이 먼저 막을 수 있다)
    ("1", "70000"),        # 정상
    ("10", "70000"),       # 정상
    ("10", "0"),           # 시장가 센티널
    ("10", "-70000"),      # 음수 가격
    ("10", "nan"),         # 비유한
    ("10", "inf"),         # 비유한
    ("10", "70000.5"),     # 국내 정수 위반
    ("10", "1"),           # 하한 경계
]


@pytest.mark.parametrize("qty,price", _AGREEMENT_GRID)
def test_validate_agrees_with_order_path(runner, validate_env, qty, price):
    """프리플라이트와 실주문이 **같은 입력에 같은 판정**을 내야 한다.

    한쪽 임계값만 바뀌면(=상수를 두 벌 두면) 이 테스트가 깨진다. 실주문 쪽은
    exit code가 아니라 **body가 실제로 전송됐는지**로 판정한다 — confirm 게이트나
    인증 실패로 인한 exit 1을 '거부'로 오독하지 않기 위함이다.
    """
    order_result, sent = _invoke(
        runner,
        ["-f", "json", "order", "buy", "005930", qty, "--price", price, "--confirm"],
        KR,
    )
    order_accepts = bool(sent)

    v = _validate(runner, ["-f", "json", "order", "validate", "buy",
                           "005930", qty, "--price", price])
    try:
        validate_accepts = v.exit_code == 0 and json.loads(v.stdout)["data"]["valid"] is True
    except (json.JSONDecodeError, TypeError, KeyError):
        validate_accepts = False

    # 이 테스트가 고정하는 것은 **판정 일치**다. 판정을 어떤 형태로 전달하는지
    # (envelope냐 traceback이냐)는 test_validate_nonfinite_price_is_envelope_not_traceback가
    # 따로 잡는다 — 두 관심사를 한 단언에 섞으면 어느 쪽이 깨졌는지 알 수 없다.
    assert order_accepts == validate_accepts, (
        f"qty={qty} price={price}: 실주문 accepts={order_accepts} "
        f"(sent={sent}) 인데 validate accepts={validate_accepts} "
        f"(exit={v.exit_code}, stdout={v.stdout[:160]!r})"
    )
