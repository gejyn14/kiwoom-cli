"""Tier-2 agent-contract regression tests (envelope purity, exit codes, discovery, purity long tail)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import click  # noqa: F401
import httpx
import pytest
from click.testing import CliRunner

from kiwoom_cli import config  # noqa: F401
from kiwoom_cli.client import KiwoomAPIError
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


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


# ── Task 1: KiwoomGroup contract fixes ───────────────────

def test_unknown_command_json_emits_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "nosuchcmd"])
    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_token_expired_8005_exits_3(runner, isolated_env):
    def raise_expired(api_id, body=None, **kwargs):
        raise KiwoomAPIError(8005, "Token 유효하지 않습니다")

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(raise_expired)
        result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 3
    doc = _doc(result)
    assert doc["error"]["code"] == "TOKEN_EXPIRED"


def test_api_error_still_exits_2(runner, isolated_env):
    def raise_api(api_id, body=None, **kwargs):
        raise KiwoomAPIError(1902, "종목 정보 없음")

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(raise_api)
        result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 2
    assert _doc(result)["error"]["code"] == "NOT_FOUND"


def test_read_timeout_emits_network_error_exit_2(runner, isolated_env):
    def raise_timeout(api_id, body=None, **kwargs):
        raise httpx.ReadTimeout("timed out")

    with patch("kiwoom_cli.commands.stock.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(raise_timeout)
        result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["error"]["code"] == "NETWORK_ERROR"
    assert doc["error"]["retryable"] is True


# ── Task 2: fail_input sweep (order paths) ───────────────

def test_kr_float_price_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                 "--price", "70000.5", "--type", "limit", "--dry-run"])
    assert result.exit_code == 1
    doc = _doc(result)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_us_partial_cancel_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "cancel", "0001", "NVDA",
                                 "--qty", "5", "--confirm"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_cond_price_on_us_symbol_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "buy", "NVDA", "10",
                                 "--cond-price", "100", "--confirm"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_fail_input_table_mode_stderr_only(runner, isolated_env):
    result = runner.invoke(cli, ["order", "buy", "005930", "10",
                                 "--price", "70000.5", "--type", "limit", "--dry-run"])
    assert result.exit_code == 1
    assert result.stdout.strip() == ""


# ── Task 3: fail_input sweep (query/config paths) ────────

def test_config_set_invalid_domain_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "config", "set", "domain", "staging"])
    assert result.exit_code == 1
    doc = _doc(result)          # 기존 버그: rich 텍스트가 stdout에 섞여 파싱 불가였음
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_config_use_unknown_profile_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "config", "use", "nope"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_krw_on_domestic_symbol_json_envelope(runner, isolated_env):
    # stock info has no --krw option; --krw lives on stock chart {tick,minute,day,week,month,year}.
    # chart tick is the first sweep-site command with --krw and no other required options.
    result = runner.invoke(cli, ["-f", "json", "stock", "chart", "tick", "005930", "--krw"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_next_key_and_all_pages_mutually_exclusive(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "--next-key", "X", "--all-pages",
                                 "stock", "info", "005930"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


# ── Task 5: describe discovery modes ─────────────────────

def test_describe_paths_flat_list(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "describe", "--paths"])
    assert result.exit_code == 0
    doc = _doc(result)
    assert isinstance(doc["data"], list)
    assert len(doc["data"]) > 100
    sample = doc["data"][0]
    assert set(sample.keys()) == {"path", "help"}


def test_describe_depth_limits_recursion(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "describe", "--depth", "1"])
    assert result.exit_code == 0
    top = _doc(result)["data"]
    by_name = {sub["path"].split()[-1]: sub for sub in top["subcommands"]}

    # order는 그룹(하위 8개 커맨드)이지만 --depth 1이 자식 재귀를 끊는다
    order_sub = by_name["order"]
    assert order_sub["subcommands"] == []

    # 깊이 제한과 무관하게, 잘린 그 자리(depth=0)의 자체 옵션/인자는 그대로 채워진다
    describe_sub = by_name["describe"]
    assert "subcommands" not in describe_sub  # describe는 그룹이 아니므로 키 자체가 없음
    assert {o["name"] for o in describe_sub["options"]} >= {"paths_only", "depth"}

    # --depth 없이 같은 그룹을 조회하면 실제로 하위 커맨드가 채워진다는 대조군
    full = runner.invoke(cli, ["-f", "json", "describe", "order"])
    assert len(_doc(full)["data"]["subcommands"]) == 8


def test_describe_full_tree_still_default(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "describe", "order", "buy"])
    assert result.exit_code == 0
    spec = _doc(result)["data"]
    assert any(o["name"] == "client_order_id" for o in spec["options"])


# ── Task 6: market.py docstrings carry API IDs ───────────

def test_all_market_commands_expose_api_id():
    import re
    from kiwoom_cli.commands.market import market

    def walk(cmd, path="market"):
        missing = []
        if isinstance(cmd, click.Group):
            for name, sub in cmd.commands.items():
                missing.extend(walk(sub, f"{path} {name}"))
        else:
            if not re.search(r"\((ka|kt|fn|us)[a-z]?\d+", cmd.help or ""):
                missing.append(path)
        return missing

    assert walk(market) == []


# ── Task 7: purity long tail ─────────────────────────────

def test_config_setup_json_never_prompts_and_emits_envelope(runner, isolated_env, monkeypatch):
    calls = []
    monkeypatch.setattr("click.prompt", lambda *a, **k: calls.append("prompt") or "x")
    result = runner.invoke(cli, ["-f", "json", "config", "setup"])
    assert calls == []                      # 프롬프트 금지
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_config_setup_json_with_keys_succeeds(runner, isolated_env, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.config.set_appkey", lambda *a, **k: None)
    monkeypatch.setattr("kiwoom_cli.config.set_secretkey", lambda *a, **k: None)
    result = runner.invoke(cli, ["-f", "json", "config", "setup",
                                 "--appkey", "AK", "--secretkey", "SK"])
    assert result.exit_code == 0
    doc = _doc(result)
    assert doc["ok"] is True
    assert doc["data"]["profile"] == "default"
    assert doc["data"]["domain"] == "mock"


def test_config_set_success_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "config", "set", "domain", "mock"])
    assert result.exit_code == 0
    doc = _doc(result)
    assert doc["data"] == {"key": "domain", "value": "mock", "profile": "default"}


def test_stream_types_json_envelope(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "stream", "types"])
    assert result.exit_code == 0
    doc = _doc(result)
    assert isinstance(doc["data"], list) and len(doc["data"]) == 19


# ── Task 8: stream edge paths ────────────────────────────

def test_stream_missing_websockets_json_error(runner, isolated_env, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_websockets(name, *a, **k):
        if name == "websockets":
            raise ImportError("No module named 'websockets'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_websockets)
    result = runner.invoke(cli, ["-f", "json", "stream", "quote", "005930", "--max-events", "1"])
    assert result.exit_code == 1
    doc = json.loads(result.stdout.strip().splitlines()[-1])
    assert doc["error"]["code"] == "DEPENDENCY_MISSING"


def test_stream_raw_with_json_rejected(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "stream", "quote", "005930", "--raw"])
    assert result.exit_code == 1
    doc = json.loads(result.stdout.strip().splitlines()[-1])
    assert doc["error"]["code"] == "INVALID_INPUT"


# ── Task 9: --fields unmatched hint ──────────────────────

def test_fields_typo_flagged_in_meta(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "--fields", "bogus_field", "config", "show"])
    assert result.exit_code == 0
    doc = _doc(result)
    assert doc["meta"]["fields_unmatched"] == ["bogus_field"]


def test_fields_match_no_flag(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "--fields", "profile", "config", "show"])
    doc = _doc(result)
    assert "fields_unmatched" not in doc["meta"]
    assert doc["data"] == {"profile": "default"}


# ── Task 18 fix round 1: --fields end-to-end on container-valued keys ────
#
# The unit test in test_envelope.py only exercises project_fields() directly.
# These drive the full CLI (emit() → project_fields() → _collect_matched())
# for the two motivating cases documented in AGENTS.md: --fields body on a
# dry-run order and --fields checks on `order validate`.

def test_fields_body_on_dry_run_order_returns_whole_payload(runner, isolated_env, monkeypatch):
    """--fields body must return the whole dry-run body dict (Task 18's
    original bug: body vanished because `k in fields` was checked after the
    isinstance(v, dict) branch had already recursed into it)."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", lambda *a, **k: fake)
    result = runner.invoke(cli, [
        "-f", "json", "--fields", "body",
        "order", "buy", "005930", "10", "--price", "70000", "--type", "limit", "--dry-run",
    ])
    assert result.exit_code == 0
    assert fake.calls == []
    doc = _doc(result)
    assert "fields_unmatched" not in doc["meta"]
    assert doc["data"] == {
        "body": {
            "dmst_stex_tp": "KRX",
            "stk_cd": "005930",
            "ord_qty": "10",
            "ord_uv": "70000",
            "trde_tp": "0",
            "cond_uv": "",
        }
    }


