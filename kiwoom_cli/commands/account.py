"""Account management commands."""

from __future__ import annotations

from datetime import datetime

import click

from ..client import KiwoomClient
from ..formatters import (
    print_account_eval,
    print_deposit,
    print_generic_table,
    print_pending_orders,
)


def _today() -> str:
    """Return today's date as YYYYMMDD."""
    return datetime.now().strftime("%Y%m%d")


def _find_list(data: dict) -> list | None:
    """Find the first list value in API response."""
    for k, v in data.items():
        if isinstance(v, list) and k not in ("return_code", "return_msg"):
            return v
    return None


@click.group("account")
def account():
    """계좌 정보 조회."""
    pass


# ── Top-level account commands ───────────────────────


@account.command("list")
def account_list():
    """계좌번호 목록 조회. (ka00001)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka00001", {})
        acct = data.get("acctNo", "")
        if acct:
            click.echo(f"계좌번호: {acct}")
        else:
            print_generic_table(data, title="계좌번호")


@account.command("balance")
@click.option("--exchange", "stex", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 구분")
@click.option("--delist", "qry_tp", default="0", type=click.Choice(["0", "1"]), help="상장폐지조회구분 (0=전체, 1=제외)")
def balance(stex: str, qry_tp: str):
    """계좌 평가현황 (잔고, 보유종목, 손익). (kt00004)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00004", {"qry_tp": qry_tp, "dmst_stex_tp": stex})
        print_account_eval(data)


@account.command("deposit")
@click.option("--type", "qry_type", type=click.Choice(["estimate", "normal"]), default="estimate", help="조회구분 (estimate=추정조회, normal=일반조회)")
def deposit(qry_type: str):
    """예수금 상세현황 조회. (kt00001)"""
    tp_map = {"estimate": "3", "normal": "2"}
    with KiwoomClient() as c:
        data, _ = c.request("kt00001", {"qry_tp": tp_map[qry_type]})
        print_deposit(data)


@account.command("asset")
@click.option("--delist", "qry_tp", default="0", type=click.Choice(["0", "1"]), help="상장폐지조회구분 (0=전체, 1=제외)")
def asset(qry_tp: str):
    """추정자산 조회. (kt00003)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00003", {"qry_tp": qry_tp})
        print_generic_table(data, title="추정자산")


@account.command("today")
def today_status():
    """계좌별 당일현황 조회. (kt00017)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00017", {})
        print_generic_table(data, title="계좌별 당일현황")


@account.command("margin-detail")
def margin_detail():
    """증거금 세부내역 조회. (kt00013)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00013", {})
        print_generic_table(data, title="증거금 세부내역")


# ── Returns (수익률) ─────────────────────────────────


@account.group("returns")
def returns():
    """수익률 관련 조회."""
    pass


@returns.command("summary")
@click.option("--exchange", "stex", default="0", type=click.Choice(["0", "1", "2"]), help="거래소구분 (0=통합, 1=KRX, 2=NXT)")
def returns_summary(stex: str):
    """계좌 수익률 조회. (ka10085)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10085", {"stex_tp": stex})
        print_generic_table(data, title="계좌 수익률")


@returns.command("daily-balance")
@click.option("--date", "qry_dt", default=None, help="조회일자 (YYYYMMDD, 기본=오늘)")
def daily_balance_returns(qry_dt: str | None):
    """일별 잔고수익률 조회. (ka01690)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka01690", {"qry_dt": qry_dt or _today()})
        items = _find_list(data)
        if isinstance(items, list):
            print_generic_table(items, title="일별 잔고수익률")
        else:
            print_generic_table(data, title="일별 잔고수익률")


@returns.command("daily-detail")
@click.option("--from", "fr_dt", required=True, help="평가시작일 (YYYYMMDD)")
@click.option("--to", "to_dt", required=True, help="평가종료일 (YYYYMMDD)")
def daily_returns_detail(fr_dt: str, to_dt: str):
    """일별 계좌수익률 상세현황. (kt00016)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00016", {"fr_dt": fr_dt, "to_dt": to_dt})
        print_generic_table(data, title="일별 계좌수익률 상세현황")


