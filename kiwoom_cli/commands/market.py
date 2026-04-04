"""Market rankings, sectors, themes, ETF, ELW, gold, and program trading commands."""

from __future__ import annotations

import click

from ..client import KiwoomClient
from ..formatters import print_api_response
from ._constants import (
    EXCHANGE_TWO,
    MARKET_ALL,
    MARKET_KOSPI_KOSDAQ,
    MARKET_TWO,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Top-level group
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@click.group("market")
def market():
    """시장 정보 (순위, 업종, 테마, ETF, ELW, 금현물, 프로그램매매)."""
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Rankings  (순위정보)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@market.group("rank")
def rank():
    """순위 정보 조회."""
    pass


# ── ka10016  신고저가 ────────────────────────────────


@rank.command("new-highlow")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "ntl_tp", default="1", help="신고저구분 (1=신고가, 2=신저가)")
@click.option("--basis", "high_low_close_tp", default="1", help="기준 (1=고저기준, 2=종가기준)")
@click.option("--period", "dt", default="5", help="기간 (5,10,20,60,250)")
@click.option("--stk-cnd", default="0", help="종목조건 (0=전체)")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--include-limit", "updown_incls", default="0", help="상하한포함 (0=미포함, 1=포함)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_new_highlow(mrkt_tp, ntl_tp, high_low_close_tp, dt, stk_cnd, trde_qty_tp, crd_cnd, updown_incls, stex_tp):
    """신고저가 순위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10016", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "ntl_tp": ntl_tp,
            "high_low_close_tp": high_low_close_tp, "stk_cnd": stk_cnd,
            "trde_qty_tp": trde_qty_tp, "crd_cnd": crd_cnd,
            "updown_incls": updown_incls, "dt": dt, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "신고저가")


# ── ka10017  상하한가 ────────────────────────────────


@rank.command("limit")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "updown_tp", default="1", help="상하한구분 (1=상한,2=상승,3=보합,4=하한,5=하락,6=전일상한,7=전일하한)")
@click.option("--sort", "sort_tp", default="2", help="정렬 (1=종목코드순,2=연속횟수순,3=등락률순)")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--trade-gold", "trde_gold_tp", default="0", help="매매금구분")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_limit(mrkt_tp, updown_tp, sort_tp, stk_cnd, trde_qty_tp, crd_cnd, trde_gold_tp, stex_tp):
    """상하한가 순위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10017", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "updown_tp": updown_tp, "sort_tp": sort_tp,
            "stk_cnd": stk_cnd, "trde_qty_tp": trde_qty_tp, "crd_cnd": crd_cnd,
            "trde_gold_tp": trde_gold_tp, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "상하한가")


# ── ka10018  고저가근접 ──────────────────────────────


@rank.command("near-highlow")
@click.option("--type", "high_low_tp", default="1", help="구분 (1=고가, 2=저가)")
@click.option("--rate", "alacc_rt", default="05", help="근접율 (05,10,15,20,25,30)")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_near_highlow(high_low_tp, alacc_rt, mrkt_tp, trde_qty_tp, stk_cnd, crd_cnd, stex_tp):
    """고저가근접 순위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10018", {
            "high_low_tp": high_low_tp, "alacc_rt": alacc_rt,
            "mrkt_tp": MARKET_ALL[mrkt_tp], "trde_qty_tp": trde_qty_tp,
            "stk_cnd": stk_cnd, "crd_cnd": crd_cnd, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "고저가근접")


# ── ka10019  가격급등락 ──────────────────────────────


@rank.command("surge")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "flu_tp", default="1", help="등락구분 (1=급등, 2=급락)")
@click.option("--time-type", "tm_tp", default="1", help="시간구분 (1=분전, 2=일전)")
@click.option("--time", "tm", default="5", help="시간")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--price-cnd", "pric_cnd", default="0", help="가격조건")
@click.option("--include-limit", "updown_incls", default="0", help="상하한포함 (0=미포함, 1=포함)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_surge(mrkt_tp, flu_tp, tm_tp, tm, trde_qty_tp, stk_cnd, crd_cnd, pric_cnd, updown_incls, stex_tp):
    """가격급등락 순위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10019", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "flu_tp": flu_tp, "tm_tp": tm_tp, "tm": tm,
            "trde_qty_tp": trde_qty_tp, "stk_cnd": stk_cnd, "crd_cnd": crd_cnd,
            "pric_cnd": pric_cnd, "updown_incls": updown_incls, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "가격급등락")


# ── ka10020  호가잔량상위 ────────────────────────────


@rank.command("orderbook-top")
@click.option("--market", "mrkt_tp", default="kospi", type=click.Choice(["kospi", "kosdaq"]), help="시장구분")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=순매수잔량순,2=순매도잔량순,3=매수비율순,4=매도비율순)")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_orderbook_top(mrkt_tp, sort_tp, trde_qty_tp, stk_cnd, crd_cnd, stex_tp):
    """호가잔량 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10020", {
            "mrkt_tp": MARKET_TWO[mrkt_tp], "sort_tp": sort_tp,
            "trde_qty_tp": trde_qty_tp, "stk_cnd": stk_cnd,
            "crd_cnd": crd_cnd, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "호가잔량상위")


# ── ka10021  호가잔량급증 ────────────────────────────


@rank.command("orderbook-surge")
@click.option("--market", "mrkt_tp", default="kospi", type=click.Choice(["kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "trde_tp", default="1", help="매매구분 (1=매수잔량, 2=매도잔량)")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=급증량, 2=급증률)")
@click.option("--minutes", "tm_tp", default="5", help="분 입력")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_orderbook_surge(mrkt_tp, trde_tp, sort_tp, tm_tp, trde_qty_tp, stk_cnd, stex_tp):
    """호가잔량 급증."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10021", {
            "mrkt_tp": MARKET_TWO[mrkt_tp], "trde_tp": trde_tp, "sort_tp": sort_tp,
            "tm_tp": tm_tp, "trde_qty_tp": trde_qty_tp,
            "stk_cnd": stk_cnd, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "호가잔량급증")


# ── ka10022  잔량율급증 ──────────────────────────────


