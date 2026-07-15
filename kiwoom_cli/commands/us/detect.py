"""US symbol detection and exchange resolution."""

from __future__ import annotations

from ._constants import KR_EXCHANGE, US_EXCHANGE


def is_us_symbol(code: str, exchange: str | None = None) -> bool:
    """미국 종목 여부 판별.

    규칙: 6자리 숫자 → 한국, 그 외 → 미국. --exchange 값이 명시되면 그것이 우선.
    """
    if exchange in US_EXCHANGE:
        return True
    if exchange in KR_EXCHANGE:
        return False
    return not (len(code) == 6 and code.isdigit())
