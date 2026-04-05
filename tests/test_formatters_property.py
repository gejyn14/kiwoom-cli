"""Property-based tests for pure helper functions in ``kiwoom_cli.formatters``.

These tests use Hypothesis to assert invariants that should hold across a wide
range of inputs (not just the hand-picked examples in ``test_formatters.py``).
"""

from hypothesis import given, strategies as st

from kiwoom_cli.formatters import (
    _calc_eval_pl,
    _find_list,
    _fmt_number,
    _sign_color,
)


@given(st.text())
def test_fmt_number_never_raises(s):
    """_fmt_number accepts any string and always returns a string."""
    result = _fmt_number(s)
    assert isinstance(result, str)


@given(st.integers(min_value=1000, max_value=10**12))
def test_fmt_number_large_ints_have_commas(n):
    """Ints >= 1000 stringified via _fmt_number contain a comma separator."""
    result = _fmt_number(str(n))
    assert "," in result


@given(st.integers(min_value=-(10**9), max_value=10**9))
def test_fmt_number_strip_sign_has_no_prefix(n):
    """strip_sign=True ensures numeric results have no leading +/- prefix."""
    result = _fmt_number(str(n), strip_sign=True)
    # "-" is the blank-marker sentinel, distinct from a negative sign.
    if result and result != "-":
        assert result[0] not in ("+", "-")


@given(st.text(alphabet=" \t\n\r", min_size=0, max_size=20))
def test_fmt_number_blank_is_dash(s):
    """Whitespace-only (or empty) input returns '-'."""
    assert _fmt_number(s) == "-"


@given(st.text())
def test_sign_color_deterministic(s):
    """_sign_color is deterministic — same input yields same output."""
    assert _sign_color(s) == _sign_color(s)


@given(st.integers(min_value=1, max_value=10**9))
def test_sign_color_negative_always_blue(n):
    """Strings like '-{digit...}' always return 'blue'."""
    assert _sign_color(f"-{n}") == "blue"


@given(
    st.integers(min_value=0, max_value=10**12),
    st.integers(min_value=0, max_value=10**12),
)
def test_calc_eval_pl_sign_tracks_difference(est_amt, pur_amt):
    """Sign of P&L and color follow tot_est_amt vs tot_pur_amt ordering."""
    data = {"tot_est_amt": str(est_amt), "tot_pur_amt": str(pur_amt)}
    amount, _amount_str, _rate_str, color = _calc_eval_pl(data)
    if est_amt > pur_amt:
        assert amount > 0
        assert color == "red"
    elif est_amt < pur_amt:
        assert amount < 0
        assert color == "blue"
    else:
        assert amount == 0
        assert color == "white"


# Scalar strategy: anything that is NOT a list value. Dicts are allowed by
# _find_list (it only picks out lists), so we keep them in the scalar set.
_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
    st.dictionaries(st.text(max_size=5), st.integers(), max_size=3),
)

# _find_list ignores these keys even when their values are lists.
_excluded = st.sampled_from(["return_code", "return_msg"])
# Safe key strategy that avoids the excluded keys.
_safe_keys = st.text(min_size=1, max_size=10).filter(
    lambda k: k not in ("return_code", "return_msg")
)


@given(
    scalar_dict=st.dictionaries(_safe_keys, _scalars, max_size=5),
    list_key=_safe_keys,
    list_val=st.lists(st.integers(), min_size=1, max_size=5),
    excluded_key=_excluded,
    excluded_list=st.lists(st.integers(), max_size=3),
)
def test_find_list_returns_none_when_no_list_values(
    scalar_dict, list_key, list_val, excluded_key, excluded_list
):
    """_find_list returns None for scalar-only dicts and skips excluded keys."""
    # Scalar-only dict (after removing any collision with list_key) → None.
    scalars_only = {k: v for k, v in scalar_dict.items() if k != list_key}
    assert _find_list(scalars_only) is None

    # Adding a list under a non-excluded key → that list is returned.
    with_list = {**scalars_only, list_key: list_val}
    assert _find_list(with_list) == list_val

    # A list under return_code/return_msg alone → still None (excluded).
    assert _find_list({excluded_key: excluded_list}) is None
