"""Rich formatters for Kiwoom API responses."""

from __future__ import annotations

import csv
import io
import json
import sys
from typing import Any

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .output import console


def _get_format() -> str:
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.obj:
        return ctx.obj.get("format", "table")
    return "table"


def _output_json(data: Any) -> None:
    """Write data as JSON to stdout."""
    clean = data
    if isinstance(data, dict):
        clean = {k: v for k, v in data.items() if k not in ("return_code", "return_msg")}
    click.echo(json.dumps(clean, ensure_ascii=False, indent=2))


def _output_csv(rows: list[dict], keys: list[str] | None = None) -> None:
    """Write rows as CSV to stdout."""
    if not rows:
        return
    if keys is None:
        keys = list(rows[0].keys())
    w = csv.DictWriter(sys.stdout, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in keys})


def _flat_dict(data: dict) -> list[dict]:
    """Flatten a dict with scalar values into a single-row list for CSV."""
    clean = {k: v for k, v in data.items()
             if not isinstance(v, (list, dict)) and k not in ("return_code", "return_msg")}
    return [clean] if clean else []


def _sign_color(value: str) -> str:
    """Return color based on sign: red for positive (상승), blue for negative (하락)."""
    v = value.strip().lstrip("+").lstrip("-")
    if value.strip().startswith("-"):
        return "blue"
    if value.strip().startswith("+") or (v and v != "0" and not value.strip().startswith("-")):
        return "red"
    return "white"


def _fmt_number(value: str) -> str:
    """Format a number string with commas, stripping leading zeros."""
    v = value.strip()
    if not v:
        return "-"
    sign = ""
    if v.startswith(("+", "-")):
        sign = v[0]
        v = v[1:]
    v = v.lstrip("0") or "0"
    try:
        return sign + f"{int(v):,}"
    except ValueError:
        try:
            return sign + f"{float(v):,.2f}"
        except ValueError:
            return value


def print_stock_info(data: dict[str, Any]) -> None:
    """Format stock basic info (ka10001)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    t = Table(title=f"📊 {data.get('stk_nm', '')} ({data.get('stk_cd', '')})", show_header=False, border_style="dim")
    t.add_column("항목", style="cyan", width=20)
    t.add_column("값", width=30)

    cur = data.get("cur_prc", "0")
    change = data.get("pred_pre", "0")
    rate = data.get("flu_rt", "0")
    color = _sign_color(change)

    t.add_row("현재가", Text(_fmt_number(cur), style=f"bold {color}"))
    t.add_row("전일대비", Text(f"{_fmt_number(change)} ({rate}%)", style=color))
    t.add_row("거래량", _fmt_number(data.get("trde_qty", "")))
    t.add_row("시가", _fmt_number(data.get("open_pric", "")))
    t.add_row("고가", _fmt_number(data.get("high_pric", "")))
    t.add_row("저가", _fmt_number(data.get("low_pric", "")))
    t.add_row("", "")
    t.add_row("시가총액", _fmt_number(data.get("mac", "")) + "억")
    t.add_row("PER", data.get("per", "-") or "-")
    t.add_row("PBR", data.get("pbr", "-") or "-")
    t.add_row("EPS", _fmt_number(data.get("eps", "")))
    t.add_row("BPS", _fmt_number(data.get("bps", "")))
    t.add_row("ROE", data.get("roe", "-") or "-")
    t.add_row("", "")
    t.add_row("52주 최고", _fmt_number(data.get("oyr_hgst", "")))
    t.add_row("52주 최저", _fmt_number(data.get("oyr_lwst", "")))
    t.add_row("상장주식수", _fmt_number(data.get("flo_stk", "")))
    t.add_row("외인소진률", data.get("for_exh_rt", "-") or "-")
    console.print(t)


def print_orderbook(data: dict[str, Any]) -> None:
    """Format 10-level orderbook (ka10004)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    t = Table(title="📋 호가창", border_style="dim")
    t.add_column("매도잔량", justify="right", style="blue", width=12)
    t.add_column("매도호가", justify="right", style="blue", width=10)
    t.add_column("매수호가", justify="right", style="red", width=10)
    t.add_column("매수잔량", justify="right", style="red", width=12)

    # Sell side (10 -> 1, top to bottom)
    sell_rows = []
    for i in range(10, 0, -1):
        suffix = "th" if i > 1 else ""
        if i == 1:
            bid_key = "sel_fpr_bid"
            qty_key = "sel_fpr_req"
        else:
            bid_key = f"sel_{i}{suffix}_pre_bid"
            qty_key = f"sel_{i}{suffix}_pre_req"
        sell_rows.append((_fmt_number(data.get(qty_key, "0")), _fmt_number(data.get(bid_key, "0"))))

    buy_rows = []
    for i in range(1, 11):
        suffix = "th"
        if i == 1:
            bid_key = "buy_fpr_bid"
            qty_key = "buy_fpr_req"
        else:
            bid_key = f"buy_{i}{suffix}_pre_bid"
            qty_key = f"buy_{i}{suffix}_pre_req"
        buy_rows.append((_fmt_number(data.get(bid_key, "0")), _fmt_number(data.get(qty_key, "0"))))

    for qty, price in sell_rows:
        t.add_row(qty, price, "", "")
    t.add_row("─" * 12, "─" * 10, "─" * 10, "─" * 12, style="dim")
    for price, qty in buy_rows:
        t.add_row("", "", price, qty)

    t.add_row("", "", "", "")
    t.add_row(
        f"[bold blue]{_fmt_number(data.get('tot_sel_req', '0'))}[/]",
        "[bold]총매도[/]",
        "[bold]총매수[/]",
        f"[bold red]{_fmt_number(data.get('tot_buy_req', '0'))}[/]",
    )
    console.print(t)


