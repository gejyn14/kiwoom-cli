# System Auth for Orders — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every money-moving order command requires OS-level system authentication (macOS Touch ID / Windows LogonUser / Linux PAM) unless the active profile has `dangerous-mode on` — making SECURITY.md's documented behavior true.

**Architecture:** A new `kiwoom_cli/sysauth.py` module exposes `authorize_order(confirm)`, which runs the y/n prompt (skipped by `--confirm`) and then platform system auth (skipped only by dangerous-mode). The 12 order commands in `commands/order.py` replace their inline `click.confirm` block with one call. Platform glue is pure ctypes — zero new dependencies. Fail closed: exit code 3.

**Tech Stack:** Python 3.10+, Click, ctypes (objc runtime / advapi32 / libpam), pytest with CliRunner + monkeypatch.

**Spec:** `docs/superpowers/specs/2026-07-15-system-auth-design.md` (approved). Read it before starting.

## Global Constraints

- Python 3.10 compatibility (no 3.11+-only syntax or stdlib).
- Zero new runtime dependencies — ctypes only for platform auth.
- `--confirm` skips ONLY the y/n prompt, never system auth.
- `dangerous-mode` is per-profile, config-file only (no env var), default off.
- Fail closed: auth failure or unavailability → `SystemExit(3)`, no API request sent.
- Exit codes: 0=성공, 1=입력오류(prompt declined), 3=인증필요.
- All user-facing messages in Korean, exact strings as given in each task.
- `ruff check kiwoom_cli/` must pass after every task.
- Work on branch `feature/system-auth` cut from `main` (this is a standalone change, independent of `feature/us-stock-trading`).
- `docs/` is gitignored — commit plan/spec files with `git add -f` if needed; never commit CLAUDE.md (also gitignored).

---

### Task 0: Branch setup

**Files:** none

- [ ] **Step 1: Create the branch**

```bash
cd /Users/yujin-an/dev/kiwoom-cli
git checkout main && git pull && git checkout -b feature/system-auth
```

- [ ] **Step 2: Verify baseline is green**

Run: `pytest tests/ -q && ruff check kiwoom_cli/`
Expected: 40 passed; ruff clean.

---

### Task 1: `dangerous-mode` config support

**Files:**
- Modify: `kiwoom_cli/config.py` (add `get_dangerous_mode` after `get_account`, ~line 127)
- Modify: `kiwoom_cli/main.py:156-170` (`config_set`), and `config_show` (add line after `main.py:153`)
- Test: `tests/test_sysauth.py` (new file)

**Interfaces:**
- Produces: `config.get_dangerous_mode(profile: str | None = None) -> bool` — used by Task 2.
- Produces: CLI `kiwoom config set dangerous-mode on|off`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sysauth.py`:

```python
"""Tests for the system-auth gate (kiwoom_cli/sysauth.py) and dangerous-mode config."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli import config as config_mod
from kiwoom_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point config.toml at a temp file so tests never touch ~/.kiwoom."""
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.toml")
    return tmp_path / "config.toml"


# ============================================================
#  dangerous-mode config
# ============================================================


def test_get_dangerous_mode_defaults_off(isolated_config):
    assert config_mod.get_dangerous_mode("default") is False


def test_config_set_dangerous_mode_on(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "dangerous-mode", "on"])
    assert result.exit_code == 0
    assert config_mod.get_dangerous_mode("default") is True
    assert "경고" in result.output


def test_config_set_dangerous_mode_off_roundtrip(runner, isolated_config):
    runner.invoke(cli, ["config", "set", "dangerous-mode", "on"])
    result = runner.invoke(cli, ["config", "set", "dangerous-mode", "off"])
    assert result.exit_code == 0
    assert config_mod.get_dangerous_mode("default") is False


def test_config_set_dangerous_mode_rejects_bad_value(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "dangerous-mode", "maybe"])
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sysauth.py -v`
Expected: FAIL — `AttributeError: module 'kiwoom_cli.config' has no attribute 'get_dangerous_mode'` and/or Click choice rejection (exit 2) for `dangerous-mode`.

- [ ] **Step 3: Implement**

In `kiwoom_cli/config.py`, after `get_account` (line ~127):

```python
def get_dangerous_mode(profile: str | None = None) -> bool:
    """주문 시스템 인증을 끄는 위험 모드 여부 (기본 off).

    보안 설정이므로 환경변수 오버라이드를 지원하지 않는다 (config 파일 전용).
    """
    p = resolve_profile(profile)
    cfg = load_config()
    return cfg.get("profiles", {}).get(p, {}).get("dangerous-mode", "off") == "on"
