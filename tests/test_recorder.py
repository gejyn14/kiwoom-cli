"""NdjsonRecorder 단위 테스트 + --record CLI 옵션 배선."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from kiwoom_cli.recorder import NdjsonRecorder, data_dir

KST = timezone(timedelta(hours=9))


def _today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


EV = {"type": "0B", "type_name": "주식체결", "symbol": "005930",
      "ts": "10:00:00+09:00", "price": 70000, "name": "삼성전자"}


@pytest.fixture
def runner():
    return CliRunner()


# ── 명시 경로 모드 ────────────────────────────────────


class TestExplicitPath:
    def test_writes_parseable_lines(self, tmp_path):
        p = tmp_path / "cap.ndjson"
        r = NdjsonRecorder(path=p)
        r.write(EV)
        r.write({**EV, "price": 70100})
        r.close()
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        docs = [json.loads(ln) for ln in lines]
        assert docs[0]["price"] == 70000
        assert docs[1]["price"] == 70100
        assert r.counts[p] == 2

    def test_non_ascii_written_raw(self, tmp_path):
        p = tmp_path / "cap.ndjson"
        r = NdjsonRecorder(path=p)
        r.write(EV)
        r.close()
        assert "삼성전자" in p.read_text(encoding="utf-8")

    def test_appends_across_reopens(self, tmp_path):
        p = tmp_path / "cap.ndjson"
        r1 = NdjsonRecorder(path=p)
        r1.write(EV)
        r1.close()
        r2 = NdjsonRecorder(path=p)
        r2.write({**EV, "price": 70100})
        r2.close()
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[1])["price"] == 70100
        assert r2.counts[p] == 1  # 카운트는 레코더 수명 기준

    def test_all_symbols_into_single_file(self, tmp_path):
        p = tmp_path / "cap.ndjson"
        r = NdjsonRecorder(path=p)
        r.write(EV)
        r.write({**EV, "symbol": "000660"})
        r.close()
        assert len(p.read_text(encoding="utf-8").splitlines()) == 2
        assert r.counts[p] == 2

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "cap.ndjson"
        r = NdjsonRecorder(path=p)
        r.write(EV)
        r.close()
        assert p.exists()


# ── 기본 레이아웃: <config dir>/data/<symbol>_<날짜>.ndjson ──


class TestDefaultLayout:
    @pytest.fixture(autouse=True)
    def _config_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        self.tmp = tmp_path

    def test_data_dir_is_config_dir_data(self):
        assert data_dir() == self.tmp / "data"

    def test_symbol_and_date_in_filename(self):
        r = NdjsonRecorder()
        path = r.write(EV)
        r.close()
        assert path == self.tmp / "data" / f"005930_{_today()}.ndjson"
        assert path.exists()

    def test_one_file_per_symbol(self):
        r = NdjsonRecorder()
        p1 = r.write(EV)
        p2 = r.write({**EV, "symbol": "000660"})
        r.close()
        assert p1 != p2
        assert p2.name == f"000660_{_today()}.ndjson"
        assert r.counts[p1] == 1
        assert r.counts[p2] == 1

    def test_account_stream_uses_type_name(self):
        # 계좌성 타입(00/04)은 심볼이 있어도 타입명으로 파일 구분
        ev = {"type": "00", "type_name": "주문체결", "symbol": "005930",
              "ts": "2026-07-16T10:00:00+09:00"}
        r = NdjsonRecorder()
        path = r.write(ev)
        r.close()
        assert path.name == f"주문체결_{_today()}.ndjson"

    def test_symbolless_event_falls_back_to_type_name(self):
        ev = {"type": "0s", "type_name": "장시작시간", "symbol": None}
        r = NdjsonRecorder()
        path = r.write(ev)
        r.close()
        assert path.name == f"장시작시간_{_today()}.ndjson"


# ── --record CLI 옵션 배선 ────────────────────────────


class TestRecordOption:
    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_flag_without_value_means_default_layout(self, mock_run, runner):
        result = runner.invoke(cli, ["stream", "quote", "005930", "--record"])
        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["record"] == ""

    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_flag_with_path(self, mock_run, runner, tmp_path):
        p = str(tmp_path / "cap.ndjson")
        result = runner.invoke(cli, ["stream", "quote", "005930", f"--record={p}"])
        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["record"] == p

    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_absent_means_none(self, mock_run, runner):
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["record"] is None

    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_account_command_has_record(self, mock_run, runner):
        result = runner.invoke(cli, ["stream", "order", "--record"])
        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["record"] == ""


# ── 하네스: handle_message → recorder.write (run_stream 훅 형상) ──


class TestRecordHarness:
    def test_events_recorded_regardless_of_format(self, tmp_path):
        from kiwoom_cli.streaming import handle_message, new_stream_state

        p = tmp_path / "cap.ndjson"
        r = NdjsonRecorder(path=p)
        state = new_stream_state(max_events=2)
        msg = {"trnm": "REAL", "data": [
            {"type": "0B", "item": "005930", "values": {"10": "+70000"}},
            {"type": "0B", "item": "005930", "values": {"10": "+70100"}},
            {"type": "0B", "item": "005930", "values": {"10": "+70200"}},
        ]}
        for ev in handle_message(msg, state):
            r.write(ev)
        r.close()
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2  # max_events로 잘린 만큼만 기록
        assert json.loads(lines[0])["price"] == 70000
