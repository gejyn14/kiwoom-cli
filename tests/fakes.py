"""Reusable fake objects for tests.

Provides FakeKiwoomClient to replace ad-hoc MagicMock patterns in command tests.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any


class FakeKiwoomClient:
    """In-memory fake of KiwoomClient that records calls and returns canned responses.

    Usage:
        fake = FakeKiwoomClient()
        fake.set_response("ka10001", {"stk_nm": "삼성전자"})
        # ... inject via monkeypatch ...
        # after test:
        assert fake.calls == [("ka10001", {"stk_cd": "005930"})]
    """

    def __init__(self):
        self._responses: dict[str, tuple[dict[str, Any], dict[str, str]]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.token: str | None = "test-token"
        self.domain = "https://mock.test"

    def set_response(
        self,
        api_id: str,
        data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        """Register a canned response for an API ID."""
        self._responses[api_id] = (
            data,
            headers or {"cont-yn": "", "next-key": ""},
        )

    def request(
        self,
        api_id: str,
        body: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Record the call and return registered response (or default success)."""
        self.calls.append((api_id, body or {}))
        if api_id in self._responses:
            return self._responses[api_id]
        return (
            {"return_code": 0, "ord_no": "0000001", "return_msg": "OK"},
            {"cont-yn": "", "next-key": ""},
        )

    def __enter__(self) -> FakeKiwoomClient:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def close(self) -> None:
        pass


# ── 가짜 WebSocket ───────────────────────────────────
#
# 실제 소켓을 열지 않고 streaming.py / watch.py의 핸드셰이크와 수신 루프를
# 검증하기 위한 스크립트형 페이크. 프레임 큐를 순서대로 돌려주고, 큐가 비면
# ConnectionClosedOK를 던져 서버가 정상 종료한 상황을 흉내낸다.


class FakeConnectionClosed(Exception):
    """실제 websockets.exceptions.ConnectionClosed 대역."""


class FakeConnectionClosedOK(FakeConnectionClosed):
    """실제와 동일하게 ConnectionClosed의 하위 클래스여야 한다."""


class FakeConnectionClosedError(FakeConnectionClosed):
    """비정상 종료(1006 등). 실제와 동일하게 ConnectionClosedOK의 하위가 아니다.

    `except ConnectionClosedOK` / `except ConnectionClosed` 두 갈래가 실제로
    갈리는지 확인하려면 이 구분이 페이크에도 있어야 한다.
    """


class FakeWebSocket:
    """프레임 큐를 순서대로 돌려주는 가짜 소켓.

    frames 원소는 dict(자동 json 직렬화), str(그대로), Exception(raise) 중 하나.
    """

    def __init__(
        self,
        frames: list[Any] | None = None,
        *,
        send_exc: Exception | None = None,
        fail_send_after: int | None = None,
    ):
        self.frames: list[Any] = list(frames or [])
        self.sent: list[str] = []
        # send_exc/fail_send_after: n번째 send부터 예외를 던진다. 닫힌 소켓에
        # PING을 에코하는 상황(실제로 ConnectionClosed가 나오는 자리)을 재현한다.
        self.send_exc = send_exc
        self.fail_send_after = fail_send_after

    async def send(self, message: str) -> None:
        if self.send_exc is not None and (
            self.fail_send_after is None or len(self.sent) >= self.fail_send_after
        ):
            raise self.send_exc
        self.sent.append(message)

    async def recv(self) -> str:
        if not self.frames:
            raise FakeConnectionClosedOK("no more frames")
        frame = self.frames.pop(0)
        if isinstance(frame, Exception):
            raise frame
        if isinstance(frame, str):
            return frame
        return json.dumps(frame, ensure_ascii=False)

    def __aiter__(self) -> FakeWebSocket:
        return self

    async def __anext__(self) -> str:
        """큐 소진 = 정상 종료 → StopAsyncIteration (실제 websockets의 `async for`와 동일).

        큐에 예외를 **명시적으로 넣은** 경우는 그대로 던진다. 비정상 종료
        (ConnectionClosedError)가 `async for`에서 raise되는 건 실제 동작이고,
        ConnectionClosedOK를 명시적으로 넣는 건 바깥 핸들러의 정상/비정상 분기가
        실제로 갈리는지 확인하기 위한 방어적 경로다.
        """
        if not self.frames:
            raise StopAsyncIteration
        return await self.recv()

    # 전송된 프레임 조회 헬퍼
    def sent_trnms(self) -> list[str]:
        """전송 프레임의 trnm만. **프레임 순서만** 볼 때 쓸 것.

        trnm 외의 모든 키를 버리므로, 이것만으로 단언하면 LOGIN의 token을
        통째로 빼거나 REG의 item/type/grp_no/refresh를 아무 값으로 바꿔도
        테스트가 전부 통과한다. 페이로드를 봐야 하면 `sent_frames`를 쓸 것.
        """
        return [f.get("trnm", "") if isinstance(f, dict) else ""
                for f in self.sent_frames()]

    def sent_frames(self) -> list[dict[str, Any]]:
        """전송 프레임을 **파싱된 dict 그대로** 돌려준다 (페이로드 포함).

        파싱 불가능한 줄은 {}로 둔다 — 자리를 없애면 인덱스가 밀린다.
        """
        out: list[dict[str, Any]] = []
        for raw in self.sent:
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                frame = None
            out.append(frame if isinstance(frame, dict) else {})
        return out


class _FakeConnect:
    def __init__(self, ws: FakeWebSocket):
        self._ws = ws

    async def __aenter__(self) -> FakeWebSocket:
        return self._ws

    async def __aexit__(self, *args: Any) -> None:
        return None


class FakeWebsocketsModule:
    """`import websockets` 자리에 끼워 넣는 가짜 모듈."""

    def __init__(self, ws: FakeWebSocket, connect_exc: Exception | None = None):
        self.ws = ws
        self.connect_exc = connect_exc
        self.exceptions = SimpleNamespace(
            ConnectionClosed=FakeConnectionClosed,
            ConnectionClosedOK=FakeConnectionClosedOK,
            ConnectionClosedError=FakeConnectionClosedError,
        )

    def connect(self, *args: Any, **kwargs: Any) -> _FakeConnect:
        if self.connect_exc is not None:
            raise self.connect_exc
        return _FakeConnect(self.ws)