```

In `kiwoom_cli/main.py`, replace the `config_set` command (lines 156-170) with:

```python
@config_cmd.command("set")
@click.argument("key", type=click.Choice(["domain", "account", "dangerous-mode"]))
@click.argument("value")
@click.pass_context
def config_set(ctx, key: str, value: str):
    """프로필 설정 변경. (예: kiwoom config set domain prod)"""
    profile = config.resolve_profile(ctx.obj.get("profile") if ctx.obj else None)
    if key == "domain" and value not in ("prod", "mock"):
        console.print("[red]domain은 prod 또는 mock만 가능합니다.[/]")
        raise SystemExit(1)
    if key == "dangerous-mode" and value not in ("on", "off"):
        console.print("[red]dangerous-mode는 on 또는 off만 가능합니다.[/]")
        raise SystemExit(1)
    cfg = config.load_config()
    cfg.setdefault("profiles", {}).setdefault(profile, {})[key] = value
    config.save_config(cfg)
    display = config.DOMAINS[value] if key == "domain" else value
    console.print(f"[green]{key} 변경:[/] {display} (프로필: {profile})")
    if key == "dangerous-mode" and value == "on":
        console.print("[bold red]경고: 주문 시 시스템 인증이 비활성화됩니다. 신뢰할 수 있는 환경에서만 사용하세요.[/]")
```

In `config_show` (`main.py`, directly after the `보안:` line at 153) add:

```python
    if profile_cfg.get("dangerous-mode", "off") == "on":
        console.print("  위험 모드: [bold red]on — 주문 시스템 인증 비활성화됨[/]")
    else:
        console.print("  위험 모드: off")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sysauth.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: all PASS (44 total), ruff clean.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/config.py kiwoom_cli/main.py tests/test_sysauth.py
git commit -m "feat: add per-profile dangerous-mode config flag

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `sysauth.py` gate module + test bypass fixture

**Files:**
- Create: `kiwoom_cli/sysauth.py`
- Modify: `tests/conftest.py` (append autouse fixture)
- Test: `tests/test_sysauth.py` (append)

**Interfaces:**
- Consumes: `config.get_dangerous_mode` (Task 1), `config.resolve_profile`, `output.err_console`.
- Produces: `authorize_order(confirm: bool) -> None` (raises `SystemExit(3)` on auth failure/unavailability, `click.Abort` on declined prompt); `system_authenticate(reason: str) -> bool` (raises `SystemAuthUnavailable`); class `SystemAuthUnavailable(Exception)`; constant `AUTH_REASON = "주문 실행 승인"`. Task 3 imports `authorize_order`; Task 4 fills in the platform functions.

- [ ] **Step 1: Add the test-suite bypass fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def bypass_system_auth(monkeypatch):
    """Default all tests to: system auth succeeds, dangerous-mode off.

    Keeps order tests hermetic (no Touch ID, no ~/.kiwoom reads).
    sysauth-specific tests override these with their own monkeypatch.
    """
    try:
        monkeypatch.setattr("kiwoom_cli.sysauth.system_authenticate", lambda reason: True)
    except (ImportError, AttributeError):
        pass  # sysauth not created yet during early tasks
    monkeypatch.setattr("kiwoom_cli.config.get_dangerous_mode", lambda profile=None: False)
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_sysauth.py`:

```python
# ============================================================
#  authorize_order gate
# ============================================================

from kiwoom_cli import sysauth  # noqa: E402


def test_authorize_order_calls_system_auth_even_with_confirm(monkeypatch):
    calls = []
    monkeypatch.setattr(sysauth, "system_authenticate", lambda reason: calls.append(reason) or True)
    sysauth.authorize_order(confirm=True)
    assert calls == ["주문 실행 승인"]


