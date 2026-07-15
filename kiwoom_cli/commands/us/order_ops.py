"""US order operations, dispatched from commands/order.py."""

from __future__ import annotations

import click
from rich.panel import Panel

from ...client import KiwoomClient
from ...formatters import print_generic_table, print_order_result
from ...output import console, err_console
from ._constants import (
    US_ORDER_TYPES,
    US_SELL_ONLY_TYPES,
    US_STOP_TYPES,
)
from .detect import UsExchangeError, resolve_us_exchange

_EXCHANGE_NAMES = {"ND": "NASDAQ", "NY": "NYSE", "NA": "AMEX"}


def fmt_us_price(price: float) -> str:
    """소수점 4자리까지, 뒤 0 제거. 0이면 빈 문자열(시장가)."""
    if not price:
        return ""
    return f"{price:.4f}".rstrip("0").rstrip(".")


def _validate_us_type(order_type: str, side: str) -> str:
    """CLI 주문유형 → trde_tp 코드. 미지원이면 exit 1."""
    if order_type not in US_ORDER_TYPES:
        err_console.print(f"[red]미국주식에서 지원하지 않는 주문유형입니다: {order_type}[/]")
        raise SystemExit(1)
    if side == "buy" and order_type in US_SELL_ONLY_TYPES:
        err_console.print(f"[red]'{order_type}'은(는) 매도 전용 주문유형입니다 (매수 미지원).[/]")
        raise SystemExit(1)
    return US_ORDER_TYPES[order_type]


def _confirm_gate(confirm: bool) -> None:
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)


def _show_us_preview(action: str, code: str, qty: int, price: float,
                     order_type: str, stex_tp: str, stop: float = 0) -> None:
    price_str = f"${fmt_us_price(price)}" if price else "시장가"
    qty_str = f"{qty:,}" if qty else "전량"
    body = (
        f"[bold]{action} 주문 (미국)[/]\n\n"
        f"  종목코드: {code}\n"
        f"  수량: {qty_str}\n"
        f"  가격: {price_str}\n"
        f"  유형: {order_type}\n"
        f"  거래소: {_EXCHANGE_NAMES.get(stex_tp, stex_tp)}"
    )
    if stop:
        body += f"\n  STOP가격: ${fmt_us_price(stop)}"
    console.print(Panel(body, title="주문 확인", border_style="yellow"))


def _resolve_or_exit(client, code: str, exchange: str | None) -> str:
    try:
        return resolve_us_exchange(client, code, exchange)
    except UsExchangeError as e:
        err_console.print(f"[red]{e}[/]")
        raise SystemExit(1) from None


def buy(code: str, qty: int, price: float, order_type: str,
        exchange: str | None, confirm: bool) -> None:
    """미국주식 매수 (ust20000)."""
    trde_tp = _validate_us_type(order_type, "buy")
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("매수", code, qty, price, order_type, stex_tp)
        data, _ = c.request("ust20000", {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "ord_qty": str(qty),
            "ord_uv": fmt_us_price(price),
            "trde_tp": trde_tp,
        })
        print_order_result(data, "매수")


def sell(code: str, qty: int, price: float, order_type: str,
         exchange: str | None, stop: float, confirm: bool) -> None:
    """미국주식 매도 (ust20001)."""
    trde_tp = _validate_us_type(order_type, "sell")
    if order_type in US_STOP_TYPES and not stop:
        err_console.print(f"[red]'{order_type}' 주문에는 --stop 가격이 필요합니다.[/]")
        raise SystemExit(1)
    if stop and order_type not in US_STOP_TYPES:
        err_console.print("[red]--stop은 stop/stop-limit 주문에서만 사용합니다.[/]")
        raise SystemExit(1)
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("매도", code, qty, price, order_type, stex_tp, stop)
        body = {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "ord_qty": str(qty),
            "ord_uv": fmt_us_price(price),
            "trde_tp": trde_tp,
        }
        if stop:
            body["stop_pric"] = fmt_us_price(stop)
        data, _ = c.request("ust20001", body)
        print_order_result(data, "매도")


def modify(orig_order_no: str, code: str, qty: int, price: float,
           exchange: str | None, stop: float, confirm: bool) -> None:
    """미국주식 정정 (ust20002) — 가격 정정만 지원, 항상 잔량 전체."""
    console.print("[yellow]미국주식 정정은 수량 변경 미지원 — 전량 가격정정으로 처리됩니다.[/]")
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("정정", code, 0, price, "limit", stex_tp, stop)
        body = {
            "orig_ord_no": orig_order_no,
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "mdfy_uv": fmt_us_price(price),
        }
        if stop:
            body["stop_pric"] = fmt_us_price(stop)
        data, _ = c.request("ust20002", body)
        print_order_result(data, "정정")


def cancel(orig_order_no: str, code: str, qty: int,
           exchange: str | None, confirm: bool) -> None:
    """미국주식 취소 (ust20003) — 잔량 전체 취소만 지원."""
    if qty:
        err_console.print("[red]미국주식은 부분 취소를 지원하지 않습니다 (수량 지정 불가, 전량 취소만 가능).[/]")
        raise SystemExit(1)
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("취소", code, 0, 0, "-", stex_tp)
        data, _ = c.request("ust20003", {
            "orig_ord_no": orig_order_no,
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
        })
        print_order_result(data, "취소")


def orderable(code: str, price: float, exchange: str | None) -> None:
    """미국주식 주문가능수량 (ust31490)."""
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        data, _ = c.request("ust31490", {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "uv": fmt_us_price(price),
        })
        print_generic_table(data, title=f"{code.upper()} 주문가능수량 (미국)")