@rank.command("balance-rate-surge")
@click.option("--market", "mrkt_tp", default="kospi", type=click.Choice(["kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "rt_tp", default="1", help="비율구분 (1=매수/매도비율, 2=매도/매수비율)")
@click.option("--minutes", "tm_tp", default="5", help="분 입력")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_balance_rate_surge(mrkt_tp, rt_tp, tm_tp, trde_qty_tp, stk_cnd, stex_tp):
    """잔량율 급증."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10022", {
            "mrkt_tp": MARKET_TWO[mrkt_tp], "rt_tp": rt_tp, "tm_tp": tm_tp,
            "trde_qty_tp": trde_qty_tp, "stk_cnd": stk_cnd, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "잔량율급증")


# ── ka10023  거래량급증 ──────────────────────────────


@rank.command("volume-surge")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=급증량,2=급증률,3=급감량,4=급감률)")
@click.option("--time-type", "tm_tp", default="1", help="구분 (1=분, 2=전일)")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--time", "tm", default="", help="시간 (선택)")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--price-type", "pric_tp", default="0", help="가격구분")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_volume_surge(mrkt_tp, sort_tp, tm_tp, trde_qty_tp, tm, stk_cnd, pric_tp, stex_tp):
    """거래량 급증."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10023", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "sort_tp": sort_tp, "tm_tp": tm_tp,
            "trde_qty_tp": trde_qty_tp, "tm": tm, "stk_cnd": stk_cnd,
            "pric_tp": pric_tp, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "거래량급증")


# ── ka10027  전일대비등락률상위 ───────────────────────


@rank.command("change")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=상승률,2=상승폭,3=하락률,4=하락폭,5=보합)")
@click.option("--vol-cnd", "trde_qty_cnd", default="0", help="거래량조건")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--include-limit", "updown_incls", default="0", help="상하한포함 (0=미포함, 1=포함)")
@click.option("--price-cnd", "pric_cnd", default="0", help="가격조건")
@click.option("--amount-cnd", "trde_prica_cnd", default="0", help="거래대금조건")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_change(mrkt_tp, sort_tp, trde_qty_cnd, stk_cnd, crd_cnd, updown_incls, pric_cnd, trde_prica_cnd, stex_tp):
    """전일대비 등락률 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10027", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "sort_tp": sort_tp,
            "trde_qty_cnd": trde_qty_cnd, "stk_cnd": stk_cnd,
            "crd_cnd": crd_cnd, "updown_incls": updown_incls,
            "pric_cnd": pric_cnd, "trde_prica_cnd": trde_prica_cnd,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "등락률상위")


# ── ka10029  예상체결등락률상위 ───────────────────────


@rank.command("expected-change")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=상승률,2=상승폭,3=보합,4=하락률,5=하락폭,6=체결량,7=상한,8=하한)")
@click.option("--vol-cnd", "trde_qty_cnd", default="0", help="거래량조건")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--price-cnd", "pric_cnd", default="0", help="가격조건")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_expected_change(mrkt_tp, sort_tp, trde_qty_cnd, stk_cnd, crd_cnd, pric_cnd, stex_tp):
    """예상체결 등락률 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10029", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "sort_tp": sort_tp,
            "trde_qty_cnd": trde_qty_cnd, "stk_cnd": stk_cnd,
            "crd_cnd": crd_cnd, "pric_cnd": pric_cnd, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "예상체결등락률상위")


# ── ka10030  당일거래량상위 ──────────────────────────


@rank.command("volume")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=거래량,2=거래회전율,3=거래대금)")
@click.option("--include-managed", "mang_stk_incls", default="0", help="관리종목포함 (0=미포함, 1=포함)")
@click.option("--credit-type", "crd_tp", default="0", help="신용구분")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--price-type", "pric_tp", default="0", help="가격구분")
@click.option("--amount-type", "trde_prica_tp", default="0", help="거래대금구분")
@click.option("--session", "mrkt_open_tp", default="0", help="장운영구분 (0=전체,1=장중,2=장전시간외,3=장후시간외)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_volume(mrkt_tp, sort_tp, mang_stk_incls, crd_tp, trde_qty_tp, pric_tp, trde_prica_tp, mrkt_open_tp, stex_tp):
    """당일 거래량 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10030", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "sort_tp": sort_tp,
            "mang_stk_incls": mang_stk_incls, "crd_tp": crd_tp,
            "trde_qty_tp": trde_qty_tp, "pric_tp": pric_tp,
            "trde_prica_tp": trde_prica_tp, "mrkt_open_tp": mrkt_open_tp,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "당일거래량상위")


# ── ka10031  전일거래량상위 ──────────────────────────


@rank.command("prev-volume")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "qry_tp", default="1", help="조회구분 (1=전일거래량, 2=전일거래대금)")
@click.option("--rank-start", "rank_strt", default="1", help="순위시작")
@click.option("--rank-end", "rank_end", default="50", help="순위끝")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_prev_volume(mrkt_tp, qry_tp, rank_strt, rank_end, stex_tp):
    """전일 거래량 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10031", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "qry_tp": qry_tp,
            "rank_strt": rank_strt, "rank_end": rank_end,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "전일거래량상위")


# ── ka10032  거래대금상위 ────────────────────────────


@rank.command("amount")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--include-managed", "mang_stk_incls", default="0", help="관리종목포함 (0=미포함, 1=포함)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_amount(mrkt_tp, mang_stk_incls, stex_tp):
    """거래대금 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10032", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "mang_stk_incls": mang_stk_incls,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "거래대금상위")


# ── ka10033  신용비율상위 ────────────────────────────


@rank.command("credit-ratio")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--include-limit", "updown_incls", default="0", help="상하한포함")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_credit_ratio(mrkt_tp, trde_qty_tp, stk_cnd, updown_incls, crd_cnd, stex_tp):
    """신용비율 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10033", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "trde_qty_tp": trde_qty_tp,
            "stk_cnd": stk_cnd, "updown_incls": updown_incls,
            "crd_cnd": crd_cnd, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "신용비율상위")


# ── ka10034  외인기간별매매상위 ───────────────────────