def test_authorize_order_dangerous_mode_skips_auth(monkeypatch):
    monkeypatch.setattr("kiwoom_cli.config.get_dangerous_mode", lambda profile=None: True)

    def boom(reason):
        raise AssertionError("system auth must not run in dangerous-mode")

    monkeypatch.setattr(sysauth, "system_authenticate", boom)
    sysauth.authorize_order(confirm=True)  # must not raise


def test_authorize_order_fails_closed_on_auth_failure(monkeypatch):
    monkeypatch.setattr(sysauth, "system_authenticate", lambda reason: False)
    with pytest.raises(SystemExit) as exc:
        sysauth.authorize_order(confirm=True)
    assert exc.value.code == 3


def test_authorize_order_fails_closed_when_unavailable(monkeypatch):
    def unavailable(reason):
        raise sysauth.SystemAuthUnavailable("no mechanism")

    monkeypatch.setattr(sysauth, "system_authenticate", unavailable)
    with pytest.raises(SystemExit) as exc:
        sysauth.authorize_order(confirm=True)
    assert exc.value.code == 3


def test_authorize_order_prompts_without_confirm(monkeypatch):
    prompts = []
    monkeypatch.setattr("click.confirm", lambda msg, abort=True: prompts.append(msg))
    monkeypatch.setattr(sysauth, "system_authenticate", lambda reason: True)
    sysauth.authorize_order(confirm=False)
    assert prompts == ["주문을 실행하시겠습니까?"]


def test_system_authenticate_unsupported_platform(monkeypatch):
    monkeypatch.setattr(sysauth.sys, "platform", "sunos5")
    with pytest.raises(sysauth.SystemAuthUnavailable):
        sysauth.system_authenticate("x")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_sysauth.py -v`
Expected: FAIL — `ImportError: cannot import name 'sysauth'`.

- [ ] **Step 4: Create `kiwoom_cli/sysauth.py`**

```python
"""System authentication gate for order commands.

Money-moving orders require OS-level authentication (macOS Touch ID via
LocalAuthentication, Windows LogonUser, Linux PAM) unless the active
profile has dangerous-mode on. --confirm skips only the y/n prompt.
Fail closed: auth failure or unavailability exits with code 3 and no
API request is sent.
"""

from __future__ import annotations

import sys

import click

from . import config
from .output import err_console

AUTH_REASON = "주문 실행 승인"

_MSG_AUTH_FAILED = "시스템 인증 실패 — 주문이 실행되지 않았습니다."
_MSG_AUTH_UNAVAILABLE = (
    "시스템 인증을 사용할 수 없습니다. 대화형 환경에서 실행하거나 "
    "'kiwoom config set dangerous-mode on'으로 비활성화하세요. (프로필: {profile})"
)


class SystemAuthUnavailable(Exception):
    """No OS authentication mechanism can run at all (headless, unsupported OS)."""


def _active_profile() -> str | None:
    ctx = click.get_current_context(silent=True)
    if ctx is not None and isinstance(ctx.obj, dict):
        return ctx.obj.get("profile")
    return None


def authorize_order(confirm: bool) -> None:
    """Gate a money-moving order: y/n prompt, then OS system authentication.

    --confirm skips only the prompt. dangerous-mode on skips system auth.
    """
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)
    profile = config.resolve_profile(_active_profile())
    if config.get_dangerous_mode(profile):
        return
    try:
        ok = system_authenticate(AUTH_REASON)
    except Exception:
        err_console.print(f"[red]{_MSG_AUTH_UNAVAILABLE.format(profile=profile)}[/]")
        raise SystemExit(3) from None
    if not ok:
        err_console.print(f"[red]{_MSG_AUTH_FAILED}[/]")
        raise SystemExit(3)


def system_authenticate(reason: str) -> bool:
    """Run platform authentication. True on success, False on failure.

    Raises SystemAuthUnavailable when no mechanism can run.
    """
    if sys.platform == "darwin":
        return _authenticate_macos(reason)
    if sys.platform == "win32":
        return _authenticate_windows(reason)
    if sys.platform.startswith("linux"):
        return _authenticate_linux(reason)
    raise SystemAuthUnavailable(f"unsupported platform: {sys.platform}")


