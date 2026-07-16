"""Tests for unified KR+US account views."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient

KR_BALANCE = {
    "return_code": 0,
    "acnt_nm": "테스트",
    "entr": "000001000000",
    "tot_pur_amt": "000007000000",
    "tot_est_amt": "000007230000",
    "aset_evlt_amt": "000008230000",
    "tdy_lspft": "0",
    "tdy_lspft_rt": "0.00",
    "stk_acnt_evlt_prst": [{
        "stk_cd": "A005930", "stk_nm": "삼성전자", "rmnd_qty": "000000100",
        "avg_prc": "000070000", "cur_prc": "000072300",
        "evlt_amt": "0007230000", "pl_amt": "000230000", "pl_rt": "3.28",
    }],
}

US_BALANCE = {
    "return_code": 0,
    "crnc_code": "USD",
    "tot_evlt_amt": "2130.40",
    "tot_prch_amt": "1952.00",
    "tot_pl_amt": "178.40",
    "tot_pl_rt": "9.13",
    "tot_evlt_amt_krw": "000002943100",
    "tot_pl_amt_krw": "000000246500",
    "result_list": [{
        "stex_nm": "NASDAQ", "crnc_code": "USD", "stk_cd": "NVDA",
        "frgn_stk_nm": "엔비디아", "poss_qty": "000000010",
        "frgn_stk_book_uv": "195.2000", "now_pric": "213.0400",
        "evlt_amt": "2130.40", "pl_amt": "178.40", "pl_rt": "9.13",
        "evlt_amt_krw": "000002943100", "pl_amt_krw": "000000246500",
    }],
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def acct_fake(monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response("kt00004", KR_BALANCE)
    fake.set_response("ust21070", US_BALANCE)
    monkeypatch.setattr("kiwoom_cli.commands.account.KiwoomClient", lambda *a, **k: fake)
    monkeypatch.setattr("kiwoom_cli.commands.us.account_ops.KiwoomClient", lambda *a, **k: fake)
    return fake


def _apis(fake):
    return [c[0] for c in fake.calls]


def test_balance_unified_calls_both(runner, acct_fake):
    result = runner.invoke(cli, ["account", "balance"])
    assert result.exit_code == 0
    assert "kt00004" in _apis(acct_fake) and "ust21070" in _apis(acct_fake)
    # both markets rendered
    assert "삼성전자" in result.output
    assert "NVDA" in result.output or "엔비디아" in result.output
    # KRW grand total = 7,230,000 + 2,943,100
    assert "10,173,100" in result.output.replace(" ", "")


def test_balance_market_kr_skips_us(runner, acct_fake):
    result = runner.invoke(cli, ["account", "balance", "--market", "kr"])
    assert result.exit_code == 0
    assert "ust21070" not in _apis(acct_fake)


def test_balance_market_us_skips_kr(runner, acct_fake):
    result = runner.invoke(cli, ["account", "balance", "--market", "us"])
    assert result.exit_code == 0
    assert "kt00004" not in _apis(acct_fake)
    assert "NVDA" in result.output or "엔비디아" in result.output


def test_balance_us_failure_degrades_gracefully(runner, acct_fake, monkeypatch):
    from kiwoom_cli.client import KiwoomAPIError

    orig = acct_fake.request

    def failing(api_id, body=None, **kw):
        if api_id == "ust21070":
            raise KiwoomAPIError(500, "US account not enabled")
        return orig(api_id, body, **kw)

    monkeypatch.setattr(acct_fake, "request", failing)
    result = runner.invoke(cli, ["account", "balance"])
    assert result.exit_code == 0          # KR still renders
    assert "삼성전자" in result.output


# ============================================================
#  Task 10: deposit / pnl / orders / history --market
# ============================================================


@pytest.fixture
def acct_fake_full(acct_fake):
    acct_fake.set_response("kt00001", {"return_code": 0, "entr": "000001000000"})
    acct_fake.set_response("ust21160", {"return_code": 0, "won_entr": "000001000000", "d0_usd_fx_entr": "1234.56"})
    acct_fake.set_response("ka10077", {"return_code": 0, "tot_pl_amt": "1000"})
    acct_fake.set_response("ust21170", {"return_code": 0, "crnc_code": "USD", "tdy_pl_amt": "12.3400", "result_list": []})
    acct_fake.set_response("ka10075", {"return_code": 0, "oso": []})
    acct_fake.set_response("ust21050", {"return_code": 0, "result_list": [
        {"ord_no": "000000123", "stk_cd": "NVDA", "frgn_stk_nm": "엔비디아",
         "ord_qty": "000000010", "ord_uv": "213.0400", "ord_remnq": "000000010",
         "slby_tp_nm": "매수", "ord_stat": "접수"},
    ]})
    acct_fake.set_response("kt00015", {"return_code": 0, "trst_list": []})
    acct_fake.set_response("ust21100", {"return_code": 0, "sell_sum": "0", "buy_sum": "0", "result_list": []})
    return acct_fake


def test_deposit_unified(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "deposit"])
    assert result.exit_code == 0
    assert "kt00001" in _apis(acct_fake_full) and "ust21160" in _apis(acct_fake_full)


def test_deposit_market_us_only(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "deposit", "--market", "us"])
    assert result.exit_code == 0
    assert "kt00001" not in _apis(acct_fake_full)


def test_pnl_today_us_no_code_needed(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "pnl", "today", "--market", "us"])
    assert result.exit_code == 0
    assert ("ust21170", {"fc_krw_tp": "0"}) in acct_fake_full.calls


def test_pnl_today_kr_still_requires_code(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "pnl", "today", "005930", "--market", "kr"])
    assert result.exit_code == 0
    assert ("ka10077", {"stk_cd": "005930"}) in acct_fake_full.calls
    bad = runner.invoke(cli, ["account", "pnl", "today", "--market", "kr"])
    assert bad.exit_code == 1


def test_orders_pending_unified(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "orders", "pending"])
    assert result.exit_code == 0
    assert "ka10075" in _apis(acct_fake_full) and "ust21050" in _apis(acct_fake_full)
    assert "NVDA" in result.output or "엔비디아" in result.output


def test_orders_pending_trade_maps_to_slby(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "orders", "pending", "--trade", "2", "--market", "us"])
    assert result.exit_code == 0
    body = [c for c in acct_fake_full.calls if c[0] == "ust21050"][0][1]
    assert body["slby_tp"] == "2"


def test_history_transactions_unified(runner, acct_fake_full):
    result = runner.invoke(
        cli, ["account", "history", "transactions", "--from", "20260701", "--to", "20260715"]
    )
    assert result.exit_code == 0
    assert "kt00015" in _apis(acct_fake_full) and "ust21100" in _apis(acct_fake_full)
    us_body = [c for c in acct_fake_full.calls if c[0] == "ust21100"][0][1]
    assert us_body == {"strt_dt": "20260701", "end_dt": "20260715", "tp": "0"}


def test_pnl_by_period_unified(runner, acct_fake_full):
    acct_fake_full.set_response("ka10073", {"return_code": 0})
    acct_fake_full.set_response("ust21530", {"return_code": 0, "tot_pl_amt": "10.00", "result_list": []})
    result = runner.invoke(
        cli, ["account", "pnl", "by-period", "--from", "20260701", "--to", "20260715"]
    )
    assert result.exit_code == 0
    assert ("ust21530", {"strt_dt": "20260701", "end_dt": "20260715", "fc_krw_tp": "0"}) in acct_fake_full.calls


def test_orders_executed_unified(runner, acct_fake_full):
    acct_fake_full.set_response("ka10076", {"return_code": 0, "cntr": []})
    acct_fake_full.set_response("ust21510", {"return_code": 0, "result_list": []})
    result = runner.invoke(cli, ["account", "orders", "executed"])
    assert result.exit_code == 0
    assert "ka10076" in _apis(acct_fake_full) and "ust21510" in _apis(acct_fake_full)


def test_orders_pending_dotted_ticker_routes_to_us(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "orders", "pending", "--code", "BRK.B"])
    assert result.exit_code == 0
    kr_body = [c for c in acct_fake_full.calls if c[0] == "ka10075"][0][1]
    assert "stk_cd" not in kr_body                      # never leaks to KR
    us_body = [c for c in acct_fake_full.calls if c[0] == "ust21050"][0][1]
    assert us_body["stk_cd"] == "BRK.B"                 # reaches US filter


def test_orders_executed_dotted_ticker_routes_to_us(runner, acct_fake_full):
    acct_fake_full.set_response("ka10076", {"return_code": 0, "cntr": []})
    acct_fake_full.set_response("ust21510", {"return_code": 0, "result_list": []})
    result = runner.invoke(cli, ["account", "orders", "executed", "--code", "BRK.B"])
    assert result.exit_code == 0
    kr_body = [c for c in acct_fake_full.calls if c[0] == "ka10076"][0][1]
    assert "stk_cd" not in kr_body
    us_body = [c for c in acct_fake_full.calls if c[0] == "ust21510"][0][1]
    assert us_body["stk_cd"] == "BRK.B"


# ============================================================
#  Task 11: account exchange (FX)
# ============================================================


@pytest.fixture
def fx_fake(monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response("ust31301", {"return_code": 0, "aplc_exrt": "1381.500000", "sell_aplc_exrt": "1380.50", "buy_aplc_exrt": "1382.50"})
    fake.set_response("ust31300", {"return_code": 0, "aplc_exrt": "1381.500000", "buy_expc_amt": "723.85"})
    fake.set_response("ust31302", {"return_code": 0, "krw_exmn_amt": "000001000000", "buy_fc_amt": "723.85"})
    monkeypatch.setattr("kiwoom_cli.commands.us.exchange.KiwoomClient", lambda *a, **k: fake)
    return fake


def test_fx_rate(runner, fx_fake):
    result = runner.invoke(cli, ["account", "exchange", "rate"])
    assert result.exit_code == 0
    assert ("ust31301", {"exch_tp": "1"}) in fx_fake.calls


def test_fx_rate_usd_krw_direction(runner, fx_fake):
    result = runner.invoke(cli, ["account", "exchange", "rate", "--direction", "usd-krw"])
    assert result.exit_code == 0
    assert ("ust31301", {"exch_tp": "2"}) in fx_fake.calls


def test_fx_estimate(runner, fx_fake):
    result = runner.invoke(cli, ["account", "exchange", "estimate", "1000000"])
    assert result.exit_code == 0
    assert ("ust31300", {"exch_tp": "1", "fc_exmn_amt": "1000000"}) in fx_fake.calls


def test_fx_apply_requires_confirm_prompt(runner, fx_fake):
    declined = runner.invoke(cli, ["account", "exchange", "apply", "1000000"], input="n\n")
    assert declined.exit_code != 0
    assert [c for c in fx_fake.calls if c[0] == "ust31302"] == []

    accepted = runner.invoke(cli, ["account", "exchange", "apply", "1000000", "--confirm"])
    assert accepted.exit_code == 0
    assert ("ust31302", {"exch_tp": "1", "fc_exmn_amt": "1000000"}) in fx_fake.calls


# ============================================================
#  Final-review fixes
# ============================================================


def test_deposit_json_single_document(runner, acct_fake_full):
    result = runner.invoke(cli, ["--format", "json", "account", "deposit"])
    assert result.exit_code == 0
    payload = json.loads(result.output)   # must parse as ONE document
    assert set(payload["data"]) == {"kr", "us", "raw"}


def test_pnl_today_json_single_document(runner, acct_fake_full):
    result = runner.invoke(cli, ["--format", "json", "account", "pnl", "today", "005930", "--market", "kr"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload["data"]) == {"kr", "us", "raw"}


def test_orders_pending_json_single_document(runner, acct_fake_full):
    result = runner.invoke(cli, ["--format", "json", "account", "orders", "pending"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload["data"]) == {"kr", "us", "raw"}


def test_orders_executed_json_single_document(runner, acct_fake_full):
    acct_fake_full.set_response("ka10076", {"return_code": 0, "cntr": []})
    acct_fake_full.set_response("ust21510", {"return_code": 0, "result_list": []})
    result = runner.invoke(cli, ["--format", "json", "account", "orders", "executed"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload["data"]) == {"kr", "us", "raw"}


def test_history_transactions_json_single_document(runner, acct_fake_full):
    result = runner.invoke(
        cli, ["--format", "json", "account", "history", "transactions", "--from", "20260701", "--to", "20260715"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload["data"]) == {"kr", "us", "raw"}


def test_pnl_by_period_json_single_document(runner, acct_fake_full):
    acct_fake_full.set_response("ka10073", {"return_code": 0})
    acct_fake_full.set_response("ust21530", {"return_code": 0, "tot_pl_amt": "10.00", "result_list": []})
    result = runner.invoke(
        cli, ["--format", "json", "account", "pnl", "by-period", "--from", "20260701", "--to", "20260715"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload["data"]) == {"kr", "us", "raw"}


def test_balance_csv_includes_us_columns(runner, acct_fake):
    result = runner.invoke(cli, ["--format", "csv", "account", "balance"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    header = lines[0].split(",")
    assert {"market", "symbol", "name", "qty", "avg_price", "cur_price",
            "eval_amt", "pl_amt", "pl_rt", "currency", "eval_krw", "pl_krw"} <= set(header)
    us_rows = [line for line in lines[1:] if line.startswith("US,")]
    assert len(us_rows) == 1
    us_row = dict(zip(header, us_rows[0].split(",")))
    assert us_row["name"] == "엔비디아"
    assert us_row["qty"] == "000000010"
    assert us_row["avg_price"] == "195.2000"


def test_pnl_today_us_ticker_never_reaches_kr(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "pnl", "today", "NVDA"])
    assert result.exit_code == 0
    assert all(c[0] != "ka10077" for c in acct_fake_full.calls)
    assert ("ust21170", {"fc_krw_tp": "0"}) in acct_fake_full.calls


def test_pnl_today_kr_market_rejects_us_ticker(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "pnl", "today", "NVDA", "--market", "kr"])
    assert result.exit_code == 1
    assert all(c[0] != "ka10077" for c in acct_fake_full.calls)


def test_balance_both_fail_exits_2(runner, acct_fake, monkeypatch):
    from kiwoom_cli.client import KiwoomAPIError

    def failing(api_id, body=None, **kw):
        if api_id in ("kt00004", "ust21070"):
            raise KiwoomAPIError(500, "boom")
        raise AssertionError(f"unexpected call {api_id}")

    monkeypatch.setattr(acct_fake, "request", failing)
    result = runner.invoke(cli, ["account", "balance"])
    assert result.exit_code == 2
