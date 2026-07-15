"""US account operations, dispatched from commands/account.py."""

from __future__ import annotations

from ...client import KiwoomClient  # noqa: F401  (patched by tests; more ops use it in Task 10)


def fetch_balance(client, stex_tp: str | None = None) -> dict:
    """미국주식 원장잔고 (ust21070). 예외는 호출측에서 처리."""
    body: dict = {}
    if stex_tp:
        body["stex_tp"] = stex_tp
    data, _ = client.request("ust21070", body)
    return data
