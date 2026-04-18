"""Rich formatters for Kiwoom API responses."""

from __future__ import annotations

import csv
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
    s = value.strip()
    if s.startswith("-"):
        return "blue"
    v = s.lstrip("+").lstrip("0")
    if v and (v[:1].isdigit() or v[:1] == "."):
        return "red"
    return "white"


def _fmt_number(value: str, strip_sign: bool = False) -> str:
    """Format a number string with commas, stripping leading zeros.

    Args:
        strip_sign: If True, remove the +/- prefix. Use for absolute value
            fields where Kiwoom uses +/- only as a direction indicator
            (e.g. cur_prc, open_pric, high_pric, etc.).
    """
    v = value.strip()
    if not v:
        return "-"
    sign = ""
    if v.startswith(("+", "-")):
        sign = v[0]
        v = v[1:]
    v = v.lstrip("0") or "0"
    if strip_sign:
        sign = ""
    try:
        return sign + f"{int(v):,}"
    except ValueError:
        try:
            return sign + f"{float(v):,.2f}"
        except ValueError:
            return v if strip_sign else value


# Fields where +/- is a direction indicator, not the actual sign.
# These represent absolute values (prices, amounts, quantities).
_ABS_FIELDS = frozenset({
    "cur_prc", "open_pric", "high_pric", "low_pric", "close_pric",
    "strt_pric", "base_pric", "upl_pric", "lst_pric",
    "oyr_hgst", "oyr_lwst", "250hgst", "250lwst",
    "sel_fpr_bid", "buy_fpr_bid", "exp_cntr_pric",
    "avg_prc", "evlt_amt", "pur_amt", "repl_pric",
    "mac", "fav", "cap", "flo_stk", "dstr_stk",
    "entr", "d2_entra", "tot_est_amt", "aset_evlt_amt",
    "tot_pur_amt", "prsm_dpst_aset_amt",
    "rmnd_qty", "ord_qty", "ord_uv", "mdfy_uv",
    "trde_qty", "acc_trde_qty", "now_trde_qty",
    "10", "16", "17", "18", "27", "28",  # WebSocket field IDs
})

# Fields where +/- is meaningful (changes, rates).
_SIGNED_FIELDS = frozenset({
    "pred_pre", "flu_rt", "pre_rt", "pl_amt", "pl_rt",
    "tdy_lspft", "lspft", "tdy_lspft_rt", "lspft_rt", "lspft_ratio",
    "11", "12", "15",  # WebSocket: 전일대비, 등락율, 거래량(+매수/-매도)
})

# Code fields that should never be number-formatted.
_CODE_FIELDS = frozenset({
    "stk_cd", "ord_no",
})


def _smart_fmt(value: str, field_key: str) -> str:
    """Format a value based on the field type."""
    if field_key in _ABS_FIELDS:
        return _fmt_number(value, strip_sign=True)
    return _fmt_number(value)


def _find_list(data: dict) -> list | None:
    """Find the first list value in API response."""
    for k, v in data.items():
        if isinstance(v, list) and k not in ("return_code", "return_msg"):
            return v
    return None


def print_api_response(data: dict | list, title: str = "결과") -> None:
    """Print API response, extracting list if present."""
    if isinstance(data, dict):
        items = _find_list(data)
        if items is not None:
            print_generic_table(items, title=title)
            return
    print_generic_table(data, title=title)


