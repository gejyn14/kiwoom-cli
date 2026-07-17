# Tier 2 Agent-Contract Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the documented agent contract airtight: every error path emits an envelope in json mode with the right exit code, `meta.cont` pagination becomes actionable via global `--next-key`/`--all-pages`, token expiry exits 3, `describe` gains affordable discovery modes, ~80 market.py commands surface their API IDs, and the remaining hidden-interactivity/stdout-purity holes (config setup prompts, stream edge paths, `--fields` typos) are closed. Includes the two Tier-1 code follow-ups (Windows lock error, validate/type-rule alignment).

**Architecture:** One shared `fail_input()` helper in `formatters.py` replaces the ~25 bare `err_console.print + SystemExit(1)` sites. `KiwoomGroup` gains a params-fallback for json-mode detection, an `httpx.RequestError` catch-all, and auth-aware exit codes for `KiwoomAPIError`. Pagination lives in `KiwoomClient.request()` (split into `_request_once` + merge loop) driven by root-level ctx flags. Everything else is localized per file.

**Tech Stack:** Python 3.10+, Click 8, httpx + pytest-httpx, pytest + CliRunner. No new dependencies.

## Global Constraints

- Feature branch off `main`: `git checkout -b feature/v2.6-agent-contract`.
- Every file keeps `from __future__ import annotations`; modern hints (`X | None`, `dict[str, Any]`); no `Optional`/`typing.Dict`.
- All user-facing messages/docstrings Korean; code identifiers English.
- No new third-party dependencies.
- After each task: `ruff check kiwoom_cli/` and `pytest tests/ -q` green before commit.
- Do NOT bump `__version__` (release is a separate flow).
- Envelope-JSON test assertions parse `result.stdout`, NOT `result.output` (Click 8.4.2 mixes stderr into `.output`; established repo pattern).
- New tests for Tasks 1–3, 9, 10 go in a new file `tests/test_contract.py`; Task 4 tests in `tests/test_pagination.py`; Tasks 5–8 add to `tests/test_contract.py`. Shared header for `tests/test_contract.py` (written once in Task 1):

```python
"""Tier-2 agent-contract regression tests (envelope purity, exit codes, discovery, purity long tail)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import click
import httpx
import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.client import KiwoomAPIError
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
```

---

### Task 1: KiwoomGroup contract fixes — json-mode fallback, timeout catch-all, auth exit codes

**Files:**
- Modify: `kiwoom_cli/main.py:40-52` (`_json_mode`, `KiwoomAPIError` handler), `main.py:95-103` (after `ConnectError` handler)
- Test: `tests/test_contract.py` (create with the shared header above)

**Interfaces:**
- Consumes: existing `envelope.classify`, `EXIT_API`/`EXIT_AUTH`.
- Produces: `_json_mode` that works before `ctx.obj` is populated; `httpx.RequestError` → `NETWORK_ERROR` envelope, exit 2; `KiwoomAPIError` with code classifying to `TOKEN_EXPIRED`/`AUTH_REQUIRED` → exit 3.

- [ ] **Step 1: Write the failing tests** (append below the shared header)

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_contract.py -v`
Expected: `test_unknown_command_json_emits_envelope` FAILS (empty stdout today); `test_token_expired_8005_exits_3` FAILS (exit 2 today); `test_read_timeout_...` FAILS (raw traceback, exit 1); `test_api_error_still_exits_2` passes already (regression guard).

- [ ] **Step 3: Implement in `main.py`**

Replace `_json_mode` (lines 40-42):

```python
    @staticmethod
    def _json_mode(ctx) -> bool:
        # 알 수 없는 하위 명령 등 ctx.obj가 채워지기 전의 오류에서도 -f json을 인식해야
        # envelope 계약이 지켜진다 (루트 파라미터는 이미 파싱되어 있음).
        if ctx.obj and ctx.obj.get("format"):
            return ctx.obj["format"] == "json"
        return ctx.params.get("output_format") == "json"
```

Replace the `KiwoomAPIError` handler (lines 47-52):

```python
        except KiwoomAPIError as e:
            stable_code, _ = envelope.classify(upstream_code=e.code)
            auth_related = stable_code in ("TOKEN_EXPIRED", "AUTH_REQUIRED")
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(e.msg, upstream_code=e.code))
            elif auth_related:
                console.print(f"[red]인증 오류:[/] {e} [dim]kiwoom auth login[/]")
            else:
                console.print(f"[red]API 오류:[/] {e}")
            ctx.exit(EXIT_AUTH if auth_related else EXIT_API)
