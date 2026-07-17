# Tier 1 Order-Safety Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the six money-path bugs found in the v2.5.0 multi-agent review: idempotency ledger races/collisions, preview-after-confirm inversion (KR/US/credit/gold), the `--price`-ignored-on-market-default trap, `account exchange apply` bypassing the confirm gate, stream/watch ignoring `--profile`/`KIWOOM_DOMAIN`, and credit/gold orders lacking `--dry-run`/`--client-order-id`.

**Architecture:** Harden `idempotency.py` (request fingerprint + cross-process file lock), centralize the guarded send path in `commands/_mutation.py` as `send_order()` (shared by KR and US order flows, `client_cls` param preserves existing test patch targets), reorder every mutation command to preview → confirm → send, and route WS domain/profile resolution through the same `config` functions the REST client uses.

**Tech Stack:** Python 3.10+, Click 8, httpx (untouched), pytest + unittest.mock + CliRunner. No new dependencies (`fcntl`/`msvcrt` are stdlib).

## Global Constraints

- Work on a feature branch off `main`: `git checkout -b feature/v2.5.1-order-safety` (main requires PR; protection is being restored).
- Every file keeps `from __future__ import annotations`; modern hints only (`X | None`, `dict[str, Any]`), no `Optional`/`typing.Dict`.
- All user-facing CLI messages in Korean; code identifiers in English.
- No new third-party dependencies.
- After each task: `ruff check kiwoom_cli/` and `pytest tests/ -q` must pass before commit.
- Do NOT bump `__version__` in this plan (release is a separate flow that triggers the release-checker agent).
- New tests for tasks 1–7 go in a new file `tests/test_order_safety.py`; task 8 tests go in a new file `tests/test_ws_target.py`. Both define fixtures locally (existing `tests/conftest.py` is not modified).
- Shared test-file header for `tests/test_order_safety.py` (written once in Task 1, reused by later tasks):

```python
"""Tier-1 order-safety regression tests (fingerprint, lock, preview order, type inference, fx gate)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from kiwoom_cli import config, idempotency
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
```

---

### Task 1: Idempotency core — fingerprint, lock, record signature

**Files:**
- Modify: `kiwoom_cli/idempotency.py`
- Test: `tests/test_order_safety.py` (create with the shared header above)

**Interfaces:**
- Consumes: existing `_ledger_file()`, `lookup(key)`.
- Produces (used by Task 2):
  - `fingerprint(api_id: str, body: dict[str, Any]) -> str` — 16-hex digest, key-order independent.
  - `locked()` — context manager serializing lookup→send→record across processes (per profile+env ledger).
  - `record(key: str, api_id: str, response: dict[str, Any], fingerprint: str | None = None) -> None` — now stores `"fingerprint"` in each JSONL line.