@rank.command("foreign-period")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "trde_tp", default="2", help="매매구분 (1=순매도, 2=순매수, 3=순매매)")
@click.option("--period", "dt", default="0", help="기간 (0=당일,1=전일,5=5일,10,20,60)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_foreign_period(mrkt_tp, trde_tp, dt, stex_tp):
    """외인 기간별 매매 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10034", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "trde_tp": trde_tp,
            "dt": dt, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "외인기간별매매상위")


# ── ka10035  외인연속순매매상위 ───────────────────────


@rank.command("foreign-consecutive")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "trde_tp", default="2", help="구분 (1=연속순매도, 2=연속순매수)")
@click.option("--base-date", "base_dt_tp", default="0", help="기준일구분 (0=당일, 1=전일)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_foreign_consecutive(mrkt_tp, trde_tp, base_dt_tp, stex_tp):
    """외인 연속 순매매 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10035", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "trde_tp": trde_tp,
            "base_dt_tp": base_dt_tp, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "외인연속순매매상위")


# ── ka10036  외인한도소진율증가상위 ───────────────────


@rank.command("foreign-exhaust")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--period", "dt", default="0", help="기간 (0=당일,1=전일,5=5일,10,20,60)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_foreign_exhaust(mrkt_tp, dt, stex_tp):
    """외인 한도소진율 증가 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10036", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "dt": dt, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "외인한도소진율증가상위")


# ── ka10037  외국계창구매매상위 ───────────────────────


@rank.command("foreign-broker")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--period", "dt", default="0", help="기간")
@click.option("--type", "trde_tp", default="1", help="매매구분 (1=순매수,2=순매도,3=매수,4=매도)")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=금액, 2=수량)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_foreign_broker(mrkt_tp, dt, trde_tp, sort_tp, stex_tp):
    """외국계 창구 매매 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10037", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "dt": dt, "trde_tp": trde_tp,
            "sort_tp": sort_tp, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "외국계창구매매상위")


# ── ka10038  종목별증권사순위 ────────────────────────


@rank.command("broker-by-stock")
@click.argument("code")
@click.option("--type", "qry_tp", default="1", help="조회구분 (1=순매도순위, 2=순매수순위)")
@click.option("--from", "strt_dt", default="", help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", default="", help="종료일자 (YYYYMMDD)")
@click.option("--period", "dt", default="1", help="기간 (1=전일,4=5일,9=10일,19=20일,39=40일,59=60일,119=120일)")
def rank_broker_by_stock(code, qry_tp, strt_dt, end_dt, dt):
    """종목별 증권사 순위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10038", {
            "stk_cd": code, "strt_dt": strt_dt, "end_dt": end_dt,
            "qry_tp": qry_tp, "dt": dt,
        })
        print_api_response(data, f"종목별증권사순위 ({code})")


# ── ka10039  증권사별매매상위 ────────────────────────


@rank.command("broker-top")
@click.argument("broker_code")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--type", "trde_tp", default="1", help="매매구분 (1=순매수, 2=순매도)")
@click.option("--period", "dt", default="1", help="기간 (1=전일,5,10,60)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_broker_top(broker_code, trde_qty_tp, trde_tp, dt, stex_tp):
    """증권사별 매매 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10039", {
            "mmcm_cd": broker_code, "trde_qty_tp": trde_qty_tp,
            "trde_tp": trde_tp, "dt": dt, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, f"증권사별매매상위 ({broker_code})")


# ── ka10040  당일주요거래원 ──────────────────────────


@rank.command("major-trader")
@click.argument("code")
def rank_major_trader(code):
    """당일 주요 거래원."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10040", {"stk_cd": code})
        print_api_response(data, f"당일주요거래원 ({code})")


# ── ka10042  순매수거래원순위 ────────────────────────


@rank.command("net-buyer")
@click.argument("code")
@click.option("--from", "strt_dt", default="", help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", default="", help="종료일자 (YYYYMMDD)")
@click.option("--date-type", "qry_dt_tp", default="0", help="조회일자구분 (0=기간, 1=일자)")
@click.option("--pot-type", "pot_tp", default="0", help="구분 (0=당일, 1=전일)")
@click.option("--period", "dt", default="5", help="기간 (5,10,20,40,60,120)")
@click.option("--sort", "sort_base", default="1", help="정렬기준 (1=종가순, 2=날짜순)")
def rank_net_buyer(code, strt_dt, end_dt, qry_dt_tp, pot_tp, dt, sort_base):
    """순매수 거래원 순위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10042", {
            "stk_cd": code, "strt_dt": strt_dt, "end_dt": end_dt,
            "qry_dt_tp": qry_dt_tp, "pot_tp": pot_tp,
            "dt": dt, "sort_base": sort_base,
        })
        print_api_response(data, f"순매수거래원순위 ({code})")


# ── ka10053  당일상위이탈원 ──────────────────────────


@rank.command("top-exit")
@click.argument("code")
def rank_top_exit(code):
    """당일 상위 이탈원."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10053", {"stk_cd": code})
        print_api_response(data, f"당일상위이탈원 ({code})")


# ── ka10062  동일순매매순위 ──────────────────────────


@rank.command("same-net-trade")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", default="", help="종료일자 (YYYYMMDD)")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--type", "trde_tp", default="1", help="매매구분 (1=순매수, 2=순매도)")
@click.option("--sort", "sort_cnd", default="1", help="정렬조건 (1=수량, 2=금액)")
@click.option("--unit", "unit_tp", default="1", help="단위 (1=단주, 1000=천주)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_same_net_trade(strt_dt, end_dt, mrkt_tp, trde_tp, sort_cnd, unit_tp, stex_tp):
    """동일 순매매 순위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10062", {
            "strt_dt": strt_dt, "end_dt": end_dt, "mrkt_tp": MARKET_ALL[mrkt_tp],
            "trde_tp": trde_tp, "sort_cnd": sort_cnd,
            "unit_tp": unit_tp, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "동일순매매순위")


# ── ka10065  장중투자자별매매상위 ─────────────────────


