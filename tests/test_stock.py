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


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "000"), ("kospi", "001"), ("kosdaq", "101")],
)
def test_analysis_volume_renewal_market_enum(
    runner, fake_client, cli_value, api_value
):
    """Each MARKET_ALL key maps to correct API value in mrkt_tp field.

    하드코딩 리터럴로 고정한다 — list(MARKET_ALL.items())로 파라미터화하면
    MARKET_ALL 자체의 극성이 뒤집혀도(all<->kospi 값 스왑 등) 테스트가
    같이 뒤집혀 계속 통과하는 자기참조 함정에 빠진다(Task 34a가 경계하는
    안티패턴 그 자체)."""
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


def test_investor_consecutive_net_type_rejects_net_sell(runner, fake_client):
    """NETSLMT_TP_NET_BUY_ONLY({net-buy:2})는 Task 34b가 추가한
    PROGRAM_TOP_SIDE({net-sell:1,net-buy:2})의 진짜 부분집합이다(클로저
    스크립트로 확인) — "net-sell"은 저쪽에만 있으므로 거부돼야 한다. 상수가
    실수로 PROGRAM_TOP_SIDE로 바꿔치기되면 이 테스트가 실패한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "consecutive", "--net-type", "net-sell"]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


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


def test_trader_analysis_days_5_sends_5_not_4(runner, fake_client):
    """--days 5(raw 스펙 코드)는 dt="5"를 보내야 한다 (ka10038의 off-by-one
    코드북과 달리 5일=5). HumanChoice는 raw API 코드를 하위호환으로 그대로
    통과시키므로 이 경로는 영향받지 않는다."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--days", "5",
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


def test_trader_analysis_days_default_unchanged(runner, fake_client):
    """--days 기본 호출은 v2.11.0과 동일하게 dt="20"을 보내야 한다(전송 바이트
    불변, default="20d" -> "20")."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "20"


def test_trader_analysis_days_human_name_maps_to_code(runner, fake_client):
    """--days(dt)는 v2.11.0에 배포된 HumanChoice로 복원됐다 — "5d" 같은 human
    이름이 dt="5"로 매핑되어 전송된다(TRADER_ANALYSIS_PERIOD_5_120, market.py의
    ka10042 --period와 공유). Task 34a가 I2 규칙 재적용으로 raw 텍스트로
    되돌렸던 것은 이미 배포된 검증을 걷어내는 조용한 회귀였다 — 리뷰에서
    다시 원복했다."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--days", "5d",
    ])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["dt"] == "5"


def test_trader_analysis_days_rejects_spec_outside_value(runner, fake_client):
    """스펙(5/10/20/40/60/120) 밖의 --days 값은 exit 1이고 요청이 나가지
    않아야 한다 — raw 텍스트로 되돌아갔던 동안(현재 HEAD 이전)에는 "999"가
    검증 없이 그대로 전송되며 exit 0을 반환했다(조용한 실패)."""
    result = runner.invoke(cli, [
        "stock", "analysis", "trader-analysis", "005930",
        "--from", "20260101", "--to", "20260107", "--broker", "001",
        "--days", "999",
    ])

    assert result.exit_code == 1
    assert fake_client.calls == []


# ============================================================
#  Task 34a — HumanChoice 전환 (daily_price ~ by_stock_total)
# ============================================================


# ── daily-price (ka10086) ────────────────────────────────


