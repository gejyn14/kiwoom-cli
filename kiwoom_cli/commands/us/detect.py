"""US symbol detection and exchange resolution."""

from __future__ import annotations

import json

from ... import config
from ._constants import KR_EXCHANGE, US_EXCHANGE

_CACHE_FILENAME = "us_exchanges.json"


def is_us_symbol(code: str, exchange: str | None = None) -> bool:
    """미국 종목 여부 판별.

    규칙: 6자리 숫자 → 한국, 그 외 → 미국. --exchange 값이 명시되면 그것이 우선.
    """
    if exchange in US_EXCHANGE:
        return True
    if exchange in KR_EXCHANGE:
        return False
    return not (len(code) == 6 and code.isdigit())


class UsExchangeError(Exception):
    """거래소를 확정할 수 없음 (미등록 또는 복수 상장). --exchange로 지정 필요."""


def _cache_file():
    return config.CACHE_DIR / _CACHE_FILENAME


def _load_cache() -> dict[str, str]:
    f = _cache_file()
    if not f.exists():
        return {}
    try:
        cache = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(cache, dict):
        return {}
    return cache


def _save_cache(cache: dict[str, str]) -> None:
    config.ensure_cache_dir()
    _cache_file().write_text(
        json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8"
    )


def resolve_us_exchange(client, code: str, exchange: str | None = None) -> str:
    """종목의 거래소 코드(ND/NY/NA)를 확정한다.

    우선순위: 명시된 --exchange > 파일 캐시 > usa10098 조회 (결과는 캐시에 저장).
    복수 상장이거나 조회 결과가 없으면 UsExchangeError.
    """
    if exchange in US_EXCHANGE:
        return US_EXCHANGE[exchange]
    symbol = code.upper()
    cache = _load_cache()
    cached = cache.get(symbol)
    if cached in US_EXCHANGE.values():
        return cached
    data, _ = client.request("usa10098", {"stk_cd": symbol}, internal=True)
    entries = [
        e for e in data.get("list", []) or []
        if e.get("stk_cd", "").upper() == symbol
    ]
    exchanges = {e.get("stex_tp") for e in entries if e.get("stex_tp")}
    if len(exchanges) != 1:
        raise UsExchangeError(
            f"'{symbol}'의 거래소를 확정할 수 없습니다 "
            f"(조회 결과 {len(exchanges)}건). --exchange nasdaq|nyse|amex 로 지정하세요."
        )
    stex_tp = exchanges.pop()
    cache[symbol] = stex_tp
    _save_cache(cache)
    return stex_tp
