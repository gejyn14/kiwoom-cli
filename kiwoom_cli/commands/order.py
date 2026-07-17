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
from ..formatters import _get_format, human, print_generic_table
from ..output import err_console
from ._mutation import confirm_gate, dry_run_payload, finish_dry_run, send_order
from .us import order_ops as us_order_ops
from .us._constants import US_ORDER_TYPES
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


def _kr_price_or_exit(price: float) -> int:
    """국내 주문 가격은 정수(원). 소수점 입력 시 exit 1."""
    if price != int(price):
        err_console.print("[red]국내 주문 가격은 정수(원)여야 합니다.[/]")
        raise SystemExit(1)
    return int(price)


def _kr_type_or_exit(order_type: str) -> str:
    if order_type not in ORDER_TYPES:
        err_console.print(f"[red]국내주식에서 지원하지 않는 주문유형입니다: {order_type}[/]")
        raise SystemExit(1)
    return ORDER_TYPES[order_type]


_MARKET_TYPES = frozenset({"market", "market-ioc", "market-fok"})


def _resolve_order_type(order_type: str | None, price: float) -> str:
    """--type 미지정 시 가격 유무로 결정한다. 시장가 계열 + 가격 지정은 모순.

    조용히 가격을 버리고 시장가로 나가는 사고(가격 지정 매수가 시장가 체결)를
    막는 안전장치다.
    """
    if order_type is None:
        return "limit" if price else "market"
    if price and order_type in _MARKET_TYPES:
        raise click.UsageError(
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
        except ValueError:
            return 0


def _quote_price_kr(client, code: str) -> int:
    """현재가 조회 (ka10001). 시장가 주문의 예상비용 계산용."""
    data, _ = client.request("ka10001", {"stk_cd": code})
    return _strip_signed_int(data.get("cur_prc"))


def _dry_run_kr(api_id: str, side: str, code: str, qty: int, kr_price: int,
                order_type: str | None, dmst_stex_tp: str | None,
                body: dict[str, Any], show_preview) -> None:
    """국내 주문 dry-run. 시장가면 현재가를 조회해 예상비용을 계산한다."""
    price, src = kr_price, None
    if not kr_price and side in ("buy", "sell"):
        with KiwoomClient() as c:
            price, src = _quote_price_kr(c, code), "market_quote"
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
    order_type = _resolve_order_type(order_type, price)
    if is_us_symbol(code, exchange):
        if cond_uv:
            err_console.print("[red]--cond-price는 국내 주문에서만 사용합니다.[/]")
            raise SystemExit(1)
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
    order_type = _resolve_order_type(order_type, price)
    if is_us_symbol(code, exchange):
        if cond_uv:
            err_console.print("[red]--cond-price는 국내 주문에서만 사용합니다.[/]")
            raise SystemExit(1)
        return us_order_ops.sell(code, qty, price, order_type, exchange, stop, confirm,
                                 dry_run=dry_run, client_order_id=client_order_id)

    if stop:
        err_console.print("[red]--stop은 미국주식 매도에서만 사용합니다.[/]")
        raise SystemExit(1)
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

    예: kiwoom order modify 0000139 005930 1 70000 --confirm
        kiwoom order modify 000000123 NVDA 5 215.5 --confirm
    """
    if is_us_symbol(code, exchange):
        if mdfy_cond_uv:
            err_console.print("[red]--cond-price는 국내 주문에서만 사용합니다.[/]")
            raise SystemExit(1)
        return us_order_ops.modify(orig_order_no, code, qty, price, exchange, stop, confirm,
                                   dry_run=dry_run, client_order_id=client_order_id)

    if stop:
        err_console.print("[red]--stop은 미국주식에서만 사용합니다.[/]")
        raise SystemExit(1)
    dmst_stex_tp = exchange or "KRX"
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
@click.option("--type", "order_type", default="market", type=click.Choice(list(ORDER_TYPES)), help="주문유형")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소")
def validate(side: str, code: str, qty: int, price: float, order_type: str, dmst_stex_tp: str):
    """주문 사전점검 — 주문을 전송하지 않는 read-only 프리플라이트. (ka10001/kt00001/kt00004)

    symbol_ok / market_open / sufficient_balance / price_ok 를 점검합니다.
    국내 주식 전용 (미국 종목 미지원). market_open은 KST 시계 휴리스틱입니다.

    예: kiwoom order validate buy 005930 10 --price 70000 -f json
    """
    if is_us_symbol(code):
        raise click.ClickException("validate는 국내 종목만 지원합니다 (미국주식 미지원).")

    price_ok = price == int(price)  # 국내 지정가는 정수(원)
    with KiwoomClient() as c:
        try:
            quote, _ = c.request("ka10001", {"stk_cd": code})
            symbol_ok = bool(str(quote.get("stk_nm") or "").strip()
                             or _strip_signed_int(quote.get("cur_prc")))
        except KiwoomAPIError:
            quote = {}
            symbol_ok = False
        est_price = int(price) if price else _strip_signed_int(quote.get("cur_prc"))
        est_cost = qty * est_price
        if side == "buy":
            deposit, _ = c.request("kt00001", {"qry_tp": "3"})
            sufficient = _strip_signed_int(deposit.get("ord_alow_amt")) >= est_cost
        else:
            balance, _ = c.request("kt00004", {"qry_tp": "0", "dmst_stex_tp": dmst_stex_tp})
            held = sum(
                _strip_signed_int(h.get("rmnd_qty"))
                for h in balance.get("stk_acnt_evlt_prst", []) or []
                if str(h.get("stk_cd", "")).removeprefix("A") == code
            )
            sufficient = held >= qty

    checks = {
        "symbol_ok": symbol_ok,
        "market_open": _market_open_kr(),
        "sufficient_balance": sufficient,
        "price_ok": price_ok,
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
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_buy(code: str, qty: int, price: float, order_type: str | None, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 매수주문 (kt50000).

    예: kiwoom order gold buy 730060 10 --type limit --price 90000 --confirm
    """
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
    }
    if dry_run:
        _dry_run_kr("kt50000", "buy", code, qty, kr_price, order_type, None, body,
                    lambda: _show_order_preview("금현물 매수", code, qty, kr_price, order_type))
        return
    _show_order_preview("금현물 매수", code, qty, kr_price, order_type)
    confirm_gate(confirm)
    send_order("kt50000", body, "금현물 매수", client_order_id, client_cls=KiwoomClient)


