"""Tier-1 order-safety regression tests (fingerprint, lock, preview order, type inference, fx gate)."""

from __future__ import annotations

import json  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import click  # noqa: F401
import pytest
from click.testing import CliRunner

from kiwoom_cli import config, idempotency
from kiwoom_cli.main import cli  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """config/ledger를 tmp로 격리하고 프로필/도메인 env를 제거한다."""
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


# ── Task 1: idempotency core ─────────────────────────────

def test_fingerprint_stable_and_body_sensitive():
    fp1 = idempotency.fingerprint("kt10000", {"stk_cd": "005930", "ord_qty": "10"})
    fp2 = idempotency.fingerprint("kt10000", {"ord_qty": "10", "stk_cd": "005930"})
    fp3 = idempotency.fingerprint("kt10000", {"stk_cd": "005930", "ord_qty": "11"})
    fp4 = idempotency.fingerprint("kt10001", {"stk_cd": "005930", "ord_qty": "10"})
    assert fp1 == fp2
    assert fp1 != fp3
    assert fp1 != fp4
    assert len(fp1) == 16


def test_record_stores_fingerprint(isolated_env):
    idempotency.record("k1", "kt10000", {"ord_no": "42", "return_code": 0},
                       fingerprint="abc123")
    hit = idempotency.lookup("k1")
    assert hit is not None
    assert hit["fingerprint"] == "abc123"
    assert hit["response"]["ord_no"] == "42"


def test_record_without_fingerprint_is_legacy_compatible(isolated_env):
    idempotency.record("k2", "kt10000", {"ord_no": "43", "return_code": 0})
    hit = idempotency.lookup("k2")
    assert hit is not None
    assert hit["fingerprint"] is None


def test_locked_creates_lock_file_and_yields(isolated_env):
    with idempotency.locked():
        pass
    lock = idempotency._ledger_file().with_suffix(".lock")
    assert lock.exists()


# ── Task 2: send_order conflict / replay / lock ──────────

def _ok_order_response(api_id, body=None, **kwargs):
    return {"ord_no": "0000001", "return_code": 0, "return_msg": "정상"}, {}


def test_idempotency_conflict_rejected_without_send(runner, isolated_env):
    # 같은 키를 '다른 주문 내용'으로 먼저 기록
    idempotency.record("dup-key", "kt10000", {"ord_no": "1", "return_code": 0},
                       fingerprint=idempotency.fingerprint("kt10000", {"stk_cd": "000660"}))
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, [
            "-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit",
            "--confirm", "--client-order-id", "dup-key",
        ])
    assert result.exit_code == 1
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    mock_cls.assert_not_called()


def test_idempotent_replay_same_body_still_works(runner, isolated_env):
    args = ["-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit",
            "--confirm", "--client-order-id", "replay-key"]
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(_ok_order_response)
        first = runner.invoke(cli, args)
    assert first.exit_code == 0
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls2:
        second = runner.invoke(cli, args)
    assert second.exit_code == 0
    doc = json.loads(second.stdout)
    assert doc["data"]["idempotent_replay"] is True
    mock_cls2.assert_not_called()


def test_legacy_record_without_fingerprint_replays(runner, isolated_env):
    idempotency.record("old-key", "kt10000", {"ord_no": "7", "return_code": 0})
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, [
            "-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit",
            "--confirm", "--client-order-id", "old-key",
        ])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["data"]["idempotent_replay"] is True
    mock_cls.assert_not_called()


# ── Task 3: US order flow — resolve → preview → confirm ──

def test_us_order_resolves_and_previews_before_confirm(runner, isolated_env, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "kiwoom_cli.commands.us.order_ops._resolve_or_exit",
        lambda c, code, ex: (calls.append("resolve"), "ND")[1])
    monkeypatch.setattr(
        "kiwoom_cli.commands.us.order_ops._show_us_preview",
        lambda *a, **k: calls.append("preview"))

    def abort_confirm(*a, **k):
        calls.append("confirm")
        raise click.Abort()
    monkeypatch.setattr("kiwoom_cli.commands._mutation.click.confirm", abort_confirm)

    with patch("kiwoom_cli.commands.us.order_ops.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(_ok_order_response)
        result = runner.invoke(cli, ["order", "buy", "NVDA", "10", "--price", "213.04", "--type", "limit"])

    assert result.exit_code != 0
    assert calls == ["resolve", "preview", "confirm"]


# ── Task 4: KR preview shown before confirm prompt ───────

def test_kr_buy_preview_before_confirm(runner, isolated_env, monkeypatch):
    calls = []
    monkeypatch.setattr("kiwoom_cli.commands.order._show_order_preview",
                        lambda *a, **k: calls.append("preview"))

    def abort_confirm(*a, **k):
        calls.append("confirm")
        raise click.Abort()
    monkeypatch.setattr("kiwoom_cli.commands._mutation.click.confirm", abort_confirm)

    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, ["order", "buy", "005930", "10",
                                     "--price", "70000", "--type", "limit"])
    assert result.exit_code != 0
    assert calls == ["preview", "confirm"]
    mock_cls.assert_not_called()


