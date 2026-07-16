"""US stock info/quote/search/chart operations, dispatched from commands/stock.py."""

from __future__ import annotations

from ...client import KiwoomClient
from ...formatters import _find_list, print_chart_data, print_generic_table
from ...output import err_console
from ._constants import US_EXCHANGE_ALL
from .detect import UsExchangeError, resolve_us_exchange


def _resolve_or_exit(client, code: str, exchange: str | None) -> str:
    try:
        return resolve_us_exchange(client, code, exchange)
    except UsExchangeError as e:
        err_console.print(f"[red]{e}[/]")
        raise SystemExit(1) from None


def info(code: str, exchange: str | None) -> None:
    """미국주식 종목 조회 (usa10100). stex_tp 필수 — 미지정 시 자동판별."""
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        data, _ = c.request("usa10100", {"stk_cd": code.upper(), "stex_tp": stex_tp})
        print_generic_table(data, title=f"{code.upper()} 종목정보 (미국)")


def price(code: str, exchange: str | None) -> None:
    """미국주식 현재가 (usa20100)."""
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        data, _ = c.request("usa20100", {"stex_tp": stex_tp, "stk_cd": code.upper()})
        print_generic_table(data, title=f"{code.upper()} 현재가 (미국)")


def orderbook(code: str, exchange: str | None) -> None:
    """미국주식 10호가 (usa20101)."""
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        data, _ = c.request("usa20101", {"stex_tp": stex_tp, "stk_cd": code.upper()})
        print_generic_table(data, title=f"{code.upper()} 호가 (미국)")


def search(keyword: str | None, exchange: str | None) -> None:
    """미국주식 종목 검색 (usa10099 리스트를 키워드로 필터)."""
    stex_tp = US_EXCHANGE_ALL.get(exchange or "all", "%")
    with KiwoomClient() as c:
        data, _ = c.request("usa10099", {"stex_tp": stex_tp})
        items = data.get("list", []) or []
        if keyword:
            kw = keyword.lower()
            items = [
                i for i in items
                if kw in i.get("stk_cd", "").lower()
                or kw in i.get("stk_nm", "").lower()
                or kw in i.get("stk_enm", "").lower()
            ]
        if not items:
            err_console.print("[yellow]검색 결과가 없습니다.[/]")
            return
        print_generic_table(items, title=f"미국주식 검색: {keyword or '전체'}")


_CHART_APIS = {
    "tick": "usa06010",
    "minute": "usa06011",
    "day": "usa06012",
    "week": "usa06013",
    "month": "usa06014",
    "year": "usa06015",
}

_CHART_TITLES = {
    "tick": "틱", "minute": "분봉", "day": "일봉",
    "week": "주봉", "month": "월봉", "year": "년봉",
}


def chart(kind: str, code: str, exchange: str | None, tic_scope: str = "1",
          strt_dt: str = "", adjusted: str = "0", krw: bool = False) -> None:
    """미국주식 차트 (usa06010~usa06015)."""
    api_id = _CHART_APIS[kind]
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        body = {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "upd_stkpc_tp": adjusted,
            "exrt_appl_tp": "1" if krw else "0",
        }
        if kind == "tick":
            body["tic_scope"] = tic_scope
        elif kind == "minute":
            body["tic_scope"] = tic_scope
            if strt_dt:
                body["strt_dt"] = strt_dt
        else:
            body["strt_dt"] = strt_dt
        data, _ = c.request(api_id, body)
        items = _find_list(data)
        title = f"{code.upper()} {_CHART_TITLES[kind]} 차트 (미국)"
        if isinstance(items, list):
            print_chart_data(items, title=title)
        else:
            print_generic_table(data, title=title)
