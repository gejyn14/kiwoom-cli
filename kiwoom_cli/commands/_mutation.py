"""Shared helpers for mutation (order) commands.

confirm_gate: --confirm/--yes 없이 실행 시 table 모드는 대화형 프롬프트,
json/csv 모드는 CONFIRMATION_REQUIRED 오류(exit 1)로 응답 — 절대 프롬프트하지 않아
비대화형/에이전트 환경에서 멈추지 않는다.

dry-run: 실제 전송될 request body를 그대로 구성해 전송 없이 출력한다.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import click

from .. import envelope, idempotency
from ..client import KiwoomAPIError
from ..formatters import _get_format, fail_api, human, print_order_result
from ..output import err_console


class QuoteUnavailable(Exception):
    """시세 응답에서 예상비용 계산용 가격을 파싱할 수 없음.

    국내(_quote_price_kr)/미국(_quote_price_us) dry-run 경로가 공유하는 시세
    파서(parse_quote_price)가 실패 시 이 예외를 던진다. 호출자는 이를 조용히
    0으로 넘기지 말고 fail_api(..., code="QUOTE_UNAVAILABLE")로 exit 2 처리해야
    한다 — dry-run이 price_source="market_quote"를 주장하면서 price/est_cost가
    0인 미리보기를 보여주는 것이 이 예외가 막으려는 실패 모드다.
    """


def parse_quote_price(value: Any) -> float:
    """시세 응답의 가격 문자열 → float. 선행 부호(+/-)는 방향지시자이지 실제
    부호가 아니므로 제거한다 (cur_prc 등 키움 관례).

    빈 값/숫자로 변환 불가/NaN/Inf는 모두 QuoteUnavailable을 던진다 — 조용한
    0 폴백은 dry-run 예상비용 미리보기를 거짓으로 만든다.
    """
    v = str(value if value is not None else "").strip().lstrip("+-")
    if not v:
        raise QuoteUnavailable(f"시세 값이 비어 있습니다: {value!r}")
    try:
        f = float(v)
    except ValueError:
        raise QuoteUnavailable(f"시세 값을 숫자로 변환할 수 없습니다: {value!r}") from None
    if not math.isfinite(f):
        raise QuoteUnavailable(f"시세 값이 유효한 숫자가 아닙니다: {value!r}")
    return f


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
    """주문 전송 + 멱등성 처리 (원장 잠금 아래에서 조회→in-flight 기록→전송→완료 기록).

    - 같은 키 + 같은 내용(fingerprint 일치): 재전송 없이 이전 응답 반환.
    - 같은 키 + 다른 내용: IDEMPOTENCY_CONFLICT (exit 1), 전송하지 않음.
    - 같은 키가 "inflight" 상태(전송 후 응답 미도착 — 타임아웃/연결 끊김/프로세스
      종료)로 남아 있으면 ORDER_STATUS_UNKNOWN (exit 2), 재전송하지 않음.
    - 같은 키가 "rejected" 상태(업스트림이 구조적으로 거부 — 주문 미실행)이면
      재전송을 막지 않는다: 새 in-flight 기록을 남기고 다시 전송을 시도한다.
    - fingerprint가 없는 과거(v2.4~v2.5.0) 기록은 종전대로 재생한다.

    client_cls: 호출 모듈의 KiwoomClient 바인딩 (테스트 patch 지점 유지).
    """
    # 주문 전송은 페이지네이션 대상이 아님 — 전역 --all-pages/--next-key를 무시한다.
    # 아래 record_rejected()의 정확성은 이 단일-요청 보장에 의존한다: 여러 페이지를
    # 도는 도중 한 페이지는 성공(주문 실행)하고 다른 페이지에서 KiwoomAPIError가
    # 나면, 실제로는 체결된 주문을 "rejected"(재사용 가능)로 잘못 기록하게 된다.
    # 이 두 줄은 절대 제거하지 말 것 — 주문 API가 cont-yn: Y를 반환하지 않는 것과
    # 별개로, 멱등성 안전성이 이 코드에 직접 의존한다.
    ctx = click.get_current_context(silent=True)
    if ctx is not None and isinstance(ctx.obj, dict):
        ctx.obj["all_pages"] = False
        ctx.obj.pop("next_key", None)

    if not client_order_id:
        with client_cls() as c:
            data, _ = c.request(api_id, body)
        print_order_result(data, action)
        return
    fp = idempotency.fingerprint(api_id, body)
    try:
        with idempotency.locked():
            hit = idempotency.lookup(client_order_id)
            if hit is not None:
                stored = hit.get("fingerprint")
                if stored is not None and stored != fp:
                    _idempotency_conflict(client_order_id)
                status = hit.get("status")
                if status == "rejected":
                    # 이전 시도는 업스트림이 구조적으로 거부해 주문이 실행되지
                    # 않았다 — 결과 불명이 아니므로 재전송을 막지 않는다.
                    pass
                elif status == "inflight" or hit.get("response") is None:
                    fail_api(
                        f"멱등성 키 '{client_order_id}'의 이전 시도는 전송 후 응답을 "
                        "받지 못했습니다. 주문이 체결되었을 수 있으므로 재전송하지 "
                        "않습니다. 'kiwoom account orders pending'으로 상태를 확인한 "
                        "뒤, 새 주문이라면 새 키를 사용하세요.",
                        code="ORDER_STATUS_UNKNOWN",
                    )
                else:
                    human(f"[dim]멱등성 키 '{client_order_id}' 기존 기록 — 재전송하지 않고 이전 응답을 반환합니다.[/]")
                    print_order_result({**hit["response"], "idempotent_replay": True}, action)
                    return
            try:
                idempotency.record_inflight(client_order_id, api_id, fp)
            except OSError as e:
                fail_api(f"멱등성 원장에 기록할 수 없어 주문을 전송하지 않았습니다: {e}")
            try:
                with client_cls() as c:
                    data, _ = c.request(api_id, body)
            except KiwoomAPIError:
                # 업스트림이 구조적으로 거부 — 주문 미실행. in-flight를 "rejected"로
                # 종결해 같은 키의 다음 재시도가 영구히 막히지 않도록 한다.
                try:
                    idempotency.record_rejected(client_order_id, api_id, fingerprint=fp)
                except OSError as e:
                    err_console.print(
                        f"[yellow]주문이 거부되었으나 원장 기록에 실패했습니다: {e}[/]")
                raise
            try:
                idempotency.record(client_order_id, api_id, data, fingerprint=fp)
            except OSError as e:
                err_console.print(
                    f"[yellow]주문은 전송되었으나 원장 기록에 실패했습니다: {e}[/]")
    except idempotency.LedgerLockBusy:
        msg = ("멱등성 원장 잠금을 획득하지 못했습니다 — 같은 프로필의 다른 주문이 "
               "전송 중입니다. 잠시 후 재시도하세요.")
        if _get_format() == "table":
            err_console.print(f"[red]{msg}[/]")
        else:
            envelope.emit(error=envelope.error_body(msg, code="LEDGER_BUSY", retryable=True))
        raise SystemExit(2)
    print_order_result(data, action)
