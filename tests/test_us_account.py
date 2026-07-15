"""Tests for unified KR+US account views."""

from __future__ import annotations

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
