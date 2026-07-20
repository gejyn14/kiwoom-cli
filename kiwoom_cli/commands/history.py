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
from ..formatters import _get_format, _output_csv, fail_input, print_generic_table
from ..output import console, err_console
from ..recorder import data_dir

KST = timezone(timedelta(hours=9))

_FILE_RE = re.compile(r"^(?P<key>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.ndjson$")

EXPORT_COLUMNS = ("ts", "symbol", "type", "price", "volume", "raw_json")

# sqlite는 csv/parquet(매번 덮어쓰기)과 달리 append이므로 재-export가 행을
# 배로 늘렸다. 아래 4개 컬럼으로 중복을 판정한다 — raw_json이 이벤트 전체를
# 담으므로 price/volume까지 넣을 필요가 없고, 0D처럼 price/volume이 NULL인
# 타입에서 NULL != NULL 때문에 제약이 무력해지는 것도 피한다.
DEDUP_COLUMNS = ("ts", "symbol", "type", "raw_json")

_EVENTS_DDL = (
    "CREATE TABLE IF NOT EXISTS events "
    "(ts TEXT, symbol TEXT, type TEXT, price REAL, volume INTEGER, raw_json TEXT, "
    f"UNIQUE({', '.join(DEDUP_COLUMNS)}))"
)

_EVENTS_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_events_symbol_ts ON events (symbol, ts)"
)


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


def _collect_with_dates(
    code: str,
    start: datetime | None,
    end: datetime | None,
    type_: str | None = None,
) -> list[tuple[dict[str, Any], str | None]]:
    """`_collect`와 같지만 각 이벤트에 **출처 파일의 날짜**를 붙여 돌려준다.

    녹화 NDJSON의 ts는 시각만 담고 날짜는 파일명에만 있다. 이벤트만 넘기면
    그 날짜가 호출자에게 도달하지 못해, export가 날짜맹목인 ts를 쓰게 된다
    (다른 날의 같은 시각 이벤트가 dedup에서 한 건으로 접힘).
    """
    rows: list[tuple[dict[str, Any], str | None]] = []
    for path in _files_for(code, start, end):
        fdate = _file_date(path)
        no_ts = 0  # ts를 못 읽어 범위 판정이 불가능했던 이벤트 수
        for ev in _iter_events(path):
            if type_ and ev.get("type") != type_:
                continue
            if start or end:
                dt = _event_dt(ev, fdate)
                if dt is None:
                    # ts가 없으면 범위 안팎을 판정할 수 없어 버린다. 조용히
                    # 버리면 정규화 누락(예: 0D의 ts=None)이 "데이터가 원래
                    # 없다"로 보여 버그를 가린다 — 반드시 알린다.
                    no_ts += 1
                    continue
                if start and dt < start:
                    continue
                if end and dt > end:
                    continue
            rows.append((ev, fdate))
        if no_ts:
            # stdout(json envelope/NDJSON)을 오염시키지 않도록 stderr로만
            err_console.print(
                f"[yellow]경고: ts를 읽을 수 없어 {no_ts}건 건너뜀 "
                f"({path.name}) — 시간 필터(--from/--to) 적용 중[/]"
            )
    return rows


def _collect(
    code: str,
    start: datetime | None,
    end: datetime | None,
    type_: str | None = None,
) -> list[dict[str, Any]]:
    """CODE의 이벤트를 파일 순서대로 수집 (ts 범위/타입 필터 적용).

    이벤트는 **녹화된 그대로** 돌려준다 (ts를 손대지 않는다). `history query`의
    출력은 녹화 NDJSON 한 줄과 같은 모양이라는 계약이므로, 날짜 결합은 여기가
    아니라 export 경로에서만 일어난다.
    """
    return [ev for ev, _ in _collect_with_dates(code, start, end, type_)]


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


def _export_ts(ev: dict[str, Any], file_date: str | None) -> Any:
    """export/dedup에 쓸 ts — 시각만 있는 녹화 ts에 출처 파일의 날짜를 결합한다.

    녹화 NDJSON의 ts는 "09:30:15+09:00"처럼 **시각만** 담는다 (WS의 HHMMSS
    필드를 normalize._iso_datetime이 그렇게 렌더한다). 날짜는 파일명에만 있다.
    그 값을 그대로 export하면 두 가지가 깨진다:

      1. DEDUP_COLUMNS(ts, symbol, type, raw_json) + INSERT OR IGNORE가
         날짜맹목이 된다. 여러 날을 한 번에 내보내면 날짜만 다른 별개
         이벤트가 조용히 한 건으로 접힌다.
      2. idx_events_symbol_ts (symbol, ts)가 날짜를 가로질러 무의미해진다.

    **녹화 파일의 ts는 바꾸지 않는다.** NDJSON 한 줄의 모양은 AGENTS.md가
    문서화한 계약이고 이미 기록된 파일과도 섞이므로, 날짜 결합은 파생물인
    export 값에서만 한다. `_event_dt`가 이미 --from/--to에 쓰는 것과 같은
    결합 규칙이다 (파일명 날짜 + 시각).

    파일명에서 날짜를 못 읽으면(명시 경로 녹화 등) 결합할 근거가 없으므로
    녹화된 ts를 그대로 둔다 — 날짜를 지어내지 않는다.
    """
    dt = _event_dt(ev, file_date)
    if dt is not None:
        return dt.isoformat()
    return ev.get("ts")


