"""Reusable fake objects for tests.

Provides FakeKiwoomClient to replace ad-hoc MagicMock patterns in command tests.
"""

from __future__ import annotations

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

    def request_all(
        self,
        api_id: str,
        body: dict[str, Any] | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fake pagination: return single page as a list."""
        data, _ = self.request(api_id, body)
        return [data]

    def __enter__(self) -> FakeKiwoomClient:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def close(self) -> None:
        pass
