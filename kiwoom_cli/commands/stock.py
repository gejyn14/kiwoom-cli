"""Stock information and market data commands."""

from __future__ import annotations

import click

from ..client import KiwoomClient
from ..formatters import (
    _fmt_number,
    _get_format,
    _output_csv,
    _output_json,
    _sign_color,
    print_chart_data,
    print_generic_table,
    print_orderbook,
    print_stock_info,
)
from ..output import console


def _find_list(data: dict) -> list | None:
    """Find the first list value in API response (skipping return_code/return_msg)."""
    for k, v in data.items():
        if isinstance(v, list) and k not in ("return_code", "return_msg"):
            return v
    return None


@click.group("stock")
def stock():
    """주식 종목 정보 및 시세 조회."""
    pass


# ═══════════════════════════════════════════════════════════════════
# Top-level convenience commands (most frequently used)
# ═══════════════════════════════════════════════════════════════════


@stock.command("info")
@click.argument("code")
def info(code: str):
    """종목 기본정보 조회. (ka10001)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10001", {"stk_cd": code})
        print_stock_info(data)


@stock.command("price")
@click.argument("code")
def price(code: str):
    """종목 현재가 간단 조회."""
    with KiwoomClient() as c:
        data, _ = c.request("ka10001", {"stk_cd": code})
        name = data.get("stk_nm", code)
        cur = data.get("cur_prc", "0")
        change = data.get("pred_pre", "0")
        rate = data.get("flu_rt", "0")
        click.echo(f"{name} ({code}): {cur}원 ({change}, {rate}%)")


@stock.command("orderbook")
@click.argument("code")
def orderbook(code: str):
    """호가창 조회. 10단계 매수/매도 호가. (ka10004)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10004", {"stk_cd": code})
        print_orderbook(data)


@stock.command("daily")
@click.argument("code")
@click.option(
    "--type", "qry_type",
    type=click.Choice(["day", "week", "month"]),
    default="day",
    help="조회 구분 (day/week/month)",
)
def daily(code: str, qry_type: str):
    """일/주/월별 시세 조회. (ka10005)"""
    tp_map = {"day": "1", "week": "2", "month": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10005", {"stk_cd": code, "qry_tp": tp_map[qry_type]})
        items = _find_list(data)
        title = {"day": "일별", "week": "주별", "month": "월별"}[qry_type]
        if items:
            print_chart_data(items, title=f"{code} {title} 시세")
        else:
            print_generic_table(data, title="시세")


@stock.command("exec")
@click.argument("code")
def executions(code: str):
    """체결정보 조회. (ka10003)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10003", {"stk_cd": code})
        items = _find_list(data)
        if items:
            print_generic_table(items, title=f"{code} 체결정보")
        else:
            print_generic_table(data, title="체결정보")


@stock.command("trader")
@click.argument("code")
def trader(code: str):
    """거래원 조회. (ka10002)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10002", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 거래원")


@stock.command("timeprice")
@click.argument("code")
def timeprice(code: str):
    """시분 시세 조회. (ka10006)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10006", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 시분 시세")


@stock.command("quote-info")
@click.argument("code")
def quote_info(code: str):
    """시세표성정보 조회. (ka10007)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10007", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 시세표성정보")


@stock.command("detail")
@click.argument("code")
def detail(code: str):
    """종목정보 상세 조회. (ka10100)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10100", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 종목정보 상세")


@stock.command("daily-price")
@click.argument("code")
@click.option("--date", "qry_dt", required=True, help="조회일자 (YYYYMMDD)")
@click.option(
    "--display", "indc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="표시구분 (0=수량, 1=금액백만원)",
)
def daily_price(code: str, qry_dt: str, indc_tp: str):
    """일별주가 조회. (ka10086)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10086", {
            "stk_cd": code,
            "qry_dt": qry_dt,
            "indc_tp": indc_tp,
        })
        print_generic_table(data, title=f"{code} 일별주가")


@stock.command("after-hours")
@click.argument("code")
def after_hours(code: str):
    """시간외단일가 조회. (ka10087)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10087", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 시간외단일가")


@stock.command("watchlist")
@click.argument("codes")
def watchlist(codes: str):
    """관심종목정보 조회 (코드를 |로 구분, 예: 005930|000660). (ka10095)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10095", {"stk_cd": codes})
        print_generic_table(data, title="관심종목정보")