def _authenticate_macos(reason: str) -> bool:
    raise SystemAuthUnavailable("not implemented")  # Task 4


def _authenticate_windows(reason: str) -> bool:
    raise SystemAuthUnavailable("not implemented")  # Task 4


def _authenticate_linux(reason: str) -> bool:
    raise SystemAuthUnavailable("not implemented")  # Task 4
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_sysauth.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: all PASS, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/sysauth.py tests/conftest.py tests/test_sysauth.py
git commit -m "feat: add system-auth gate module (authorize_order)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Wire the gate into the 12 order commands (+ preview reorder)

**Files:**
- Modify: `kiwoom_cli/commands/order.py`
- Test: `tests/test_sysauth.py` (append)

**Interfaces:**
- Consumes: `authorize_order(confirm)` from Task 2.
- Produces: gated CLI commands; no signature changes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sysauth.py`:

```python
# ============================================================
#  Order command wiring
# ============================================================

from tests.fakes import FakeKiwoomClient  # noqa: E402


@pytest.fixture
def fake_client(monkeypatch):
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.order.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


@pytest.mark.parametrize(
    "argv",
    [
        ["order", "buy", "005930", "1", "--confirm"],
        ["order", "credit", "sell", "005930", "1", "--confirm"],
        ["order", "gold", "buy", "M04020000", "1", "--price", "100000", "--confirm"],
    ],
)
def test_confirm_still_runs_system_auth(runner, fake_client, monkeypatch, argv):
    calls = []
    monkeypatch.setattr(
        "kiwoom_cli.sysauth.system_authenticate",
        lambda reason: calls.append(reason) or True,
    )
    result = runner.invoke(cli, argv)
    assert result.exit_code == 0
    assert calls == ["주문 실행 승인"]
    assert len(fake_client.calls) == 1


