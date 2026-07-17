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