@stock.command("search")
@click.argument("keyword", required=False)
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq", "k-otc", "konex", "etf", "elw"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq/k-otc/konex/etf/elw)",
)
def search(keyword: str | None, mrkt_tp: str):
    """종목 리스트 / 검색. (ka10099)"""
    _market_map = {"kospi": "0", "kosdaq": "10", "k-otc": "30", "konex": "50", "etf": "8", "elw": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10099", {"mrkt_tp": _market_map[mrkt_tp]})
        items = _find_list(data) or []
        if keyword and isinstance(items, list):
            items = [
                i for i in items
                if keyword in i.get("stk_nm", "") or keyword in i.get("stk_cd", "")
            ]
        if isinstance(items, list):
            print_generic_table(items[:30], title="종목 리스트")
        else:
            print_generic_table(data, title="종목 리스트")


@stock.command("list")
@click.option(
    "--market", "-m",
    type=click.Choice(["all", "kospi", "kosdaq", "konex"], case_sensitive=False),
    default="all",
    help="시장구분 (all/kospi/kosdaq/konex)",
)
@click.option("--search", "-s", default=None, help="종목명/코드 검색 키워드")
@click.option("--refresh", is_flag=True, help="캐시 무시하고 새로 조회")
def list_stocks(market: str, search: str | None, refresh: bool):
    """KRX 전체 상장종목 리스트 (pykrx)."""
    from ..krx_data import get_stock_list
    from ..output import err_console

    with err_console.status("[dim]종목 리스트 조회 중...[/]", spinner="dots"):
        items = get_stock_list(market.upper(), refresh=refresh)

    if search:
        kw = search.lower()
        items = [
            i for i in items
            if kw in i["stk_nm"].lower() or kw in i["stk_cd"].lower()
        ]

    fmt = _get_format()
    if fmt == "json":
        _output_json({"stocks": items, "total": len(items)})
    elif fmt == "csv":
        _output_csv(items)
    else:
        print_generic_table(items, title=f"상장종목 ({len(items)}개)")


@stock.command("brokers")
def brokers():
    """회원사(증권사) 리스트 조회. (ka10102)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10102", {})
        items = _find_list(data) or []
        if isinstance(items, list):
            print_generic_table(items, title="회원사 리스트")
        else:
            print_generic_table(data, title="회원사 리스트")


@stock.command("short")
@click.argument("code")
@click.option("--from", "strt_dt", default=None, help="시작일자 (YYYYMMDD, 기본=30일전)")
@click.option("--to", "end_dt", default=None, help="종료일자 (YYYYMMDD, 기본=오늘)")
def short_selling(code: str, strt_dt: str | None, end_dt: str | None):
    """공매도 추이 조회. (ka10014)"""
    from datetime import datetime, timedelta
    today = datetime.now()
    if not end_dt:
        end_dt = today.strftime("%Y%m%d")
    if not strt_dt:
        strt_dt = (today - timedelta(days=30)).strftime("%Y%m%d")
    with KiwoomClient() as c:
        data, _ = c.request("ka10014", {
            "stk_cd": code,
            "tm_tp": "1",
            "strt_dt": strt_dt,
            "end_dt": end_dt,
        })
        items = _find_list(data)
        if isinstance(items, list):
            print_generic_table(items, title=f"{code} 공매도 추이")
        else:
            print_generic_table(data, title="공매도")


@stock.command("foreign")
@click.argument("code")
def foreign(code: str):
    """외국인 종목별 매매동향 조회. (ka10008)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10008", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 외국인 매매동향")


@stock.command("institution")
@click.argument("code")
def institution(code: str):
    """주식기관 조회. (ka10009)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10009", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 기관 매매")


@stock.command("tick-strength")
@click.argument("code")
def tick_strength_time(code: str):
    """체결강도추이 시간별. (ka10046)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10046", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 체결강도추이(시간별)")


@stock.command("daily-strength")
@click.argument("code")
def tick_strength_daily(code: str):
    """체결강도추이 일별. (ka10047)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10047", {"stk_cd": code})
        print_generic_table(data, title=f"{code} 체결강도추이(일별)")


@stock.command("today-exec")
@click.argument("code")
@click.option(
    "--when", "tdy_pred",
    type=click.Choice(["1", "2"]),
    default="1",
    help="당일전일 (1=당일, 2=전일)",
)
@click.option(
    "--mode", "tic_min",
    type=click.Choice(["0", "1"]),
    default="0",
    help="틱/분 (0=틱, 1=분)",
)
@click.option("--time", "tm", default="", help="시간 (4자리, 예: 1030)")
def today_exec(code: str, tdy_pred: str, tic_min: str, tm: str):
    """당일/전일 체결 조회. (ka10084)"""
    body: dict = {
        "stk_cd": code,
        "tdy_pred": tdy_pred,
        "tic_min": tic_min,
    }
    if tm:
        body["tm"] = tm
    with KiwoomClient() as c:
        data, _ = c.request("ka10084", body)
        label = "당일" if tdy_pred == "1" else "전일"
        print_generic_table(data, title=f"{code} {label} 체결")


@stock.command("today-volume")
@click.argument("code")
@click.option(
    "--when", "tdy_pred",
    type=click.Choice(["1", "2"]),
    default="1",
    help="당일전일 (1=당일, 2=전일)",
)
def today_volume(code: str, tdy_pred: str):
    """당일/전일 체결량 조회. (ka10055)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10055", {
            "stk_cd": code,
            "tdy_pred": tdy_pred,
        })
        label = "당일" if tdy_pred == "1" else "전일"
        print_generic_table(data, title=f"{code} {label} 체결량")


# ═══════════════════════════════════════════════════════════════════
# stock credit -- 신용매매 관련
# ═══════════════════════════════════════════════════════════════════


@stock.group("credit")
def credit():
    """신용매매 / 신용융자 정보."""
    pass


@credit.command("trend")
@click.argument("code")
@click.option("--date", "dt", required=True, help="일자 (YYYYMMDD)")
@click.option(
    "--type", "qry_tp",
    type=click.Choice(["loan", "short-sell"]),
    default="loan",
    help="구분 (loan=융자, short-sell=대주)",
)
def credit_trend(code: str, dt: str, qry_tp: str):
    """신용매매동향 조회. (ka10013)"""
    _type_map = {"loan": "1", "short-sell": "2"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10013", {
            "stk_cd": code,
            "dt": dt,
            "qry_tp": _type_map[qry_tp],
        })
        print_generic_table(data, title=f"{code} 신용매매동향")


