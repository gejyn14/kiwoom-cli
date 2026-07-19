"""Direct unit tests for kiwoom_cli/commands/_mutation.py helpers.

parse_quote_price is a pure function shared by all dry-run quote paths
(KR stock/credit, KR gold, US) — tested directly here instead of only
indirectly through CLI invocations.
"""

from __future__ import annotations

import pytest

from kiwoom_cli.commands._mutation import QuoteUnavailable, parse_quote_price


@pytest.mark.parametrize(
    "value, expected",
    [
        ("70000", 70000.0),
        ("+70000", 70000.0),
        ("-70000", 70000.0),  # 부호는 방향지시자 — 절대값으로 파싱된다
        ("201.4700", 201.47),
        ("+201.4700", 201.47),
        (70000, 70000.0),
        (70000.5, 70000.5),
    ],
)
def test_parse_quote_price_valid(value, expected):
    assert parse_quote_price(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    "value",
    ["0", "+0", "-0", "+00000000", "0.0000", "-0.0"],
)
def test_parse_quote_price_zero_is_unavailable(value):
    """실거래 종목에 가격 0은 없다 — 거래정지/상장전 등 '시세 없음'을 뜻한다.

    원래 버그(조용한 0 폴백)가 정확히 이 값들을 만들어냈다 — 이 값들을 걸러
    내지 못하면 이 함수는 자신이 막으려는 실패를 재현한다.
    """
    with pytest.raises(QuoteUnavailable):
        parse_quote_price(value)


@pytest.mark.parametrize("value", ["", None, "   "])
def test_parse_quote_price_empty_is_unavailable(value):
    with pytest.raises(QuoteUnavailable):
        parse_quote_price(value)


@pytest.mark.parametrize("value", ["N/A", "-", "abc", "1,000"])
def test_parse_quote_price_non_numeric_is_unavailable(value):
    with pytest.raises(QuoteUnavailable):
        parse_quote_price(value)


@pytest.mark.parametrize("value", ["inf", "+inf", "-inf", "Infinity", "nan", "-nan"])
def test_parse_quote_price_non_finite_is_unavailable(value):
    """float()가 파싱은 성공하지만 유한하지 않은 값(Inf/NaN)."""
    with pytest.raises(QuoteUnavailable):
        parse_quote_price(value)