def _calc_eval_pl(data: dict) -> tuple[int, str, str, str]:
    """Calculate evaluation P&L. Returns (amount, amount_str, rate_str, color)."""
    try:
        evlt = int(data.get("tot_est_amt", "0").lstrip("0") or "0")
        pur = int(data.get("tot_pur_amt", "0").lstrip("0") or "0")
        eval_pl = evlt - pur
        eval_pl_rt = (eval_pl / pur * 100) if pur else 0
        eval_pl_str = f"+{eval_pl:,}" if eval_pl > 0 else f"{eval_pl:,}"
        eval_pl_rt_str = f"{eval_pl_rt:+.2f}"
    except (ValueError, ZeroDivisionError):
        eval_pl = 0
        eval_pl_str = "-"
        eval_pl_rt_str = "0.00"
    color = "red" if eval_pl > 0 else ("blue" if eval_pl < 0 else "white")
    return eval_pl, eval_pl_str, eval_pl_rt_str, color


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
    color = _sign_color(cur)

    t.add_row("현재가", Text(_fmt_number(cur, strip_sign=True), style=f"bold {color}"))
    t.add_row("전일대비", Text(f"{_fmt_number(change)} ({rate}%)", style=color))
    t.add_row("거래량", _fmt_number(data.get("trde_qty", ""), strip_sign=True))
    t.add_row("시가", _fmt_number(data.get("open_pric", ""), strip_sign=True))
    t.add_row("고가", _fmt_number(data.get("high_pric", ""), strip_sign=True))
    t.add_row("저가", _fmt_number(data.get("low_pric", ""), strip_sign=True))
    t.add_row("", "")
    t.add_row("시가총액", _fmt_number(data.get("mac", ""), strip_sign=True) + "억")
    t.add_row("PER", data.get("per", "-") or "-")
    t.add_row("PBR", data.get("pbr", "-") or "-")
    t.add_row("EPS", _fmt_number(data.get("eps", ""), strip_sign=True))
    t.add_row("BPS", _fmt_number(data.get("bps", ""), strip_sign=True))
    t.add_row("ROE", data.get("roe", "-") or "-")
    t.add_row("", "")
    t.add_row("52주 최고", _fmt_number(data.get("oyr_hgst", ""), strip_sign=True))
    t.add_row("52주 최저", _fmt_number(data.get("oyr_lwst", ""), strip_sign=True))
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

    # 평가손익 = 유가잔고평가액 - 총매입금액
    _, eval_pl_str, eval_pl_rt_str, eval_color = _calc_eval_pl(data)
    summary.add_row("평가손익", Text(eval_pl_str, style=eval_color))
    summary.add_row("평가손익율", Text(eval_pl_rt_str + "%", style=eval_color))
    pl_color = _sign_color(data.get("tdy_lspft", "0"))
    summary.add_row("당일실현손익", Text(_fmt_number(data.get("tdy_lspft", "")), style=pl_color))
    summary.add_row("당일실현손익율", Text(data.get("tdy_lspft_rt", "0") + "%", style=pl_color))
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
            _fmt_number(item.get("open_pric", item.get("strt_pric", "")), strip_sign=True),
            _fmt_number(item.get("high_pric", ""), strip_sign=True),
            _fmt_number(item.get("low_pric", ""), strip_sign=True),
            _fmt_number(item.get("close_pric", item.get("cls_pric", item.get("cur_prc", ""))), strip_sign=True),
            _fmt_number(item.get("trde_qty", item.get("acml_trde_qty", "")), strip_sign=True),
        )
    console.print(t)


