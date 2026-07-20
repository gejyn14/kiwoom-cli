"""Tier-1 order-safety regression tests (fingerprint, lock, preview order, type inference, fx gate)."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import mock
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from kiwoom_cli import config, idempotency
from kiwoom_cli.client import KiwoomAPIError, KiwoomAuthError
from kiwoom_cli.client import KiwoomClient as _RealKiwoomClient
from kiwoom_cli.main import cli


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


# ── Task 8: in-flight record blocks duplicate after transport failure ──

def test_inflight_record_blocks_duplicate_after_transport_failure(runner, isolated_env):
    """전송 중 네트워크 오류 후 같은 키로 재시도하면 재전송하지 않는다 (inflight-only)."""
    import httpx

    sent = []

    class FailingClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            sent.append((api_id, body))
            raise httpx.ReadTimeout("timeout")

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", FailingClient):
        r1 = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                 "--price", "70000", "--type", "limit",
                                 "--confirm", "--client-order-id", "dup-1"])
    assert r1.exit_code == 2
    assert len(sent) == 1

    class OkClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            sent.append((api_id, body))
            return {"ord_no": "0000777", "return_code": 0}, {}

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", OkClient):
        r2 = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                 "--price", "70000", "--type", "limit",
                                 "--confirm", "--client-order-id", "dup-1"])
    doc = json.loads(r2.stdout)
    assert len(sent) == 1, "재시도가 주문을 재전송했다 — 중복 주문"
    assert r2.exit_code == 2
    assert doc["error"]["code"] == "ORDER_STATUS_UNKNOWN"
    assert doc["error"]["retryable"] is False


def test_legacy_ledger_without_status_still_replays(runner, isolated_env):
    """v2.4~v2.8 원장(status 키 없음)은 CLI 경로에서도 종전대로 재생된다.

    idempotency.record()를 거치지 않고 원장 줄을 직접 써서, 진짜로 "status" 키가
    없는 레코드를 만든 뒤 CLI를 통해 재생 여부를 검증한다 (모듈 API로는
    record()가 항상 "status": "done"을 쓰므로 이 경로를 재현할 수 없다).
    """
    # buy 005930 10 --price 70000 --type limit 이 실제로 구성하는 body와
    # 정확히 일치해야 fingerprint가 맞아 재생(replay)으로 처리된다.
    legacy_body = {
        "dmst_stex_tp": "KRX",
        "stk_cd": "005930",
        "ord_qty": "10",
        "ord_uv": "70000",
        "trde_tp": "0",
        "cond_uv": "",
    }
    fp = idempotency.fingerprint("kt10000", legacy_body)
    ledger = idempotency._ledger_file()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    legacy_rec = {
        "key": "legacy-no-status",
        "api_id": "kt10000",
        "ord_no": "0000111",
        "fingerprint": fp,
        # 의도적으로 "status" 키 없음 — v2.4~v2.8 원장 형식
        "response": {"ord_no": "0000111", "return_code": 0, "return_msg": "정상"},
        "ts": "2026-01-01T00:00:00+00:00",
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(legacy_rec, ensure_ascii=False) + "\n")

    hit = idempotency.lookup("legacy-no-status")
    assert "status" not in hit  # 픽스처가 진짜로 status-less 레코드인지 확인

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, [
            "-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit",
            "--confirm", "--client-order-id", "legacy-no-status",
        ])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["data"]["idempotent_replay"] is True
    assert doc["data"]["order_no"] == "0000111"
    mock_cls.assert_not_called()


# ── Task 9: upstream rejection does not burn the idempotency key ────────

def test_rejected_order_can_be_retried_with_same_key(runner, isolated_env):
    """업스트림 구조적 거부(KiwoomAPIError) 후 같은 키+같은 내용으로 재시도하면
    실제로 재전송된다 (ORDER_STATUS_UNKNOWN으로 막히지 않고, replay로도 처리되지
    않음) — inflight+rejected, 이어서 inflight+rejected+inflight+done 상태를 검증."""
    sent = []

    class RejectingClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            sent.append((api_id, body))
            raise KiwoomAPIError(-1, "예수금부족")

    args = ["-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit",
            "--confirm", "--client-order-id", "reject-key"]

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", RejectingClient):
        r1 = runner.invoke(cli, args)
    assert r1.exit_code == 2
    assert len(sent) == 1

    # inflight+rejected 상태 확인
    hit = idempotency.lookup("reject-key")
    assert hit["status"] == "rejected"
    assert hit["response"] is None

    class OkClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            sent.append((api_id, body))
            return {"ord_no": "0000555", "return_code": 0}, {}

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", OkClient):
        r2 = runner.invoke(cli, args)
    assert r2.exit_code == 0, r2.stdout
    assert len(sent) == 2, "거부 후 재시도가 실제로 재전송되지 않았다"
    doc = json.loads(r2.stdout)
    assert "idempotent_replay" not in doc["data"], "재전송 결과가 replay로 오인됨"
    assert doc["data"]["order_no"] == "0000555"

    # inflight+rejected+inflight+done 상태 확인 (lookup은 마지막 매치를 반환)
    lines = idempotency._ledger_file().read_text().strip().splitlines()
    statuses = [json.loads(line)["status"] for line in lines]
    assert statuses == ["inflight", "rejected", "inflight", "done"]
    final_hit = idempotency.lookup("reject-key")
    assert final_hit["status"] == "done"
    assert final_hit["response"]["ord_no"] == "0000555"


def test_rejected_record_still_conflicts_on_different_body(runner, isolated_env):
    """거부 기록이 있어도 다른 주문 내용(다른 fingerprint)으로 같은 키를 재사용하면
    여전히 IDEMPOTENCY_CONFLICT — '거부 후 재전송 허용'이 fingerprint 검사를
    우회하지 않는다."""
    sent = []

    class RejectingClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            sent.append((api_id, body))
            raise KiwoomAPIError(-1, "예수금부족")

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", RejectingClient):
        r1 = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                 "--price", "70000", "--type", "limit",
                                 "--confirm", "--client-order-id", "reject-key-2"])
    assert r1.exit_code == 2
    assert len(sent) == 1

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        r2 = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "20",
                                 "--price", "71000", "--type", "limit",
                                 "--confirm", "--client-order-id", "reject-key-2"])
    assert r2.exit_code == 1
    doc = json.loads(r2.stdout)
    assert doc["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    mock_cls.assert_not_called()
    assert len(sent) == 1  # 두 번째 시도는 전송되지 않음


# ── I1: pre-transmission auth failure must not burn the idempotency key ──

def test_auth_error_before_send_does_not_burn_key(runner, isolated_env):
    """전송 전 인증 실패(토큰 없음)는 KiwoomAuthError로 나타난다 — 실제 HTTP 전송
    (self._http.post) 이전, 요청 준비 단계에서 발생하므로 업스트림에 도달하지
    않았음이 코드 구조상 보장된다. inflight로 영구히 막혀서는 안 되고, 토큰 발급
    후 같은 키로 재시도하면 실제로 전송되어야 한다 (ORDER_STATUS_UNKNOWN에 막히지
    않고, replay로도 처리되지 않음 — 실제로 새 요청이 나가야 한다)."""
    sent = []

    class NoTokenClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            # 실제 코드에서 KiwoomAuthError는 client.py의 _request_once()가
            # self._http.post()를 호출하기 전, 토큰 유무를 확인하는 첫 줄에서
            # 던진다 — 전송 시도 자체가 없다.
            raise KiwoomAuthError()

    args = ["-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit",
            "--confirm", "--client-order-id", "auth-key"]

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", NoTokenClient):
        r1 = runner.invoke(cli, args)
    assert r1.exit_code == 3, r1.stdout  # EXIT_AUTH
    assert len(sent) == 0, "인증 실패인데 전송 시도가 기록됐다"

    # 핵심 검증: 인증 실패 후 원장이 "rejected"로 종결되어야 한다.
    # inflight로 영구히 남으면(회귀 전 동작) 아래 재시도가 ORDER_STATUS_UNKNOWN으로
    # 막히고, 이 assert가 그 사실을 직접 드러낸다.
    hit = idempotency.lookup("auth-key")
    assert hit is not None
    assert hit["status"] == "rejected", (
        f"인증 실패가 원장에 '{hit['status']}'로 남았다 — inflight로 남으면 "
        "재시도가 영구히 ORDER_STATUS_UNKNOWN으로 막힌다 (아무것도 전송되지 않았는데도)."
    )
    assert hit["response"] is None

    class OkClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            sent.append((api_id, body))
            return {"ord_no": "0000999", "return_code": 0}, {}

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", OkClient):
        r2 = runner.invoke(cli, args)
    assert r2.exit_code == 0, r2.stdout
    doc = json.loads(r2.stdout)
    assert len(sent) == 1, (
        "토큰 발급 후 재시도가 실제로 전송되지 않았다 — "
        f"exit_code={r2.exit_code}, stdout={r2.stdout}"
    )
    assert "idempotent_replay" not in doc["data"], "재전송 결과가 replay로 오인됨"
    assert doc["data"]["order_no"] == "0000999"

    # inflight+rejected+inflight+done 상태 확인 (rejected 케이스와 동일한 형태)
    lines = idempotency._ledger_file().read_text().strip().splitlines()
    statuses = [json.loads(line)["status"] for line in lines]
    assert statuses == ["inflight", "rejected", "inflight", "done"]


# ── Task 10: OSError branches keep their fail-closed / fail-open direction ──

def test_inflight_write_oserror_blocks_send(runner, isolated_env, monkeypatch):
    """in-flight 기록 실패 시 주문을 전송하지 않는다 (fail closed)."""
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(idempotency, "record_inflight", boom)

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                     "--price", "70000", "--type", "limit",
                                     "--confirm", "--client-order-id", "oserror-inflight"])
    assert result.exit_code == 2
    mock_cls.assert_not_called()
    doc = json.loads(result.stdout)
    assert doc["ok"] is False


def test_final_record_oserror_does_not_block_already_sent_order(runner, isolated_env, monkeypatch):
    """완료 기록 실패는 이미 전송된 주문을 되돌리지 않는다 (fail open, exit 0)."""
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(idempotency, "record", boom)

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(_ok_order_response)
        result = runner.invoke(cli, ["-f", "json", "order", "buy", "005930", "10",
                                     "--price", "70000", "--type", "limit",
                                     "--confirm", "--client-order-id", "oserror-final"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["data"]["order_no"] == "0000001"


# ── Task 11: pagination suppression pins record_rejected() safety ───────

def test_send_order_forces_single_request_even_with_global_all_pages(runner, isolated_env):
    """send_order는 전역 --all-pages를 강제로 꺼야 한다.

    record_rejected()의 정확성은 주문 전송이 항상 단일 요청이라는 데 의존한다:
    여러 페이지를 도는 도중 한 페이지가 체결(성공)되고 다른 페이지에서
    KiwoomAPIError가 발생하면, 실제로 체결된 주문을 "rejected"(재사용 가능한
    키)로 잘못 기록하게 된다. 오늘은 주문 API가 cont-yn: Y를 반환하지 않아
    이중으로 보호되지만, _mutation.send_order가 ctx.obj["all_pages"]를 False로
    강제하는 코드가 없어지면 그 방어선이 사라진다. 이 테스트는 그 강제 동작
    자체를 고정한다."""
    captured = {}

    class RecordingClient:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, api_id, body, **kw):
            ctx = click.get_current_context(silent=True)
            captured["all_pages"] = ctx.obj.get("all_pages")
            captured["next_key_present"] = "next_key" in ctx.obj
            return {"ord_no": "1", "return_code": 0}, {}

    with mock.patch("kiwoom_cli.commands.order.KiwoomClient", RecordingClient):
        result = runner.invoke(cli, [
            "--all-pages", "-f", "json", "order", "buy", "005930", "10",
            "--price", "70000", "--type", "limit", "--confirm",
        ])
    assert result.exit_code == 0, result.stdout
    # 전역 플래그가 켜져 있었음에도 send_order가 명령 실행 전에 꺼야 한다.
    assert captured["all_pages"] is False
    assert captured["next_key_present"] is False


# ── Task 6: 환전 신청 + 조건검색 페이지네이션 가드 (audit N6) ───────────

def _real_client(*_a, **_k):
    """실제 KiwoomClient — domain/token만 고정해 프로필/키체인 해석을 우회한다.

    FakeKiwoomClient류의 목은 client.py의 실제 페이지네이션 while 루프를
    갖고 있지 않아 그 루프를 우회해버린다 — 이 헬퍼는 진짜 KiwoomClient를
    써서 실제 반복 전송 메커니즘을 그대로 통과시킨다."""
    return _RealKiwoomClient(domain="https://mock.test", token="test-token")


def test_suppress_pagination_clears_all_pages_and_next_key():
    """suppress_pagination()은 ctx.obj["all_pages"]를 False로 두고 next_key를 제거한다."""
    from kiwoom_cli.commands._mutation import suppress_pagination

    ctx = click.Context(click.Command("x"), obj={"all_pages": True, "next_key": "K"})
    with ctx:
        suppress_pagination()
    assert ctx.obj["all_pages"] is False
    assert "next_key" not in ctx.obj


def test_suppress_pagination_noop_without_active_context():
    """활성 click 컨텍스트가 없어도(라이브러리로 호출되는 경우) 예외를 던지지 않는다."""
    from kiwoom_cli.commands._mutation import suppress_pagination

    suppress_pagination()


def test_exchange_apply_single_real_request_despite_all_pages(runner, isolated_env, monkeypatch, httpx_mock):
    """환전 신청(ust31302) — 실제 KiwoomClient.request()의 페이지네이션 루프를 통해도
    --all-pages가 반복 전송을 일으키지 않는지 실제 HTTP 요청 횟수로 검증한다.

    가드가 없으면 cont-yn: Y가 계속 오는 한 client.py의 _ALL_PAGES_CAP(50)까지
    같은 환전 요청이 반복 전송된다 — 감사 N6(high), 실제 자금이 최대 50회 이동."""
    monkeypatch.setattr("kiwoom_cli.commands.us.exchange.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0, "krw_exmn_amt": "1000000", "buy_fc_amt": "723.85"},
        headers={"cont-yn": "Y", "next-key": "K"},
        is_reusable=True,
    )
    result = runner.invoke(cli, [
        "-f", "json", "--all-pages", "account", "exchange", "apply", "1000000", "--confirm",
    ])
    assert result.exit_code == 0, result.stdout
    assert len(httpx_mock.get_requests()) == 1, (
        f"환전 요청이 {len(httpx_mock.get_requests())}회 전송됨 (기대: 1회)"
    )


@pytest.mark.parametrize("args", [
    ["order", "condition", "search", "001", "--confirm"],
    ["order", "condition", "realtime", "001", "--confirm"],
    ["order", "condition", "stop", "001", "--confirm"],
])
def test_condition_commands_single_real_request_despite_all_pages(
    runner, isolated_env, monkeypatch, httpx_mock, args,
):
    """조건검색 요청/실시간등록/실시간해제(ka10172~4) — confirm_gate는 있지만
    MUTATION_APIS에는 없어 send_order 경로를 타지 않는다. 스윕 중 추가로 발견된
    미보호 지점: --all-pages로 반복 전송되지 않아야 한다."""
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0},
        headers={"cont-yn": "Y", "next-key": "K"},
        is_reusable=True,
    )
    result = runner.invoke(cli, ["-f", "json", "--all-pages", *args])
    assert result.exit_code == 0, result.stdout
    assert len(httpx_mock.get_requests()) == 1, (
        f"{args[2]} 요청이 {len(httpx_mock.get_requests())}회 전송됨 (기대: 1회)"
    )


def test_send_order_single_real_request_despite_all_pages(runner, isolated_env, monkeypatch, httpx_mock):
    """send_order 경로(국내 주식 매수, kt10000) — 실제 KiwoomClient.request() 루프를 통해도
    단일 요청만 나가는지 확인한다. 기존 test_send_order_forces_single_request_even_with_global_all_pages
    는 ctx.obj 플래그만 스냅샷하는 목을 쓰므로 그 목 자체가 반복 루프를 갖고 있지 않다 —
    "메커니즘이 아니라 결과"를 증명하려면 실제 클라이언트로 실제 HTTP 요청 수를 세야 한다."""
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0, "ord_no": "0000001"},
        headers={"cont-yn": "Y", "next-key": "K"},
        is_reusable=True,
    )
    result = runner.invoke(cli, [
        "-f", "json", "--all-pages", "order", "buy", "005930", "10",
        "--price", "70000", "--type", "limit", "--confirm",
    ])
    assert result.exit_code == 0, result.stdout
    assert len(httpx_mock.get_requests()) == 1, (
        f"매수 주문이 {len(httpx_mock.get_requests())}회 전송됨 (기대: 1회)"
    )


# ── Task 6b: 변이 응답은 meta.cont를 남기지 않는다 (client.py:112-118) ───
#
# suppress_pagination()이 --all-pages 반복 전송(50회 상한)은 막았지만, 응답
# envelope의 meta.cont는 여전히 살아있었다 — AGENTS.md는 meta.cont가 있으면
# --next-key로 "이어서" 실행하라고 안내하므로, 변이(주문/환전/조건검색)에서는
# 그 안내 자체가 실제 동작을 한 번 더 실행하라는 유도가 된다. 실제 HTTP
# transport(httpx_mock)를 통해 진짜 KiwoomClient.request()가 만든 envelope을
# 검증한다 — FakeKiwoomClient류의 클래스 치환 목은 last_cont를 기록하는 코드
# 경로 자체를 우회해 이 결함을 놓친다.

def test_order_buy_envelope_has_no_meta_cont(runner, isolated_env, monkeypatch, httpx_mock):
    """order buy(kt10000) — 업스트림이 cont-yn: Y를 보내더라도 meta.cont는 None."""
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0, "ord_no": "0000001"},
        headers={"cont-yn": "Y", "next-key": "K"},
    )
    result = runner.invoke(cli, [
        "-f", "json", "order", "buy", "005930", "10",
        "--price", "70000", "--type", "limit", "--confirm",
    ])
    assert result.exit_code == 0, result.stdout
    assert len(httpx_mock.get_requests()) == 1
    assert json.loads(result.stdout)["meta"]["cont"] is None


def test_exchange_apply_envelope_has_no_meta_cont(runner, isolated_env, monkeypatch, httpx_mock):
    """account exchange apply(ust31302) — 실제 자금 이동. 동일 결함 재현."""
    monkeypatch.setattr("kiwoom_cli.commands.us.exchange.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0, "krw_exmn_amt": "1000000", "buy_fc_amt": "723.85"},
        headers={"cont-yn": "Y", "next-key": "K"},
    )
    result = runner.invoke(cli, [
        "-f", "json", "account", "exchange", "apply", "1000000", "--confirm",
    ])
    assert result.exit_code == 0, result.stdout
    assert len(httpx_mock.get_requests()) == 1
    assert json.loads(result.stdout)["meta"]["cont"] is None


def test_exchange_apply_outgoing_request_has_no_cont_headers(
    runner, isolated_env, monkeypatch, httpx_mock,
):
    """account exchange apply --next-key PREV — 실제 자금이 이동하는 POST 자체에
    cont-yn/next-key 헤더가 실리면 안 된다.

    이 결함의 사전-수정 형태(감사 N6 이전)는 정확히 이랬다: 전역 --next-key가
    ctx.obj에 남아 있으면 client.py:150-158의 페이지네이션 주입 분기
    (`if obj and not next_key and obj.get("next_key")`)가 그 값을 소비해
    cont_yn="Y"/next_key="PREV"를 실제 환전 신청 요청에 실어 보냈다.
    suppress_pagination()이 요청 전에 ctx.obj["next_key"]를 pop하면서 지금은
    막혀 있지만, 지금까지는 이를 pin하는 테스트가 helper 단위 테스트
    (test_suppress_pagination_clears_all_pages_and_next_key)와
    test_raw_api_mutation_clears_global_next_key(test_security.py) 뿐이었다 —
    둘 다 ctx.obj 스냅샷이거나 FakeKiwoomClient 클래스 치환이라
    client.py의 실제 주입 분기 자체를 우회한다. 여기서는 실제 KiwoomClient +
    httpx_mock으로 그 분기를 그대로 통과시켜 진짜 나가는 HTTP 요청의 헤더를
    검사한다."""
    monkeypatch.setattr("kiwoom_cli.commands.us.exchange.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0, "krw_exmn_amt": "1000000", "buy_fc_amt": "723.85"},
        headers={"cont-yn": "N", "next-key": ""},
    )
    result = runner.invoke(cli, [
        "-f", "json", "--next-key", "PREV", "account", "exchange", "apply", "1000000", "--confirm",
    ])
    assert result.exit_code == 0, result.stdout
    reqs = httpx_mock.get_requests()
    assert len(reqs) == 1
    assert "next-key" not in reqs[0].headers, (
        f"환전 신청 요청에 next-key 헤더가 실렸음: {dict(reqs[0].headers)}"
    )
    assert "cont-yn" not in reqs[0].headers, (
        f"환전 신청 요청에 cont-yn 헤더가 실렸음: {dict(reqs[0].headers)}"
    )


def test_raw_api_mutation_envelope_has_no_meta_cont(runner, isolated_env, monkeypatch, httpx_mock):
    """kiwoom api ust31302 — raw api 게이트를 거치는 변이 경로도 동일하게 억제."""
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0},
        headers={"cont-yn": "Y", "next-key": "K"},
    )
    result = runner.invoke(cli, [
        "-f", "json", "api", "ust31302", '{"exch_tp":"1","fc_exmn_amt":"1000000"}', "--confirm",
    ])
    assert result.exit_code == 0, result.stdout
    assert len(httpx_mock.get_requests()) == 1
    assert json.loads(result.stdout)["meta"]["cont"] is None


def test_condition_search_envelope_has_no_meta_cont(runner, isolated_env, monkeypatch, httpx_mock):
    """order condition search(ka10172) — MUTATION_APIS 밖의 별도 변이 경로. 동일 결함 재현."""
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0},
        headers={"cont-yn": "Y", "next-key": "K"},
    )
    result = runner.invoke(cli, [
        "-f", "json", "order", "condition", "search", "001", "--confirm",
    ])
    assert result.exit_code == 0, result.stdout
    assert len(httpx_mock.get_requests()) == 1
    assert json.loads(result.stdout)["meta"]["cont"] is None


def test_market_read_command_still_advertises_meta_cont(runner, isolated_env, monkeypatch, httpx_mock):
    """대조군: 읽기 전용 명령(주문성 아님)은 여전히 meta.cont를 정상적으로 노출해야
    한다 — 변이 억제가 읽기 전용 페이지네이션 계약을 깨면 원래 결함보다 더 나쁘다."""
    monkeypatch.setattr("kiwoom_cli.commands.market.KiwoomClient", _real_client)
    httpx_mock.add_response(
        json={"return_code": 0},
        headers={"cont-yn": "Y", "next-key": "K"},
    )
    result = runner.invoke(cli, ["-f", "json", "market", "rank", "volume"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["meta"]["cont"] == {"next_key": "K"}


# ── D8/29-3: 원장 정리(prune) ─────────────────────────
#
# 원장은 append-only라 파일도 lookup 스캔도 무한히 자란다. 90일 지난
# **종결된** 키를 지운다. 트리거는 수동 명령(`kiwoom config prune-ledger`)
# 하나뿐이다 — record()에서 확률적으로 돌리는 안은 채택하지 않았다.
# 잘린 원장은 lookup이 None을 반환해 중복 주문을 재전송시키므로, 큰 원장보다
# 훨씬 나쁘다. 그 위험을 주문 실행 도중에 무작위로 터뜨릴 이유가 없다.

def _write_ledger(lines):
    ledger = idempotency._ledger_file()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "w", encoding="utf-8") as f:
        for line in lines:
            f.write((line if isinstance(line, str) else json.dumps(line, ensure_ascii=False)) + "\n")
    return ledger


def _rec(key, status, days_ago, **extra):
    from datetime import timedelta
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")
    return {"key": key, "api_id": "kt10000", "ord_no": "1", "fingerprint": "f",
            "status": status, "response": {"ord_no": "1"}, "ts": ts, **extra}


def test_prune_removes_old_resolved_keys(isolated_env):
    _write_ledger([_rec("old-done", "done", 200), _rec("fresh-done", "done", 3)])
    stats = idempotency.prune(max_age_days=90)
    assert stats["removed_keys"] == 1
    assert idempotency.lookup("old-done") is None
    assert idempotency.lookup("fresh-done") is not None


def test_prune_never_removes_inflight_however_old(isolated_env):
    """in-flight는 주문이 브로커에 닿았을 수 있다는 유일한 증거다 —
    나이와 무관하게 절대 지우지 않는다. 이걸 지우면 재실행이 실제 주문을
    다시 쏜다."""
    _write_ledger([_rec("ancient-inflight", "inflight", 3650)])
    stats = idempotency.prune(max_age_days=90)
    assert stats["removed_keys"] == 0
    hit = idempotency.lookup("ancient-inflight")
    assert hit is not None and hit["status"] == "inflight"


def test_prune_removes_superseded_inflight_only_with_its_resolved_key(isolated_env):
    """모든 주문은 inflight를 먼저 쓰고 done으로 종결한다. 종결된 오래된 키는
    inflight 줄까지 함께 사라져야 실제로 공간이 회수된다 — 그러나 이는 그 키의
    **최종** 레코드가 종결 상태일 때에만 허용된다."""
    _write_ledger([_rec("k", "inflight", 200), _rec("k", "done", 200)])
    assert idempotency.prune(max_age_days=90)["removed_keys"] == 1
    assert idempotency.lookup("k") is None

    _write_ledger([_rec("k2", "done", 200), _rec("k2", "inflight", 200)])
    assert idempotency.prune(max_age_days=90)["removed_keys"] == 0
    assert idempotency.lookup("k2")["status"] == "inflight"


def test_prune_keeps_unparseable_lines_and_missing_ts(isolated_env):
    """해석 불가능한 줄은 보존한다 — 지울 근거가 없으면 남기는 쪽이 안전하다."""
    _write_ledger(["{쓰레기", {"key": "no-ts", "status": "done"}, _rec("old", "done", 200)])
    idempotency.prune(max_age_days=90)
    text = idempotency._ledger_file().read_text(encoding="utf-8")
    assert "{쓰레기" in text
    assert "no-ts" in text
    assert "\"old\"" not in text


def test_prune_dry_run_does_not_touch_file(isolated_env):
    ledger = _write_ledger([_rec("old", "done", 200)])
    before = ledger.read_bytes()
    stats = idempotency.prune(max_age_days=90, dry_run=True)
    assert stats["removed_keys"] == 1  # 지웠을 것을 보고는 한다
    assert ledger.read_bytes() == before
    assert idempotency.lookup("old") is not None


def test_prune_leaves_ledger_intact_when_write_fails(isolated_env, monkeypatch):
    """쓰다 죽어도 원장은 잘리지 않아야 한다. 임시 파일에 쓰고 os.replace로
    갈아끼우므로, 실패 시 원본이 그대로 남는다."""
    ledger = _write_ledger([_rec("old", "done", 200), _rec("fresh", "done", 1)])
    before = ledger.read_bytes()

    real_replace = os.replace

    def boom(src, dst):
        raise OSError("디스크 꽉 참")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        idempotency.prune(max_age_days=90)
    monkeypatch.setattr(os, "replace", real_replace)

    assert ledger.read_bytes() == before, "원장이 손상됐다"
    assert idempotency.lookup("old") is not None
    assert idempotency.lookup("fresh") is not None
    # 임시 파일이 남아 다음 실행을 헷갈리게 하면 안 된다
    leftovers = [p.name for p in ledger.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], leftovers


def test_prune_leaves_ledger_intact_when_write_dies_midway(isolated_env, monkeypatch):
    """쓰기 **도중** 죽는 경우. 원장에 직접 open(...,"w")하는 구현은 그 순간
    파일이 잘리므로 이 테스트가 잡는다 — os.replace 실패만 보는 테스트로는
    비원자적 구현을 구분할 수 없다."""
    ledger = _write_ledger([_rec("old", "done", 200), _rec("fresh", "done", 1)])
    before = ledger.read_bytes()

    def boom(fd):
        raise OSError("쓰는 중에 죽음")

    monkeypatch.setattr(os, "fsync", boom)
    with pytest.raises(OSError):
        idempotency.prune(max_age_days=90)

    assert ledger.read_bytes() == before, "원장이 잘렸다 — 원자적 교체가 아니다"
    assert idempotency.lookup("old") is not None
    assert idempotency.lookup("fresh") is not None


def test_prune_no_ledger_is_a_noop(isolated_env):
    stats = idempotency.prune(max_age_days=90)
    assert stats["removed_keys"] == 0 and stats["kept_keys"] == 0


def test_prune_holds_the_ledger_lock(isolated_env, monkeypatch):
    """잠금 없이 재작성하면 동시 실행 중인 주문의 조회→전송→기록 구간과
    겹쳐 기록이 유실될 수 있다."""
    held = []
    real_locked = idempotency.locked

    @contextmanager
    def spy(blocking: bool = True):
        held.append(blocking)
        with real_locked(blocking=blocking):
            yield

    monkeypatch.setattr(idempotency, "locked", spy)
    _write_ledger([_rec("old", "done", 200)])
    idempotency.prune(max_age_days=90)
    # 잠금을 잡았고, **논블로킹**으로 잡았다 (D9/L1 — 블로킹이면 main.py의
    # LedgerLockBusy 핸들러가 POSIX에서 절대 실행되지 않는다)
    assert held == [False]


def test_prune_preserves_file_permissions(isolated_env):
    _write_ledger([_rec("old", "done", 200), _rec("fresh", "done", 1)])
    idempotency.prune(max_age_days=90)
    mode = idempotency._ledger_file().stat().st_mode & 0o777
    assert mode == 0o600, oct(mode)


def test_config_prune_ledger_command(runner, isolated_env):
    _write_ledger([_rec("old", "done", 200), _rec("fresh", "done", 1)])
    result = runner.invoke(cli, ["config", "prune-ledger"])
    assert result.exit_code == 0, result.output
    assert idempotency.lookup("old") is None
    assert idempotency.lookup("fresh") is not None


def test_config_prune_ledger_json_and_dry_run(runner, isolated_env):
    ledger = _write_ledger([_rec("old", "done", 200)])
    before = ledger.read_bytes()
    result = runner.invoke(cli, ["-f", "json", "config", "prune-ledger", "--dry-run"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["data"]["removed_keys"] == 1
    assert payload["data"]["dry_run"] is True
    assert ledger.read_bytes() == before


@pytest.mark.parametrize("days", ["0", "-5"])
def test_config_prune_ledger_rejects_bad_days(runner, isolated_env, days):
    """--days 0은 "전부 지워라"가 된다. 원장을 통째로 날리는 오타를 막는다.

    "No such command"로 우연히 exit 1이 나는 공허한 통과를 배제하기 위해
    메시지까지 본다."""
    result = runner.invoke(cli, ["config", "prune-ledger", "--days", days])
    assert result.exit_code == 1
    assert "No such command" not in result.output
    assert "1 이상" in result.output


# ── D9/L1: prune의 잠금 대기는 논블로킹이어야 한다 ────────────
#
# main.py의 prune-ledger는 LedgerLockBusy를 잡아 "잠시 후 다시 시도하세요"를
# 안내한다. 그런데 POSIX의 _acquire는 LOCK_NB 없이 flock(LOCK_EX)이라 영원히
# 기다린다 — 동시에 주문이 돌면 그 핸들러는 절대 실행되지 않고 사용자
# 프롬프트가 조용히 멈춘다. 주문 경로는 정확성 때문에 계속 블로킹해야 하므로
# 논블로킹은 사람이 부르는 경로에만 준다.


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock 경로")
def test_prune_reports_busy_instead_of_hanging(isolated_env):
    """다른 프로세스가 잠금을 쥐고 있으면 매달리지 않고 LedgerLockBusy."""
    _write_ledger([_rec("old", "done", 200)])
    ledger = idempotency._ledger_file()
    lock_path = ledger.with_suffix(".lock")

    import fcntl
    # 같은 프로세스라도 open이 다르면 file description이 달라 flock이 실제로
    # 경합한다 — 별도 프로세스를 띄우지 않고도 경합을 재현할 수 있다.
    with open(lock_path, "a+", encoding="utf-8") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        try:
            with pytest.raises(idempotency.LedgerLockBusy):
                idempotency.prune(max_age_days=90)
        finally:
            fcntl.flock(holder, fcntl.LOCK_UN)

    # 잠금이 풀리면 정상 동작한다 (논블로킹이 항상 실패로 굳지 않았는지)
    assert idempotency.prune(max_age_days=90)["removed_keys"] == 1


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock 경로")
def test_order_path_lock_still_blocks(isolated_env):
    """주문 경로(locked() 기본값)는 계속 블로킹한다 — 여기서 실패로 바꾸면
    동시 주문이 LEDGER_BUSY로 흔들린다. 논블로킹은 prune 전용이다."""
    import fcntl
    import threading

    ledger = idempotency._ledger_file()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger.with_suffix(".lock")
    entered = threading.Event()

    with open(lock_path, "a+", encoding="utf-8") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)

        def waiter():
            with idempotency.locked():
                entered.set()

        t = threading.Thread(target=waiter, daemon=True)
        t.start()
        # 논블로킹이었다면 즉시 LedgerLockBusy로 죽어 entered가 서지 않고
        # 스레드가 끝난다. 블로킹이면 아직 대기 중이어야 한다.
        assert not entered.wait(timeout=0.3), "주문 경로가 논블로킹으로 바뀌었다"
        assert t.is_alive(), "주문 경로가 대기하지 않고 즉시 종료했다"
        fcntl.flock(holder, fcntl.LOCK_UN)

    assert entered.wait(timeout=2.0), "잠금 해제 후에도 진입하지 못했다"
    t.join(timeout=2.0)


def test_ledger_path_unchanged_by_resolution_refactor(monkeypatch, tmp_path):
    """원장 경로가 움직이면 기록된 멱등키가 전부 안 보이게 되고, send_order가
    이미 체결됐을 수 있는 주문을 재전송한다. 해석 방식을 바꾸는 작업에서
    가장 위험한 부작용이라 값 자체를 리터럴로 고정한다."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[general]\ndefault_profile = "default"\n[profiles.default]\ndomain = "mock"\n')
    monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", cfg)
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    assert idempotency._ledger_file().name == "default-mock.jsonl"

    with click.Context(click.Command("x"), obj={"profile": "live", "resolved_profile": "live",
                                                "domain_key": "prod"}):
        assert idempotency._ledger_file().name == "live-prod.jsonl"
