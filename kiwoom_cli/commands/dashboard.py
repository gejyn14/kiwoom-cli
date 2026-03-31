"""Dashboard command: combined account + market overview."""

from __future__ import annotations

from typing import Any

import click
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..client import KiwoomClient, KiwoomAPIError
from ..formatters import (
    _fmt_number,
    _get_format,
    _sign_color,
    print_generic_table,
)
from ..output import console


def _build_account_panel(data: dict[str, Any]) -> Panel:
    """Build a Rich Panel summarising the account balance."""
    t = Table(show_header=False, border_style="dim", expand=True)
    t.add_column("항목", style="cyan", width=18)
    t.add_column("값", width=22)

    t.add_row("계좌명", data.get("acnt_nm", ""))
    t.add_row("예수금", _fmt_number(data.get("entr", "")))
    t.add_row("총매입금액", _fmt_number(data.get("tot_pur_amt", "")))
    t.add_row("유가잔고평가액", _fmt_number(data.get("tot_est_amt", "")))
    t.add_row("예탁자산평가액", _fmt_number(data.get("aset_evlt_amt", "")))

    pl_color = _sign_color(data.get("tdy_lspft", "0"))
    t.add_row("당일손익", Text(_fmt_number(data.get("tdy_lspft", "")), style=pl_color))
    t.add_row("당일손익율", Text(data.get("tdy_lspft_rt", "0") + "%", style=pl_color))

    cum_color = _sign_color(data.get("lspft", "0"))
    t.add_row("누적손익", Text(_fmt_number(data.get("lspft", "")), style=cum_color))
    t.add_row("누적손익율", Text(data.get("lspft_rt", "0") + "%", style=cum_color))

    return Panel(t, title="계좌 요약", border_style="green")


def _build_movers_table(items: list[dict[str, Any]]) -> Table:
    """Build a Rich Table for top-volume stocks."""
    t = Table(title="당일 거래량 상위", border_style="dim", expand=True)
    t.add_column("종목코드", style="dim")
    t.add_column("종목명")
    t.add_column("현재가", justify="right")
    t.add_column("전일대비", justify="right")
    t.add_column("등락율", justify="right")
    t.add_column("거래량", justify="right")

    for item in items[:15]:
        change = item.get("pred_pre", item.get("flu_amt", "0"))
        color = _sign_color(change)
        rate = item.get("flu_rt", item.get("pre_rt", ""))
        t.add_row(
            item.get("stk_cd", ""),
            item.get("stk_nm", ""),
            _fmt_number(item.get("cur_prc", "")),
            Text(_fmt_number(change), style=color),
            Text(rate + "%" if rate else "-", style=color),
            _fmt_number(item.get("trde_qty", item.get("acc_trde_qty", ""))),
        )
    return t


@click.command("dashboard")
def dashboard():
    """대시보드: 계좌 요약 + 거래량 상위 종목.

    계좌 잔고(kt00004)와 당일 거래량 상위(ka10030)를 한 화면에 표시합니다.
    """
    fmt = _get_format()

    acct_data: dict[str, Any] | None = None
    movers_data: dict[str, Any] | None = None
    movers_items: list[dict[str, Any]] = []

    with KiwoomClient() as c:
        # Account balance -- skip gracefully when not logged in
        if c.token:
            try:
                acct_data, _ = c.request("kt00004", {"qry_tp": "0", "dmst_stex_tp": "KRX"})
            except KiwoomAPIError:
                acct_data = None
        else:
            acct_data = None

        # Top volume stocks (public-ish, but still needs token)
        try:
            movers_data, _ = c.request("ka10030", {
                "mrkt_tp": "000",
                "sort_tp": "1",
                "mang_stk_incls": "1",
                "crd_tp": "0",
                "trde_qty_tp": "0",
                "pric_tp": "0",
                "trde_prica_tp": "0",
                "mrkt_open_tp": "0",
                "stex_tp": "1",
            })
            # Extract list from response
            if movers_data:
                for v in movers_data.values():
                    if isinstance(v, list):
                        movers_items = v
                        break
        except KiwoomAPIError:
            movers_data = None

    # ── JSON / CSV output ─────────────────────────────────
    if fmt in ("json", "csv"):
        combined: dict[str, Any] = {}
        if acct_data:
            combined["account"] = acct_data
        if movers_items:
            combined["top_volume"] = movers_items
        elif movers_data:
            combined["top_volume"] = movers_data
        print_generic_table(combined, title="대시보드")
        return

    # ── Rich table output ─────────────────────────────────
    if acct_data:
        console.print(_build_account_panel(acct_data))
    else:
        console.print(
            Panel(
                "[yellow]계좌 정보를 불러올 수 없습니다.[/]\n"
                "[dim]'kiwoom auth login' 으로 토큰을 발급하세요.[/]",
                title="계좌 요약",
                border_style="yellow",
            )
        )

    console.print()

    if movers_items:
        console.print(_build_movers_table(movers_items))
    elif movers_data:
        print_generic_table(movers_data, title="당일 거래량 상위")
    else:
        console.print("[dim]거래량 상위 데이터를 불러올 수 없습니다.[/]")