@returns.command("daily-asset")
@click.option("--from", "start_dt", required=True, help="시작조회기간 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료조회기간 (YYYYMMDD)")
def daily_estimated_asset(start_dt: str, end_dt: str):
    """일별 추정예탁자산 현황. (kt00002)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00002", {"start_dt": start_dt, "end_dt": end_dt})
        print_generic_table(data, title="일별 추정예탁자산 현황")


# ── PnL (손익) ───────────────────────────────────────


@account.group("pnl")
def pnl():
    """실현손익 관련 조회."""
    pass


@pnl.command("today")
@click.argument("code")
def pnl_today(code: str):
    """당일 실현손익 상세 (종목코드 필수). (ka10077)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10077", {"stk_cd": code})
        print_generic_table(data, title="당일 실현손익 상세")


@pnl.command("by-date")
@click.option("--code", "stk_cd", default="", help="종목코드 (미입력시 전체)")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
def pnl_by_date(stk_cd: str, strt_dt: str):
    """일자별 종목별 실현손익 (일자 기준). (ka10072)"""
    with KiwoomClient() as c:
        body: dict = {"strt_dt": strt_dt}
        if stk_cd:
            body["stk_cd"] = stk_cd
        data, _ = c.request("ka10072", body)
        print_generic_table(data, title="일자별 종목별 실현손익 (일자)")


@pnl.command("by-period")
@click.option("--code", "stk_cd", default="", help="종목코드 (미입력시 전체)")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
def pnl_by_period(stk_cd: str, strt_dt: str, end_dt: str):
    """일자별 종목별 실현손익 (기간 기준). (ka10073)"""
    with KiwoomClient() as c:
        body: dict = {"strt_dt": strt_dt, "end_dt": end_dt}
        if stk_cd:
            body["stk_cd"] = stk_cd
        data, _ = c.request("ka10073", body)
        print_generic_table(data, title="일자별 종목별 실현손익 (기간)")


@pnl.command("daily")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
def pnl_daily(strt_dt: str, end_dt: str):
    """일자별 실현손익. (ka10074)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10074", {"strt_dt": strt_dt, "end_dt": end_dt})
        print_generic_table(data, title="일자별 실현손익")


# ── Orders (주문 조회) ──────────────────────────────


@account.group("orders")
def orders():
    """주문/체결/미체결 조회."""
    pass


@orders.command("pending")
@click.option("--all-stocks", "all_stk_tp", default="0", type=click.Choice(["0", "1"]), help="전체종목구분 (0=전체, 1=종목)")
@click.option("--trade", "trde_tp", default="0", type=click.Choice(["0", "1", "2"]), help="매매구분 (0=전체, 1=매도, 2=매수)")
@click.option("--code", "stk_cd", default="", help="종목코드 (미입력시 전체)")
@click.option("--exchange", "stex_tp", default="0", type=click.Choice(["0", "1", "2"]), help="거래소구분 (0=통합, 1=KRX, 2=NXT)")
def orders_pending(all_stk_tp: str, trde_tp: str, stk_cd: str, stex_tp: str):
    """미체결 주문 조회. (ka10075)"""
    with KiwoomClient() as c:
        body: dict = {
            "all_stk_tp": all_stk_tp,
            "trde_tp": trde_tp,
            "stex_tp": stex_tp,
        }
        if stk_cd:
            body["stk_cd"] = stk_cd
        data, _ = c.request("ka10075", body)
        items = _find_list(data)
        if isinstance(items, list):
            print_pending_orders(items)
        else:
            print_generic_table(data, title="미체결")


@orders.command("executed")
@click.option("--code", "stk_cd", default="", help="종목코드 (미입력시 전체)")
@click.option("--qry-type", "qry_tp", default="0", type=click.Choice(["0", "1"]), help="조회구분 (0=전체, 1=종목)")
@click.option("--side", "sell_tp", default="0", type=click.Choice(["0", "1", "2"]), help="매도수구분 (0=전체, 1=매도, 2=매수)")
@click.option("--order-no", "ord_no", default="", help="주문번호")
@click.option("--exchange", "stex_tp", default="0", type=click.Choice(["0", "1", "2"]), help="거래소구분 (0=통합, 1=KRX, 2=NXT)")
def orders_executed(stk_cd: str, qry_tp: str, sell_tp: str, ord_no: str, stex_tp: str):
    """체결 내역 조회. (ka10076)"""
    with KiwoomClient() as c:
        body: dict = {
            "qry_tp": qry_tp,
            "sell_tp": sell_tp,
            "stex_tp": stex_tp,
        }
        if stk_cd:
            body["stk_cd"] = stk_cd
        if ord_no:
            body["ord_no"] = ord_no
        data, _ = c.request("ka10076", body)
        items = _find_list(data)
        if isinstance(items, list):
            print_generic_table(items, title="체결 내역")
        else:
            print_generic_table(data, title="체결 내역")


@orders.command("split-detail")
@click.argument("order_no")
def orders_split_detail(order_no: str):
    """미체결 분할주문 상세 조회. (ka10088)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10088", {"ord_no": order_no})
        print_generic_table(data, title="미체결 분할주문 상세")