def test_auth_failure_blocks_api_call(runner, fake_client, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.sysauth.system_authenticate", lambda reason: False)
    result = runner.invoke(cli, ["order", "buy", "005930", "1", "--confirm"])
    assert result.exit_code == 3
    assert fake_client.calls == []


def test_dangerous_mode_on_skips_auth_for_order(runner, fake_client, monkeypatch):
    monkeypatch.setattr("kiwoom_cli.config.get_dangerous_mode", lambda profile=None: True)

    def boom(reason):
        raise AssertionError("must not auth in dangerous-mode")

    monkeypatch.setattr("kiwoom_cli.sysauth.system_authenticate", boom)
    result = runner.invoke(cli, ["order", "buy", "005930", "1", "--confirm"])
    assert result.exit_code == 0
    assert len(fake_client.calls) == 1


def test_read_only_gold_balance_not_gated(runner, fake_client, monkeypatch):
    def boom(reason):
        raise AssertionError("read-only command must not auth")

    monkeypatch.setattr("kiwoom_cli.sysauth.system_authenticate", boom)
    result = runner.invoke(cli, ["order", "gold", "balance"])
    assert result.exit_code == 0


def test_preview_shown_before_prompt(runner, fake_client, monkeypatch):
    """Declining the prompt must still have shown the preview panel first."""
    result = runner.invoke(cli, ["order", "buy", "005930", "1"], input="n\n")
    assert "주문 확인" in result.output
    assert fake_client.calls == []
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sysauth.py -v`
Expected: the new wiring tests FAIL (`system_authenticate` never called → `calls == []`; preview test fails because today the prompt precedes the preview).

- [ ] **Step 3: Edit `kiwoom_cli/commands/order.py`**

Add to the imports block (after `from ..output import console`):

```python
from ..sysauth import authorize_order
```

Then apply the same mechanical edit to ALL 12 money-moving commands. Each currently begins with:

```python
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_..._preview(<args>)
```

Replace with (preview FIRST, then the gate — same `<args>`, unchanged):

```python
    _show_..._preview(<args>)
    authorize_order(confirm)
```

The 12 functions and their preview calls (line numbers from current HEAD; re-locate with `grep -n "def \|click.confirm" kiwoom_cli/commands/order.py`):

| Function (line) | Preview call to move above the gate |
|---|---|
| `buy` (124) | `_show_order_preview("매수", code, qty, price, order_type, dmst_stex_tp)` |
| `sell` (154) | `_show_order_preview("매도", code, qty, price, order_type, dmst_stex_tp)` |
| `modify` (184) | `_show_modify_preview("정정", orig_order_no, code, qty, price, dmst_stex_tp)` |
| `cancel` (212) | `_show_cancel_preview("취소", orig_order_no, code, qty, dmst_stex_tp)` |
| `credit_buy` (250) | `_show_order_preview("신용매수", code, qty, price, order_type, dmst_stex_tp)` |
| `credit_sell` (280) | `_show_order_preview("신용매도", code, qty, price, order_type, dmst_stex_tp)` |
| `credit_modify` (310) | `_show_modify_preview("신용정정", orig_order_no, code, qty, price, dmst_stex_tp)` |
| `credit_cancel` (338) | `_show_cancel_preview("신용취소", orig_order_no, code, qty, dmst_stex_tp)` |
| `gold_buy` (374) | `_show_order_preview("금현물 매수", code, qty, price, order_type)` |
| `gold_sell` (400) | `_show_order_preview("금현물 매도", code, qty, price, order_type)` |
| `gold_modify` (426) | `_show_modify_preview("금현물 정정", orig_order_no, code, qty, price)` |
| `gold_cancel` (451) | `_show_cancel_preview("금현물 취소", orig_order_no, code, qty)` |

The exact preview labels/args above are indicative — copy each function's OWN existing preview call verbatim; only its position and the confirm-block change. Do NOT touch: `gold_balance`, `gold_deposit`, `gold_executions*`, `gold_history`, `gold_pending`, all `condition` commands (read-only — no gate).

Also update the module docstring (lines 3-4) to:

```
Order commands show a preview, prompt for confirmation (skipped by
--confirm), then require system authentication unless the profile has
dangerous-mode on.
```

- [ ] **Step 4: Run the full suite**

Run: `pytest tests/ -q && ruff check kiwoom_cli/`
Expected: ALL tests pass — including the pre-existing 40 (the conftest autouse fixture from Task 2 keeps them green). If any old order test fails, the wiring or fixture is wrong — do not edit the old tests to make them pass.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/commands/order.py tests/test_sysauth.py
git commit -m "feat: require system auth on all 12 order commands; show preview before prompt

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Platform implementations (ctypes)

**Files:**
- Modify: `kiwoom_cli/sysauth.py` (replace the three stubs)
- Test: covered by existing dispatch/failure tests; platform glue is verified manually (below)

**Interfaces:**
- Consumes: stubs `_authenticate_macos/_windows/_linux` from Task 2.
- Produces: working implementations; each returns `bool` (auth outcome) or raises `SystemAuthUnavailable` (mechanism can't run). No signature changes.

- [ ] **Step 1: Replace `_authenticate_macos`**

```python
def _authenticate_macos(reason: str) -> bool:
    """Touch ID via LocalAuthentication (LAPolicyDeviceOwnerAuthentication).

    Policy 2 falls back to the login password automatically, so SSH
    sessions into a Mac still authenticate. Pure ctypes objc bridge.
    """
    import ctypes
    import ctypes.util
    import threading

    try:
        objc = ctypes.CDLL(ctypes.util.find_library("objc"))
        ctypes.CDLL(
            "/System/Library/Frameworks/LocalAuthentication.framework/LocalAuthentication"
        )
        ctypes.CDLL(ctypes.util.find_library("Foundation"))
    except (OSError, TypeError) as e:
        raise SystemAuthUnavailable(str(e)) from None

    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]

    def send(receiver, selector, *args, restype=ctypes.c_void_p, argtypes=()):
        objc.objc_msgSend.restype = restype
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
        return objc.objc_msgSend(receiver, objc.sel_registerName(selector.encode()), *args)

    la_context = send(send(objc.objc_getClass(b"LAContext"), "alloc"), "init")
    if not la_context:
        raise SystemAuthUnavailable("LAContext init failed")

    POLICY_DEVICE_OWNER_AUTH = 2  # biometrics with OS password fallback
    can = send(
        la_context, "canEvaluatePolicy:error:", POLICY_DEVICE_OWNER_AUTH, None,
        restype=ctypes.c_bool, argtypes=[ctypes.c_long, ctypes.c_void_p],
    )
    if not can:
        raise SystemAuthUnavailable("no evaluatable auth policy")

    ns_reason = send(
        objc.objc_getClass(b"NSString"), "stringWithUTF8String:",
        reason.encode(), argtypes=[ctypes.c_char_p],
    )

    done = threading.Event()
    outcome = {"ok": False}
    ReplyFunc = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_bool, ctypes.c_void_p)

    def _reply(_block, success, _error):
        outcome["ok"] = bool(success)
        done.set()

    reply_cb = ReplyFunc(_reply)

    class BlockDescriptor(ctypes.Structure):
        _fields_ = [("reserved", ctypes.c_ulong), ("size", ctypes.c_ulong)]

    class Block(ctypes.Structure):
        _fields_ = [
            ("isa", ctypes.c_void_p),
            ("flags", ctypes.c_int),
            ("reserved", ctypes.c_int),
            ("invoke", ReplyFunc),
            ("descriptor", ctypes.POINTER(BlockDescriptor)),
        ]

    descriptor = BlockDescriptor(0, ctypes.sizeof(Block))
    stack_block_isa = ctypes.c_void_p.in_dll(ctypes.CDLL(None), "_NSConcreteStackBlock")
    block = Block(
        ctypes.addressof(stack_block_isa), 0, 0, reply_cb, ctypes.pointer(descriptor)
    )

    send(
        la_context, "evaluatePolicy:localizedReason:reply:",
        POLICY_DEVICE_OWNER_AUTH, ns_reason, ctypes.byref(block),
        restype=None, argtypes=[ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p],
    )
    if not done.wait(timeout=120):
        return False
    return outcome["ok"]
