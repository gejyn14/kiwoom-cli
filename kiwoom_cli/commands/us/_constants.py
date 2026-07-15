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
