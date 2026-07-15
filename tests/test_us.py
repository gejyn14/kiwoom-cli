"""Tests for US stock trading (kiwoom_cli/commands/us/)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.api_spec import API_REGISTRY
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


# ============================================================
#  Task 1: API registry
# ============================================================

US_API_URLS = {
    "ust20000": "/api/us/ordr", "ust20001": "/api/us/ordr",
    "ust20002": "/api/us/ordr", "ust20003": "/api/us/ordr",
    "ust31490": "/api/us/ordr",
    "ust21070": "/api/us/acnt", "ust21160": "/api/us/acnt",
    "ust21110": "/api/us/acnt", "ust21530": "/api/us/acnt",
    "ust21170": "/api/us/acnt", "ust21050": "/api/us/acnt",
    "ust21150": "/api/us/acnt", "ust21510": "/api/us/acnt",
    "ust21180": "/api/us/acnt", "ust21100": "/api/us/acnt",
    "usa10098": "/api/us/stkinfo", "usa10099": "/api/us/stkinfo",
    "usa10100": "/api/us/stkinfo",
    "usa20100": "/api/us/mrkcond", "usa20101": "/api/us/mrkcond",
    "usa06010": "/api/us/chart", "usa06011": "/api/us/chart",
    "usa06012": "/api/us/chart", "usa06013": "/api/us/chart",
    "usa06014": "/api/us/chart", "usa06015": "/api/us/chart",
    "ust31300": "/api/us/exchange", "ust31301": "/api/us/exchange",
    "ust31302": "/api/us/exchange",
}


def test_us_apis_registered():
    for api_id, url in US_API_URLS.items():
        assert api_id in API_REGISTRY, f"{api_id} missing"
        assert API_REGISTRY[api_id][0] == url, f"{api_id} wrong URL"


def test_us_apis_have_korean_descriptions():
    for api_id in US_API_URLS:
        desc = API_REGISTRY[api_id][1]
        assert desc, f"{api_id} has empty description"


# ============================================================
#  Task 2: constants + symbol detection
# ============================================================

from kiwoom_cli.commands.us._constants import (  # noqa: E402
    US_BUY_TYPES,
    US_EXCHANGE,
    US_ORDER_TYPES,
    US_SELL_TYPES,
    US_STOP_TYPES,
)
from kiwoom_cli.commands.us.detect import is_us_symbol  # noqa: E402


@pytest.mark.parametrize("code,exchange,expected", [
    ("005930", None, False),          # 6-digit numeric → KR
    ("NVDA", None, True),             # alpha ticker → US
    ("AAPL", None, True),
    ("BRK.B", None, True),            # dotted ticker → US
    ("12345", None, True),            # 5 digits → not KR shape → US
    ("005930", "nasdaq", True),       # explicit US override wins
    ("NVDA", "KRX", False),           # explicit KR override wins
    ("NVDA", "SOR", False),
    ("TSLA", "amex", True),
])
def test_is_us_symbol(code, exchange, expected):
    assert is_us_symbol(code, exchange) is expected


def test_us_order_type_codes():
    assert US_ORDER_TYPES == {
        "limit": "00", "market": "03",
        "vwap-limit": "26", "twap-limit": "27",
        "loc": "30", "moc": "33",
        "stop-limit": "34", "stop": "35",
        "vwap": "36", "twap": "37",
    }
    assert US_STOP_TYPES == frozenset({"stop", "stop-limit"})
    # buy has NO moc/stop/stop-limit
    assert US_BUY_TYPES == frozenset(
        {"limit", "market", "vwap-limit", "twap-limit", "loc", "vwap", "twap"}
    )
    assert US_SELL_TYPES == US_BUY_TYPES | frozenset({"moc", "stop", "stop-limit"})
    assert US_EXCHANGE == {"nasdaq": "ND", "nyse": "NY", "amex": "NA"}
