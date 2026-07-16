"""Shared helpers for mutation (order) commands.

confirm_gate: --confirm/--yes 없이 실행 시 table 모드는 대화형 프롬프트,
json/csv 모드는 CONFIRMATION_REQUIRED 오류(exit 1)로 응답 — 절대 프롬프트하지 않아
비대화형/에이전트 환경에서 멈추지 않는다.

dry-run: 실제 전송될 request body를 그대로 구성해 전송 없이 출력한다.
"""

from __future__ import annotations

from typing import Any, Callable

import click

from .. import envelope
from ..formatters import _get_format, human


def confirm_gate(confirm: bool) -> None:
    """주문 실행 전 확인 게이트."""
    if confirm:
        return
    if _get_format() == "table":
        click.confirm("주문을 실행하시겠습니까?", abort=True, err=True)
        return
    envelope.emit(error=envelope.error_body(
        "pass --confirm", code="CONFIRMATION_REQUIRED", retryable=False,
    ))
    raise SystemExit(1)


def dry_run_payload(
    *,
    api_id: str,
    side: str,
    symbol: str,
    qty: int,
    price: float,
    order_type: str | None,
    exchange: str | None,
    currency: str,
    body: dict[str, Any],
    price_source: str | None = None,
) -> dict[str, Any]:
    """--dry-run 출력 문서. body는 실제 전송과 정확히 동일해야 한다."""
    est_cost = qty * price
    payload: dict[str, Any] = {
        "would_send": True,
        "api_id": api_id,
        "side": side,
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "order_type": order_type,
        "exchange": exchange,
        "est_cost": int(est_cost) if currency == "KRW" else round(est_cost, 4),
        "currency": currency,
        "env": envelope.build_meta()["env"],
        "body": body,
    }
    if price_source:
        payload["price_source"] = price_source
    return payload


def finish_dry_run(payload: dict[str, Any], show_preview: Callable[[], None]) -> None:
    """table 모드는 기존 미리보기 + 안내 라인, json/csv 모드는 envelope 문서."""
    if _get_format() == "table":
        show_preview()
        human(r"[yellow]\[dry-run] 전송하지 않음[/]")
    else:
        envelope.emit(data=payload)
