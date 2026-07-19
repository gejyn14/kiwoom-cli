"""Shared lookup maps for US stock commands."""

from __future__ import annotations

# CLI value -> API stex_tp code
US_EXCHANGE = {"nasdaq": "ND", "nyse": "NY", "amex": "NA"}
# list-type APIs accept % (전체)
US_EXCHANGE_ALL = {**US_EXCHANGE, "all": "%"}

# Korean exchange CLI values (existing convention in order.py/account.py)
KR_EXCHANGE = frozenset({"KRX", "NXT", "SOR"})

# CLI value -> trde_tp code (ust20000/ust20001)
US_ORDER_TYPES = {
    "limit": "00",       # 지정가
    "market": "03",      # 시장가
    "vwap-limit": "26",  # VWAP 지정가
    "twap-limit": "27",  # TWAP 지정가
    "loc": "30",         # Limit On Close
    "moc": "33",         # Market On Close (매도 전용)
    "stop-limit": "34",  # Stop Limit (매도 전용, --stop + --price)
    "stop": "35",        # Stop Market (매도 전용, --stop)
    "vwap": "36",        # VWAP 시장가
    "twap": "37",        # TWAP 시장가
}

# 매도 전용 유형 (ust20000 매수는 미지원)
US_SELL_ONLY_TYPES = frozenset({"moc", "stop", "stop-limit"})
US_BUY_TYPES = frozenset(US_ORDER_TYPES) - US_SELL_ONLY_TYPES
US_SELL_TYPES = frozenset(US_ORDER_TYPES)
US_STOP_TYPES = frozenset({"stop", "stop-limit"})

# ord_uv(주문단가)가 빈 값 처리되는 시장가 계열 (ust20000/ust20001 스펙:
# "trde_tp가 00(지정가),30(LOC)...인 경우 필수 입력, 그 외 시장가 거래유형
# 설정 시 입력 값은 빈 값 처리"). vwap-limit(26)/twap-limit(27)/loc(30)은
# "지정가" 계열이라 제외 — 시장가 변형인 moc(33)/vwap(36)/twap(37)/stop(35)
# 만 포함한다. stop-limit(34)은 트리거 후 지정가로 체결되므로 제외.
US_MARKET_TYPES = frozenset({"market", "moc", "vwap", "twap", "stop"})

# ord_uv(주문단가)가 필수인 지정가 계열 — ust20000/ust20001 스펙:
# "trde_tp가 00(지정가),30(LOC)...인 경우 필수 입력".
# US_MARKET_TYPES의 여집합으로 정의한다 — 이 정의 방식은 실수를 막지 못하고
# 비대칭으로 만든다. 새 주문유형을 추가하며 US_MARKET_TYPES 갱신을 깜빡하면
# 그 유형은 조용히 이쪽(지정가 계열)으로 떨어져 --price를 요구하게 된다.
# 즉 실제 시장가 유형에 --price 없이 정상 주문을 넣으려는 호출이 거부되는
# 쪽으로만 실패한다 — 반대로 지정가 유형이 시장가로 잘못 분류돼 --price
# 없이 조용히 전송되는 실패는 나올 수 없다. 주문 경로에서는 이 비대칭이
# 의도한 선택이다: 정당한 요청을 잘못 거부하는 편이, 가격을 빠뜨린 주문을
# 조용히 내보내는 것보다 안전하다.
US_LIMIT_TYPES = frozenset(US_ORDER_TYPES) - US_MARKET_TYPES