def test_daily_price_default_sends_indc_tp_zero(runner, fake_client):
    """기본 호출은 종전과 동일하게 indc_tp="0"(수량)을 보내야 한다."""
    result = runner.invoke(cli, ["stock", "daily-price", "005930", "--date", "20260101"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("ka10086", {"stk_cd": "005930", "qry_dt": "20260101", "indc_tp": "0"})
    ]


@pytest.mark.parametrize("cli_value,api_value", [("quantity", "0"), ("amount", "1")])
def test_daily_price_display_enum(runner, fake_client, cli_value, api_value):
    """--display quantity/amount가 indc_tp 0/1로 매핑되어야 한다 (리터럴 핀 —
    AMT_QTY_TP_0_1(0:금액,1:수량)과 극성이 반대라 자기참조 테스트로는 못
    잡는다)."""
    result = runner.invoke(
        cli, ["stock", "daily-price", "005930", "--date", "20260101", "--display", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["indc_tp"] == api_value


def test_daily_price_display_raw_code_backcompat(runner, fake_client):
    """--display 1(원시 코드)도 통과해 indc_tp="1"을 보내야 한다."""
    result = runner.invoke(
        cli, ["stock", "daily-price", "005930", "--date", "20260101", "--display", "1"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["indc_tp"] == "1"


# ── today-exec (ka10084) / today-volume (ka10055) ────────


def test_today_exec_default_sends_today_tick(runner, fake_client):
    """기본 호출은 종전과 동일하게 tdy_pred="1", tic_min="0"을 보내야 한다."""
    result = runner.invoke(cli, ["stock", "today-exec", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        ("ka10084", {"stk_cd": "005930", "tdy_pred": "1", "tic_min": "0"})
    ]


@pytest.mark.parametrize("cli_value,api_value", [("today", "1"), ("previous", "2")])
def test_today_exec_when_enum_literal(runner, fake_client, cli_value, api_value):
    """--when today/previous가 tdy_pred 1/2로 매핑되어야 한다 (리터럴 핀 —
    TODAY_PREV_1_2는 다른 today/previous 계열(today:0,previous:1)과 극성이
    반대라 자기참조 테스트로는 극성 뒤바뀜을 못 잡는다)."""
    result = runner.invoke(cli, ["stock", "today-exec", "005930", "--when", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["tdy_pred"] == api_value


@pytest.mark.parametrize("cli_value,api_value", [("tick", "0"), ("minute", "1")])
def test_today_exec_mode_enum_literal(runner, fake_client, cli_value, api_value):
    """--mode tick/minute이 tic_min 0/1로 매핑되어야 한다 (리터럴 핀)."""
    result = runner.invoke(cli, ["stock", "today-exec", "005930", "--mode", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["tic_min"] == api_value


def test_today_volume_default_sends_today(runner, fake_client):
    """기본 호출은 종전과 동일하게 tdy_pred="1"을 보내야 한다."""
    result = runner.invoke(cli, ["stock", "today-volume", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10055", {"stk_cd": "005930", "tdy_pred": "1"})]


@pytest.mark.parametrize("cli_value,api_value", [("today", "1"), ("previous", "2")])
def test_today_volume_when_enum_literal(runner, fake_client, cli_value, api_value):
    """--when today/previous가 tdy_pred 1/2로 매핑되어야 한다 (리터럴 핀,
    today-exec와 TODAY_PREV_1_2를 공유 — 2개 api_id 커플링)."""
    result = runner.invoke(cli, ["stock", "today-volume", "005930", "--when", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["tdy_pred"] == api_value


# ── analysis price-cluster (ka10025) ─────────────────────


def test_price_cluster_default_sends_cur_prc_entry_zero(runner, fake_client):
    """기본 호출은 종전과 동일하게 cur_prc_entry="0"(미포함)을 보내야 한다."""
    result = runner.invoke(cli, ["stock", "analysis", "price-cluster"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10025",
            {
                "mrkt_tp": "000", "prps_cnctr_rt": "50", "cur_prc_entry": "0",
                "prpscnt": "5", "cycle_tp": "100", "stex_tp": "3",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("yes", "1"), ("no", "0")])
def test_price_cluster_include_current_enum(runner, fake_client, cli_value, api_value):
    """--include-current yes/no가 cur_prc_entry 1/0로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "price-cluster", "--include-current", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["cur_prc_entry"] == api_value


# ── analysis open-change (ka10028) ───────────────────────


def test_open_change_default_body_after_qty_cnd_fix(runner, fake_client):
    """기본 호출 바디 (trde_qty_cnd 결함 수정 후).

    --volume-cond(trde_qty_cnd)는 전환 전 자유 텍스트로 기본값 raw "0"을
    보내고 있었는데, 스펙(4자리 zero-pad)에는 "0"이 없고 "0000"이 전체조회다
    — Task 31b의 RANK_CHANGE_QTY_CND와 동일한 패턴의 결함이라 여기서도
    "0000"으로 교정했다(전송 바이트가 바뀌는 fix, CHANGELOG 기재 대상).
    나머지 필드는 전송값이 종전과 동일하다.
    """
    result = runner.invoke(cli, ["stock", "analysis", "open-change"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10028",
            {
                "sort_tp": "1", "trde_qty_cnd": "0000", "mrkt_tp": "000",
                "updown_incls": "0", "stk_cnd": "0", "crd_cnd": "0",
                "trde_prica_cnd": "0", "flu_cnd": "1", "stex_tp": "3",
            },
        )
    ]


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("open", "1"), ("high", "2"), ("low", "3"), ("base", "4")],
)
def test_open_change_sort_enum_literal(runner, fake_client, cli_value, api_value):
    """--sort open/high/low/base가 sort_tp 1/2/3/4로 매핑되어야 한다 (리터럴
    핀 — NEAR_HIGHLOW_KIND(high:1,low:2)와 high/low 키가 겹치지만 값이 다르다,
    극성 해저드)."""
    result = runner.invoke(cli, ["stock", "analysis", "open-change", "--sort", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["sort_tp"] == api_value


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "0000"), ("10k", "0010"), ("1000k", "1000")],
)
def test_open_change_volume_cond_enum(runner, fake_client, cli_value, api_value):
    """--volume-cond의 human 이름이 4자리 zero-pad trde_qty_cnd로 매핑되어야
    한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--volume-cond", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_qty_cnd"] == api_value


def test_open_change_volume_cond_rejects_sibling_only_value(runner, fake_client):
    """OPEN_CHANGE_QTY_CND는 RANK_CHANGE_QTY_CND(ka10027)의 진짜 부분집합이다
    — "150k"는 RANK_CHANGE_QTY_CND에만 있고 여기엔 없으므로 거부돼야 한다.
    형제 상수로 바꿔치기하면(OPEN_CHANGE_QTY_CND -> RANK_CHANGE_QTY_CND) 이
    테스트가 실패한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--volume-cond", "150k"]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


@pytest.mark.parametrize("cli_value,api_value", [("yes", "1"), ("no", "0")])
def test_open_change_include_limit_enum(runner, fake_client, cli_value, api_value):
    """--include-limit yes/no가 updown_incls 1/0로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--include-limit", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["updown_incls"] == api_value


@pytest.mark.parametrize(
    "absent",
    [
        "exclude-managed-preferred-alert",  # LIMIT_MOVE_STK_CND(ka10017) 전용
        "exclude-liquidation",   # RANK_CHANGE/EXPECTED_CHANGE/VOLUME_SURGE/AFTERHOURS_CHANGE 전용
        "only-margin-50",        # RANK_CHANGE/EXPECTED_CHANGE/VOLUME_SURGE/AFTERHOURS_CHANGE 전용
        "only-margin-60",        # RANK_CHANGE/EXPECTED_CHANGE/VOLUME_SURGE/AFTERHOURS_CHANGE 전용
        "exclude-etf",           # RANK_CHANGE/EXPECTED_CHANGE/VOLUME_SURGE/AFTERHOURS_CHANGE 전용
        "exclude-spac",          # RANK_CHANGE/EXPECTED_CHANGE/VOLUME_SURGE/AFTERHOURS_CHANGE 전용
        "exclude-etf-etn",       # RANK_CHANGE/EXPECTED_CHANGE/VOLUME_SURGE/AFTERHOURS_CHANGE 전용
        "exclude-etn",           # VOLUME_SURGE/AFTERHOURS_CHANGE 전용
        "exclude-etf-etn-spac",  # VOLUME_SURGE 전용
    ],
)
def test_open_change_stock_cond_rejects_sibling_only_value(runner, fake_client, absent):
    """OPEN_CHANGE_STK_CND(9개 값)는 LIMIT_MOVE_STK_CND(ka10017)/
    RANK_CHANGE_STK_CND(ka10027)/EXPECTED_CHANGE_STK_CND(ka10029)/
    VOLUME_SURGE_STK_CND(ka10023)/AFTERHOURS_CHANGE_STK_CND(ka10098)
    5개 전부의 진짜 부분집합이다(superset-closure 스크립트로 확인) —
    이 5개 형제 상수가 OPEN_CHANGE_STK_CND에 없이 추가로 갖는 키의
    합집합을 파라미터화했다. 형제 상수 하나로만 검증하면(예:
    exclude-liquidation만) 다른 형제로의 오치환(예: OPEN_CHANGE_STK_CND
    -> LIMIT_MOVE_STK_CND, 유일한 초과 키는
    exclude-managed-preferred-alert)을 놓친다 — 실제로 그 치환은 suite를
    통과시킨 채 stk_cnd="10"(ka10028엔 미정의)을 전송했다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--stock-cond", absent]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


def test_open_change_stock_cond_accepts_all_nine_values(runner, fake_client):
    """OPEN_CHANGE_STK_CND의 9개 값 전부가 stk_cnd로 매핑되어야 한다(자유
    텍스트 -> enum 전환의 커버리지 확인, breaking 표기 근거)."""
    expected = {
        "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
        "exclude-managed-preferred": "4", "exclude-margin-100": "5",
        "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
        "only-margin-20": "9",
    }
    for name, code in expected.items():
        result = runner.invoke(
            cli, ["stock", "analysis", "open-change", "--stock-cond", name]
        )
        assert result.exit_code == 0
        assert fake_client.calls[-1][1]["stk_cnd"] == code


def test_open_change_credit_cond_rejects_sibling_only_value(runner, fake_client):
    """OPEN_CHANGE_CREDIT_CND(7개 값)는 EXPECTED_CHANGE_CREDIT_CND/
    AFTERHOURS_CHANGE_CREDIT_CND(9개 값, ka10029/ka10098)의 진짜 부분집합
    이다 — "short"/"exclude-overlimit"은 저쪽에만 있으므로 여기서는 거부돼야
    한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--credit-cond", "short"]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "0"), ("a", "1"), ("e", "7"), ("all-financing", "9")],
)
def test_open_change_credit_cond_enum(runner, fake_client, cli_value, api_value):
    """--credit-cond human 이름이 crd_cnd로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--credit-cond", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["crd_cnd"] == api_value


def test_open_change_amount_cond_50m_literal_pin(runner, fake_client):
    """--amount-cond 50m이 trde_prica_cnd="5"로 매핑되어야 한다 (리터럴 핀 —
    VOLUME_RANK_AMOUNT_TYPE(ka10030)의 키 집합을 포함하지만 "50m"만 값이
    다르다(거기는 "4"), 극성 해저드). 자기참조 테스트로는 이 뒤바뀜을 못
    잡는다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--amount-cond", "50m"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_prica_cnd"] == "5"
    assert fake_client.calls[0][1]["trde_prica_cnd"] != "4"


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "0"), ("30m", "3"), ("1b", "100"), ("50b", "5000")],
)
def test_open_change_amount_cond_enum(runner, fake_client, cli_value, api_value):
    """--amount-cond human 이름이 trde_prica_cnd로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--amount-cond", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_prica_cnd"] == api_value


@pytest.mark.parametrize("cli_value,api_value", [("top", "1"), ("bottom", "2")])
def test_open_change_direction_enum(runner, fake_client, cli_value, api_value):
    """--direction top/bottom이 flu_cnd 1/2로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "open-change", "--direction", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["flu_cnd"] == api_value


# ── analysis instant-volume (ka10052) ────────────────────


def test_instant_volume_default_body(runner, fake_client):
    """기본 호출 바디는 종전과 동일해야 한다 (qty_tp는 이번 태스크에서 미전환
    -- 코드 3/5 라벨 미확인)."""
    result = runner.invoke(cli, ["stock", "analysis", "instant-volume", "--broker", "001"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10052",
            {"mmcm_cd": "001", "mrkt_tp": "0", "qty_tp": "0", "pric_tp": "0", "stex_tp": "3"},
        )
    ]


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "0"), ("kospi", "1"), ("kosdaq", "2"), ("stock", "3")],
)
def test_instant_volume_market_enum_literal(runner, fake_client, cli_value, api_value):
    """--market이 mrkt_tp로 매핑되어야 한다 (리터럴 핀 — mrkt_tp는 이
    코드베이스에 최소 4개의 서로 다른 코드북이 있다, MARKET_ALL/MARKET_TWO/
    SECTOR_PRICE_MARKET 등과 절대 합치면 안 됨)."""
    result = runner.invoke(
        cli, ["stock", "analysis", "instant-volume", "--broker", "001", "--market", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == api_value


def test_instant_volume_price_type_rejects_sibling_only_value(runner, fake_client):
    """INSTANT_VOLUME_PRICE_TYPE(7개 값)는 RANK_CHANGE_PRICE_CND/
    EXPECTED_CHANGE_PRICE_CND(8개 값, ka10027/ka10029)의 진짜 부분집합이다
    — "under-10k"는 저쪽에만 있으므로 여기서는 거부돼야 한다."""
    result = runner.invoke(
        cli,
        ["stock", "analysis", "instant-volume", "--broker", "001", "--price-type", "under-10k"],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "0"), ("under-1k", "1"), ("over-1k", "8"), ("over-10k", "5")],
)
def test_instant_volume_price_type_enum(runner, fake_client, cli_value, api_value):
    """--price-type human 이름이 pric_tp로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "instant-volume", "--broker", "001", "--price-type", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["pric_tp"] == api_value


# ── analysis vi-trigger (ka10054) ────────────────────────


def test_vi_trigger_default_body(runner, fake_client):
    """기본 호출 바디는 종전과 동일해야 한다."""
    result = runner.invoke(cli, ["stock", "analysis", "vi-trigger"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10054",
            {
                "mrkt_tp": "000", "bf_mkrt_tp": "0", "motn_tp": "0", "skip_stk": "0",
                "trde_qty_tp": "0", "trde_prica_tp": "0", "motn_drc": "0", "stex_tp": "3",
            },
        )
    ]


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "0"), ("regular", "1"), ("after-hours", "2")],
)
def test_vi_trigger_session_enum_literal(runner, fake_client, cli_value, api_value):
    """--session이 bf_mkrt_tp로 매핑되어야 한다 (리터럴 핀 — VOLUME_RANK_SESSION
    (ka10030)과 all/regular는 값이 같지만 after-hours만 다르다(거기는 "3"),
    극성 해저드)."""
    result = runner.invoke(cli, ["stock", "analysis", "vi-trigger", "--session", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["bf_mkrt_tp"] == api_value


def test_vi_trigger_session_after_hours_not_three(runner, fake_client):
    """--session after-hours는 bf_mkrt_tp="2"여야 한다 ("3"이 아님 —
    VOLUME_RANK_SESSION과 바꿔치기하면 "3"이 나가 이 테스트가 실패한다)."""
    result = runner.invoke(
        cli, ["stock", "analysis", "vi-trigger", "--session", "after-hours"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["bf_mkrt_tp"] == "2"
    assert fake_client.calls[0][1]["bf_mkrt_tp"] != "3"


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "0"), ("static", "1"), ("dynamic", "2"), ("both", "3")],
)
def test_vi_trigger_type_enum(runner, fake_client, cli_value, api_value):
    """--trigger-type이 motn_tp로 매핑되어야 한다."""
    result = runner.invoke(
        cli, ["stock", "analysis", "vi-trigger", "--trigger-type", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["motn_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", [("yes", "1"), ("no", "0")])
def test_vi_trigger_volume_type_enum(runner, fake_client, cli_value, api_value):
    """--volume-type yes/no가 trde_qty_tp 1/0로 매핑되어야 한다 (자유 텍스트
    -> enum 전환, breaking)."""
    result = runner.invoke(
        cli, ["stock", "analysis", "vi-trigger", "--volume-type", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_qty_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", [("yes", "1"), ("no", "0")])
def test_vi_trigger_amount_type_enum(runner, fake_client, cli_value, api_value):
    """--amount-type yes/no가 trde_prica_tp 1/0로 매핑되어야 한다 (자유 텍스트
    -> enum 전환, breaking)."""
    result = runner.invoke(
        cli, ["stock", "analysis", "vi-trigger", "--amount-type", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_prica_tp"] == api_value


@pytest.mark.parametrize(
    "cli_value,api_value", [("all", "0"), ("rise", "1"), ("fall", "2")]
)
def test_vi_trigger_direction_enum(runner, fake_client, cli_value, api_value):
    """--direction이 motn_drc로 매핑되어야 한다."""
    result = runner.invoke(cli, ["stock", "analysis", "vi-trigger", "--direction", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["motn_drc"] == api_value


# ── analysis warrant (ka10011) ───────────────────────────


def test_warrant_default_sends_all(runner, fake_client):
    """기본 호출은 종전과 동일하게 newstk_recvrht_tp="00"을 보내야 한다."""
    result = runner.invoke(cli, ["stock", "analysis", "warrant"])

    assert result.exit_code == 0
    assert fake_client.calls == [("ka10011", {"newstk_recvrht_tp": "00"})]


@pytest.mark.parametrize(
    "cli_value,api_value",
    [("all", "00"), ("warrant-security", "05"), ("warrant-certificate", "07")],
)
def test_warrant_type_enum(runner, fake_client, cli_value, api_value):
    """--type human 이름이 newstk_recvrht_tp로 매핑되어야 한다."""
    result = runner.invoke(cli, ["stock", "analysis", "warrant", "--type", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["newstk_recvrht_tp"] == api_value


# ── investor daily-trade (ka10044) ───────────────────────


def test_investor_daily_trade_default_sends_net_buy(runner, fake_client):
    """기본 호출은 종전과 동일하게 trde_tp="2"(순매수)를 보내야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "daily-trade", "--from", "20260101", "--to", "20260107"]
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10044",
            {
                "strt_dt": "20260101", "end_dt": "20260107", "trde_tp": "2",
                "mrkt_tp": "001", "stex_tp": "3",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("net-sell", "1"), ("net-buy", "2")])
def test_investor_daily_trade_trade_enum_literal(runner, fake_client, cli_value, api_value):
    """--trade net-sell/net-buy가 trde_tp 1/2로 매핑되어야 한다 (리터럴 핀 —
    BROKER_TOP_SIDE(net-buy:1,net-sell:2)와 극성이 정반대라 자기참조
    테스트로는 뒤바뀜을 못 잡는다)."""
    result = runner.invoke(
        cli, ["stock", "investor", "daily-trade", "--from", "20260101", "--to", "20260107",
              "--trade", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_value


def test_investor_daily_trade_rejects_net_trade(runner, fake_client):
    """INVESTOR_DAILY_TRADE_SIDE는 FOREIGN_PERIOD_SIDE(ka10034)의 진짜
    부분집합이다 — "net-trade"(3)는 저쪽에만 있으므로 거부돼야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "daily-trade", "--from", "20260101", "--to", "20260107",
              "--trade", "net-trade"]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


# ── investor stock-institution (ka10045) ─────────────────


def test_stock_institution_trend_default_sends_buy(runner, fake_client):
    """기본 호출은 종전과 동일하게 orgn_prsm_unp_tp="1", for_prsm_unp_tp="1"을
    보내야 한다."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "stock-institution", "005930",
            "--from", "20260101", "--to", "20260107",
        ],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10045",
            {
                "stk_cd": "005930", "strt_dt": "20260101", "end_dt": "20260107",
                "orgn_prsm_unp_tp": "1", "for_prsm_unp_tp": "1",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("buy", "1"), ("sell", "2")])
def test_stock_institution_trend_inst_price_enum_literal(
    runner, fake_client, cli_value, api_value
):
    """--inst-price buy/sell이 orgn_prsm_unp_tp 1/2로 매핑되어야 한다 (리터럴
    핀 — TRADE_SIDE(all:0,sell:1,buy:2)/FOREIGN_BROKER_SIDE(buy:3,sell:4)와
    키가 겹치지만 값이 다르다, 극성 해저드)."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "stock-institution", "005930",
            "--from", "20260101", "--to", "20260107", "--inst-price", cli_value,
        ],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["orgn_prsm_unp_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", [("buy", "1"), ("sell", "2")])
def test_stock_institution_trend_foreign_price_enum_literal(
    runner, fake_client, cli_value, api_value
):
    """--foreign-price buy/sell이 for_prsm_unp_tp 1/2로 매핑되어야 한다 (리터럴
    핀, INST_FOREIGN_PRICE_TYPE을 --inst-price와 공유)."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "stock-institution", "005930",
            "--from", "20260101", "--to", "20260107", "--foreign-price", cli_value,
        ],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["for_prsm_unp_tp"] == api_value


def test_stock_institution_trend_rejects_net_buy(runner, fake_client):
    """INST_FOREIGN_PRICE_TYPE(buy/sell)은 TRDE_TP_NET_BUY_BUY_SELL
    (net-buy/buy/sell)의 진짜 부분집합이다 — "net-buy"는 저쪽에만 있으므로
    거부돼야 한다."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "stock-institution", "005930",
            "--from", "20260101", "--to", "20260107", "--inst-price", "net-buy",
        ],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


# ── investor daily-by-investor (ka10058) ─────────────────


def test_daily_by_investor_default_body(runner, fake_client):
    """기본 호출 바디는 종전과 동일해야 한다 (trde_tp="2", invsr_tp="9000")."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "daily-by-investor", "--from", "20260101", "--to", "20260107"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10058",
            {
                "strt_dt": "20260101", "end_dt": "20260107", "trde_tp": "2",
                "mrkt_tp": "001", "invsr_tp": "9000", "stex_tp": "3",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("net-sell", "1"), ("net-buy", "2")])
def test_daily_by_investor_trade_enum_literal(runner, fake_client, cli_value, api_value):
    """--trade net-sell/net-buy가 trde_tp 1/2로 매핑되어야 한다 (리터럴 핀 —
    BROKER_TOP_SIDE와 극성이 정반대인 클러스터라 자기참조 테스트로는
    못 잡는다)."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "daily-by-investor",
            "--from", "20260101", "--to", "20260107", "--trade", cli_value,
        ],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_value


def test_daily_by_investor_trade_rejects_net_trade(runner, fake_client):
    """DAILY_BY_INVESTOR_TRADE_SIDE는 FOREIGN_PERIOD_SIDE(ka10034)의 진짜
    부분집합이다 — "net-trade"(3)는 저쪽에만 있으므로 거부돼야 한다."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "daily-by-investor",
            "--from", "20260101", "--to", "20260107", "--trade", "net-trade",
        ],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


@pytest.mark.parametrize(
    "cli_value,api_value",
    [
        ("individual", "8000"), ("foreign", "9000"), ("financial-investment", "1000"),
        ("investment-trust", "3000"), ("private-fund", "3100"), ("other-financial", "5000"),
        ("bank", "4000"), ("insurance", "2000"), ("pension", "6000"), ("state", "7000"),
        ("other-corporate", "7100"), ("institution", "9999"),
    ],
)
def test_daily_by_investor_type_enum(runner, fake_client, cli_value, api_value):
    """--investor-type의 human 이름 12종이 invsr_tp로 매핑되어야 한다 (자유
    텍스트 -> enum 전환, breaking)."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "daily-by-investor",
            "--from", "20260101", "--to", "20260107", "--investor-type", cli_value,
        ],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["invsr_tp"] == api_value


def test_daily_by_investor_type_default_unchanged(runner, fake_client):
    """--investor-type 기본 호출은 변경 전과 동일하게 invsr_tp="9000"을
    보내야 한다."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "daily-by-investor", "--from", "20260101", "--to", "20260107"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["invsr_tp"] == "9000"


def test_daily_by_investor_type_rejects_name_absent_from_ka10058(runner, fake_client):
    """"foreign-broker"는 market.py의 INVESTOR_TOP_ORGN(ka10065)에만 있고
    DAILY_BY_INVESTOR_TYPE(ka10058)엔 없다. 두 상수는 10개 키의 값이
    character-for-character 동일하지만(individual/private-fund는 ka10058
    전용, foreign-broker는 ka10065 전용) 어느 쪽도 다른 쪽의 진짜
    부분집합이 아니다 — superset-closure 스크립트의 부분집합 predicate가
    양방향 모두 이 쌍에서 fire하지 않는다(부분 겹침, 해저드 3유형).
    값 겹침에만 의존한 병합 리팩터는 이 테스트로만 잡힌다."""
    result = runner.invoke(
        cli,
        [
            "stock", "investor", "daily-by-investor",
            "--from", "20260101", "--to", "20260107", "--investor-type", "foreign-broker",
        ],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


# ── investor by-stock (ka10059) / by-stock-total (ka10061) ──


def test_by_stock_default_body(runner, fake_client):
    """기본 호출 바디는 종전과 동일해야 한다 (amt_qty_tp="1", trde_tp="0",
    unit_tp="1")."""
    result = runner.invoke(cli, ["stock", "investor", "by-stock", "005930", "--date", "20260101"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10059",
            {
                "dt": "20260101", "stk_cd": "005930", "amt_qty_tp": "1",
                "trde_tp": "0", "unit_tp": "1",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("amount", "1"), ("quantity", "2")])
def test_by_stock_amount_qty_enum(runner, fake_client, cli_value, api_value):
    """--amount-qty가 amt_qty_tp로 매핑되어야 한다 (AMT_QTY_TP_1_2 공유, 이번
    태스크에서 ka10059로 확장)."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "by-stock", "005930", "--date", "20260101",
         "--amount-qty", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


@pytest.mark.parametrize(
    "cli_value,api_value", [("net-buy", "0"), ("buy", "1"), ("sell", "2")]
)
def test_by_stock_trade_enum(runner, fake_client, cli_value, api_value):
    """--trade가 trde_tp로 매핑되어야 한다 (TRDE_TP_NET_BUY_BUY_SELL 공유,
    이번 태스크에서 ka10059로 확장)."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "by-stock", "005930", "--date", "20260101",
         "--trade", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", [("thousand", "1000"), ("share", "1")])
def test_by_stock_unit_enum(runner, fake_client, cli_value, api_value):
    """--unit thousand/share가 unit_tp 1000/1로 매핑되어야 한다."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "by-stock", "005930", "--date", "20260101",
         "--unit", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["unit_tp"] == api_value


def test_by_stock_total_default_body(runner, fake_client):
    """기본 호출 바디는 종전과 동일해야 한다 (amt_qty_tp="1", trde_tp="0",
    unit_tp="1")."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "by-stock-total", "005930",
         "--from", "20260101", "--to", "20260107"],
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10061",
            {
                "stk_cd": "005930", "strt_dt": "20260101", "end_dt": "20260107",
                "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("amount", "1"), ("quantity", "2")])
def test_by_stock_total_amount_qty_enum(runner, fake_client, cli_value, api_value):
    """--amount-qty가 amt_qty_tp로 매핑되어야 한다 (AMT_QTY_TP_1_2 공유,
    이번 태스크에서 ka10061로 확장)."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "by-stock-total", "005930",
         "--from", "20260101", "--to", "20260107", "--amount-qty", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


def test_by_stock_total_trade_default_sends_net_buy(runner, fake_client):
    """--trade 기본 호출은 변경 전과 동일하게 trde_tp="0"을 보내야 한다."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "by-stock-total", "005930",
         "--from", "20260101", "--to", "20260107"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == "0"


def test_by_stock_total_trade_rejects_buy_and_sell(runner, fake_client):
    """ka10061 스펙의 trde_tp는 "0:순매수" 단일값뿐이다. 이전 코드는
    click.Choice(["0","1","2"])로 스펙에 없는 1/2까지 받고 있었는데,
    HumanChoice({"net-buy":"0"})로 좁히면서 그 두 값이 거부된다(breaking,
    이미 click.Choice였던 자리의 값 집합 축소)."""
    for raw in ("1", "2"):
        result = runner.invoke(
            cli,
            ["stock", "investor", "by-stock-total", "005930",
             "--from", "20260101", "--to", "20260107", "--trade", raw],
        )
        assert result.exit_code == 1
        assert fake_client.calls == []


@pytest.mark.parametrize("cli_value,api_value", [("thousand", "1000"), ("share", "1")])
def test_by_stock_total_unit_enum(runner, fake_client, cli_value, api_value):
    """--unit thousand/share가 unit_tp 1000/1로 매핑되어야 한다 (INVESTOR_BY_STOCK_UNIT
    공유, ka10059/ka10061)."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "by-stock-total", "005930",
         "--from", "20260101", "--to", "20260107", "--unit", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["unit_tp"] == api_value


# ============================================================
#  Task 34b — investor program-top (ka90003)
# ============================================================


def test_program_top_default_unchanged_body(runner, fake_client):
    """기본 호출은 종전과 동일하게 trde_upper_tp="2", amt_qty_tp="1",
    mrkt_tp="P00101"(코스피), stex_tp="3"(all)을 보내야 한다."""
    result = runner.invoke(cli, ["stock", "investor", "program-top"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka90003",
            {
                "trde_upper_tp": "2",
                "amt_qty_tp": "1",
                "mrkt_tp": "P00101",
                "stex_tp": "3",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("net-sell", "1"), ("net-buy", "2")])
def test_program_top_trade_enum_literal(runner, fake_client, cli_value, api_value):
    """--trade net-sell/net-buy가 trde_upper_tp 1/2로 매핑되어야 한다 (리터럴 핀 —
    PROGRAM_TOP_SIDE는 ELW_BROKER_SIDE(net-buy:1,net-sell:2)와 키가 같고 극성이
    반대다, 폴백으로 상수가 바꿔치기되면 이 테스트가 실패한다)."""
    result = runner.invoke(
        cli, ["stock", "investor", "program-top", "--trade", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_upper_tp"] == api_value


def test_program_top_trade_rejects_net_trade(runner, fake_client):
    """PROGRAM_TOP_SIDE({net-sell:1,net-buy:2})는 FOREIGN_PERIOD_SIDE
    ({net-sell:1,net-buy:2,net-trade:3})의 진짜 부분집합이다(클로저 스크립트로
    확인) — "net-trade"는 저쪽에만 있으므로 거부돼야 한다."""
    result = runner.invoke(
        cli, ["stock", "investor", "program-top", "--trade", "net-trade"]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


@pytest.mark.parametrize("cli_value,api_value", [("amount", "1"), ("quantity", "2")])
def test_program_top_amount_qty_enum_literal(runner, fake_client, cli_value, api_value):
    """--amount-qty amount/quantity가 amt_qty_tp 1/2로 매핑되어야 한다 (리터럴 핀 —
    AMT_QTY_TP_1_2는 AMT_QTY_TP_0_1/SAME_NET_TRADE_SORT/DAILY_PRICE_DISPLAY와
    키가 같고 극성이 다르다)."""
    result = runner.invoke(
        cli, ["stock", "investor", "program-top", "--amount-qty", cli_value]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


def test_program_top_market_and_exchange_unchanged(runner, fake_client):
    """--market/--exchange는 이번 태스크 범위 밖 — 그대로 동작해야 한다."""
    result = runner.invoke(
        cli,
        ["stock", "investor", "program-top", "--market", "kosdaq", "--exchange", "KRX"],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["mrkt_tp"] == "P10102"
    assert fake_client.calls[0][1]["stex_tp"] == "1"


# ============================================================
#  Task 34b — chart tick/minute/day/week/month/year (--adjusted)
# ============================================================

_CHART_ADJUSTED_COMMANDS = [
    ("tick", ["stock", "chart", "tick", "005930"]),
    ("minute", ["stock", "chart", "minute", "005930"]),
    ("day", ["stock", "chart", "day", "005930", "--base-date", "20260101"]),
    ("week", ["stock", "chart", "week", "005930", "--base-date", "20260101"]),
    ("month", ["stock", "chart", "month", "005930", "--base-date", "20260101"]),
    ("year", ["stock", "chart", "year", "005930", "--base-date", "20260101"]),
]


@pytest.mark.parametrize("name,args", _CHART_ADJUSTED_COMMANDS)
def test_chart_adjusted_default_unchanged(runner, fake_client, name, args):
    """--adjusted 기본 호출은 종전과 동일하게 upd_stkpc_tp="0"을 보내야 한다."""
    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["upd_stkpc_tp"] == "0"


@pytest.mark.parametrize("name,args", _CHART_ADJUSTED_COMMANDS)
@pytest.mark.parametrize("cli_value,api_value", [("raw", "0"), ("adjusted", "1")])
def test_chart_adjusted_enum_literal(
    runner, fake_client, name, args, cli_value, api_value
):
    """--adjusted raw/adjusted가 upd_stkpc_tp 0/1로 매핑되어야 한다 (리터럴 핀,
    CHART_ADJUSTED_PRICE는 6개 api_id가 공유하고 GOLD_PRICE_TYPE과 값이
    완전히 동일한 구분 불가 클러스터라 이 테스트로도 그 둘의 치환은 못 잡는다
    — 이름 규약이 유일한 방어선)."""
    result = runner.invoke(cli, [*args, "--adjusted", cli_value])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["upd_stkpc_tp"] == api_value


def test_chart_tick_adjusted_rejects_out_of_spec_value(runner, fake_client):
    """CHART_ADJUSTED_PRICE는 0/1 두 값뿐이라 다른 값은 exit 1이어야 한다."""
    result = runner.invoke(
        cli, ["stock", "chart", "tick", "005930", "--adjusted", "2"]
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


# ============================================================
#  Task 34b — chart investor (ka10060)
# ============================================================


def test_chart_investor_default_unchanged_body(runner, fake_client):
    """기본 호출은 종전과 동일하게 amt_qty_tp="1", trde_tp="0", unit_tp="1"을
    보내야 한다."""
    result = runner.invoke(
        cli, ["stock", "chart", "investor", "005930", "--date", "20260101"]
    )

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10060",
            {
                "dt": "20260101",
                "stk_cd": "005930",
                "amt_qty_tp": "1",
                "trde_tp": "0",
                "unit_tp": "1",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("amount", "1"), ("quantity", "2")])
def test_chart_investor_amount_qty_enum_literal(runner, fake_client, cli_value, api_value):
    """--amount-qty amount/quantity가 amt_qty_tp 1/2로 매핑되어야 한다 (리터럴 핀)."""
    result = runner.invoke(
        cli,
        ["stock", "chart", "investor", "005930", "--date", "20260101",
         "--amount-qty", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


@pytest.mark.parametrize(
    "cli_value,api_value", [("net-buy", "0"), ("buy", "1"), ("sell", "2")]
)
def test_chart_investor_trade_enum_literal(runner, fake_client, cli_value, api_value):
    """--trade net-buy/buy/sell이 trde_tp 0/1/2로 매핑되어야 한다 (리터럴 핀)."""
    result = runner.invoke(
        cli,
        ["stock", "chart", "investor", "005930", "--date", "20260101",
         "--trade", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_value


@pytest.mark.parametrize("cli_value,api_value", [("thousand", "1000"), ("share", "1")])
def test_chart_investor_unit_enum_literal(runner, fake_client, cli_value, api_value):
    """--unit thousand/share가 unit_tp 1000/1로 매핑되어야 한다 (리터럴 핀,
    INVESTOR_BY_STOCK_UNIT 공유 — ka10059/ka10061/ka10060 3곳)."""
    result = runner.invoke(
        cli,
        ["stock", "chart", "investor", "005930", "--date", "20260101",
         "--unit", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["unit_tp"] == api_value


def test_chart_investor_trade_rejects_out_of_spec_value(runner, fake_client):
    """TRDE_TP_NET_BUY_BUY_SELL은 0/1/2 세 값뿐이라 다른 값은 exit 1이어야 한다."""
    result = runner.invoke(
        cli,
        ["stock", "chart", "investor", "005930", "--date", "20260101",
         "--trade", "3"],
    )

    assert result.exit_code == 1
    assert fake_client.calls == []


# ============================================================
#  Task 34b — chart intraday-investor (ka10064)
# ============================================================


def test_chart_intraday_investor_default_unchanged_body(runner, fake_client):
    """기본 호출은 종전과 동일하게 mrkt_tp="001", amt_qty_tp="1", trde_tp="0"을
    보내야 한다."""
    result = runner.invoke(cli, ["stock", "chart", "intraday-investor", "005930"])

    assert result.exit_code == 0
    assert fake_client.calls == [
        (
            "ka10064",
            {
                "mrkt_tp": "001",
                "amt_qty_tp": "1",
                "trde_tp": "0",
                "stk_cd": "005930",
            },
        )
    ]


@pytest.mark.parametrize("cli_value,api_value", [("amount", "1"), ("quantity", "2")])
def test_chart_intraday_investor_amount_qty_enum_literal(
    runner, fake_client, cli_value, api_value
):
    """--amount-qty amount/quantity가 amt_qty_tp 1/2로 매핑되어야 한다 (리터럴 핀)."""
    result = runner.invoke(
        cli,
        ["stock", "chart", "intraday-investor", "005930", "--amount-qty", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["amt_qty_tp"] == api_value


@pytest.mark.parametrize(
    "cli_value,api_value", [("net-buy", "0"), ("buy", "1"), ("sell", "2")]
)
def test_chart_intraday_investor_trade_enum_literal(
    runner, fake_client, cli_value, api_value
):
    """--trade net-buy/buy/sell이 trde_tp 0/1/2로 매핑되어야 한다 (리터럴 핀)."""
    result = runner.invoke(
        cli,
        ["stock", "chart", "intraday-investor", "005930", "--trade", cli_value],
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["trde_tp"] == api_value


# ============================================================
#  Task 34b — lending trend/by-stock (--all, 미확인 — raw 텍스트 유지)
# ============================================================


def test_lending_trend_all_still_accepts_arbitrary_text(runner, fake_client):
    """ka10068의 all_tp는 스펙에 "1:전체표시" 하나만 문서화돼 있어(반대값 불명)
    이번 태스크에서 HumanChoice로 좁히지 않았다 — 자유 텍스트는 계속 그대로
    전송돼야 한다(breaking 아님을 확인)."""
    result = runner.invoke(cli, ["stock", "lending", "trend", "--all", "9"])

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["all_tp"] == "9"


def test_lending_by_stock_all_still_accepts_arbitrary_text(runner, fake_client):
    """ka20068의 all_tp도 마찬가지로 자유 텍스트로 남겨 뒀다(스펙에 "0:종목코드
    입력종목만" 하나만 문서화, 반대값 불명)."""
    result = runner.invoke(
        cli, ["stock", "lending", "by-stock", "005930", "--all", "9"]
    )

    assert result.exit_code == 0
    assert fake_client.calls[0][1]["all_tp"] == "9"
