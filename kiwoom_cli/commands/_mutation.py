"""Shared helpers for mutation (order) commands.

confirm_gate: --confirm/--yes 없이 실행 시 table 모드는 대화형 프롬프트,
json/csv 모드는 CONFIRMATION_REQUIRED 오류(exit 1)로 응답 — 절대 프롬프트하지 않아
비대화형/에이전트 환경에서 멈추지 않는다.

dry-run: 실제 전송될 request body를 그대로 구성해 전송 없이 출력한다.
"""

from __future__ import annotations

from typing import Any, Callable

import click

from .. import envelope, idempotency
from ..formatters import _get_format, human, print_order_result
from ..output import err_console


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


def _idempotency_conflict(key: str) -> None:
    msg = (f"멱등성 키 '{key}'는 다른 주문 내용으로 이미 사용되었습니다. "
           "재시도라면 명령 인자가 이전 실행과 완전히 같은지 확인하고, "
           "새 주문이라면 다른 키를 사용하세요.")
    if _get_format() == "table":
        err_console.print(f"[red]{msg}[/]")
    else:
        envelope.emit(error=envelope.error_body(
            msg, code="IDEMPOTENCY_CONFLICT", retryable=False,
        ))
    raise SystemExit(1)


def send_order(api_id: str, body: dict[str, Any], action: str,
               client_order_id: str | None, *, client_cls) -> None:
    """주문 전송 + 멱등성 처리 (원장 잠금 아래에서 조회→전송→기록).

    - 같은 키 + 같은 내용(fingerprint 일치): 재전송 없이 이전 응답 반환.
    - 같은 키 + 다른 내용: IDEMPOTENCY_CONFLICT (exit 1), 전송하지 않음.
    - fingerprint가 없는 과거(v2.4~v2.5.0) 기록은 종전대로 재생한다.

    client_cls: 호출 모듈의 KiwoomClient 바인딩 (테스트 patch 지점 유지).
    """
    if not client_order_id:
        with client_cls() as c:
            data, _ = c.request(api_id, body)
        print_order_result(data, action)
        return
    fp = idempotency.fingerprint(api_id, body)
    with idempotency.locked():
        hit = idempotency.lookup(client_order_id)
        if hit is not None:
            stored = hit.get("fingerprint")
            if stored is not None and stored != fp:
                _idempotency_conflict(client_order_id)
            human(f"[dim]멱등성 키 '{client_order_id}' 기존 기록 — 재전송하지 않고 이전 응답을 반환합니다.[/]")
            print_order_result({**hit["response"], "idempotent_replay": True}, action)
            return
        with client_cls() as c:
            data, _ = c.request(api_id, body)
        idempotency.record(client_order_id, api_id, data, fingerprint=fp)
    print_order_result(data, action)
