"""Tier-3 human-UX regression tests (price formatting, --no-color, truncation, discovery, human options)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.client import KiwoomAPIError  # noqa: F401  (used from Task 8 on)
from kiwoom_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """config를 tmp로 격리하고 프로필/도메인 env를 제거한다."""
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


def _mock_kiwoom_client(request_fn):
    """conventions 패턴: context-manager를 지원하는 KiwoomClient MagicMock."""
    mc = MagicMock()
    mc.request = request_fn
    mc.__enter__ = lambda s: s
    mc.__exit__ = MagicMock(return_value=False)
    return mc


def _doc(result):
    """stdout에서 envelope 문서 파싱 (stderr 혼입 방지를 위해 stdout 사용)."""
    return json.loads(result.stdout)


# ── Task 1: stock price ──────────────────────────────────

_PRICE_RESPONSE = {
    "stk_nm": "삼성전자", "cur_prc": "-70000", "pred_pre": "-1000",
    "flu_rt": "-1.41", "return_code": 0,
}


def _price_client():
    def fake(api_id, body=None, **kwargs):
        return dict(_PRICE_RESPONSE), {}
    return _mock_kiwoom_client(fake)


def test_stock_price_table_strips_direction_sign(runner, isolated_env):
    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _price_client()
        result = runner.invoke(cli, ["stock", "price", "005930"])
    assert result.exit_code == 0
    assert "-70,000" not in result.output          # 방향지시자 부호 제거
    assert "70,000원" in result.output
    assert "-1,000" in result.output               # 전일대비는 부호 유지


def test_stock_price_json_emits_envelope(runner, isolated_env):
    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _price_client()
        result = runner.invoke(cli, ["-f", "json", "stock", "price", "005930"])
    assert result.exit_code == 0
    doc = _doc(result)
    assert doc["ok"] is True and doc["schema"] == "v1"
    assert doc["data"]["raw"]["cur_prc"] == "-70000"


# ── Task 2: --no-color ───────────────────────────────────

@pytest.fixture
def reset_no_color():
    yield
    from kiwoom_cli import output
    output.console.no_color = False
    output.err_console.no_color = False


def test_no_color_mutates_shared_console_instances(runner, isolated_env, reset_no_color):
    from kiwoom_cli import output
    from kiwoom_cli.formatters import console as fmt_console
    before_out, before_err = output.console, output.err_console
    assert fmt_console is before_out       # import-time 바인딩이 같은 객체를 봐야 함
    result = runner.invoke(cli, ["--no-color", "describe", "--paths"])
    assert result.exit_code == 0
    assert output.console is before_out and output.err_console is before_err
    assert output.console.no_color is True
    assert output.err_console.no_color is True
    assert fmt_console.no_color is True    # 실제 회귀: 재바인딩은 이 단언에서 실패


# ── Task 3: truncation notice ────────────────────────────

def test_generic_table_truncation_notice(capsys):
    from kiwoom_cli.formatters import print_generic_table
    rows = [{"stk_cd": f"{i:06d}"} for i in range(60)]
    print_generic_table(rows, title="t")
    out = capsys.readouterr().out
    assert "60행 중 50행 표시" in out


def test_generic_table_no_notice_at_cap(capsys):
    from kiwoom_cli.formatters import print_generic_table
    rows = [{"stk_cd": f"{i:06d}"} for i in range(50)]
    print_generic_table(rows, title="t")
    assert "행 표시" not in capsys.readouterr().out


def test_chart_truncation_notice(capsys):
    from kiwoom_cli.formatters import print_chart_data
    items = [{"dt": f"202601{i:02d}", "open_pric": "1"} for i in range(1, 41)]
    print_chart_data(items, title="t")
    assert "40행 중 30행 표시" in capsys.readouterr().out


# ── Task 4: kiwoom find ──────────────────────────────────

def test_find_matches_commands_and_apis(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "find", "미체결"])
    assert result.exit_code == 0
    doc = _doc(result)
    paths = [r["path"] for r in doc["data"]["commands"]]
    assert "kiwoom account orders pending" in paths
    api_ids = [r["api_id"] for r in doc["data"]["apis"]]
    assert "ka10075" in api_ids


def test_find_case_insensitive_on_paths(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "find", "BALANCE"])
    doc = _doc(result)
    assert any("balance" in r["path"] for r in doc["data"]["commands"])


def test_find_no_results_exits_0(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "find", "zzz-nope"])
    assert result.exit_code == 0
    assert _doc(result)["data"] == {"commands": [], "apis": []}


def test_find_table_output(runner, isolated_env):
    result = runner.invoke(cli, ["find", "미체결"])
    assert result.exit_code == 0
    assert "ka10075" in result.output
    assert "account orders pending" in result.output


def test_find_markup_in_keyword_does_not_crash(runner, isolated_env):
    result = runner.invoke(cli, ["find", "[/]"])
    assert result.exit_code == 0
    assert "결과가 없습니다" in result.output


# ── Task 5: kiwoom api list ──────────────────────────────

def test_api_list_all(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "api", "list"])
    assert result.exit_code == 0
    rows = _doc(result)["data"]
    assert len(rows) >= 217
    assert {"api_id": "ka10001", "url_path": "/api/dostk/stkinfo",
            "description": "주식기본정보요청"} in rows


def test_api_list_keyword_filter(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "api", "list", "미체결"])
    assert result.exit_code == 0
    ids = [r["api_id"] for r in _doc(result)["data"]]
    assert "ka10075" in ids
    assert "ka10001" not in ids


def test_api_list_needs_no_auth(runner, isolated_env):
    # 토큰 없는 격리 환경에서도 성공해야 한다 (KiwoomClient 미사용 경로)
    result = runner.invoke(cli, ["api", "list", "미체결"])
    assert result.exit_code == 0
    assert "ka10075" in result.output


# ── Task 6: human-readable option values ─────────────────

def _capture_client(captured):
    def fake(api_id, body=None, **kwargs):
        captured.setdefault("calls", []).append((api_id, body))
        return {"return_code": 0}, {}
    return _mock_kiwoom_client(fake)


def test_human_option_converts_to_api_code(runner, isolated_env):
    captured = {}
    with patch("kiwoom_cli.commands.account.KiwoomClient") as mock_cls:
        mock_cls.return_value = _capture_client(captured)
        result = runner.invoke(cli, ["-f", "json", "account", "orders", "pending",
                                     "--market", "kr", "--trade", "sell"])
    assert result.exit_code == 0
    api_id, body = captured["calls"][0]
    assert api_id == "ka10075"
    assert body["trde_tp"] == "1"


def test_human_option_accepts_legacy_numeric_code(runner, isolated_env):
    captured = {}
    with patch("kiwoom_cli.commands.account.KiwoomClient") as mock_cls:
        mock_cls.return_value = _capture_client(captured)
        result = runner.invoke(cli, ["-f", "json", "account", "orders", "pending",
                                     "--market", "kr", "--trade", "1"])
    assert result.exit_code == 0
    assert captured["calls"][0][1]["trde_tp"] == "1"


def test_human_option_default_converts(runner, isolated_env):
    captured = {}
    with patch("kiwoom_cli.commands.account.KiwoomClient") as mock_cls:
        mock_cls.return_value = _capture_client(captured)
        result = runner.invoke(cli, ["-f", "json", "account", "orders", "pending",
                                     "--market", "kr"])
    assert result.exit_code == 0
    assert captured["calls"][0][1]["trde_tp"] == "0"


def test_human_option_invalid_value_lists_human_names(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "account", "orders", "pending",
                                 "--trade", "9"])
    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["error"]["code"] == "INVALID_INPUT"
    assert "sell" in doc["error"]["message"]


def test_describe_shows_human_choices(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "describe", "account", "orders", "pending"])
    doc = _doc(result)
    opt = next(o for o in doc["data"]["options"] if o["name"] == "trde_tp")
    assert opt["choices"] == ["all", "sell", "buy"]
    assert opt["default"] == "all"


def test_market_rank_hot_period_human(runner, isolated_env):
    captured = {}
    with patch("kiwoom_cli.commands.market.KiwoomClient") as mock_cls:
        mock_cls.return_value = _capture_client(captured)
        result = runner.invoke(cli, ["-f", "json", "market", "rank", "hot",
                                     "--period", "1h"])
    assert result.exit_code == 0
    assert captured["calls"][0][1]["qry_tp"] == "3"


def test_history_transactions_human_deposit_still_kr_only(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "account", "history", "transactions",
                                 "--market", "us", "--from", "20260101",
                                 "--to", "20260131", "--type", "deposit"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


@pytest.mark.parametrize("mapping_name", [
    "DELIST_QRY", "TRADE_SIDE", "ALL_STOCK_QRY", "ORDER_DETAIL_QRY",
    "ASSET_TYPE", "MARKET_STATUS_KOSPI", "FILLED_QRY", "HOLDINGS_EVAL_QRY",
    "TRANSACTION_TYPE", "PRODUCT_TYPE", "ODD_LOT_QRY", "CASH_CREDIT", "HOT_PERIOD",
    "STOCK_CONDITION", "MANAGED_STOCK_INCLUDE", "VOLUME_RANK_SORT",
    "VOLUME_RANK_CREDIT_TYPE", "VOLUME_RANK_QTY_TYPE", "VOLUME_RANK_PRICE_TYPE",
    "VOLUME_RANK_AMOUNT_TYPE", "VOLUME_RANK_SESSION", "BROKER_BY_STOCK_SIDE",
    "PERIOD_DAYS_OFF_BY_ONE", "ELW_BROKER_QTY_TYPE", "ELW_BROKER_SIDE",
    "ELW_BROKER_PERIOD",
    "TRADER_ANALYSIS_DATE_MODE", "TRADER_ANALYSIS_POSITION",
    "TRADER_ANALYSIS_SORT",
    # 아래 13개는 HumanChoice 데코레이터에 실제로 물려 있는데도 이 목록에
    # 빠져 있었다. GOLD_ORDER_TYPES는 금현물 주문 경로다.
    "GOLD_ORDER_TYPES", "CREDIT_MARKET", "CREDIT_GRADE",
    "AMT_QTY_TP_0_1", "AMT_QTY_TP_1_2", "AMT_QTY_TP_COMBINED",
    "INTRADAY_INVESTOR", "MIN_TIC_TP", "CHECK_YES_1_NO_0",
    "NETSLMT_TP_NET_BUY_ONLY", "PERIOD_RECENT_OR_RANGE",
    "STK_INDS_TP", "TRDE_TP_NET_BUY_BUY_SELL",
    # Task 31a — market rank ka10016~ka10023 HumanChoice 전환.
    "NEW_HIGH_LOW_KIND", "NEW_HIGH_LOW_BASIS", "NEW_HIGH_LOW_STK_CND",
    "NEW_HIGH_LOW_CREDIT_CND", "NEW_HIGH_LOW_INCLUDE_LIMIT",
    "LIMIT_MOVE_DIRECTION", "LIMIT_MOVE_SORT", "LIMIT_MOVE_STK_CND",
    "LIMIT_MOVE_CREDIT_CND", "LIMIT_MOVE_PRICE_CND",
    "NEAR_HIGHLOW_KIND", "NEAR_HIGHLOW_STK_CND", "NEAR_HIGHLOW_CREDIT_CND",
    "SURGE_DIRECTION", "SURGE_TIME_UNIT", "SURGE_STK_CND",
    "SURGE_CREDIT_CND", "SURGE_PRICE_CND", "SURGE_INCLUDE_LIMIT",
    "ORDERBOOK_TOP_SORT", "ORDERBOOK_TOP_STK_CND", "ORDERBOOK_TOP_CREDIT_CND",
    "ORDERBOOK_SURGE_SIDE", "ORDERBOOK_SURGE_SORT", "ORDERBOOK_SURGE_STK_CND",
    "BALANCE_RATE_TYPE", "BALANCE_RATE_STK_CND",
    "VOLUME_SURGE_SORT", "VOLUME_SURGE_TIME_UNIT", "VOLUME_SURGE_STK_CND",
    "VOLUME_SURGE_PRICE_TYPE",
    # Task 31a-fix — trde_qty_tp(--vol-type) 8개 코드북. 자릿수가 서로 달라
    # (5자리/4자리/무패딩) 이름에 형식을 박아 뒀다. 절대 합치지 말 것.
    "NEW_HIGH_LOW_QTY_TYPE_5DIGIT", "LIMIT_MOVE_QTY_TYPE_5DIGIT",
    "NEAR_HIGHLOW_QTY_TYPE_5DIGIT", "SURGE_QTY_TYPE_5DIGIT",
    "ORDERBOOK_TOP_QTY_TYPE_4DIGIT", "ORDERBOOK_SURGE_QTY_TYPE_BARE",
    "BALANCE_RATE_QTY_TYPE_BARE", "VOLUME_SURGE_QTY_TYPE_BARE",
    # Task 31b — market rank ka10027~ka10039 HumanChoice 전환. ka10030/32/38
    # 은 Tranche B에서 이미 전환돼 이 목록에 없다(위 STOCK_CONDITION 등 참고).
    "RANK_CHANGE_SORT", "RANK_CHANGE_QTY_CND", "RANK_CHANGE_STK_CND",
    "RANK_CHANGE_CREDIT_CND", "RANK_CHANGE_INCLUDE_LIMIT", "RANK_CHANGE_PRICE_CND",
    "RANK_CHANGE_AMOUNT_CND",
    "EXPECTED_CHANGE_SORT", "EXPECTED_CHANGE_QTY_CND", "EXPECTED_CHANGE_STK_CND",
    "EXPECTED_CHANGE_CREDIT_CND", "EXPECTED_CHANGE_PRICE_CND",
    "PREV_VOLUME_KIND",
    "CREDIT_RATIO_QTY_TYPE", "CREDIT_RATIO_STK_CND",
    "CREDIT_RATIO_INCLUDE_LIMIT", "CREDIT_RATIO_CREDIT_CND",
    "PERIOD_TODAY_PREV_5_60", "FOREIGN_PERIOD_SIDE",
    "FOREIGN_CONSECUTIVE_SIDE", "FOREIGN_CONSECUTIVE_BASE_DATE",
    "FOREIGN_BROKER_SIDE", "FOREIGN_BROKER_SORT",
    "BROKER_TOP_QTY_TYPE", "BROKER_TOP_SIDE", "BROKER_TOP_PERIOD",
    # Task 31c — market rank ka10042/ka10062/ka10065/ka10098/ka90009
    # HumanChoice 전환. ka10042는 새 상수 없이 TRADER_ANALYSIS_DATE_MODE/
    # TRADER_ANALYSIS_POSITION/TRADER_ANALYSIS_SORT(위 목록에 이미 있음,
    # ka10043과 공유)를 재사용해 이 목록에 새로 추가하지 않았다.
    "SAME_NET_TRADE_SIDE", "SAME_NET_TRADE_SORT", "SAME_NET_TRADE_UNIT",
    "INVESTOR_TOP_SIDE", "INVESTOR_TOP_ORGN",
    "AFTERHOURS_CHANGE_SORT", "AFTERHOURS_CHANGE_STK_CND",
    "AFTERHOURS_CHANGE_QTY_CND", "AFTERHOURS_CHANGE_CREDIT_CND",
    "AFTERHOURS_CHANGE_AMOUNT_CND", "FOREIGN_INST_DATE_INCLUDE",
    # Task 32 — market sector·theme (ka10051/ka20001/ka20002/ka20009/
    # ka10101/ka90001) HumanChoice 전환. AMT_QTY_TP_0_1은 위 목록에 이미
    # 있음(ka10131과 공유, ka10051이 이번에 이관돼도 새로 추가하지 않음).
    "SECTOR_PRICE_MARKET", "SECTOR_CODES_MARKET",
    "THEME_LOOKUP_KIND", "THEME_LOOKUP_SORT",
    # Task 33 — market etf·elw·gold·program (ka40001/ka40004/ka30001/
    # ka30004/ka30005/ka30009/ka30010/ka50079/ka50081/ka50082/ka50083/
    # ka90007/ka90008) HumanChoice 전환. AMT_QTY_TP_1_2는 위 목록에 이미
    # 있음(ka90007/ka90008이 이번에 이관돼도 새로 추가하지 않음).
    # ELW_BROKER_END_SKIP은 EXCLUDE_ENDED_ELW로 이름이 바뀌어 5개 api_id
    # (ka30001/ka30002/ka30004/ka30009/ka30010) 공유 상수가 됐다.
    "ETF_RETURNS_PERIOD", "ETF_ALL_TAX_TYPE", "ETF_ALL_NAV", "ETF_ALL_TAXABLE",
    "ELW_SURGE_DIRECTION", "ELW_SURGE_TIME_UNIT", "ELW_SURGE_QTY_TYPE",
    "ELW_RIGHT_TYPE_3DIGIT", "ELW_RIGHT_TYPE_1DIGIT", "ELW_SEARCH_SORT",
    "ELW_CHANGE_RANK_SORT", "ELW_RANK_RIGHT_TYPE_3DIGIT", "ELW_BALANCE_RANK_SORT",
    "EXCLUDE_ENDED_ELW", "GOLD_PRICE_TYPE",
    # Task 34a — stock 일별주가~투자자별매매(daily_price~by_stock_total)
    # HumanChoice 전환. TRADER_ANALYSIS_PERIOD_5_120은 위 목록에서 제거됐다
    # (I2 규칙 재적용으로 --days가 raw 텍스트로 되돌아가 더 이상 쓰이지 않음).
    "DAILY_PRICE_DISPLAY", "TODAY_PREV_1_2", "TODAY_EXEC_TIC_MIN",
    "PRICE_CLUSTER_CUR_PRC_ENTRY",
    "OPEN_CHANGE_SORT", "OPEN_CHANGE_QTY_CND", "OPEN_CHANGE_INCLUDE_LIMIT",
    "OPEN_CHANGE_STK_CND", "OPEN_CHANGE_CREDIT_CND", "OPEN_CHANGE_AMOUNT_CND",
    "OPEN_CHANGE_DIRECTION",
    "INSTANT_VOLUME_MARKET", "INSTANT_VOLUME_PRICE_TYPE",
    "VI_TRIGGER_SESSION", "VI_TRIGGER_TYPE", "VI_TRIGGER_USE_FILTER",
    "VI_TRIGGER_DIRECTION",
    "WARRANT_TYPE",
    "INVESTOR_DAILY_TRADE_SIDE", "INST_FOREIGN_PRICE_TYPE",
    "DAILY_BY_INVESTOR_TRADE_SIDE", "DAILY_BY_INVESTOR_TYPE",
    "INVESTOR_BY_STOCK_UNIT", "BY_STOCK_TOTAL_TRADE_SIDE",
    # AMT_QTY_TP_1_2/TRDE_TP_NET_BUY_BUY_SELL은 위 목록에 이미 있음(ka10059/
    # ka10061이 이번에 이관돼도 새로 추가하지 않음, 커플링 주석 참고).
    # Task 34b — stock program_top/chart_*/lending HumanChoice 전환.
    # AMT_QTY_TP_1_2/TRDE_TP_NET_BUY_BUY_SELL/INVESTOR_BY_STOCK_UNIT은 위
    # 목록에 이미 있음(ka90003/ka10060/ka10064가 이번에 이관돼도 새로
    # 추가하지 않음, 각 상수 정의부 커플링 주석 참고). lending_trend/
    # lending_by_stock의 --all(all_tp)은 스펙에 값이 하나뿐이라(반대쪽
    # 불명) 미확인으로 전환하지 않았다 — raw 텍스트로 남아 있다.
    "PROGRAM_TOP_SIDE", "CHART_ADJUSTED_PRICE",
])
def test_every_mapping_converts_all_human_names(mapping_name):
    from kiwoom_cli.commands import _constants
    mapping = getattr(_constants, mapping_name)
    hc = _constants.HumanChoice(mapping)
    for human, code in mapping.items():
        assert hc.convert(human, None, None) == code    # human 이름 → 코드
        assert hc.convert(code, None, None) == code     # 원시 코드 하위호환


def test_all_converted_decorators_use_human_choice(runner, isolated_env):
    """전환 옵션이 전부 HumanChoice로 남아있는지 데코레이터 레벨에서 고정.

    루트(`cli`)부터 전체 트리를 훑는다. 예전에는 account/market/stock만
    손으로 나열해 order 그룹이 통째로 빠져 있었고, 그 바람에 금현물 주문의
    `--order-type`(GOLD_ORDER_TYPES) 2개가 집계에서 누락됐다. 그룹을
    새로 추가해도 자동으로 잡히도록 루트에서 내려간다.
    """
    import click
    from kiwoom_cli.commands import _constants
    from kiwoom_cli.main import cli as root_cli

    def _iter_options(cmd, path=()):
        here = path + (cmd.name,)
        yield from ((here, p) for p in cmd.params if isinstance(p, click.Option))
        if isinstance(cmd, click.Group):
            for sub in cmd.commands.values():
                yield from _iter_options(sub, here)

    converted = [
        (" ".join(path), p.name)
        for path, p in _iter_options(root_cli)
        if isinstance(p.type, _constants.HumanChoice)
    ]
    # 202 = 170(Task 33까지의 누적치, 아래 옛 주석 참고) + Task 34a(stock
    # daily-price~by-stock-total, ka10086/84/55/24(제외)/25/28/43/52/54/11/
    # 44/45/58/59/61)의 순증 31 + Task 34a 리뷰(trader-analysis --days
    # 원복 + net-buyer --period 전환)의 순증 1 = daily-price 1[indc_tp] +
    # today-exec 2[tdy_pred/tic_min] + today-volume 1[tdy_pred] +
    # price-cluster 1[cur_prc_entry] + open-change 7[sort_tp/trde_qty_cnd/
    # updown_incls/stk_cnd/crd_cnd/trde_prica_cnd/flu_cnd] + instant-volume
    # 2[mrkt_tp/pric_tp] + vi-trigger 5[bf_mkrt_tp/motn_tp/trde_qty_tp/
    # trde_prica_tp/motn_drc] + warrant 1[newstk_recvrht_tp] + daily-trade
    # 1[trde_tp] + stock-institution 2[orgn_prsm_unp_tp/for_prsm_unp_tp] +
    # daily-by-investor 2[trde_tp/invsr_tp] + by-stock 3[amt_qty_tp/trde_tp/
    # unit_tp] + by-stock-total 3[amt_qty_tp/trde_tp/unit_tp] +
    # trader-analysis 1[dt] = 32, minus trader-analysis --days가 이번 태스크
    # 안에서 한 차례 raw로 되돌아갔다가(I2 규칙 재적용, -1) 리뷰에서 다시
    # HumanChoice로 원복됐으므로(+1) net 변화는 0 = 31. 여기에 리뷰가
    # net-buyer(ka10042) --period(dt)를 TRADER_ANALYSIS_PERIOD_5_120 공유로
    # 새로 전환한 +1을 더해 32. credit available/trader-analysis(--pot·
    # --sort·--date-type)/intraday/after-close/consecutive는 Task 34a
    # 이전에 이미 HumanChoice였다(선행 fix 커밋들) — 이 델타에 포함되지
    # 않는다.
    # volume-renewal의 --volume-type(trde_qty_tp)은 기본값 "0"이 스펙 8개
    # 값(5/10/50/100/200/300/500/1000) 어디에도 없는 결함이라 Task 31a의
    # 동일 패턴과 같은 이유로 이번에도 raw 텍스트로 남겼다(전환 안 함).
    # instant-volume의 --volume-type(qty_tp)/vi-trigger의
    # --skip-stock(skip_stk)도 라벨 미확인/비트마스크라 raw 텍스트로 남겼다.
    #
    # 170 = 145(Task 32까지의 누적치, 아래 옛 주석 참고) + Task 33(market
    # etf·elw·gold·program)의 25 = etf returns 1[dt] + etf all 3[txon_type/
    # navpre/txon_yn] + elw surge 5[flu_tp/tm_tp/trde_qty_tp/rght_tp/
    # trde_end_elwskip] + elw disparity 2[rght_tp/trde_end_elwskip] +
    # elw search 2[rght_tp/sort_tp] + elw change-rank 3[sort_tp/rght_tp/
    # trde_end_skip] + elw balance-rank 3[sort_tp/rght_tp/trde_end_skip] +
    # gold chart-tick/day/week/month 4[upd_stkpc_tp 각 1개] + program
    # cumulative 1[amt_qty_tp] + program stock-time 1[amt_qty_tp].
    # (elw broker-top의 --exclude-expired는 ELW_BROKER_END_SKIP →
    # EXCLUDE_ENDED_ELW 이름만 바뀌었을 뿐 기존에 이미 HumanChoice였던
    # 데코레이터라 이 델타에 포함되지 않는다. --exchange 3자리
    # 정리(ka10030/ka90006/ka90007)는 HumanChoice가 아니라 순수
    # click.Choice(list(EXCHANGE_ALL))라 이 카운트에 잡히지 않는다.)
    #
    # 145 = 138(Task 31c까지의 누적치, 아래 옛 주석 참고) + Task 32(market
    # sector·theme ka10051/ka20001/ka20002/ka20009/ka10101/ka90001)의 7 =
    # sector investor 1[amt_qty_tp] + sector current/stocks/daily 3[mrkt_tp
    # 각 1개] + sector codes 1[mrkt_tp] + theme groups 2[qry_tp/flu_pl_amt_tp].
    #
    # 138 = 122(Task 31b까지의 누적치, 아래 옛 주석 참고) + Task 31c(market
    # rank ka10042/ka10062/ka10065/ka10098/ka90009)의 16 = ka10042 3
    # [qry_dt_tp/pot_tp/sort_base — dt는 I2 규칙으로 raw 유지해 미포함] +
    # ka10062 3[trde_tp/sort_cnd/unit_tp] + ka10065 3[trde_tp/orgn_tp/
    # amt_qty_tp] + ka10098 5[sort_base/stk_cnd/trde_qty_cnd/crd_cnd/
    # trde_prica] + ka90009 2[amt_qty_tp/qry_dt_tp].
    #
    # 122 = 94(account/market/stock를 훑던 시절의 53 + order 그룹의 2
    # [order gold buy/sell --order-type, GOLD_ORDER_TYPES] + Task 31a(market
    # rank ka10016~ka10023)의 31 + Task 31a-fix의 8[같은 8개 커맨드의
    # --vol-type/trde_qty_tp — 종전 기본값 raw "0"이 어느 API 스펙에도
    # 없던 결함이라 값 교정과 함께 전환했다, task-31a-fix-report.md 참고])
    # + Task 31b(market rank ka10027~ka10039)의 28. ka10030/ka10032/ka10038
    # 은 Tranche B에서 이미 전환돼 있어 31b가 새로 늘린 옵션이 아니다 —
    # 28 = ka10027 7 + ka10029 5 + ka10031 1 + ka10033 4 + ka10034 2 +
    # ka10035 2 + ka10036 1 + ka10037 3 + ka10039 3.
    # 이 수는 트리 순회로 재도출한 값이지 델타 추정이 아니다.
    #
    # 215 = 202(Task 34a 리뷰까지의 누적치, 위 주석 참고) + Task 34b(stock
    # program_top/chart_*/lending)의 순증 13 = program-top 2[trde_upper_tp/
    # amt_qty_tp] + chart tick/minute/day/week/month/year 6[upd_stkpc_tp
    # 각 1개, CHART_ADJUSTED_PRICE 공유] + chart investor 3[amt_qty_tp/
    # trde_tp/unit_tp] + chart intraday-investor 2[amt_qty_tp/trde_tp].
    # lending trend/by-stock의 --all(all_tp)은 스펙에 값이 하나뿐이라
    # (반대쪽 불명) 전환하지 않아 이 델타에 포함되지 않는다. chart
    # tick/minute의 --range/--interval(tic_scope)도 값=라벨 그대로인
    # 자기서술적 수량이라(I2 규칙) 전환 대상에서 제외했다.
    assert len(converted) == 215
    assert ("cli stock investor program-top", "trde_upper_tp") in converted
    assert ("cli stock investor program-top", "amt_qty_tp") in converted
    for command in ("tick", "minute", "day", "week", "month", "year"):
        assert (f"cli stock chart {command}", "upd_stkpc_tp") in converted
    assert ("cli stock chart investor", "amt_qty_tp") in converted
    assert ("cli stock chart investor", "trde_tp") in converted
    assert ("cli stock chart investor", "unit_tp") in converted
    assert ("cli stock chart intraday-investor", "amt_qty_tp") in converted
    assert ("cli stock chart intraday-investor", "trde_tp") in converted
    # lending trend/by-stock의 --all(all_tp)은 스펙에 값이 하나뿐이라
    # (반대쪽 불명) 이번 태스크에서 의도적으로 전환하지 않았다 — 이름으로
    # 못 박아 실수로 전환되어도(또는 실수로 빠져도) 눈에 띄게 한다.
    assert ("cli stock lending trend", "all_tp") not in converted
    assert ("cli stock lending by-stock", "all_tp") not in converted
    # 금현물 주문 두 건은 이름으로도 못 박아 둔다. 개수만 맞추면 다른 곳이
    # 늘고 여기가 빠져도 통과하기 때문이다.
    assert ("cli order gold buy", "order_type") in converted
    assert ("cli order gold sell", "order_type") in converted
    # 8개 rank 커맨드의 --vol-type이 전부 실제로 물려 있는지 이름으로도
    # 못 박는다 — 개수만 맞추면 여기가 빠져도 통과하기 때문이다.
    for command in ("new-highlow", "limit", "near-highlow", "surge",
                    "orderbook-top", "orderbook-surge", "balance-rate-surge",
                    "volume-surge"):
        assert (f"cli market rank {command}", "trde_qty_tp") in converted
    # Task 31b: ka10027 --vol-cnd(trde_qty_cnd)는 값 교정까지 겸한 자리라
    # 이름으로 못 박는다. ka10039 broker-top --type(trde_tp)도 형제 API와
    # 값 집합이 달라(buy/sell 단독값 없음) 이름으로 못 박아 둔다.
    assert ("cli market rank change", "trde_qty_cnd") in converted
    assert ("cli market rank broker-top", "trde_tp") in converted
    # Task 31c: ka10042 --sort는 TRADER_ANALYSIS_SORT(ka10043과 공유)를
    # 재사용해 새 상수 없이 전환됐다는 것을 이름으로 못 박는다 — 개수만
    # 맞추면 이 커플링이 깨져도(예: ka10042가 별도 raw 텍스트로 되돌아가도)
    # 통과하기 때문이다.
    assert ("cli market rank net-buyer", "sort_base") in converted
    # Task 34a 리뷰: net-buyer(ka10042) --period(dt)는 stock.py의
    # trader-analysis(ka10043) --days(dt)와 TRADER_ANALYSIS_PERIOD_5_120을
    # 공유하도록 함께 전환됐다 — v2.11.0에서 trader-analysis --days만
    # HumanChoice였던 비대칭을 net-buyer 쪽을 끌어올려 해소했다(반대 방향,
    # raw로 되돌리는 쪽은 검증을 걷어내는 조용한 회귀라 기각). 개수만
    # 맞추면 이 커플링이 깨져도 통과하므로 양쪽 다 이름으로 못 박는다.
    assert ("cli market rank net-buyer", "dt") in converted
    assert ("cli stock analysis trader-analysis", "dt") in converted
    assert ("cli market rank same-net-trade", "trde_tp") in converted
    assert ("cli market rank investor-top", "orgn_tp") in converted
    assert ("cli market rank afterhours-change", "trde_prica") in converted
    assert ("cli market rank foreign-inst", "qry_dt_tp") in converted
    # Task 33: elw broker-top의 --exclude-expired는 이름만 EXCLUDE_ENDED_ELW로
    # 바뀌었을 뿐 여전히 HumanChoice여야 한다(개수만 맞추면 라운드트립 중
    # raw 텍스트로 되돌아가도 통과하기 때문에 이름으로 못 박는다).
    assert ("cli market elw broker-top", "trde_end_elwskip") in converted
    # ka90005/ka90010(program time-trend/daily-trend)의 --unit/--tick-type은
    # Tranche B가 이미 HumanChoice로 전환해 뒀다 — Task 33은 손대지 않았다는
    # 것을 이름으로 못 박는다(개수만 맞추면 이 두 자리가 빠져도 통과한다).
    assert ("cli market program time-trend", "amt_qty_tp") in converted
    assert ("cli market program daily-trend", "amt_qty_tp") in converted
    # ka90013(program stock-daily)의 --unit은 Required=N + 기존 기본값이
    # 빈 문자열이라 이번 태스크에서 의도적으로 전환하지 않았다 — 이름으로
    # 못 박아 실수로 전환되어도(또는 실수로 빠져도) 눈에 띄게 한다.
    assert ("cli market program stock-daily", "amt_qty_tp") not in converted
    # ka50080(gold chart-minute)의 --price-type도 같은 이유로 raw 유지.
    assert ("cli market gold chart-minute", "upd_stkpc_tp") not in converted


# ── Task 8: both-fail envelope (fail_api) ────────────────

def _raise_api_error(api_id, body=None, **kwargs):
    raise KiwoomAPIError(1999, "server down")


def test_balance_both_fail_json_emits_envelope_exit_2(runner, isolated_env):
    with patch("kiwoom_cli.commands.account.KiwoomClient") as mock_cls, \
         patch("kiwoom_cli.commands.us.account_ops.fetch_balance",
               side_effect=KiwoomAPIError(1999, "us down")):
        mock_cls.return_value = _mock_kiwoom_client(_raise_api_error)
        result = runner.invoke(cli, ["-f", "json", "account", "balance"])
    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "UPSTREAM_ERROR"


def test_deposit_both_fail_json_emits_envelope_exit_2(runner, isolated_env):
    with patch("kiwoom_cli.commands.account.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(_raise_api_error)
        result = runner.invoke(cli, ["-f", "json", "account", "deposit"])
    assert result.exit_code == 2
    assert _doc(result)["error"]["code"] == "UPSTREAM_ERROR"


def test_balance_both_fail_table_still_exit_2(runner, isolated_env):
    with patch("kiwoom_cli.commands.account.KiwoomClient") as mock_cls, \
         patch("kiwoom_cli.commands.us.account_ops.fetch_balance",
               side_effect=KiwoomAPIError(1999, "us down")):
        mock_cls.return_value = _mock_kiwoom_client(_raise_api_error)
        result = runner.invoke(cli, ["account", "balance"])
    assert result.exit_code == 2


def test_deposit_both_fail_table_exits_2(runner, isolated_env):
    with patch("kiwoom_cli.commands.account.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(_raise_api_error)
        result = runner.invoke(cli, ["account", "deposit"])
    assert result.exit_code == 2


# ── Task 9: config setup --profile alignment ─────────────

def _stub_keys(monkeypatch):
    monkeypatch.setattr("kiwoom_cli.config.set_appkey", lambda *a, **k: None)
    monkeypatch.setattr("kiwoom_cli.config.set_secretkey", lambda *a, **k: None)


def test_config_setup_uses_root_profile(runner, isolated_env, monkeypatch):
    _stub_keys(monkeypatch)
    result = runner.invoke(cli, ["-f", "json", "-p", "work", "config", "setup",
                                 "--appkey", "AK", "--secretkey", "SK"])
    assert result.exit_code == 0
    assert _doc(result)["data"]["profile"] == "work"


def test_config_setup_explicit_profile_beats_root(runner, isolated_env, monkeypatch):
    _stub_keys(monkeypatch)
    result = runner.invoke(cli, ["-f", "json", "-p", "work", "config", "setup",
                                 "--profile", "mock2",
                                 "--appkey", "AK", "--secretkey", "SK"])
    assert result.exit_code == 0
    assert _doc(result)["data"]["profile"] == "mock2"
