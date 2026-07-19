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
from ..formatters import _fmt_number, _get_format, _sign_color, fail_input
from ..output import console
from ..streaming import EXIT_API, EXIT_AUTH, print_system_frame, recv_ack, resolve_ws_target
from .. import auth


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
            Text(_fmt_number(vals.get("10", "-"), strip_sign=True), style=f"bold {color}"),
            Text(_fmt_number(change), style=color),
            Text(f"{rate}%", style=color),
            _fmt_number(vals.get("15", "-"), strip_sign=True),
            _fmt_number(vals.get("13", "-"), strip_sign=True),
            _fmt_number(vals.get("16", "-"), strip_sign=True),
            _fmt_number(vals.get("17", "-"), strip_sign=True),
            _fmt_number(vals.get("18", "-"), strip_sign=True),
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
    # Rich Live TUI라 json/csv의 파싱 가능 출력 계약을 지킬 수 없다.
    # 조용히 TUI를 띄우면 -f json 소비자가 빈 stdout을 받는다 → 명시적으로 거부.
    if _get_format() != "table":
        fail_input(
            "watch는 table 출력 전용입니다. 'kiwoom stream quote'를 사용하세요.",
            code="INVALID_INPUT",
        )

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

    profile, ws_url = resolve_ws_target()
    token = auth.load_token(profile=profile)

    if not token:
        console.print("[red]토큰이 없습니다. 'kiwoom auth login'으로 발급하세요.[/]")
        raise SystemExit(EXIT_AUTH)

    try:
        import websockets
    except ImportError:
        console.print("[red]websockets 패키지가 필요합니다: pip install websockets[/]")
        raise SystemExit(1) from None

    code_str = ", ".join(f"{stock_state[c].get('_name', c)}({c})" for c in code_list)
    console.print(f"[dim]실시간 모니터링: {code_str}[/]")
    console.print("[dim]Ctrl+C로 종료[/]\n")

    def _system(frame: dict[str, str]) -> None:
        print_system_frame(frame, console.print)

    async def _live_stream() -> int:
        """종료 코드를 반환한다 (0=정상, EXIT_API=2, EXIT_AUTH=3)."""
        url = f"{ws_url}/api/dostk/websocket"
        try:
            async with websockets.connect(
                url,
                additional_headers={"content-type": "application/json;charset=UTF-8"},
                ping_interval=None,
                ping_timeout=None,
            ) as ws:
                # Auth.
                # ack를 recv() 순번으로 집지 않는다 — prod는 LOGIN 응답 뒤에 SYSTEM
                # 프레임을 보내지만 mock은 안 보내서, 위치로 읽으면 환경에 따라
                # 엉뚱한 프레임을 ack로 오독한다 (return_code 부재 → 사유 공란 실패).
                await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
                auth_resp = await recv_ack(ws, on_system=_system)
                if auth_resp is None:
                    console.print("[red]인증 응답을 받지 못했습니다 (LOGIN 응답 프레임 없음).[/]")
                    return EXIT_AUTH
                if str(auth_resp.get("return_code")) != "0":
                    console.print(f"[red]인증 실패: {auth_resp.get('return_msg', '')}[/]")
                    return EXIT_AUTH

                # Register for 0B (체결)
                reg = {
                    "trnm": "REG",
                    "grp_no": "1",
                    "refresh": "1",
                    "data": [{"item": code_list, "type": ["0B"]}],
                }
                await ws.send(json.dumps(reg))
                reg_resp = await recv_ack(ws, on_system=_system)
                if reg_resp is None:
                    console.print("[red]등록 응답을 받지 못했습니다.[/]")
                    return EXIT_API
                if str(reg_resp.get("return_code")) != "0":
                    console.print(f"[red]등록 실패: {reg_resp.get('return_msg', '')}[/]")
                    return EXIT_API

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

                        # 시스템 메시지를 조용히 버리지 않는다 (streaming.py와 동일)
                        if trnm == "SYSTEM":
                            _system(data)
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
            # 서버가 정상적으로 끊은 스트림의 끝은 실패가 아니다
            console.print("\n[yellow]서버 연결 종료. 재접속하려면 다시 실행하세요.[/]")
            return 0
        except ConnectionRefusedError:
            console.print("[red]WebSocket 연결 실패. 도메인과 토큰을 확인하세요.[/]")
            return EXIT_API
        except Exception as e:
            # JSONDecodeError 등 나머지가 raw traceback으로 새지 않게 (streaming.py와 동일)
            console.print(f"[red]오류: {e}[/]")
            return EXIT_API
        return 0

    try:
        exit_code = asyncio.run(_live_stream())
    except KeyboardInterrupt:
        console.print("\n[dim]모니터링 종료[/]")
        exit_code = 0
    if exit_code:
        raise SystemExit(exit_code)
