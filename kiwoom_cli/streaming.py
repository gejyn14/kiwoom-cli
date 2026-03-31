"""WebSocket streaming client for Kiwoom real-time data.

Connects to wss://api.kiwoom.com:10000/api/dostk/websocket
and streams real-time market data.
"""

from __future__ import annotations

import json
import signal
import sys
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from . import auth, config

console = Console()

# Real-time type codes -> (name, description)
REALTIME_TYPES: dict[str, tuple[str, str]] = {
    "00": ("주문체결", "주문 접수/체결/정정/취소 실시간 수신"),
    "04": ("잔고", "보유잔고 실시간 변동"),
    "0A": ("주식기세", "현재가, 전일대비, 거래량 등"),
    "0B": ("주식체결", "체결시간, 현재가, 거래량 등"),
    "0C": ("주식우선호가", "최우선 매도/매수 호가"),
    "0D": ("주식호가잔량", "10단계 호가잔량"),
    "0E": ("주식시간외호가", "시간외 호가"),
    "0F": ("주식당일거래원", "당일 거래원별 매매"),
    "0G": ("ETF NAV", "ETF 순자산가치"),
    "0H": ("주식예상체결", "예상 체결가/수량"),
    "0I": ("국제금환산가격", "국제금 환산가격"),
    "0J": ("업종지수", "업종별 지수"),
    "0U": ("업종등락", "업종 등락 정보"),
    "0g": ("주식종목정보", "종목 기본정보 변동"),
    "0m": ("ELW 이론가", "ELW 이론가"),
    "0s": ("장시작시간", "장 시작/마감 시간"),
    "0u": ("ELW 지표", "ELW 지표"),
    "0w": ("종목프로그램매매", "종목별 프로그램 매매"),
    "1h": ("VI발동/해제", "변동성완화장치 발동/해제"),
}

WS_DOMAINS = {
    "prod": "wss://api.kiwoom.com:10000",
    "mock": "wss://mockapi.kiwoom.com:10000",
}


def _build_register_msg(
    types: list[str],
    items: list[str],
    grp_no: str = "1",
    refresh: str = "1",
) -> dict[str, Any]:
    """Build WebSocket registration message.

    Per the API docs, item and type inside data must be arrays:
      {"item": ["005930"], "type": ["0B"]}
    """
    # Account-level types (no item needed)
    account_types = {"00", "04"}
    if all(t in account_types for t in types):
        data = [{"item": [], "type": types}]
    else:
        data = [{"item": items, "type": types}]

    return {
        "trnm": "REG",
        "grp_no": grp_no,
        "refresh": refresh,
        "data": data,
    }


def _build_unregister_msg(
    types: list[str],
    items: list[str],
    grp_no: str = "1",
) -> dict[str, Any]:
    """Build WebSocket unregistration message."""
    return {
        "trnm": "REMOVE",
        "grp_no": grp_no,
        "data": [{"item": items, "type": types}],
    }


def _format_values(values: dict[str, str], type_code: str) -> dict[str, str]:
    """Convert numeric field IDs to readable names where known."""
    # Common field mappings
    field_names = {
        "10": "현재가",
        "11": "전일대비",
        "12": "등락율",
        "13": "누적거래량",
        "14": "누적거래대금",
        "15": "거래량",
        "16": "시가",
        "17": "고가",
        "18": "저가",
        "20": "체결시간",
        "25": "전일대비기호",
        "27": "매도호가",
        "28": "매수호가",
        "29": "거래대금증감",
        "30": "전일거래량대비",
        "31": "거래회전율",
        "302": "종목명",
        "900": "주문수량",
        "901": "주문가격",
        "902": "미체결수량",
        "903": "체결누계금액",
        "904": "원주문번호",
        "905": "주문구분",
        "906": "매매구분",
        "907": "매도수구분",
        "908": "주문체결시간",
        "909": "체결번호",
        "910": "체결가",
        "911": "체결량",
        "912": "주문업무분류",
        "913": "주문상태",
        "916": "대출일",
        "917": "신용구분",
        "920": "체결수량",
        "930": "보유수량",
        "931": "매입단가",
        "932": "총매입가",
        "933": "주문가능수량",
        "938": "당일순매수수량",
        "939": "매도매수구분",
        "940": "당일총매도손익",
        "941": "예수금",
        "950": "당일실현손익",
        "951": "당일실현손익율",
        "9001": "종목코드",
        "9201": "계좌번호",
        "9203": "주문번호",
    }
    result = {}
    for k, v in values.items():
        name = field_names.get(k, k)
        result[name] = v
    return result