@rank.command("investor-top")
@click.option("--type", "trde_tp", default="1", help="매매구분 (1=순매수, 2=순매도)")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--investor", "orgn_tp", default="9000", help="기관구분 (9000=외국인, 9999=기관계 등)")
@click.option("--unit", "amt_qty_tp", default="1", help="구분 (1=금액, 2=수량)")
def rank_investor_top(trde_tp, mrkt_tp, orgn_tp, amt_qty_tp):
    """장중 투자자별 매매 상위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10065", {
            "trde_tp": trde_tp, "mrkt_tp": MARKET_ALL[mrkt_tp],
            "orgn_tp": orgn_tp, "amt_qty_tp": amt_qty_tp,
        })
        print_api_response(data, "장중투자자별매매상위")


# ── ka10098  시간외단일가등락율순위 ───────────────────


@rank.command("afterhours-change")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--sort", "sort_base", default="1", help="정렬 (1=상승률,2=상승폭,3=하락률,4=하락폭,5=보합)")
@click.option("--stk-cnd", default="0", help="종목조건")
@click.option("--vol-cnd", "trde_qty_cnd", default="0", help="거래량조건")
@click.option("--credit", "crd_cnd", default="0", help="신용조건")
@click.option("--amount", "trde_prica", default="0", help="거래대금")
def rank_afterhours_change(mrkt_tp, sort_base, stk_cnd, trde_qty_cnd, crd_cnd, trde_prica):
    """시간외 단일가 등락율 순위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10098", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "sort_base": sort_base,
            "stk_cnd": stk_cnd, "trde_qty_cnd": trde_qty_cnd,
            "crd_cnd": crd_cnd, "trde_prica": trde_prica,
        })
        print_api_response(data, "시간외단일가등락율순위")


# ── ka90009  외국인기관매매상위 ───────────────────────


@rank.command("foreign-inst")
@click.option("--market", "mrkt_tp", default="all", type=click.Choice(["all", "kospi", "kosdaq"]), help="시장구분")
@click.option("--unit", "amt_qty_tp", default="1", help="금액/수량 (1=금액, 2=수량)")
@click.option("--date-type", "qry_dt_tp", default="0", help="날짜포함구분 (0=미포함, 1=포함)")
@click.option("--date", default="", help="날짜 (YYYYMMDD)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def rank_foreign_inst(mrkt_tp, amt_qty_tp, qry_dt_tp, date, stex_tp):
    """외국인/기관 매매 상위."""

    with KiwoomClient() as c:
        data, _ = c.request("ka90009", {
            "mrkt_tp": MARKET_ALL[mrkt_tp], "amt_qty_tp": amt_qty_tp,
            "qry_dt_tp": qry_dt_tp, "date": date, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "외국인기관매매상위")


# ── ka00198  실시간종목조회순위 ───────────────────────


@rank.command("hot")
@click.option("--period", "qry_tp", type=click.Choice(["1", "2", "3", "4", "5"]), default="4",
              help="구분 (1=1분, 2=10분, 3=1시간, 4=당일누적, 5=30초)")
def rank_hot(qry_tp):
    """실시간 종목 조회 순위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka00198", {"qry_tp": qry_tp})
        print_api_response(data, "실시간종목조회순위")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sectors  (업종)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@market.group("sector")
def sector():
    """업종 정보 조회."""
    pass


# ── ka10010  업종프로그램 ────────────────────────────


@sector.command("program")
@click.argument("code")
def sector_program(code):
    """업종 프로그램매매."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10010", {"stk_cd": code})
        print_api_response(data, f"업종프로그램 ({code})")


# ── ka10051  업종별투자자순매수 ───────────────────────


@sector.command("investor")
@click.option("--market", "mrkt_tp", default="kospi", type=click.Choice(["kospi", "kosdaq"]), help="시장구분")
@click.option("--unit", "amt_qty_tp", default="0", help="금액/수량 (0=금액, 1=수량)")
@click.option("--date", "base_dt", default="", help="기준일자 (YYYYMMDD)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def sector_investor(mrkt_tp, amt_qty_tp, base_dt, stex_tp):
    """업종별 투자자 순매수."""

    with KiwoomClient() as c:
        data, _ = c.request("ka10051", {
            "mrkt_tp": MARKET_KOSPI_KOSDAQ[mrkt_tp], "amt_qty_tp": amt_qty_tp,
            "base_dt": base_dt, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "업종별투자자순매수")


# ── ka20001  업종현재가 ──────────────────────────────


@sector.command("current")
@click.argument("inds_cd")
@click.option("--market", "mrkt_tp", default="0", help="시장구분 (0=코스피, 1=코스닥, 2=코스피200)")
def sector_current(inds_cd, mrkt_tp):
    """업종 현재가 조회."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20001", {
            "mrkt_tp": mrkt_tp, "inds_cd": inds_cd,
        })
        print_api_response(data, f"업종현재가 ({inds_cd})")


# ── ka20002  업종별주가 ──────────────────────────────


@sector.command("stocks")
@click.argument("inds_cd")
@click.option("--market", "mrkt_tp", default="0", help="시장구분")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def sector_stocks(inds_cd, mrkt_tp, stex_tp):
    """업종별 주가."""

    with KiwoomClient() as c:
        data, _ = c.request("ka20002", {
            "mrkt_tp": mrkt_tp, "inds_cd": inds_cd, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, f"업종별주가 ({inds_cd})")


# ── ka20003  전업종지수 ──────────────────────────────


@sector.command("index")
@click.option("--inds-cd", default="001", help="업종코드 (001=KOSPI종합, 101=KOSDAQ종합)")
def sector_index(inds_cd):
    """전업종 지수."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20003", {"inds_cd": inds_cd})
        print_api_response(data, "전업종지수")


# ── ka20009  업종현재가일별 ──────────────────────────


@sector.command("daily")
@click.argument("inds_cd")
@click.option("--market", "mrkt_tp", default="0", help="시장구분")
def sector_daily(inds_cd, mrkt_tp):
    """업종 현재가 일별."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20009", {
            "mrkt_tp": mrkt_tp, "inds_cd": inds_cd,
        })
        print_api_response(data, f"업종현재가일별 ({inds_cd})")


# ── ka10101  업종코드리스트 ──────────────────────────


@sector.command("codes")
@click.option("--market", "mrkt_tp", default="0", help="시장구분 (0=코스피,1=코스닥,2=KOSPI200,4=KOSPI100,7=KRX100)")
def sector_codes(mrkt_tp):
    """업종코드 리스트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10101", {"mrkt_tp": mrkt_tp})
        print_api_response(data, "업종코드리스트")


# ── Sector Charts (업종차트) ─────────────────────────


@sector.group("chart")
def sector_chart():
    """업종 차트 조회."""
    pass


# ── ka20004  업종틱차트 ──────────────────────────────


@sector_chart.command("tick")
@click.argument("inds_cd")
@click.option("--scope", "tic_scope", default="1", help="틱범위 (1,3,5,10,30)")
def sector_chart_tick(inds_cd, tic_scope):
    """업종 틱차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20004", {
            "inds_cd": inds_cd, "tic_scope": tic_scope,
        })
        print_api_response(data, f"업종틱차트 ({inds_cd})")


# ── ka20005  업종분봉 ────────────────────────────────


@sector_chart.command("minute")
@click.argument("inds_cd")
@click.option("--scope", "tic_scope", default="1", help="틱범위 (1,3,5,10,30)")
@click.option("--date", "base_dt", default="", help="기준일자 (YYYYMMDD)")
def sector_chart_minute(inds_cd, tic_scope, base_dt):
    """업종 분봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20005", {
            "inds_cd": inds_cd, "tic_scope": tic_scope, "base_dt": base_dt,
        })
        print_api_response(data, f"업종분봉 ({inds_cd})")