- [ ] **Step 1: Write the failing tests** (append to the shared header in `tests/test_order_safety.py`)

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_order_safety.py -v`
Expected: FAIL — `AttributeError: module 'kiwoom_cli.idempotency' has no attribute 'fingerprint'` (and `locked`), plus `TypeError` for the `fingerprint=` kwarg.

- [ ] **Step 3: Implement in `kiwoom_cli/idempotency.py`**

Replace the import block (lines 11–18) with:

```python
from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config, envelope
```

Update the module docstring line-format note (line 8) to:

```python
줄 형식: {"key", "api_id", "ord_no", "fingerprint", "response", "ts"}
```

Add after `_ledger_file()` (after line 23):

```python
def fingerprint(api_id: str, body: dict[str, Any]) -> str:
    """주문 내용 지문. 같은 키가 다른 주문 내용에 재사용되는 것을 감지한다."""
    canon = json.dumps({"api_id": api_id, "body": body},
                       sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


if sys.platform == "win32":  # pragma: no cover
    import msvcrt

    def _acquire(f) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _release(f) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _acquire(f) -> None:
        fcntl.flock(f, fcntl.LOCK_EX)

    def _release(f) -> None:
        fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def locked():
    """원장 파일 잠금 — 조회→전송→기록 구간을 프로세스 간 직렬화한다.

    같은 --client-order-id로 동시에 두 프로세스가 진입해 둘 다 미기록 상태를
    보고 둘 다 전송하는 중복 주문을 막는다. 프로필+환경 원장 단위 잠금이므로
    같은 프로필의 서로 다른 주문도 잠금 구간 동안 직렬화된다 (정확성 우선).
    """
    ledger = _ledger_file()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger.with_suffix(".lock")
    with open(lock_path, "a+", encoding="utf-8") as f:
        _acquire(f)
        try:
            yield
        finally:
            _release(f)
```

Replace `record()` (lines 46–58) with:

```python
def record(key: str, api_id: str, response: dict[str, Any],
           fingerprint: str | None = None) -> None:
    """전송 성공한 주문 응답을 원장에 append."""
    ledger = _ledger_file()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "key": key,
        "api_id": api_id,
        "ord_no": response.get("ord_no", ""),
        "fingerprint": fingerprint,
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
```

Note: `fingerprint` the module function and `fingerprint` the parameter shadow each other only inside `record()`, which never calls the function — acceptable and keeps the public kwarg name clean.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_order_safety.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: all PASS (existing `record(key, api_id, data)` callers still work — new kwarg is optional).

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/idempotency.py tests/test_order_safety.py
git commit -m "feat(idempotency): request fingerprint + cross-process ledger lock"
```

---

### Task 2: Shared guarded send path (`send_order`) with conflict rejection

**Files:**
- Modify: `kiwoom_cli/commands/_mutation.py`
- Modify: `kiwoom_cli/commands/order.py` (delete `_send_order` at lines 120–133; rewire 4 call sites at lines 241, 289, 336, 371)
- Test: `tests/test_order_safety.py`

**Interfaces:**
- Consumes: Task 1's `idempotency.fingerprint/locked/record`.
- Produces (used by Tasks 3 and 7):
  - `send_order(api_id: str, body: dict[str, Any], action: str, client_order_id: str | None, *, client_cls) -> None` in `_mutation.py`. `client_cls` is the caller's module-level `KiwoomClient` binding so existing test patches on `kiwoom_cli.commands.order.KiwoomClient` keep working.
  - New stable error code `IDEMPOTENCY_CONFLICT` (exit 1, retryable false).

- [ ] **Step 1: Write the failing tests**

```python
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
    doc = json.loads(result.output)
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
    doc = json.loads(second.output)
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
    doc = json.loads(result.output)
    assert doc["data"]["idempotent_replay"] is True
    mock_cls.assert_not_called()
```

Note on `doc["data"]["idempotent_replay"]`: `print_order_result` in json mode emits the normalized order response as envelope data; the replay flag is merged into the response dict before printing. If the existing envelope nests it differently (check `tests/test_order.py`'s replay assertions and mirror the exact path used there), adjust the two assertions to that established path.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_order_safety.py -v -k "conflict or replay or legacy"`
Expected: FAIL — `IDEMPOTENCY_CONFLICT` never emitted (conflict test sends the order instead / no such error code).

- [ ] **Step 3: Implement `send_order` in `kiwoom_cli/commands/_mutation.py`**

Replace the import block (lines 10–17) with:

```python
from __future__ import annotations

from typing import Any, Callable

import click

from .. import envelope, idempotency
from ..formatters import _get_format, human, print_order_result
from ..output import err_console
```

Append at the end of the file:

```python
def _idempotency_conflict(key: str) -> None:
    msg = (f"멱등성 키 '{key}'는 다른 주문 내용으로 이미 사용되었습니다. "
           "재시도라면 명령 인자가 이전 실행과 완전히 같은지 확인하고, "
           "새 주문이라면 다른 키를 사용하세요.")
    if _get_format() == "table":
        err_console.print(f"[red]{msg}[/]")
    else:
        envelope.emit(error=envelope.error_body(
            msg, code="IDEMPOTENCY_CONFLICT", retryable=False,
        ))
    raise SystemExit(1)


def send_order(api_id: str, body: dict[str, Any], action: str,
               client_order_id: str | None, *, client_cls) -> None:
    """주문 전송 + 멱등성 처리 (원장 잠금 아래에서 조회→전송→기록).

    - 같은 키 + 같은 내용(fingerprint 일치): 재전송 없이 이전 응답 반환.
    - 같은 키 + 다른 내용: IDEMPOTENCY_CONFLICT (exit 1), 전송하지 않음.
    - fingerprint가 없는 과거(v2.4~v2.5.0) 기록은 종전대로 재생한다.

    client_cls: 호출 모듈의 KiwoomClient 바인딩 (테스트 patch 지점 유지).
    """
    if not client_order_id:
        with client_cls() as c:
            data, _ = c.request(api_id, body)
        print_order_result(data, action)
        return
    fp = idempotency.fingerprint(api_id, body)
    with idempotency.locked():
        hit = idempotency.lookup(client_order_id)
        if hit is not None:
            stored = hit.get("fingerprint")
            if stored is not None and stored != fp:
                _idempotency_conflict(client_order_id)
            human(f"[dim]멱등성 키 '{client_order_id}' 기존 기록 — 재전송하지 않고 이전 응답을 반환합니다.[/]")
            print_order_result({**hit["response"], "idempotent_replay": True}, action)
            return
        with client_cls() as c:
            data, _ = c.request(api_id, body)
        idempotency.record(client_order_id, api_id, data, fingerprint=fp)
    print_order_result(data, action)
```

- [ ] **Step 4: Rewire `kiwoom_cli/commands/order.py`**

Delete `_send_order` (lines 120–133). Change the `._mutation` import (line 33) to:

```python
from ._mutation import confirm_gate, dry_run_payload, finish_dry_run, send_order
```

Change line 29 from `from .. import envelope, idempotency` to `from .. import envelope` (the `idempotency` import is now unused here).

Replace the four call sites:

```python
# buy (was line 241)
    send_order("kt10000", body, "매수", client_order_id, client_cls=KiwoomClient)
# sell (was line 289)
    send_order("kt10001", body, "매도", client_order_id, client_cls=KiwoomClient)
# modify (was line 336)
    send_order("kt10002", body, "정정", client_order_id, client_cls=KiwoomClient)
# cancel (was line 371)
    send_order("kt10003", body, "취소", client_order_id, client_cls=KiwoomClient)
```

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS. If any existing test patched `kiwoom_cli.commands.order._send_order` directly (grep first: `grep -rn "_send_order" tests/`), update that patch target to `kiwoom_cli.commands._mutation.send_order`.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/_mutation.py kiwoom_cli/commands/order.py tests/test_order_safety.py
git commit -m "feat(order): fingerprint-bound idempotency with IDEMPOTENCY_CONFLICT + locked send path"
```

---

### Task 3: US orders — resolve exchange and show preview BEFORE the confirm gate

**Files:**
- Modify: `kiwoom_cli/commands/us/order_ops.py`
- Test: `tests/test_order_safety.py`

**Interfaces:**
- Consumes: `send_order` from Task 2; existing `_resolve_or_exit`, `confirm_gate`.
- Produces: new `_send_us_order(api_id, action, code, exchange, body_fn, show_preview_fn, client_order_id, confirm)` signature — callers no longer call `confirm_gate` themselves.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_order_safety.py -v -k us_order_resolves`
Expected: FAIL — current code confirms first, so `calls` starts with `"confirm"`.

- [ ] **Step 3: Restructure `kiwoom_cli/commands/us/order_ops.py`**

Change the imports: line 7 `from ... import idempotency` is removed; line 11 becomes:

```python
from .._mutation import confirm_gate, dry_run_payload, finish_dry_run, send_order
```

Also remove `print_order_result` from the formatters import on line 9 if it becomes unused (keep `human`, `print_generic_table`).

Replace `_send_us_order` (lines 70–85) with:

```python
def _send_us_order(api_id: str, action: str, code: str, exchange: str | None,
                   body_fn, show_preview_fn, client_order_id: str | None,
                   confirm: bool) -> None:
    """거래소 확정 → 미리보기 → 확인 게이트 → 전송(멱등성).

    자동 판별된 거래소까지 사용자가 본 뒤에 확인하도록 게이트가 마지막이다.
    """
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
    show_preview_fn(stex_tp)
    confirm_gate(confirm)
    send_order(api_id, body_fn(stex_tp), action, client_order_id,
               client_cls=KiwoomClient)
```

In `buy` (lines 131–136), `sell` (166–171), `modify` (194–199), `cancel` (220–225): delete the `confirm_gate(confirm)` line and pass `confirm` into `_send_us_order`. Final form of each dispatch tail:

```python
    # buy
    if dry_run:
        _dry_run_us("ust20000", "buy", code, qty, price, order_type, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20000", "매수", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)

    # sell
    if dry_run:
        _dry_run_us("ust20001", "sell", code, qty, price, order_type, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20001", "매도", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)

    # modify
    if dry_run:
        _dry_run_us("ust20002", "modify", code, 0, price, None, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20002", "정정", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)

    # cancel
    if dry_run:
        _dry_run_us("ust20003", "cancel", code, 0, 0, None, exchange,
                    body_fn, preview_fn)
        return
    _send_us_order("ust20003", "취소", code, exchange, body_fn, preview_fn,
                   client_order_id, confirm)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_order_safety.py -v -k us_order_resolves && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS. Existing US tests in `tests/test_us.py` exercise `--confirm` paths (gate short-circuits) and dry-run paths (unchanged), so they should hold; if one asserts on prompt ordering, update it to preview-first.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/commands/us/order_ops.py tests/test_order_safety.py
git commit -m "fix(order/us): show resolved exchange + preview before the confirm gate"
```

---

### Task 4: KR stock orders — preview before confirm

**Files:**
- Modify: `kiwoom_cli/commands/order.py` (buy/sell/modify/cancel only; credit/gold are rebuilt in Task 7)
- Test: `tests/test_order_safety.py`

**Interfaces:**
- Consumes: nothing new. Pure reordering.
- Produces: interactive flow contract "미리보기 → 확인 프롬프트" that Task 7 replicates.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_order_safety.py -v -k "preview_before_confirm"`
Expected: FAIL with `calls == ["confirm"]` (preview never reached after abort).

- [ ] **Step 3: Swap the two lines in each of the four commands**

`buy` — replace (current lines 238–241):

```python
    _show_order_preview("매수", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10000", body, "매수", client_order_id, client_cls=KiwoomClient)
```

`sell` — same pattern:

```python
    _show_order_preview("매도", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10001", body, "매도", client_order_id, client_cls=KiwoomClient)
```

`modify`:

```python
    _show_modify_preview("정정", orig_order_no, code, qty, kr_price, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10002", body, "정정", client_order_id, client_cls=KiwoomClient)
```

`cancel`:

```python
    _show_cancel_preview("취소", orig_order_no, code, qty, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10003", body, "취소", client_order_id, client_cls=KiwoomClient)
```

Note: in json/csv mode the preview goes through `human()` (stderr/table-only), so stdout purity is unchanged; `confirm_gate` still short-circuits with `--confirm` and still emits `CONFIRMATION_REQUIRED` in json mode.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_order_safety.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS (json-purity tests unaffected because previews are `human()`-routed).

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/commands/order.py tests/test_order_safety.py
git commit -m "fix(order): show order preview before the confirmation prompt (KR stock)"
```

---

### Task 5: `--price` + default-market trap — infer limit, reject contradictions

**Files:**
- Modify: `kiwoom_cli/commands/order.py` (new helper + `buy`/`sell` options and bodies)
- Test: `tests/test_order_safety.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (used by Task 7): `_resolve_order_type(order_type: str | None, price: float) -> str` and constant `_MARKET_TYPES`.

- [ ] **Step 1: Write the failing tests**

```python
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
    doc = json.loads(result.output)
    assert doc["error"]["code"] == "INVALID_INPUT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_order_safety.py -v -k "price_without_type or no_price_no_type or explicit_market"`
Expected: `test_price_without_type_sends_limit` FAILS (`trde_tp == "3"` today); `test_explicit_market_with_price_rejected` FAILS (exit 0 today); the market default case passes already.

- [ ] **Step 3: Implement the helper** (in `order.py`, after `_kr_type_or_exit`, ~line 78)

```python
_MARKET_TYPES = frozenset({"market", "market-ioc", "market-fok"})


def _resolve_order_type(order_type: str | None, price: float) -> str:
    """--type 미지정 시 가격 유무로 결정한다. 시장가 계열 + 가격 지정은 모순.

    조용히 가격을 버리고 시장가로 나가는 사고(가격 지정 매수가 시장가 체결)를
    막는 안전장치다.
    """
    if order_type is None:
        return "limit" if price else "market"
    if price and order_type in _MARKET_TYPES:
        raise click.UsageError(
            f"'{order_type}' 주문유형은 가격을 사용하지 않습니다. "
            "--price를 빼거나 --type limit을 지정하세요."
        )
    return order_type
```

(`click.UsageError` is already converted to an `INVALID_INPUT` envelope + exit 1 by `KiwoomGroup` in `main.py`.)

- [ ] **Step 4: Apply to `buy` and `sell`**

In both commands change the option declaration (lines 204 and 248) to:

```python
@click.option("--type", "order_type", default=None, type=click.Choice(ALL_ORDER_TYPES), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
```

and the parameter annotation to `order_type: str | None`. Insert as the FIRST statement of each function body (before the `is_us_symbol` dispatch, so US tickers get the same inference):

```python
    order_type = _resolve_order_type(order_type, price)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_order_safety.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS. (Verified: every existing test that passes `--price` also passes `--type limit` explicitly, so no existing assertion depends on the old silent-market behavior.)

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/order.py tests/test_order_safety.py
git commit -m "fix(order): --price without --type now means limit; market+price is an error"
```

---

### Task 6: `account exchange apply` through the confirm gate

**Files:**
- Modify: `kiwoom_cli/commands/us/exchange.py`
- Test: `tests/test_order_safety.py`

**Interfaces:**
- Consumes: `confirm_gate` from `_mutation.py`.
- Produces: json/csv-mode `CONFIRMATION_REQUIRED` (exit 1) for `account exchange apply`; `--yes` alias.

- [ ] **Step 1: Write the failing test**

```python
# ── Task 6: fx apply uses the confirm gate ───────────────

def test_fx_apply_json_mode_never_prompts(runner, isolated_env):
    with patch("kiwoom_cli.commands.us.exchange.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, ["-f", "json", "account", "exchange", "apply", "1000000"])
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["error"]["code"] == "CONFIRMATION_REQUIRED"
    mock_cls.assert_not_called()


def test_fx_apply_yes_alias(runner, isolated_env):
    with patch("kiwoom_cli.commands.us.exchange.KiwoomClient") as mock_cls:
        mock_cls.return_value = _mock_kiwoom_client(
            lambda api_id, body=None, **kw: ({"return_code": 0, "return_msg": "정상"}, {}))
        result = runner.invoke(cli, ["-f", "json", "account", "exchange", "apply",
                                     "1000000", "--yes"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_order_safety.py -v -k fx_apply`
Expected: FAIL — json mode currently raises `click.Abort` on closed stdin (exit 1 but no envelope; `json.loads` fails) and `--yes` is `no such option`.

- [ ] **Step 3: Implement**

In `kiwoom_cli/commands/us/exchange.py`, add to the imports:

```python
from .._mutation import confirm_gate
```

Replace `fx_apply` (lines 42–63) with:

```python
@exchange_group.command("apply")
@click.argument("amount", type=int)
@click.option("--direction", "direction", default="krw-usd", type=click.Choice(list(DIRECTION)), help="환전 방향")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 실행")
def fx_apply(amount: int, direction: str, confirm: bool):
    """환전 신청 (ust31302). 실제 자금이 이동합니다."""
    unit = "원" if direction == "krw-usd" else "달러"
    human(Panel(
        f"[bold]환전 신청[/]\n\n"
        f"  방향: {_DIRECTION_LABELS[direction]}\n"
        f"  금액: {amount:,}{unit}",
        title="환전 확인",
        border_style="yellow",
    ))
    confirm_gate(confirm)
    with KiwoomClient() as c:
        data, _ = c.request("ust31302", {
            "exch_tp": DIRECTION[direction],
            "fc_exmn_amt": str(amount),
        })
        print_generic_table(data, title="환전 신청 결과")
```

(`confirm_gate` prompts "주문을 실행하시겠습니까?" in table mode — acceptable generic wording; preview panel above it names the action as 환전.)

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_order_safety.py -v -k fx_apply && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/commands/us/exchange.py tests/test_order_safety.py
git commit -m "fix(exchange): route fx apply through confirm_gate (json CONFIRMATION_REQUIRED, --yes alias)"
```

---

### Task 7: Credit & gold orders — full safety parity

**Files:**
- Modify: `kiwoom_cli/commands/order.py` (8 commands: credit buy/sell/modify/cancel at lines 480–589, gold buy/sell/modify/cancel at lines 602–697)
- Test: `tests/test_order_safety.py`

**Interfaces:**
- Consumes: `send_order` (Task 2), `_resolve_order_type` (Task 5), existing `_dry_run_kr`, `_kr_price_or_exit`, preview helpers, `confirm_gate`.
- Produces: `--dry-run` + `--client-order-id` on all credit/gold mutations; preview-before-confirm ordering; `--price` as float (consistent with stock orders).

- [ ] **Step 1: Write the failing tests**

```python
# ── Task 7: credit/gold safety parity ────────────────────

def test_credit_buy_dry_run_sends_nothing(runner, isolated_env):
    with patch("kiwoom_cli.commands.order.KiwoomClient") as mock_cls:
        result = runner.invoke(cli, ["-f", "json", "order", "credit", "buy",
                                     "005930", "10", "--price", "70000", "--dry-run"])
    assert result.exit_code == 0
    doc = json.loads(result.output)
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
    doc = json.loads(second.output)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_order_safety.py -v -k "credit or gold"`
Expected: FAIL — `--dry-run`/`--client-order-id` are `no such option` on credit/gold; preview order is inverted.

- [ ] **Step 3: Rewrite the 8 commands.** Final form (replaces lines 480–697 of `order.py`; the read-only gold queries `balance/deposit/executions*/history/pending` below them are untouched):

```python
@credit.command("buy")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_buy(code: str, qty: int, price: float, order_type: str | None, dmst_stex_tp: str, cond_uv: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 매수주문 (kt10006).

    예: kiwoom order credit buy 005930 10 --type limit --price 70000 --confirm
    """
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
        "cond_uv": str(cond_uv) if cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10006", "buy", code, qty, kr_price, order_type, dmst_stex_tp, body,
                    lambda: _show_order_preview("신용 매수", code, qty, kr_price, order_type, dmst_stex_tp))
        return
    _show_order_preview("신용 매수", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10006", body, "신용 매수", client_order_id, client_cls=KiwoomClient)


@credit.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_sell(code: str, qty: int, price: float, order_type: str | None, dmst_stex_tp: str, cond_uv: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 매도주문 (kt10007).

    예: kiwoom order credit sell 005930 10 --type market --confirm
    """
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
        "cond_uv": str(cond_uv) if cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10007", "sell", code, qty, kr_price, order_type, dmst_stex_tp, body,
                    lambda: _show_order_preview("신용 매도", code, qty, kr_price, order_type, dmst_stex_tp))
        return
    _show_order_preview("신용 매도", code, qty, kr_price, order_type, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10007", body, "신용 매도", client_order_id, client_cls=KiwoomClient)


@credit.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=float)
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--cond-price", "mdfy_cond_uv", type=int, default=0, help="정정 조건부가격")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_modify(orig_order_no: str, code: str, qty: int, price: float, dmst_stex_tp: str, mdfy_cond_uv: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 정정주문 (kt10008).

    예: kiwoom order credit modify 0000139 005930 1 70000 --confirm
    """
    kr_price = _kr_price_or_exit(price)
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "mdfy_qty": str(qty),
        "mdfy_uv": str(kr_price),
        "mdfy_cond_uv": str(mdfy_cond_uv) if mdfy_cond_uv else "",
    }
    if dry_run:
        _dry_run_kr("kt10008", "modify", code, qty, kr_price, None, dmst_stex_tp, body,
                    lambda: _show_modify_preview("신용 정정", orig_order_no, code, qty, kr_price, dmst_stex_tp))
        return
    _show_modify_preview("신용 정정", orig_order_no, code, qty, kr_price, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10008", body, "신용 정정", client_order_id, client_cls=KiwoomClient)


@credit.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT", "SOR"]), help="거래소")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def credit_cancel(orig_order_no: str, code: str, qty: int, dmst_stex_tp: str, confirm: bool, dry_run: bool, client_order_id: str | None):
    """신용 취소주문 (kt10009).

    예: kiwoom order credit cancel 0000140 005930 --confirm
    """
    body = {
        "dmst_stex_tp": dmst_stex_tp,
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "cncl_qty": str(qty),
    }
    if dry_run:
        _dry_run_kr("kt10009", "cancel", code, qty, 0, None, dmst_stex_tp, body,
                    lambda: _show_cancel_preview("신용 취소", orig_order_no, code, qty, dmst_stex_tp))
        return
    _show_cancel_preview("신용 취소", orig_order_no, code, qty, dmst_stex_tp)
    confirm_gate(confirm)
    send_order("kt10009", body, "신용 취소", client_order_id, client_cls=KiwoomClient)
```

Gold (same structure; no `--exchange`, previews pass `dmst_stex_tp=None` implicitly):

```python
@gold.command("buy")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_buy(code: str, qty: int, price: float, order_type: str | None, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 매수주문 (kt50000).

    예: kiwoom order gold buy 730060 10 --type limit --price 90000 --confirm
    """
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
    }
    if dry_run:
        _dry_run_kr("kt50000", "buy", code, qty, kr_price, order_type, None, body,
                    lambda: _show_order_preview("금현물 매수", code, qty, kr_price, order_type))
        return
    _show_order_preview("금현물 매수", code, qty, kr_price, order_type)
    confirm_gate(confirm)
    send_order("kt50000", body, "금현물 매수", client_order_id, client_cls=KiwoomClient)


@gold.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략)")
@click.option("--type", "order_type", default=None, type=click.Choice(list(ORDER_TYPES.keys())), help="주문유형 (기본: --price 지정 시 limit, 미지정 시 market)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_sell(code: str, qty: int, price: float, order_type: str | None, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 매도주문 (kt50001).

    예: kiwoom order gold sell 730060 10 --type market --confirm
    """
    order_type = _resolve_order_type(order_type, price)
    kr_price = _kr_price_or_exit(price)
    body = {
        "stk_cd": code,
        "ord_qty": str(qty),
        "ord_uv": str(kr_price) if kr_price else "",
        "trde_tp": ORDER_TYPES[order_type],
    }
    if dry_run:
        _dry_run_kr("kt50001", "sell", code, qty, kr_price, order_type, None, body,
                    lambda: _show_order_preview("금현물 매도", code, qty, kr_price, order_type))
        return
    _show_order_preview("금현물 매도", code, qty, kr_price, order_type)
    confirm_gate(confirm)
    send_order("kt50001", body, "금현물 매도", client_order_id, client_cls=KiwoomClient)


@gold.command("modify")
@click.argument("orig_order_no")
@click.argument("code")
@click.argument("qty", type=int)
@click.argument("price", type=float)
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_modify(orig_order_no: str, code: str, qty: int, price: float, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 정정주문 (kt50002).

    예: kiwoom order gold modify 0000139 730060 1 90000 --confirm
    """
    kr_price = _kr_price_or_exit(price)
    body = {
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "mdfy_qty": str(qty),
        "mdfy_uv": str(kr_price),
    }
    if dry_run:
        _dry_run_kr("kt50002", "modify", code, qty, kr_price, None, None, body,
                    lambda: _show_modify_preview("금현물 정정", orig_order_no, code, qty, kr_price))
        return
    _show_modify_preview("금현물 정정", orig_order_no, code, qty, kr_price)
    confirm_gate(confirm)
    send_order("kt50002", body, "금현물 정정", client_order_id, client_cls=KiwoomClient)


@gold.command("cancel")
@click.argument("orig_order_no")
@click.argument("code")
@click.option("--qty", type=int, default=0, help="취소수량 (0=전량취소)")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
@click.option("--dry-run", "dry_run", is_flag=True, help="전송될 내용만 출력하고 주문을 전송하지 않음")
@click.option("--client-order-id", "client_order_id", default=None, help="멱등성 키 (같은 키 재실행 시 재전송 없이 이전 응답 반환)")
def gold_cancel(orig_order_no: str, code: str, qty: int, confirm: bool, dry_run: bool, client_order_id: str | None):
    """금현물 취소주문 (kt50003).

    예: kiwoom order gold cancel 0000140 730060 --confirm
    """
    body = {
        "orig_ord_no": orig_order_no,
        "stk_cd": code,
        "cncl_qty": str(qty),
    }
    if dry_run:
        _dry_run_kr("kt50003", "cancel", code, qty, 0, None, None, body,
                    lambda: _show_cancel_preview("금현물 취소", orig_order_no, code, qty))
        return
    _show_cancel_preview("금현물 취소", orig_order_no, code, qty)
    confirm_gate(confirm)
    send_order("kt50003", body, "금현물 취소", client_order_id, client_cls=KiwoomClient)
```

Also update the module docstring line 8–10 of `order.py` to reflect the wider coverage:

```python
buy/sell/modify/cancel (주식/신용/금현물/미국) 공통 지원:
  --dry-run           전송될 body를 구성만 하고 전송하지 않음 (--confirm보다 우선)
  --client-order-id   멱등성 키 — 같은 키+같은 내용 재실행 시 재전송 없이 이전 응답
                      반환, 같은 키+다른 내용이면 IDEMPOTENCY_CONFLICT(exit 1)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_order_safety.py -v -k "credit or gold" && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS. Existing credit/gold tests in `tests/test_order.py` (lines 239–313) all pass explicit `--type`/`--confirm`, unaffected by the None-default and reordering.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/commands/order.py tests/test_order_safety.py
git commit -m "feat(order): credit/gold get --dry-run, --client-order-id, preview-first confirm"
```

---

### Task 8: stream/watch honor `--profile` and `KIWOOM_DOMAIN`

**Files:**
- Modify: `kiwoom_cli/config.py` (add `get_domain_key`, refactor `get_domain`)
- Modify: `kiwoom_cli/streaming.py` (add `resolve_ws_target`, use it at lines 300–304)
- Modify: `kiwoom_cli/commands/watch.py` (use it at lines 95–99)
- Test: `tests/test_ws_target.py` (create)

**Interfaces:**
- Consumes: existing `resolve_profile`, `DOMAINS`, `WS_DOMAINS`, click ctx obj `{"profile": ...}` set by `main.py`.
- Produces:
  - `config.get_domain_key(profile: str | None = None) -> str` — returns `"prod"` or `"mock"`; `KIWOOM_DOMAIN` env wins (invalid value → `"mock"`, matching current `get_domain` semantics exactly).
  - `streaming.resolve_ws_target() -> tuple[str, str]` — `(profile, ws_url)` honoring CLI `--profile` from ctx and `KIWOOM_DOMAIN`.

- [ ] **Step 1: Write the failing tests** in new `tests/test_ws_target.py`

```python
"""stream/watch가 --profile과 KIWOOM_DOMAIN을 REST 경로와 동일하게 존중하는지 검증."""

from __future__ import annotations

import click
import pytest

from kiwoom_cli import config, streaming


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


def test_get_domain_key_env_wins(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "prod")
    assert config.get_domain_key() == "prod"


def test_get_domain_key_invalid_env_forces_mock(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "nonsense")
    assert config.get_domain_key() == "mock"


def test_get_domain_still_matches_key(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "prod")
    assert config.get_domain() == config.DOMAINS["prod"]


def test_resolve_ws_target_honors_env(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "prod")
    profile, ws_url = streaming.resolve_ws_target()
    assert profile == "default"
    assert ws_url == streaming.WS_DOMAINS["prod"]


def test_resolve_ws_target_uses_ctx_profile(isolated_config):
    cfg_file = config.CONFIG_FILE
    cfg_file.write_bytes(
        b'[general]\ndefault_profile = "default"\n\n'
        b'[profiles.default]\ndomain = "mock"\n\n'
        b'[profiles.live]\ndomain = "prod"\n'
    )
    ctx = click.Context(click.Command("stream"), obj={"profile": "live"})
    with ctx:
        profile, ws_url = streaming.resolve_ws_target()
    assert profile == "live"
    assert ws_url == streaming.WS_DOMAINS["prod"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ws_target.py -v`
Expected: FAIL — `config` has no `get_domain_key`, `streaming` has no `resolve_ws_target`.

- [ ] **Step 3: Implement `config.get_domain_key`** — replace `get_domain` (config.py lines 91–98) with:

```python
def get_domain_key(profile: str | None = None) -> str:
    """도메인 키('prod'|'mock'). KIWOOM_DOMAIN env > 프로필 설정 > 'mock'.

    잘못된 KIWOOM_DOMAIN 값은 기존 get_domain과 동일하게 mock으로 강제한다
    (실서버로 잘못 붙는 것보다 안전한 방향).
    """
    env = os.environ.get("KIWOOM_DOMAIN")
    if env:
        return env if env in DOMAINS else "mock"
    p = resolve_profile(profile)
    cfg = load_config()
    key = cfg.get("profiles", {}).get(p, {}).get("domain", "mock")
    return key if key in DOMAINS else "mock"


def get_domain(profile: str | None = None) -> str:
    return DOMAINS[get_domain_key(profile)]
```

- [ ] **Step 4: Implement `streaming.resolve_ws_target`** — add right after the `WS_DOMAINS` dict (streaming.py line 62):

```python
def resolve_ws_target() -> tuple[str, str]:
    """(profile, ws_url) — REST 경로와 동일하게 --profile(ctx)과 KIWOOM_DOMAIN을 존중한다."""
    ctx = click.get_current_context(silent=True)
    cli_profile = ctx.obj.get("profile") if ctx is not None and isinstance(ctx.obj, dict) else None
    profile = config.resolve_profile(cli_profile)
    return profile, WS_DOMAINS[config.get_domain_key(profile)]
```

Replace streaming.py lines 300–304 with:

```python
    profile, ws_url = resolve_ws_target()
    token = auth.load_token(profile=profile)
```

- [ ] **Step 5: Rewire `watch.py`** — change the import on line 20 from `from ..streaming import WS_DOMAINS` to:

```python
from ..streaming import resolve_ws_target
```

Replace watch.py lines 95–99 with:

```python
    profile, ws_url = resolve_ws_target()
    token = auth.load_token(profile=profile)
```

If `config` in watch.py's `from .. import auth, config` (line 21) is now unused, change it to `from .. import auth` (ruff will flag it).

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_ws_target.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS (existing `tests/test_stream.py` never exercised profile/domain resolution — verified during review).

- [ ] **Step 7: Commit**

```bash
git add kiwoom_cli/config.py kiwoom_cli/streaming.py kiwoom_cli/commands/watch.py tests/test_ws_target.py
git commit -m "fix(stream/watch): honor --profile and KIWOOM_DOMAIN like the REST client"
```

---

### Task 9: Documentation sync + final verification

**Files:**
- Modify: `AGENTS.md` (error-code table + idempotency semantics)
- Modify: `CLAUDE.md` (order-safety convention line)
- Modify: `CHANGELOG.md` (new Unreleased section)
- Modify: `README.md` (order section: document the `--type` inference)

**Interfaces:** none — docs only.

- [ ] **Step 1: AGENTS.md** — add to the error-code table (alongside CONFIRMATION_REQUIRED / VALIDATION_FAILED):

```markdown
| `IDEMPOTENCY_CONFLICT` | false | 같은 `--client-order-id`가 다른 주문 내용으로 이미 사용됨. 재시도라면 인자가 이전 실행과 동일한지 확인, 새 주문이면 새 키 사용. exit 1, 전송되지 않음. |
```

And in the idempotency description, state the binding: 멱등키는 주문 내용(api_id+body)의 fingerprint에 바인딩되며, 조회→전송→기록 구간은 원장 파일 잠금으로 프로세스 간 직렬화된다.

- [ ] **Step 2: CLAUDE.md** — update the 주문 안전 convention line to:

```markdown
- 주문 안전: 주문 미리보기 → 대화형 확인 (기본, 미리보기가 항상 먼저). `--confirm`으로 생략 (자동화). 모든 buy/sell/modify/cancel(주식/신용/금현물/미국)은 `--dry-run`(전송 없이 body 출력, --confirm보다 우선)과 `--client-order-id`(멱등키 — 같은 키+같은 내용 재실행 시 재전송 없이 이전 응답, 다른 내용이면 IDEMPOTENCY_CONFLICT exit 1; 원장 파일 잠금으로 동시 실행 직렬화) 지원. `--price` 지정 + `--type` 미지정 = limit으로 추론, `--price` + 시장가 계열 --type = INVALID_INPUT. `order validate buy|sell`은 read-only 사전점검 (symbol_ok/market_open/sufficient_balance/price_ok, 실패 시 VALIDATION_FAILED exit 1). `account exchange apply`도 confirm_gate 경유 (json 모드 CONFIRMATION_REQUIRED)
```

- [ ] **Step 3: CHANGELOG.md** — add at the top:

```markdown
## [Unreleased]

### Fixed — 주문 안전 (v2.5.0 전수 리뷰 Tier 1)
- 모든 주문 명령(주식/신용/금현물/미국)에서 주문 **미리보기가 확인 프롬프트보다 먼저** 표시되도록 수정. 미국 주문은 자동 판별된 거래소까지 확인 전에 표시.
- `--price` 지정 + `--type` 미지정 시 **limit으로 추론** (기존: 조용히 시장가 전송). `--price` + 시장가 계열 `--type`은 INVALID_INPUT으로 거부.
- `account exchange apply`(환전)가 공용 confirm_gate를 사용하도록 수정 — json/csv 모드에서 프롬프트 없이 CONFIRMATION_REQUIRED(exit 1), `--yes` 별칭 추가.
- 멱등성 원장 강화: `--client-order-id`가 주문 내용 fingerprint에 바인딩되어 같은 키+다른 주문은 **IDEMPOTENCY_CONFLICT**(exit 1)로 거부. 조회→전송→기록 구간 파일 잠금으로 동시 실행 시 중복 주문 방지.
- `stream`/`watch`가 `--profile`과 `KIWOOM_DOMAIN`을 REST 경로와 동일하게 존중 (기존: 항상 기본 프로필/설정 도메인으로 접속).

### Added
- 신용/금현물 주문에 `--dry-run`, `--client-order-id` 지원 (주식/미국 주문과 동일한 안전장치).
```

- [ ] **Step 4: README.md** — in the order section, add one line under the buy/sell examples:

```markdown
`--price`를 지정하고 `--type`을 생략하면 지정가(limit)로 주문됩니다. 시장가 주문은 `--price` 없이 실행하세요.
```

- [ ] **Step 5: Full verification**

Run: `pytest tests/ -v --tb=short && ruff check kiwoom_cli/`
Expected: all tests PASS, ruff clean. Then run the network-free litmus twin: `pytest tests/test_order.py::test_litmus_loop_json_driven -v` — PASS.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md CLAUDE.md CHANGELOG.md README.md
git commit -m "docs: tier-1 order-safety semantics (IDEMPOTENCY_CONFLICT, type inference, preview-first)"
```

---

## Self-Review Notes

- **Spec coverage:** Tier 1 items → tasks: preview-after-confirm (Tasks 3, 4, 7), `--price` trap (Tasks 5, 7), exchange-apply gate (Task 6), idempotency binding+lock (Tasks 1, 2), stream/watch profile/domain (Task 8), credit/gold parity (Task 7). Docs (Task 9). No gaps.
- **Type consistency:** `send_order(api_id, body, action, client_order_id, *, client_cls)` used identically in Tasks 2, 3, 4, 7. `_resolve_order_type(order_type, price)` defined Task 5, consumed Task 7. `fingerprint/locked/record` defined Task 1, consumed Task 2 only.
- **Known judgment calls:** (a) `client_cls` kwarg exists solely to keep `kiwoom_cli.commands.order.KiwoomClient` / `...us.order_ops.KiwoomClient` as valid test patch targets — do not "simplify" it away; (b) the ledger lock serializes all same-profile orders during send (~seconds) — correctness over throughput for a CLI; (c) US replay-hit now happens after exchange resolution (one cached usa10098 call) — acceptable cost for showing the preview pre-gate.