def _export_row(ev: dict[str, Any], file_date: str | None = None) -> tuple:
    return (
        _export_ts(ev, file_date),
        ev.get("symbol"),
        ev.get("type"),
        _num(ev.get("price"), float),
        _num(ev.get("volume"), int),
        json.dumps(ev, ensure_ascii=False),
    )


def _has_dedup_constraint(con: sqlite3.Connection) -> bool:
    """events 테이블에 DEDUP_COLUMNS UNIQUE 제약이 걸려 있는지.

    sqlite_master의 SQL 문자열을 grep하지 않는다 — 공백/대소문자/컬럼 순서에
    따라 오판한다. 실제 인덱스 메타데이터로 판정한다.
    """
    for row in con.execute("PRAGMA index_list('events')"):
        name, is_unique = row[1], row[2]
        if not is_unique:
            continue
        cols = [r[2] for r in con.execute(f"PRAGMA index_info('{name}')")]
        if cols == list(DEDUP_COLUMNS):
            return True
    return False


def _upgrade_legacy_events_table(con: sqlite3.Connection) -> None:
    """구 DDL(UNIQUE 없음)로 만들어진 events를 제약 있는 스키마로 승격.

    `CREATE TABLE IF NOT EXISTS`는 기존 테이블이 있으면 아무것도 하지 않으므로,
    구 파일에 재-export하면 새 제약이 붙지 않고 `INSERT OR IGNORE`가 사실상
    `INSERT`로 퇴화한다 — 조용히 계속 중복된다. 그래서 승격이 필요하다.

    기존 행 중 DEDUP_COLUMNS가 겹치는 것(=구 버전 버그로 쌓인 중복)은 이 과정에서
    한 건으로 접힌다. 의도된 것이다: 그 중복은 원래 같은 이벤트를 두 번 쓴 결과다.
    sqlite의 DDL은 트랜잭션 안에서 동작하므로 중간에 죽어도 반쪽 스키마로 남지 않는다.
    """
    con.execute("ALTER TABLE events RENAME TO events_legacy_migration")
    # 인덱스는 rename을 따라가므로 이름 충돌을 피하려면 먼저 지운다
    con.execute("DROP INDEX IF EXISTS idx_events_symbol_ts")
    con.execute(_EVENTS_DDL)
    cols = ", ".join(EXPORT_COLUMNS)
    con.execute(
        f"INSERT OR IGNORE INTO events ({cols}) "
        f"SELECT {cols} FROM events_legacy_migration"
    )
    con.execute("DROP TABLE events_legacy_migration")


def _export_sqlite(rows: list[tuple[dict[str, Any], str | None]], out: Path) -> int:
    """sqlite에 append하고 **실제로 삽입된 행 수**를 돌려준다.

    수집 건수(len(rows))가 아니다 — sqlite만 append라 INSERT OR IGNORE가
    기존 행과 겹치는 건 버린다. 수집 건수를 보고하면 `-f json` 소비자가
    "events: 2"를 받고 테이블엔 1행만 있는 상태가 된다.
    """
    con = sqlite3.connect(out)
    try:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone()
        if exists and not _has_dedup_constraint(con):
            _upgrade_legacy_events_table(con)
        con.execute(_EVENTS_DDL)
        con.execute(_EVENTS_INDEX_DDL)
        # OR IGNORE: 같은 이벤트를 다시 내보내도 행이 늘지 않는다 (재-export 멱등)
        before = con.total_changes
        con.executemany(
            "INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)",
            [_export_row(ev, fdate) for ev, fdate in rows],
        )
        inserted = con.total_changes - before
        con.commit()
    finally:
        con.close()
    return inserted


def _export_csv(rows: list[tuple[dict[str, Any], str | None]], out: Path) -> int:
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(EXPORT_COLUMNS)
        for ev, fdate in rows:
            w.writerow(_export_row(ev, fdate))
    return len(rows)


def _export_parquet(rows: list[tuple[dict[str, Any], str | None]], out: Path) -> int:
    try:
        import pandas as pd
        import pyarrow  # noqa: F401  (to_parquet 엔진 확인)
    except ImportError:
        fail_input(
            "parquet 내보내기에는 pandas와 pyarrow가 필요합니다: pip install pandas pyarrow",
            code="DEPENDENCY_MISSING",
        )
    df = pd.DataFrame([_export_row(ev, fdate) for ev, fdate in rows],
                      columns=EXPORT_COLUMNS)
    df.to_parquet(out)
    return len(rows)


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
    rows = _collect_with_dates(code, start, end)
    out_path = Path(out) if out else Path(f"{code}.{dest}")
    # recorder.NdjsonRecorder.write와 같은 패턴 — 상위 디렉터리를 만들어 둔다.
    # 없으면 sqlite/csv/parquet 각자 다른 예외를 raw traceback으로 던졌고,
    # json 모드에서는 envelope 없이 죽었다.
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        fail_input(
            f"출력 경로의 디렉터리를 만들 수 없습니다: {out_path.parent} ({e})",
            code="INVALID_INPUT",
        )
    # events는 수집 건수가 아니라 **실제로 쓰인 행 수**다. csv/parquet은 매번
    # 덮어쓰므로 둘이 같지만, sqlite는 append라 재-export가 0을 보고한다.
    if dest == "sqlite":
        written = _export_sqlite(rows, out_path)
    elif dest == "csv":
        written = _export_csv(rows, out_path)
    else:
        written = _export_parquet(rows, out_path)
    if _get_format() == "json":
        envelope.emit(data={"out": str(out_path), "format": dest, "events": written})
    else:
        console.print(f"[green]내보내기 완료:[/] {out_path} ({written}건, {dest})")