```

- [ ] **Step 2: Replace `_authenticate_windows`**

```python
def _authenticate_windows(reason: str) -> bool:
    """Password check against the local account via advapi32 LogonUserW."""
    import ctypes
    import getpass

    user = getpass.getuser()
    err_console.print(f"[yellow]{reason}[/] — Windows 계정 암호를 입력하세요.")
    password = getpass.getpass(f"{user} 암호: ")

    LOGON32_LOGON_INTERACTIVE = 2
    LOGON32_PROVIDER_DEFAULT = 0
    token = ctypes.c_void_p()
    ok = ctypes.windll.advapi32.LogonUserW(
        user, ".", password,
        LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT, ctypes.byref(token),
    )
    if ok:
        ctypes.windll.kernel32.CloseHandle(token)
        return True
    return False
```

- [ ] **Step 3: Replace `_authenticate_linux`**

```python
def _authenticate_linux(reason: str) -> bool:
    """Password check via PAM (libpam conversation), service 'login'."""
    import ctypes
    import ctypes.util
    import getpass

    libpam_path = ctypes.util.find_library("pam")
    if not libpam_path:
        raise SystemAuthUnavailable("libpam not found")
    try:
        libpam = ctypes.CDLL(libpam_path)
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
    except OSError as e:
        raise SystemAuthUnavailable(str(e)) from None

    class PamMessage(ctypes.Structure):
        _fields_ = [("msg_style", ctypes.c_int), ("msg", ctypes.c_char_p)]

    class PamResponse(ctypes.Structure):
        _fields_ = [("resp", ctypes.c_void_p), ("resp_retcode", ctypes.c_int)]

    ConvFunc = ctypes.CFUNCTYPE(
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.POINTER(PamMessage)),
        ctypes.POINTER(ctypes.POINTER(PamResponse)),
        ctypes.c_void_p,
    )

    class PamConv(ctypes.Structure):
        _fields_ = [("conv", ConvFunc), ("appdata_ptr", ctypes.c_void_p)]

    libc.calloc.restype = ctypes.c_void_p
    libc.calloc.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
    libc.strdup.restype = ctypes.c_void_p
    libc.strdup.argtypes = [ctypes.c_char_p]
    libpam.pam_start.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p,
        ctypes.POINTER(PamConv), ctypes.POINTER(ctypes.c_void_p),
    ]
    libpam.pam_authenticate.argtypes = [ctypes.c_void_p, ctypes.c_int]
    libpam.pam_end.argtypes = [ctypes.c_void_p, ctypes.c_int]

    user = getpass.getuser()
    err_console.print(f"[yellow]{reason}[/] — 시스템 계정 암호를 입력하세요.")
    password = getpass.getpass(f"{user} 암호: ").encode()

    PAM_SUCCESS = 0
    PAM_BUF_ERR = 5
    PAM_PROMPT_ECHO_OFF = 1
    PAM_PROMPT_ECHO_ON = 2

    @ConvFunc
    def conv(n, msgs, resp_out, _appdata):
        addr = libc.calloc(n, ctypes.sizeof(PamResponse))
        if not addr:
            return PAM_BUF_ERR
        responses = ctypes.cast(addr, ctypes.POINTER(PamResponse))
        for i in range(n):
            if msgs[i].contents.msg_style in (PAM_PROMPT_ECHO_OFF, PAM_PROMPT_ECHO_ON):
                responses[i].resp = libc.strdup(password)
        resp_out[0] = responses
        return PAM_SUCCESS

    handle = ctypes.c_void_p()
    pam_conv = PamConv(conv, None)
    if libpam.pam_start(b"login", user.encode(), ctypes.byref(pam_conv), ctypes.byref(handle)) != PAM_SUCCESS:
        raise SystemAuthUnavailable("pam_start failed")
    ret = libpam.pam_authenticate(handle, 0)
    libpam.pam_end(handle, ret)
    return ret == PAM_SUCCESS
