"""Stable JSON response envelope (v1) for `-f json` output.

성공/실패 모두 하나의 envelope로 감쌉니다:
{"ok": bool, "schema": "v1", "data": ..., "meta": {...}, "error": ...}

에러는 안정적인 enum 코드로 분류되어 자동화/에이전트가 upstream 메시지를
파싱하지 않고도 분기할 수 있습니다. csv/table 모드에는 적용되지 않습니다.
"""

from __future__ import annotations

import json
import os
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
    env = os.environ.get("KIWOOM_DOMAIN")
    if env not in config.DOMAINS:
        cfg = config.load_config()
        env = cfg.get("profiles", {}).get(profile, {}).get("domain", "mock")
        if env not in config.DOMAINS:
            env = "mock"
    return {"profile": profile, "env": env, "cont": obj.get("last_cont") or None}


def emit(data: Any = None, *, error: dict[str, Any] | None = None) -> None:
    """Envelope 전체를 단일 JSON 문서로 stdout에 출력."""
    doc = {
        "ok": error is None,
        "schema": SCHEMA,
        "data": data,
        "meta": build_meta(),
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