def run_stream(
    types: list[str],
    items: list[str],
    raw: bool = False,
) -> None:
    """Connect to WebSocket and stream real-time data."""
    import asyncio

    try:
        import websockets
    except ImportError:
        console.print("[red]websockets 패키지가 필요합니다: pip install websockets[/]")
        return

    cfg = config.load_config()
    domain_key = cfg.get("general", {}).get("domain", "mock")
    ws_url = WS_DOMAINS.get(domain_key, WS_DOMAINS["mock"])
    token = auth.load_token()
    if not token:
        console.print("[red]토큰이 없습니다. 'kiwoom auth login'으로 발급하세요.[/]")
        return

    type_names = ", ".join(
        f"{t}({REALTIME_TYPES.get(t, ('?', ''))[0]})" for t in types
    )
    item_str = ", ".join(items) if items else "(계좌)"
    console.print(f"[dim]실시간 스트리밍 시작: {type_names}[/]")
    console.print(f"[dim]종목: {item_str}[/]")
    console.print("[dim]Ctrl+C로 종료[/]\n")

    async def _stream():
        url = f"{ws_url}/api/dostk/websocket"
        headers = {
            "content-type": "application/json;charset=UTF-8",
        }

        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                # Step 1: Send token authentication first
                auth_msg = {
                    "trnm": "LOGIN",
                    "token": token,
                }
                await ws.send(json.dumps(auth_msg))
                console.print("[dim]토큰 인증 요청...[/]")

                # Wait for auth response
                auth_resp = await ws.recv()
                try:
                    auth_data = json.loads(auth_resp)
                    if auth_data.get("code") and auth_data["code"] != "0":
                        console.print(f"[red]인증 실패: {auth_data.get('message', auth_resp)}[/]")
                        return
                    console.print("[green]인증 성공[/]")
                except json.JSONDecodeError:
                    pass

                # Step 2: Send registration
                reg_msg = _build_register_msg(types, items)
                await ws.send(json.dumps(reg_msg))
                console.print("[dim]종목 등록 요청...[/]")

                # Receive loop
                async for message in ws:
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        if raw:
                            console.print(message)
                        continue

                    if raw:
                        console.print_json(json.dumps(data, ensure_ascii=False))
                        continue

                    trnm = data.get("trnm", "")

                    # Server sends PING as keepalive - just ignore it
                    if trnm == "PING":
                        continue

                    # Handle system messages (login, errors)
                    if trnm == "SYSTEM":
                        msg = data.get("message", "")
                        code = data.get("code", "")
                        if code and code != "0":
                            console.print(f"[red]시스템: {msg}[/]")
                        else:
                            console.print(f"[dim]시스템: {msg}[/]")
                        continue

                    # Handle registration response
                    rc = data.get("return_code")
                    if rc is not None:
                        if str(rc) == "0":
                            console.print("[green]등록 성공[/]")
                        else:
                            console.print(f"[red]오류: {data.get('return_msg', '')}[/]")
                        continue

                    # Handle real-time data
                    trnm = data.get("trnm", "")
                    if trnm == "REAL":
                        for entry in data.get("data", []):
                            type_code = entry.get("type", "")
                            type_name = REALTIME_TYPES.get(type_code, ("?", ""))[0]
                            item_code = entry.get("item", "")
                            values = entry.get("values", {})

                            if isinstance(values, list) and values:
                                values = values[0] if isinstance(values[0], dict) else {}

                            named = _format_values(values, type_code)

                            # Compact one-line output
                            parts = [f"[cyan]{type_name}[/]"]
                            if item_code:
                                parts.append(f"[dim]{item_code}[/]")
                            for k, v in named.items():
                                if v and v != "0":
                                    parts.append(f"{k}={v}")
                            console.print(" | ".join(parts))
                    else:
                        # Other messages
                        console.print(f"[dim]{json.dumps(data, ensure_ascii=False)}[/]")

        except websockets.exceptions.ConnectionClosed as e:
            console.print(f"\n[yellow]연결 종료: {e}[/]")
        except ConnectionRefusedError:
            console.print("[red]WebSocket 연결 실패. 도메인과 토큰을 확인하세요.[/]")
        except Exception as e:
            console.print(f"[red]오류: {e}[/]")

    try:
        asyncio.run(_stream())
    except KeyboardInterrupt:
        console.print("\n[dim]스트리밍 종료[/]")
