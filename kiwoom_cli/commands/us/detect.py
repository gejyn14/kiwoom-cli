"""US symbol detection and exchange resolution."""

from __future__ import annotations

import json
import time

from ... import config
from ...normalize import strip_kr_market_prefix
from ._constants import KR_EXCHANGE, US_EXCHANGE

# 거래소 캐시는 도메인(prod/mock)별로 파일이 갈린다 — 아래 _cache_file 주석 참고.
# 세대 표식 "2": v2.13.0의 도메인 분리가 -p 축을 놓쳐, prod에서 학습한 거래소가
# us_exchanges-mock.json에 기록됐을 수 있다. 그 파일들은 마이그레이션하지 않고
# 읽지 않는다 (v2.12 평문 형식을 폐기한 선례와 동일). 최악의 비용은 usa10098
# 재조회 1회다.
_CACHE_PREFIX = "us_exchanges2"
_CACHE_TTL_SEC = 24 * 60 * 60


def is_us_symbol(code: str, exchange: str | None = None) -> bool:
    """미국 종목 여부 판별.

    규칙: 6자리 숫자 → 한국, 그 외 → 미국. --exchange 값이 명시되면 그것이 우선.
    잔고 응답이 주는 시장구분 접두사 형태('A005930')도 국내로 본다.
    """
    if exchange in US_EXCHANGE:
        return True
    if exchange in KR_EXCHANGE:
        return False
    code = strip_kr_market_prefix(code)
    return not (len(code) == 6 and code.isdigit())


class UsExchangeError(Exception):
    """거래소를 확정할 수 없음 (미등록 또는 복수 상장). --exchange로 지정 필요."""


def _cache_file():
    """도메인별 캐시 파일 경로 (us_exchanges2-prod.json / us_exchanges2-mock.json).

    파일이 하나뿐이면 모의투자에서 학습한 거래소가 실거래 주문의 stex_tp로
    그대로 나간다 — 잘못된 거래소로 실주문이 나가는 경로다.

    프로필로는 나누지 않는다. 'NVDA가 나스닥 상장'은 계좌가 아니라 시장의
    사실이라, 같은 도메인의 프로필끼리는 공유해도 틀릴 여지가 없다. 도메인은
    응답을 주는 서버 자체가 다르므로 반드시 나눈다.

    get_domain_key()를 인자 없이 호출하지만, resolve_profile이 Click 컨텍스트의
    --profile을 읽으므로 -p로 고른 프로필의 도메인이 반영된다. v2.13.0까지는
    그렇지 않아 모의 학습값이 실주문에 실릴 수 있었다.
    """
    return config.CACHE_DIR / f"{_CACHE_PREFIX}-{config.get_domain_key()}.json"


def _load_cache() -> dict:
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


def _cached_exchange(cache: dict, symbol: str) -> str | None:
    """캐시 항목에서 아직 유효한 거래소 코드를 꺼낸다. 없거나 낡았으면 None.

    v2.12 이하의 평문 형식({"NVDA": "ND"})은 마이그레이션하지 않고 버린다 —
    ts가 없어 신선도를 알 수 없고 어느 도메인에서 학습했는지도 모른다.
    다음 조회 때 자연히 새 형식으로 덮인다.
    """
    entry = cache.get(symbol)
    if not isinstance(entry, dict):
        return None
    exchange = entry.get("exchange")
    ts = entry.get("ts")
    if exchange not in US_EXCHANGE.values():
        return None
    if not isinstance(ts, (int, float)) or isinstance(ts, bool):
        return None
    if time.time() - ts > _CACHE_TTL_SEC:
        return None
    return exchange


def _save_cache(cache: dict) -> None:
    config.ensure_cache_dir()
    f = _cache_file()
    f.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    config.secure_file(f)


def resolve_us_exchange(client, code: str, exchange: str | None = None) -> str:
    """종목의 거래소 코드(ND/NY/NA)를 확정한다.

    우선순위: 명시된 --exchange > 파일 캐시 > usa10098 조회 (결과는 캐시에 저장).
    복수 상장이거나 조회 결과가 없으면 UsExchangeError.
    """
    if exchange in US_EXCHANGE:
        return US_EXCHANGE[exchange]
    symbol = code.upper()
    cache = _load_cache()
    cached = _cached_exchange(cache, symbol)
    if cached is not None:
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
    cache[symbol] = {"exchange": stex_tp, "ts": time.time()}
    _save_cache(cache)
    return stex_tp
