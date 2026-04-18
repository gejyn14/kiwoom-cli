"""Order management commands.

Order commands prompt for confirmation by default. Use --confirm to skip
the prompt (for scripts/automation).

Subgroups:
  order buy/sell/modify/cancel     - Stock orders (kt10000-kt10003)
  order credit buy/sell/modify/cancel - Credit orders (kt10006-kt10009)
  order gold buy/sell/modify/cancel/balance/deposit/executions/execution/history/pending
                                   - Gold orders & account (kt50000-kt50003, kt50020-kt50075)
  order condition list/search/realtime/stop - Condition search (ka10171-ka10174)
"""

from __future__ import annotations

import click
from rich.panel import Panel

from ..client import KiwoomClient
from ..formatters import print_order_result, print_generic_table
from ..output import console

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


def _order_type_help() -> str:
    lines = []
    for k, v in ORDER_TYPES.items():
        lines.append(f"  {k} ({v})")
    return "주문유형:\n" + "\n".join(lines)


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
    console.print(Panel(
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
    console.print(Panel(
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
    console.print(Panel(
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
@click.option("--price", type=int, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default="market", type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격 (스톱지정가 등)")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def buy(code: str, qty: int, price: int, order_type: str, dmst_stex_tp: str, cond_uv: int, confirm: bool):
    """주식 매수주문 (kt10000).

    예: kiwoom order buy 005930 10 --price 70000 --type limit --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("매수", code, qty, price, order_type, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10000", {
            "dmst_stex_tp": dmst_stex_tp,
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price else "",
            "trde_tp": ORDER_TYPES[order_type],
            "cond_uv": str(cond_uv) if cond_uv else "",
        })
        print_order_result(data, "매수")


@order.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=int, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default="market", type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격 (스톱지정가 등)")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def sell(code: str, qty: int, price: int, order_type: str, dmst_stex_tp: str, cond_uv: int, confirm: bool):
    """주식 매도주문 (kt10001).

    예: kiwoom order sell 005930 10 --type market --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("매도", code, qty, price, order_type, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10001", {
            "dmst_stex_tp": dmst_stex_tp,
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price else "",
            "trde_tp": ORDER_TYPES[order_type],
            "cond_uv": str(cond_uv) if cond_uv else "",
        })
        print_order_result(data, "매도")


@order.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=int)
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "mdfy_cond_uv", type=int, default=0, help="정정 조건부가격")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def modify(orig_order_no: str, code: str, qty: int, price: int, dmst_stex_tp: str, mdfy_cond_uv: int, confirm: bool):
    """주식 정정주문 (kt10002).

    예: kiwoom order modify 0000139 005930 1 70000 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_modify_preview("정정", orig_order_no, code, qty, price, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10002", {
            "dmst_stex_tp": dmst_stex_tp,
            "orig_ord_no": orig_order_no,
            "stk_cd": code,
            "mdfy_qty": str(qty),
            "mdfy_uv": str(price),
            "mdfy_cond_uv": str(mdfy_cond_uv) if mdfy_cond_uv else "",
        })
        print_order_result(data, "정정")


@order.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def cancel(orig_order_no: str, code: str, qty: int, dmst_stex_tp: str, confirm: bool):
    """주식 취소주문 (kt10003).

    예: kiwoom order cancel 0000140 005930 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_cancel_preview("취소", orig_order_no, code, qty, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10003", {
            "dmst_stex_tp": dmst_stex_tp,
            "orig_ord_no": orig_order_no,
            "stk_cd": code,
            "cncl_qty": str(qty),
        })
        print_order_result(data, "취소")


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
@click.option("--price", type=int, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default="market", type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def credit_buy(code: str, qty: int, price: int, order_type: str, dmst_stex_tp: str, cond_uv: int, confirm: bool):
    """신용 매수주문 (kt10006).

    예: kiwoom order credit buy 005930 10 --type limit --price 70000 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("신용 매수", code, qty, price, order_type, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10006", {
            "dmst_stex_tp": dmst_stex_tp,
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price else "",
            "trde_tp": ORDER_TYPES[order_type],
            "cond_uv": str(cond_uv) if cond_uv else "",
        })
        print_order_result(data, "신용 매수")


@credit.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=int, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default="market", type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def credit_sell(code: str, qty: int, price: int, order_type: str, dmst_stex_tp: str, cond_uv: int, confirm: bool):
    """신용 매도주문 (kt10007).

    예: kiwoom order credit sell 005930 10 --type market --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("신용 매도", code, qty, price, order_type, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10007", {
            "dmst_stex_tp": dmst_stex_tp,
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price else "",
            "trde_tp": ORDER_TYPES[order_type],
            "cond_uv": str(cond_uv) if cond_uv else "",
        })
        print_order_result(data, "신용 매도")


@credit.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=int)
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "mdfy_cond_uv", type=int, default=0, help="정정 조건부가격")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def credit_modify(orig_order_no: str, code: str, qty: int, price: int, dmst_stex_tp: str, mdfy_cond_uv: int, confirm: bool):
    """신용 정정주문 (kt10008).

    예: kiwoom order credit modify 0000139 005930 1 70000 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_modify_preview("신용 정정", orig_order_no, code, qty, price, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10008", {
            "dmst_stex_tp": dmst_stex_tp,
            "orig_ord_no": orig_order_no,
            "stk_cd": code,
            "mdfy_qty": str(qty),
            "mdfy_uv": str(price),
            "mdfy_cond_uv": str(mdfy_cond_uv) if mdfy_cond_uv else "",
        })
        print_order_result(data, "신용 정정")


@credit.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def credit_cancel(orig_order_no: str, code: str, qty: int, dmst_stex_tp: str, confirm: bool):
    """신용 취소주문 (kt10009).

    예: kiwoom order credit cancel 0000140 005930 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_cancel_preview("신용 취소", orig_order_no, code, qty, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10009", {
            "dmst_stex_tp": dmst_stex_tp,
            "orig_ord_no": orig_order_no,
            "stk_cd": code,
            "cncl_qty": str(qty),
        })
        print_order_result(data, "신용 취소")


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
@click.option("--price", type=int, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default="market", type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def gold_buy(code: str, qty: int, price: int, order_type: str, confirm: bool):
    """금현물 매수주문 (kt50000).

    예: kiwoom order gold buy 730060 10 --type limit --price 90000 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("금현물 매수", code, qty, price, order_type)

    with KiwoomClient() as c:
        data, _ = c.request("kt50000", {
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price else "",
            "trde_tp": ORDER_TYPES[order_type],
        })
        print_order_result(data, "금현물 매수")


@gold.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=int, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default="market", type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def gold_sell(code: str, qty: int, price: int, order_type: str, confirm: bool):
    """금현물 매도주문 (kt50001).

    예: kiwoom order gold sell 730060 10 --type market --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("금현물 매도", code, qty, price, order_type)

    with KiwoomClient() as c:
        data, _ = c.request("kt50001", {
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(price) if price else "",
            "trde_tp": ORDER_TYPES[order_type],
        })
        print_order_result(data, "금현물 매도")


@gold.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=int)
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def gold_modify(orig_order_no: str, code: str, qty: int, price: int, confirm: bool):
    """금현물 정정주문 (kt50002).

    예: kiwoom order gold modify 0000139 730060 1 90000 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_modify_preview("금현물 정정", orig_order_no, code, qty, price)

    with KiwoomClient() as c:
        data, _ = c.request("kt50002", {
            "orig_ord_no": orig_order_no,
            "stk_cd": code,
            "mdfy_qty": str(qty),
            "mdfy_uv": str(price),
        })
        print_order_result(data, "금현물 정정")


@gold.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소)")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def gold_cancel(orig_order_no: str, code: str, qty: int, confirm: bool):
    """금현물 취소주문 (kt50003).

    예: kiwoom order gold cancel 0000140 730060 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_cancel_preview("금현물 취소", orig_order_no, code, qty)

    with KiwoomClient() as c:
        data, _ = c.request("kt50003", {
            "orig_ord_no": orig_order_no,
            "stk_cd": code,
            "cncl_qty": str(qty),
        })
        print_order_result(data, "금현물 취소")


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
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def condition_search(seq: str, stex_tp: str, cont_yn: str, next_key: str, confirm: bool):
    """조건검색 요청 일반 (ka10172).

    예: kiwoom order condition search 001 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

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
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def condition_realtime(seq: str, stex_tp: str, confirm: bool):
    """조건검색 요청 실시간 (ka10173).

    예: kiwoom order condition realtime 001 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

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
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def condition_stop(seq: str, confirm: bool):
    """조건검색 실시간 해제 (ka10174).

    예: kiwoom order condition stop 001 --confirm
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    with KiwoomClient() as c:
        data, _ = c.request("ka10174", {
            "trnm": "CNSRCLR",
            "seq": seq,
        })
        print_generic_table(data, title="조건검색 실시간 해제")