@credit.command("available")
def credit_available():
    """신용융자 가능종목 조회. (kt20016)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt20016", {})
        print_generic_table(data, title="신용융자 가능종목")


@credit.command("inquiry")
def credit_inquiry():
    """신용융자 가능문의. (kt20017)"""
    with KiwoomClient() as c:
        data, _ = c.request("kt20017", {})
        print_generic_table(data, title="신용융자 가능문의")


# ═══════════════════════════════════════════════════════════════════
# stock detail-trade -- 거래 상세 / 분석 관련
# ═══════════════════════════════════════════════════════════════════


@stock.group("analysis")
def analysis():
    """거래 분석 / 상세 정보."""
    pass


@analysis.command("daily-detail")
@click.argument("code")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
def daily_detail(code: str, strt_dt: str):
    """일별거래상세 조회. (ka10015)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10015", {
            "stk_cd": code,
            "strt_dt": strt_dt,
        })
        print_generic_table(data, title=f"{code} 일별거래상세")


@analysis.command("volume-renewal")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["all", "kospi", "kosdaq"]),
    default="all",
    help="시장구분 (all/kospi/kosdaq)",
)
@click.option(
    "--cycle", "cycle_tp",
    type=click.Choice(["5", "10", "20", "60", "250"]),
    default="20",
    help="주기구분 (5/10/20/60/250일)",
)
@click.option("--volume-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def volume_renewal(mrkt_tp: str, cycle_tp: str, trde_qty_tp: str, stex_tp: str):
    """거래량갱신 조회. (ka10024)"""
    _market_map = {"all": "000", "kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10024", {
            "mrkt_tp": _market_map[mrkt_tp],
            "cycle_tp": cycle_tp,
            "trde_qty_tp": trde_qty_tp,
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="거래량갱신")


@analysis.command("price-cluster")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["all", "kospi", "kosdaq"]),
    default="all",
    help="시장구분 (all/kospi/kosdaq)",
)
@click.option("--ratio", "prps_cnctr_rt", default="50", help="매물집중비율 (0~100)")
@click.option(
    "--include-current", "cur_prc_entry",
    type=click.Choice(["0", "1"]),
    default="0",
    help="현재가진입 (0=미포함, 1=포함)",
)
@click.option("--count", "prpscnt", default="5", help="매물대수")
@click.option(
    "--cycle", "cycle_tp",
    type=click.Choice(["50", "100", "150", "200", "250", "300"]),
    default="100",
    help="주기구분",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def price_cluster(
    mrkt_tp: str,
    prps_cnctr_rt: str,
    cur_prc_entry: str,
    prpscnt: str,
    cycle_tp: str,
    stex_tp: str,
):
    """매물대집중 조회. (ka10025)"""
    _market_map = {"all": "000", "kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10025", {
            "mrkt_tp": _market_map[mrkt_tp],
            "prps_cnctr_rt": prps_cnctr_rt,
            "cur_prc_entry": cur_prc_entry,
            "prpscnt": prpscnt,
            "cycle_tp": cycle_tp,
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="매물대집중")


@analysis.command("per-rank")
@click.option(
    "--type", "pertp",
    type=click.Choice(["low-pbr", "high-pbr", "low-per", "high-per", "low-roe", "high-roe"]),
    default="low-per",
    help="PER구분 (low-pbr/high-pbr/low-per/high-per/low-roe/high-roe)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def per_rank(pertp: str, stex_tp: str):
    """고저PER 조회. (ka10026)"""
    _type_map = {"low-pbr": "1", "high-pbr": "2", "low-per": "3", "high-per": "4", "low-roe": "5", "high-roe": "6"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10026", {
            "pertp": _type_map[pertp],
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="고저PER")


@analysis.command("open-change")
@click.option(
    "--sort", "sort_tp",
    type=click.Choice(["1", "2", "3", "4"]),
    default="1",
    help="정렬구분 (1=시가, 2=고가, 3=저가, 4=기준가)",
)
@click.option("--volume-cond", "trde_qty_cnd", default="0", help="거래량조건")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["all", "kospi", "kosdaq"]),
    default="all",
    help="시장구분 (all/kospi/kosdaq)",
)
@click.option(
    "--include-limit", "updown_incls",
    type=click.Choice(["0", "1"]),
    default="0",
    help="상하한포함 (0=미포함, 1=포함)",
)
@click.option("--stock-cond", "stk_cnd", default="0", help="종목조건")
@click.option("--credit-cond", "crd_cnd", default="0", help="신용조건")
@click.option("--amount-cond", "trde_prica_cnd", default="0", help="거래대금조건")
@click.option(
    "--direction", "flu_cnd",
    type=click.Choice(["1", "2"]),
    default="1",
    help="등락조건 (1=상위, 2=하위)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def open_change(
    sort_tp: str,
    trde_qty_cnd: str,
    mrkt_tp: str,
    updown_incls: str,
    stk_cnd: str,
    crd_cnd: str,
    trde_prica_cnd: str,
    flu_cnd: str,
    stex_tp: str,
):
    """시가대비등락률 조회. (ka10028)"""
    _market_map = {"all": "000", "kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10028", {
            "sort_tp": sort_tp,
            "trde_qty_cnd": trde_qty_cnd,
            "mrkt_tp": _market_map[mrkt_tp],
            "updown_incls": updown_incls,
            "stk_cnd": stk_cnd,
            "crd_cnd": crd_cnd,
            "trde_prica_cnd": trde_prica_cnd,
            "flu_cnd": flu_cnd,
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="시가대비등락률")


@analysis.command("trader-analysis")
@click.argument("code")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
@click.option(
    "--date-type", "qry_dt_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="조회구분 (0=기간, 1=일자)",
)
@click.option(
    "--pot", "pot_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="당일/전일 (0=당일, 1=전일)",
)
@click.option(
    "--days", "dt",
    type=click.Choice(["5", "10", "20", "40", "60", "120"]),
    default="20",
    help="기간 (5/10/20/40/60/120일)",
)
@click.option(
    "--sort", "sort_base",
    type=click.Choice(["1", "2"]),
    default="2",
    help="정렬기준 (1=종가순, 2=날짜순)",
)
@click.option("--broker", "mmcm_cd", default="", help="회원사코드")
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def trader_analysis(
    code: str,
    strt_dt: str,
    end_dt: str,
    qry_dt_tp: str,
    pot_tp: str,
    dt: str,
    sort_base: str,
    mmcm_cd: str,
    stex_tp: str,
):
    """거래원매물대분석 조회. (ka10043)"""
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10043", {
            "stk_cd": code,
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "qry_dt_tp": qry_dt_tp,
            "pot_tp": pot_tp,
            "dt": dt,
            "sort_base": sort_base,
            "mmcm_cd": mmcm_cd,
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title=f"{code} 거래원매물대분석")


@analysis.command("instant-volume")
@click.option("--broker", "mmcm_cd", required=True, help="회원사코드")
@click.option("--code", "stk_cd", default="", help="종목코드 (선택)")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["0", "1", "2", "3"]),
    default="0",
    help="시장구분 (0=전체, 1=코스피, 2=코스닥, 3=종목)",
)
@click.option("--volume-type", "qty_tp", default="0", help="수량구분")
@click.option("--price-type", "pric_tp", default="0", help="가격구분")
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def instant_volume(
    mmcm_cd: str,
    stk_cd: str,
    mrkt_tp: str,
    qty_tp: str,
    pric_tp: str,
    stex_tp: str,
):
    """거래원순간거래량 조회. (ka10052)"""
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    body: dict = {
        "mmcm_cd": mmcm_cd,
        "mrkt_tp": mrkt_tp,
        "qty_tp": qty_tp,
        "pric_tp": pric_tp,
        "stex_tp": _exchange_map[stex_tp],
    }
    if stk_cd:
        body["stk_cd"] = stk_cd
    with KiwoomClient() as c:
        data, _ = c.request("ka10052", body)
        print_generic_table(data, title="거래원순간거래량")