def print_account_eval(data: dict[str, Any]) -> None:
    """Format account evaluation (kt00004)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        holdings = data.get("stk_acnt_evlt_prst", [])
        if holdings:
            _output_csv(holdings)
        else:
            _output_csv(_flat_dict(data))
        return
    summary = Table(title="💰 계좌평가현황", show_header=False, border_style="dim")
    summary.add_column("항목", style="cyan", width=20)
    summary.add_column("값", width=25)

    summary.add_row("계좌명", data.get("acnt_nm", ""))
    summary.add_row("예수금", _fmt_number(data.get("entr", "")))
    summary.add_row("D+2 예수금", _fmt_number(data.get("d2_entra", "")))
    summary.add_row("총매입금액", _fmt_number(data.get("tot_pur_amt", "")))
    summary.add_row("유가잔고평가액", _fmt_number(data.get("tot_est_amt", "")))
    summary.add_row("예탁자산평가액", _fmt_number(data.get("aset_evlt_amt", "")))
    summary.add_row("추정예탁자산", _fmt_number(data.get("prsm_dpst_aset_amt", "")))

    pl_color = _sign_color(data.get("tdy_lspft", "0"))
    summary.add_row("당일손익", Text(_fmt_number(data.get("tdy_lspft", "")), style=pl_color))
    summary.add_row("당일손익율", Text(data.get("tdy_lspft_rt", "0") + "%", style=pl_color))
    summary.add_row("누적손익", Text(_fmt_number(data.get("lspft", "")), style=_sign_color(data.get("lspft", "0"))))
    summary.add_row("누적손익율", data.get("lspft_rt", "0") + "%")
    console.print(summary)

    holdings = data.get("stk_acnt_evlt_prst", [])
    if holdings:
        ht = Table(title="📦 보유종목", border_style="dim")
        ht.add_column("종목코드", style="dim")
        ht.add_column("종목명")
        ht.add_column("보유수량", justify="right")
        ht.add_column("평균단가", justify="right")
        ht.add_column("현재가", justify="right")
        ht.add_column("평가금액", justify="right")
        ht.add_column("손익금액", justify="right")
        ht.add_column("손익율", justify="right")

        for h in holdings:
            pl = h.get("pl_amt", "0")
            color = _sign_color(pl)
            ht.add_row(
                h.get("stk_cd", ""),
                h.get("stk_nm", ""),
                _fmt_number(h.get("rmnd_qty", "")),
                _fmt_number(h.get("avg_prc", "")),
                _fmt_number(h.get("cur_prc", "")),
                _fmt_number(h.get("evlt_amt", "")),
                Text(_fmt_number(pl), style=color),
                Text(h.get("pl_rt", "0") + "%", style=color),
            )
        console.print(ht)


def print_order_result(data: dict[str, Any], action: str = "주문") -> None:
    """Format order response."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    msg = data.get("return_msg", "")
    ord_no = data.get("ord_no", "")
    console.print(Panel(
        f"[bold green]✓ {action} 완료[/]\n\n"
        f"  주문번호: [bold]{ord_no}[/]\n"
        f"  메시지: {msg}",
        border_style="green",
    ))


def print_pending_orders(items: list[dict[str, Any]]) -> None:
    """Format pending orders list (ka10075)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(items)
        return
    if fmt == "csv":
        _output_csv(items)
        return
    if not items:
        console.print("[dim]미체결 주문이 없습니다.[/]")
        return

    t = Table(title="📝 미체결 주문", border_style="dim")
    t.add_column("주문번호")
    t.add_column("종목명")
    t.add_column("구분")
    t.add_column("주문수량", justify="right")
    t.add_column("주문가격", justify="right")
    t.add_column("미체결수량", justify="right")
    t.add_column("주문시간")

    for item in items:
        t.add_row(
            item.get("ord_no", ""),
            item.get("stk_nm", ""),
            item.get("buy_sell_tp", ""),
            _fmt_number(item.get("ord_qty", "")),
            _fmt_number(item.get("ord_uv", "")),
            _fmt_number(item.get("uncn_qty", "")),
            item.get("ord_tm", ""),
        )
    console.print(t)


def print_chart_data(items: list[dict[str, Any]], title: str = "차트") -> None:
    """Format chart data (OHLCV)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(items)
        return
    if fmt == "csv":
        _output_csv(items)
        return
    if not items:
        console.print("[dim]데이터가 없습니다.[/]")
        return

    t = Table(title=f"📈 {title}", border_style="dim")
    t.add_column("일자", style="dim")
    t.add_column("시가", justify="right")
    t.add_column("고가", justify="right", style="red")
    t.add_column("저가", justify="right", style="blue")
    t.add_column("종가", justify="right")
    t.add_column("거래량", justify="right")

    for item in items[:30]:
        t.add_row(
            item.get("dt", item.get("date", "")),
            _fmt_number(item.get("open_pric", item.get("strt_pric", ""))),
            _fmt_number(item.get("high_pric", "")),
            _fmt_number(item.get("low_pric", "")),
            _fmt_number(item.get("close_pric", item.get("cls_pric", item.get("cur_prc", "")))),
            _fmt_number(item.get("trde_qty", item.get("acml_trde_qty", ""))),
        )
    console.print(t)


