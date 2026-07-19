"""watch(실시간 TUI 대시보드) 커맨드 테스트 — 실제 websocket 없음.

watch.py는 오랫동안 테스트가 없었고 어떤 실패 경로에서도 0이 아닌 종료 코드를
내지 않았다. 여기서 고정하는 것: 프레임 순서 가정 제거, 실패 종료 코드,
json 모드 거부, 예외 처리.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient, FakeWebSocket, FakeWebsocketsModule

LOGIN_OK = {"trnm": "LOGIN", "return_code": 0, "return_msg": "정상"}
LOGIN_FAIL = {
    "trnm": "LOGIN",
    "return_code": 805004,
    "return_msg": "토큰 인증에 실패했습니다 [CODE=8005, MESSAGE=Token이 유효하지 않습니다]",
}
SYSTEM_FRAME = {"trnm": "SYSTEM", "code": "R10004", "message": "접속허용요청이 들어오지 않았습니다"}
REG_OK = {"trnm": "REG", "return_code": 0, "return_msg": "정상"}
REG_FAIL = {"trnm": "REG", "return_code": 1, "return_msg": "등록 종목수 초과"}


def _real(price="+70000", item="005930"):
    return {"trnm": "REAL", "data": [{"type": "0B", "item": item, "values": {"10": price}}]}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def watch_env(monkeypatch):
    """가짜 REST 클라이언트 + 가짜 websockets 모듈 + 고정 토큰/도메인."""
    import sys

    fake_rest = FakeKiwoomClient()
    fake_rest.set_response("ka10001", {"stk_nm": "삼성전자", "cur_prc": "+70000"})
    monkeypatch.setattr("kiwoom_cli.commands.watch.KiwoomClient", lambda *a, **k: fake_rest)
    monkeypatch.setattr(
        "kiwoom_cli.commands.watch.resolve_ws_target", lambda: ("default", "wss://test.invalid")
    )
    monkeypatch.setattr("kiwoom_cli.auth.load_token", lambda profile=None: "tok")

    state: dict = {"rest": fake_rest, "ws": None}

    def _install(frames):
        ws = FakeWebSocket(frames)
        state["ws"] = ws
        monkeypatch.setitem(sys.modules, "websockets", FakeWebsocketsModule(ws))
        return ws

    state["install"] = _install
    return state


def _run(runner, watch_env, frames, *, fmt="table", args=("005930",)):
    watch_env["install"](frames)
    argv = ["watch", *args]
    if fmt != "table":
        argv = ["-f", fmt, *argv]
    return runner.invoke(cli, argv)


# ── json 모드 거부 (감사 N41) ────────────────────────


class TestWatchFormatRejection:
    @pytest.mark.parametrize("fmt", ["json", "csv"])
    def test_non_table_format_rejected(self, runner, watch_env, fmt):
        """watch는 Rich TUI라 NDJSON 계약을 지킬 수 없다 → 조용히 TUI를 띄우지 말고 거부."""
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK], fmt=fmt)
        assert result.exit_code == 1, result.output
        assert "table 출력 전용" in result.output
        assert "stream quote" in result.output

    def test_json_mode_emits_error_envelope(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK], fmt="json")
        doc = json.loads(result.output)  # envelope.emit은 pretty-print
        assert doc["ok"] is False
        assert doc["error"]["code"] == "INVALID_INPUT"

    def test_rejected_before_any_api_call(self, runner, watch_env):
        """거부는 REST 조회 전에 일어나야 한다 (쓸데없는 호출·지연 방지)."""
        _run(runner, watch_env, [LOGIN_OK, REG_OK], fmt="json")
        assert watch_env["rest"].calls == []

    def test_table_mode_still_runs(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK, _real()])
        assert result.exit_code == 0, result.output


# ── 실패 경로 종료 코드 ──────────────────────────────


class TestWatchExitCodes:
    def test_missing_token_exits_auth(self, runner, watch_env, monkeypatch):
        monkeypatch.setattr("kiwoom_cli.auth.load_token", lambda profile=None: None)
        result = _run(runner, watch_env, [])
        assert result.exit_code == 3, result.output
        assert "토큰이 없습니다" in result.output

    def test_auth_failure_exits_auth(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "인증 실패" in result.output
        assert "8005" in result.output

    def test_registration_failure_exits_api(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, REG_FAIL])
        assert result.exit_code == 2, result.output
        assert "등록 종목수 초과" in result.output

    def test_missing_ack_exits_auth(self, runner, watch_env):
        """서버가 ack를 아예 안 주면 성공으로 넘어가지 않는다."""
        result = _run(runner, watch_env, [SYSTEM_FRAME] * 40)
        assert result.exit_code == 3, result.output

    def test_normal_close_exits_zero(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK, _real(), _real("+71000")])
        assert result.exit_code == 0, result.output


# ── 프레임 순서 (prod는 SYSTEM을 끼워 보낸다) ────────


class TestWatchFrameOrder:
    def test_system_before_login_ack_is_skipped(self, runner, watch_env):
        """SYSTEM을 ack로 오독하면 return_code 부재 → 사유 공란 '인증 실패' → exit 0이었다."""
        result = _run(runner, watch_env, [SYSTEM_FRAME, LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "8005" in result.output, "SYSTEM 프레임을 LOGIN ack로 오독했다"

    def test_system_between_login_and_reg_ack_is_skipped(self, runner, watch_env):
        """prod 실측 순서: LOGIN ack → SYSTEM → REG ack. 등록 성공이어야 한다."""
        result = _run(runner, watch_env, [LOGIN_OK, SYSTEM_FRAME, REG_OK, _real()])
        assert result.exit_code == 0, result.output
        assert "등록 실패" not in result.output

    def test_ping_during_handshake_is_echoed(self, runner, watch_env):
        ws = watch_env["install"]([{"trnm": "PING"}, LOGIN_OK, {"trnm": "PING"}, REG_OK])
        result = runner.invoke(cli, ["watch", "005930"])
        assert result.exit_code == 0, result.output
        assert ws.sent_trnms() == ["LOGIN", "PING", "REG", "PING"]

    def test_system_frame_in_stream_loop_is_surfaced(self, runner, watch_env):
        """수신 루프의 SYSTEM 프레임을 조용히 버리지 않는다."""
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK, SYSTEM_FRAME, _real()])
        assert result.exit_code == 0, result.output
        assert "접속허용요청" in result.output


# ── 예외 처리 ────────────────────────────────────────


class TestWatchErrorHandling:
    def test_missing_websockets_is_clean_message(self, runner, watch_env, monkeypatch):
        """ImportError가 raw traceback으로 새지 않는다."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "websockets":
                raise ImportError("no module named websockets")
            return real_import(name, *args, **kwargs)

        watch_env["install"]([])
        monkeypatch.setattr(builtins, "__import__", fake_import)
        result = runner.invoke(cli, ["watch", "005930"])
        assert result.exit_code == 1, result.output
        assert "pip install websockets" in result.output
        assert not isinstance(result.exception, ImportError)
        assert "Traceback" not in result.output

    def test_unexpected_exception_exits_api(self, runner, watch_env):
        """ConnectionClosed/Refused 외의 예외도 traceback 대신 종료 코드로 나온다."""
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK, ValueError("깨진 프레임")])
        assert result.exit_code == 2, result.output
        assert "깨진 프레임" in result.output
        assert not isinstance(result.exception, ValueError)

    def test_invalid_json_frame_does_not_crash(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK, "not-json", _real()])
        assert result.exit_code == 0, result.output
