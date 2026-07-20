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

    def _install(frames, *, connect_exc=None, **ws_kwargs):
        ws = FakeWebSocket(frames, **ws_kwargs)
        state["ws"] = ws
        monkeypatch.setitem(
            sys.modules, "websockets", FakeWebsocketsModule(ws, connect_exc=connect_exc)
        )
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

    def test_frame_queue_exhaustion_exits_zero(self, runner, watch_env):
        """큐 소진 = `async for`가 조용히 끝나는 경로. 바깥 핸들러에 **들어가지 않는다**.

        (이전 이름은 test_normal_close_exits_zero였는데, ConnectionClosed 핸들러를
        고정하는 것처럼 보이지만 실제로는 StopAsyncIteration으로 끝나 그 핸들러를
        한 번도 실행하지 않았다. 핸들러 고정은 TestWatchCloseKind로 옮겼다.)
        """
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK, _real(), _real("+71000")])
        assert result.exit_code == 0, result.output
        assert "서버 연결 종료" not in result.output, "이 경로는 바깥 핸들러를 타지 않는다"


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


# ============================================================
#  Chunk D1 리뷰 수정 (F2/F3/F4/F6/F7/F8/F10)
# ============================================================


class TestWatchCloseKind:
    """F3/F6: 정상 종료와 비정상 종료를 한 핸들러로 뭉뚱그리지 않는다.

    이전에는 `except ConnectionClosed → return 0`이 "정상 종료는 실패가 아니다"라는
    주석을 달고 있었지만, 실제 websockets는 정상 종료면 `async for`를 조용히 끝내고
    비정상일 때만 raise한다. 즉 저 핸들러에 실제로 도달하는 건 비정상 종료 쪽이었다.
    """

    def test_normal_close_in_handler_exits_zero(self, runner, watch_env):
        from tests.fakes import FakeConnectionClosedOK

        result = _run(
            runner, watch_env,
            [LOGIN_OK, REG_OK, _real(), FakeConnectionClosedOK("1000 bye")],
        )
        assert result.exit_code == 0, result.output
        assert "서버 연결 종료" in result.output, "바깥 정상 종료 갈래를 타지 않았다"

    def test_abnormal_close_exits_api(self, runner, watch_env):
        from tests.fakes import FakeConnectionClosedError

        result = _run(
            runner, watch_env,
            [LOGIN_OK, REG_OK, _real(), FakeConnectionClosedError("1006 abnormal")],
        )
        assert result.exit_code == 2, result.output
        assert "비정상 종료" in result.output
        assert "재접속하려면" not in result.output

    def test_connection_refused_exits_api(self, runner, watch_env):
        watch_env["install"]([], connect_exc=ConnectionRefusedError("refused"))
        result = runner.invoke(cli, ["watch", "005930"])
        assert result.exit_code == 2, result.output
        assert "WebSocket 연결 실패" in result.output


class TestWatchHandshakeClose:
    """F2: LOGIN에 답하지 않고 끊긴 세션은 인증되지 않았다 → exit 0 금지."""

    def test_close_before_login_ack_exits_auth(self, runner, watch_env):
        result = _run(runner, watch_env, [])
        assert result.exit_code == 3, result.output
        assert "인증 응답을 받기 전에 연결이 끊겼습니다" in result.output
        assert "서버 연결 종료. 재접속하려면" not in result.output

    def test_close_before_reg_ack_exits_api(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK])
        assert result.exit_code == 2, result.output
        assert "등록 응답을 받기 전에 연결이 끊겼습니다" in result.output


class TestWatchHandshakeBuffering:
    """F4: recv_ack가 ack를 기다리는 동안 도착한 REAL 프레임을 버리지 않는다.

    tick 카운터가 제목에 나타나는지로 본다 — 프레임이 버려지면 tick_count가 0이라
    '실시간 시세 (tick #1)' 제목 자체가 생기지 않는다.
    """

    def test_control_real_after_both_acks(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, REG_OK, _real("+99999")])
        assert result.exit_code == 0, result.output
        assert "tick #1" in result.output

    def test_real_between_login_and_reg_ack_is_kept(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, _real("+99999"), REG_OK])
        assert result.exit_code == 0, result.output
        assert "tick #1" in result.output, "REG ack 대기 중 도착한 REAL이 버려졌다"

    def test_real_before_login_ack_is_kept(self, runner, watch_env):
        result = _run(runner, watch_env, [_real("+99999"), LOGIN_OK, REG_OK])
        assert result.exit_code == 0, result.output
        assert "tick #1" in result.output, "LOGIN ack 대기 중 도착한 REAL이 버려졌다"

    def test_many_reals_before_ack_do_not_exhaust_budget(self, runner, watch_env):
        """잡담 예산(10)에 데이터 프레임을 청구하면 11개째부터 등록 실패가 났다."""
        result = _run(runner, watch_env, [LOGIN_OK] + [_real("+99999")] * 20 + [REG_OK])
        assert result.exit_code == 0, result.output
        assert "tick #20" in result.output

    def test_ping_budget_is_separate(self, runner, watch_env):
        """F8: 핸드셰이크 중 킵얼라이브 PING 10번이 인증 실패로 이어지면 안 된다."""
        ws = watch_env["install"]([{"trnm": "PING"}] * 10 + [LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["watch", "005930"])
        assert result.exit_code == 0, result.output
        assert ws.sent_trnms().count("PING") == 10


class TestWatchAckSlotDiscipline:
    """F7: LOGIN ack가 REG 자리에서 소비되면 등록 없이 조용히 성공한다."""

    def test_duplicate_login_ack_is_not_taken_as_reg_ack(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, LOGIN_OK])
        assert result.exit_code == 2, result.output
        assert "tick #" not in result.output