```

- [ ] **Step 4: Run the suite (glue must not break unit tests)**

Run: `pytest tests/ -q && ruff check kiwoom_cli/`
Expected: all PASS (system_authenticate is bypassed by conftest; these functions never run in CI), ruff clean.

- [ ] **Step 5: Manual verification on macOS (this machine)**

```bash
python3 -c "from kiwoom_cli.sysauth import system_authenticate; print(system_authenticate('테스트'))"
```
Expected: Touch ID dialog appears with reason "테스트"; `True` after fingerprint, `False` after cancel. Then a real end-to-end check against the mock domain:
```bash
kiwoom order buy 005930 1 --price 60000 --type limit --confirm
```
Expected: Touch ID prompt fires BEFORE any API call. Windows/Linux verification happens on those platforms before release (note it in the PR description as an unchecked box).

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/sysauth.py
git commit -m "feat: implement Touch ID / LogonUser / PAM system auth via ctypes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Documentation + final verification

**Files:**
- Modify: `SECURITY.md`, `README.md`, `CLAUDE.md` (CLAUDE.md is gitignored — edit locally, it won't be committed)

**Interfaces:** none (docs only).

- [ ] **Step 1: SECURITY.md**

After line 16 (`- **주문**: 시스템 인증 필수 ...`) insert:

```markdown
- 시스템 인증 실패·사용 불가 시 주문 차단 (fail-closed, exit code 3). `--confirm`은 확인 프롬프트만 생략하며 시스템 인증은 생략하지 않음
```

- [ ] **Step 2: CLAUDE.md**

In the Security section, change `(macOS: Touch ID, Windows: LogonUser, Linux: su/PAM)` to `(macOS: Touch ID, Windows: LogonUser, Linux: PAM)`. Locate with: `grep -n "su/PAM" CLAUDE.md`.

- [ ] **Step 3: README.md**

Locate the `--confirm` / automation section (`grep -n "confirm" README.md`) and add:

```markdown
> **주의 (v1.2 변경):** 주문 명령은 `--confirm` 여부와 관계없이 시스템 인증(macOS Touch ID 등)을 요구합니다.
> 스크립트/자동화 환경에서는 `kiwoom config set dangerous-mode on`으로 프로필 단위 비활성화가 필요합니다.
```

- [ ] **Step 4: Final verification**

Run: `pytest tests/ -q && ruff check kiwoom_cli/`
Expected: all PASS, ruff clean.

- [ ] **Step 5: Commit and open PR**

```bash
git add SECURITY.md README.md
git commit -m "docs: document fail-closed system auth and dangerous-mode migration for automation

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

PR body must flag the breaking change: existing automation using `--confirm` must run `kiwoom config set dangerous-mode on` once per profile. Include the unchecked Windows/Linux manual-verification boxes.
