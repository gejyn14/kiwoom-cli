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

# WebSocket 실시간 필드 ID -> 한글 이름 (streaming._format_values에서 이전한 공유 상수)
WS_FIELD_NAMES: dict[str, str] = {
    "10": "현재가",
    "11": "전일대비",
    "12": "등락율",
    "13": "누적거래량",
    "14": "누적거래대금",
    "15": "거래량",
    "16": "시가",
    "17": "고가",
    "18": "저가",
    "20": "체결시간",
    "21": "호가시간",  # 0D(주식호가잔량). "20"(체결시간)과 다른 필드다
    "25": "전일대비기호",
    "27": "매도호가",
    "28": "매수호가",
    "29": "거래대금증감",
    "30": "전일거래량대비",
    "31": "거래회전율",
    "302": "종목명",
    "900": "주문수량",
    "901": "주문가격",
    "902": "미체결수량",
    "903": "체결누계금액",
    "904": "원주문번호",
    "905": "주문구분",
    "906": "매매구분",
    "907": "매도수구분",
    "908": "주문체결시간",
    "909": "체결번호",
    "910": "체결가",
    "911": "체결량",
    "912": "주문업무분류",
    "913": "주문상태",
    "916": "대출일",
    "917": "신용구분",
    "920": "체결수량",
    "930": "보유수량",
    "931": "매입단가",
    "932": "총매입가",
    "933": "주문가능수량",
    "938": "당일순매수수량",
    "939": "매도매수구분",
    "940": "당일총매도손익",
    "941": "예수금",
    "950": "당일실현손익",
    "951": "당일실현손익율",
    "9001": "종목코드",
    "9201": "계좌번호",
    "9203": "주문번호",
}

# 0D(주식호가잔량) 10단계 호가. 스펙(docs/미국 REST API 문서.xlsx 시트
# '주식호가잔량(0D)' Response)과 kwcli 0.1.1 동봉 kiwoom_api_spec.json의
# 같은 API 항목이 필드별로 일치함을 대조해 확인했다:
#   41~50 매도호가1~10      51~60 매수호가1~10
#   61~70 매도호가수량1~10  71~80 매수호가수량1~10
# 블록 시작 ID를 헷갈리면 매도/매수가 통째로 뒤바뀌므로 절대 추측하지 말 것.
# 81~100(직전대비), 121/122/125/126(총잔량), 128/138(순매수·순매도잔량),
# 6044~6115(KRX/NXT 분리 잔량)은 아직 미등록이다.
_ASK_BID_BLOCKS = (
    (41, "매도호가", "ask"),
    (51, "매수호가", "bid"),
    (61, "매도호가수량", "ask_qty"),
    (71, "매수호가수량", "bid_qty"),
)

for _base, _ko, _en in _ASK_BID_BLOCKS:
    for _lvl in range(1, 11):
        WS_FIELD_NAMES[str(_base + _lvl - 1)] = f"{_ko}{_lvl}"
del _base, _ko, _en, _lvl

# WebSocket 필드 ID -> 정규 영문명 (CANONICAL_NAMES와 같은 축).
# 미등록 ID는 WS_FIELD_NAMES의 한글 이름으로, 그것도 없으면 ID 그대로 통과.
WS_CANONICAL: dict[str, str] = {
    "10": "price",
    "11": "change",
    "12": "change_pct",
    "13": "acc_volume",
    "14": "acc_amount",
    "15": "volume",
    "16": "open",
    "17": "high",
    "18": "low",
    "20": "ts",
    "27": "ask",
    "28": "bid",
    "302": "name",
    "908": "ts",
    "9001": "symbol",
    "9203": "order_no",
    "21": "ts",  # 0D 호가시간 (HHmmss) — 20/908과 같은 축의 시각 필드
}

# 0D 10단계 호가: ask1~ask10 / bid1~bid10 / ask_qty1~10 / bid_qty1~10
for _base, _ko, _en in _ASK_BID_BLOCKS:
    for _lvl in range(1, 11):
        WS_CANONICAL[str(_base + _lvl - 1)] = f"{_en}{_lvl}"
del _base, _ko, _en, _lvl

# 시각 필드 ID: 20(체결시간), 908(주문체결시간), 21(호가시간).
# 여기 빠지면 handle_message가 ts=None을 내고 history가 조용히 버린다.
#
# 미검증 위험 — 미국 실시간의 타임존:
# _iso_datetime은 HHMMSS에 무조건 +09:00을 붙인다. 국내 타입(0B/0D 등)은 KST가
# 맞지만, 이 ID들은 미국 타입과도 공유된다 (FT의 21=시간, FE의 20=시간).
# FT/FE 값이 KST인지 현지(ET)인지 스펙으로 확정하지 못했다:
#  - 정황: FE에는 51020 "현지 체결시간"이 따로 있어 20은 현지가 아닌 것으로 보인다
#  - 반증 불가: 워크북 Response Example이 합성 데이터다 (FE의 20과 51020이 둘 다
#    "215300"으로 같고, FT의 41과 FE의 27이 똑같이 "198.5400"이다)
# 틀렸다면 미국 이벤트 ts가 13~14시간 어긋난다. 실제 US 프레임으로 확인 필요.
# 타입별로 다른 타임존을 주려면 _WS_TIME_IDS/_iso_datetime에 타입 문맥이
# 있어야 하는데 지금은 없다 (분류 상수 전반이 api_id 문맥 없이 필드명 기준).
_WS_TIME_IDS = frozenset({"20", "21", "908"})


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


def normalize_ws_values(values: dict[str, Any]) -> dict[str, Any]:
    """WebSocket REAL values(숫자 필드 ID)를 이름 있는 타입 값으로 변환.

    - WS_CANONICAL에 있는 ID는 영문명, 아니면 WS_FIELD_NAMES 한글명, 둘 다 없으면 ID 유지
    - "20"/"908" (체결시간) -> ISO-8601 (+09:00), 키는 "ts"
    - "9001" (종목코드) -> 선행 시장구분 문자(A 등) 제거
    - 숫자 분류는 formatters의 _ABS_FIELDS/_SIGNED_FIELDS를 그대로 따름
      (ABS: 절대값 + 방향 동반 키, SIGNED: 부호 유지)
    """
    out: dict[str, Any] = {}
    for k, v in values.items():
        canon = WS_CANONICAL.get(k) or WS_FIELD_NAMES.get(k, k)
        if k in _WS_TIME_IDS:
            out[canon] = _iso_datetime("tm", v)
        elif k == "9001":
            s = str(v).strip()
            out[canon] = s[1:] if s[:1].isalpha() else s
        elif isinstance(v, str) and k in _NUMERIC_FIELDS:
            num, direction = parse_signed(v)
            if num is None:
                out[canon] = v
            elif k in _ABS_FIELDS:
                out[canon] = abs(num)
                if direction != "flat":
                    dir_key = "change_direction" if canon == "price" else f"{canon}_direction"
                    out[dir_key] = direction
            else:
                out[canon] = num
        else:
            out[canon] = v
    return out


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
