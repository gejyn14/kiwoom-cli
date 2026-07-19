"""Stable JSON response envelope (v1) for `-f json` output.

성공/실패 모두 하나의 envelope로 감쌉니다:
{"ok": bool, "schema": "v1", "data": ..., "meta": {...}, "error": ...}

에러는 안정적인 enum 코드로 분류되어 자동화/에이전트가 upstream 메시지를
파싱하지 않고도 분기할 수 있습니다. csv/table 모드에는 적용되지 않습니다.
"""

from __future__ import annotations

import json
from typing import Any

import click

from . import config

SCHEMA = "v1"

# 키움 REST API 공식 오류코드 (docs/키움 REST API 문서.xlsx '오류코드' 시트)
# → (stable_code, retryable). 미등록 코드는 ("UPSTREAM_ERROR", False).
CODE_MAP: dict[int, tuple[str, bool]] = {
    # API 라우팅
    1501: ("INVALID_API", False),      # API ID Null/없음
    1504: ("INVALID_API", False),      # URI가 지원하지 않는 API ID
    1505: ("INVALID_API", False),      # 존재하지 않는 API ID
    # 입력 검증
    2: ("INVALID_INPUT", False),       # 입력 값 오류 (실측)
    1511: ("INVALID_INPUT", False),    # 필수 입력 누락
    1512: ("INVALID_INPUT", False),    # Http header 값 누락/불가독
    1517: ("INVALID_INPUT", False),    # 입력 값 형식 오류
    # 인증 헤더/토큰
    1513: ("AUTH_REQUIRED", False),    # authorization 필드 없음
    1514: ("AUTH_REQUIRED", False),    # authorization 형식 오류
    1515: ("AUTH_REQUIRED", False),    # Grant Type 형식 오류
    1516: ("AUTH_REQUIRED", False),    # Token 미정의
    8005: ("TOKEN_EXPIRED", False),    # Token 유효하지 않음
    # 호출 제한
    1687: ("RATE_LIMITED", False),     # 재귀 호출 제한 (재시도 무의미)
    1700: ("RATE_LIMITED", True),      # 허용 요청 개수 초과
    # 종목/시장 조회
    1901: ("NOT_FOUND", False),        # 시장 코드 없음
    1902: ("NOT_FOUND", False),        # 종목 정보 없음
    # 서버 오류
    1999: ("UPSTREAM_ERROR", True),    # 예기치 못한 에러
    # 앱키/토큰 발급·폐기
    8001: ("INVALID_CREDENTIALS", False),  # App/Secret Key 검증 실패
    8002: ("INVALID_CREDENTIALS", False),
    8020: ("INVALID_CREDENTIALS", False),  # appkey/secretkey 미입력
    8003: ("TOKEN_ISSUE_FAILED", False),   # Access Token 조회 실패
    8006: ("TOKEN_ISSUE_FAILED", False),
    8009: ("TOKEN_ISSUE_FAILED", False),
    8011: ("TOKEN_ISSUE_FAILED", False),
    8012: ("TOKEN_ISSUE_FAILED", False),
    8015: ("TOKEN_REVOKE_FAILED", False),
    8016: ("TOKEN_REVOKE_FAILED", False),
    # 환경/단말 제약
    8010: ("IP_MISMATCH", False),          # 발급 IP와 요청 IP 불일치
    8030: ("ENV_MISMATCH", False),         # 실전/모의 구분 불일치 (Appkey)
    8031: ("ENV_MISMATCH", False),         # 실전/모의 구분 불일치 (Token)
    8040: ("DEVICE_AUTH_FAILED", False),
    8050: ("DEVICE_AUTH_FAILED", False),
    8103: ("DEVICE_AUTH_FAILED", False),
}

HTTP_MAP: dict[int, tuple[str, bool]] = {
    401: ("TOKEN_EXPIRED", False),
    429: ("RATE_LIMITED", True),
}

DEFAULT = ("UPSTREAM_ERROR", False)

# CLI가 직접 발행하는 코드(업스트림 숫자 코드 없음) — CODE_MAP을 거치지 않고
# error_body(code=..., retryable=...)로 호출부에서 직접 지정한다. 참고용 목록:
# CONFIRMATION_REQUIRED, VALIDATION_FAILED, IDEMPOTENCY_CONFLICT, LEDGER_BUSY,
# ORDER_STATUS_UNKNOWN(전송 후 응답 미도착 in-flight 재시도 차단, retryable=False),
# QUOTE_UNAVAILABLE(--dry-run 시장가 예상비용 계산용 시세를 숫자로 해석할 수
# 없음 — 빈 값/0 이하/NaN/Inf 등, retryable=False),
# NOT_CONFIGURED, KEYCHAIN_UNAVAILABLE, NETWORK_ERROR, DEPENDENCY_MISSING.
# 전체 의미는 AGENTS.md "Error codes" 표 참고.