# ── ka20006  업종일봉 ────────────────────────────────


@sector_chart.command("day")
@click.argument("inds_cd")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
def sector_chart_day(inds_cd, base_dt):
    """업종 일봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20006", {
            "inds_cd": inds_cd, "base_dt": base_dt,
        })
        print_api_response(data, f"업종일봉 ({inds_cd})")


# ── ka20007  업종주봉 ────────────────────────────────


@sector_chart.command("week")
@click.argument("inds_cd")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
def sector_chart_week(inds_cd, base_dt):
    """업종 주봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20007", {
            "inds_cd": inds_cd, "base_dt": base_dt,
        })
        print_api_response(data, f"업종주봉 ({inds_cd})")


# ── ka20008  업종월봉 ────────────────────────────────


@sector_chart.command("month")
@click.argument("inds_cd")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
def sector_chart_month(inds_cd, base_dt):
    """업종 월봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20008", {
            "inds_cd": inds_cd, "base_dt": base_dt,
        })
        print_api_response(data, f"업종월봉 ({inds_cd})")


# ── ka20019  업종년봉 ────────────────────────────────


@sector_chart.command("year")
@click.argument("inds_cd")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
def sector_chart_year(inds_cd, base_dt):
    """업종 년봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka20019", {
            "inds_cd": inds_cd, "base_dt": base_dt,
        })
        print_api_response(data, f"업종년봉 ({inds_cd})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Theme  (테마)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@market.group("theme")
def theme():
    """테마 정보 조회."""
    pass


# ── ka90001  테마그룹별 ──────────────────────────────


@theme.command("groups")
@click.option("--type", "qry_tp", default="0", help="검색구분 (0=전체, 1=테마검색, 2=종목검색)")
@click.option("--code", "stk_cd", default="", help="종목코드 (종목검색시)")
@click.option("--date-type", "date_tp", default="1", help="날짜구분 (n일전)")
@click.option("--theme-name", "thema_nm", default="", help="테마명 (테마검색시)")
@click.option("--sort", "flu_pl_amt_tp", default="1",
              help="정렬 (1=상위기간수익률,2=하위기간수익률,3=상위등락률,4=하위등락률)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def theme_groups(qry_tp, stk_cd, date_tp, thema_nm, flu_pl_amt_tp, stex_tp):
    """테마 그룹별 조회."""

    with KiwoomClient() as c:
        data, _ = c.request("ka90001", {
            "qry_tp": qry_tp, "stk_cd": stk_cd, "date_tp": date_tp,
            "thema_nm": thema_nm, "flu_pl_amt_tp": flu_pl_amt_tp,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "테마그룹별")


# ── ka90002  테마구성종목 ────────────────────────────


@theme.command("stocks")
@click.argument("theme_code")
@click.option("--date-type", "date_tp", default="1", help="날짜구분 (1~99일)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def theme_stocks(theme_code, date_tp, stex_tp):
    """테마 구성종목 조회."""

    with KiwoomClient() as c:
        data, _ = c.request("ka90002", {
            "date_tp": date_tp, "thema_grp_cd": theme_code,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, f"테마구성종목 ({theme_code})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ETF
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@market.group("etf")
def etf():
    """ETF 정보 조회."""
    pass


# ── ka40001  ETF수익율 ───────────────────────────────


@etf.command("returns")
@click.argument("code")
@click.option("--index", "etfobjt_idex_cd", default="", help="ETF대상지수코드")
@click.option("--period", "dt", default="0", help="기간 (0=1주,1=1달,2=6개월,3=1년)")
def etf_returns(code, etfobjt_idex_cd, dt):
    """ETF 수익율 조회."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40001", {
            "stk_cd": code, "etfobjt_idex_cd": etfobjt_idex_cd, "dt": dt,
        })
        print_api_response(data, f"ETF수익율 ({code})")


# ── ka40002  ETF종목정보 ─────────────────────────────


@etf.command("info")
@click.argument("code")
def etf_info(code):
    """ETF 종목정보."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40002", {"stk_cd": code})
        print_api_response(data, f"ETF종목정보 ({code})")


# ── ka40003  ETF일별추이 ─────────────────────────────


@etf.command("daily")
@click.argument("code")
def etf_daily(code):
    """ETF 일별추이."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40003", {"stk_cd": code})
        print_api_response(data, f"ETF일별추이 ({code})")


# ── ka40004  ETF전체시세 ─────────────────────────────


@etf.command("all")
@click.option("--tax-type", "txon_type", default="0", help="과세유형 (0=전체)")
@click.option("--nav", "navpre", default="0", help="NAV대비 (0=전체)")
@click.option("--company", "mngmcomp", default="0000", help="운용사 (0000=전체)")
@click.option("--taxable", "txon_yn", default="0", help="과세여부 (0=전체)")
@click.option("--index", "trace_idex", default="0", help="추적지수 (0=전체)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def etf_all(txon_type, navpre, mngmcomp, txon_yn, trace_idex, stex_tp):
    """ETF 전체 시세."""

    with KiwoomClient() as c:
        data, _ = c.request("ka40004", {
            "txon_type": txon_type, "navpre": navpre,
            "mngmcomp": mngmcomp, "txon_yn": txon_yn,
            "trace_idex": trace_idex, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "ETF전체시세")


# ── ka40006  ETF시간대별추이 ─────────────────────────


@etf.command("time-trend")
@click.argument("code")
def etf_time_trend(code):
    """ETF 시간대별 추이."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40006", {"stk_cd": code})
        print_api_response(data, f"ETF시간대별추이 ({code})")


# ── ka40007  ETF시간대별체결 ─────────────────────────


@etf.command("time-exec")
@click.argument("code")
def etf_time_exec(code):
    """ETF 시간대별 체결."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40007", {"stk_cd": code})
        print_api_response(data, f"ETF시간대별체결 ({code})")


# ── ka40008  ETF일자별체결 ───────────────────────────


@etf.command("daily-exec")
@click.argument("code")
def etf_daily_exec(code):
    """ETF 일자별 체결."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40008", {"stk_cd": code})
        print_api_response(data, f"ETF일자별체결 ({code})")


# ── ka40009  ETF시간대별체결2 ────────────────────────


@etf.command("time-exec2")
@click.argument("code")
def etf_time_exec2(code):
    """ETF 시간대별 체결 (상세)."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40009", {"stk_cd": code})
        print_api_response(data, f"ETF시간대별체결2 ({code})")


# ── ka40010  ETF시간대별추이2 ────────────────────────


@etf.command("time-trend2")
@click.argument("code")
def etf_time_trend2(code):
    """ETF 시간대별 추이 (상세)."""
    with KiwoomClient() as c:
        data, _ = c.request("ka40010", {"stk_cd": code})
        print_api_response(data, f"ETF시간대별추이2 ({code})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ELW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@market.group("elw")
def elw():
    """ELW 정보 조회."""
    pass


# ── ka10048  ELW일별민감도지표 ────────────────────────


@elw.command("sensitivity-daily")
@click.argument("code")
def elw_sensitivity_daily(code):
    """ELW 일별 민감도 지표."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10048", {"stk_cd": code})
        print_api_response(data, f"ELW일별민감도지표 ({code})")


# ── ka10050  ELW민감도지표 ───────────────────────────


@elw.command("sensitivity")
@click.argument("code")
def elw_sensitivity(code):
    """ELW 민감도 지표."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10050", {"stk_cd": code})
        print_api_response(data, f"ELW민감도지표 ({code})")


# ── ka30001  ELW가격급등락 ───────────────────────────


@elw.command("surge")
@click.option("--type", "flu_tp", default="1", help="등락구분 (1=급등, 2=급락)")
@click.option("--time-type", "tm_tp", default="1", help="시간구분 (1=분전, 2=일전)")
@click.option("--time", "tm", default="5", help="시간")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분 (0=전체)")
@click.option("--issuer", "isscomp_cd", default="000000000000", help="발행사코드 (000000000000=전체)")
@click.option("--underlying", "bsis_aset_cd", default="000000000000", help="기초자산코드 (000000000000=전체)")
@click.option("--right-type", "rght_tp", default="000", help="권리구분 (000=전체)")
@click.option("--lp", "lpcd", default="000000000000", help="LP코드 (000000000000=전체)")
@click.option("--exclude-expired", "trde_end_elwskip", default="1", help="거래종료ELW제외 (0=포함, 1=제외)")
def elw_surge(flu_tp, tm_tp, tm, trde_qty_tp, isscomp_cd, bsis_aset_cd, rght_tp, lpcd, trde_end_elwskip):
    """ELW 가격 급등락."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30001", {
            "flu_tp": flu_tp, "tm_tp": tm_tp, "tm": tm,
            "trde_qty_tp": trde_qty_tp, "isscomp_cd": isscomp_cd,
            "bsis_aset_cd": bsis_aset_cd, "rght_tp": rght_tp,
            "lpcd": lpcd, "trde_end_elwskip": trde_end_elwskip,
        })
        print_api_response(data, "ELW가격급등락")


# ── ka30002  거래원별ELW순매매상위 ────────────────────


@elw.command("broker-top")
@click.option("--issuer", "isscomp_cd", default="000000000000", help="발행사코드")
@click.option("--vol-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--type", "trde_tp", default="1", help="매매구분 (1=순매수, 2=순매도)")
@click.option("--period", "dt", default="1", help="기간 (1=전일,5,10,40,60)")
@click.option("--exclude-expired", "trde_end_elwskip", default="1", help="거래종료ELW제외 (0=포함, 1=제외)")
def elw_broker_top(isscomp_cd, trde_qty_tp, trde_tp, dt, trde_end_elwskip):
    """거래원별 ELW 순매매 상위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30002", {
            "isscomp_cd": isscomp_cd, "trde_qty_tp": trde_qty_tp,
            "trde_tp": trde_tp, "dt": dt,
            "trde_end_elwskip": trde_end_elwskip,
        })
        print_api_response(data, "거래원별ELW순매매상위")


# ── ka30003  ELWLP보유일별추이 ───────────────────────


@elw.command("lp-daily")
@click.argument("underlying_code")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
def elw_lp_daily(underlying_code, base_dt):
    """ELW LP 보유 일별 추이."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30003", {
            "bsis_aset_cd": underlying_code, "base_dt": base_dt,
        })
        print_api_response(data, f"ELWLP보유일별추이 ({underlying_code})")