def test_fields_checks_on_order_validate_returns_whole_dict(runner, isolated_env, monkeypatch):
    """--fields checks must return the whole checks dict (all 5 booleans),
    the second container-valued key documented in AGENTS.md for Task 18."""
    fake = FakeKiwoomClient()
    fake.set_response("ka10001", {"stk_nm": "삼성전자", "cur_prc": "70000"})
    fake.set_response("kt00001", {"ord_alow_amt": "100000000"})
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", lambda *a, **k: fake)
    # market_open is a KST wall-clock heuristic (real Sat/Sun or off-hours would
    # make "valid" False and exit 1 regardless of --fields) — pin it so this
    # test's outcome depends only on the --fields projection under test, not
    # on when it happens to run.
    monkeypatch.setattr("kiwoom_cli.commands.order._market_open_kr", lambda: True)
    result = runner.invoke(cli, [
        "-f", "json", "--fields", "checks",
        "order", "validate", "buy", "005930", "10", "--price", "70000",
    ])
    assert result.exit_code == 0
    doc = _doc(result)
    assert "fields_unmatched" not in doc["meta"]
    assert set(doc["data"]) == {"checks"}
    assert doc["data"]["checks"] == {
        "symbol_ok": True,
        "market_open": True,
        "sufficient_balance": True,
        "price_ok": True,
        "price_known": True,
    }