```

Add a new handler immediately AFTER the `httpx.ConnectError` handler (after line 103) and BEFORE `except click.ClickException` (order matters — `ConnectError` is a `RequestError` subclass, so the specific handler must stay first):

```python
        except httpx.RequestError as e:
            # 타임아웃 등 나머지 전송 오류 — traceback 대신 계약대로 종료
            if self._json_mode(ctx):
                envelope.emit(error=envelope.error_body(
                    f"네트워크 오류: {type(e).__name__}. 잠시 후 재시도하세요.",
                    code="NETWORK_ERROR", retryable=True,
                ))
            else:
                console.print(f"[red]네트워크 오류:[/] {type(e).__name__} — 잠시 후 재시도하세요.")
            ctx.exit(EXIT_API)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_contract.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS. If an existing test asserts exit 2 for an 8005-class error, examine it: it is asserting the old buggy contract — amend to exit 3 and note the amendment.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/main.py tests/test_contract.py
git commit -m "fix(main): json-mode fallback for early errors, RequestError catch-all, token-expiry exit 3"
```

---

### Task 2: `fail_input()` helper + sweep of order.py and us/order_ops.py

**Files:**
- Modify: `kiwoom_cli/formatters.py` (add helper at module level, near `human`)
- Modify: `kiwoom_cli/commands/order.py` (7 sites), `kiwoom_cli/commands/us/order_ops.py` (6 sites)
- Test: `tests/test_contract.py`

**Interfaces:**
- Produces (used by Tasks 3, 7, 8): `fail_input(message: str, *, code: str = "INVALID_INPUT") -> None` in `formatters.py` — table mode: red stderr text; json/csv mode: envelope error on stdout (same format branch as `confirm_gate`); always `raise SystemExit(1)`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify RED**

Run: `pytest tests/test_contract.py -v -k "fail_input or json_envelope"`
Expected: the three json tests FAIL (empty stdout today → `json.loads` raises); table test may already pass (guard).

- [ ] **Step 3: Add the helper to `formatters.py`**

Place directly after the `human()` function definition:

```python
def fail_input(message: str, *, code: str = "INVALID_INPUT") -> None:
    """입력 오류 계약 종료: table=stderr 빨간 메시지, json/csv=envelope 오류. exit 1.

    커맨드 본문에서 err_console.print + SystemExit(1) 패턴 대신 사용한다 —
    json 모드에서 stdout이 비는(에이전트가 분기할 수 없는) 종료를 막는다.
    """
    if _get_format() == "table":
        err_console.print(f"[red]{message}[/]")
    else:
        envelope.emit(error=envelope.error_body(message, code=code, retryable=False))
    raise SystemExit(1)
```

(`formatters.py` already imports `envelope`, `err_console`, and defines `_get_format` — verify; add any missing import.)

- [ ] **Step 4: Sweep the sites**

Transformation rule (identical at every site): the two-line pattern

```python
        err_console.print("[red]<메시지>[/]")
        raise SystemExit(1)
```

becomes the single line

```python
        fail_input("<메시지>")
```

with the message string preserved exactly (f-strings stay f-strings). Sites:

`kiwoom_cli/commands/order.py` — add `fail_input` to the `..formatters` import; convert:
- L69-70 (`_kr_price_or_exit`): `fail_input("국내 주문 가격은 정수(원)여야 합니다.")`
- L76-77 (`_kr_type_or_exit`): `fail_input(f"국내주식에서 지원하지 않는 주문유형입니다: {order_type}")`
- L223-224 (buy, cond-price on US): `fail_input("--cond-price는 국내 주문에서만 사용합니다.")`
- L268-269 (sell, same): identical replacement
- L274-275 (sell, --stop on KR): `fail_input("--stop은 미국주식 매도에서만 사용합니다.")`
- L315-316 (modify, cond-price on US): identical to L223 replacement
- L321-322 (modify, --stop on KR): `fail_input("--stop은 미국주식에서만 사용합니다.")`

Do NOT touch order.py L458-459 / L468-469 (validate) — those already emit `VALIDATION_FAILED` envelopes.

`kiwoom_cli/commands/us/order_ops.py` — add `fail_input` to the `...formatters` import; convert:
- L31-32: `fail_input(f"미국주식에서 지원하지 않는 주문유형입니다: {order_type}")`
- L34-35: `fail_input(f"'{order_type}'은(는) 매도 전용 주문유형입니다 (매수 미지원).")`
- L105-106 (`_resolve_or_exit`): `fail_input(str(e))` — note the original has `from None`; the helper raises `SystemExit` internally so the two-line except body becomes just `fail_input(str(e))`
- L141-142: `fail_input(f"'{order_type}' 주문에는 --stop 가격이 필요합니다.")`
- L144-145: `fail_input("--stop은 stop/stop-limit 주문에서만 사용합니다.")`
- L203-204: `fail_input("미국주식은 부분 취소를 지원하지 않습니다 (수량 지정 불가, 전량 취소만 가능).")`

If `err_console` becomes unused in either file, remove it from the import (ruff will flag).

- [ ] **Step 5: Run tests, commit**

Run: `pytest tests/test_contract.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
Expected: PASS. Existing tests that assert these failures via stderr text and exit 1 keep passing (table behavior unchanged).