# ── ka30004  ELW괴리율 ───────────────────────────────


@elw.command("disparity")
@click.option("--issuer", "isscomp_cd", default="000000000000", help="발행사코드")
@click.option("--underlying", "bsis_aset_cd", default="000000000000", help="기초자산코드")
@click.option("--right-type", "rght_tp", default="000", help="권리구분")
@click.option("--lp", "lpcd", default="000000000000", help="LP코드")
@click.option("--exclude-expired", "trde_end_elwskip", default="1", help="거래종료ELW제외 (0=포함, 1=제외)")
def elw_disparity(isscomp_cd, bsis_aset_cd, rght_tp, lpcd, trde_end_elwskip):
    """ELW 괴리율."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30004", {
            "isscomp_cd": isscomp_cd, "bsis_aset_cd": bsis_aset_cd,
            "rght_tp": rght_tp, "lpcd": lpcd,
            "trde_end_elwskip": trde_end_elwskip,
        })
        print_api_response(data, "ELW괴리율")


# ── ka30005  ELW조건검색 ─────────────────────────────


@elw.command("search")
@click.option("--issuer", "isscomp_cd", default="000000000000", help="발행사코드")
@click.option("--underlying", "bsis_aset_cd", default="000000000000", help="기초자산코드")
@click.option("--right-type", "rght_tp", default="0", help="권리구분 (0~7)")
@click.option("--lp", "lpcd", default="000000000000", help="LP코드")
@click.option("--sort", "sort_tp", default="0", help="정렬 (0~7)")
def elw_search(isscomp_cd, bsis_aset_cd, rght_tp, lpcd, sort_tp):
    """ELW 조건 검색."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30005", {
            "isscomp_cd": isscomp_cd, "bsis_aset_cd": bsis_aset_cd,
            "rght_tp": rght_tp, "lpcd": lpcd, "sort_tp": sort_tp,
        })
        print_api_response(data, "ELW조건검색")


