"""스트리밍 NDJSON 출력 + 종료 조건 테스트 (실제 websocket 없음)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from kiwoom_cli.normalize import WS_FIELD_NAMES, normalize_ws_values
from kiwoom_cli.streaming import (
    KST,
    _emit_line,
    handle_message,
    new_stream_state,
    parse_duration,
    parse_until,
    should_stop,
)


@pytest.fixture
def runner():
    return CliRunner()


# ── 필드 ID 이름 맵 (공유 상수) ──────────────────────


class TestWsFieldNames:
    def test_map_moved_to_shared_constant(self):
        assert WS_FIELD_NAMES["10"] == "현재가"
        assert WS_FIELD_NAMES["12"] == "등락율"
        assert WS_FIELD_NAMES["908"] == "주문체결시간"


# ── normalize_ws_values ──────────────────────────────


class TestNormalizeWsValues:
    def test_quote_fields_typed_and_named(self):
        out = normalize_ws_values({
            "10": "+70000",
            "11": "+500",
            "12": "+0.72",
            "13": "123456",
            "15": "-10",
            "20": "153000",
            "302": "삼성전자",
        })
        assert out["price"] == 70000
        assert out["change_direction"] == "up"
        assert out["change"] == 500
        assert out["change_pct"] == 0.72
        assert out["acc_volume"] == 123456
        assert out["volume"] == -10  # 15는 부호 유의미 (+매수/-매도)
        assert out["ts"] == "15:30:00+09:00"
        assert out["name"] == "삼성전자"

    def test_abs_field_down_direction(self):
        out = normalize_ws_values({"10": "-70000"})
        assert out["price"] == 70000
        assert out["change_direction"] == "down"

    def test_order_fields_korean_fallback(self):
        out = normalize_ws_values({
            "9001": "A005930",
            "900": "10",
            "910": "+70500",
            "913": "체결",
            "908": "20260716153000",
        })
        assert out["symbol"] == "005930"  # 선행 A 제거
        assert out["주문수량"] == 10
        assert out["체결가"] == 70500
        assert out["주문상태"] == "체결"
        assert out["ts"] == "2026-07-16T15:30:00+09:00"

    def test_empty_string_passes_through(self):
        out = normalize_ws_values({"10": ""})
        assert out["price"] == ""

    def test_unknown_id_passes_through(self):
        out = normalize_ws_values({"9999": "x"})
        assert out["9999"] == "x"


# ── handle_message ────────────────────────────────────


def _real_msg(values=None, type_code="0B", item="005930"):
    return {
        "trnm": "REAL",
        "data": [{"type": type_code, "item": item, "values": values or {"10": "+70000"}}],
    }


class TestHandleMessage:
    def test_real_message_normalized_event(self):
        state = new_stream_state()
        events = handle_message(_real_msg({"10": "+70000", "12": "+0.72", "20": "153000"}), state)
        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "0B"
        assert ev["type_name"] == "주식체결"
        assert ev["symbol"] == "005930"
        assert ev["ts"] == "15:30:00+09:00"
        assert ev["price"] == 70000
        assert ev["change_pct"] == 0.72
        assert state["event_count"] == 1

    def test_ping_returns_empty(self):
        state = new_stream_state()
        assert handle_message({"trnm": "PING"}, state) == []
        assert state["event_count"] == 0

    def test_system_returns_empty(self):
        state = new_stream_state()
        assert handle_message({"trnm": "SYSTEM", "message": "hi", "code": "0"}, state) == []

    def test_registration_ack_returns_empty(self):
        state = new_stream_state()
        assert handle_message({"trnm": "REG", "return_code": 0}, state) == []

    def test_values_as_list_unwrapped(self):
        state = new_stream_state()
        msg = {"trnm": "REAL", "data": [{"type": "0B", "item": "005930", "values": [{"10": "+100"}]}]}
        events = handle_message(msg, state)
        assert events[0]["price"] == 100

    def test_symbol_falls_back_to_9001(self):
        state = new_stream_state()
        msg = {"trnm": "REAL", "data": [{"type": "00", "item": "", "values": {"9001": "A005930"}}]}
        events = handle_message(msg, state)
        assert events[0]["symbol"] == "005930"

    def test_max_events_truncates_entries(self):
        state = new_stream_state(max_events=3)
        entries = [{"type": "0B", "item": "005930", "values": {"10": "+1"}}] * 5
        events = handle_message({"trnm": "REAL", "data": entries}, state)
        assert len(events) == 3
        assert state["event_count"] == 3


# ── parse_duration / parse_until ─────────────────────


class TestParseDuration:
    @pytest.mark.parametrize("text,expected", [("30s", 30), ("5m", 300), ("2h", 7200)])
    def test_valid(self, text, expected):
        assert parse_duration(text) == expected

    @pytest.mark.parametrize("text", ["abc", "5x", "", "s", "1.5h", "-30s"])
    def test_invalid_raises_usage_error(self, text):
        with pytest.raises(click.UsageError):
            parse_duration(text)


class TestParseUntil:
    def test_naive_assumes_kst(self):
        dt = parse_until("2026-07-16T16:00:00")
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=9)

    def test_explicit_offset_preserved(self):
        dt = parse_until("2026-07-16T16:00:00+00:00")
        assert dt.utcoffset() == timedelta(0)

    def test_invalid_raises_usage_error(self):
        with pytest.raises(click.UsageError):
            parse_until("not-a-date")


# ── 종료 조건 (new_stream_state / should_stop) ───────


class TestStopConditions:
    def test_no_conditions_never_stops(self):
        state = new_stream_state()
        state["event_count"] = 1000
        assert should_stop(state, now=datetime.now(KST)) is False

    def test_max_events_reached(self):
        state = new_stream_state(max_events=3)
        state["event_count"] = 3
        assert should_stop(state) is True
        state["event_count"] = 2
        assert should_stop(state) is False

    def test_duration_deadline(self):
        base = datetime(2026, 7, 16, 15, 0, 0, tzinfo=KST)
        state = new_stream_state(duration="30s", now=base)
        assert state["deadline"] == base + timedelta(seconds=30)
        assert should_stop(state, now=base + timedelta(seconds=29)) is False
        assert should_stop(state, now=base + timedelta(seconds=30)) is True

    def test_until_deadline(self):
        base = datetime(2026, 7, 16, 15, 0, 0, tzinfo=KST)
        state = new_stream_state(until="2026-07-16T16:00:00", now=base)
        assert should_stop(state, now=base) is False
        assert should_stop(state, now=datetime(2026, 7, 16, 16, 0, 0, tzinfo=KST)) is True

    def test_duration_and_until_earliest_wins(self):
        base = datetime(2026, 7, 16, 15, 0, 0, tzinfo=KST)
        state = new_stream_state(duration="30s", until="2026-07-16T16:00:00", now=base)
        assert state["deadline"] == base + timedelta(seconds=30)


# ── NDJSON 출력 (_emit_line) ─────────────────────────


class TestEmitLine:
    def test_event_is_single_compact_line(self, capsys):
        _emit_line({"type": "0B", "price": 70000}, meta={})
        out = capsys.readouterr().out
        assert out.count("\n") == 1
        doc = json.loads(out)
        assert doc["ok"] is True
        assert doc["schema"] == "v1"
        assert doc["data"]["price"] == 70000
        assert doc["error"] is None
        assert "raw" not in doc["data"]

    def test_fields_projection(self, capsys):
        _emit_line({"type": "0B", "price": 70000, "volume": 5}, meta={}, fields=["price"])
        doc = json.loads(capsys.readouterr().out)
        assert doc["data"] == {"price": 70000}

    def test_error_line(self, capsys):
        from kiwoom_cli.envelope import error_body

        _emit_line(error=error_body("연결 종료", code="UPSTREAM_ERROR", retryable=True), meta={})
        doc = json.loads(capsys.readouterr().out)
        assert doc["ok"] is False
        assert doc["data"] is None
        assert doc["error"]["code"] == "UPSTREAM_ERROR"


# ── done-check 하네스: --max-events 3 → 정확히 3줄 ───


class TestMaxEventsHarness:
    def test_three_events_three_lines_then_stop(self, capsys):
        state = new_stream_state(max_events=3)
        stopped = False
        for _ in range(5):  # 3개 이후 도착하는 메시지는 소비되지 않아야 함
            events = handle_message(_real_msg(), state)
            for ev in events:
                _emit_line(ev, meta={})
            if should_stop(state):
                stopped = True
                break
        assert stopped
        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
        assert len(lines) == 3
        for ln in lines:
            doc = json.loads(ln)
            assert doc["ok"] is True
            assert doc["data"]["type"] == "0B"
            assert doc["data"]["price"] == 70000


# ── CLI 옵션 배선 ─────────────────────────────────────


class TestStreamCommandOptions:
    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_quote_passes_stop_options(self, mock_run, runner):
        result = runner.invoke(cli, [
            "-f", "json", "stream", "quote", "005930",
            "--max-events", "3", "--duration", "30s", "--until", "2026-07-16T16:00:00",
        ])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["0B"], ["005930"],
            raw=False, max_events=3, duration="30s", until="2026-07-16T16:00:00",
            record=None,
        )

    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_account_command_has_options(self, mock_run, runner):
        result = runner.invoke(cli, ["stream", "order", "--max-events", "1"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["00"], [], raw=False, max_events=1, duration=None, until=None,
            record=None,
        )

    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_custom_passes_types_and_options(self, mock_run, runner):
        result = runner.invoke(cli, ["stream", "custom", "0B,0D", "005930", "--duration", "5m"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["0B", "0D"], ["005930"],
            raw=False, max_events=None, duration="5m", until=None,
            record=None,
        )

    def test_bad_duration_exits_1_before_connecting(self, runner):
        result = runner.invoke(cli, ["stream", "quote", "005930", "--duration", "abc"])
        assert result.exit_code == 1

    def test_bad_max_events_exits_1(self, runner):
        result = runner.invoke(cli, ["stream", "quote", "005930", "--max-events", "0"])
        assert result.exit_code == 1


# ============================================================
#  Task 22: LOGIN/REG 핸드셰이크 — 실패 감지, 종료 코드, 프레임 순서
#
#  실측(.superpowers/sdd/task-22-login-frame-evidence.md):
#    LOGIN 응답 = {"trnm":"LOGIN","return_code":805004,"return_msg":"..."}
#    return_code는 int. code/message는 SYSTEM 프레임에만 있다.
#    prod는 LOGIN 응답 뒤에 SYSTEM 프레임을 보내지만 mock은 보내지 않는다.
# ============================================================

LOGIN_OK = {"trnm": "LOGIN", "return_code": 0, "return_msg": "정상"}
LOGIN_FAIL = {
    "trnm": "LOGIN",
    "return_code": 805004,
    "return_msg": "토큰 인증에 실패했습니다. 접속을 종료합니다 [CODE=8005, MESSAGE=Token이 유효하지 않습니다]",
}
SYSTEM_FRAME = {"trnm": "SYSTEM", "code": "R10004", "message": "접속허용요청(토큰)이 들어오지 않았습니다"}
REG_OK = {"trnm": "REG", "return_code": 0, "return_msg": "정상"}
REG_FAIL = {"trnm": "REG", "return_code": 1, "return_msg": "등록 종목수 초과"}


@pytest.fixture
def ws_env(monkeypatch):
    """가짜 websockets 모듈 + 토큰/도메인 고정. 실제 소켓·키체인·config 접근 없음."""
    import sys

    from tests.fakes import FakeWebsocketsModule, FakeWebSocket

    def _install(frames):
        ws = FakeWebSocket(frames)
        monkeypatch.setitem(sys.modules, "websockets", FakeWebsocketsModule(ws))
        return ws

    monkeypatch.setattr(
        "kiwoom_cli.streaming.resolve_ws_target", lambda: ("default", "wss://test.invalid")
    )
    monkeypatch.setattr("kiwoom_cli.streaming.auth.load_token", lambda profile=None: "tok")
    return _install


def _run(runner, ws_env, frames, *, fmt="table"):
    ws_env(frames)
    args = ["stream", "quote", "005930"]
    if fmt != "table":
        args = ["-f", fmt, *args]
    return runner.invoke(cli, args)


class TestStreamLoginFailure:
    def test_table_mode_exits_auth(self, runner, ws_env):
        """인증 실패는 table 모드에서도 exit 3 (기존: return_code를 못 읽어 '인증 성공' 후 exit 0)."""
        result = _run(runner, ws_env, [LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "인증 실패" in result.output
        assert "8005" in result.output
        assert "인증 성공" not in result.output

    def test_json_mode_exits_auth_with_envelope(self, runner, ws_env):
        result = _run(runner, ws_env, [LOGIN_FAIL], fmt="json")
        assert result.exit_code == 3, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs, result.output
        assert docs[-1]["ok"] is False
        assert docs[-1]["error"]["code"] == "AUTH_REQUIRED"

    def test_return_code_is_int_not_string(self, runner, ws_env):
        """실측상 return_code는 int다. 문자열 비교(rc != "0")로 짜면 성공도 실패로 읽힌다."""
        result = _run(runner, ws_env, [LOGIN_OK, REG_OK])
        assert result.exit_code == 0, result.output
        assert "인증 성공" in result.output

    def test_string_return_code_also_accepted(self, runner, ws_env):
        result = _run(runner, ws_env, [{"trnm": "LOGIN", "return_code": "0"}, REG_OK])
        assert result.exit_code == 0, result.output
        assert "인증 성공" in result.output


class TestStreamLoginFrameOrder:
    def test_system_frame_before_login_ack_is_skipped(self, runner, ws_env):
        """prod 전용 동작: SYSTEM이 먼저 와도 LOGIN ack를 놓치지 않는다.

        SYSTEM을 ack로 오독해도 exit 3이 나오므로 종료 코드만으로는 구분되지 않는다.
        실제로 뒤의 LOGIN 프레임을 읽었는지는 return_msg 내용(8005)으로 고정한다.
        """
        result = _run(runner, ws_env, [SYSTEM_FRAME, LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "인증 실패" in result.output
        assert "8005" in result.output, "SYSTEM 프레임을 LOGIN ack로 오독했다"
        assert "시스템: 접속허용요청" in result.output, "건너뛴 SYSTEM 프레임이 표시되지 않았다"

    def test_ping_before_login_ack_is_echoed_and_skipped(self, runner, ws_env):
        ws = ws_env([{"trnm": "PING"}, LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 0, result.output
        assert "인증 성공" in result.output
        assert ws.sent_trnms() == ["LOGIN", "PING", "REG"]

    def test_skip_loop_is_bounded(self, runner, ws_env):
        """서버가 SYSTEM만 계속 보내도 매달리지 않고 인증 오류로 끝난다."""
        ws = ws_env([SYSTEM_FRAME] * 40 + [LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 3, result.output
        assert ws.frames, "건너뛰기 루프가 큐 전체를 소비했다 = 상한이 없다"


class TestStreamRegistrationFailure:
    def test_table_mode_exits_api(self, runner, ws_env):
        """등록 실패는 table 모드에서도 exit 2 (기존: 빨간 글씨 후 continue → 미구독 소켓)."""
        result = _run(runner, ws_env, [LOGIN_OK, REG_FAIL])
        assert result.exit_code == 2, result.output
        assert "등록 종목수 초과" in result.output

    def test_json_mode_exits_api(self, runner, ws_env):
        result = _run(runner, ws_env, [LOGIN_OK, REG_FAIL], fmt="json")
        assert result.exit_code == 2, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["error"]["code"] == "UPSTREAM_ERROR"

    def test_success_path_streams_real_events(self, runner, ws_env):
        result = _run(runner, ws_env, [LOGIN_OK, REG_OK, _real_msg()], fmt="json")
        assert result.exit_code == 0, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["data"]["price"] == 70000


class TestStreamMissingToken:
    def test_table_mode_exits_auth(self, runner, ws_env, monkeypatch):
        """토큰 없음도 table/json 양쪽에서 exit 3 (기존 table: 메시지 후 exit 0)."""
        ws_env([])
        monkeypatch.setattr("kiwoom_cli.streaming.auth.load_token", lambda profile=None: None)
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 3, result.output
        assert "토큰이 없습니다" in result.output

    def test_json_mode_exits_auth(self, runner, ws_env, monkeypatch):
        ws_env([])
        monkeypatch.setattr("kiwoom_cli.streaming.auth.load_token", lambda profile=None: None)
        result = runner.invoke(cli, ["-f", "json", "stream", "quote", "005930"])
        assert result.exit_code == 3, result.output