@orders.command("detail")
@click.option("--date", "ord_dt", default="", help="주문일자 (YYYYMMDD, 미입력시 당일)")
@click.option("--qry-type", "qry_tp", default="1", type=click.Choice(["1", "2", "3", "4"]), help="조회구분 (1=주문순, 2=역순, 3=미체결, 4=체결내역만)")
@click.option("--asset", "stk_bond_tp", default="0", type=click.Choice(["0", "1", "2"]), help="주식채권구분 (0=전체, 1=주식, 2=채권)")
@click.option("--side", "sell_tp", default="0", type=click.Choice(["0", "1", "2"]), help="매도수구분 (0=전체, 1=매도, 2=매수)")
@click.option("--code", "stk_cd", default="", help="종목코드")
@click.option("--from-order", "fr_ord_no", default="", help="시작주문번호")
@click.option("--exchange", "dmst_stex_tp", default="%", type=click.Choice(["%", "KRX", "NXT", "SOR"]), help="거래소구분 (%=전체)")
def orders_detail(ord_dt: str, qry_tp: str, stk_bond_tp: str, sell_tp: str, stk_cd: str, fr_ord_no: str, dmst_stex_tp: str):
    """계좌별 주문체결내역 상세. (kt00007)"""
    with KiwoomClient() as c:
        body: dict = {
            "qry_tp": qry_tp,
            "stk_bond_tp": stk_bond_tp,
            "sell_tp": sell_tp,
            "dmst_stex_tp": dmst_stex_tp,
        }
        if ord_dt:
            body["ord_dt"] = ord_dt
        if stk_cd:
            body["stk_cd"] = stk_cd
        if fr_ord_no:
            body["fr_ord_no"] = fr_ord_no
        data, _ = c.request("kt00007", body)
        print_generic_table(data, title="계좌별 주문체결내역 상세")


