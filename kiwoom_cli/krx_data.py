"""Fetch and cache KRX stock lists via pykrx."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from pykrx import stock

from kiwoom_cli.config import CACHE_DIR, ensure_cache_dir

CACHE_TTL = timedelta(hours=24)


def get_stock_list(market: str = "ALL", *, refresh: bool = False) -> list[dict]:
    """Return cached (or freshly fetched) stock list for the given market.

    Args:
        market: One of "ALL", "KOSPI", "KOSDAQ", "KONEX".
        refresh: If True, ignore cache and re-fetch.
    """
    cache_key = market.upper()
    if not refresh:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached

    data = _fetch_stocks(cache_key)
    _save_cache(cache_key, data)
    return data


def _fetch_stocks(market: str) -> list[dict]:
    """Fetch all tickers + names from KRX via pykrx."""
    today = datetime.now().strftime("%Y%m%d")
    tickers = stock.get_market_ticker_list(today, market=market)
    result = []
    for t in tickers:
        name = stock.get_market_ticker_name(t)
        result.append({"stk_cd": t, "stk_nm": name, "market": market})
    return result


def _cache_path(cache_key: str) -> Path:
    return CACHE_DIR / f"stocks_{cache_key}.json"


def _load_cache(cache_key: str) -> list[dict] | None:
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(raw["fetched_at"])
        if datetime.now() - fetched_at > CACHE_TTL:
            return None
        return raw["data"]
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_cache(cache_key: str, data: list[dict]) -> None:
    ensure_cache_dir()
    payload = {"fetched_at": datetime.now().isoformat(), "data": data}
    _cache_path(cache_key).write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
