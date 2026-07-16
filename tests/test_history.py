"""history list/query/export 커맨드 테스트 (녹화 NDJSON 읽기)."""

from __future__ import annotations

import json
import sqlite3
import sys

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


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
        _dump({"type": "0D", "type_name": "주식호가잔량", "symbol": "005930",
               "ts": "11:30:00+09:00"}),
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
            assert row == ("11:00:00+09:00", "005930", "0B", 70100.0, -5)
            raw = con.execute(
                "SELECT raw_json FROM events WHERE price = 70100").fetchone()[0]
            assert json.loads(raw)["price"] == 70100
            idx = con.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='events'").fetchall()
            assert idx  # (symbol, ts) 인덱스 존재
        finally:
            con.close()

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