@analysis.command("vi-trigger")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["all", "kospi", "kosdaq"]),
    default="all",
    help="시장구분 (all/kospi/kosdaq)",
)
@click.option(
    "--session", "bf_mkrt_tp",
    type=click.Choice(["0", "1", "2"]),
    default="0",
    help="장전구분 (0=전체, 1=정규시장, 2=시간외단일가)",
)
@click.option("--code", "stk_cd", default="", help="종목코드 (선택)")
@click.option(
    "--trigger-type", "motn_tp",
    type=click.Choice(["0", "1", "2", "3"]),
    default="0",
    help="발동구분 (0=전체, 1=정적VI, 2=동적VI, 3=동적+정적)",
)
@click.option("--skip-stock", "skip_stk", default="0", help="제외종목")
@click.option("--volume-type", "trde_qty_tp", default="0", help="거래량구분")
@click.option("--min-volume", "min_trde_qty", default="", help="최소거래량")
@click.option("--max-volume", "max_trde_qty", default="", help="최대거래량")
@click.option("--amount-type", "trde_prica_tp", default="0", help="거래대금구분")
@click.option("--min-amount", "min_trde_prica", default="", help="최소거래대금")
@click.option("--max-amount", "max_trde_prica", default="", help="최대거래대금")
@click.option(
    "--direction", "motn_drc",
    type=click.Choice(["0", "1", "2"]),
    default="0",
    help="발동방향 (0=전체, 1=상승, 2=하락)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def vi_trigger(
    mrkt_tp: str,
    bf_mkrt_tp: str,
    stk_cd: str,
    motn_tp: str,
    skip_stk: str,
    trde_qty_tp: str,
    min_trde_qty: str,
    max_trde_qty: str,
    trde_prica_tp: str,
    min_trde_prica: str,
    max_trde_prica: str,
    motn_drc: str,
    stex_tp: str,
):
    """변동성완화장치(VI) 발동종목 조회. (ka10054)"""
    _market_map = {"all": "000", "kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    body: dict = {
        "mrkt_tp": _market_map[mrkt_tp],
        "bf_mkrt_tp": bf_mkrt_tp,
        "motn_tp": motn_tp,
        "skip_stk": skip_stk,
        "trde_qty_tp": trde_qty_tp,
        "trde_prica_tp": trde_prica_tp,
        "motn_drc": motn_drc,
        "stex_tp": _exchange_map[stex_tp],
    }
    if stk_cd:
        body["stk_cd"] = stk_cd
    if min_trde_qty:
        body["min_trde_qty"] = min_trde_qty
    if max_trde_qty:
        body["max_trde_qty"] = max_trde_qty
    if min_trde_prica:
        body["min_trde_prica"] = min_trde_prica
    if max_trde_prica:
        body["max_trde_prica"] = max_trde_prica
    with KiwoomClient() as c:
        data, _ = c.request("ka10054", body)
        print_generic_table(data, title="VI 발동종목")


@analysis.command("warrant")
@click.option(
    "--type", "newstk_recvrht_tp",
    type=click.Choice(["00", "05", "07"]),
    default="00",
    help="신주인수권구분 (00=전체, 05=신주인수권증권, 07=신주인수권증서)",
)
def warrant(newstk_recvrht_tp: str):
    """신주인수권전체시세 조회. (ka10011)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10011", {
            "newstk_recvrht_tp": newstk_recvrht_tp,
        })
        print_generic_table(data, title="신주인수권전체시세")


@analysis.command("broker-stock")
@click.option("--broker", "mmcm_cd", required=True, help="회원사코드")
@click.option("--code", "stk_cd", required=True, help="종목코드")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
def broker_stock_trend(mmcm_cd: str, stk_cd: str, strt_dt: str, end_dt: str):
    """증권사별종목매매동향 조회. (ka10078)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10078", {
            "mmcm_cd": mmcm_cd,
            "stk_cd": stk_cd,
            "strt_dt": strt_dt,
            "end_dt": end_dt,
        })
        print_generic_table(data, title=f"{stk_cd} 증권사별종목매매동향")


