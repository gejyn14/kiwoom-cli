"""US order operations, dispatched from commands/order.py."""

from __future__ import annotations

from rich.panel import Panel

from ...client import KiwoomClient
from ...formatters import fail_api, fail_input, human, print_generic_table
from .._mutation import (
    QuoteUnavailable,
    confirm_gate,
    dry_run_payload,
    finish_dry_run,
    parse_quote_price,
    send_order,
)
from ._constants import (
    US_LIMIT_TYPES,
    US_MARKET_TYPES,
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


def _validate_us_type(order_type: str, side: str, price: float) -> str:
    """CLI 주문유형 → trde_tp 코드. 미지원이면 exit 1.

    price가 주어졌는데 order_type이 시장가 계열(US_MARKET_TYPES)이면 거부한다
    — ord_uv는 그 유형들에서 빈 값 처리되므로(스펙), 안 그러면 사용자가 지정한
    가격이 조용히 버려지고 시장가로 체결된다(v2.9 audit finding N2).

    반대 방향도 거부한다 — order_type이 지정가 계열(US_LIMIT_TYPES)인데 price가
    없으면 ord_uv=""로 전송되어 거부되거나 의도치 않게 처리된다(ust20000/
    ust20001 스펙: "trde_tp가 00(지정가),30(LOC)...인 경우 필수 입력"). 이
    가드가 없으면 `order buy NVDA 10 --type limit`이 조용히 ord_uv=""로
    전송된다(task 14b — 국내 kt10000/kt10001은 대상 아님: 그쪽 ord_uv
    Description엔 "단위: 원"뿐이고 이 조건부 필수 문구가 없다).

    price는 필수 위치 인자다 — 기본값 0을 두면 그 값 자체가 이 가드를 조용히
    건너뛰는 우회로가 되어, 이 작업 전체가 막으려는 바로 그 실패 모드(가격
    무시)가 다음 호출부 추가 때 재발할 수 있다(v2.9 audit finding 1).
    """
    if order_type not in US_ORDER_TYPES:
        fail_input(f"미국주식에서 지원하지 않는 주문유형입니다: {order_type}")
    if side == "buy" and order_type in US_SELL_ONLY_TYPES:
        fail_input(f"'{order_type}'은(는) 매도 전용 주문유형입니다 (매수 미지원).")
    if price and order_type in US_MARKET_TYPES:
        fail_input(
            f"'{order_type}' 주문유형은 가격을 사용하지 않습니다. "
            "--price를 빼거나 --type limit을 지정하세요."
        )
    if not price and order_type in US_LIMIT_TYPES:
        fail_input(
            f"'{order_type}' 주문유형은 가격이 필수입니다 (지정가 계열이며 "
            "시장가로 처리되지 않습니다). --price를 지정하세요.",
            code="INVALID_INPUT",
        )
    return US_ORDER_TYPES[order_type]


def _quote_price_us(client, code: str, stex_tp: str) -> float:
    """미국주식 현재가 (usa20100). 시장가 주문의 예상비용 계산용.

    usa20100 스펙 응답 필드는 cur_prc (예: "+201.4700") — now_pric가 아니다.
    now_pric는 계좌 잔고 API(ust21070 등)의 현재가 필드 이름이다. 가격 파싱은
    parse_quote_price를 거친다 — 파싱 실패를 조용히 0으로 넘기지 않고
    QuoteUnavailable로 호출자(_dry_run_us)에 전파한다.
    """
    data, _ = client.request(
        "usa20100", {"stex_tp": stex_tp, "stk_cd": code.upper()}, internal=True
    )
    return parse_quote_price(data.get("cur_prc"))


def _dry_run_us(api_id: str, side: str, code: str, qty: int, price: float,
                order_type: str | None, exchange: str | None,
                body_fn, show_preview_fn) -> None:
    """미국 주문 dry-run. 거래소를 확정하고(body에 필요) 전송 없이 출력한다.

    body_fn(stex_tp) -> 실제 전송과 동일한 body.
    show_preview_fn(stex_tp) -> table 모드 미리보기.

    현재가 파싱이 실패하면(빈 값/숫자 아님/NaN/Inf) price=0인 미리보기를
    price_source="market_quote"와 함께 보여주지 않고 QUOTE_UNAVAILABLE로
    exit 2 — "실제 시세로 계산했다"는 거짓 주장을 막는다.
    """
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        est_price, src = price, None
        if not price and side in ("buy", "sell"):
            try:
                est_price, src = _quote_price_us(c, code, stex_tp), "market_quote"
            except QuoteUnavailable as e:
                fail_api(
                    f"현재가 조회 결과를 해석할 수 없어 예상비용을 계산할 수 없습니다: {e}",
                    code="QUOTE_UNAVAILABLE",
                )
    finish_dry_run(dry_run_payload(
        api_id=api_id, side=side, symbol=code.upper(), qty=qty, price=est_price,
        order_type=order_type, exchange=stex_tp, currency="USD",
        body=body_fn(stex_tp), price_source=src,
    ), lambda: show_preview_fn(stex_tp))


def _send_us_order(api_id: str, action: str, code: str, exchange: str | None,
                   body_fn, show_preview_fn, client_order_id: str | None,
                   confirm: bool) -> None:
    """거래소 확정 → 미리보기 → 확인 게이트 → 전송(멱등성).

    자동 판별된 거래소까지 사용자가 본 뒤에 확인하도록 게이트가 마지막이다.
    """
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
    show_preview_fn(stex_tp)
    confirm_gate(confirm)
    send_order(api_id, body_fn(stex_tp), action, client_order_id,
               client_cls=KiwoomClient)


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
    human(Panel(body, title="주문 확인", border_style="yellow"))


def _resolve_or_exit(client, code: str, exchange: str | None) -> str:
    try:
        return resolve_us_exchange(client, code, exchange)
    except UsExchangeError as e:
        fail_input(str(e))


def buy(code: str, qty: int, price: float, order_type: str,
        exchange: str | None, confirm: bool,
        dry_run: bool = False, client_order_id: str | None = None) -> None:
    """미국주식 매수 (ust20000)."""
    trde_tp = _validate_us_type(order_type, "buy", price)

    def body_fn(stex_tp: str) -> dict[str, str]:
        return {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "ord_qty": str(qty),
            "ord_uv": fmt_us_price(price),
            "trde_tp": trde_tp,
        }

    def preview_fn(stex_tp: str) -> None:
        _show_us_preview("매수", code, qty, price, order_type, stex_tp)

    if dry_run:
        _dry_run_us("ust20000", "buy", code, qty, price, order_type, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20000", "매수", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)


def sell(code: str, qty: int, price: float, order_type: str,
         exchange: str | None, stop: float, confirm: bool,
         dry_run: bool = False, client_order_id: str | None = None) -> None:
    """미국주식 매도 (ust20001)."""
    trde_tp = _validate_us_type(order_type, "sell", price)
    if order_type in US_STOP_TYPES and not stop:
        fail_input(f"'{order_type}' 주문에는 --stop 가격이 필요합니다.")
    if stop and order_type not in US_STOP_TYPES:
        fail_input("--stop은 stop/stop-limit 주문에서만 사용합니다.")

    def body_fn(stex_tp: str) -> dict[str, str]:
        body = {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "ord_qty": str(qty),
            "ord_uv": fmt_us_price(price),
            "trde_tp": trde_tp,
        }
        if stop:
            body["stop_pric"] = fmt_us_price(stop)
        return body

    def preview_fn(stex_tp: str) -> None:
        _show_us_preview("매도", code, qty, price, order_type, stex_tp, stop)

    if dry_run:
        _dry_run_us("ust20001", "sell", code, qty, price, order_type, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20001", "매도", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)


def modify(orig_order_no: str, code: str, qty: int, price: float,
           exchange: str | None, stop: float, confirm: bool,
           dry_run: bool = False, client_order_id: str | None = None) -> None:
    """미국주식 정정 (ust20002) — 가격 정정만 지원, 항상 잔량 전체."""
    human("[yellow]미국주식 정정은 수량 변경 미지원 — 전량 가격정정으로 처리됩니다.[/]")

    def body_fn(stex_tp: str) -> dict[str, str]:
        body = {
            "orig_ord_no": orig_order_no,
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "mdfy_uv": fmt_us_price(price),
        }
        if stop:
            body["stop_pric"] = fmt_us_price(stop)
        return body

    def preview_fn(stex_tp: str) -> None:
        _show_us_preview("정정", code, 0, price, "limit", stex_tp, stop)

    if dry_run:
        _dry_run_us("ust20002", "modify", code, 0, price, None, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20002", "정정", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)


def cancel(orig_order_no: str, code: str, qty: int,
           exchange: str | None, confirm: bool,
           dry_run: bool = False, client_order_id: str | None = None) -> None:
    """미국주식 취소 (ust20003) — 잔량 전체 취소만 지원."""
    if qty:
        fail_input("미국주식은 부분 취소를 지원하지 않습니다 (수량 지정 불가, 전량 취소만 가능).")

    def body_fn(stex_tp: str) -> dict[str, str]:
        return {
            "orig_ord_no": orig_order_no,
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
        }

    def preview_fn(stex_tp: str) -> None:
        _show_us_preview("취소", code, 0, 0, "-", stex_tp)

    if dry_run:
        _dry_run_us("ust20003", "cancel", code, 0, 0, None, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20003", "취소", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)


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
