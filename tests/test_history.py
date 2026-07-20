"""history list/query/export 커맨드 테스트 (녹화 NDJSON 읽기)."""

from __future__ import annotations

import json
import sqlite3
import sys

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from kiwoom_cli.streaming import handle_message


@pytest.fixture
def runner():
    return CliRunner()


def recorded_0d(hhmmss: str, symbol: str = "005930") -> dict:
    """레코더가 실제로 기록하는 모양의 0D 이벤트.

    손으로 쓴 dict을 쓰지 않는다 — 이전 픽스처들은 레코더가 만들 수 없는
    ts와 REST 필드명(sel_fpr_bid)을 손으로 넣어 0D 정규화 누락 버그를
    통째로 가렸다. 여기서는 서버 프레임을 handle_message에 통과시켜
    파이프라인이 내놓는 모양을 그대로 쓴다.
    """
    frame = {"trnm": "REAL", "data": [{
        "type": "0D", "name": "주식호가잔량", "item": symbol,
        "values": {
            "21": hhmmss,
            "41": "+70100", "61": "82",    # 매도호가1 / 매도호가수량1
            "51": "-69900", "71": "23847",  # 매수호가1 / 매수호가수량1
        },
    }]}
    return handle_message(frame, {})[0]


@pytest.fixture
def data_setup(tmp_path, monkeypatch):
    """<config dir>/data에 녹화 파일 3개 구성 (잘못된 줄 1개 포함)."""
    monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", tmp_path / "config.toml")
    d = tmp_path / "data"
    d.mkdir()

    def _dump(ev):
        return json.dumps(ev, ensure_ascii=False)

    (d / "005930_2026-07-16.ndjson").write_text("\n".join([
        _dump({"type": "0B", "type_name": "주식체결", "symbol": "005930",
               "ts": "10:00:00+09:00", "price": 70000, "volume": 10}),
        "NOT JSON",
        _dump({"type": "0B", "type_name": "주식체결", "symbol": "005930",
               "ts": "11:00:00+09:00", "price": 70100, "volume": -5}),
        _dump(recorded_0d("113000")),
    ]) + "\n", encoding="utf-8")

    (d / "005930_2026-07-15.ndjson").write_text(_dump(
        {"type": "0B", "type_name": "주식체결", "symbol": "005930",
         "ts": "14:00:00+09:00", "price": 69000, "volume": 3},
    ) + "\n", encoding="utf-8")

    (d / "주문체결_2026-07-16.ndjson").write_text(_dump(
        {"type": "00", "type_name": "주문체결", "symbol": "005930",
         "ts": "2026-07-16T10:30:00+09:00", "체결가": 70000},
    ) + "\n", encoding="utf-8")

    return d


# ── history list ──────────────────────────────────────


