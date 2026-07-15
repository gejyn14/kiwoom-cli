"""US account operations, dispatched from commands/account.py."""

from __future__ import annotations

from ...client import KiwoomClient  # noqa: F401  (patched by tests; more ops use it in Task 10)
from ...formatters import print_generic_table


def fetch_balance(client, stex_tp: str | None = None) -> dict:
    """미국주식 원장잔고 (ust21070). 예외는 호출측에서 처리."""
    body: dict = {}
    if stex_tp:
        body["stex_tp"] = stex_tp
    data, _ = client.request("ust21070", body)
    return data


def print_deposit_us(client) -> None:
    """미국주식 예수금 상세 (ust21160)."""
    data, _ = client.request("ust21160", {})
    print_generic_table(data, title="미국주식 예수금")


def print_pnl_today_us(client, fc_krw: str = "0") -> None:
    """미국주식 당일 종목별 실현손익 (ust21170)."""
    data, _ = client.request("ust21170", {"fc_krw_tp": fc_krw})
    print_generic_table(data, title="미국주식 당일 실현손익")


def print_pending_us(client, slby_tp: str = "0", stk_cd: str = "") -> None:
    """미국주식 원장 미체결 (ust21050)."""
    body: dict = {"slby_tp": slby_tp}
    if stk_cd:
        body["stk_cd"] = stk_cd.upper()
    data, _ = client.request("ust21050", body)
    print_generic_table(data, title="미국주식 미체결")


def print_history_us(client, strt_dt: str, end_dt: str, tp: str = "0") -> None:
    """미국주식 거래내역 (ust21100)."""
    data, _ = client.request("ust21100", {"strt_dt": strt_dt, "end_dt": end_dt, "tp": tp})
    print_generic_table(data, title="미국주식 거래내역")


def print_pnl_period_us(client, strt_dt: str, end_dt: str, fc_krw: str = "0") -> None:
    """미국주식 기간 실현손익 (ust21530)."""
    data, _ = client.request("ust21530", {"strt_dt": strt_dt, "end_dt": end_dt, "fc_krw_tp": fc_krw})
    print_generic_table(data, title="미국주식 실현손익")


def print_executed_us(client, slby_tp: str = "0", stk_cd: str = "") -> None:
    """미국주식 당일 주문체결 확인 (ust21510)."""
    body: dict = {"slby_tp": slby_tp}
    if stk_cd:
        body["stk_cd"] = stk_cd.upper()
    data, _ = client.request("ust21510", body)
    print_generic_table(data, title="미국주식 당일 체결")
