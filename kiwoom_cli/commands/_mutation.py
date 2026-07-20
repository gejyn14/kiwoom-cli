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
from ..client import KiwoomAPIError, KiwoomAuthError
from ..formatters import _get_format, fail_api, fail_input, human, print_order_result
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

    빈 값/숫자로 변환 불가/NaN/Inf/0 이하는 모두 QuoteUnavailable을 던진다 —
    조용한 0 폴백은 dry-run 예상비용 미리보기를 거짓으로 만든다. 실거래 종목에
    가격 0은 없다 — 거래정지/상장전 등 "시세 없음"을 뜻한다. 원래 버그가
    정확히 "0"을 만들어냈으므로 이 값을 걸러내지 못하면 이 함수는 자신이
    막으려는 실패를 재현한다.

    음수를 별도로 취급하지 않는 이유: 위에서 선행 부호를 이미 제거했으므로
    (키움 API에서 cur_prc의 부호는 방향지시자일 뿐 실제 부호가 아니다), 이
    지점에 도달한 f는 유효한 숫자 문자열인 한 항상 0 이상이다 — "파싱된 음수
    시세"는 이 함수의 계약상 나타날 수 없어 별도 메시지가 불필요하다.
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
    if f <= 0:
        raise QuoteUnavailable(f"시세 값이 0 이하입니다 (시세 없음 — 거래정지/상장전 등): {value!r}")
    return f


def is_valid_order_qty(qty: int, *, allow_zero: bool = False) -> bool:
    """주문 수량 유효성 **술어** — 순수 함수이며 종료하지 않는다.

    이 함수가 "유효한 수량"의 **유일한 정의**다. 두 소비자가 공유한다:
      - `validate_order_qty` (실주문 경로 — 위반 시 fail_input으로 exit 1)
      - `order validate`의 `checks.qty_ok` (사전점검 — 위반 시 체크가 false)

    임계값을 양쪽에 각각 적어 두면 반드시 어긋난다. 실제로 어긋났었다: D5가
    주문 경로에만 하한을 넣어, 사전점검이 `valid: true`라고 답한 수량을 실주문이
    거부하는 상태가 됐다(D5b). 프리플라이트의 존재 이유가 실주문 결과 예측이므로
    이 드리프트는 그 자체로 결함이다. 새 임계값을 넣을 일이 있으면 반드시
    여기에만 넣을 것.
    """
    return qty > 0 or (qty == 0 and allow_zero)


def is_valid_order_price(price: float, *, allow_zero: bool = True) -> bool:
    """주문 가격 유효성 **술어** — 순수 함수이며 종료하지 않는다.

    `is_valid_order_qty`와 같은 이유로 존재한다: `validate_order_price`(실주문)와
    `order validate`의 `checks.price_ok`(사전점검)가 이 정의 하나를 공유한다.

    국내 경로의 "정수(원)" 규칙은 여기 없다 — 그건 국내 전용이라 order.py의
    `_is_kr_integer_price`가 갖고 있고, 그쪽도 같은 이유로 단일 정의다.
    """
    if not math.isfinite(price):
        return False
    return price > 0 or (price == 0 and allow_zero)