@orders.command("status")
@click.option("--date", "ord_dt", default="", help="주문일자 (YYYYMMDD, 미입력시 당일)")
@click.option("--asset", "stk_bond_tp", default="0", type=click.Choice(["0", "1", "2"]), help="주식채권구분 (0=전체, 1=주식, 2=채권)")
@click.option("--market", "mrkt_tp", default="0", type=click.Choice(["0", "1", "2"]), help="시장구분 (0=전체, 1=코스피, 2=코스닥)")
@click.option("--side", "sell_tp", default="0", type=click.Choice(["0", "1", "2"]), help="매도수구분 (0=전체, 1=매도, 2=매수)")
@click.option("--qry-type", "qry_tp", default="0", type=click.Choice(["0", "1"]), help="조회구분 (0=전체, 1=체결)")
@click.option("--code", "stk_cd", default="", help="종목코드")
@click.option("--from-order", "fr_ord_no", default="", help="시작주문번호")
@click.option("--exchange", "dmst_stex_tp", default="%", type=click.Choice(["%", "KRX", "NXT", "SOR"]), help="거래소구분 (%=전체)")
def orders_status(ord_dt: str, stk_bond_tp: str, mrkt_tp: str, sell_tp: str, qry_tp: str, stk_cd: str, fr_ord_no: str, dmst_stex_tp: str):
    """계좌별 주문체결현황. (kt00009)"""
    with KiwoomClient() as c:
        body: dict = {
            "stk_bond_tp": stk_bond_tp,
            "mrkt_tp": mrkt_tp,
            "sell_tp": sell_tp,
            "qry_tp": qry_tp,
            "dmst_stex_tp": dmst_stex_tp,
        }
        if ord_dt:
            body["ord_dt"] = ord_dt
        if stk_cd:
            body["stk_cd"] = stk_cd
        if fr_ord_no:
            body["fr_ord_no"] = fr_ord_no
        data, _ = c.request("kt00009", body)
        print_generic_table(data, title="계좌별 주문체결현황")


# ── Holdings (잔고) ──────────────────────────────────


@account.group("holdings")
def holdings():
    """잔고 및 평가 조회."""
    pass


@holdings.command("eval")
@click.option("--qry-type", "qry_tp", default="1", type=click.Choice(["1", "2"]), help="조회구분 (1=합산, 2=개별)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 구분")
def holdings_eval(qry_tp: str, dmst_stex_tp: str):
    """계좌평가 잔고내역. (kt00018)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00018", {"qry_tp": qry_tp, "dmst_stex_tp": dmst_stex_tp})
        print_generic_table(data, title="계좌평가 잔고내역")


@holdings.command("settled")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 구분")
def holdings_settled(dmst_stex_tp: str):
    """체결잔고 조회. (kt00005)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt00005", {"dmst_stex_tp": dmst_stex_tp})
        print_generic_table(data, title="체결잔고")


@holdings.command("next-settle")
@click.option("--from-seq", "strt_dcd_seq", default="", help="시작결제번호")
def holdings_next_settle(strt_dcd_seq: str):
    """계좌별 익일결제예정 내역. (kt00008)"""
    with KiwoomClient() as c:
        body: dict = {}
        if strt_dcd_seq:
            body["strt_dcd_seq"] = strt_dcd_seq
        data, _ = c.request("kt00008", body)
        print_generic_table(data, title="계좌별 익일결제예정 내역")


# ── Orderable (주문 가능) ────────────────────────────


@account.group("orderable")
def orderable():
    """주문 가능 금액/수량 조회."""
    pass


@orderable.command("amount")
@click.argument("code")
@click.option("--side", "trde_tp", required=True, type=click.Choice(["sell", "buy"]), help="매매구분 (sell=매도, buy=매수)")
@click.option("--price", "uv", required=True, help="매수가격")
@click.option("--io-amount", "io_amt", default="", help="입출금액")
@click.option("--qty", "trde_qty", default="", help="매매수량")
@click.option("--est-price", "exp_buy_unp", default="", help="예상매수단가")
def orderable_amount(code: str, trde_tp: str, uv: str, io_amt: str, trde_qty: str, exp_buy_unp: str):
    """주문 인출가능 금액 조회. (kt00010)"""
    _side_map = {"sell": "1", "buy": "2"}
    with KiwoomClient() as c:
        body: dict = {
            "stk_cd": code,
            "trde_tp": _side_map[trde_tp],
            "uv": uv,
        }
        if io_amt:
            body["io_amt"] = io_amt
        if trde_qty:
            body["trde_qty"] = trde_qty
        if exp_buy_unp:
            body["exp_buy_unp"] = exp_buy_unp
        data, _ = c.request("kt00010", body)
        print_generic_table(data, title="주문 인출가능 금액")