def classify(upstream_code: int | None = None, http_status: int | None = None) -> tuple[str, bool]:
    """(stable_code, retryable)로 분류. http_status가 있으면 우선."""
    if http_status is not None:
        if http_status in HTTP_MAP:
            return HTTP_MAP[http_status]
        if 500 <= http_status < 600:
            return ("UPSTREAM_ERROR", True)
        return DEFAULT
    if upstream_code is not None and upstream_code in CODE_MAP:
        return CODE_MAP[upstream_code]
    return DEFAULT


def build_meta() -> dict[str, Any]:
    ctx = click.get_current_context(silent=True)
    obj = ctx.obj if ctx is not None and isinstance(ctx.obj, dict) else {}
    profile = config.resolve_profile(obj.get("profile"))
    env = config.get_domain_key(profile)
    return {"profile": profile, "env": env, "cont": obj.get("last_cont") or None}


def project_fields(data: Any, fields: list[str]) -> Any:
    """--fields 투영: 요청된 키만 유지, raw 제거.

    키 자체가 fields에 있으면 값이 dict/list여도 통째로 선택된다
    (예: --fields body가 dry-run의 body 전체를 반환). 선택된 값이 dict이면
    최상위 "raw" 키만 제거하고(중첩 raw는 그대로 둠) 원본은 변경하지 않는다.
    선택된 값이 list이면 요소를 건드리지 않고 그대로 반환한다.

    키 자체가 요청되지 않은 dict 컨테이너는 내부를 같은 필드 목록으로
    재귀 투영하고, 결과가 비어 있으면 그 키는 버려진다.

    키 자체가 요청되지 않은 list 컨테이너는 각 dict 원소만 재귀 투영하고
    (스칼라 원소는 그대로 둠), "적어도 하나의 원소가 비어있지 않은 dict로
    투영됐는가"로 보존 여부를 판단한다 — 원소 값의 진위(0, "", False 등)가
    아니라 "요청한 필드를 실제로 담고 있는 dict가 있는가"를 본다. dict를
    하나도 담지 않은 리스트(스칼라 리스트, 빈 리스트)는 이름으로 요청되지
    않는 한 키를 가질 수 없으므로 항상 버려진다.
    """
    if isinstance(data, list):
        return [project_fields(x, fields) if isinstance(x, (dict, list)) else x for x in data]
    if not isinstance(data, dict):
        return data
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k == "raw":
            continue
        if k in fields:
            if isinstance(v, dict):
                out[k] = {kk: vv for kk, vv in v.items() if kk != "raw"}
            else:
                out[k] = v
            continue
        if isinstance(v, list):
            projected = [project_fields(i, fields) if isinstance(i, dict) else i for i in v]
            if any(isinstance(p, dict) and p for p in projected):
                out[k] = projected
        elif isinstance(v, dict):
            sub = project_fields(v, fields)
            if sub:
                out[k] = sub
    return out


def _collect_matched(data: Any, fields: list[str], found: set[str]) -> None:
    """투영된 data를 순회하며 fields 중 실제로 존재한 키를 found에 모은다."""
    if isinstance(data, list):
        for x in data:
            _collect_matched(x, fields, found)
    elif isinstance(data, dict):
        for k, v in data.items():
            if k in fields:
                found.add(k)
            _collect_matched(v, fields, found)


def emit(data: Any = None, *, error: dict[str, Any] | None = None) -> None:
    """Envelope 전체를 단일 JSON 문서로 stdout에 출력."""
    ctx = click.get_current_context(silent=True)
    obj = ctx.obj if ctx is not None and isinstance(ctx.obj, dict) else {}
    fields = obj.get("fields")
    unmatched: list[str] = []
    if fields and data is not None:
        data = project_fields(data, fields)
        found: set[str] = set()
        _collect_matched(data, fields, found)
        unmatched = sorted(set(fields) - found)
    meta = build_meta()
    if unmatched:
        meta["fields_unmatched"] = unmatched
    doc = {
        "ok": error is None,
        "schema": SCHEMA,
        "data": data,
        "meta": meta,
        "error": error,
    }
    click.echo(json.dumps(doc, ensure_ascii=False, indent=2))


def error_body(
    message: str,
    *,
    upstream_code: int | None = None,
    http_status: int | None = None,
    code: str | None = None,
    retryable: bool | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """에러 dict 구성. code/retryable을 직접 주지 않으면 classify()로 결정."""
    if code is None or retryable is None:
        c, r = classify(upstream_code=upstream_code, http_status=http_status)
        code = code if code is not None else c
        retryable = retryable if retryable is not None else r
    body: dict[str, Any] = {
        "code": code,
        "retryable": retryable,
        "message": message,
        "upstream_code": upstream_code if upstream_code is not None else http_status,
    }
    if details is not None:
        body["details"] = details
    return body