# ── ka30009  ELW등락율순위 ───────────────────────────


@elw.command("change-rank")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=상승률,2=상승폭,3=하락률,4=하락폭)")
@click.option("--right-type", "rght_tp", default="000", help="권리구분 (000=전체)")
@click.option("--exclude-expired", "trde_end_skip", default="1", help="거래종료제외 (0=포함, 1=제외)")
def elw_change_rank(sort_tp, rght_tp, trde_end_skip):
    """ELW 등락율 순위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30009", {
            "sort_tp": sort_tp, "rght_tp": rght_tp,
            "trde_end_skip": trde_end_skip,
        })
        print_api_response(data, "ELW등락율순위")


# ── ka30010  ELW잔량순위 ─────────────────────────────


@elw.command("balance-rank")
@click.option("--sort", "sort_tp", default="1", help="정렬 (1=순매수잔량상위, 2=순매도잔량상위)")
@click.option("--right-type", "rght_tp", default="000", help="권리구분 (000=전체)")
@click.option("--exclude-expired", "trde_end_skip", default="1", help="거래종료제외 (0=포함, 1=제외)")
def elw_balance_rank(sort_tp, rght_tp, trde_end_skip):
    """ELW 잔량 순위."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30010", {
            "sort_tp": sort_tp, "rght_tp": rght_tp,
            "trde_end_skip": trde_end_skip,
        })
        print_api_response(data, "ELW잔량순위")


# ── ka30011  ELW근접율 ───────────────────────────────


@elw.command("proximity")
@click.argument("code")
def elw_proximity(code):
    """ELW 근접율."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30011", {"stk_cd": code})
        print_api_response(data, f"ELW근접율 ({code})")


# ── ka30012  ELW종목상세정보 ─────────────────────────


@elw.command("detail")
@click.argument("code")
def elw_detail(code):
    """ELW 종목 상세정보."""
    with KiwoomClient() as c:
        data, _ = c.request("ka30012", {"stk_cd": code})
        print_api_response(data, f"ELW종목상세정보 ({code})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Gold  (금현물)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@market.group("gold")
def gold():
    """금현물 정보 조회."""
    pass


# ── ka50010  금현물체결추이 ──────────────────────────


@gold.command("executions")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드 (M04020000=금99.99_1kg, M04020100=미니금99.99_100g)")
def gold_executions(stk_cd):
    """금현물 체결 추이."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50010", {"stk_cd": stk_cd})
        print_api_response(data, "금현물체결추이")


# ── ka50012  금현물일별추이 ──────────────────────────


@gold.command("daily")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
def gold_daily(stk_cd, base_dt):
    """금현물 일별 추이."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50012", {
            "stk_cd": stk_cd, "base_dt": base_dt,
        })
        print_api_response(data, "금현물일별추이")


# ── ka50079  금현물틱차트 ────────────────────────────


@gold.command("chart-tick")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--scope", "tic_scope", default="1", help="틱범위 (1,3,5,10,30)")
@click.option("--price-type", "upd_stkpc_tp", default="0", help="수정주가구분")
def gold_chart_tick(stk_cd, tic_scope, upd_stkpc_tp):
    """금현물 틱차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50079", {
            "stk_cd": stk_cd, "tic_scope": tic_scope,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        print_api_response(data, "금현물틱차트")


# ── ka50080  금현물분봉차트 ──────────────────────────


@gold.command("chart-minute")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--scope", "tic_scope", default="1", help="틱범위 (1,3,5,10,15,30,45,60)")
@click.option("--price-type", "upd_stkpc_tp", default="", help="수정주가구분 (선택)")
def gold_chart_minute(stk_cd, tic_scope, upd_stkpc_tp):
    """금현물 분봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50080", {
            "stk_cd": stk_cd, "tic_scope": tic_scope,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        print_api_response(data, "금현물분봉차트")


# ── ka50081  금현물일봉차트 ──────────────────────────


@gold.command("chart-day")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
@click.option("--price-type", "upd_stkpc_tp", default="0", help="수정주가구분")
def gold_chart_day(stk_cd, base_dt, upd_stkpc_tp):
    """금현물 일봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50081", {
            "stk_cd": stk_cd, "base_dt": base_dt,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        print_api_response(data, "금현물일봉차트")


# ── ka50082  금현물주봉차트 ──────────────────────────


@gold.command("chart-week")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
@click.option("--price-type", "upd_stkpc_tp", default="0", help="수정주가구분")
def gold_chart_week(stk_cd, base_dt, upd_stkpc_tp):
    """금현물 주봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50082", {
            "stk_cd": stk_cd, "base_dt": base_dt,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        print_api_response(data, "금현물주봉차트")


# ── ka50083  금현물월봉차트 ──────────────────────────


@gold.command("chart-month")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
@click.option("--price-type", "upd_stkpc_tp", default="0", help="수정주가구분")
def gold_chart_month(stk_cd, base_dt, upd_stkpc_tp):
    """금현물 월봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50083", {
            "stk_cd": stk_cd, "base_dt": base_dt,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        print_api_response(data, "금현물월봉차트")


# ── ka50087  금현물예상체결 ──────────────────────────


@gold.command("expected")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
def gold_expected(stk_cd):
    """금현물 예상 체결."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50087", {"stk_cd": stk_cd})
        print_api_response(data, "금현물예상체결")


# ── ka50091  금현물당일틱차트 ─────────────────────────


@gold.command("today-tick")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--scope", "tic_scope", default="1", help="틱범위 (1,3,5,10,30)")
def gold_today_tick(stk_cd, tic_scope):
    """금현물 당일 틱차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50091", {
            "stk_cd": stk_cd, "tic_scope": tic_scope,
        })
        print_api_response(data, "금현물당일틱차트")


