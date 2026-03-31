"""Live TUI dashboard: real-time stock price monitoring.

Uses WebSocket streaming + Rich Live display to show
continuously updating stock prices in the terminal.
"""

from __future__ import annotations

import asyncio
import json

import click
from rich.live import Live
from rich.table import Table
from rich.text import Text

from ..client import KiwoomClient
from ..formatters import _fmt_number, _sign_color
from ..output import console
from ..streaming import WS_DOMAINS
from .. import auth, config


def _build_live_table(stocks: dict[str, dict[str, str]], title: str = "실시간 시세") -> Table:
    """Build a Rich table from current stock state."""
    t = Table(title=title, border_style="dim", expand=True)
    t.add_column("종목코드", style="dim", width=8)
    t.add_column("종목명", width=14)
    t.add_column("현재가", justify="right", width=10)
    t.add_column("전일대비", justify="right", width=10)
    t.add_column("등락율", justify="right", width=8)
    t.add_column("거래량", justify="right", width=10)
    t.add_column("누적거래량", justify="right", width=12)
    t.add_column("시가", justify="right", width=10)
    t.add_column("고가", justify="right", style="red", width=10)
    t.add_column("저가", justify="right", style="blue", width=10)
    t.add_column("체결강도", justify="right", width=8)

    for code, vals in stocks.items():
        change = vals.get("11", "0")
        color = _sign_color(change)
        rate = vals.get("12", "0")

        t.add_row(
            code,
            vals.get("_name", code),
            Text(_fmt_number(vals.get("10", "-")), style=f"bold {color}"),
            Text(_fmt_number(change), style=color),
            Text(f"{rate}%", style=color),
            _fmt_number(vals.get("15", "-")),
            _fmt_number(vals.get("13", "-")),
            _fmt_number(vals.get("16", "-")),
            _fmt_number(vals.get("17", "-")),
            _fmt_number(vals.get("18", "-")),
            vals.get("228", "-"),
        )
    return t


@click.command("watch")
@click.argument("codes", nargs=-1, required=True)
def watch(codes: tuple[str, ...]):
    """실시간 종목 모니터링 (TUI 대시보드).

    \b
    WebSocket으로 실시간 체결 데이터를 수신하며 라이브 업데이트합니다.
    Ctrl+C로 종료.

    \b
    예시:
      kiwoom watch 005930                    # 삼성전자
      kiwoom watch 005930 000660 035420      # 여러 종목
    """
    code_list = list(codes)

    # Fetch initial stock names via REST
    stock_state: dict[str, dict[str, str]] = {}
    with KiwoomClient() as c:
        for code in code_list:
            try:
                data, _ = c.request("ka10001", {"stk_cd": code})
                stock_state[code] = {
                    "_name": data.get("stk_nm", code),
                    "10": data.get("cur_prc", "0"),
                    "11": data.get("pred_pre", "0"),
                    "12": data.get("flu_rt", "0"),
                    "13": data.get("trde_qty", "0"),
                    "16": data.get("open_pric", "0"),
                    "17": data.get("high_pric", "0"),
                    "18": data.get("low_pric", "0"),
                }
            except Exception:
                stock_state[code] = {"_name": code}

    cfg = config.load_config()
    domain_key = cfg.get("general", {}).get("domain", "mock")
    ws_url = WS_DOMAINS.get(domain_key, WS_DOMAINS["mock"])
    token = auth.load_token()

    if not token:
        console.print("[red]토큰이 없습니다. 'kiwoom auth login'으로 발급하세요.[/]")
        return

    code_str = ", ".join(f"{stock_state[c].get('_name', c)}({c})" for c in code_list)
    console.print(f"[dim]실시간 모니터링: {code_str}[/]")
    console.print("[dim]Ctrl+C로 종료[/]\n")

    async def _live_stream():
        import websockets

        url = f"{ws_url}/api/dostk/websocket"
        try:
            async with websockets.connect(
                url,
                additional_headers={"content-type": "application/json;charset=UTF-8"},
                ping_interval=None,
                ping_timeout=None,
            ) as ws:
                # Auth
                await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
                auth_resp = json.loads(await ws.recv())
                if auth_resp.get("return_code", -1) != 0:
                    console.print(f"[red]인증 실패: {auth_resp.get('return_msg', '')}[/]")
                    return

                # Register for 0B (체결)
                reg = {
                    "trnm": "REG",
                    "grp_no": "1",
                    "refresh": "1",
                    "data": [{"item": code_list, "type": ["0B"]}],
                }
                await ws.send(json.dumps(reg))
                reg_resp = json.loads(await ws.recv())
                if reg_resp.get("return_code", -1) != 0:
                    console.print(f"[red]등록 실패: {reg_resp.get('return_msg', '')}[/]")
                    return

                tick_count = 0

                with Live(
                    _build_live_table(stock_state),
                    console=console,
                    refresh_per_second=4,
                    transient=False,
                ) as live:
                    async for message in ws:
                        try:
                            data = json.loads(message)
                        except json.JSONDecodeError:
                            continue

                        trnm = data.get("trnm", "")

                        # Heartbeat
                        if trnm == "PING":
                            try:
                                await ws.send(json.dumps({"trnm": "PING"}))
                            except websockets.exceptions.ConnectionClosed:
                                break
                            continue

                        if trnm != "REAL":
                            continue

                        # Update stock state from real-time data
                        for entry in data.get("data", []):
                            item_code = entry.get("item", "")
                            values = entry.get("values", {})
                            if isinstance(values, list) and values:
                                values = values[0] if isinstance(values[0], dict) else {}

                            if item_code in stock_state:
                                name = stock_state[item_code].get("_name", item_code)
                                for k, v in values.items():
                                    if v:
                                        stock_state[item_code][k] = v
                                stock_state[item_code]["_name"] = name

                        tick_count += 1
                        title = f"실시간 시세 (tick #{tick_count})"
                        live.update(_build_live_table(stock_state, title=title))

        except websockets.exceptions.ConnectionClosed:
            console.print("\n[yellow]서버 연결 종료. 재접속하려면 다시 실행하세요.[/]")
        except ConnectionRefusedError:
            console.print("[red]WebSocket 연결 실패. 도메인과 토큰을 확인하세요.[/]")

    try:
        asyncio.run(_live_stream())
    except KeyboardInterrupt:
        console.print("\n[dim]모니터링 종료[/]")
