"""Typed, canonical normalization of Kiwoom API responses.

키움 API는 모든 값을 문자열로 반환하고, 가격류 필드의 +/- 부호는 실제 부호가
아니라 방향지시자입니다 ("+70000" = 상승, 값 70000). 에이전트가 이 인코딩을
알 필요가 없도록 숫자로 파싱하고, 방향지시 필드는 부호를 벗겨
`change_direction`(cur_prc) 또는 `<필드>_direction` 동반 키로 분리합니다.

필드 분류(_ABS_FIELDS/_SIGNED_FIELDS/_USD_FIELDS)는 formatters.py가 단일
소스이며 여기서 재정의하지 않습니다.
"""

from __future__ import annotations

from typing import Any

from .formatters import _ABS_FIELDS, _SIGNED_FIELDS, _USD_FIELDS

# 키움 필드명 -> 정규 필드명 (나머지 키는 그대로 통과)
CANONICAL_NAMES: dict[str, str] = {
    "cur_prc": "price",
    "flu_rt": "change_pct",
    "pred_pre": "change",
    "trde_qty": "volume",
    "stk_cd": "symbol",
    "stk_nm": "name",
    "rmnd_qty": "qty",
    "avg_prc": "avg_price",
    "evlt_amt": "eval_amount",
    "pl_amt": "pl_amount",
    "pl_rt": "pl_pct",
    "ord_no": "order_no",
}

_DATETIME_KEYS = frozenset({"dt", "tm", "cntr_tm"})

_NUMERIC_FIELDS = _ABS_FIELDS | _SIGNED_FIELDS | _USD_FIELDS


def parse_signed(v: Any) -> tuple[int | float | None, str]:
    """키움 숫자 문자열 -> (숫자값, 방향).

    "+70000" -> (70000, "up"), "-1.45" -> (-1.45, "down"), "0" -> (0, "flat"),
    "" -> (None, "flat"). 부호는 값에 반영되며, 방향지시자로 쓸지 여부는
    호출측(normalize_record)이 필드 분류에 따라 결정합니다.
    """
    s = str(v if v is not None else "").strip()
    if not s:
        return None, "flat"
    sign = ""
    if s[0] in "+-":
        sign, s = s[0], s[1:]
    s = s.lstrip("0") or "0"
    try:
        num: int | float = int(s) if "." not in s else float(s)
    except ValueError:
        return None, "flat"
    if sign == "-":
        num = -num
    if num == 0:
        return num, "flat"
    return num, ("down" if sign == "-" else "up" if sign == "+" else "flat")


def _iso_datetime(key: str, v: Any) -> Any:
    """dt/tm/cntr_tm -> ISO-8601 (+09:00). 형식이 안 맞으면 원본 유지."""
    s = str(v).strip()
    if not s.isdigit():
        return v
    if len(s) == 14:  # YYYYMMDDHHMMSS
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:14]}+09:00"
    if key == "dt":
        if len(s) == 8:  # YYYYMMDD (날짜만 — 오프셋 부적용)
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        return v
    if len(s) == 6:  # HHMMSS
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}+09:00"
    return v


def normalize_record(d: dict[str, Any]) -> dict[str, Any]:
    """응답 dict를 정규 이름 + 타입 있는 값으로 변환.

    - CANONICAL_NAMES에 있는 키는 개명, 나머지는 원래 키 유지
    - _ABS_FIELDS: 부호 제거한 숫자 + (부호가 있었으면) 방향 동반 키
    - _SIGNED_FIELDS/_USD_FIELDS: 부호 그대로의 숫자
    - dt/tm/cntr_tm: ISO-8601
    - list/dict 값은 재귀, 알 수 없는 키는 그대로 통과
    """
    out: dict[str, Any] = {}
    for k, v in d.items():
        canon = CANONICAL_NAMES.get(k, k)
        if isinstance(v, dict):
            out[canon] = normalize_record(v)
        elif isinstance(v, list):
            out[canon] = [normalize_record(x) if isinstance(x, dict) else x for x in v]
        elif k in _DATETIME_KEYS:
            out[canon] = _iso_datetime(k, v)
        elif isinstance(v, str) and k in _NUMERIC_FIELDS:
            num, direction = parse_signed(v)
            if num is None:
                out[canon] = v
            elif k in _ABS_FIELDS:
                # 부호 = 방향지시자: 값은 절대값, 방향은 동반 키로
                out[canon] = abs(num)
                if direction != "flat":
                    dir_key = "change_direction" if k == "cur_prc" else f"{canon}_direction"
                    out[dir_key] = direction
            else:
                out[canon] = num
        else:
            out[canon] = v
    return out