# ── ka50092  금현물당일분봉차트 ───────────────────────


@gold.command("today-minute")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--scope", "tic_scope", default="1", help="틱범위")
def gold_today_minute(stk_cd, tic_scope):
    """금현물 당일 분봉 차트."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50092", {
            "stk_cd": stk_cd, "tic_scope": tic_scope,
        })
        print_api_response(data, "금현물당일분봉차트")


# ── ka50100  금현물시세정보 ──────────────────────────


@gold.command("price")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
def gold_price(stk_cd):
    """금현물 시세정보."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50100", {"stk_cd": stk_cd})
        print_api_response(data, "금현물시세정보")


# ── ka50101  금현물호가 ──────────────────────────────


@gold.command("orderbook")
@click.option("--code", "stk_cd", default="M04020000", help="종목코드")
@click.option("--scope", "tic_scope", default="1", help="틱범위")
def gold_orderbook(stk_cd, tic_scope):
    """금현물 호가."""
    with KiwoomClient() as c:
        data, _ = c.request("ka50101", {
            "stk_cd": stk_cd, "tic_scope": tic_scope,
        })
        print_api_response(data, "금현물호가")


# ── ka52301  금현물투자자현황 ─────────────────────────


@gold.command("investors")
def gold_investors():
    """금현물 투자자 현황."""
    with KiwoomClient() as c:
        data, _ = c.request("ka52301", {})
        print_api_response(data, "금현물투자자현황")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Program Trading  (프로그램매매)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@market.group("program")
def program():
    """프로그램 매매 정보."""
    pass


# ── ka90005  프로그램매매추이 시간대별 ────────────────


@program.command("time-trend")
@click.option("--date", required=True, help="날짜 (YYYYMMDD)")
@click.option("--unit", "amt_qty_tp", default="1", help="금액/수량 (1=금액백만원, 2=수량천주)")
@click.option("--market", "mrkt_tp", default="0", help="시장구분")
@click.option("--tick-type", "min_tic_tp", default="1", help="분틱구분 (0=틱, 1=분)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def program_time_trend(date, amt_qty_tp, mrkt_tp, min_tic_tp, stex_tp):
    """프로그램매매 추이 (시간대별)."""

    with KiwoomClient() as c:
        data, _ = c.request("ka90005", {
            "date": date, "amt_qty_tp": amt_qty_tp,
            "mrkt_tp": mrkt_tp, "min_tic_tp": min_tic_tp,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "프로그램매매추이(시간대별)")


# ── ka90006  프로그램매매차익잔고추이 ─────────────────


@program.command("arbitrage-balance")
@click.option("--date", required=True, help="날짜 (YYYYMMDD)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def program_arbitrage_balance(date, stex_tp):
    """프로그램매매 차익잔고 추이."""

    with KiwoomClient() as c:
        data, _ = c.request("ka90006", {
            "date": date, "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "프로그램매매차익잔고추이")


# ── ka90007  프로그램매매누적추이 ─────────────────────


@program.command("cumulative")
@click.option("--date", required=True, help="날짜 (YYYYMMDD)")
@click.option("--unit", "amt_qty_tp", default="1", help="금액/수량")
@click.option("--market", "mrkt_tp", default="kospi", type=click.Choice(["kospi", "kosdaq"]), help="시장구분")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def program_cumulative(date, amt_qty_tp, mrkt_tp, stex_tp):
    """프로그램매매 누적 추이."""

    with KiwoomClient() as c:
        data, _ = c.request("ka90007", {
            "date": date, "amt_qty_tp": amt_qty_tp,
            "mrkt_tp": MARKET_KOSPI_KOSDAQ[mrkt_tp], "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "프로그램매매누적추이")


# ── ka90008  종목시간별프로그램매매추이 ────────────────


@program.command("stock-time")
@click.argument("code")
@click.option("--unit", "amt_qty_tp", default="1", help="금액/수량")
@click.option("--date", default="", help="날짜 (YYYYMMDD)")
def program_stock_time(code, amt_qty_tp, date):
    """종목 시간별 프로그램매매 추이."""
    with KiwoomClient() as c:
        data, _ = c.request("ka90008", {
            "amt_qty_tp": amt_qty_tp, "stk_cd": code, "date": date,
        })
        print_api_response(data, f"종목시간별프로그램매매추이 ({code})")


# ── ka90010  프로그램매매추이 일자별 ──────────────────


@program.command("daily-trend")
@click.option("--date", required=True, help="날짜 (YYYYMMDD)")
@click.option("--unit", "amt_qty_tp", default="1", help="금액/수량")
@click.option("--market", "mrkt_tp", default="0", help="시장구분")
@click.option("--tick-type", "min_tic_tp", default="1", help="분틱구분 (0=틱, 1=분)")
@click.option("--exchange", "stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="거래소 (KRX/NXT)")
def program_daily_trend(date, amt_qty_tp, mrkt_tp, min_tic_tp, stex_tp):
    """프로그램매매 추이 (일자별)."""

    with KiwoomClient() as c:
        data, _ = c.request("ka90010", {
            "date": date, "amt_qty_tp": amt_qty_tp,
            "mrkt_tp": mrkt_tp, "min_tic_tp": min_tic_tp,
            "stex_tp": EXCHANGE_TWO[stex_tp],
        })
        print_api_response(data, "프로그램매매추이(일자별)")


# ── ka90013  종목일별프로그램매매추이 ─────────────────


@program.command("stock-daily")
@click.argument("code")
@click.option("--unit", "amt_qty_tp", default="", help="금액/수량 (선택)")
@click.option("--date", default="", help="날짜 (YYYYMMDD, 선택)")
def program_stock_daily(code, amt_qty_tp, date):
    """종목 일별 프로그램매매 추이."""
    with KiwoomClient() as c:
        data, _ = c.request("ka90013", {
            "amt_qty_tp": amt_qty_tp, "stk_cd": code, "date": date,
        })
        print_api_response(data, f"종목일별프로그램매매추이 ({code})")