```bash
git add kiwoom_cli/formatters.py kiwoom_cli/commands/order.py kiwoom_cli/commands/us/order_ops.py tests/test_contract.py
git commit -m "fix(order): input errors emit INVALID_INPUT envelope in json mode via fail_input()"
```

---

### Task 3: fail_input sweep — stock.py, account.py, history.py, main.py config commands

**Files:**
- Modify: `kiwoom_cli/commands/stock.py` (6 sites), `kiwoom_cli/commands/account.py` (5 sites), `kiwoom_cli/commands/history.py` (1 site), `kiwoom_cli/main.py` (config_set 2 sites, config_use 1 site)
- Test: `tests/test_contract.py`

**Interfaces:** Consumes `fail_input` from Task 2.

- [ ] **Step 1: Write the failing tests**

```python
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
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930", "--krw"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"
```

(If `stock info` has no `--krw` option, pick the first stock.py command from the site list below that does — the test must target a real site.)

- [ ] **Step 2: RED**

Run: `pytest tests/test_contract.py -v -k "config_set_invalid or config_use_unknown or krw_on"`
Expected: FAIL — config_set currently prints rich text to *stdout* (non-JSON) and the others produce empty stdout.

- [ ] **Step 3: Sweep**

Same transformation rule as Task 2. Sites:

`kiwoom_cli/commands/stock.py` (import `fail_input` from `..formatters`): L1330-1331, L1368-1369, L1403-1404, L1435-1436, L1467-1468, L1499-1500 — all six are the identical pair `err_console.print("[red]--krw는 미국주식에서만 사용합니다.[/]")` + `raise SystemExit(1)` → `fail_input("--krw는 미국주식에서만 사용합니다.")`.

`kiwoom_cli/commands/account.py` (import `fail_input`): the `err_console.print(...red...)` + `raise SystemExit(1)` pairs at L251, L254, L585, L590, L636 (locate by content; messages preserved verbatim):
- "국내 당일 실현손익은 종목코드가 필요합니다."
- "국내 당일 실현손익에는 국내 종목코드가 필요합니다 (미국 티커는 지원하지 않음)."
- "미국주식 주문가능수량 조회에는 --price가 필요합니다."
- "--price는 숫자여야 합니다."
- "입금/출금 구분(6/7)은 국내 전용입니다. --market us 에서는 사용할 수 없습니다."

(The `[dim]`/graceful-skip `err_console` lines in account.py are NOT errors — leave them.)

`kiwoom_cli/commands/history.py` L261 area: the parquet-dependency failure follows the same pattern → `fail_input(<기존 메시지 그대로>)`.

`kiwoom_cli/main.py` — add `fail_input` to the `.formatters` import (line 22); convert:
- `config_set` L249-251: `fail_input("domain은 prod 또는 mock만 가능합니다.")`
- `config_set` L252-254: `fail_input("token_storage는 keychain 또는 env만 가능합니다.")`
- `config_use` L276-278: `fail_input(f"프로필 '{profile_name}'을(를) 찾을 수 없습니다.")`

Note these three currently print to **stdout** via `console.print` — the conversion also fixes that stdout leak (table mode moves to stderr; acceptable and correct: errors belong on stderr).

- [ ] **Step 4: Run + commit**

Run: `pytest tests/test_contract.py -v && pytest tests/ -q && ruff check kiwoom_cli/`
If existing tests asserted the old config_set/use stdout text, amend them to stderr/envelope expectations and note the amendment.

```bash
git add kiwoom_cli/commands/stock.py kiwoom_cli/commands/account.py kiwoom_cli/commands/history.py kiwoom_cli/main.py tests/test_contract.py
git commit -m "fix(cli): remaining input-error paths emit envelopes; config set/use errors off stdout"
```

---

### Task 4: Global `--next-key` and `--all-pages`

**Files:**
- Modify: `kiwoom_cli/main.py` (root options, lines 115-144)
- Modify: `kiwoom_cli/client.py` (split `request` into `_request_once` + cursor/merge logic; delete dead `request_all`)
- Test: `tests/test_pagination.py` (create)

**Interfaces:**
- Produces: root options `--next-key <key>` (consumed by the FIRST API request of the command) and `--all-pages` (auto-paginate each request, merging list fields; page cap 50 with stderr notice). Mutually exclusive → `click.UsageError`. `meta.cont` reflects the FINAL page's cursor (null when exhausted).

- [ ] **Step 1: Write the failing tests** in new `tests/test_pagination.py`