# ═══════════════════════════════════════════════════════════════════
# stock investor -- 투자자 / 기관 / 외국인 관련
# ═══════════════════════════════════════════════════════════════════


@stock.group("investor")
def investor():
    """투자자별/기관/외국인 매매 정보."""
    pass


@investor.command("daily-trade")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
@click.option(
    "--trade", "trde_tp",
    type=click.Choice(["1", "2"]),
    default="2",
    help="매매구분 (1=순매도, 2=순매수)",
)
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def investor_daily_trade(strt_dt: str, end_dt: str, trde_tp: str, mrkt_tp: str, stex_tp: str):
    """일별기관매매종목 조회. (ka10044)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10044", {
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "trde_tp": trde_tp,
            "mrkt_tp": _market_map[mrkt_tp],
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="일별기관매매종목")


@investor.command("stock-institution")
@click.argument("code")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
@click.option(
    "--inst-price", "orgn_prsm_unp_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="기관추정단가구분 (1=매수단가, 2=매도단가)",
)
@click.option(
    "--foreign-price", "for_prsm_unp_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="외인추정단가구분 (1=매수단가, 2=매도단가)",
)
def stock_institution_trend(
    code: str,
    strt_dt: str,
    end_dt: str,
    orgn_prsm_unp_tp: str,
    for_prsm_unp_tp: str,
):
    """종목별기관매매추이 조회. (ka10045)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10045", {
            "stk_cd": code,
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "orgn_prsm_unp_tp": orgn_prsm_unp_tp,
            "for_prsm_unp_tp": for_prsm_unp_tp,
        })
        print_generic_table(data, title=f"{code} 종목별기관매매추이")


@investor.command("daily-by-investor")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
@click.option(
    "--trade", "trde_tp",
    type=click.Choice(["1", "2"]),
    default="2",
    help="매매구분 (1=순매도, 2=순매수)",
)
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--investor-type", "invsr_tp",
    default="9000",
    help="투자자구분 (8000=개인, 9000=외국인 등)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def daily_by_investor(
    strt_dt: str,
    end_dt: str,
    trde_tp: str,
    mrkt_tp: str,
    invsr_tp: str,
    stex_tp: str,
):
    """투자자별일별매매종목 조회. (ka10058)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10058", {
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "trde_tp": trde_tp,
            "mrkt_tp": _market_map[mrkt_tp],
            "invsr_tp": invsr_tp,
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="투자자별일별매매종목")


@investor.command("by-stock")
@click.argument("code")
@click.option("--date", "dt", required=True, help="일자 (YYYYMMDD)")
@click.option(
    "--amount-qty", "amt_qty_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="금액수량구분 (1=금액, 2=수량)",
)
@click.option(
    "--trade", "trde_tp",
    type=click.Choice(["0", "1", "2"]),
    default="0",
    help="매매구분 (0=순매수, 1=매수, 2=매도)",
)
@click.option(
    "--unit", "unit_tp",
    type=click.Choice(["1000", "1"]),
    default="1",
    help="단위구분 (1000=천주, 1=단주)",
)
def by_stock(code: str, dt: str, amt_qty_tp: str, trde_tp: str, unit_tp: str):
    """종목별투자자기관별 조회. (ka10059)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10059", {
            "dt": dt,
            "stk_cd": code,
            "amt_qty_tp": amt_qty_tp,
            "trde_tp": trde_tp,
            "unit_tp": unit_tp,
        })
        print_generic_table(data, title=f"{code} 종목별투자자기관별")


@investor.command("by-stock-total")
@click.argument("code")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", required=True, help="종료일자 (YYYYMMDD)")
@click.option(
    "--amount-qty", "amt_qty_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="금액수량구분 (1=금액, 2=수량)",
)
@click.option(
    "--trade", "trde_tp",
    type=click.Choice(["0", "1", "2"]),
    default="0",
    help="매매구분 (0=순매수, 1=매수, 2=매도)",
)
@click.option(
    "--unit", "unit_tp",
    type=click.Choice(["1000", "1"]),
    default="1",
    help="단위구분 (1000=천주, 1=단주)",
)
def by_stock_total(
    code: str,
    strt_dt: str,
    end_dt: str,
    amt_qty_tp: str,
    trde_tp: str,
    unit_tp: str,
):
    """종목별투자자기관별합계 조회. (ka10061)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10061", {
            "stk_cd": code,
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "amt_qty_tp": amt_qty_tp,
            "trde_tp": trde_tp,
            "unit_tp": unit_tp,
        })
        print_generic_table(data, title=f"{code} 종목별투자자기관별합계")


@investor.command("intraday")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--amount-qty", "amt_qty_tp",
    default="1",
    help="금액수량구분 (1=금액&수량)",
)
@click.option("--investor-type", "invsr", default="1000", help="투자자별")
@click.option(
    "--foreign-all", "frgn_all",
    type=click.Choice(["0", "1"]),
    default="0",
    help="외국계전체 (0/1)",
)
@click.option(
    "--simultaneous", "smtm_netprps_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="동시순매수구분 (0/1)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def intraday(
    mrkt_tp: str,
    amt_qty_tp: str,
    invsr: str,
    frgn_all: str,
    smtm_netprps_tp: str,
    stex_tp: str,
):
    """장중투자자별매매 조회. (ka10063)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10063", {
            "mrkt_tp": _market_map[mrkt_tp],
            "amt_qty_tp": amt_qty_tp,
            "invsr": invsr,
            "frgn_all": frgn_all,
            "smtm_netprps_tp": smtm_netprps_tp,
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="장중투자자별매매")


