"""Tests for order commands (kiwoom_cli/commands/order.py).

Strict coverage for all 23 order commands. Tests validate:
- Correct API ID per command
- API body field mapping (qty, price, type, exchange, etc.)
- --confirm flag behavior (prompt gating)
- ORDER_TYPES translation
- Error propagation
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.client import KiwoomAPIError
from kiwoom_cli.commands.order import ORDER_TYPES
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject FakeKiwoomClient into order module."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.order.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


# ============================================================
#  Stock Orders (kt10000 ~ kt10003)
# ============================================================


def test_buy_with_confirm_sends_correct_body(runner, fake_client):
    """--confirm skips prompt and sends full body to kt10000."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--price", "70000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt10000",
            {
                "dmst_stex_tp": "KRX",
                "stk_cd": "005930",
                "ord_qty": "10",
                "ord_uv": "70000",
                "trde_tp": "0",
                "cond_uv": "",
            },
        )
    ]


def test_buy_without_confirm_answering_no_aborts(runner, fake_client):
    """Without --confirm, answering 'n' aborts without sending request."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market"],
        input="n\n",
    )

    assert result.exit_code != 0
    assert fake_client.calls == []


def test_buy_without_confirm_answering_yes_sends_request(runner, fake_client):
    """Without --confirm, answering 'y' sends request."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0][0] == "kt10000"


def test_buy_market_order_omits_price(runner, fake_client):
    """Market order (no --price) sends empty string for ord_uv, not '0'."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 0
    body = fake_client.calls[0][1]
    assert body["ord_uv"] == ""
    assert body["trde_tp"] == "3"  # market = "3"


def test_sell_sends_to_kt10001(runner, fake_client):
    """Sell command hits kt10001 with correct body."""
    result = runner.invoke(
        cli,
        ["order", "sell", "005930", "5", "--price", "72000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "kt10001"
    assert body["stk_cd"] == "005930"
    assert body["ord_qty"] == "5"
    assert body["ord_uv"] == "72000"


def test_modify_sends_to_kt10002_with_mdfy_fields(runner, fake_client):
    """Modify command hits kt10002 with mdfy_qty/mdfy_uv fields."""
    result = runner.invoke(
        cli,
        ["order", "modify", "0000139", "005930", "1", "70000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt10002",
            {
                "dmst_stex_tp": "KRX",
                "orig_ord_no": "0000139",
                "stk_cd": "005930",
                "mdfy_qty": "1",
                "mdfy_uv": "70000",
                "mdfy_cond_uv": "",
            },
        )
    ]


def test_cancel_sends_to_kt10003_with_cncl_qty(runner, fake_client):
    """Cancel command hits kt10003 with cncl_qty."""
    result = runner.invoke(
        cli,
        ["order", "cancel", "0000140", "005930", "--qty", "5", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt10003",
            {
                "dmst_stex_tp": "KRX",
                "orig_ord_no": "0000140",
                "stk_cd": "005930",
                "cncl_qty": "5",
            },
        )
    ]


def test_cancel_full_qty_defaults_to_zero(runner, fake_client):
    """Cancel without --qty sends cncl_qty='0' (full cancel)."""
    result = runner.invoke(
        cli,
        ["order", "cancel", "0000140", "005930", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["cncl_qty"] == "0"


# ============================================================
#  Exchange option propagation
# ============================================================


def test_buy_with_nxt_exchange(runner, fake_client):
    """--exchange NXT propagates to dmst_stex_tp."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market", "--exchange", "NXT", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dmst_stex_tp"] == "NXT"


# ============================================================
#  Credit Orders (kt10006 ~ kt10009)
# ============================================================