def validate_order_qty(qty: int, *, allow_zero: bool = False,
                       label: str = "주문수량") -> int:
    """주문 수량 하한 검증. 위반 시 fail_input(exit 1)이며 요청은 전송되지 않는다.

    판정은 `is_valid_order_qty`에 위임한다 — 임계값 정의는 그쪽 한 곳뿐이다.

    근거는 키움이 직접 배포하는 kwcli 0.1.1의 `maps/arguments.csv`다 —
    주문·정정 수량(ord_qty/mdfy_qty)은 `type=quantity`, 취소 수량(cncl_qty)은
    `type=cancel_quantity`로 선언되고, `argument_maps.py`의 TYPE_PARSERS가 각각
    `positive_int_string`(`<= 0` 거부)과 `nonnegative_int_string`(0 허용)에
    매핑한다. allow_zero=True가 후자에 해당한다.

    **allow_zero=True는 취소 경로에만 쓸 것.** 매수/매도/정정에 0을 허용하면
    ord_qty="0"이 그대로 전송된다 — 이 가드 이전의 실제 동작이 그랬다.

    취소에서 0을 허용하는 것은 우리 문서화된 계약(`--qty 0` = 전량취소, 그리고
    `--qty`의 기본값이 0)이자 kwcli의 credit-cancel/gold-cancel 선언과도 같다.
    kwcli는 `domestic orders cancel --qty`만 `quantity`(양수)로 선언해 자기
    형제 명령들과 어긋나는데, 그쪽을 따르면 우리 기본값 0이 항상 거부되므로
    따르지 않는다 — kwcli 내부 불일치로 보고 우리 계약을 유지한다.
    """
    if not is_valid_order_qty(qty, allow_zero=allow_zero):
        limit = "0 이상" if allow_zero else "1 이상"
        fail_input(f"{label}은(는) {limit}이어야 합니다 (입력값: {qty}).")
    return qty


def validate_order_price(price: float, *, allow_zero: bool = True,
                         label: str = "주문가격") -> float:
    """주문 가격 검증: 비유한(NaN/Inf)과 음수를 거부한다. 위반 시 exit 1.

    근거는 kwcli 0.1.1이 모든 가격 필드(ord_uv/mdfy_uv/cond_uv)에 붙이는
    `type=price` → `price_string`이다: `^\\d+$` 매칭 후 `int(value) < 0`을
    거부하므로 음수·NaN·Inf가 전부 걸러진다. 0은 통과시킨다.

    allow_zero=True(기본)인 이유: 이 코드베이스 전반에서 price=0은 "가격 미지정"
    = 시장가 센티널이며(`ord_uv`를 빈 문자열로 보낸다), 값이 아니다. 여기서 0을
    막으면 시장가 주문 전체가 막힌다. 정정처럼 시장가 개념이 없는 경로만
    allow_zero=False를 쓴다.

    NaN/Inf를 별도로 막는 이유: 이 가드 이전에는 국내 경로에서
    `int(float('nan'))`이 ValueError를, `int(float('inf'))`가 OverflowError를
    던져 envelope 없이 죽었고(json 모드 stdout 공백 — envelope-항상 계약 위반),
    미국 경로에서는 `fmt_us_price`가 NaN을 truthy로 보아 `ord_uv="nan"`을
    실제로 전송했다.

    _mutation.py의 `parse_quote_price`와 혼동하지 말 것 — 그쪽은 **시세 응답**을
    검증하고 이쪽은 **사용자 입력**을 검증한다. 계약도 다르다(그쪽은 0 이하를
    "시세 없음"으로 거부한다).

    판정은 `is_valid_order_price`에 위임한다 — 임계값 정의는 그쪽 한 곳뿐이다.
    비유한 값은 메시지를 구분하기 위해서만 따로 검사한다(판정 자체는 술어가 이미
    False를 준다).
    """
    if not math.isfinite(price):
        fail_input(f"{label}이(가) 유효한 숫자가 아닙니다 (입력값: {price}).")
    if not is_valid_order_price(price, allow_zero=allow_zero):
        limit = "0 이상이어야" if allow_zero else "0보다 커야"
        fail_input(f"{label}은(는) {limit} 합니다 (입력값: {price:g}).")
    return price


