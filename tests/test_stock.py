"""Tests for stock commands (kiwoom_cli/commands/stock.py).

Phase 2 refactor-confidence coverage for read-only stock query commands.
stock.py is ~1684 lines with many subgroups (credit/analysis/investor/
chart/lending). One representative smoke per subgroup plus enum
parametrization for non-trivial CLI -> API mappings.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from kiwoom_cli.commands._constants import MARKET_ALL
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject FakeKiwoomClient into stock module."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.stock.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


@pytest.fixture
def tmp_stock_cache(tmp_path, monkeypatch):
    """Point the stock list cache at a temp dir."""
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)
    return tmp_path / "stocks.json"


# ============================================================
#  Top-level stock commands
# ============================================================


def test_info_sends_code_to_ka10001(runner, fake_client):
    """info smoke: positional code -> stk_cd body, hits ka10001."""
    result = runner.invoke(cli, ["stock", "info", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10001", {"stk_cd": "005930"})]


def test_price_echoes_name_and_cur_prc(runner, fake_client):
    """price command prints stk_nm and cur_prc from API response."""
    fake_client.set_response(
        "ka10001",
        {
            "stk_nm": "삼성전자",
            "cur_prc": "70000",
            "pred_pre": "+500",
            "flu_rt": "+0.71",
        },
    )
    result = runner.invoke(cli, ["stock", "price", "005930"])

    assert result.exit_code == 0
    assert "삼성전자 (005930): 70,000원 (+500, +0.71%)" in result.output


def test_compare_strips_direction_sign_from_price(runner, fake_client):
    """compare table: 하락 종목의 현재가는 음수로 표시되지 않는다 (부호는 방향지시자)."""
    fake_client.set_response(
        "ka10001",
        {
            "stk_nm": "삼성전자",
            "cur_prc": "-68000",
            "trde_qty": "10000000",
        },
    )
    result = runner.invoke(cli, ["stock", "compare", "005930", "000660"])

    assert result.exit_code == 0
    assert "-68,000" not in result.output, "현재가에 방향지시자 부호가 그대로 노출됨"
    assert "68,000" in result.output


def test_orderbook_sends_to_ka10004(runner, fake_client):
    """orderbook smoke: positional code -> stk_cd body, hits ka10004."""
    result = runner.invoke(cli, ["stock", "orderbook", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10004", {"stk_cd": "005930"})]


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("day", "1"), ("week", "2"), ("month", "3")],
)
def test_daily_qry_type_enum_parametrized(
    runner, fake_client, cli_value, api_value
):
    """daily --type day/week/month maps to qry_tp 1/2/3."""
    result = runner.invoke(
        cli, ["stock", "daily", "005930", "--type", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("ka10005", {"stk_cd": "005930", "qry_tp": api_value})
    ]


def test_watchlist_passes_pipe_delimited_codes(runner, fake_client):
    """watchlist sends pipe-delimited codes to stk_cd as-is."""
    result = runner.invoke(cli, ["stock", "watchlist", "005930|000660"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10095", {"stk_cd": "005930|000660"})]


def test_sync_emits_json_envelope(runner, fake_client, tmp_stock_cache):
    """stock sync -f json 출력은 파싱 가능한 envelope이어야 한다.

    기존에는 모든 포맷에서 click.echo로 평문을 찍어 -f json이 stdout에
    envelope 대신 사람이 읽는 문장을 남겼다 (agent contract 위반).
    """
    result = runner.invoke(cli, ["-f", "json", "stock", "sync"])

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["ok"] is True
    assert doc["data"]["synced"] == 0
    assert doc["data"]["cache"].endswith("stocks.json")


def test_sync_csv_stdout_is_empty(runner, fake_client, tmp_stock_cache):
    """stock sync -f csv 는 stdout에 아무것도 남기지 않아야 한다 (CSV 계약).

    envelope.emit은 항상 JSON을 찍으므로 `_get_format() != "table"` 게이트로는
    -f csv에서도 JSON 블롭이 stdout에 새어나간다. csv 모드에서는 완료 메시지가
    stderr로만 가고 stdout은 완전히 비어 있어야 한다.
    """
    result = runner.invoke(cli, ["-f", "csv", "stock", "sync"])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "동기화 완료" in result.stderr


def test_search_empty_result_emits_json_envelope(runner, tmp_stock_cache):
    """검색 결과가 없을 때도 -f json은 파싱 가능한 envelope을 출력해야 한다.

    기존에는 click.echo("검색 결과가 없습니다.")로 평문만 남겨 -f json에서
    stdout이 파싱 불가능한 문장이 됐다.
    """
    tmp_stock_cache.write_text(
        json.dumps({
            "fetched_at": "2026-01-01T00:00:00",
            "count": 1,
            "data": [
                {"stk_cd": "005930", "stk_nm": "삼성전자", "market": "코스피", "type": "주식"},
            ],
        }),
        encoding="utf-8",
    )

    result = runner.invoke(cli, ["-f", "json", "stock", "search", "존재하지않는종목명"])

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["ok"] is True
    assert doc["data"]["items"] == []


def test_daily_price_required_date(runner, fake_client):
    """daily-price without --date fails nonzero and makes no request."""
    result = runner.invoke(cli, ["stock", "daily-price", "005930"])

    assert result.exit_code != 0
    assert fake_client.calls == []


# ============================================================
#  Credit subgroup
# ============================================================


def test_credit_trend_sends_correct_api(runner, fake_client):
    """credit trend smoke: hits ka10013 with stk_cd/dt/qry_tp body."""
    result = runner.invoke(
        cli,
        ["stock", "credit", "trend", "005930", "--date", "20260101"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10013",
            {"stk_cd": "005930", "dt": "20260101", "qry_tp": "1"},
        )
    ]


# ============================================================
#  Analysis subgroup
# ============================================================


@pytest.mark.parametrize("cli_value,api_value", list(MARKET_ALL.items()))
def test_analysis_volume_renewal_market_enum(
    runner, fake_client, cli_value, api_value
):
    """Each MARKET_ALL key maps to correct API value in mrkt_tp field."""
    result = runner.invoke(
        cli,
        ["stock", "analysis", "volume-renewal", "--market", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][0] == "ka10024"
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value
    assert fake_client.calls[0][1]["stex_tp"] == "3"  # EXCHANGE_ALL["all"] default