@investor.command("after-close")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--amount-qty", "amt_qty_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="금액수량구분 (1=금액, 2=수량)",
)
@click.option(
    "--trade", "trde_tp",
    type=click.Choice(["1", "2"]),
    default="2",
    help="매매구분 (1=순매도, 2=순매수)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def after_close(mrkt_tp: str, amt_qty_tp: str, trde_tp: str, stex_tp: str):
    """장마감후투자자별매매 조회. (ka10066)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10066", {
            "mrkt_tp": _market_map[mrkt_tp],
            "amt_qty_tp": amt_qty_tp,
            "trde_tp": trde_tp,
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="장마감후투자자별매매")


@investor.command("consecutive")
@click.option("--period", "dt", default="5", help="기간 (일수)")
@click.option("--from", "strt_dt", default="", help="시작일자 (YYYYMMDD, 선택)")
@click.option("--to", "end_dt", default="", help="종료일자 (YYYYMMDD, 선택)")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--net-type", "netslmt_tp",
    default="2",
    help="순매수구분 (2=순매수)",
)
@click.option(
    "--stock-sector", "stk_inds_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="종목/업종 (0=종목, 1=업종)",
)
@click.option(
    "--amount-qty", "amt_qty_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="금액수량구분 (1=금액, 2=수량)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def consecutive(
    dt: str,
    strt_dt: str,
    end_dt: str,
    mrkt_tp: str,
    netslmt_tp: str,
    stk_inds_tp: str,
    amt_qty_tp: str,
    stex_tp: str,
):
    """기관/외국인 연속매매현황 조회. (ka10131)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    body: dict = {
        "dt": dt,
        "mrkt_tp": _market_map[mrkt_tp],
        "netslmt_tp": netslmt_tp,
        "stk_inds_tp": stk_inds_tp,
        "amt_qty_tp": amt_qty_tp,
        "stex_tp": _exchange_map[stex_tp],
    }
    if strt_dt:
        body["strt_dt"] = strt_dt
    if end_dt:
        body["end_dt"] = end_dt
    with KiwoomClient() as c:
        data, _ = c.request("ka10131", body)
        print_generic_table(data, title="기관/외국인 연속매매현황")


@investor.command("program-top")
@click.option(
    "--trade", "trde_upper_tp",
    type=click.Choice(["1", "2"]),
    default="2",
    help="매매구분 (1=순매도, 2=순매수)",
)
@click.option(
    "--amount-qty", "amt_qty_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="금액수량구분 (1=금액, 2=수량)",
)
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def program_top(trde_upper_tp: str, amt_qty_tp: str, mrkt_tp: str, stex_tp: str):
    """프로그램순매수상위50 조회. (ka90003)"""
    _market_map = {"kospi": "P00101", "kosdaq": "P10102"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka90003", {
            "trde_upper_tp": trde_upper_tp,
            "amt_qty_tp": amt_qty_tp,
            "mrkt_tp": _market_map[mrkt_tp],
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="프로그램순매수상위50")


@investor.command("program-by-stock")
@click.option("--date", "dt", required=True, help="일자 (YYYYMMDD)")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--exchange", "stex_tp",
    type=click.Choice(["KRX", "NXT", "all"]),
    default="all",
    help="거래소구분 (KRX/NXT/all)",
)
def program_by_stock(dt: str, mrkt_tp: str, stex_tp: str):
    """종목별프로그램매매현황 조회. (ka90004)"""
    _market_map = {"kospi": "P00101", "kosdaq": "P10102"}
    _exchange_map = {"KRX": "1", "NXT": "2", "all": "3"}
    with KiwoomClient() as c:
        data, _ = c.request("ka90004", {
            "dt": dt,
            "mrkt_tp": _market_map[mrkt_tp],
            "stex_tp": _exchange_map[stex_tp],
        })
        print_generic_table(data, title="종목별프로그램매매현황")


# ═══════════════════════════════════════════════════════════════════
# stock chart -- 차트 데이터
# ═══════════════════════════════════════════════════════════════════


@stock.group("chart")
def chart():
    """차트 데이터 조회."""
    pass


