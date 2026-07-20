"""Dashboard command: combined account + market overview."""

from __future__ import annotations

from typing import Any

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import envelope
from ..client import KiwoomClient, KiwoomAPIError
from ..formatters import (
    _calc_eval_pl,
    _fmt_number,
    _get_format,
    _sign_color,
    fail_api,
    print_generic_table,
)
from ..output import console, err_console
from ._constants import EXCHANGE_ALL, STOCK_CONDITION


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

    # 평가손익 = 유가잔고평가액 - 총매입금액
    _, eval_pl_str, eval_pl_rt_str, eval_color = _calc_eval_pl(data)
    t.add_row("평가손익", Text(eval_pl_str, style=eval_color))
    t.add_row("평가손익율", Text(eval_pl_rt_str + "%", style=eval_color))

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
            _fmt_number(item.get("cur_prc", ""), strip_sign=True),
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
    acct_failed = False
    movers_failed = False
    # 문서화된 3상태를 유지한다: 키 없음 = 시도조차 안 함(토큰 없음),
    # null = 시도했고 실패. partial_failures에는 후자만 들어간다.
    failures: dict[str, str] = {}

    with KiwoomClient() as c:
        # Account balance -- skip gracefully when not logged in
        if c.token:
            try:
                acct_data, _ = c.request("kt00004", {"qry_tp": "0", "dmst_stex_tp": "KRX"})
            except KiwoomAPIError as e:
                acct_data = None
                acct_failed = True
                failures["account"] = envelope.classify(upstream_code=e.code)[0]
                err_console.print(f"[dim]계좌 조회 실패: {e}[/]")
        else:
            acct_data = None

        # Top volume stocks (public-ish, but still needs token)
        try:
            movers_data, _ = c.request("ka10030", {
                "mrkt_tp": "000",
                "sort_tp": "1",
                "mang_stk_incls": STOCK_CONDITION["include-managed"],
                "crd_tp": "0",
                "trde_qty_tp": "0",
                "pric_tp": "0",
                "trde_prica_tp": "0",
                "mrkt_open_tp": "0",
                # `market rank volume`(같은 ka10030)의 --exchange 기본값과 맞춘다.
                # D7이 그쪽 기본값을 KRX(1)에서 통합(3)으로 옮겼을 때 여기만
                # "1"로 남아, 같은 "당일 거래량 상위"가 두 명령에서 갈렸다.
                # 리터럴 대신 상수를 참조해 다음 이동 때 다시 갈리지 않게 한다.
                "stex_tp": EXCHANGE_ALL["all"],
            })
            # mang_stk_incls도 `market rank volume` 기본값과 맞춘다. 예전에는
            # 여기만 "1"(exclude-managed)이라 dashboard의 거래량 상위에서
            # 관리종목이 조용히 빠졌다 — 관리종목은 상장폐지·감사의견 이슈로
            # 거래량이 튀는 날 상위권에 들어오는 종목이라, 같은 "당일 거래량
            # 상위"가 두 명령에서 다른 목록으로 나왔다.
            # ka10030의 이 필드는 boolean이 아니라 15개짜리 종목조건 코드북이다
            # (_constants.py의 STOCK_CONDITION 주석 참고). 리터럴 대신 상수를
            # 참조해 market 쪽 기본값이 움직여도 다시 갈리지 않게 한다.
            # Extract list from response
            if movers_data:
                for v in movers_data.values():
                    if isinstance(v, list):
                        movers_items = v
                        break
        except KiwoomAPIError as e:
            movers_data = None
            movers_failed = True
            failures["top_volume"] = envelope.classify(upstream_code=e.code)[0]
            err_console.print(f"[dim]거래량 상위 조회 실패: {e}[/]")

    if acct_failed and movers_failed:
        fail_api("계좌·거래량 조회가 모두 실패했습니다.")

    # ── JSON / CSV output ─────────────────────────────────
    if fmt in ("json", "csv"):
        combined: dict[str, Any] = {}
        if acct_failed:
            combined["account"] = None
        elif acct_data:
            combined["account"] = acct_data
        if movers_failed:
            combined["top_volume"] = None
        elif movers_items:
            combined["top_volume"] = movers_items
        elif movers_data:
            combined["top_volume"] = movers_data
        print_generic_table(combined, title="대시보드",
                            partial_failures=failures or None)
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
