"""Real-time WebSocket streaming commands.

Covers all 19 real-time type codes:
  00: 주문체결, 04: 잔고, 0A: 주식기세, 0B: 주식체결, 0C: 주식우선호가,
  0D: 주식호가잔량, 0E: 주식시간외호가, 0F: 주식당일거래원, 0G: ETF NAV,
  0H: 주식예상체결, 0I: 국제금환산가격, 0J: 업종지수, 0U: 업종등락,
  0g: 주식종목정보, 0m: ELW 이론가, 0s: 장시작시간, 0u: ELW 지표,
  0w: 종목프로그램매매, 1h: VI발동/해제
"""

from __future__ import annotations

import click

from .. import envelope
from ..formatters import _get_format
from ..streaming import REALTIME_TYPES, run_stream


def _stream_options(f):
    """모든 스트림 커맨드 공용 옵션 (--raw + 종료 조건 + --record)."""
    f = click.option("--record", "record", is_flag=False, flag_value="", default=None,
                     help="이벤트를 NDJSON 파일에 저장 (경로 생략 시 설정 디렉토리의 "
                          "data/<심볼>_<날짜>.ndjson). 출력 형식과 무관하게 동작")(f)
    f = click.option("--until", "until", default=None,
                     help="이 시각 도달 시 종료 (ISO-8601, 타임존 없으면 +09:00)")(f)
    f = click.option("--duration", "duration", default=None,
                     help="이 시간 경과 시 종료 (예: 30s, 5m, 2h)")(f)
    f = click.option("--max-events", "max_events", type=click.IntRange(min=1), default=None,
                     help="이 개수만큼 이벤트 수신 후 종료")(f)
    f = click.option("--raw", is_flag=True, help="JSON 원본 출력")(f)
    return f


@click.group("stream")
def stream():
    """실시간 시세 스트리밍 (WebSocket).

    \b
    사용법:
      kiwoom stream quote 005930         # 주식체결 실시간
      kiwoom stream orderbook 005930     # 호가잔량 실시간
      kiwoom stream order                # 주문체결 실시간
      kiwoom stream custom 0B 005930 000660  # 커스텀 타입+종목
      kiwoom -f json stream quote 005930 --max-events 3  # NDJSON, 3건 후 종료
    """
    pass


# ── 주식 시세 ─────────────────────────────────────────

@stream.command("quote")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def quote(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식체결 실시간 (0B). 현재가, 체결시간, 거래량 등."""
    run_stream(["0B"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("price")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def price(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식기세 실시간 (0A). 현재가, 등락율, 시고저."""
    run_stream(["0A"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("orderbook")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def orderbook(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식호가잔량 실시간 (0D). 10단계 호가."""
    run_stream(["0D"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("best-bid")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def best_bid(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식우선호가 실시간 (0C). 최우선 매도/매수 호가."""
    run_stream(["0C"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("after-hours")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def after_hours(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식시간외호가 실시간 (0E)."""
    run_stream(["0E"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("expected")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def expected(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식예상체결 실시간 (0H). 예상 체결가/수량."""
    run_stream(["0H"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("stock-info")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def stock_info(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식종목정보 실시간 (0g)."""
    run_stream(["0g"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


# ── 거래원/프로그램 ───────────────────────────────────

@stream.command("trader")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def trader(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식당일거래원 실시간 (0F)."""
    run_stream(["0F"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("program")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def program(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """종목프로그램매매 실시간 (0w)."""
    run_stream(["0w"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


# ── 계좌 (종목코드 불필요) ────────────────────────────

@stream.command("order")
@_stream_options
def order_exec(raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주문체결 실시간 (00). 주문 접수/체결/정정/취소."""
    run_stream(["00"], [], raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("balance")
@_stream_options
def balance(raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """잔고 실시간 (04). 보유잔고 변동."""
    run_stream(["04"], [], raw=raw, max_events=max_events, duration=duration, until=until, record=record)


# ── 업종/지수 ─────────────────────────────────────────

@stream.command("sector-index")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def sector_index(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """업종지수 실시간 (0J)."""
    run_stream(["0J"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("sector-change")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def sector_change(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """업종등락 실시간 (0U)."""
    run_stream(["0U"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


# ── ETF/ELW ───────────────────────────────────────────

@stream.command("etf-nav")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def etf_nav(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """ETF NAV 실시간 (0G)."""
    run_stream(["0G"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("elw-theory")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def elw_theory(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """ELW 이론가 실시간 (0m)."""
    run_stream(["0m"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("elw-indicator")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def elw_indicator(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """ELW 지표 실시간 (0u)."""
    run_stream(["0u"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


# ── 금현물/시장 ───────────────────────────────────────

@stream.command("gold")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def gold(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """국제금환산가격 실시간 (0I)."""
    run_stream(["0I"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("market-time")
@_stream_options
def market_time(raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """장시작시간 실시간 (0s). 장 시작/마감 알림."""
    run_stream(["0s"], [], raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("vi")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def vi(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """VI발동/해제 실시간 (1h)."""
    run_stream(["1h"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


# ── 멀티/커스텀 ───────────────────────────────────────

@stream.command("multi")
@click.argument("codes", nargs=-1, required=True)
@_stream_options
def multi(codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """주식체결+호가잔량 동시 스트리밍 (0B+0D).

    예: kiwoom stream multi 005930 000660
    """
    run_stream(["0B", "0D"], list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("custom")
@click.argument("type_codes")
@click.argument("codes", nargs=-1)
@_stream_options
def custom(type_codes: str, codes: tuple[str, ...], raw: bool, max_events: int | None, duration: str | None, until: str | None, record: str | None):
    """커스텀 실시간 타입으로 스트리밍.

    \b
    TYPE_CODES는 쉼표로 구분 (예: 0B,0D)
    사용 가능한 타입:
      00: 주문체결    04: 잔고       0A: 주식기세
      0B: 주식체결    0C: 우선호가   0D: 호가잔량
      0E: 시간외호가  0F: 당일거래원 0G: ETF NAV
      0H: 예상체결    0I: 국제금     0J: 업종지수
      0U: 업종등락    0g: 종목정보   0m: ELW이론가
      0s: 장시작시간  0u: ELW지표    0w: 프로그램매매
      1h: VI발동해제

    예: kiwoom stream custom 0B,0D 005930 000660
    """
    types = [t.strip() for t in type_codes.split(",")]
    invalid = [t for t in types if t not in REALTIME_TYPES]
    if invalid:
        raise click.ClickException(f"잘못된 실시간 타입: {', '.join(invalid)}")
    run_stream(types, list(codes), raw=raw, max_events=max_events, duration=duration, until=until, record=record)


@stream.command("types")
def list_types():
    """사용 가능한 실시간 타입 코드 목록."""
    if _get_format() == "json":
        envelope.emit(data=[
            {"type": code, "name": name, "description": desc}
            for code, (name, desc) in REALTIME_TYPES.items()
        ])
        return
    from rich.table import Table
    from ..output import console

    t = Table(title="실시간 타입 코드", border_style="dim")
    t.add_column("코드", style="bold")
    t.add_column("이름")
    t.add_column("설명", style="dim")

    for code, (name, desc) in REALTIME_TYPES.items():
        t.add_row(code, name, desc)
    console.print(t)