@chart.command("tick")
@click.argument("code")
@click.option(
    "--range", "tic_scope",
    type=click.Choice(["1", "3", "5", "10", "30"]),
    default="1",
    help="틱범위 (1/3/5/10/30)",
)
@click.option(
    "--adjusted", "upd_stkpc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="수정주가구분 (0=미적용, 1=적용)",
)
def chart_tick(code: str, tic_scope: str, upd_stkpc_tp: str):
    """틱 차트 조회. (ka10079)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10079", {
            "stk_cd": code,
            "tic_scope": tic_scope,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        items = _find_list(data)
        if isinstance(items, list):
            print_chart_data(items, title=f"{code} 틱 차트")
        else:
            print_generic_table(data, title="틱 차트")


@chart.command("minute")
@click.argument("code")
@click.option(
    "--interval", "tic_scope",
    type=click.Choice(["1", "3", "5", "10", "15", "30", "45", "60"]),
    default="5",
    help="분봉 간격 (1/3/5/10/15/30/45/60)",
)
@click.option(
    "--adjusted", "upd_stkpc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="수정주가구분 (0=미적용, 1=적용)",
)
@click.option("--base-date", "base_dt", default="", help="기준일자 (YYYYMMDD, 선택)")
def chart_minute(code: str, tic_scope: str, upd_stkpc_tp: str, base_dt: str):
    """분봉 차트 조회. (ka10080)"""
    body: dict = {
        "stk_cd": code,
        "tic_scope": tic_scope,
        "upd_stkpc_tp": upd_stkpc_tp,
    }
    if base_dt:
        body["base_dt"] = base_dt
    with KiwoomClient() as c:
        data, _ = c.request("ka10080", body)
        items = _find_list(data)
        if isinstance(items, list):
            print_chart_data(items, title=f"{code} {tic_scope}분봉 차트")
        else:
            print_generic_table(data, title="분봉 차트")


@chart.command("day")
@click.argument("code")
@click.option("--base-date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
@click.option(
    "--adjusted", "upd_stkpc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="수정주가구분 (0=미적용, 1=적용)",
)
def chart_day(code: str, base_dt: str, upd_stkpc_tp: str):
    """일봉 차트 조회. (ka10081)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10081", {
            "stk_cd": code,
            "base_dt": base_dt,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        items = _find_list(data)
        if isinstance(items, list):
            print_chart_data(items, title=f"{code} 일봉 차트")
        else:
            print_generic_table(data, title="일봉 차트")


