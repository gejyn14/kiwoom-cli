"""Tests for account commands (kiwoom_cli/commands/account.py).

Phase 2 refactor-confidence coverage for read-only account query commands.
One representative test per subgroup, exercising non-trivial bits:
enum -> API value mapping, conditional body keys, date defaults,
and required argument validation.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject FakeKiwoomClient into account module."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.account.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


# ============================================================
#  Top-level account commands
# ============================================================


def test_account_list_hits_ka00001(runner, fake_client):
    """account list smoke test — invokes ka00001 with empty body."""
    result = runner.invoke(cli, ["account", "list"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka00001", {})]


def test_balance_exchange_enum_maps_to_api_value(runner, fake_client):
    """--exchange KRX maps through to dmst_stex_tp, with qry_tp default."""
    result = runner.invoke(cli, ["account", "balance", "--exchange", "KRX"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("kt00004", {"qry_tp": "0", "dmst_stex_tp": "KRX"})
    ]


@pytest.mark.parametrize(
    "type_name,expected_qry_tp",
    [("estimate", "3"), ("normal", "2")],
)
def test_deposit_type_maps_to_qry_tp(
    runner, fake_client, type_name, expected_qry_tp
):
    """--type estimate -> qry_tp=3, --type normal -> qry_tp=2."""
    result = runner.invoke(cli, ["account", "deposit", "--type", type_name])

    assert result.exit_code == 0
    assert fake_client.calls == [("kt00001", {"qry_tp": expected_qry_tp})]


# ============================================================
#  Returns (수익률)
# ============================================================


def test_returns_daily_balance_defaults_to_today(runner, fake_client, monkeypatch):
    """No --date sends body qry_dt == today (YYYYMMDD)."""
    monkeypatch.setattr(
        "kiwoom_cli.commands.account._today",
        lambda: "20260405",
    )

    result = runner.invoke(cli, ["account", "returns", "daily-balance"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka01690", {"qry_dt": "20260405"})]


def test_returns_daily_detail_sends_date_range(runner, fake_client):
    """--from/--to are sent as fr_dt/to_dt to kt00016."""
    result = runner.invoke(
        cli,
        ["account", "returns", "daily-detail", "--from", "20260101", "--to", "20260331"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("kt00016", {"fr_dt": "20260101", "to_dt": "20260331"})
    ]


# ============================================================
#  PnL (손익)
# ============================================================


def test_pnl_today_requires_code_arg(runner, fake_client):
    """pnl today without positional code arg exits nonzero and makes no request."""
    result = runner.invoke(cli, ["account", "pnl", "today"])

    assert result.exit_code != 0
    assert fake_client.calls == []


@pytest.mark.parametrize(
    "code_arg,expected_present",
    [(None, False), ("005930", True)],
    ids=["no-code", "with-code"],
)
def test_pnl_by_date_stk_cd_conditional(
    runner, fake_client, code_arg, expected_present
):
    """pnl by-date: --code adds stk_cd to body when present, omits it otherwise."""
    args = ["account", "pnl", "by-date", "--from", "20260101"]
    if code_arg:
        args += ["--code", code_arg]
    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "ka10072"
    if expected_present:
        assert body["stk_cd"] == code_arg
    else:
        assert "stk_cd" not in body


# ============================================================
#  Orders (주문 조회)
# ============================================================


@pytest.mark.parametrize(
    "code_arg,expected_present",
    [(None, False), ("005930", True)],
    ids=["no-code", "with-code"],
)
def test_orders_pending_stk_cd_conditional(
    runner, fake_client, code_arg, expected_present
):
    """orders pending: --code adds stk_cd to body when present, omits it otherwise."""
    args = ["account", "orders", "pending"]
    if code_arg:
        args += ["--code", code_arg]
    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "ka10075"
    if expected_present:
        assert body["stk_cd"] == code_arg
    else:
        assert "stk_cd" not in body


@pytest.mark.parametrize(
    "order_no_arg,expected_present",
    [(None, False), ("000123", True)],
    ids=["no-order-no", "with-order-no"],
)
def test_orders_executed_ord_no_conditional(
    runner, fake_client, order_no_arg, expected_present
):
    """orders executed: --order-no adds ord_no to body when present, omits it otherwise."""
    args = ["account", "orders", "executed"]
    if order_no_arg:
        args += ["--order-no", order_no_arg]
    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "ka10076"
    if expected_present:
        assert body["ord_no"] == order_no_arg
    else:
        assert "ord_no" not in body


def test_orders_split_detail_sends_order_no(runner, fake_client):
    """orders split-detail: positional arg -> body['ord_no']."""
    result = runner.invoke(
        cli,
        ["account", "orders", "split-detail", "0000139"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10088", {"ord_no": "0000139"})]