class TestWatchHandshakeSystemDisplay:
    """F10: 핸드셰이크에서 건너뛴 SYSTEM 프레임을 조용히 삼키지 않는다."""

    def test_system_before_login_ack_is_displayed(self, runner, watch_env):
        result = _run(runner, watch_env, [SYSTEM_FRAME, LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "시스템: 접속허용요청" in result.output, "건너뛴 SYSTEM이 표시되지 않았다"

    def test_system_between_acks_is_displayed(self, runner, watch_env):
        result = _run(runner, watch_env, [LOGIN_OK, SYSTEM_FRAME, REG_OK, _real()])
        assert result.exit_code == 0, result.output
        assert "시스템: 접속허용요청" in result.output


# ============================================================
#  D9/H5: watch의 핸드셰이크 **페이로드**와 미검증 경로
#
#  기존 단언은 전부 sent_trnms() 기반이라 trnm 외의 키를 전부 버렸다. 그
#  상태에서는 LOGIN의 token을 빼거나 REG에 엉뚱한 종목/타입/grp_no/refresh를
#  실어도 스위트가 통과했다. 아래는 sent_frames()로 프레임 자체를 본다.
# ============================================================


class TestWatchHandshakePayload:
    def test_login_frame_carries_the_token(self, runner, watch_env):
        ws = watch_env["install"]([LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["watch", "005930"])
        assert result.exit_code == 0, result.output
        assert ws.sent_frames()[0] == {"trnm": "LOGIN", "token": "tok"}

    def test_reg_frame_carries_watched_codes_and_type(self, runner, watch_env):
        ws = watch_env["install"]([LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["watch", "005930", "000660"])
        assert result.exit_code == 0, result.output
        assert ws.sent_frames()[1] == {
            "trnm": "REG",
            "grp_no": "1",
            "refresh": "1",
            "data": [{"item": ["005930", "000660"], "type": ["0B"]}],
        }


class TestWatchLoginSlotRejection:
    """LOGIN 자리의 reject_trnm=("REG","REMOVE")가 실제로 걸리는지.

    task-D1-fix-report.md §5는 "양방향 모두 고정됐다"고 적었지만 REG 자리만
    고정돼 있었다 (TestWatchAckSlotDiscipline). 여기가 나머지 방향이다.
    """

    def test_reg_ack_is_not_consumed_as_login_ack(self, runner, watch_env):
        """REG ack가 LOGIN 자리에서 소비되면 인증 없이 인증 성공이 된다.

        큐에 REG ack **하나만** 둔다. 거부가 살아 있으면 LOGIN 자리는 그것을
        ack로 받지 않고 버퍼로 넘기며, 큐가 말라 인증 단계에서 exit 3(EXIT_AUTH)
        으로 끝난다. 거부를 빼면 REG_OK를 LOGIN ack로 삼켜 "인증 성공"이 된 뒤
        REG 자리에서 막혀 exit 2가 난다 — 두 종료 코드가 실제로 갈린다.
        (프레임을 [REG_OK, LOGIN_OK]로 두면 어느 쪽이든 exit 2라 판별되지 않는다.)
        """
        result = _run(runner, watch_env, [REG_OK])
        assert result.exit_code == 3, result.output
        assert "인증 응답을 받기 전에 연결이 끊겼습니다" in result.output

    def test_remove_ack_is_not_consumed_as_login_ack(self, runner, watch_env):
        result = _run(runner, watch_env, [{"trnm": "REMOVE", "return_code": 0}])
        assert result.exit_code == 3, result.output


class TestWatchUncoveredGuards:
    def test_missing_reg_ack_exits_api(self, runner, watch_env):
        """등록 응답 없음(reg_resp is None) 가드 — 어떤 테스트도 들어가지 않던 경로.

        큐를 그냥 말리면 recv가 ConnectionClosed를 던져 **다른** 핸들러로
        간다. None을 받게 하려면 ack 없이 잡담(SYSTEM)만으로 건너뛰기 예산
        (MAX_HANDSHAKE_SKIP=10)을 소진시켜야 한다.
        """
        result = _run(runner, watch_env, [LOGIN_OK] + [SYSTEM_FRAME] * 10)
        assert result.exit_code == 2, result.output
        assert "등록 응답을 받지 못했습니다" in result.output

    def test_ping_in_receive_loop_is_echoed(self, runner, watch_env):
        """수신 루프(핸드셰이크가 아니라)의 PING 에코 — 미검증 경로였다.

        핸드셰이크 PING 에코는 이미 고정돼 있지만(recv_ack 안), 두 ack가 모두
        끝난 뒤 Live 루프 안에서 오는 PING은 watch.py가 직접 처리한다.
        """
        ws = watch_env["install"]([LOGIN_OK, REG_OK, {"trnm": "PING"}, _real()])
        result = runner.invoke(cli, ["watch", "005930"])
        assert result.exit_code == 0, result.output
        assert ws.sent_trnms() == ["LOGIN", "REG", "PING"]

    def test_keyboard_interrupt_exits_zero(self, runner, watch_env, monkeypatch):
        """Ctrl+C는 실패가 아니다 (exit 0). 미검증 경로였다."""
        watch_env["install"]([LOGIN_OK, REG_OK])

        def interrupted(coro, *a, **k):
            coro.close()
            raise KeyboardInterrupt

        monkeypatch.setattr("asyncio.run", interrupted)
        result = runner.invoke(cli, ["watch", "005930"])
        assert result.exit_code == 0, result.output
        assert "모니터링 종료" in result.output
