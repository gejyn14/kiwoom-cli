"""녹화된 실시간 스트림 조회 (--record로 저장된 NDJSON 읽기).

파일은 <config dir>/data/<symbol>_<YYYY-MM-DD>.ndjson 레이아웃을 가정한다
(계좌성 스트림은 심볼 대신 타입명). 파일 전체를 메모리에 올리지 않고
한 줄씩 스트리밍으로 읽는다.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click

from .. import envelope
from ..formatters import _get_format, _output_csv, print_generic_table
from ..output import console, err_console
from ..recorder import data_dir

EXIT_INPUT = 1  # main.py와 동일 (순환 import 회피)

KST = timezone(timedelta(hours=9))

_FILE_RE = re.compile(r"^(?P<key>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.ndjson$")

EXPORT_COLUMNS = ("ts", "symbol", "type", "price", "volume", "raw_json")


@click.group("history")
def history():
    """녹화된 실시간 데이터 조회 (stream --record로 저장된 NDJSON)."""
    pass


# ── 공용 헬퍼 ─────────────────────────────────────────


def _parse_bound(text: str | None, opt: str) -> datetime | None:
    """--from/--to/--until ISO-8601 파싱. 타임존 없으면 +09:00(KST) 가정."""
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.strip())
    except ValueError:
        raise click.UsageError(
            f"{opt} 형식 오류: {text!r} (ISO-8601, 예: 2026-07-16T10:30:00)"
        ) from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt


def _file_date(path: Path) -> str | None:
    m = _FILE_RE.match(path.name)
    return m.group("date") if m else None


def _files_for(code: str, start: datetime | None, end: datetime | None) -> list[Path]:
    """CODE의 녹화 파일 목록. 파일명 날짜로 범위 밖 파일은 미리 건너뜀."""
    files = []
    for p in sorted(data_dir().glob(f"{code}_*.ndjson")):
        d = _file_date(p)
        if d:
            if start and d < start.astimezone(KST).date().isoformat():
                continue
            if end and d > end.astimezone(KST).date().isoformat():
                continue
        files.append(p)
    return files


def _iter_events(path: Path, warn: bool = True) -> Iterator[dict[str, Any]]:
    """NDJSON 파일을 한 줄씩 읽어 이벤트 dict를 낸다 (잘못된 줄은 건너뜀)."""
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                ev = None
            if not isinstance(ev, dict):
                if warn:
                    err_console.print(
                        f"[yellow]경고: 잘못된 줄 건너뜀 ({path.name}:{lineno})[/]"
                    )
                continue
            yield ev


def _event_dt(ev: dict[str, Any], file_date: str | None) -> datetime | None:
    """이벤트 ts -> aware datetime. 시간만 있는 ts는 파일명 날짜와 결합."""
    ts = ev.get("ts")
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        if file_date is None:
            return None
        try:
            dt = datetime.fromisoformat(f"{file_date}T{ts}")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt


def _collect(
    code: str,
    start: datetime | None,
    end: datetime | None,
    type_: str | None = None,
) -> list[dict[str, Any]]:
    """CODE의 이벤트를 파일 순서대로 수집 (ts 범위/타입 필터 적용)."""
    rows: list[dict[str, Any]] = []
    for path in _files_for(code, start, end):
        fdate = _file_date(path)
        for ev in _iter_events(path):
            if type_ and ev.get("type") != type_:
                continue
            if start or end:
                dt = _event_dt(ev, fdate)
                if dt is None:
                    continue
                if start and dt < start:
                    continue
                if end and dt > end:
                    continue
            rows.append(ev)
    return rows


# ── list ──────────────────────────────────────────────


@history.command("list")
def history_list():
    """녹화 파일 목록 — 심볼, 날짜, 이벤트 수, 시작/종료 ts."""
    rows: list[dict[str, Any]] = []
    base = data_dir()
    for path in sorted(base.glob("*.ndjson")) if base.is_dir() else []:
        m = _FILE_RE.match(path.name)
        count = 0
        first_ts = last_ts = None
        for ev in _iter_events(path, warn=False):
            count += 1
            ts = ev.get("ts")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
        rows.append({
            "file": str(path),
            "symbol": m.group("key") if m else path.stem,
            "date": m.group("date") if m else None,
            "events": count,
            "first_ts": first_ts,
            "last_ts": last_ts,
        })
    fmt = _get_format()
    if fmt == "json":
        envelope.emit(data={"items": rows})
    elif fmt == "csv":
        _output_csv(rows)
    else:
        # 전체 경로는 테이블 폭을 넘겨 잘리므로 파일명만 (디렉토리는 제목에)
        short = [{**r, "file": Path(r["file"]).name} for r in rows]
        print_generic_table(short, title=f"녹화 파일 ({base})")


# ── query ─────────────────────────────────────────────


@history.command("query")
@click.argument("code")
@click.option("--from", "from_", default=None,
              help="시작 시각 (ISO-8601, 타임존 없으면 +09:00)")
@click.option("--to", "to", default=None,
              help="종료 시각 (ISO-8601, 타임존 없으면 +09:00)")
@click.option("--type", "type_", default=None, help="실시간 타입 필터 (예: 0B)")
def history_query(code: str, from_: str | None, to: str | None, type_: str | None):
    """CODE의 녹화 이벤트 조회 — 파일을 한 줄씩 읽어 ts 범위/타입 필터."""
    start = _parse_bound(from_, "--from")
    end = _parse_bound(to, "--to")
    rows = _collect(code, start, end, type_)
    fmt = _get_format()
    if fmt == "json":
        envelope.emit(data={"items": rows})
    elif fmt == "csv":
        _output_csv(rows)
    else:
        print_generic_table(rows, title=f"{code} 녹화 이벤트")


# ── export ────────────────────────────────────────────


def _num(value: Any, cast: type) -> Any:
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _export_row(ev: dict[str, Any]) -> tuple:
    return (
        ev.get("ts"),
        ev.get("symbol"),
        ev.get("type"),
        _num(ev.get("price"), float),
        _num(ev.get("volume"), int),
        json.dumps(ev, ensure_ascii=False),
    )


def _export_sqlite(rows: list[dict[str, Any]], out: Path) -> None:
    con = sqlite3.connect(out)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS events "
            "(ts TEXT, symbol TEXT, type TEXT, price REAL, volume INTEGER, raw_json TEXT)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_symbol_ts ON events (symbol, ts)"
        )
        con.executemany(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            [_export_row(ev) for ev in rows],
        )
        con.commit()
    finally:
        con.close()


def _export_csv(rows: list[dict[str, Any]], out: Path) -> None:
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(EXPORT_COLUMNS)
        for ev in rows:
            w.writerow(_export_row(ev))


def _export_parquet(rows: list[dict[str, Any]], out: Path) -> None:
    try:
        import pandas as pd
        import pyarrow  # noqa: F401  (to_parquet 엔진 확인)
    except ImportError:
        err_console.print(
            "[red]parquet 내보내기에는 pandas와 pyarrow가 필요합니다: "
            "pip install pandas pyarrow[/]"
        )
        raise SystemExit(EXIT_INPUT) from None
    df = pd.DataFrame([_export_row(ev) for ev in rows], columns=EXPORT_COLUMNS)
    df.to_parquet(out)


@history.command("export")
@click.argument("code")
@click.option("--dest", "dest", required=True,
              type=click.Choice(["sqlite", "csv", "parquet"]), help="내보내기 형식")
@click.option("--out", "out", default=None, help="출력 파일 경로 (기본: <CODE>.<형식>)")
@click.option("--from", "from_", default=None,
              help="시작 시각 (ISO-8601, 타임존 없으면 +09:00)")
@click.option("--to", "to", default=None,
              help="종료 시각 (ISO-8601, 타임존 없으면 +09:00)")
def history_export(code: str, dest: str, out: str | None,
                   from_: str | None, to: str | None):
    """CODE의 녹화 이벤트를 sqlite/csv/parquet 파일로 내보내기."""
    start = _parse_bound(from_, "--from")
    end = _parse_bound(to, "--to")
    rows = _collect(code, start, end)
    out_path = Path(out) if out else Path(f"{code}.{dest}")
    if dest == "sqlite":
        _export_sqlite(rows, out_path)
    elif dest == "csv":
        _export_csv(rows, out_path)
    else:
        _export_parquet(rows, out_path)
    if _get_format() == "json":
        envelope.emit(data={"out": str(out_path), "format": dest, "events": len(rows)})
    else:
        console.print(f"[green]내보내기 완료:[/] {out_path} ({len(rows)}건, {dest})")
