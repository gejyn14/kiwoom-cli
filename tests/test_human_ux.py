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
    "ELW_BROKER_PERIOD", "ELW_BROKER_END_SKIP",
])
def test_every_mapping_converts_all_human_names(mapping_name):
    from kiwoom_cli.commands import _constants
    mapping = getattr(_constants, mapping_name)
    hc = _constants.HumanChoice(mapping)
    for human, code in mapping.items():
        assert hc.convert(human, None, None) == code    # human 이름 → 코드
        assert hc.convert(code, None, None) == code     # 원시 코드 하위호환


def test_all_converted_decorators_use_human_choice(runner, isolated_env):
    """18개 전환 옵션이 전부 HumanChoice로 남아있는지 데코레이터 레벨에서 고정."""
    import click
    from kiwoom_cli.commands import _constants
    from kiwoom_cli.commands.account import account
    from kiwoom_cli.commands.market import market

    def _iter_options(cmd):
        yield from ((cmd, p) for p in cmd.params if isinstance(p, click.Option))
        if isinstance(cmd, click.Group):
            for sub in cmd.commands.values():
                yield from _iter_options(sub)

    converted = [
        (cmd.name, p.name) for cmd, p in list(_iter_options(account)) + list(_iter_options(market))
        if isinstance(p.type, _constants.HumanChoice)
    ]
    # 19, not 18: balance's and asset's --delist are two separate physical decorators
    # that both apply DELIST_QRY (task-6-brief.md Step 4 lists them as distinct bullets,
    # "orders pending" through "history journal" sum to 18 in account.py alone), plus
    # market.py's rank hot --period = 19. The brief's prose summary ("17 + 1 = 18") undercounts
    # by one relative to its own itemized decorator list; this assertion pins the verified
    # ground truth instead. See task-6-report.md for the full recount.
    # 23, not 19: task-13 (ka90005/ka90010, program time-trend/daily-trend) converted
    # 4 more raw-text options to HumanChoice — --unit (AMT_QTY_TP_1_2) and --tick-type
    # (MIN_TIC_TP) on each of the two commands. 19 + 4 = 23. See task-13-report.md.
    # 37, not 23: task-14 (ka10030 rank volume, ka10032 rank amount, ka10038
    # broker-by-stock, ka30002 elw broker-top) converted 14 more raw-text options
    # to HumanChoice — rank volume's 7 (--sort, --stock-condition, --credit-type,
    # --vol-type, --price-type, --amount-type, --session), rank amount's 1
    # (--include-managed), broker-by-stock's 2 (--type, --period), elw broker-top's
    # 4 (--vol-type, --type, --period, --exclude-expired). 23 + 14 = 37.
    # See task-14-report.md.
    assert len(converted) == 37


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