@gold.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_sell(code: str, qty: int, price: float, order_type: str | None, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 매도주문 (kt50001).

    예: kiwoom order gold sell 730060 10 --type market --confirm
    """
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
    }
    if dry_run:
        _dry_run_kr("kt50001", "sell", code, qty, kr_price, order_type, None, body,
                    lambda: _show_order_preview("금현물 매도", code, qty, kr_price, order_type))
        return
    _show_order_preview("금현물 매도", code, qty, kr_price, order_type)
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

    예: kiwoom order gold modify 0000139 730060 1 90000 --confirm
    """
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

    예: kiwoom order gold cancel 0000140 730060 --confirm
    """
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
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def condition_search(seq: str, stex_tp: str, cont_yn: str, next_key: str, confirm: bool):
    """조건검색 요청 일반 (ka10172).

    예: kiwoom order condition search 001 --confirm
    """
    confirm_gate(confirm)

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
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def condition_realtime(seq: str, stex_tp: str, confirm: bool):
    """조건검색 요청 실시간 (ka10173).

    예: kiwoom order condition realtime 001 --confirm
    """
    confirm_gate(confirm)

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
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def condition_stop(seq: str, confirm: bool):
    """조건검색 실시간 해제 (ka10174).

    예: kiwoom order condition stop 001 --confirm
    """
    confirm_gate(confirm)

    with KiwoomClient() as c:
        data, _ = c.request("ka10174", {
            "trnm": "CNSRCLR",
            "seq": seq,
        })
        print_generic_table(data, title="조건검색 실시간 해제")