def suppress_pagination() -> None:
    """변이 요청은 페이지네이션 대상이 아님 — 전역 --all-pages/--next-key를 무시하고,
    응답 envelope에도 meta.cont를 남기지 않는다.

    반복 실행은 조회에서는 안전하지만(같은 페이지를 다시 읽을 뿐), 변이(주문
    전송·환전 신청 등)에서는 실제 동작을 여러 번 반복 실행하는 것과 같다.
    confirm_gate를 통과한 직후, 실제 요청을 보내기 전에 호출해야 한다 —
    ctx.obj["all_pages"]를 False로 되돌리고 ctx.obj["next_key"]를 제거해
    KiwoomClient.request()의 전역 페이지네이션 루프(--all-pages 반복,
    --next-key 커서 주입)가 이 요청에 적용되지 않도록 한다.

    ctx.obj["suppress_cont"] = True도 여기서 함께 세팅한다. 자동 반복(50회 상한)은
    이 함수의 위 두 줄로 막히지만, last_cont는 KiwoomClient._request_once()가
    응답을 받은 "이후"에 기록하므로 이 함수만으로는 막을 수 없다 — 대신
    _request_once()가 이 플래그를 보고 last_cont 기록 자체를 건너뛴다(client.py
    참고). 반복 억제와 meta.cont 억제를 같은 호출(suppress_pagination) 한 곳에
    묶어 두는 이유: 각 변이 호출부가 "meta.cont도 지워야 한다"는 것을 별도로
    기억해야 하는 설계였다면, 새 변이 커맨드가 추가될 때 그 기억이 누락되는 일이
    반드시 생긴다 — 이 시리즈에서 고치고 있는 결함들이 바로 그렇게 생겨났다."""
    ctx = click.get_current_context(silent=True)
    if ctx is not None and isinstance(ctx.obj, dict):
        ctx.obj["all_pages"] = False
        ctx.obj.pop("next_key", None)
        ctx.obj["suppress_cont"] = True


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
    - 같은 키가 "rejected" 상태(업스트림이 구조적으로 거부됐거나, 아예 업스트림에
      도달하지 못했음이 코드 구조상 보장됨 — 주문 미실행)이면 재전송을 막지
      않는다: 새 in-flight 기록을 남기고 다시 전송을 시도한다.
    - fingerprint가 없는 과거(v2.4~v2.5.0) 기록은 종전대로 재생한다.

    client_cls: 호출 모듈의 KiwoomClient 바인딩 (테스트 patch 지점 유지).
    """
    # 아래 record_rejected()의 정확성은 이 단일-요청 보장에 의존한다: 여러 페이지를
    # 도는 도중 한 페이지는 성공(주문 실행)하고 다른 페이지에서 KiwoomAPIError가
    # 나면, 실제로는 체결된 주문을 "rejected"(재사용 가능)로 잘못 기록하게 된다.
    # 이 호출은 절대 제거하지 말 것 — 주문 API가 cont-yn: Y를 반환하지 않는 것과
    # 별개로, 멱등성 안전성이 이 코드에 직접 의존한다.
    suppress_pagination()

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
            except (KiwoomAPIError, KiwoomAuthError):
                # 업스트림이 구조적으로 거부(KiwoomAPIError)했거나, 애초에 업스트림에
                # 도달하지 못했다(KiwoomAuthError — client_cls() 생성/c.request()의
                # 인증 단계는 실제 HTTP 전송(self._http.post) 이전에 실행되므로,
                # 여기서 발생하면 전송이 일어나지 않았음이 코드 구조상 보장된다).
                # 어느 경우든 주문은 미실행이므로 in-flight를 "rejected"로 종결해
                # 같은 키의 다음 재시도가 영구히 막히지 않도록 한다.
                #
                # 이 튜플에 예외 타입을 추가하려면 "실제 전송(self._http.post) 이전
                # 지점에서만 발생함이 코드 구조상 보장되는지"를 반드시 확인할 것 —
                # 애매한 경우(예: httpx.ReadTimeout — 요청 바이트가 이미 나갔을 수
                # 있음)는 절대 포함하면 안 된다. 그 경우는 in-flight로 남아
                # ORDER_STATUS_UNKNOWN을 내는 것이 안전한 방향이다
                # (test_inflight_record_blocks_duplicate_after_transport_failure 참고).
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
