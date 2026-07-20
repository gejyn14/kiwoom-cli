"""Order management commands.

Order commands prompt for confirmation by default (table mode). Use
--confirm/--yes to skip. In json/csv mode there is never a prompt: without
--confirm the command fails with CONFIRMATION_REQUIRED (exit 1) so
non-interactive/agent runs never hang.

buy/sell/modify/cancel (주식/신용/금현물/미국) 공통 지원:
  --dry-run           전송될 body를 구성만 하고 전송하지 않음 (--confirm보다 우선)
  --client-order-id   멱등성 키 — 같은 키+같은 내용 재실행 시 재전송 없이 이전 응답
                      반환, 같은 키+다른 내용이면 IDEMPOTENCY_CONFLICT(exit 1)

Subgroups:
  order buy/sell/modify/cancel     - Stock orders (kt10000-kt10003)
  order validate buy|sell          - Read-only preflight (주문 미전송)
  order credit buy/sell/modify/cancel - Credit orders (kt10006-kt10009)
  order gold buy/sell/modify/cancel/balance/deposit/executions/execution/history/pending
                                   - Gold orders & account (kt50000-kt50003, kt50020-kt50075)
  order condition list/search/realtime/stop - Condition search (ka10171-ka10174)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import click
from rich.panel import Panel

from .. import envelope
from ..client import KiwoomAPIError, KiwoomClient
from ..formatters import _get_format, fail_api, fail_input, human, print_generic_table
from ._constants import GOLD_ORDER_TYPES, HumanChoice
from ._mutation import (
    QuoteUnavailable,
    confirm_gate,
    dry_run_payload,
    finish_dry_run,
    parse_quote_price,
    is_valid_order_price,
    is_valid_order_qty,
    send_order,
    suppress_pagination,
    validate_order_price,
    validate_order_qty,
)
from .us import order_ops as us_order_ops
from .us._constants import US_ORDER_TYPES
from ..normalize import strip_kr_market_prefix
from .us.detect import is_us_symbol

ORDER_TYPES = {
    "limit": "0",         # 보통 (지정가)
    "market": "3",        # 시장가
    "conditional": "5",   # 조건부지정가
    "after-hours": "81",  # 장마감후시간외
    "pre-market": "61",   # 장시작전시간외
    "single": "62",       # 시간외단일가
    "best": "6",          # 최유리지정가
    "first": "7",         # 최우선지정가
    "ioc": "10",          # 보통(IOC)
    "market-ioc": "13",   # 시장가(IOC)
    "best-ioc": "16",     # 최유리(IOC)
    "fok": "20",          # 보통(FOK)
    "market-fok": "23",   # 시장가(FOK)
    "best-fok": "26",     # 최유리(FOK)
    "stop": "28",         # 스톱지정가
    "mid": "29",          # 중간가
    "mid-ioc": "30",      # 중간가(IOC)
    "mid-fok": "31",      # 중간가(FOK)
}


# 국내+미국 주문유형 CLI 이름 합집합 (경로별로 재검증)
ALL_ORDER_TYPES = sorted(set(ORDER_TYPES) | set(US_ORDER_TYPES))
ORDER_EXCHANGES = ["KRX", "NXT", "SOR", "nasdaq", "nyse", "amex"]


def _is_kr_integer_price(price: float) -> bool:
    """국내 주문 가격은 정수(원)인가 — 이 규칙의 **유일한 정의**.

    실주문(`_kr_price_or_exit`)과 사전점검(`_kr_price_ok` → `checks.price_ok`)이
    이 함수를 공유한다. 비유한 값에 `int()`를 쓰면 터지므로, 호출부는 반드시
    `is_valid_order_price`로 먼저 걸러 낸 뒤에 호출해야 한다 — 두 호출부 모두
    그렇게 되어 있다.
    """
    return price == int(price)


def _kr_price_ok(price: float) -> bool:
    """국내 주문 가격 전체 유효성 술어 (유한·음수 아님·정수). 종료하지 않는다.

    `order validate`의 `checks.price_ok`가 쓴다. `_kr_price_or_exit`와 **같은 두
    규칙**(공용 술어 + 정수 규칙)을 같은 순서로 조합하므로, 사전점검과 실주문의
    가격 판정이 구조적으로 어긋날 수 없다.

    `is_valid_order_price`가 먼저 와야 한다 — and의 단축평가가 NaN/Inf를 걸러
    `_is_kr_integer_price`의 `int()`가 터지지 않게 한다.
    """
    return is_valid_order_price(price) and _is_kr_integer_price(price)


def _kr_price_or_exit(price: float) -> int:
    """국내 주문 가격은 정수(원). 소수점 입력 시 exit 1.

    유한성·음수 검사를 먼저 돌린다 — 이 순서가 아니면 NaN/Inf가 아래 `int(price)`에
    도달해 ValueError/OverflowError로 envelope 없이 죽는다(이 가드 이전의 실제
    동작). 국내 경로(주식/신용/금현물의 매수·매도·정정)는 전부 이 함수를 지나므로
    여기 한 곳에서 세 계열을 모두 덮는다.
    """
    validate_order_price(price, label="국내 주문가격")
    if not _is_kr_integer_price(price):
        fail_input("국내 주문 가격은 정수(원)여야 합니다.")
    return int(price)


def _kr_type_or_exit(order_type: str) -> str:
    if order_type not in ORDER_TYPES:
        fail_input(f"국내주식에서 지원하지 않는 주문유형입니다: {order_type}")
    return ORDER_TYPES[order_type]


def _resolve_gold_type(order_type: str) -> tuple[str, str]:
    """--type 값을 금현물(kt50000/kt50001) trde_tp 코드로 정규화한다.

    order_type은 두 경로로 들어온다: --type을 명시하면 HumanChoice가 이미
    API 코드("00"/"10"/"20")로 변환해 넘긴다(gold_buy/gold_sell의 --type
    옵션이 HumanChoice(GOLD_ORDER_TYPES)라서 그 외 값은 Click 파싱 단계에서
    이미 거부된다). --type을 생략하면 _resolve_order_type의 기본값 로직이
    Click을 거치지 않고 사람이 읽는 이름("limit" 또는 "market")을 그대로
    반환한다 — 금현물은 전부 보통(지정가) 계열이라 시장가가 없으므로,
    가격도 --type도 생략한 경우의 기본값 "market"은 여기서 거부해야 한다.

    반환값은 (wire 코드, 사람이 읽는 이름) — 후자는 미리보기 표시용이다.
    """
    if order_type in GOLD_ORDER_TYPES:
        return GOLD_ORDER_TYPES[order_type], order_type
    if order_type in GOLD_ORDER_TYPES.values():
        label = next(k for k, v in GOLD_ORDER_TYPES.items() if v == order_type)
        return order_type, label
    fail_input(
        "금현물은 limit/ioc/fok 세 가지 주문유형만 지원합니다"
        f" (입력값: {order_type!r}). --type limit/ioc/fok 중 하나와 --price를 지정하세요.",
        code="INVALID_INPUT",
    )


# 시장가 계열 — ord_uv(주문단가)를 시스템이 결정하므로 사용자가 넘긴 --price는
# 조용히 버려진다. kt10000 스펙 자체에는 US ust20001처럼 "빈 값 처리" 문구가
# 없지만, 최유리지정가/최우선지정가/중간가는 체결가가 최우선/최유리 호가나
# 중간가로 자동 결정되는 유형이라 사용자 지정 가격이 의미를 갖지 않는다
# (v2.9 audit finding N2 — 시장가/시장가IOC/시장가FOK 3종만 막고 최유리·최우선·
# 중간가 7종은 빠뜨려 --price가 조용히 전송·무시되던 갭).
#
# "stop"(28, 스톱지정가)은 여기 포함하지 않는다 — 도메인이 같은 dict를 공유하는
# 미국 stop(시장가, 35)과 이름만 같을 뿐 국내 스톱지정가는 지정가 계열이라
# 가격을 유지해야 한다(us/_constants.py의 US_MARKET_TYPES가 미국 쪽을 별도로
# 담당).
_MARKET_TYPES = frozenset({
    "market", "market-ioc", "market-fok",
    "best", "best-ioc", "best-fok",
    "first",
    "mid", "mid-ioc", "mid-fok",
})


def _resolve_order_type(order_type: str | None, price: float) -> str:
    """--type 미지정 시 가격 유무로 결정한다. 시장가 계열 + 가격 지정은 모순.

    조용히 가격을 버리고 시장가로 나가는 사고(가격 지정 매수가 시장가 체결)를
    막는 안전장치다.

    입력 오류는 `fail_input`으로 종료한다 — `click.UsageError`를 쓰면 csv/table
    모드에서 프로젝트 컨벤션(fail_input의 스타일 있는 오류 출력/envelope)
    대신 Click 기본 usage 배너가 노출된다(v2.9 audit finding 4: us/order_ops.py의
    동급 가드는 이미 fail_input을 쓰는데 이쪽만 다른 메커니즘이었다). json 모드는
    두 메커니즘 모두 이전에도 KiwoomGroup의 ClickException 처리로 envelope가
    나갔지만, csv 모드는 raw Click 텍스트가 그대로 노출되고 있었다.
    """
    if order_type is None:
        return "limit" if price else "market"
    if price and order_type in _MARKET_TYPES:
        fail_input(
            f"'{order_type}' 주문유형은 가격을 사용하지 않습니다. "
            "--price를 빼거나 --type limit을 지정하세요."
        )
    return order_type


def _order_type_help() -> str:
    lines = []
    for k, v in ORDER_TYPES.items():
        lines.append(f"  {k} ({v})")
    return "주문유형:\n" + "\n".join(lines)


def _strip_signed_int(value: Any) -> int:
    """키움 숫자 문자열('+00070000', '-70000') → 절대값 int."""
    v = str(value or "").strip().lstrip("+-").lstrip("0") or "0"
    try:
        return int(v)
    except ValueError:
        try:
            return int(float(v))
        except (ValueError, OverflowError):
            # float(v)가 inf/-inf일 때 int()는 ValueError가 아니라 OverflowError를
            # 던진다 — 이 분기가 없으면 계좌 잔고류 응답이 예상 밖의 값을 줄 때
            # 전역 핸들러가 잡지 못하는 traceback으로 이어진다(json 모드 stdout
            # 공백 — envelope-항상 계약 위반).
            return 0


def _quote_price_kr(client, code: str) -> int:
    """현재가 조회 (ka10001). 시장가 주문(주식/신용)의 예상비용 계산용.

    가격 파싱은 (검증 등 다른 용도에 쓰이는) `_strip_signed_int`가 아니라
    `parse_quote_price`를 거친다 — 파싱 실패를 조용히 0으로 넘기지 않고
    QuoteUnavailable로 호출자(_dry_run_kr)에 전파한다.
    """
    data, _ = client.request("ka10001", {"stk_cd": code}, internal=True)
    cur_prc = data.get("cur_prc")
    price = int(parse_quote_price(cur_prc))
    if price <= 0:
        # parse_quote_price는 f > 0만 보장한다(> 0, >= 1이 아님) — (0, 1) 구간의
        # 소수가 여기서 int() 절삭으로 0이 되면 이 함수가 막으려는 바로 그 실패
        # (price=0의 미리보기를 "실제 시세로 계산했다"고 주장)가 재현된다.
        raise QuoteUnavailable(f"시세 값이 정수로 절삭되며 0이 되었습니다: {cur_prc!r}")
    return price


def _dry_run_kr(api_id: str, side: str, code: str, qty: int, kr_price: int,
                order_type: str | None, dmst_stex_tp: str | None,
                body: dict[str, Any], show_preview) -> None:
    """국내 주문 dry-run. 시장가면 현재가(ka10001/_quote_price_kr)를 조회해
    예상비용을 계산한다.

    금현물(kt50000/kt50001)은 전체 유형이 지정가 계열이라 --price가 항상
    필수이므로(gold_buy/gold_sell이 호출 전에 강제) 여기 도달하는 시점엔
    kr_price가 이미 0이 아니다 — 이 시장가-조회 분기 자체가 금현물에는 열리지
    않는다. (과거엔 ka50010 기반 `_quote_price_gold`로 별도 라우팅했으나, 금현물
    시장가 주문이라는 존재하지 않는 기능을 지원하기 위한 죽은 코드였으므로
    제거했다 — Task 7b.)

    현재가 파싱이 실패하면(빈 값/숫자 아님/NaN/Inf/0 이하) price=0인 미리보기를
    price_source="market_quote"와 함께 보여주지 않고 QUOTE_UNAVAILABLE로
    exit 2 — "실제 시세로 계산했다"는 거짓 주장을 막는다.
    """
    price, src = kr_price, None
    if not kr_price and side in ("buy", "sell"):
        with KiwoomClient() as c:
            try:
                price, src = _quote_price_kr(c, code), "market_quote"
            except QuoteUnavailable as e:
                fail_api(
                    f"현재가 조회 결과를 해석할 수 없어 예상비용을 계산할 수 없습니다: {e}",
                    code="QUOTE_UNAVAILABLE",
                )
    finish_dry_run(dry_run_payload(
        api_id=api_id, side=side, symbol=code, qty=qty, price=price,
        order_type=order_type, exchange=dmst_stex_tp, currency="KRW",
        body=body, price_source=src,
    ), show_preview)


def _show_order_preview(action: str, code: str, qty: int, price: int, order_type: str, dmst_stex_tp: str | None = None) -> None:
    price_str = f"{price:,}원" if price else "시장가"
    body = (
        f"[bold]{action} 주문[/]\n\n"
        f"  종목코드: {code}\n"
        f"  수량: {qty:,}\n"
        f"  가격: {price_str}\n"
        f"  유형: {order_type}"
    )
    if dmst_stex_tp is not None:
        body += f"\n  거래소: {dmst_stex_tp}"
    human(Panel(
        body,
        title="주문 확인",
        border_style="yellow",
    ))


def _show_modify_preview(action: str, orig_ord_no: str, code: str, qty: int, price: int, dmst_stex_tp: str | None = None) -> None:
    lines = [
        f"  원주문번호: {orig_ord_no}",
        f"  종목코드: {code}",
        f"  수량: {qty:,}",
        f"  가격: {price:,}원",
    ]
    if dmst_stex_tp is not None:
        lines.append(f"  거래소: {dmst_stex_tp}")
    human(Panel(
        f"[bold]{action} 주문[/]\n\n" + "\n".join(lines),
        title="주문 확인",
        border_style="yellow",
    ))


def _show_cancel_preview(action: str, orig_ord_no: str, code: str, qty: int, dmst_stex_tp: str | None = None) -> None:
    qty_str = f"{qty:,}" if qty else "전량"
    lines = [
        f"  원주문번호: {orig_ord_no}",
        f"  종목코드: {code}",
        f"  수량: {qty_str}",
    ]
    if dmst_stex_tp is not None:
        lines.append(f"  거래소: {dmst_stex_tp}")
    human(Panel(
        f"[bold]{action} 주문[/]\n\n" + "\n".join(lines),
        title="주문 확인",
        border_style="yellow",
    ))


# ════════════════════════════════════════════════════════
#  Top-level order group
# ════════════════════════════════════════════════════════

@click.group("order")
def order():
    """주문 (매수/매도/정정/취소/신용/금현물/조건검색)."""
    pass


# ────────────────────────────────────────────────────────
#  Stock Orders (kt10000 ~ kt10003)
# ────────────────────────────────────────────────────────

@order.command("buy")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략, 미국주식은 소수점 4자리까지)")
@click.option("--type", "order_type", default=None, type=click.Choice(ALL_ORDER_TYPES), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--exchange", "exchange", default=None, type=click.Choice(ORDER_EXCHANGES), help="거래소 (기본: 국내 KRX / 미국 자동판별)")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격 (국내 전용)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def buy(code: str, qty: int, price: float, order_type: str | None, exchange: str | None, cond_uv: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """주식 매수주문 (국내 kt10000 / 미국 ust20000).

    예: kiwoom order buy 005930 10 --price 70000 --type limit --confirm
        kiwoom order buy NVDA 10 --price 213.04 --confirm
    """
    # US 분기 이전에 검증한다 — 국내/미국 양쪽 경로를 한 곳에서 덮는다.
    validate_order_qty(qty, label="매수수량")
    order_type = _resolve_order_type(order_type, price)
    code = strip_kr_market_prefix(code)
    if is_us_symbol(code, exchange):
        if cond_uv:
            fail_input("--cond-price는 국내 주문에서만 사용합니다.")
        return us_order_ops.buy(code, qty, price, order_type, exchange, confirm,
                                dry_run=dry_run, client_order_id=client_order_id)

    dmst_stex_tp = exchange or "KRX"
    trde_tp = _kr_type_or_exit(order_type)
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": trde_tp,
        "cond_uv": str(cond_uv) if cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10000", "buy", code, qty, kr_price, order_type, dmst_stex_tp, body,
                    lambda: _show_order_preview("매수", code, qty, kr_price, order_type, dmst_stex_tp))
        return
    _show_order_preview("매수", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10000", body, "매수", client_order_id, client_cls=KiwoomClient)


@order.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략, 미국주식은 소수점 4자리까지)")
@click.option("--type", "order_type", default=None, type=click.Choice(ALL_ORDER_TYPES), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--exchange", "exchange", default=None, type=click.Choice(ORDER_EXCHANGES), help="거래소 (기본: 국내 KRX / 미국 자동판별)")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격 (국내 전용)")
@click.option("--stop", "stop", type=float, default=0, help="STOP가격 (미국 stop/stop-limit 전용)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def sell(code: str, qty: int, price: float, order_type: str | None, exchange: str | None, cond_uv: int, stop: float, confirm: bool, dry_run: bool, client_order_id: str | None):
    """주식 매도주문 (국내 kt10001 / 미국 ust20001).

    예: kiwoom order sell 005930 10 --type market --confirm
        kiwoom order sell NVDA 5 --type stop-limit --price 200.5 --stop 199.99 --confirm
    """
    # US 분기 이전에 검증한다 — 국내/미국 양쪽 경로를 한 곳에서 덮는다.
    validate_order_qty(qty, label="매도수량")
    order_type = _resolve_order_type(order_type, price)
    code = strip_kr_market_prefix(code)
    if is_us_symbol(code, exchange):
        if cond_uv:
            fail_input("--cond-price는 국내 주문에서만 사용합니다.")
        return us_order_ops.sell(code, qty, price, order_type, exchange, stop, confirm,
                                 dry_run=dry_run, client_order_id=client_order_id)

    if stop:
        fail_input("--stop은 미국주식 매도에서만 사용합니다.")
    dmst_stex_tp = exchange or "KRX"
    trde_tp = _kr_type_or_exit(order_type)
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": trde_tp,
        "cond_uv": str(cond_uv) if cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10001", "sell", code, qty, kr_price, order_type, dmst_stex_tp, body,
                    lambda: _show_order_preview("매도", code, qty, kr_price, order_type, dmst_stex_tp))
        return
    _show_order_preview("매도", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10001", body, "매도", client_order_id, client_cls=KiwoomClient)


@order.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=float)
@click.option("--exchange", "exchange", default=None, type=click.Choice(ORDER_EXCHANGES), help="거래소 (기본: 국내 KRX / 미국 자동판별)")
@click.option("--cond-price", "mdfy_cond_uv", type=int, default=0, help="정정 조건부가격 (국내 전용)")
@click.option("--stop", "stop", type=float, default=0, help="STOP가격 (미국 정정 전용)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def modify(orig_order_no: str, code: str, qty: int, price: float, exchange: str | None, mdfy_cond_uv: int, stop: float, confirm: bool, dry_run: bool, client_order_id: str | None):
    """주식 정정주문 (국내 kt10002 / 미국 ust20002).

    QTY 0은 국내에서 "잔량 전부 정정"이고(kt10002/kt10008/kt50002 스펙),
    미국(ust20002)은 요청 스펙에 수량 필드가 없어 **0만** 받는다.

    예: kiwoom order modify 0000139 005930 1 70000 --confirm
        kiwoom order modify 0000139 005930 0 70000 --confirm   # 잔량 전부
        kiwoom order modify 000000123 NVDA 0 215.5 --confirm   # 미국은 항상 0
    """
    code = strip_kr_market_prefix(code)
    if is_us_symbol(code, exchange):
        if mdfy_cond_uv:
            fail_input("--cond-price는 국내 주문에서만 사용합니다.")
        return us_order_ops.modify(orig_order_no, code, qty, price, exchange, stop, confirm,
                                   dry_run=dry_run, client_order_id=client_order_id)

    if stop:
        fail_input("--stop은 미국주식에서만 사용합니다.")
    dmst_stex_tp = exchange or "KRX"
    # 정정 수량 검증은 US 분기 뒤에 온다 — 국내와 미국의 계약이 다르기 때문이다.
    # 국내 kt10002는 mdfy_qty를 실제로 보내고 **0을 특수값으로 정의한다**:
    # "단위: 1주, '0' 입력 시 잔량 전부 정정" (docs/미국 REST API 문서.xlsx
    # 시트 kt10002 Request). 부분체결 뒤 남은 잔량을 재호가하는 문서화된
    # 관용구라 allow_zero=True다. 미국 ust20002는 요청 스펙에 수량 필드 자체가
    # 없어 us_order_ops.modify가 0 이외의 값을 거부한다.
    validate_order_qty(qty, allow_zero=True, label="정정수량")
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "mdfy_qty": str(qty),
        "mdfy_uv": str(kr_price),
        "mdfy_cond_uv": str(mdfy_cond_uv) if mdfy_cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10002", "modify", code, qty, kr_price, None, dmst_stex_tp, body,
                    lambda: _show_modify_preview("정정", orig_order_no, code, qty, kr_price, dmst_stex_tp))
        return
    _show_modify_preview("정정", orig_order_no, code, qty, kr_price, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10002", body, "정정", client_order_id, client_cls=KiwoomClient)


@order.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소, 미국은 전량취소만 지원)")
@click.option("--exchange", "exchange", default=None, type=click.Choice(ORDER_EXCHANGES), help="거래소 (기본: 국내 KRX / 미국 자동판별)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def cancel(orig_order_no: str, code: str, qty: int, exchange: str | None, confirm: bool, dry_run: bool, client_order_id: str | None):
    """주식 취소주문 (국내 kt10003 / 미국 ust20003).

    예: kiwoom order cancel 0000140 005930 --confirm
        kiwoom order cancel 000000123 NVDA --confirm
    """
    # 취소만 allow_zero=True — `--qty 0`(기본값) = 전량취소가 문서화된 계약이다.
    validate_order_qty(qty, allow_zero=True, label="취소수량")
    code = strip_kr_market_prefix(code)
    if is_us_symbol(code, exchange):
        return us_order_ops.cancel(orig_order_no, code, qty, exchange, confirm,
                                   dry_run=dry_run, client_order_id=client_order_id)

    dmst_stex_tp = exchange or "KRX"
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "cncl_qty": str(qty),
    }
    if dry_run:
        _dry_run_kr("kt10003", "cancel", code, qty, 0, None, dmst_stex_tp, body,
                    lambda: _show_cancel_preview("취소", orig_order_no, code, qty, dmst_stex_tp))
        return
    _show_cancel_preview("취소", orig_order_no, code, qty, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10003", body, "취소", client_order_id, client_cls=KiwoomClient)


# ────────────────────────────────────────────────────────
#  Validate — 주문 사전점검 (read-only, 주문 미전송)
# ────────────────────────────────────────────────────────

KST = timezone(timedelta(hours=9))


def _now_kst() -> datetime:
    return datetime.now(KST)


def _market_open_kr() -> bool:
    """KST 정규장 휴리스틱 (월–금 09:00–15:30). 공휴일은 감지하지 못한다."""
    now = _now_kst()
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 15 * 60 + 30


@order.command("validate")
@click.argument("side", type=click.Choice(["buy", "sell"]))
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (생략 시 현재가로 예상비용 계산)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES)), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소")
def validate(side: str, code: str, qty: int, price: float, order_type: str | None, dmst_stex_tp: str):
    """주문 사전점검 — 주문을 전송하지 않는 read-only 프리플라이트. (ka10001/kt00001/kt00004)

    symbol_ok / market_open / sufficient_balance / price_ok / price_known 를
    점검합니다. 국내 주식 전용 (미국 종목 미지원). market_open은 KST 시계
    휴리스틱입니다. price_known은 --price 미지정 시 현재가(ka10001의 cur_prc)로
    예상비용을 계산할 수 있었는지 — 시세를 해석할 수 없으면(빈 값/0 이하/NaN/
    Inf 등) False이고, 가격을 확정하지 못한 사전점검은 valid: true를 주장하지
    않는다(est_cost도 신뢰할 수 없는 0이 된다). 매수 측 sufficient_balance는
    price_known이 false이면 est_cost=0에 대해 계산한 결과를 true로 보고하지
    않는다(checks만 읽는 에이전트가 미수행 점검을 참으로 오인하지 않도록).

    예: kiwoom -f json order validate buy 005930 10 --price 70000
    """
    order_type = _resolve_order_type(order_type, price)
    code = strip_kr_market_prefix(code)
    if is_us_symbol(code):
        raise click.ClickException("validate는 국내 종목만 지원합니다 (미국주식 미지원).")

    # 실주문 경로와 **같은 술어**를 쓴다 (_mutation.is_valid_order_qty /
    # _kr_price_ok). 사전점검은 실주문 결과를 예측하는 것이 존재 이유이므로,
    # 임계값이 두 벌이 되면 그 자체가 결함이다 — D5b 이전에는 실제로 qty=0과
    # 음수 가격에 valid: true를 답했고 실주문은 거부했다.
    qty_ok = is_valid_order_qty(qty)
    price_ok = _kr_price_ok(price)  # 유한 + 음수 아님 + 국내 정수(원)
    with KiwoomClient() as c:
        quote_price: float | None = None
        try:
            quote, _ = c.request("ka10001", {"stk_cd": code})
        except KiwoomAPIError:
            symbol_ok = False
        else:
            # 가격 파싱은 (검증 대상이 아닌 다른 필드에 쓰이는) `_strip_signed_int`가
            # 아니라 dry-run과 동일한 `parse_quote_price`를 거친다 — inf 같은
            # 값에서 `_strip_signed_int`가 내는 OverflowError(미포착 traceback)를
            # 피하고, symbol_ok 판정에 쓰는 "시세 있음"의 의미도 dry-run과 통일한다.
            try:
                quote_price = parse_quote_price(quote.get("cur_prc"))
            except QuoteUnavailable:
                quote_price = None
            symbol_ok = bool(str(quote.get("stk_nm") or "").strip() or quote_price)
        if price and is_valid_order_price(price):
            est_price = int(price)
            price_known = True
        elif price:
            # --price가 주어졌지만 유효하지 않다(비유한/음수). `if price:`만 보고
            # 곧장 int(price)를 하면 NaN에서 ValueError, Inf에서 OverflowError가
            # 나 envelope 없이 죽는다 — NaN은 truthy라 이 분기를 통과한다.
            # price_ok가 이미 false라 valid는 false로 확정이므로, 예상비용은
            # 계산하지 않고 "가격 모름"으로 둔다.
            est_price = 0
            price_known = False
        elif quote_price is not None:
            # parse_quote_price는 f > 0만 보장한다(> 0, >= 1이 아님) — (0, 1) 구간의
            # 소수는 여기서 int() 절삭으로 0이 될 수 있다. 그 경우 price_known을
            # true로 주장하면 est_cost=0인 사전점검이 그대로 통과(valid: true)해
            # dry-run 경로가 막는 것과 같은 실패를 재현한다.
            est_price = int(quote_price)
            price_known = est_price > 0
        else:
            est_price = 0
            price_known = False
        est_cost = qty * est_price
        if side == "buy":
            deposit, _ = c.request("kt00001", {"qry_tp": "3"})
            # price_known이 false면 est_cost는 신뢰할 수 없는 0이므로
            # "ord_alow_amt >= 0"이 공허하게 참이 된다 — sufficient_balance는
            # 수행하지 못한 점검을 true로 주장해서는 안 된다(v2.9 audit finding 1).
            sufficient = price_known and _strip_signed_int(deposit.get("ord_alow_amt")) >= est_cost
        else:
            balance, _ = c.request("kt00004", {"qry_tp": "0", "dmst_stex_tp": dmst_stex_tp})
            held = sum(
                _strip_signed_int(h.get("rmnd_qty"))
                for h in balance.get("stk_acnt_evlt_prst", []) or []
                # 여기 stk_cd는 kt00004의 **원본** 응답이라 'A005930' 형태다
                # (normalize_record는 출력 단계에서만 걸린다). 따라서 이 접두사
                # 제거는 죽은 코드가 아니다 — 빼면 보유수량이 0으로 잡힌다.
                # removeprefix("A")였던 것을 가드 있는 헬퍼로 바꿨다: 국내
                # 코드에 대해서는 동작이 같고, 혹시 미국 티커가 흘러들어와도
                # AAPL -> APL로 망가뜨리지 않는다.
                if strip_kr_market_prefix(str(h.get("stk_cd", ""))) == code
            )
            sufficient = held >= qty

    checks = {
        "symbol_ok": symbol_ok,
        "market_open": _market_open_kr(),
        "sufficient_balance": sufficient,
        # qty_ok는 D5b에서 추가됐다. 잘못된 수량을 기존 체크에 얹지 않은 이유:
        # 유일하게 그럴듯한 후보인 sufficient_balance는 "잔고 부족"으로 읽히므로,
        # 수량이 0인 사용자에게 입금하라고 안내하는 **틀린 진단**이 된다.
        "qty_ok": qty_ok,
        "price_ok": price_ok,
        "price_known": price_known,
    }
    result = {"valid": all(checks.values()), "checks": checks,
              "est_cost": est_cost, "heuristic": True}
    failing = {k: v for k, v in checks.items() if not v}

    if _get_format() == "table":
        lines = [
            f"  [{'green' if ok else 'red'}]{'✓' if ok else '✗'}[/] {name}"
            for name, ok in checks.items()
        ]
        lines.append(f"\n  예상금액: {est_cost:,}원 [dim](market_open은 시계 휴리스틱)[/]")
        human(Panel(
            "\n".join(lines),
            title=f"주문 사전점검 — {side} {code} x{qty:,}",
            border_style="green" if result["valid"] else "red",
        ))
        if not result["valid"]:
            raise SystemExit(1)
        return

    if result["valid"]:
        envelope.emit(data=result)
        return
    envelope.emit(data=result, error=envelope.error_body(
        "주문 사전점검 실패: " + ", ".join(failing),
        code="VALIDATION_FAILED", retryable=False, details=failing,
    ))
    raise SystemExit(1)


# ════════════════════════════════════════════════════════
#  Credit Orders (kt10006 ~ kt10009)
# ════════════════════════════════════════════════════════

@order.group("credit")
def credit():
    """신용주문 (매수/매도/정정/취소)."""
    pass


@credit.command("buy")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_buy(code: str, qty: int, price: float, order_type: str | None, dmst_stex_tp: str, cond_uv: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 매수주문 (kt10006).

    예: kiwoom order credit buy 005930 10 --type limit --price 70000 --confirm
    """
    validate_order_qty(qty, label="신용 매수수량")
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
        "cond_uv": str(cond_uv) if cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10006", "buy", code, qty, kr_price, order_type, dmst_stex_tp, body,
                    lambda: _show_order_preview("신용 매수", code, qty, kr_price, order_type, dmst_stex_tp))
        return
    _show_order_preview("신용 매수", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10006", body, "신용 매수", client_order_id, client_cls=KiwoomClient)


@credit.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_sell(code: str, qty: int, price: float, order_type: str | None, dmst_stex_tp: str, cond_uv: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 매도주문 (kt10007).

    예: kiwoom order credit sell 005930 10 --type market --confirm
    """
    validate_order_qty(qty, label="신용 매도수량")
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
        "cond_uv": str(cond_uv) if cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10007", "sell", code, qty, kr_price, order_type, dmst_stex_tp, body,
                    lambda: _show_order_preview("신용 매도", code, qty, kr_price, order_type, dmst_stex_tp))
        return
    _show_order_preview("신용 매도", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10007", body, "신용 매도", client_order_id, client_cls=KiwoomClient)


@credit.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=float)
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "mdfy_cond_uv", type=int, default=0, help="정정 조건부가격")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_modify(orig_order_no: str, code: str, qty: int, price: float, dmst_stex_tp: str, mdfy_cond_uv: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 정정주문 (kt10008).

    예: kiwoom order credit modify 0000139 005930 1 70000 --confirm
    """
    # kt10002와 같은 비고: "'0' 입력 시 잔량 전부 정정" (kt10008 Request)
    validate_order_qty(qty, allow_zero=True, label="신용 정정수량")
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "mdfy_qty": str(qty),
        "mdfy_uv": str(kr_price),
        "mdfy_cond_uv": str(mdfy_cond_uv) if mdfy_cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10008", "modify", code, qty, kr_price, None, dmst_stex_tp, body,
                    lambda: _show_modify_preview("신용 정정", orig_order_no, code, qty, kr_price, dmst_stex_tp))
        return
    _show_modify_preview("신용 정정", orig_order_no, code, qty, kr_price, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10008", body, "신용 정정", client_order_id, client_cls=KiwoomClient)


@credit.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_cancel(orig_order_no: str, code: str, qty: int, dmst_stex_tp: str, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 취소주문 (kt10009).

    예: kiwoom order credit cancel 0000140 005930 --confirm
    """
    validate_order_qty(qty, allow_zero=True, label="신용 취소수량")
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "cncl_qty": str(qty),
    }
    if dry_run:
        _dry_run_kr("kt10009", "cancel", code, qty, 0, None, dmst_stex_tp, body,
                    lambda: _show_cancel_preview("신용 취소", orig_order_no, code, qty, dmst_stex_tp))
        return
    _show_cancel_preview("신용 취소", orig_order_no, code, qty, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10009", body, "신용 취소", client_order_id, client_cls=KiwoomClient)


# ════════════════════════════════════════════════════════
#  Gold Orders & Account (kt50000 ~ kt50003, kt50020 ~ kt50075)
# ════════════════════════════════════════════════════════

@order.group("gold")
def gold():
    """금현물 주문 및 계좌 조회."""
    pass


@gold.command("buy")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (금현물은 전체 유형이 지정가 계열이라 필수)")
@click.option("--type", "order_type", default=None, type=HumanChoice(GOLD_ORDER_TYPES), help="주문유형 (limit=보통, ioc=보통(IOC), fok=보통(FOK); 시장가 없음, 기본 limit)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_buy(code: str, qty: int, price: float, order_type: str | None, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 매수주문 (kt50000). 지정가 계열만 지원 (limit/ioc/fok) — 시장가 없음.

    예: kiwoom order gold buy M04020000 10 --type limit --price 90000 --confirm
    """
    validate_order_qty(qty, label="금현물 매수수량")
    order_type = _resolve_order_type(order_type, price)
    trde_tp, order_type_label = _resolve_gold_type(order_type)
    kr_price = _kr_price_or_exit(price)
    if not kr_price:
        fail_input(
            "금현물 주문은 가격이 필수입니다 (전체 유형이 보통/지정가 계열이며 시장가가 없습니다). --price를 지정하세요.",
            code="INVALID_INPUT",
        )
    body = {
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price),
        "trde_tp": trde_tp,
    }
    if dry_run:
        _dry_run_kr("kt50000", "buy", code, qty, kr_price, order_type_label, None, body,
                    lambda: _show_order_preview("금현물 매수", code, qty, kr_price, order_type_label))
        return
    _show_order_preview("금현물 매수", code, qty, kr_price, order_type_label)
    confirm_gate(confirm)
    send_order("kt50000", body, "금현물 매수", client_order_id, client_cls=KiwoomClient)


@gold.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (금현물은 전체 유형이 지정가 계열이라 필수)")
@click.option("--type", "order_type", default=None, type=HumanChoice(GOLD_ORDER_TYPES), help="주문유형 (limit=보통, ioc=보통(IOC), fok=보통(FOK); 시장가 없음, 기본 limit)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_sell(code: str, qty: int, price: float, order_type: str | None, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 매도주문 (kt50001). 지정가 계열만 지원 (limit/ioc/fok) — 시장가 없음.

    예: kiwoom order gold sell M04020000 10 --type limit --price 90000 --confirm
    """
    validate_order_qty(qty, label="금현물 매도수량")
    order_type = _resolve_order_type(order_type, price)
    trde_tp, order_type_label = _resolve_gold_type(order_type)
    kr_price = _kr_price_or_exit(price)
    if not kr_price:
        fail_input(
            "금현물 주문은 가격이 필수입니다 (전체 유형이 보통/지정가 계열이며 시장가가 없습니다). --price를 지정하세요.",
            code="INVALID_INPUT",
        )
    body = {
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price),
        "trde_tp": trde_tp,
    }
    if dry_run:
        _dry_run_kr("kt50001", "sell", code, qty, kr_price, order_type_label, None, body,
                    lambda: _show_order_preview("금현물 매도", code, qty, kr_price, order_type_label))
        return
    _show_order_preview("금현물 매도", code, qty, kr_price, order_type_label)
    confirm_gate(confirm)
    send_order("kt50001", body, "금현물 매도", client_order_id, client_cls=KiwoomClient)


@gold.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=float)
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_modify(orig_order_no: str, code: str, qty: int, price: float, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 정정주문 (kt50002).

    예: kiwoom order gold modify 0000139 M04020000 1 90000 --confirm
    """
    # kt10002와 같은 비고: "'0' 입력 시 잔량 전부 정정" (kt50002 Request)
    validate_order_qty(qty, allow_zero=True, label="금현물 정정수량")
    kr_price = _kr_price_or_exit(price)
    body = {
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "mdfy_qty": str(qty),
        "mdfy_uv": str(kr_price),
    }
    if dry_run:
        _dry_run_kr("kt50002", "modify", code, qty, kr_price, None, None, body,
                    lambda: _show_modify_preview("금현물 정정", orig_order_no, code, qty, kr_price))
        return
    _show_modify_preview("금현물 정정", orig_order_no, code, qty, kr_price)
    confirm_gate(confirm)
    send_order("kt50002", body, "금현물 정정", client_order_id, client_cls=KiwoomClient)


@gold.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_cancel(orig_order_no: str, code: str, qty: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 취소주문 (kt50003).

    예: kiwoom order gold cancel 0000140 M04020000 --confirm
    """
    validate_order_qty(qty, allow_zero=True, label="금현물 취소수량")
    body = {
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "cncl_qty": str(qty),
    }
    if dry_run:
        _dry_run_kr("kt50003", "cancel", code, qty, 0, None, None, body,
                    lambda: _show_cancel_preview("금현물 취소", orig_order_no, code, qty))
        return
    _show_cancel_preview("금현물 취소", orig_order_no, code, qty)
    confirm_gate(confirm)
    send_order("kt50003", body, "금현물 취소", client_order_id, client_cls=KiwoomClient)


# ── Gold Account Queries ───────────────────────────────

@gold.command("balance")
def gold_balance():
    """금현물 잔고확인 (kt50020).

    예: kiwoom order gold balance
    """
    with KiwoomClient() as c:
        data, _ = c.request("kt50020", {})
        print_generic_table(data, title="금현물 잔고확인")


@gold.command("deposit")
def gold_deposit():
    """금현물 예수금 (kt50021).

    예: kiwoom order gold deposit
    """
    with KiwoomClient() as c:
        data, _ = c.request("kt50021", {})
        print_generic_table(data, title="금현물 예수금")


@gold.command("executions-all")
def gold_executions_all():
    """금현물 주문체결전체조회 (kt50030).

    예: kiwoom order gold executions-all
    """
    with KiwoomClient() as c:
        data, _ = c.request("kt50030", {})
        print_generic_table(data, title="금현물 주문체결전체조회")


@gold.command("executions")
def gold_executions():
    """금현물 주문체결조회 (kt50031).

    예: kiwoom order gold executions
    """
    with KiwoomClient() as c:
        data, _ = c.request("kt50031", {})
        print_generic_table(data, title="금현물 주문체결조회")


@gold.command("history")
def gold_history():
    """금현물 거래내역조회 (kt50032).

    예: kiwoom order gold history
    """
    with KiwoomClient() as c:
        data, _ = c.request("kt50032", {})
        print_generic_table(data, title="금현물 거래내역조회")


@gold.command("pending")
def gold_pending():
    """금현물 미체결조회 (kt50075).

    예: kiwoom order gold pending
    """
    with KiwoomClient() as c:
        data, _ = c.request("kt50075", {})
        print_generic_table(data, title="금현물 미체결조회")


# ════════════════════════════════════════════════════════
#  Condition Search (ka10171 ~ ka10174) - WebSocket-based
# ════════════════════════════════════════════════════════

@order.group("condition")
def condition():
    """조건검색 (목록조회/검색요청/실시간/해제)."""
    pass


@condition.command("list")
def condition_list():
    """조건검색 목록조회 (ka10171).

    예: kiwoom order condition list
    """
    with KiwoomClient() as c:
        data, _ = c.request("ka10171", {
            "trnm": "CNSRLST",
        })
        print_generic_table(data, title="조건검색 목록")


@condition.command("search")
@click.argument("seq")
@click.option("--exchange", "stex_tp", default="K", type=click.Choice(["K"]), help="거래소 (K=KRX)")
@click.option("--cont-yn", default="", help="연속조회여부")
@click.option("--next-key", default="", help="연속조회키")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 조건검색 조회 실행")
def condition_search(seq: str, stex_tp: str, cont_yn: str, next_key: str, confirm: bool):
    """조건검색 요청 일반 (ka10172).

    예: kiwoom order condition search 001 --confirm
    """
    confirm_gate(confirm)
    suppress_pagination()  # 조건검색 요청도 confirm_gate 대상 — --all-pages로 재전송하면 안 됨

    body = {
        "trnm": "CNSRREQ",
        "seq": seq,
        "search_type": "0",
        "stex_tp": stex_tp,
    }
    if cont_yn:
        body["cont_yn"] = cont_yn
    if next_key:
        body["next_key"] = next_key

    with KiwoomClient() as c:
        data, _ = c.request("ka10172", body)
        print_generic_table(data, title="조건검색 결과")


@condition.command("realtime")
@click.argument("seq")
@click.option("--exchange", "stex_tp", default="K", type=click.Choice(["K"]), help="거래소 (K=KRX)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 조건검색 실시간 등록 실행")
def condition_realtime(seq: str, stex_tp: str, confirm: bool):
    """조건검색 요청 실시간 (ka10173).

    예: kiwoom order condition realtime 001 --confirm
    """
    confirm_gate(confirm)
    suppress_pagination()  # 실시간 등록 반복은 서버측 중복 구독을 유발 — --all-pages 무시

    with KiwoomClient() as c:
        data, _ = c.request("ka10173", {
            "trnm": "CNSRREQ",
            "seq": seq,
            "search_type": "1",
            "stex_tp": stex_tp,
        })
        print_generic_table(data, title="조건검색 실시간 등록")


@condition.command("stop")
@click.argument("seq")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 조건검색 실시간 해제 실행")
def condition_stop(seq: str, confirm: bool):
    """조건검색 실시간 해제 (ka10174).

    예: kiwoom order condition stop 001 --confirm
    """
    confirm_gate(confirm)
    suppress_pagination()  # 해제 요청도 confirm_gate 대상 — --all-pages로 재전송하면 안 됨

    with KiwoomClient() as c:
        data, _ = c.request("ka10174", {
            "trnm": "CNSRCLR",
            "seq": seq,
        })
        print_generic_table(data, title="조건검색 실시간 해제")