# ── Task 10: tier-1 follow-ups ───────────────────────────

def test_lock_busy_typed_error(runner, isolated_env, monkeypatch):
    from kiwoom_cli import idempotency
    monkeypatch.setattr(idempotency, "_acquire", MagicMock(side_effect=OSError("locked")))
    result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                 "--price", "70000", "--confirm", "--client-order-id", "k1"])
    assert result.exit_code == 2
    doc = _doc(result)
    assert doc["error"]["code"] == "LEDGER_BUSY"
    assert doc["error"]["retryable"] is True


def test_validate_rejects_market_plus_price(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10",
                                 "--price", "70000", "--type", "market"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_validate_rejects_best_plus_price(runner, isolated_env, monkeypatch):
    """validate는 order buy/sell과 같은 _resolve_order_type을 거치므로 확장된
    시장가 계열(최유리/최우선/중간가) 가드도 그대로 적용돼야 한다 — validate가
    통과시키는데 실제 주문 경로가 거부하는 괴리(과거 발견 사례)를 막는다.

    isolated_env만으로는(자격증명 없음) 가드가 없어도 실제 API 호출 시도가
    KiwoomAuthError로 죽어 exit 3(AUTH_REQUIRED)이 나온다 — 그러면 이 테스트는
    "가드가 거부했다"가 아니라 "인증이 안 됐다"로 우연히 실패/통과를 구분 못
    한다(v2.9 audit finding 2). FakeKiwoomClient를 주입해 인증을 우회하면,
    가드가 없을 때는 ka10001/kt00001 호출이 실제로 발생하고 exit 1이어도
    error.code가 VALIDATION_FAILED(잔고부족 등)이지 INVALID_INPUT이 아니며
    calls도 비어있지 않다 — sibling인 test_order.py의
    `fake_client.calls == []` 패턴과 동일하게, 가드가 API 호출 전에 발동했다는
    것 자체를 직접 확인한다."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", lambda *a, **k: fake)
    result = runner.invoke(cli, ["-f", "json", "order", "validate", "buy", "005930", "10",
                                 "--price", "70000", "--type", "best"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"
    assert fake.calls == []


def test_us_stock_info_exchange_resolution_failure_json_envelope(runner, isolated_env, monkeypatch):
    from kiwoom_cli.commands.us import stock_ops
    from kiwoom_cli.commands.us.detect import UsExchangeError

    def raise_exchange_error(client, code, exchange=None):
        raise UsExchangeError("거래소를 판별할 수 없습니다")

    monkeypatch.setattr(stock_ops, "resolve_us_exchange", raise_exchange_error)
    with patch("kiwoom_cli.commands.us.stock_ops.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(lambda api_id, body=None, **kw: ({}, {}))
        result = runner.invoke(cli, ["-f", "json", "stock", "info", "ZZZZZZZ"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"


def test_send_order_strips_pagination_flags(runner, isolated_env):
    captured = {}

    def capture(api_id, body=None, **kwargs):
        ctx = click.get_current_context(silent=True)
        captured["all_pages"] = ctx.obj.get("all_pages")
        captured["next_key"] = ctx.obj.get("next_key")
        return {"ord_no": "1", "return_code": 0}, {}

    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        mc = _mock_kiwoom_client(capture)
        mock_cls.return_value = mc
        result = runner.invoke(cli, ["-f", "json", "--all-pages", "order", "buy", "005930",
                                     "10", "--confirm"])
    assert result.exit_code == 0
    assert captured["all_pages"] is False
    assert captured["next_key"] is None