_FIELD_LABELS: dict[str, str] = {
    "stk_cd": "종목코드", "stk_nm": "종목명", "cur_prc": "현재가",
    "pred_pre": "전일대비", "flu_rt": "등락율", "trde_qty": "거래량",
    "trde_amt": "거래대금", "open_pric": "시가", "high_pric": "고가",
    "low_pric": "저가", "close_pric": "종가", "date": "일자", "dt": "일자",
    "stk_cnd": "종목조건", "sel_fpr_bid": "매도호가", "buy_fpr_bid": "매수호가",
    "ord_no": "주문번호", "ord_qty": "주문수량", "ord_uv": "주문가격",
    "rmnd_qty": "보유수량", "avg_prc": "평균단가", "evlt_amt": "평가금액",
    "pl_amt": "손익금액", "pl_rt": "손익율", "acnt_nm": "계좌명",
    "pre_rt": "등락율", "acc_trde_qty": "누적거래량", "tm": "시간",
    "cntr_trde_qty": "체결량", "now_trde_qty": "거래량",
}


def print_generic_table(data: dict[str, Any] | list, title: str = "결과") -> None:
    """Generic formatter for any API response. Respects --format option."""
    fmt = _get_format()

    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        if isinstance(data, list):
            _output_csv(data)
        elif isinstance(data, dict):
            # Flatten: output lists first, then scalars
            lists = {k: v for k, v in data.items() if isinstance(v, list)}
            if lists:
                for lv in lists.values():
                    _output_csv(lv)
            else:
                _output_csv(_flat_dict(data))
        return

    # Table mode (default)
    if isinstance(data, list):
        if not data:
            console.print("[dim]데이터가 없습니다.[/]")
            return
        all_keys = list(data[0].keys())
        keys = [
            k for k in all_keys
            if any(str(item.get(k, "")).strip() for item in data[:50])
        ]
        if not keys:
            keys = all_keys

        t = Table(title=title, border_style="dim", show_lines=False)
        for k in keys:
            label = _FIELD_LABELS.get(k, k)
            justify = "right" if k in (
                "cur_prc", "pred_pre", "flu_rt", "trde_qty", "trde_amt",
                "open_pric", "high_pric", "low_pric", "close_pric",
                "ord_qty", "ord_uv", "rmnd_qty", "avg_prc", "evlt_amt",
                "pl_amt", "pl_rt", "acc_trde_qty", "cntr_trde_qty",
                "now_trde_qty", "pre_rt",
            ) else "left"
            t.add_column(label, justify=justify)
        for item in data[:50]:
            row = []
            for k in keys:
                v = str(item.get(k, ""))
                row.append(_fmt_number(v) if v.lstrip("+-").isdigit() and len(v) > 4 else v)
            t.add_row(*row)
        console.print(t)
    elif isinstance(data, dict):
        scalar = {k: v for k, v in data.items() if not isinstance(v, (list, dict)) and k not in ("return_code", "return_msg")}
        lists = {k: v for k, v in data.items() if isinstance(v, list)}

        if scalar:
            t = Table(title=title, show_header=False, border_style="dim")
            t.add_column("항목", style="cyan", width=25)
            t.add_column("값", width=35)
            for k, v in scalar.items():
                label = _FIELD_LABELS.get(k, k)
                t.add_row(label, str(v))
            console.print(t)

        for list_key, list_val in lists.items():
            print_generic_table(list_val, title=list_key)


def print_deposit(data: dict[str, Any]) -> None:
    """Format deposit info (kt00001)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    t = Table(title="💵 예수금 상세현황", show_header=False, border_style="dim")
    t.add_column("항목", style="cyan", width=25)
    t.add_column("금액", width=20, justify="right")

    fields = [
        ("entr", "예수금"),
        ("ord_alow_amt", "주문가능금액"),
        ("pymn_alow_amt", "출금가능금액"),
        ("profa_ch", "주식증거금현금"),
        ("repl_amt", "대용금평가액"),
        ("ch_uncla", "현금미수금"),
        ("ch_uncla_tot", "현금미수금합계"),
    ]
    for key, label in fields:
        val = data.get(key, "")
        if val:
            t.add_row(label, _fmt_number(val))
    console.print(t)