_FIELD_LABELS: dict[str, str] = {
    # 기본 시세
    "stk_cd": "종목코드", "stk_nm": "종목명", "cur_prc": "현재가",
    "pred_pre": "전일대비", "pred_pre_sig": "전일대비기호", "pre_sig": "대비기호",
    "flu_rt": "등락율", "flu_sig": "등락기호", "pre_rt": "대비율",
    "pred_rt": "전일비", "stk_cnd": "종목조건", "stk_cls": "종목분류",
    "stk_infr": "종목정보", "state": "종목상태", "rank": "순위",
    "market": "시장", "type": "종류",
    # 가격
    "open_pric": "시가", "high_pric": "고가", "low_pric": "저가",
    "close_pric": "종가", "base_pric": "기준가", "upl_pric": "상한가",
    "lst_pric": "하한가", "pred_close_pric": "전일종가", "repl_pric": "대용가",
    "exp_cntr_pric": "예상체결가", "exp_cntr_qty": "예상체결량",
    "fav": "액면가", "mac": "시가총액", "cap": "자본금",
    "52wk_hgst_pric": "52주최고가", "52wk_lwst_pric": "52주최저가",
    "52wk_hgst_pric_dt": "52주최고가일", "52wk_lwst_pric_dt": "52주최저가일",
    # 거래
    "trde_qty": "거래량", "trde_amt": "거래금액", "trde_prica": "거래대금",
    "acc_trde_qty": "누적거래량", "acc_trde_prica": "누적거래대금",
    "trde_tern_rt": "거래회전율", "pred_trde_qty": "전일거래량",
    "opmr_trde_qty": "장중거래량", "af_mkrt_trde_qty": "장후거래량",
    "bf_mkrt_trde_qty": "장전거래량", "now_trde_qty": "거래량",
    "trde_pre": "전일거래량대비", "trde_wght": "매매비중",
    # 체결
    "cntr_qty": "체결량", "cntr_pric": "체결가", "cntr_uv": "체결단가",
    "cntr_str": "체결강도", "cntr_tm": "체결시간", "cntr_dt": "체결일",
    "cntr_no": "체결번호", "cntr_trde_qty": "체결량",
    "cntr_str_5min": "체결강도5분", "cntr_str_20min": "체결강도20분",
    "cntr_str_60min": "체결강도60분",
    # 호가
    "sel_fpr_bid": "매도호가", "buy_fpr_bid": "매수호가",
    "sel_bid": "매도호가", "buy_bid": "매수호가",
    "sel_req": "매도잔량", "buy_req": "매수잔량",
    "tot_sel_req": "총매도잔량", "tot_buy_req": "총매수잔량",
    "netprps_req": "순매수잔량", "sdnin_qty": "급증수량", "sdnin_rt": "급증률",
    # 주문
    "ord_no": "주문번호", "ord_qty": "주문수량", "ord_uv": "주문가격",
    "ord_pric": "주문가격", "ord_tm": "주문시간", "ord_stt": "주문상태",
    "ord_remnq": "주문잔량", "ord_alowa": "주문가능현금",
    "ord_alow_amt": "주문가능금액", "ord_pos_repl": "주문가능대용",
    "orig_ord_no": "원주문번호", "io_tp_nm": "주문구분",
    "oso_qty": "미체결수량", "cncl_qty": "취소수량", "mdfy_qty": "정정수량",
    "sell_tp": "매도/수구분", "trde_tp": "매매구분",
    "cond_uv": "스톱가", "stop_pric": "스톱가",
    # 계좌/잔고
    "acnt_nm": "계좌명", "rmnd_qty": "보유수량", "avg_prc": "평균단가",
    "evlt_amt": "평가금액", "pl_amt": "손익금액", "pl_rt": "손익율",
    "evltv_prft": "평가손익", "prft_rt": "수익률", "tot_prft_rt": "수익률",
    "tot_evlt_pl": "총평가손익", "dt_prft_rt": "기간수익률",
    "entr": "예수금", "d2_entra": "D+2추정예수금",
    "tot_pur_amt": "총매입금액", "tot_est_amt": "유가잔고평가액",
    "prsm_dpst_aset_amt": "추정예탁자산", "tot_evlt_amt": "총평가금액",
    "pur_amt": "매입금액", "pur_pric": "매입가", "buy_uv": "매입단가",
    "pur_cmsn": "매입수수료", "sell_cmsn": "매도수수료", "sum_cmsn": "총수수료",
    "repl_amt": "대용금", "pymn_alow_amt": "출금가능금액",
    "rmnd": "잔고주수", "remn_amt": "잔고금액", "setl_remn": "결제잔고",
    "trde_able_qty": "매매가능수량", "poss_rt": "보유비중",
    "cmsn": "수수료", "tax": "세금",
    "tdy_trde_cmsn": "당일매매수수료", "tdy_trde_tax": "당일매매세금",
    "tdy_sel_pl": "당일매도손익", "profa_ch": "증거금현금",
    "tot_loan_amt": "총대출금액", "tot_crd_loan_amt": "총신용대출금액",
    "tot_crd_ls_amt": "총신용이자금액",
    "crd_tp_nm": "신용구분명", "crd_loan_dt": "신용대출일",
    "pred_buyq": "전일매수수량", "pred_sellq": "전일매도수량",
    "tdy_buyq": "당일매수수량", "tdy_sellq": "당일매도수량",
    "aset_evlt_amt": "예탁자산평가액", "acnt_evlt_remn_indv_tot": "계좌평가잔고상세",
    "stk_acnt_evlt_prst": "보유종목",
    # 매수/매도
    "buy_qty": "매수수량", "sell_qty": "매도수량",
    "buy_amt": "매수금액", "sell_amt": "매도금액",
    "netprps_qty": "순매수수량", "netprps_amt": "순매수금액",
    "netprps": "순매수", "nettrde_qty": "순매매수량", "nettrde_amt": "순매매금액",
    "buy_trde_qty": "매수거래량", "sel_trde_qty": "매도거래량",
    # 투자자
    "ind_invsr": "개인투자자", "frgnr_invsr": "외국인투자자",
    "orgn": "기관계", "fnnc_invt": "금융투자", "insrnc": "보험",
    "invtrt": "투신", "penfnd_etc": "연기금등", "samo_fund": "사모펀드",
    "etc_fnnc": "기타금융", "etc_corp": "기타법인", "bank": "은행",
    "ind_netprps": "개인순매수", "for_netprps": "외인순매수",
    "orgn_netprps": "기관순매수", "for_netprps_qty": "외인순매수수량",
    "orgn_netprps_qty": "기관순매수수량",
    "for_poss": "외인보유", "for_wght": "외인비중",
    "limit_exh_rt": "한도소진율",
    # 신용/대차
    "crd_rt": "신용비율", "crd_remn_rt": "신용잔고율", "crd_tp": "신용구분",
    "loan_dt": "대출일", "dbrt_trde_cntrcnt": "대차거래체결주수",
    "dbrt_trde_rpy": "대차거래상환주수", "dbrt_trde_irds": "대차거래증감",
    "nrpy_loan": "미상환융자금",
    # 프로그램매매
    "prm": "프로그램", "prm_buy_amt": "프로그램매수금액",
    "prm_sell_amt": "프로그램매도금액", "prm_netprps_amt": "프로그램순매수금액",
    "prm_buy_qty": "프로그램매수수량", "prm_sell_qty": "프로그램매도수량",
    "prm_netprps_qty": "프로그램순매수수량",
    "dfrt_trde_buy": "차익거래매수", "dfrt_trde_sel": "차익거래매도",
    "dfrt_trde_netprps": "차익거래순매수",
    "ndiffpro_trde_buy": "비차익거래매수", "ndiffpro_trde_sel": "비차익거래매도",
    "ndiffpro_trde_netprps": "비차익거래순매수",
    # 업종
    "inds_cd": "업종코드", "rising": "상승", "fall": "하락", "stdns": "보합",
    # ELW/ETF
    "nav": "NAV", "dispty_rt": "괴리율", "trace_eor_rt": "추적오차율",
    "delta": "델타", "gam": "감마", "theta": "쎄타", "vega": "베가",
    "iv": "IV", "theory_pric": "이론가", "exec_pric": "행사가격",
    "expr_dt": "만기일", "srvive_dys": "잔존일수",
    "isscomp_nm": "발행사명", "base_aset_nm": "기초자산명",
    # 거래원
    "sel_trde_ori_1": "매도거래원1", "sel_trde_ori_2": "매도거래원2",
    "sel_trde_ori_3": "매도거래원3", "sel_trde_ori_4": "매도거래원4",
    "sel_trde_ori_5": "매도거래원5",
    "buy_trde_ori_1": "매수거래원1", "buy_trde_ori_2": "매수거래원2",
    "buy_trde_ori_3": "매수거래원3", "buy_trde_ori_4": "매수거래원4",
    "buy_trde_ori_5": "매수거래원5",
    "mmcm_nm": "회원사명",
    # 날짜/시간
    "dt": "일자", "date": "일자", "tm": "시간",
    "qry_dt": "조회일자", "trde_dt": "매매일자",
    # 업종 추가
    "inds_nm": "업종명", "upl": "상한", "lst": "하한",
    "flo_stk_num": "유통주식수", "wght": "비중", "kospi200": "KOSPI200",
    "pre_smbol": "대비부호",
    # 순위
    "now_rank": "현재순위", "pred_rank": "전일순위", "bigd_rank": "대형주순위",
    "rank_chg": "순위변동", "rank_chg_sign": "순위변동기호",
    "cnt": "건수", "tot": "합계", "drng": "기간",
    # 전일/기준 대비
    "pred_pre_1": "전일대비1", "pred_pre_2": "전일대비2", "pred_pre_3": "전일대비3",
    "pred_dvida": "전일거래대금",
    "prev_base_chgr": "전일기준변동율", "prev_base_sign": "전일기준기호",
    "base_comp_chgr": "기준대비변동율", "base_comp_sign": "기준대비기호",
    "past_curr_prc": "과거현재가",
    # 장구분별 시세
    "opmr_pred_rt": "장중전일비", "opmr_trde_amt": "장중거래대금",
    "opmr_trde_rt": "장중거래비율",
    "af_mkrt_pred_rt": "장후전일비", "af_mkrt_trde_amt": "장후거래대금",
    "af_mkrt_trde_rt": "장후거래비율",
    "bf_mkrt_pred_rt": "장전전일비", "bf_mkrt_trde_amt": "장전거래대금",
    "bf_mkrt_trde_rt": "장전거래비율",
    # 투자자 순매수
    "frgnr_netprps": "외국인순매수", "insrnc_netprps": "보험순매수",
    "invtrt_netprps": "투신순매수", "bank_netprps": "은행순매수",
    "samo_fund_netprps": "사모펀드순매수", "endw_netprps": "기금순매수",
    "etc_corp_netprps": "기타법인순매수", "sc_netprps": "증권순매수",
    "natn_netprps": "국가순매수", "jnsinkm_netprps": "연기금순매수",
    "native_trmt_frgnr_netprps": "내국인대우외인순매수",
    # 외인/기관 상세
    "for_netprps_amt": "외인순매수금액",
    "for_netprps_stk_cd": "외인순매수종목코드", "for_netprps_stk_nm": "외인순매수종목명",
    "for_netslmt_amt": "외인순매도금액", "for_netslmt_qty": "외인순매도수량",
    "for_netslmt_stk_cd": "외인순매도종목코드", "for_netslmt_stk_nm": "외인순매도종목명",
    "orgn_netprps_amt": "기관순매수금액",
    "orgn_netprps_stk_cd": "기관순매수종목코드", "orgn_netprps_stk_nm": "기관순매수종목명",
    "orgn_netslmt_amt": "기관순매도금액", "orgn_netslmt_qty": "기관순매도수량",
    "orgn_netslmt_stk_cd": "기관순매도종목코드", "orgn_netslmt_stk_nm": "기관순매도종목명",
    # 프로그램매매 추가
    "dfrt_trde_acc": "차익거래누적", "dfrt_trde_tdy": "차익거래당일",
    "ndiffpro_trde_acc": "비차익거래누적", "ndiffpro_trde_tdy": "비차익거래당일",
    "all_acc": "전체누적", "all_tdy": "전체당일",
    # ETF 추가
    "trace_flu_rt": "추적등락율", "trace_idex": "추적지수",
    "trace_idex_cd": "추적지수코드", "trace_idex_nm": "추적지수명",
    "basis": "베이시스", "dvid_bf_base": "배당전기준가", "txbs": "세전",
    # 순위/테마 추가
    "base_limit_exh_rt": "기준한도소진율", "base_pre": "기준대비",
    "buy_tot_req": "매수총잔량", "sel_tot_req": "매도총잔량",
    "exh_rt_incrs": "소진율증가", "fall_stk_num": "하락종목수",
    "rising_stk_num": "상승종목수", "stk_num": "종목수",
    "gain_pos_stkcnt": "보유종목수", "poss_stkcnt": "보유종목수",
    "jmp_rt": "급등률", "main_stk": "주력종목",
    "netslmt": "순매도", "sel_qty": "매도수량",
    "pred_trde_qty_pre_rt": "전일거래량대비율", "prev_trde_qty": "전일거래량",
    "tdy_close_pric": "당일종가", "tdy_close_pric_flu_rt": "당일종가등락율",
    "tdy_high_pric": "당일고가", "tdy_low_pric": "당일저가",
    "thema_grp_cd": "테마그룹코드", "thema_nm": "테마명",
    # 기타
    "dm1": "연속일1", "dm2": "연속일2", "dm3": "연속일3",
    "pipe1": "구분1", "pipe2": "구분2", "pipe3": "구분3",
}


def _get_label(key: str) -> str:
    """Get Korean label for an API field key, with _n suffix fallback."""
    label = _FIELD_LABELS.get(key)
    if label:
        return label
    if key.endswith("_n") and len(key) > 2:
        return _FIELD_LABELS.get(key[:-2], key)
    return key


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
            label = _get_label(k)
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
                if k not in _CODE_FIELDS and v.lstrip("+-").isdigit() and len(v) > 4:
                    row.append(_smart_fmt(v, k))
                else:
                    row.append(v)
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
                label = _get_label(k)
                sv = str(v)
                if k not in _CODE_FIELDS and sv.lstrip("+-").isdigit() and len(sv) > 4:
                    sv = _smart_fmt(sv, k)
                t.add_row(label, sv)
            console.print(t)

        for list_key, list_val in lists.items():
            list_title = _get_label(list_key)
            print_generic_table(list_val, title=list_title)


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