```python
"""전역 --next-key / --all-pages 페이지네이션 계약 테스트 (client 레벨, pytest-httpx)."""

from __future__ import annotations

import click
import pytest

from kiwoom_cli.client import KiwoomClient


@pytest.fixture
def client(httpx_mock):
    c = KiwoomClient(domain="https://mock.test", token="test-token")
    yield c, httpx_mock
    c.close()


def _page(items, cont=""):
    return {
        "json": {"acnt_evlt_prst": items, "return_code": 0},
        "headers": {"cont-yn": "Y" if cont else "N", "next-key": cont},
    }


def test_all_pages_merges_lists(client):
    c, httpx_mock = client
    p1, p2 = _page([{"n": "1"}], cont="K2"), _page([{"n": "2"}])
    httpx_mock.add_response(json=p1["json"], headers=p1["headers"])
    httpx_mock.add_response(json=p2["json"], headers=p2["headers"])
    ctx = click.Context(click.Command("x"), obj={"all_pages": True})
    with ctx:
        data, headers = c.request("kt00004", {"qry_tp": "0"})
    assert [r["n"] for r in data["acnt_evlt_prst"]] == ["1", "2"]
    assert headers["cont-yn"] != "Y"
    assert ctx.obj["last_cont"] is None


def test_next_key_injected_once(client):
    c, httpx_mock = client
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    ctx = click.Context(click.Command("x"), obj={"next_key": "CURSOR1"})
    with ctx:
        c.request("kt00004", {})
        c.request("kt00004", {})   # 두 번째 요청에는 주입되지 않아야 함
    reqs = httpx_mock.get_requests()
    assert reqs[0].headers.get("next-key") == "CURSOR1"
    assert reqs[0].headers.get("cont-yn") == "Y"
    assert "next-key" not in reqs[1].headers


def test_explicit_cursor_beats_ctx(client):
    c, httpx_mock = client
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    ctx = click.Context(click.Command("x"), obj={"next_key": "CTX"})
    with ctx:
        c.request("kt00004", {}, cont_yn="Y", next_key="EXPLICIT")
    assert httpx_mock.get_requests()[0].headers.get("next-key") == "EXPLICIT"
    assert ctx.obj["next_key"] == "CTX"   # 소비되지 않음
```

Plus one CLI-level exclusivity test in `tests/test_contract.py`:

```python
def test_next_key_and_all_pages_mutually_exclusive(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "--next-key", "X", "--all-pages",
                                 "stock", "info", "005930"])
    assert result.exit_code == 1
    assert _doc(result)["error"]["code"] == "INVALID_INPUT"
```

