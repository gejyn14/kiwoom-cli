"""Tier-1 order-safety regression tests (fingerprint, lock, preview order, type inference, fx gate)."""

from __future__ import annotations

import json
from unittest import mock
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from kiwoom_cli import config, idempotency
from kiwoom_cli.client import KiwoomAPIError
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


# ── Task 12: 환전 신청 + 조건검색 페이지네이션 가드 (audit N6, task 6) ───

from kiwoom_cli.client import KiwoomClient as _RealKiwoomClient  # noqa: E402


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