@chart.command("week")
@click.argument("code")
@click.option("--base-date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
@click.option(
    "--adjusted", "upd_stkpc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="수정주가구분 (0=미적용, 1=적용)",
)
def chart_week(code: str, base_dt: str, upd_stkpc_tp: str):
    """주봉 차트 조회. (ka10082)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10082", {
            "stk_cd": code,
            "base_dt": base_dt,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        items = _find_list(data)
        if isinstance(items, list):
            print_chart_data(items, title=f"{code} 주봉 차트")
        else:
            print_generic_table(data, title="주봉 차트")


@chart.command("month")
@click.argument("code")
@click.option("--base-date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
@click.option(
    "--adjusted", "upd_stkpc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="수정주가구분 (0=미적용, 1=적용)",
)
def chart_month(code: str, base_dt: str, upd_stkpc_tp: str):
    """월봉 차트 조회. (ka10083)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10083", {
            "stk_cd": code,
            "base_dt": base_dt,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        items = _find_list(data)
        if isinstance(items, list):
            print_chart_data(items, title=f"{code} 월봉 차트")
        else:
            print_generic_table(data, title="월봉 차트")


@chart.command("year")
@click.argument("code")
@click.option("--base-date", "base_dt", required=True, help="기준일자 (YYYYMMDD)")
@click.option(
    "--adjusted", "upd_stkpc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="수정주가구분 (0=미적용, 1=적용)",
)
def chart_year(code: str, base_dt: str, upd_stkpc_tp: str):
    """년봉 차트 조회. (ka10094)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10094", {
            "stk_cd": code,
            "base_dt": base_dt,
            "upd_stkpc_tp": upd_stkpc_tp,
        })
        items = _find_list(data)
        if isinstance(items, list):
            print_chart_data(items, title=f"{code} 년봉 차트")
        else:
            print_generic_table(data, title="년봉 차트")


@chart.command("investor")
@click.argument("code")
@click.option("--date", "dt", required=True, help="일자 (YYYYMMDD)")
@click.option(
    "--amount-qty", "amt_qty_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="금액수량구분 (1=금액, 2=수량)",
)
@click.option(
    "--trade", "trde_tp",
    type=click.Choice(["0", "1", "2"]),
    default="0",
    help="매매구분 (0=순매수, 1=매수, 2=매도)",
)
@click.option(
    "--unit", "unit_tp",
    type=click.Choice(["1000", "1"]),
    default="1",
    help="단위구분 (1000=천주, 1=단주)",
)
def chart_investor(code: str, dt: str, amt_qty_tp: str, trde_tp: str, unit_tp: str):
    """종목별투자자기관별 차트 조회. (ka10060)"""
    with KiwoomClient() as c:
        data, _ = c.request("ka10060", {
            "dt": dt,
            "stk_cd": code,
            "amt_qty_tp": amt_qty_tp,
            "trde_tp": trde_tp,
            "unit_tp": unit_tp,
        })
        print_generic_table(data, title=f"{code} 종목별투자자기관별 차트")


@chart.command("intraday-investor")
@click.argument("code")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
@click.option(
    "--amount-qty", "amt_qty_tp",
    type=click.Choice(["1", "2"]),
    default="1",
    help="금액수량구분 (1=금액, 2=수량)",
)
@click.option(
    "--trade", "trde_tp",
    type=click.Choice(["0", "1", "2"]),
    default="0",
    help="매매구분 (0=순매수, 1=매수, 2=매도)",
)
def chart_intraday_investor(code: str, mrkt_tp: str, amt_qty_tp: str, trde_tp: str):
    """장중투자자별매매 차트 조회. (ka10064)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    with KiwoomClient() as c:
        data, _ = c.request("ka10064", {
            "mrkt_tp": _market_map[mrkt_tp],
            "amt_qty_tp": amt_qty_tp,
            "trde_tp": trde_tp,
            "stk_cd": code,
        })
        print_generic_table(data, title=f"{code} 장중투자자별매매 차트")


# ═══════════════════════════════════════════════════════════════════
# stock lending -- 대차거래 관련
# ═══════════════════════════════════════════════════════════════════


@stock.group("lending")
def lending():
    """대차거래 정보."""
    pass


@lending.command("trend")
@click.option("--from", "strt_dt", default="", help="시작일자 (YYYYMMDD, 선택)")
@click.option("--to", "end_dt", default="", help="종료일자 (YYYYMMDD, 선택)")
@click.option(
    "--all", "all_tp",
    default="1",
    help="전체표시 (1=전체표시)",
)
def lending_trend(strt_dt: str, end_dt: str, all_tp: str):
    """대차거래추이 조회. (ka10068)"""
    body: dict = {"all_tp": all_tp}
    if strt_dt:
        body["strt_dt"] = strt_dt
    if end_dt:
        body["end_dt"] = end_dt
    with KiwoomClient() as c:
        data, _ = c.request("ka10068", body)
        print_generic_table(data, title="대차거래추이")


@lending.command("top10")
@click.option("--from", "strt_dt", required=True, help="시작일자 (YYYYMMDD)")
@click.option("--to", "end_dt", default="", help="종료일자 (YYYYMMDD, 선택)")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
def lending_top10(strt_dt: str, end_dt: str, mrkt_tp: str):
    """대차거래상위10종목 조회. (ka10069)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    body: dict = {
        "strt_dt": strt_dt,
        "mrkt_tp": _market_map[mrkt_tp],
    }
    if end_dt:
        body["end_dt"] = end_dt
    with KiwoomClient() as c:
        data, _ = c.request("ka10069", body)
        print_generic_table(data, title="대차거래상위10종목")


@lending.command("by-stock")
@click.argument("code")
@click.option("--from", "strt_dt", default="", help="시작일자 (YYYYMMDD, 선택)")
@click.option("--to", "end_dt", default="", help="종료일자 (YYYYMMDD, 선택)")
@click.option(
    "--all", "all_tp",
    default="0",
    help="전체표시 (0=종목코드 입력종목만)",
)
def lending_by_stock(code: str, strt_dt: str, end_dt: str, all_tp: str):
    """대차거래추이 종목별 조회. (ka20068)"""
    body: dict = {
        "stk_cd": code,
    }
    if all_tp:
        body["all_tp"] = all_tp
    if strt_dt:
        body["strt_dt"] = strt_dt
    if end_dt:
        body["end_dt"] = end_dt
    with KiwoomClient() as c:
        data, _ = c.request("ka20068", body)
        print_generic_table(data, title=f"{code} 대차거래추이")


@lending.command("detail")
@click.option("--date", "dt", required=True, help="일자 (YYYYMMDD)")
@click.option(
    "--market", "mrkt_tp",
    type=click.Choice(["kospi", "kosdaq"]),
    default="kospi",
    help="시장구분 (kospi/kosdaq)",
)
def lending_detail(dt: str, mrkt_tp: str):
    """대차거래내역 조회. (ka90012)"""
    _market_map = {"kospi": "001", "kosdaq": "101"}
    with KiwoomClient() as c:
        data, _ = c.request("ka90012", {
            "dt": dt,
            "mrkt_tp": _market_map[mrkt_tp],
        })
        print_generic_table(data, title="대차거래내역")


# ═══════════════════════════════════════════════════════════════════
# stock compare -- 종목 비교
# ═══════════════════════════════════════════════════════════════════


_COMPARE_ROWS = [
    ("종목명", "stk_nm"),
    ("현재가", "cur_prc"),
    ("전일대비", "pred_pre"),
    ("등락율", "flu_rt"),
    ("거래량", "trde_qty"),
    ("시가총액", "mac"),
    ("PER", "per"),
    ("PBR", "pbr"),
    ("52주고", "oyr_hgst"),
    ("52주저", "oyr_lwst"),
]


@stock.command("compare")
@click.argument("codes", nargs=-1, required=True)
def compare(codes: tuple[str, ...]):
    """종목 비교 (2개 이상). 주요 지표를 나란히 비교합니다. (ka10001)

    \b
    예시:
      kiwoom stock compare 005930 000660
      kiwoom stock compare 005930 000660 035420
    """
    if len(codes) < 2:
        raise click.UsageError("비교할 종목 코드를 2개 이상 입력하세요.")

    results: list[dict] = []
    with KiwoomClient() as c:
        for code in codes:
            data, _ = c.request("ka10001", {"stk_cd": code})
            data["_code"] = code
            results.append(data)

    fmt = _get_format()

    # ── JSON output ───────────────────────────────────────
    if fmt == "json":
        _output_json(results)
        return

    # ── CSV output ────────────────────────────────────────
    if fmt == "csv":
        rows = []
        for r in results:
            row = {"종목코드": r.get("_code", r.get("stk_cd", ""))}
            for label, key in _COMPARE_ROWS:
                row[label] = r.get(key, "")
            rows.append(row)
        _output_csv(rows)
        return

    # ── Rich table output ─────────────────────────────────
    from rich.table import Table
    from rich.text import Text

    t = Table(title="종목 비교", border_style="dim")
    t.add_column("항목", style="cyan", width=12)
    for r in results:
        name = r.get("stk_nm", r.get("_code", ""))
        code = r.get("_code", r.get("stk_cd", ""))
        t.add_column(f"{name}\n({code})", justify="right", min_width=14)

    for label, key in _COMPARE_ROWS:
        row_vals: list[str | Text] = [label]
        for r in results:
            val = r.get(key, "-") or "-"
            if key in ("cur_prc", "trde_qty", "mac", "oyr_hgst", "oyr_lwst"):
                display = _fmt_number(val)
                if key == "mac":
                    display += "억"
            elif key == "pred_pre":
                display = _fmt_number(val)
            elif key == "flu_rt":
                display = val + "%"
            else:
                display = val

            if key in ("pred_pre", "flu_rt"):
                color = _sign_color(val)
                row_vals.append(Text(display, style=color))
            else:
                row_vals.append(display)
        t.add_row(*row_vals)

    console.print(t)