- [ ] **Step 2: RED** — `pytest tests/test_pagination.py -v` fails (options/flags don't exist; ctx keys ignored).

- [ ] **Step 3: Implement `main.py` root options** — add after the `--fields` option (line 122):

```python
@click.option("--next-key", "next_key", default=None,
              help="연속조회 커서 — 이전 응답 meta.cont.next_key를 전달하면 첫 API 요청이 해당 페이지부터 조회")
@click.option("--all-pages", "all_pages", is_flag=True,
              help="연속조회를 끝까지 자동 반복해 리스트를 병합 (최대 50페이지)")
```

Update the `cli` signature to `def cli(ctx, output_format, profile, fields, no_color, next_key, all_pages):` and add to the body after the `fields` line:

```python
    if next_key and all_pages:
        raise click.UsageError("--next-key와 --all-pages는 함께 사용할 수 없습니다.")
    ctx.obj["next_key"] = next_key
    ctx.obj["all_pages"] = all_pages
```

- [ ] **Step 4: Implement `client.py`**

Rename the existing `request` body (lines 78-117) to `_request_once` (same signature/return, including the `last_cont` ctx bookkeeping), then add a new `request`:

```python
    _ALL_PAGES_CAP = 50

    def request(
        self,
        api_id: str,
        body: dict[str, Any] | None = None,
        *,
        cont_yn: str = "",
        next_key: str = "",
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """단일 요청 + 전역 페이지네이션 플래그 처리.

        --next-key: 명령의 첫 API 요청에만 커서를 주입한다 (소비형).
        --all-pages: cont-yn이 끝날 때까지 반복, 리스트 필드를 병합한다.
        """
        ctx = click.get_current_context(silent=True)
        obj = ctx.obj if ctx is not None and isinstance(ctx.obj, dict) else None
        if obj and not next_key and obj.get("next_key"):
            next_key = obj.pop("next_key")
            cont_yn = "Y"
        data, headers = self._request_once(api_id, body, cont_yn=cont_yn, next_key=next_key)
        if not (obj and obj.get("all_pages")):
            return data, headers
        pages = 1
        while headers.get("cont-yn") == "Y" and headers.get("next-key") and pages < self._ALL_PAGES_CAP:
            page, headers = self._request_once(api_id, body, cont_yn="Y", next_key=headers["next-key"])
            for k, v in page.items():
                if isinstance(v, list) and isinstance(data.get(k), list):
                    data[k].extend(v)
            pages += 1
        if headers.get("cont-yn") == "Y":
            err_console.print(f"[dim]--all-pages 상한({self._ALL_PAGES_CAP}페이지) 도달 — meta.cont로 계속 조회 가능[/]")
        return data, headers
```

Delete the dead `request_all` method (lines 119-143). Grep `tests/` for `request_all`; if tests exist for it, delete them too (authorized — the method has zero CLI callers) and note the amendment.

- [ ] **Step 5: Run + commit**

Run: `pytest tests/test_pagination.py tests/test_contract.py -v && pytest tests/ -q && ruff check kiwoom_cli/`

```bash
git add kiwoom_cli/main.py kiwoom_cli/client.py tests/test_pagination.py tests/test_contract.py
git commit -m "feat(cli): global --next-key and --all-pages make meta.cont actionable on every command"
```

---

### Task 5: `describe --paths` and `--depth`

**Files:**
- Modify: `kiwoom_cli/main.py` (describe command, lines 515-537; `_describe_command`, lines 477-490)
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    for sub in top.get("subcommands", []):
        assert "subcommands" not in sub or sub["subcommands"] == []
        assert "options" not in sub or sub.get("path")  # 1단계 하위는 요약형


def test_describe_full_tree_still_default(runner, isolated_env):
    result = runner.invoke(cli, ["-f", "json", "describe", "order", "buy"])
    assert result.exit_code == 0
    spec = _doc(result)["data"]
    assert any(o["name"] == "client_order_id" for o in spec["options"])
```

- [ ] **Step 2: RED** — the first two fail (`--paths`/`--depth` don't exist).

- [ ] **Step 3: Implement**

Change `_describe_command` to accept a depth limit:

```python
def _describe_command(cmd: click.Command, path: str, depth: int | None = None) -> dict:
    spec: dict = {
        "path": path,
        "help": (cmd.help or cmd.short_help or "").strip(),
        "arguments": [_param_spec(p) for p in cmd.params if isinstance(p, click.Argument)],
        "options": [_param_spec(p) for p in cmd.params if isinstance(p, click.Option)],
    }
    if isinstance(cmd, click.Group):
        if depth is not None and depth <= 0:
            spec["subcommands"] = []
        else:
            next_depth = None if depth is None else depth - 1
            spec["subcommands"] = [
                _describe_command(sub, f"{path} {name}", next_depth)
                for name, sub in sorted(cmd.commands.items())
                if not sub.hidden
            ]
    return spec


def _collect_paths(cmd: click.Command, path: str) -> list[dict]:
    head = ((cmd.help or cmd.short_help or "").strip().splitlines() or [""])[0]
    rows = [{"path": path, "help": head}]
    if isinstance(cmd, click.Group):
        for name, sub in sorted(cmd.commands.items()):
            if not sub.hidden:
                rows.extend(_collect_paths(sub, f"{path} {name}"))
    return rows
```

Update the `describe` command:

```python
@cli.command("describe")
@click.argument("command_path", nargs=-1)
@click.option("--paths", "paths_only", is_flag=True,
              help="경로+한줄설명 평면 목록만 출력 (전체 트리 대비 토큰 절약 — 발견용)")
@click.option("--depth", type=int, default=None,
              help="하위 명령 재귀 깊이 제한 (예: --depth 1 = 한 단계만)")
def describe(command_path: tuple[str, ...], paths_only: bool, depth: int | None):
    """CLI 명령 구조 자기서술 — 경로/도움말/인자/옵션(타입·기본값·choices).

    에이전트가 도구 스키마를 파악할 때 사용합니다.

    \b
    예: kiwoom describe --paths -f json   # 전체 경로 목록 (저비용 발견)
        kiwoom describe order buy -f json # 단일 명령 상세 스키마
        kiwoom describe order --depth 1
    """
    cmd: click.Command = cli
    path = "kiwoom"
    for name in command_path:
        if not isinstance(cmd, click.Group) or name not in cmd.commands:
            raise click.ClickException(f"명령을 찾을 수 없습니다: {' '.join(command_path)}")
        cmd = cmd.commands[name]
        path += f" {name}"
    if paths_only:
        rows = _collect_paths(cmd, path)
        if _get_format() == "json":
            envelope.emit(data=rows)
            return
        for r in rows:
            console.print(f"[bold]{r['path']}[/]  [dim]{r['help']}[/]", highlight=False)
        return
    spec = _describe_command(cmd, path, depth)
    if _get_format() == "json":
        envelope.emit(data=spec)
        return
    _render_describe(spec)
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/test_contract.py -v -k describe && pytest tests/ -q && ruff check kiwoom_cli/`

```bash
git add kiwoom_cli/main.py tests/test_contract.py
git commit -m "feat(describe): --paths flat discovery mode and --depth recursion limit"
```

---

### Task 6: market.py docstring API IDs (describe coverage for ~80 commands)

**Files:**
- Modify: `kiwoom_cli/commands/market.py` (every command whose docstring lacks an API ID)
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: RED** — the test fails listing ~80 paths.

- [ ] **Step 3: Implement the sweep**

Rule, applied to every leaf command function in `market.py`: the API ID is the first argument of the `c.request("...")` call inside the function body. Append it to the docstring's first line in the standard format. Example transformation:

```python
# before
def rank_new_highlow(...):
    """신고저가 순위."""
# after
def rank_new_highlow(...):
    """신고저가 순위. (ka10016)"""
```

If a command makes multiple `c.request` calls with different IDs, list the primary (first) one. Do not change any code, only docstring first lines. The `# ── kaXXXXX ──` section comments stay as they are.

- [ ] **Step 4: Run + commit**

Run: `pytest tests/test_contract.py -v -k market_commands && pytest tests/ -q && ruff check kiwoom_cli/`

```bash
git add kiwoom_cli/commands/market.py tests/test_contract.py
git commit -m "docs(market): every command docstring carries its API ID (describe coverage)"
```

---

### Task 7: json-purity long tail — config setup/set/use, account list, stream types

**Files:**
- Modify: `kiwoom_cli/main.py` (`config_setup` lines 178-211, `config_set` success line 258-259, `config_use` success line 279-280)
- Modify: `kiwoom_cli/commands/account.py` (list command, line ~99)
- Modify: `kiwoom_cli/commands/stream.py` (types command, line ~249-262)
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: RED** — setup prompts today (Click `prompt=`), set/use/types print non-envelope output.

- [ ] **Step 3: Implement**

`config_setup`: remove all `prompt=` attributes from its five options; make `appkey`/`secretkey` `default=None` and the rest keep their current defaults (`domain="mock"`, `account=""`, `token_storage="keychain"`, but `domain`/`token_storage` become `default=None` so we can distinguish "given" from "prompt me" in table mode). New body top and tail:

```python
def config_setup(profile: str, appkey: str | None, secretkey: str | None,
                 domain: str | None, account: str, token_storage: str | None):
    """초기 설정 (App Key, Secret Key, 도메인)."""
    interactive = _get_format() == "table"
    if not interactive:
        missing = [n for n, v in (("--appkey", appkey), ("--secretkey", secretkey)) if not v]
        if missing:
            fail_input("config setup 필수 옵션 누락: " + ", ".join(missing))
        domain = domain or "mock"
        token_storage = token_storage or "keychain"
    else:
        if appkey is None:
            appkey = click.prompt("App Key", err=True)
        if secretkey is None:
            secretkey = click.prompt("Secret Key", hide_input=True, err=True)
        if domain is None:
            domain = click.prompt("도메인 (prod=실거래, mock=모의투자)",
                                  type=click.Choice(["prod", "mock"]), default="mock", err=True)
        if not account:
            account = click.prompt("계좌번호 (없으면 Enter)", default="", err=True)
        if token_storage is None:
            token_storage = click.prompt(
                "토큰 저장 방식 (keychain=OS 키체인, env=KIWOOM_TOKEN 직접 관리)",
                type=click.Choice(list(config.TOKEN_STORAGES)), default="keychain", err=True)
    # ...기존 저장 로직 그대로 (legacy purge, set_appkey/set_secretkey, cfg 저장)...
    if _get_format() == "json":
        envelope.emit(data={
            "profile": profile, "domain": domain,
            "account": account or "", "token_storage": token_storage,
        })
        return
    # ...기존 console.print 성공 출력 그대로...
```

(`account` keeps `default=""`; prompts move to stderr via `err=True` — table UX text unchanged.)

`config_set` success (after save): 

```python
    if _get_format() == "json":
        envelope.emit(data={"key": key, "value": value, "profile": profile})
        return
    console.print(f"[green]{key} 변경:[/] {display} (프로필: {profile})")
```

`config_use` success: same pattern with `data={"default_profile": profile_name}`.

`account list` (~account.py:99): replace the bare `click.echo(f"계좌번호: {acct}")` path with json branch `envelope.emit(data={"account": acct})` / table branch `human(f"계좌번호: {acct}")` (check surrounding code for the exact variable; keep the not-configured error path via `fail_input`).

`stream types` (stream.py:249-262): before building the Rich table, add:

```python
    if _get_format() == "json":
        envelope.emit(data=[
            {"type": code, "name": name, "description": desc}
            for code, (name, desc) in REALTIME_TYPES.items()
        ])
        return
```

(import `envelope` + `_get_format` as needed; `REALTIME_TYPES` comes from `..streaming`.)

- [ ] **Step 4: Run + commit** — full suite; amend any test asserting the old prompt/echo behavior (note amendments).

```bash
git add kiwoom_cli/main.py kiwoom_cli/commands/account.py kiwoom_cli/commands/stream.py tests/test_contract.py
git commit -m "fix(cli): config setup/set/use, account list, stream types honor the json envelope; setup never prompts in json mode"
```

---

### Task 8: stream edge paths — Ctrl+C stderr, missing websockets, --raw×json

**Files:**
- Modify: `kiwoom_cli/streaming.py` (three sites, locate by content)
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing test** (the testable one; the other two verified by code review + existing stream tests)

```python
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
```

- [ ] **Step 2: RED** — currently prints a message and returns exit 0.

- [ ] **Step 3: Implement** (locate each by content in streaming.py)

(a) Missing-dependency block (`except ImportError:` after `import websockets`, ~line 294-298) becomes:

```python
    try:
        import websockets
    except ImportError:
        msg = "websockets 패키지가 필요합니다: pip install websockets"
        if json_mode:
            _emit_line(error=envelope.error_body(msg, code="DEPENDENCY_MISSING", retryable=False))
        else:
            err_console.print(f"[red]{msg}[/]")
        raise SystemExit(1)
```

(b) Ctrl+C shutdown notice (`console.print` of "스트리밍 종료" ~line 463): change `console.print(...)` → `err_console.print(...)` so NDJSON stdout stays pure.

(c) `--raw` in json mode: at the top of the streaming entry function (where `json_mode = _get_format() == "json"` is computed, ~line 280), if the function receives a `raw` flag parameter, add:

```python
    if raw and json_mode:
        _emit_line(error=envelope.error_body(
            "--raw는 json 모드와 함께 사용할 수 없습니다 (NDJSON 한 줄 계약 위반).",
            code="INVALID_INPUT", retryable=False))
        raise SystemExit(1)
```

If `raw` is not a parameter of this function (it may live in a specific stream subcommand), apply the same guard where the flag is handled (grep `--raw` in streaming.py/commands/stream.py) — same code, same message.

- [ ] **Step 4: Run + commit**

```bash
git add kiwoom_cli/streaming.py kiwoom_cli/commands/stream.py tests/test_contract.py
git commit -m "fix(stream): edge paths honor the contract (dep error envelope+exit 1, Ctrl+C to stderr, --raw json rejected)"
```

---

### Task 9: `--fields` unmatched warning (`meta.fields_unmatched`)

**Files:**
- Modify: `kiwoom_cli/envelope.py` (`emit`, lines 127-141)
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: RED** — `fields_unmatched` doesn't exist.

- [ ] **Step 3: Implement in `envelope.py`**

Add a collector and wire it into `emit`:

```python
def _collect_matched(data: Any, fields: list[str], found: set[str]) -> None:
    if isinstance(data, list):
        for x in data:
            _collect_matched(x, fields, found)
    elif isinstance(data, dict):
        for k, v in data.items():
            if k in fields:
                found.add(k)
            _collect_matched(v, fields, found)
```

In `emit`, replace the projection block:

```python
    fields = obj.get("fields")
    unmatched: list[str] = []
    if fields and data is not None:
        data = project_fields(data, fields)
        found: set[str] = set()
        _collect_matched(data, fields, found)
        unmatched = sorted(set(fields) - found)
    meta = build_meta()
    if unmatched:
        meta["fields_unmatched"] = unmatched
    doc = {
        "ok": error is None,
        "schema": SCHEMA,
        "data": data,
        "meta": meta,
        "error": error,
    }
    click.echo(json.dumps(doc, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Run + commit**

```bash
git add kiwoom_cli/envelope.py tests/test_contract.py
git commit -m "feat(envelope): meta.fields_unmatched warns when --fields keys match nothing"
```

---

### Task 10: Tier-1 follow-ups — Windows lock busy error, validate type-rule alignment

**Files:**
- Modify: `kiwoom_cli/idempotency.py` (`locked()`), `kiwoom_cli/commands/_mutation.py` (`send_order`)
- Modify: `kiwoom_cli/commands/order.py` (`validate`, lines ~394-412)
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: RED** — lock OSError today produces a traceback; validate accepts market+price.

- [ ] **Step 3: Implement**

`idempotency.py` — add an exception class and wrap acquisition inside `locked()`:

```python
class LedgerLockBusy(Exception):
    """원장 잠금을 제한시간 내 획득하지 못함 (Windows msvcrt ~10초 재시도 후)."""
```

In `locked()`, change `_acquire(f)` to:

```python
        try:
            _acquire(f)
        except OSError as e:
            raise LedgerLockBusy(str(e)) from e
```

`_mutation.py` `send_order` — wrap the `with idempotency.locked():` block:

```python
    try:
        with idempotency.locked():
            ...  # 기존 블록 그대로
    except idempotency.LedgerLockBusy:
        msg = ("멱등성 원장 잠금을 획득하지 못했습니다 — 같은 프로필의 다른 주문이 "
               "전송 중입니다. 잠시 후 재시도하세요.")
        if _get_format() == "table":
            err_console.print(f"[red]{msg}[/]")
        else:
            envelope.emit(error=envelope.error_body(msg, code="LEDGER_BUSY", retryable=True))
        raise SystemExit(2)
```

(Indent the existing block one level; nothing else inside changes.)

`order.py` `validate` — change its `--type` option to `default=None` with the same help text as buy/sell, annotation `order_type: str | None`, and insert as the first statement of the function body:

```python
    order_type = _resolve_order_type(order_type, price)
```

- [ ] **Step 4: Run + commit**

```bash
git add kiwoom_cli/idempotency.py kiwoom_cli/commands/_mutation.py kiwoom_cli/commands/order.py tests/test_contract.py
git commit -m "fix(order): typed LEDGER_BUSY on lock timeout; validate applies the --price/--type rules"
```

---

### Task 11: Docs sync + final verification

**Files:**
- Modify: `AGENTS.md`, `README.md`, `CHANGELOG.md` (CLAUDE.md on disk only, uncommitted per convention)

- [ ] **Step 1: AGENTS.md**
  - Error-code table: add rows for `NOT_CONFIGURED` (설정 필요 — `kiwoom config setup`; exit 1), `KEYCHAIN_UNAVAILABLE` (키체인 접근 불가 — `KIWOOM_TOKEN` 사용; exit 1), `NETWORK_ERROR` covers timeouts now (retryable ✓, exit 2), `LEDGER_BUSY` (원장 잠금 경합 — 재시도; retryable ✓, exit 2), `DEPENDENCY_MISSING` (exit 1).
  - Exit-code table: note that `TOKEN_EXPIRED`(8005) now exits 3.
  - Pagination section: `meta.cont.next_key` → 재조회는 전역 `--next-key <값>`; 전체 수집은 `--all-pages` (리스트 병합, 최대 50페이지, 상한 도달 시 stderr 안내 + meta.cont 유지).
  - Discovery: `kiwoom describe --paths -f json` (저비용 경로 목록) / `--depth N`; market 명령 docstring에 API ID 포함됨.
  - `--fields`: 요청 키가 하나도 매칭되지 않으면 `meta.fields_unmatched`로 표시됨.
  - Idempotency: 미국 주문 재실행 시 거래소 자동판별이 달라지면 body가 달라져 `IDEMPOTENCY_CONFLICT`가 날 수 있음 (의도된 동작 — 같은 주문인지 확인 후 새 키 사용).
- [ ] **Step 2: CHANGELOG.md** — new `## [Unreleased]` section listing: 전역 `--next-key`/`--all-pages`; 입력 오류 전면 envelope화(`fail_input`); 8005 → exit 3; httpx 타임아웃 → NETWORK_ERROR; `describe --paths/--depth`; market 명령 API ID 노출; config setup 비대화형 지원(json 모드 프롬프트 제거); stream 엣지 경로 계약 준수; `meta.fields_unmatched`; `LEDGER_BUSY`; validate --price/--type 규칙 적용. Breaking 표시: `-f json`에서 config set/use 오류·성공 출력이 envelope로 변경, 8005 exit code 2→3.
- [ ] **Step 3: README.md** — 에이전트 섹션에 `--all-pages`/`--next-key`와 `describe --paths` 예시 한 줄씩 추가.
- [ ] **Step 4: CLAUDE.md (disk only)** — conventions 줄 갱신: exit 3에 토큰 만료 포함; 전역 옵션에 `--next-key`/`--all-pages` 추가; `fail_input` 사용 규칙 한 줄 ("커맨드의 입력 오류는 formatters.fail_input 사용 — err_console+SystemExit 금지").
- [ ] **Step 5: Full verification** — `pytest tests/ -v --tb=short`, `ruff check kiwoom_cli/`, `pytest tests/test_order.py::test_litmus_loop_json_driven -v`, and a describe sanity: `python -m kiwoom_cli.main -f json describe --paths | head -5`.
- [ ] **Step 6: Commit**

```bash
git add AGENTS.md README.md CHANGELOG.md
git commit -m "docs: tier-2 agent-contract semantics (pagination, error codes, discovery modes)"
```

---

## Self-Review Notes

- **Coverage vs Tier-2 findings:** pagination H2→Task 4; fail_input sweep H4/M2→Tasks 2-3; 8005 H3→Task 1; describe H5→Task 5; timeout M3→Task 1; unknown-command M1→Task 1; config setup prompts M8→Task 7; purity long tail M6→Task 7; stream edges M9→Task 8; fields typo M4→Task 9; market docstrings→Task 6; Tier-1 follow-ups→Task 10; docs→Task 11. Not in scope (deferred deliberately): `--compact`/`--no-raw` token economy, `find`/`api list` (roadmap step 4), account masking (Tier-4/roadmap).
- **Type consistency:** `fail_input(message, *, code="INVALID_INPUT")` defined Task 2, consumed Tasks 3/7/8; `_request_once` private to client.py; `LedgerLockBusy` defined and consumed in Task 10 only.
- **Known judgment calls:** (a) `--next-key` is consume-once (first request of the command) — documented in help text and AGENTS.md; multi-request commands paginate only their first call, which matches how cursors are minted; (b) `--all-pages` merges only list-typed fields, scalar fields keep page-1 values — same semantics the dead `request_all` had; (c) config setup prompts move to stderr (`err=True`) — cosmetic table change, required for stdout purity; (d) `LEDGER_BUSY` exits 2 (transient class), not 1.
- **Line numbers** for stock.py/account.py/streaming.py sites may drift; every site is also identified by its exact message string — locate by content.
