"""WebSocket streaming client for Kiwoom real-time data.

Connects to wss://api.kiwoom.com:10000/api/dostk/websocket
and streams real-time market data.

json 모드에서는 REAL 이벤트마다 envelope 한 건을 compact JSON 한 줄(NDJSON)로
stdout에 출력하고, --max-events/--duration/--until 종료 조건으로 스스로 끝난다.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import click

from . import auth, config, envelope
from .formatters import _get_format, human
from .normalize import WS_FIELD_NAMES, normalize_ws_values
from .output import console, err_console
from .recorder import NdjsonRecorder, data_dir

EXIT_API = 2   # main.py와 동일 (main import 시 순환 발생하여 별도 정의)
EXIT_AUTH = 3

KST = timezone(timedelta(hours=9))


def _now_kst() -> datetime:
    return datetime.now(KST)


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


def resolve_ws_target() -> tuple[str, str]:
    """(profile, ws_url) — REST 경로와 동일하게 --profile(ctx)과 KIWOOM_DOMAIN을 존중한다."""
    ctx = click.get_current_context(silent=True)
    cli_profile = ctx.obj.get("profile") if ctx is not None and isinstance(ctx.obj, dict) else None
    profile = config.resolve_profile(cli_profile)
    return profile, WS_DOMAINS[config.get_domain_key(profile)]


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
    result = {}
    for k, v in values.items():
        name = WS_FIELD_NAMES.get(k, k)
        result[name] = v
    return result


# ── 종료 조건 ─────────────────────────────────────────

_DURATION_RE = re.compile(r"^(\d+)([smh])$")


def parse_duration(text: str) -> int:
    """"30s"/"5m"/"2h" -> 초. 형식 오류는 click.UsageError (exit 1)."""
    m = _DURATION_RE.match(text.strip())
    if not m:
        raise click.UsageError(f"--duration 형식 오류: {text!r} (예: 30s, 5m, 2h)")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)]


def parse_until(text: str) -> datetime:
    """ISO-8601 문자열 -> aware datetime. 타임존 없으면 +09:00(KST) 가정."""
    try:
        dt = datetime.fromisoformat(text.strip())
    except ValueError:
        raise click.UsageError(
            f"--until 형식 오류: {text!r} (ISO-8601, 예: 2026-07-16T15:30:00)"
        ) from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt


def new_stream_state(
    max_events: int | None = None,
    duration: str | None = None,
    until: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """스트림 종료 조건 상태 dict 구성. duration/until 문자열은 여기서 파싱."""
    now = now or _now_kst()
    deadline: datetime | None = None
    if duration:
        deadline = now + timedelta(seconds=parse_duration(duration))
    if until:
        u = parse_until(until)
        deadline = u if deadline is None else min(deadline, u)
    return {"max_events": max_events, "deadline": deadline, "event_count": 0}


def should_stop(state: dict[str, Any], now: datetime | None = None) -> bool:
    """종료 조건 도달 여부 (이벤트 수 또는 마감시각)."""
    max_events = state.get("max_events")
    if max_events is not None and state.get("event_count", 0) >= max_events:
        return True
    deadline = state.get("deadline")
    if deadline is not None and (now or _now_kst()) >= deadline:
        return True
    return False


def _remaining_seconds(state: dict[str, Any]) -> float | None:
    """마감시각까지 남은 초. 마감 없으면 None (무한 대기)."""
    deadline = state.get("deadline")
    if deadline is None:
        return None
    return (deadline - _now_kst()).total_seconds()


# ── 메시지 처리 (순수 함수) ───────────────────────────


def handle_message(data: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    """REAL 메시지 -> 정규화 이벤트 목록 (I/O 없는 순수 처리).

    PING/SYSTEM/등록응답은 ws 루프가 직접 처리하고 여기서는 빈 목록.
    state["max_events"] 초과분은 잘라내고 state["event_count"]를 갱신한다.
    이벤트: {"type","type_name","symbol","ts", <normalize_ws_values 타입 필드>}
    """
    if data.get("trnm") != "REAL":
        return []
    events: list[dict[str, Any]] = []
    max_events = state.get("max_events")
    for entry in data.get("data", []):
        if max_events is not None and state.get("event_count", 0) >= max_events:
            break
        values = entry.get("values", {})
        if isinstance(values, list):
            values = values[0] if values and isinstance(values[0], dict) else {}
        fields = normalize_ws_values(values)
        type_code = entry.get("type", "")
        event: dict[str, Any] = {
            "type": type_code,
            "type_name": REALTIME_TYPES.get(type_code, ("?", ""))[0],
            "symbol": entry.get("item") or fields.get("symbol"),
            "ts": fields.pop("ts", None),
        }
        fields.pop("symbol", None)
        event.update(fields)
        events.append(event)
        state["event_count"] = state.get("event_count", 0) + 1
    return events


# ── 출력 ─────────────────────────────────────────────


def _emit_line(
    data: dict[str, Any] | None = None,
    *,
    error: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    fields: list[str] | None = None,
) -> None:
    """NDJSON: envelope 한 건을 compact JSON 한 줄로 stdout에 출력.

    envelope.emit은 pretty-print(indent=2)라 스트림에 쓸 수 없어 직접 구성.
    스트림 이벤트에는 data.raw를 넣지 않는다 (크기 절약).
    """
    if fields and data is not None:
        data = envelope.project_fields(data, fields)
    doc = {
        "ok": error is None,
        "schema": envelope.SCHEMA,
        "data": data,
        "meta": envelope.build_meta() if meta is None else meta,
        "error": error,
    }
    click.echo(json.dumps(doc, ensure_ascii=False))
    sys.stdout.flush()


def _print_entry_table(entry: dict[str, Any]) -> None:
    """REAL 항목 한 건을 테이블 모드 한 줄로 출력 (기존 출력 형식 그대로)."""
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


# ── 스트림 루프 ───────────────────────────────────────


def run_stream(
    types: list[str],
    items: list[str],
    raw: bool = False,
    max_events: int | None = None,
    duration: str | None = None,
    until: str | None = None,
    record: str | None = None,
) -> None:
    """Connect to WebSocket and stream real-time data.

    max_events/duration/until 종료 조건 도달 시 소켓을 닫고 정상 종료(exit 0).
    json 모드에서는 REAL 이벤트를 NDJSON 한 줄씩, 오류는 envelope 오류 한 줄
    (exit 2, 인증은 exit 3)로 출력한다. table/raw 모드 출력은 기존과 동일.
    record가 None이 아니면 정규화 이벤트를 NDJSON 파일에도 기록한다
    (""=기본 레이아웃, 그 외=명시 경로. 출력 형식과 무관).
    """
    import asyncio

    json_mode = _get_format() == "json"
    # 입력 검증(UsageError -> exit 1)은 연결 시도 전에
    state = new_stream_state(max_events=max_events, duration=duration, until=until)

    recorder: NdjsonRecorder | None = None
    if record is not None:
        recorder = NdjsonRecorder(path=record or None)
        err_console.print(f"[dim]레코딩: {record or data_dir()}[/]")

    def _record(events: list[dict[str, Any]]) -> None:
        if recorder is not None:
            for ev in events:
                recorder.write(ev)

    try:
        import websockets
    except ImportError:
        human("[red]websockets 패키지가 필요합니다: pip install websockets[/]")
        return

    profile, ws_url = resolve_ws_target()
    token = auth.load_token(profile=profile)
    if not token:
        if json_mode:
            _emit_line(error=envelope.error_body(
                "토큰이 없습니다. 'kiwoom auth login'으로 발급하세요.",
                code="AUTH_REQUIRED", retryable=False,
            ))
            raise SystemExit(EXIT_AUTH)
        console.print("[red]토큰이 없습니다. 'kiwoom auth login'으로 발급하세요.[/]")
        return

    type_names = ", ".join(
        f"{t}({REALTIME_TYPES.get(t, ('?', ''))[0]})" for t in types
    )
    item_str = ", ".join(items) if items else "(계좌)"
    err_console.print(f"[dim]실시간 스트리밍 시작: {type_names}[/]")
    err_console.print(f"[dim]종목: {item_str}[/]")
    err_console.print("[dim]Ctrl+C로 종료[/]\n")

    # 이벤트마다 재계산하지 않도록 한 번만 (config 파일 I/O 절약)
    meta = envelope.build_meta()
    ctx = click.get_current_context(silent=True)
    fields = (ctx.obj or {}).get("fields") if ctx else None

    async def _stream() -> tuple[int, dict[str, Any] | None]:
        """(exit_code, error_body|None) 반환. 정상/종료조건 도달은 (0, None)."""
        url = f"{ws_url}/api/dostk/websocket"
        headers = {
            "content-type": "application/json;charset=UTF-8",
        }

        try:
            async with websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=None,
                ping_timeout=None,
            ) as ws:
                # Step 1: Send token authentication first
                auth_msg = {
                    "trnm": "LOGIN",
                    "token": token,
                }
                await ws.send(json.dumps(auth_msg))
                err_console.print("[dim]토큰 인증 요청...[/]")

                # Wait for auth response
                auth_resp = await ws.recv()
                try:
                    auth_data = json.loads(auth_resp)
                    if auth_data.get("code") and auth_data["code"] != "0":
                        msg = f"인증 실패: {auth_data.get('message', auth_resp)}"
                        if json_mode:
                            return EXIT_AUTH, envelope.error_body(
                                msg, code="AUTH_REQUIRED", retryable=False)
                        console.print(f"[red]{msg}[/]")
                        return 0, None
                    err_console.print("[green]인증 성공[/]")
                except json.JSONDecodeError:
                    pass

                # Step 2: Send registration
                reg_msg = _build_register_msg(types, items)
                await ws.send(json.dumps(reg_msg))
                err_console.print("[dim]종목 등록 요청...[/]")

                # Receive loop: 타이머(마감시각) 겸용 recv
                while True:
                    timeout = _remaining_seconds(state)
                    if timeout is not None and timeout <= 0:
                        break
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        break  # --duration/--until 도달 (유휴 스트림 포함)
                    except websockets.exceptions.ConnectionClosedOK:
                        break

                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        if raw:
                            console.print(message)
                        continue

                    if raw:
                        console.print_json(json.dumps(data, ensure_ascii=False))
                        _record(handle_message(data, state))  # raw도 종료 조건/레코딩은 계산
                        if should_stop(state, _now_kst()):
                            break
                        continue

                    trnm = data.get("trnm", "")

                    # Server sends PING as keepalive - echo it back
                    if trnm == "PING":
                        await ws.send(json.dumps({"trnm": "PING"}))
                        continue

                    # Handle system messages (login, errors)
                    if trnm == "SYSTEM":
                        msg = data.get("message", "")
                        code = data.get("code", "")
                        if code and code != "0":
                            human(f"[red]시스템: {msg}[/]")
                        else:
                            human(f"[dim]시스템: {msg}[/]")
                        continue

                    # Handle registration response
                    rc = data.get("return_code")
                    if rc is not None:
                        if str(rc) == "0":
                            err_console.print("[green]등록 성공[/]")
                        else:
                            msg = f"등록 실패: {data.get('return_msg', '')}"
                            if json_mode:
                                return EXIT_API, envelope.error_body(
                                    msg, code="UPSTREAM_ERROR", retryable=False)
                            console.print(f"[red]오류: {data.get('return_msg', '')}[/]")
                        continue

                    # Handle real-time data
                    events = handle_message(data, state)
                    _record(events)
                    if events:
                        if json_mode:
                            for ev in events:
                                _emit_line(ev, meta=meta, fields=fields)
                        else:
                            # max_events로 잘린 만큼만 출력
                            for entry in data.get("data", [])[:len(events)]:
                                _print_entry_table(entry)
                    elif trnm != "REAL":
                        # Other messages
                        human(f"[dim]{json.dumps(data, ensure_ascii=False)}[/]")

                    if should_stop(state, _now_kst()):
                        break

        except websockets.exceptions.ConnectionClosed as e:
            if json_mode:
                return EXIT_API, envelope.error_body(
                    f"연결 종료: {e}", code="UPSTREAM_ERROR", retryable=True)
            console.print(f"\n[yellow]연결 종료: {e}[/]")
        except ConnectionRefusedError:
            msg = "WebSocket 연결 실패. 도메인과 토큰을 확인하세요."
            if json_mode:
                return EXIT_API, envelope.error_body(msg, code="NETWORK_ERROR", retryable=True)
            console.print(f"[red]{msg}[/]")
        except Exception as e:
            if json_mode:
                return EXIT_API, envelope.error_body(f"오류: {e}", code="UPSTREAM_ERROR", retryable=False)
            console.print(f"[red]오류: {e}[/]")
        return 0, None

    try:
        exit_code, error = asyncio.run(_stream())
    except KeyboardInterrupt:
        console.print("\n[dim]스트리밍 종료[/]")
        exit_code, error = 0, None
    finally:
        if recorder is not None:
            recorder.close()
            if recorder.counts:
                for path, count in recorder.counts.items():
                    err_console.print(f"[dim]레코딩 완료: {path} ({count}건)[/]")
            else:
                err_console.print("[dim]레코딩 완료: 수신 이벤트 없음[/]")
    if error is not None:
        _emit_line(error=error, meta=meta, fields=fields)
    if exit_code:
        raise SystemExit(exit_code)