def test_kr_cancel_preview_before_confirm(runner, isolated_env, monkeypatch):
    calls = []
    monkeypatch.setattr("kiwoom_cli.commands.order._show_cancel_preview",
                        lambda *a, **k: calls.append("preview"))

    def abort_confirm(*a, **k):
        calls.append("confirm")
        raise click.Abort()
    monkeypatch.setattr("kiwoom_cli.commands._mutation.click.confirm", abort_confirm)

    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, ["order", "cancel", "0000140", "005930"])
    assert result.exit_code != 0
    assert calls == ["preview", "confirm"]
    mock_cls.assert_not_called()


# ── Task 5: --price implies limit; market+price rejected ─

def test_price_without_type_sends_limit(runner, isolated_env):
    captured = {}

    def capture(api_id, body=None, **kwargs):
        captured["api_id"], captured["body"] = api_id, body
        return {"ord_no": "1", "return_code": 0}, {}

    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(capture)
        result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                     "--price", "70000", "--confirm"])
    assert result.exit_code == 0
    assert captured["body"]["trde_tp"] == "0"      # limit
    assert captured["body"]["ord_uv"] == "70000"


def test_no_price_no_type_sends_market(runner, isolated_env):
    captured = {}

    def capture(api_id, body=None, **kwargs):
        captured["body"] = body
        return {"ord_no": "1", "return_code": 0}, {}

    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(capture)
        result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                     "--confirm"])
    assert result.exit_code == 0
    assert captured["body"]["trde_tp"] == "3"      # market
    assert captured["body"]["ord_uv"] == ""


def test_explicit_market_with_price_rejected(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                 "--price", "70000", "--type", "market", "--confirm"])
    assert result.exit_code == 1
    doc = json.loads(result.stdout)
    assert doc["error"]["code"] == "INVALID_INPUT"


# ── Task 6: fx apply uses the confirm gate ───────────────

def test_fx_apply_json_mode_never_prompts(runner, isolated_env):
    with patch("kiwoom_cli.commands.us.exchange.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, ["-f", "json", "account", "exchange", "apply", "1000000"])
    assert result.exit_code == 1
    doc = json.loads(result.stdout)
    assert doc["error"]["code"] == "CONFIRMATION_REQUIRED"
    mock_cls.assert_not_called()


def test_fx_apply_yes_alias(runner, isolated_env):
    with patch("kiwoom_cli.commands.us.exchange.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(
            lambda api_id, body=None, **kw: ({"return_code": 0, "return_msg": "정상"}, {}))
        result = runner.invoke(cli, ["-f", "json", "account", "exchange", "apply",
                                     "1000000", "--yes"])
    assert result.exit_code == 0


# ── Task 7: credit/gold safety parity ────────────────────

def test_credit_buy_dry_run_sends_nothing(runner, isolated_env):
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, ["-f", "json", "order", "credit", "buy",
                                     "005930", "10", "--price", "70000", "--dry-run"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["data"]["would_send"] is True
    assert doc["data"]["api_id"] == "kt10006"
    assert doc["data"]["body"]["trde_tp"] == "0"   # price implies limit
    mock_cls.assert_not_called()


def test_gold_sell_client_order_id_replays(runner, isolated_env):
    args = ["-f", "json", "order", "gold", "sell", "M04020000", "1",
            "--price", "90000", "--confirm", "--client-order-id", "gold-k1"]
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(_ok_order_response)
        first = runner.invoke(cli, args)
    assert first.exit_code == 0
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls2:
        second = runner.invoke(cli, args)
    assert second.exit_code == 0
    doc = json.loads(second.stdout)
    assert doc["data"]["idempotent_replay"] is True
    mock_cls2.assert_not_called()


def test_credit_modify_preview_before_confirm(runner, isolated_env, monkeypatch):
    calls = []
    monkeypatch.setattr("kiwoom_cli.commands.order._show_modify_preview",
                        lambda *a, **k: calls.append("preview"))

    def abort_confirm(*a, **k):
        calls.append("confirm")
        raise click.Abort()
    monkeypatch.setattr("kiwoom_cli.commands._mutation.click.confirm", abort_confirm)

    with patch("kiwoom_cli.commands.order.KiwoomClient"):
        result = runner.invoke(cli, ["order", "credit", "modify",
                                     "0000139", "005930", "1", "70000"])
    assert result.exit_code != 0
    assert calls == ["preview", "confirm"]