def test_credit_buy_sends_to_kt10006(runner, fake_client):
    """Credit buy hits kt10006 with body identical to stock buy."""
    result = runner.invoke(
        cli,
        ["order", "credit", "buy", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 0
    api_id, body = fake_client.calls[0]
    assert api_id == "kt10006"
    assert body["trde_tp"] == "3"
    assert body["stk_cd"] == "005930"


def test_credit_sell_sends_to_kt10007(runner, fake_client):
    """Credit sell hits kt10007."""
    result = runner.invoke(
        cli,
        ["order", "credit", "sell", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt10007"


def test_credit_modify_sends_to_kt10008(runner, fake_client):
    """Credit modify hits kt10008."""
    result = runner.invoke(
        cli,
        ["order", "credit", "modify", "0000139", "005930", "1", "70000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt10008"


def test_credit_cancel_sends_to_kt10009(runner, fake_client):
    """Credit cancel hits kt10009."""
    result = runner.invoke(
        cli,
        ["order", "credit", "cancel", "0000140", "005930", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt10009"


# ============================================================
#  Gold Orders (kt50000 ~ kt50003)
# ============================================================


def test_gold_buy_sends_to_kt50000_without_cond_uv(runner, fake_client):
    """Gold buy hits kt50000 — note NO cond_uv field in body."""
    result = runner.invoke(
        cli,
        ["order", "gold", "buy", "730060", "1", "--price", "90000", "--type", "limit", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "kt50000",
            {
                "dmst_stex_tp": "KRX",
                "stk_cd": "730060",
                "ord_qty": "1",
                "ord_uv": "90000",
                "trde_tp": "0",
            },
        )
    ]
    assert "cond_uv" not in fake_client.calls[0][1]


def test_gold_sell_sends_to_kt50001(runner, fake_client):
    """Gold sell hits kt50001."""
    result = runner.invoke(
        cli,
        ["order", "gold", "sell", "730060", "1", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50001"


def test_gold_modify_sends_to_kt50002(runner, fake_client):
    """Gold modify hits kt50002."""
    result = runner.invoke(
        cli,
        ["order", "gold", "modify", "0000139", "730060", "1", "90000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50002"


def test_gold_cancel_sends_to_kt50003(runner, fake_client):
    """Gold cancel hits kt50003."""
    result = runner.invoke(
        cli,
        ["order", "gold", "cancel", "0000140", "730060", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50003"


# ============================================================
#  Gold Queries (read-only, no --confirm)
# ============================================================


def test_gold_balance_sends_to_kt50020(runner, fake_client):
    """Gold balance query hits kt50020."""
    result = runner.invoke(cli, ["order", "gold", "balance"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50020"


def test_gold_deposit_sends_to_kt50021(runner, fake_client):
    """Gold deposit query hits kt50021."""
    result = runner.invoke(cli, ["order", "gold", "deposit"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50021"


def test_gold_executions_all_sends_to_kt50030(runner, fake_client):
    """Gold executions-all hits kt50030."""
    result = runner.invoke(cli, ["order", "gold", "executions-all"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50030"


def test_gold_executions_sends_to_kt50031(runner, fake_client):
    """Gold executions hits kt50031."""
    result = runner.invoke(cli, ["order", "gold", "executions"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50031"


def test_gold_history_sends_to_kt50032(runner, fake_client):
    """Gold history hits kt50032."""
    result = runner.invoke(cli, ["order", "gold", "history"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50032"


def test_gold_pending_sends_to_kt50075(runner, fake_client):
    """Gold pending hits kt50075."""
    result = runner.invoke(cli, ["order", "gold", "pending"])

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "kt50075"


# ============================================================
#  Condition Search (ka10171 ~ ka10174)
# ============================================================


def test_condition_list_sends_trnm_cnsrlst(runner, fake_client):
    """condition list hits ka10171 with trnm=CNSRLST."""
    result = runner.invoke(cli, ["order", "condition", "list"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10171", {"trnm": "CNSRLST"})]


def test_condition_search_sends_search_type_0(runner, fake_client):
    """condition search hits ka10172 with search_type=0."""
    result = runner.invoke(
        cli,
        ["order", "condition", "search", "001", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10172",
            {
                "trnm": "CNSRREQ",
                "seq": "001",
                "search_type": "0",
                "stex_tp": "K",
            },
        )
    ]


def test_condition_realtime_sends_search_type_1(runner, fake_client):
    """condition realtime hits ka10173 with search_type=1."""
    result = runner.invoke(
        cli,
        ["order", "condition", "realtime", "001", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10173",
            {
                "trnm": "CNSRREQ",
                "seq": "001",
                "search_type": "1",
                "stex_tp": "K",
            },
        )
    ]


def test_condition_stop_sends_trnm_cnsrclr(runner, fake_client):
    """condition stop hits ka10174 with trnm=CNSRCLR."""
    result = runner.invoke(
        cli,
        ["order", "condition", "stop", "001", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("ka10174", {"trnm": "CNSRCLR", "seq": "001"})
    ]


# ============================================================
#  ORDER_TYPES translation (18 types parametrized)
# ============================================================


@pytest.mark.parametrize("type_name,api_code", list(ORDER_TYPES.items()))
def test_order_type_translation(runner, fake_client, type_name, api_code):
    """Each of 18 order types maps to correct API code in trde_tp field."""
    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", type_name, "--price", "70000", "--confirm"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_code


# ============================================================
#  Error propagation
# ============================================================


def test_api_error_returns_nonzero_exit(runner, monkeypatch):
    """KiwoomAPIError from request propagates to exit code 2."""

    class FailingClient(FakeKiwoomClient):
        def request(self, api_id, body=None, **kwargs):
            raise KiwoomAPIError(-1, "주문 실패")

    fake = FailingClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.order.KiwoomClient",
        lambda *args, **kwargs: fake,
    )

    result = runner.invoke(
        cli,
        ["order", "buy", "005930", "10", "--type", "market", "--confirm"],
    )

    assert result.exit_code == 2
