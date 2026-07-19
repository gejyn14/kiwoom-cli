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


def test_daily_sends_only_stk_cd(runner, fake_client):
    """daily는 ka10005에 stk_cd만 보낸다 (qry_tp는 스펙에 없는 지어낸 필드였음)."""
    result = runner.invoke(cli, ["stock", "daily", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10005", {"stk_cd": "005930"})]
    body = fake_client.calls[0][1]
    assert "qry_tp" not in body


def test_daily_type_option_removed(runner, fake_client):
    """--type은 ka10005에 존재하지 않는 파라미터였으므로 제거됐다. 이제 거부된다."""
    result = runner.invoke(
        cli, ["stock", "daily", "005930", "--type", "week"]
    )

    assert result.exit_code != 0
    assert fake_client.calls == []


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


def test_credit_inquiry_sends_stk_cd(runner, fake_client):
    """credit inquiry 039490 -> {"stk_cd": "039490"} to kt20017.

    Previously this command sent {} (no way to supply the required stk_cd),
    so the call was rejected by the API outright.
    """
    result = runner.invoke(cli, ["stock", "credit", "inquiry", "039490"])

    assert result.exit_code == 0
    assert fake_client.calls == [("kt20017", {"stk_cd": "039490"})]


def test_credit_inquiry_requires_code_argument(runner, fake_client):
    """credit inquiry without a code argument fails and makes no request.

    Click's UsageError (missing argument) is remapped project-wide to
    EXIT_INPUT=1 (see main.py: click.exceptions.UsageError.exit_code =
    EXIT_INPUT), not Click's default of 2 -- exit code 1 means 입력오류 here.
    """
    result = runner.invoke(cli, ["stock", "credit", "inquiry"])

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_credit_available_default_sends_all_market_and_grade(runner, fake_client):
    """credit available with no options -> mrkt_deal_tp/crd_stk_grde_tp default to "%", no stk_cd key."""
    result = runner.invoke(cli, ["stock", "credit", "available"])

    assert result.exit_code == 0
    assert len(fake_client.calls) == 1
    api_id, body = fake_client.calls[0]
    assert api_id == "kt20016"
    assert body == {"crd_stk_grde_tp": "%", "mrkt_deal_tp": "%"}
    assert "stk_cd" not in body


def test_credit_available_market_kosdaq_sends_0_not_1(runner, fake_client):
    """credit available --market kosdaq must send mrkt_deal_tp="0" (kt20016 polarity is
    inverted vs. the common MARKET_KOSPI_KOSDAQ codebook where kosdaq=1) -- "1" would be
    a polarity-reuse bug.
    """
    result = runner.invoke(
        cli, ["stock", "credit", "available", "--market", "kosdaq"]
    )

    assert result.exit_code == 0
    _, body = fake_client.calls[0]
    assert body["mrkt_deal_tp"] == "0"


def test_credit_available_market_kospi_sends_1(runner, fake_client):
    """credit available --market kospi sends mrkt_deal_tp="1" (kt20016 polarity)."""
    result = runner.invoke(
        cli, ["stock", "credit", "available", "--market", "kospi"]
    )

    assert result.exit_code == 0
    _, body = fake_client.calls[0]
    assert body["mrkt_deal_tp"] == "1"


def test_credit_available_code_and_grade_options(runner, fake_client):
    """credit available --code 039490 --grade a -> stk_cd="039490", crd_stk_grde_tp="A"."""
    result = runner.invoke(
        cli,
        [
            "stock", "credit", "available",
            "--code", "039490", "--grade", "a",
        ],
    )

    assert result.exit_code == 0
    _, body = fake_client.calls[0]
    assert body["stk_cd"] == "039490"
    assert body["crd_stk_grde_tp"] == "A"


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


# ============================================================
#  Investor subgroup — intraday (ka10063)
# ============================================================


def test_investor_intraday_default_sends_all_body_fields(runner, fake_client):
    """기본 호출이 스펙(ka10063 Request Body) 값을 그대로 보내야 한다.

    이전 코드는 --investor-type의 default가 "1000"이었다(ka10058 invsr_tp
    코드북을 복붙한 값으로, ka10063 스펙 invsr는 length=1이라 애초에
    정의되지 않은 값이었다). 이 테스트는 수정 전 코드에서 invsr == "1000"으로
    실패해야 한다(폴스화).
    """
    result = runner.invoke(cli, ["stock", "investor", "intraday"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10063",
            {
                "mrkt_tp": "001",
                "amt_qty_tp": "1",
                "invsr": "6",
                "frgn_all": "0",
                "smtm_netprps_tp": "0",
                "stex_tp": "3",
            },
        )
    ]


def test_investor_intraday_market_all_supported(runner, fake_client):
    """스펙(mrkt_tp: 000:전체, 001:코스피, 101:코스닥)에 000:전체가 있으므로 --market all 지원."""
    result = runner.invoke(cli, ["stock", "investor", "intraday", "--market", "all"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == "000"


@pytest.mark.parametrize(
    "cli_value,api_value",
    [
        ("foreign", "6"), ("institution", "7"), ("investment-trust", "1"),
        ("insurance", "0"), ("bank", "2"), ("pension", "3"), ("state", "4"),
        ("other-corporate", "5"),
    ],
)
def test_investor_intraday_investor_type_enum(runner, fake_client, cli_value, api_value):
    """--investor-type의 human 이름 8종이 invsr 코드로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "intraday", "--investor-type", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["invsr"] == api_value


def test_investor_intraday_investor_type_raw_code_backcompat(runner, fake_client):
    """--investor-type 6 (원시 코드)도 하위호환으로 그대로 통과해 invsr="6"을 보내야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "intraday", "--investor-type", "6"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["invsr"] == "6"


def test_investor_intraday_foreign_all_yes(runner, fake_client):
    """--foreign-all yes가 frgn_all="1"로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "intraday", "--foreign-all", "yes"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["frgn_all"] == "1"


def test_investor_intraday_simultaneous_yes(runner, fake_client):
    """--simultaneous yes가 smtm_netprps_tp="1"로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "intraday", "--simultaneous", "yes"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["smtm_netprps_tp"] == "1"


def test_investor_intraday_amount_qty_rejects_out_of_spec_value(runner, fake_client):
    """--amount-qty는 스펙상 1(금액&수량) 하나뿐이라 다른 값은 exit 1이어야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "intraday", "--amount-qty", "2"]
    )

    assert result.exit_code != 0


def test_investor_intraday_exchange_unchanged(runner, fake_client):
    """--exchange는 이미 EXCHANGE_ALL로 전환되어 있어 이번 작업에서 그대로 둔다."""
    result = runner.invoke(cli, ["stock", "investor", "intraday"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "3"


# ============================================================
#  Investor subgroup — after-close (ka10066)
# ============================================================


def test_investor_after_close_default_sends_net_buy_trde_tp_zero(runner, fake_client):
    """기본 호출은 trde_tp="0"(순매수)를 보내야 한다 (ka10066 스펙: 0:순매수, 1:매수, 2:매도).

    이전 코드는 --trade Choice(["1","2"])에 default="2"였다. help는 "2=순매수"라고
    적었지만 스펙상 2는 매도이고, 진짜 순매수 코드 0은 Choice에 없어 도달 불가능했다.
    이 테스트는 수정 전 코드에서 trde_tp == "2"로 실패해야 한다(폴스화).
    """
    result = runner.invoke(cli, ["stock", "investor", "after-close"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10066",
            {
                "mrkt_tp": "001",
                "amt_qty_tp": "1",
                "trde_tp": "0",
                "stex_tp": "3",
            },
        )
    ]


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("net-buy", "0"), ("buy", "1"), ("sell", "2")],
)
def test_investor_after_close_trade_enum(runner, fake_client, cli_value, api_value):
    """--trade net-buy/buy/sell 각각이 trde_tp 0/1/2로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "after-close", "--trade", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_value


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("amount", "1"), ("quantity", "2")],
)
def test_investor_after_close_amount_qty_enum(runner, fake_client, cli_value, api_value):
    """--amount-qty amount/quantity가 amt_qty_tp 1/2로 매핑되어야 한다 (E-only, 값 불변)."""
    result = runner.invoke(
        cli, ["stock", "investor", "after-close", "--amount-qty", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


def test_investor_after_close_amount_qty_default_unchanged(runner, fake_client):
    """--amount-qty 기본 호출은 변경 전과 동일하게 amt_qty_tp="1"을 보내야 한다."""
    result = runner.invoke(cli, ["stock", "investor", "after-close"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == "1"


def test_investor_after_close_market_all_supported(runner, fake_client):
    """스펙(mrkt_tp: 000:전체, 001:코스피, 101:코스닥)에 000:전체가 있으므로 --market all 지원."""
    result = runner.invoke(
        cli, ["stock", "investor", "after-close", "--market", "all"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == "000"


def test_investor_after_close_market_kosdaq_supported(runner, fake_client):
    """MARKET_TWO -> MARKET_ALL 전환 후에도 --market kosdaq이 mrkt_tp="101"로 계속 동작해야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "after-close", "--market", "kosdaq"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == "101"


# ============================================================
#  Investor subgroup — consecutive (ka10131)
# ============================================================


def test_investor_consecutive_default_sends_amt_qty_tp_zero(runner, fake_client):
    """기본 호출은 amt_qty_tp="0"(금액)을 보내야 한다 (ka10131 스펙: 0:금액, 1:수량).

    이전 코드는 --amount-qty Choice(["1","2"])에 default="1"이었다. 스펙상
    amt_qty_tp는 0:금액,1:수량이라 이전 기본값 "1"은 실제로 수량을 의미했고
    (help의 "1=금액" 표기는 틀렸다), 2는 스펙에 정의조차 없는 값이었다. 이
    테스트는 수정 전 코드에서 amt_qty_tp == "1"로 실패해야 한다(폴스화).
    """
    result = runner.invoke(cli, ["stock", "investor", "consecutive"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == "0"


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("amount", "0"), ("quantity", "1")],
)
def test_investor_consecutive_amount_qty_enum(runner, fake_client, cli_value, api_value):
    """--amount-qty amount/quantity가 amt_qty_tp 0/1로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "consecutive", "--amount-qty", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


def test_investor_consecutive_amount_qty_rejects_two(runner, fake_client):
    """이전 Choice(["1","2"])에서 받아주던 2는 스펙 밖 값이라 이제 exit 1이어야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "consecutive", "--amount-qty", "2"]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


@pytest.mark.parametrize("raw_value,api_value", [("0", "0"), ("1", "1")])
def test_investor_consecutive_amount_qty_raw_codes_still_work(
    runner, fake_client, raw_value, api_value
):
    """스펙이 정의한 raw 코드 0/1은 하위호환으로 계속 전송돼야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "consecutive", "--amount-qty", raw_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


@pytest.mark.parametrize(
    "cli_value,api_value",
    [
        ("recent", "1"), ("3d", "3"), ("5d", "5"), ("10d", "10"),
        ("20d", "20"), ("120d", "120"), ("range", "0"),
    ],
)
def test_investor_consecutive_period_enum(runner, fake_client, cli_value, api_value):
    """--period recent/3d/5d/10d/20d/120d/range가 dt 1/3/5/10/20/120/0으로 매핑되어야 한다 (E-only, 값 불변)."""
    result = runner.invoke(
        cli, ["stock", "investor", "consecutive", "--period", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == api_value


def test_investor_consecutive_period_default_unchanged(runner, fake_client):
    """--period 기본 호출은 변경 전과 동일하게 dt="5"를 보내야 한다."""
    result = runner.invoke(cli, ["stock", "investor", "consecutive"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "5"


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("stock", "0"), ("sector", "1")],
)
def test_investor_consecutive_stock_sector_enum(runner, fake_client, cli_value, api_value):
    """--stock-sector stock/sector가 stk_inds_tp 0/1로 매핑되어야 한다 (E-only, 값 불변)."""
    result = runner.invoke(
        cli, ["stock", "investor", "consecutive", "--stock-sector", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stk_inds_tp"] == api_value


def test_investor_consecutive_net_type_default_sends_net_buy(runner, fake_client):
    """--net-type 기본 호출은 netslmt_tp="2"(순매수, 스펙상 고정값)를 보내야 한다 (E-only, 값 불변)."""
    result = runner.invoke(cli, ["stock", "investor", "consecutive"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["netslmt_tp"] == "2"


def test_investor_consecutive_net_type_net_buy_explicit(runner, fake_client):
    """--net-type net-buy가 netslmt_tp="2"로 매핑되어야 한다 (유일한 값)."""
    result = runner.invoke(
        cli, ["stock", "investor", "consecutive", "--net-type", "net-buy"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["netslmt_tp"] == "2"


def test_investor_consecutive_exchange_unchanged(runner, fake_client):
    """--exchange는 이미 EXCHANGE_ALL로 전환되어 있어 이번 작업에서 그대로 둔다."""
    result = runner.invoke(cli, ["stock", "investor", "consecutive"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["stex_tp"] == "3"


# ============================================================
#  task-14: ka10043 trader-analysis — qry_dt_tp default + required broker
# ============================================================


def test_trader_analysis_default_sends_start_end_mode(runner, fake_client):
    """--date-type 기본값은 이제 "1"(시작일자,종료일자로 조회)이어야 한다.

    이전 기본값 "0"(기간으로 조회)은 --from/--to가 required=True인데도
    API가 무시하고 dt(기간)로 조회하게 만들었다.
    """
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["qry_dt_tp"] == "1"


def test_trader_analysis_broker_required_no_request_sent(runner, fake_client):
    """--broker(mmcm_cd) 없이 호출하면 exit 1이고 요청이 전혀 나가지 않아야 한다."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107",
    ])

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_trader_analysis_days_5d_sends_5_not_4(runner, fake_client):
    """--days 5d는 dt="5"를 보내야 한다 (ka10038의 off-by-one 코드북과 달리 5일=5)."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--days", "5d",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "5"
    assert fake_client.calls[0][1]["dt"] != "4"


def test_trader_analysis_date_type_period_human_name(runner, fake_client):
    """--date-type period -> qry_dt_tp="0"."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--date-type", "period",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["qry_dt_tp"] == "0"


def test_trader_analysis_pot_previous_human_name(runner, fake_client):
    """--pot previous -> pot_tp="1"."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--pot", "previous",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["pot_tp"] == "1"


def test_trader_analysis_sort_close_human_name(runner, fake_client):
    """--sort close -> sort_base="1"."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--sort", "close",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["sort_base"] == "1"


def test_trader_analysis_days_raw_code_backcompat(runner, fake_client):
    """하위호환: --days 5(원시 코드)도 통과해 dt="5"를 보내야 한다."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--days", "5",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "5"