class TestHistoryList:
    def test_json_reports_per_file(self, runner, data_setup):
        result = runner.invoke(cli, ["-f", "json", "history", "list"])
        assert result.exit_code == 0
        doc = json.loads(result.stdout)
        assert doc["ok"] is True
        items = doc["data"]["items"]
        assert len(items) == 3
        by_file = {it["file"].rsplit("/", 1)[-1]: it for it in items}
        row = by_file["005930_2026-07-16.ndjson"]
        assert row["symbol"] == "005930"
        assert row["date"] == "2026-07-16"
        assert row["events"] == 3  # 잘못된 줄은 세지 않음
        assert row["first_ts"] == "10:00:00+09:00"
        assert row["last_ts"] == "11:30:00+09:00"
        order_row = by_file["주문체결_2026-07-16.ndjson"]
        assert order_row["symbol"] == "주문체결"
        assert order_row["events"] == 1

    def test_table_mode_ok(self, runner, data_setup):
        result = runner.invoke(cli, ["history", "list"])
        assert result.exit_code == 0
        assert "005930" in result.output
        # symbol은 코드 필드 — 숫자 포매팅(5,930) 금지
        assert "5,930" not in result.output

    def test_empty_dir_ok(self, runner, tmp_path, monkeypatch):
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        result = runner.invoke(cli, ["-f", "json", "history", "list"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["data"]["items"] == []


# ── history query ─────────────────────────────────────


class TestHistoryQuery:
    def test_all_events_for_code(self, runner, data_setup):
        result = runner.invoke(cli, ["-f", "json", "history", "query", "005930"])
        assert result.exit_code == 0
        items = json.loads(result.stdout)["data"]["items"]
        assert len(items) == 4  # 양일 파일 합산, 잘못된 줄 제외

    def test_malformed_line_warns_on_stderr(self, runner, data_setup):
        result = runner.invoke(cli, ["-f", "json", "history", "query", "005930"])
        assert result.exit_code == 0
        assert "잘못된 줄" in result.stderr
        assert "005930_2026-07-16.ndjson:2" in result.stderr
        json.loads(result.stdout)  # stdout은 단일 envelope 유지

    def test_ts_less_event_warns_instead_of_vanishing(self, runner, tmp_path,
                                                      monkeypatch):
        """ts가 없거나 못 읽는 이벤트를 시간 필터가 조용히 버리면 안 된다.

        이 조용한 폐기가 0D 버그(ts=None)를 보이지 않게 만들었다. 폐기는
        유지하되(범위 판정 불가) 반드시 stderr로 알린다.
        """
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        d = tmp_path / "data"
        d.mkdir()
        (d / "005930_2026-07-16.ndjson").write_text("\n".join([
            json.dumps({"type": "0B", "symbol": "005930",
                        "ts": "10:00:00+09:00", "price": 70000}),
            json.dumps({"type": "0D", "symbol": "005930", "ts": None,
                        "ask1": 70100}),
            json.dumps({"type": "0D", "symbol": "005930", "ts": "쓰레기",
                        "ask1": 70200}),
        ]) + "\n", encoding="utf-8")

        result = runner.invoke(cli, [
            "-f", "json", "history", "query", "005930",
            "--from", "2026-07-16T00:00:00",
        ])
        assert result.exit_code == 0
        doc = json.loads(result.stdout)  # stdout은 단일 envelope 유지
        assert len(doc["data"]["items"]) == 1
        assert "ts" in result.stderr and "2" in result.stderr
        assert "005930_2026-07-16.ndjson" in result.stderr
        # 경고가 stdout을 오염시키지 않았는지 (json 계약)
        assert "경고" not in result.stdout

    def test_no_time_filter_keeps_ts_less_events(self, runner, data_setup):
        """시간 필터가 없으면 ts 없는 이벤트도 살아남는다 (기존 동작 유지)."""
        result = runner.invoke(cli, ["-f", "json", "history", "query", "005930"])
        items = json.loads(result.stdout)["data"]["items"]
        assert len(items) == 4

    def test_range_filter(self, runner, data_setup):
        result = runner.invoke(cli, [
            "-f", "json", "history", "query", "005930",
            "--from", "2026-07-16T10:30:00", "--to", "2026-07-16T12:00:00",
        ])
        assert result.exit_code == 0
        items = json.loads(result.stdout)["data"]["items"]
        assert [it["ts"] for it in items] == ["11:00:00+09:00", "11:30:00+09:00"]

    def test_range_prunes_other_dates(self, runner, data_setup):
        result = runner.invoke(cli, [
            "-f", "json", "history", "query", "005930",
            "--from", "2026-07-16T00:00:00",
        ])
        items = json.loads(result.stdout)["data"]["items"]
        assert all(it["ts"].startswith(("10:", "11:")) for it in items)
        assert len(items) == 3

    def test_range_filter_discriminates_by_date_not_just_time_of_day(
        self, runner, colliding_days,
    ):
        """날짜만 다르고 시각이 같은 두 이벤트 중 하나만 남아야 한다.

        data_setup은 날마다 시각이 전부 달라서, 범위 필터가 파일명 날짜를
        전혀 안 보고 시각만 비교해도 통과했다 (구조적 맹목). 여기서는 시각이
        같으므로 날짜를 실제로 쓰지 않으면 0건 또는 2건이 나온다.
        """
        result = runner.invoke(cli, [
            "-f", "json", "history", "query", "005930",
            "--from", "2026-07-16T00:00:00", "--to", "2026-07-16T23:59:59",
        ])
        assert result.exit_code == 0
        items = json.loads(result.stdout)["data"]["items"]
        assert len(items) == 1, "날짜가 범위 판정에 반영되지 않았다"

    def test_type_filter(self, runner, data_setup):
        result = runner.invoke(cli, [
            "-f", "json", "history", "query", "005930", "--type", "0B",
        ])
        items = json.loads(result.stdout)["data"]["items"]
        assert len(items) == 3
        assert all(it["type"] == "0B" for it in items)

    def test_full_iso_ts_filters(self, runner, data_setup):
        result = runner.invoke(cli, [
            "-f", "json", "history", "query", "주문체결",
            "--from", "2026-07-16T10:00:00", "--to", "2026-07-16T11:00:00",
        ])
        items = json.loads(result.stdout)["data"]["items"]
        assert len(items) == 1
        assert items[0]["type"] == "00"

    def test_csv_output(self, runner, data_setup):
        result = runner.invoke(cli, [
            "-f", "csv", "history", "query", "005930", "--type", "0B",
        ])
        assert result.exit_code == 0
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 4  # header + 3
        assert lines[0].startswith("type")

    def test_bad_from_exits_1(self, runner, data_setup):
        result = runner.invoke(cli, ["history", "query", "005930", "--from", "nope"])
        assert result.exit_code == 1

    def test_no_files_empty(self, runner, data_setup):
        result = runner.invoke(cli, ["-f", "json", "history", "query", "999999"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["data"]["items"] == []

    def test_mixed_event_types_column_unique_to_later_row_survives(
        self, runner, tmp_path, monkeypatch,
    ):
        """감사 확인 #21/N29 — recorder.path_for는 심볼 기준으로 파일을 나누므로
        `stream multi`로 --record하면 0B(체결)와 0D(호가잔량)가 같은 파일에 섞여
        쓰인다. 0D 전용 필드(호가잔량 등)가 첫 행(0B)에 없다는 이유로 모든 행에서
        사라지면 안 된다 — csv/table 둘 다."""
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        d = tmp_path / "data"
        d.mkdir()

        def _dump(ev):
            return json.dumps(ev, ensure_ascii=False)

        (d / "005930_2026-07-16.ndjson").write_text("\n".join([
            _dump({"type": "0B", "type_name": "주식체결", "symbol": "005930",
                   "ts": "10:00:00+09:00", "price": 70000, "volume": 10}),
            _dump(recorded_0d("100005")),
        ]) + "\n", encoding="utf-8")

        csv_result = runner.invoke(cli, [
            "-f", "csv", "history", "query", "005930",
        ])
        assert csv_result.exit_code == 0
        lines = csv_result.stdout.strip().splitlines()
        header = lines[0].split(",")
        assert "ask1" in header, "0D 전용 필드가 첫 행(0B)에 없다고 CSV 헤더에서 누락됨"
        assert "70100" in lines[2], "0D 행에 자신의 고유 필드 값이 채워지지 않음"

        # 0D 이벤트는 컬럼이 11개라 기본 폭(80)에서는 Rich가 값을 잘라낸다.
        # 잘림은 렌더링 폭 문제이지 데이터 유실이 아니므로 폭을 넓혀서 본다.
        table_result = runner.invoke(cli, ["history", "query", "005930"],
                                     env={"COLUMNS": "250"})
        assert table_result.exit_code == 0
        # 컬럼 라벨로 확인. 레코딩된 WS 이벤트는 정규 영문명이 그대로 헤더가
        # 된다(price/volume/acc_volume도 동일) — 이전 픽스처가 REST 필드명
        # sel_fpr_bid를 넣는 바람에 한글 라벨 "매도호가"가 나왔던 것뿐이다.
        assert "ask1" in table_result.output, "테이블 출력에서 0D 전용 필드가 누락됨"
        assert "70,100" in table_result.output or "70100" in table_result.output


# ── history export ────────────────────────────────────


class TestHistoryExport:
    def test_sqlite_roundtrip(self, runner, data_setup, tmp_path):
        out = tmp_path / "out.sqlite"
        result = runner.invoke(cli, [
            "history", "export", "005930", "--dest", "sqlite", "--out", str(out),
        ])
        assert result.exit_code == 0
        con = sqlite3.connect(out)
        try:
            assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 4
            row = con.execute(
                "SELECT ts, symbol, type, price, volume FROM events "
                "WHERE price = 70100").fetchone()
            # export ts는 파일명 날짜와 결합된다 (녹화 파일의 ts는 시각만 담는다)
            assert row == ("2026-07-16T11:00:00+09:00", "005930", "0B", 70100.0, -5)
            raw = con.execute(
                "SELECT raw_json FROM events WHERE price = 70100").fetchone()[0]
            assert json.loads(raw)["price"] == 70100
            idx = con.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='events'").fetchall()
            assert idx  # (symbol, ts) 인덱스 존재
        finally:
            con.close()

    def test_0d_row_exports_with_null_price_volume_but_lossless_raw(
        self, runner, data_setup, tmp_path,
    ):
        """0D(호가 스냅샷)는 EXPORT_COLUMNS의 price/volume에 대응하는 값이 없다.

        의도된 동작이다 — 호가북에는 단일 '체결가'가 없고, 40여 개 호가 필드
        중 둘을 골라 price/volume에 억지로 넣으면 그게 체결가처럼 보인다.
        대신 ts/symbol/type은 채워지고 raw_json이 무손실로 전부 보존한다.
        (수정 전에는 ts까지 NULL이었고, 시간 필터를 걸면 행 자체가 사라졌다.)
        """
        out = tmp_path / "out.sqlite"
        result = runner.invoke(cli, [
            "history", "export", "005930", "--dest", "sqlite", "--out", str(out),
        ])
        assert result.exit_code == 0
        con = sqlite3.connect(out)
        try:
            row = con.execute(
                "SELECT ts, symbol, type, price, volume, raw_json FROM events "
                "WHERE type = '0D'").fetchone()
        finally:
            con.close()
        ts, symbol, type_, price, volume, raw = row
        assert (ts, symbol, type_) == ("2026-07-16T11:30:00+09:00", "005930", "0D")
        assert price is None and volume is None
        book = json.loads(raw)
        assert book["ask1"] == 70100 and book["bid1"] == 69900
        assert book["ask_qty1"] == 82 and book["bid_qty1"] == 23847

    def test_sqlite_range_filter(self, runner, data_setup, tmp_path):
        out = tmp_path / "out.sqlite"
        result = runner.invoke(cli, [
            "history", "export", "005930", "--dest", "sqlite", "--out", str(out),
            "--from", "2026-07-16T00:00:00",
        ])
        assert result.exit_code == 0
        con = sqlite3.connect(out)
        try:
            assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3
        finally:
            con.close()

    def test_csv_export(self, runner, data_setup, tmp_path):
        out = tmp_path / "out.csv"
        result = runner.invoke(cli, [
            "history", "export", "005930", "--dest", "csv", "--out", str(out),
        ])
        assert result.exit_code == 0
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "ts,symbol,type,price,volume,raw_json"
        assert len(lines) == 5  # header + 4

    def test_default_out_name(self, runner, data_setup, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["history", "export", "005930", "--dest", "sqlite"])
        assert result.exit_code == 0
        assert (tmp_path / "005930.sqlite").exists()

    def test_json_mode_reports_summary(self, runner, data_setup, tmp_path):
        out = tmp_path / "out.sqlite"
        result = runner.invoke(cli, [
            "-f", "json", "history", "export", "005930",
            "--dest", "sqlite", "--out", str(out),
        ])
        assert result.exit_code == 0
        doc = json.loads(result.stdout)
        assert doc["data"]["events"] == 4
        assert doc["data"]["format"] == "sqlite"

    def test_parquet_without_pandas_hints_and_exits_1(
            self, runner, data_setup, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "pandas", None)  # import 시 ImportError 유도
        result = runner.invoke(cli, [
            "history", "export", "005930", "--dest", "parquet",
            "--out", str(tmp_path / "out.parquet"),
        ])
        assert result.exit_code == 1
        assert "pandas" in result.stderr


# ── export: 출력 경로 생성 ──────────────────────────────


class TestExportParentDir:
    """--out의 상위 디렉터리가 없을 때. recorder.NdjsonRecorder.write와 같은
    패턴(parents=True, exist_ok=True)을 따라야 한다 — 유일하게 빠져 있었다."""

    @pytest.mark.parametrize("dest", ["sqlite", "csv"])
    def test_creates_missing_parent_dirs(self, runner, data_setup, tmp_path, dest):
        # 두 단계 깊이: mkdir(parents=True)가 아니면 못 만든다
        out = tmp_path / "exports" / "nested" / f"out.{dest}"
        assert not out.parent.exists()
        result = runner.invoke(cli, [
            "history", "export", "005930", "--dest", dest, "--out", str(out),
        ])
        # exit_code만 보면 안 된다: CliRunner는 잡히지 않은 예외도 exit 1로
        # 바꾸므로, 파일이 실제로 생겼는지가 판별 기준이다.
        assert result.exit_code == 0, result.output
        assert out.exists(), "상위 디렉터리를 만들지 않아 파일이 생성되지 않았다"

    def test_unmakeable_parent_is_input_error_not_traceback(
        self, runner, data_setup, tmp_path,
    ):
        """상위 경로가 '파일'이면 mkdir이 NotADirectoryError를 던진다.
        raw traceback(json 모드에서 envelope 없음) 대신 INVALID_INPUT이어야 한다."""
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        out = blocker / "sub" / "out.csv"
        result = runner.invoke(cli, [
            "-f", "json", "history", "export", "005930",
            "--dest", "csv", "--out", str(out),
        ])
        assert result.exit_code == 1
        # 판별 기준: stdout에 envelope이 실제로 있고 code가 INVALID_INPUT인지.
        # 수정 전에는 OSError가 그대로 튀어 stdout이 비어 있었다.
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            f"처리되지 않은 예외가 남았다: {result.exception!r}"
        )
        doc = json.loads(result.stdout)
        assert doc["ok"] is False
        assert doc["error"]["code"] == "INVALID_INPUT"


# ── export: sqlite 중복 ────────────────────────────────


def _events_ddl(con) -> str:
    return con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='events'"
    ).fetchone()[0]


@pytest.fixture
def colliding_days(tmp_path, monkeypatch):
    """서로 다른 날짜에 **같은 시각**의 이벤트를 두는 픽스처.

    data_setup은 이틀치를 담지만 시각이 전부 달라, ts가 시각만 담고 있어도
    (날짜가 빠져 있어도) 행이 서로 구분됐다 — dedup 컬럼의 날짜맹목을
    구조적으로 볼 수 없는 픽스처였다. 여기서는 날짜만 다르고 시각·심볼·타입이
    같은 두 이벤트를 만들어, 날짜가 ts에 실제로 반영되는지 판별한다.

    이벤트 **내용까지 완전히 동일**하게 둔다. 내용이 조금이라도 다르면
    raw_json이 갈려 DEDUP_COLUMNS가 날짜 없이도 두 행을 구분해 버리므로,
    날짜맹목 자체를 시험하려면 남는 차이가 날짜뿐이어야 한다.
    """
    monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", tmp_path / "config.toml")
    d = tmp_path / "data"
    d.mkdir()
    event = json.dumps({
        "type": "0B", "type_name": "주식체결", "symbol": "005930",
        "ts": "09:30:15+09:00", "price": 70000, "volume": 10,
    }, ensure_ascii=False) + "\n"
    for date in ("2026-07-15", "2026-07-16"):
        (d / f"005930_{date}.ndjson").write_text(event, encoding="utf-8")
    return d


class TestExportTsCarriesDate:
    """녹화 NDJSON의 ts는 시각만 담는다 (날짜는 파일명에만 있다).

    export가 그 시각을 그대로 쓰면 (a) DEDUP_COLUMNS가 날짜맹목이라 다른
    날의 서로 다른 이벤트가 한 건으로 접히고 (b) (symbol, ts) 인덱스가
    날짜를 가로질러 무의미해진다. export 시점에 파일명 날짜를 결합한다.
    """

    def test_same_time_on_different_days_survives_dedup(
        self, runner, colliding_days, tmp_path,
    ):
        out = tmp_path / "out.sqlite"
        result = runner.invoke(cli, [
            "-f", "json", "history", "export", "005930",
            "--dest", "sqlite", "--out", str(out),
        ])
        assert result.exit_code == 0, result.output
        con = sqlite3.connect(out)
        try:
            rows = con.execute("SELECT ts, price FROM events ORDER BY ts").fetchall()
        finally:
            con.close()
        assert rows == [
            ("2026-07-15T09:30:15+09:00", 70000.0),
            ("2026-07-16T09:30:15+09:00", 70000.0),
        ]
        # 보고한 건수도 실제 삽입 행수와 같아야 한다
        assert json.loads(result.stdout)["data"]["events"] == 2

    def test_csv_export_ts_also_carries_date(self, runner, colliding_days, tmp_path):
        out = tmp_path / "out.csv"
        assert runner.invoke(cli, [
            "history", "export", "005930", "--dest", "csv", "--out", str(out),
        ]).exit_code == 0
        rows = out.read_text(encoding="utf-8").strip().splitlines()
        assert rows[1].startswith("2026-07-15T09:30:15+09:00,")
        assert rows[2].startswith("2026-07-16T09:30:15+09:00,")

    def test_ndjson_recorded_shape_is_unchanged(self, runner, colliding_days):
        """on-the-wire 계약은 그대로다 — query는 녹화된 ts를 손대지 않는다."""
        result = runner.invoke(cli, ["-f", "json", "history", "query", "005930"])
        assert result.exit_code == 0
        items = json.loads(result.stdout)["data"]["items"]
        assert [it["ts"] for it in items] == ["09:30:15+09:00", "09:30:15+09:00"]

    def test_reexport_reports_zero_new_rows(self, runner, colliding_days, tmp_path):
        """두 번째 export는 아무것도 삽입하지 않으므로 events=0이어야 한다.
        (len(rows)를 보고하면 수집 건수 2를 보고해 DB 상태와 어긋난다.)"""
        out = tmp_path / "out.sqlite"
        args = ["-f", "json", "history", "export", "005930",
                "--dest", "sqlite", "--out", str(out)]
        assert runner.invoke(cli, args).exit_code == 0
        second = runner.invoke(cli, args)
        assert second.exit_code == 0
        assert json.loads(second.stdout)["data"]["events"] == 0
        con = sqlite3.connect(out)
        try:
            assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2
        finally:
            con.close()


class TestExportSqliteDedup:
    """sqlite는 csv/parquet(덮어쓰기)과 달리 append다. 같은 내용을 다시
    내보내면 행이 배로 늘었다 (PK도 UNIQUE도 없는 무조건 INSERT)."""

    def test_reexport_same_file_does_not_duplicate(self, runner, data_setup, tmp_path):
        out = tmp_path / "out.sqlite"
        args = ["history", "export", "005930", "--dest", "sqlite", "--out", str(out)]
        first = runner.invoke(cli, args)
        assert first.exit_code == 0, first.output
        second = runner.invoke(cli, args)
        assert second.exit_code == 0, second.output
        con = sqlite3.connect(out)
        try:
            # 핵심 판별: 행 "수". 두 번째 export가 성공했다는 것만으로는
            # 제약 유무를 구분할 수 없다.
            assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 4
        finally:
            con.close()

    def test_new_events_still_append_across_exports(
        self, runner, data_setup, tmp_path,
    ):
        """dedup이 'append 자체를 막는' 것으로 과잉되면 안 된다 — 새 이벤트는
        여전히 추가되어야 한다 (덮어쓰기가 아니라 중복만 무시)."""
        out = tmp_path / "out.sqlite"
        args = ["history", "export", "005930", "--dest", "sqlite", "--out", str(out)]
        assert runner.invoke(cli, args).exit_code == 0

        with open(data_setup / "005930_2026-07-17.ndjson", "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "type": "0B", "type_name": "주식체결", "symbol": "005930",
                "ts": "09:05:00+09:00", "price": 71000, "volume": 7,
            }, ensure_ascii=False) + "\n")

        assert runner.invoke(cli, args).exit_code == 0
        con = sqlite3.connect(out)
        try:
            assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 5
            assert con.execute(
                "SELECT COUNT(*) FROM events WHERE price = 71000").fetchone()[0] == 1
        finally:
            con.close()

    def test_preexisting_legacy_table_is_upgraded_and_deduped(
        self, runner, data_setup, tmp_path,
    ):
        """구 DDL(제약 없음)로 만들어진 기존 파일. CREATE TABLE IF NOT EXISTS는
        무시되므로 새 제약이 적용되지 않고 INSERT OR IGNORE가 그냥 INSERT로
        퇴화한다 — 조용히 계속 중복된다. 스키마를 승격해야 한다."""
        out = tmp_path / "legacy.sqlite"
        con = sqlite3.connect(out)
        try:
            con.execute(
                "CREATE TABLE events (ts TEXT, symbol TEXT, type TEXT, "
                "price REAL, volume INTEGER, raw_json TEXT)"
            )
            con.execute(
                "CREATE INDEX idx_events_symbol_ts ON events (symbol, ts)"
            )
            # 구 버전 버그로 이미 쌓인 중복 2건 + 보존되어야 할 고유 행 1건
            dup = ("09:00:00+09:00", "005930", "0B", 1.0, 1, '{"a": 1}')
            con.executemany("INSERT INTO events VALUES (?,?,?,?,?,?)", [dup, dup])
            con.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                        ("09:00:01+09:00", "005930", "0B", 2.0, 2, '{"a": 2}'))
            con.commit()
        finally:
            con.close()

        args = ["history", "export", "005930", "--dest", "sqlite", "--out", str(out)]
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, result.output
        assert result.exception is None, f"처리되지 않은 예외: {result.exception!r}"

        con = sqlite3.connect(out)
        try:
            # 스키마가 실제로 승격됐는지
            assert "UNIQUE" in _events_ddl(con).upper(), "구 스키마가 그대로 남았다"
            # 기존 고유 행 2종은 보존되고 중복 1건만 접힘 + 신규 4건
            assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2 + 4
            assert con.execute(
                "SELECT COUNT(*) FROM events WHERE ts = '09:00:00+09:00'"
            ).fetchone()[0] == 1
            # 임시 테이블이 남지 않았는지
            names = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            assert names == {"events"}, f"잔여 테이블: {names}"
            # (symbol, ts) 인덱스는 승격 후에도 살아 있어야 한다
            idx = con.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_events_symbol_ts'").fetchall()
            assert idx, "승격 과정에서 (symbol, ts) 인덱스가 사라졌다"
        finally:
            con.close()

        # 승격 후 재-export도 중복되지 않아야 한다
        assert runner.invoke(cli, args).exit_code == 0
        con = sqlite3.connect(out)
        try:
            assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2 + 4
        finally:
            con.close()