@orderable.command("margin-qty")
@click.argument("code")
@click.option("--price", "uv", default="", help="매수가격")
def orderable_margin_qty(code: str, uv: str):
    """증거금율별 주문가능 수량 조회. (kt00011)"""
    with KiwoomClient() as c:
        body: dict = {"stk_cd": code}
        if uv:
            body["uv"] = uv
        data, _ = c.request("kt00011", body)
        print_generic_table(data, title="증거금율별 주문가능 수량")


@orderable.command("credit-qty")
@click.argument("code")
@click.option("--price", "uv", default="", help="매수가격")
def orderable_credit_qty(code: str, uv: str):
    """신용보증금율별 주문가능 수량 조회. (kt00012)"""
    with KiwoomClient() as c:
        body: dict = {"stk_cd": code}
        if uv:
            body["uv"] = uv
        data, _ = c.request("kt00012", body)
        print_generic_table(data, title="신용보증금율별 주문가능 수량")


# ── History (거래내역) ───────────────────────────────


@account.group("history")
def history():
    """거래내역 및 매매일지."""
    pass


@history.command("transactions")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
@click.option("--type", "tp", default="0", type=click.Choice(["0", "1", "2", "3", "4", "5", "6", "7"]), help="구분 (0=전체, 1=입출금, 2=입출고, 3=매매, 4=매수, 5=매도, 6=입금, 7=출금)")
@click.option("--code", "stk_cd", default="", help="종목코드")
@click.option("--currency", "crnc_cd", default="", help="통화코드")
@click.option("--product", "gds_tp", default="0", type=click.Choice(["0", "1"]), help="상품구분 (0=전체, 1=국내주식)")
@click.option("--foreign-exchange", "frgn_stex_code", default="", help="해외거래소코드")
@click.option("--exchange", "dmst_stex_tp", default="%", type=click.Choice(["%", "KRX", "NXT"]), help="거래소구분 (%=전체)")
def history_transactions(strt_dt: str, end_dt: str, tp: str, stk_cd: str, crnc_cd: str, gds_tp: str, frgn_stex_code: str, dmst_stex_tp: str):
    """위탁 종합거래내역 조회. (kt00015)"""
    with KiwoomClient() as c:
        body: dict = {
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "tp": tp,
            "gds_tp": gds_tp,
            "dmst_stex_tp": dmst_stex_tp,
        }
        if stk_cd:
            body["stk_cd"] = stk_cd
        if crnc_cd:
            body["crnc_cd"] = crnc_cd
        if frgn_stex_code:
            body["frgn_stex_code"] = frgn_stex_code
        data, _ = c.request("kt00015", body)
        print_generic_table(data, title="위탁 종합거래내역")


@history.command("journal")
@click.option("--date", "base_dt", default="", help="기준일자 (YYYYMMDD, 미입력시 당일)")
@click.option("--odd-lot", "ottks_tp", default="1", type=click.Choice(["1", "2"]), help="단주구분 (1=당일매수에 대한 당일매도, 2=당일매도 전체)")
@click.option("--cash-credit", "ch_crd_tp", default="0", type=click.Choice(["0", "1", "2"]), help="현금신용구분 (0=전체, 1=현금매매만, 2=신용매매만)")
def history_journal(base_dt: str, ottks_tp: str, ch_crd_tp: str):
    """당일 매매일지 조회. (ka10170)"""
    with KiwoomClient() as c:
        body: dict = {
            "ottks_tp": ottks_tp,
            "ch_crd_tp": ch_crd_tp,
        }
        if base_dt:
            body["base_dt"] = base_dt
        data, _ = c.request("ka10170", body)
        print_generic_table(data, title="당일 매매일지")
