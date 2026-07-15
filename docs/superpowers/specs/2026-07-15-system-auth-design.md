# System Authentication for Orders — Design Spec

**Date:** 2026-07-15
**Status:** Approved design
**Target:** standalone change, lands before the US-stocks pass (v2.0)

## 1. Goal

Make the order-safety behavior documented in SECURITY.md and CLAUDE.md true: every
money-moving order requires OS-level system authentication (macOS Touch ID, Windows
LogonUser, Linux PAM) unless the user explicitly opts out with `dangerous-mode on`.
Today the only gate is a `click.confirm` y/n prompt that `--confirm` bypasses entirely.

## 2. Decisions (locked)

| Question | Decision |
|---|---|
| Does `--confirm` skip system auth? | **No.** `--confirm` skips only the y/n prompt. System auth fires on every order unless dangerous-mode is on. This is a deliberate breaking change for automation; scripts fix it once with `config set dangerous-mode on`. |
| Platform mechanism | **Zero new dependencies, ctypes only.** No pyobjc, no python-pam. |
| Auth unavailable or fails | **Fail closed.** Refuse the order, exit code 3 (인증필요), message pointing to interactive use or dangerous-mode. |
| dangerous-mode scope | **Per-profile**, stored in the profile's config.toml section like domain/account. Default off. |
| Auth caching | **None.** Every order authenticates (매 주문 시스템 인증), matching the docs. |

## 3. Gate flow

New public function `authorize_order(confirm: bool) -> None` in a new module
`kiwoom_cli/sysauth.py`:

```
1. y/n prompt ("주문을 실행하시겠습니까?")   — skipped when --confirm
2. resolve profile → read dangerous-mode
   - on  → return (no system auth)
   - off → system_authenticate("주문 실행 승인")
             success → return
             failure/unavailable → err_console message + SystemExit(3)
```

Gated commands (12): `order buy/sell/modify/cancel`, `order credit buy/sell/modify/cancel`,
`order gold buy/sell/modify/cancel`. Each command's existing
`if not confirm: click.confirm(...)` block is replaced by one `authorize_order(confirm)` call.

NOT gated (read-only): `order gold balance/deposit/executions*/history/pending`,
`order condition *`, and all stock/account/market queries.

**Preview ordering fix (included).** Today the y/n prompt fires before the preview panel
(`order.py:129-132`) — the user confirms before seeing what they confirm. New order:
**preview → authorize_order (prompt → system auth) → API call.** The preview helpers
(`_show_order_preview` etc.) move above the gate in each command body.

When the future US order path lands (see `2026-07-03-us-stock-trading-design.md` §5), its
ops functions are called from these same Click commands after the gate, so US orders
inherit this protection with no additional work.

## 4. Platform implementations (`sysauth.py`, ~150 lines total)

`system_authenticate(reason: str) -> bool` dispatches on `sys.platform`. Any exception in
platform glue is caught and returns `False` (caller fails closed). Unknown platform →
`False`.

### macOS — LocalAuthentication via ctypes + objc runtime
- `ctypes.CDLL` on `/usr/lib/libobjc.A.dylib` and the LocalAuthentication framework.
- `LAContext` alloc/init via `objc_msgSend`; evaluate
  `LAPolicyDeviceOwnerAuthentication` (policy 2) — Touch ID with **automatic OS fallback
  to the login password**, so SSH-into-Mac sessions still authenticate.
- `evaluatePolicy:localizedReason:reply:` takes an ObjC block; the block is built by hand
  in ctypes (literal `__NSConcreteStackBlock` struct + C callback) and completion is
  awaited with `threading.Event` (timeout 120 s → False).
- `canEvaluatePolicy:error:` first; if the policy can't be evaluated at all → False.

### Windows — LogonUser via ctypes
- Prompt: username defaults to `getpass.getuser()`, password via `getpass.getpass`.
- `advapi32.LogonUserW(user, ".", pwd, LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT, &token)`.
- Success → `kernel32.CloseHandle(token)`, return True. Failure → False.

### Linux — PAM via ctypes on libpam
- `ctypes.CDLL("libpam.so.0")`; `pam_start("login", user, conv, &handle)` with a
  conversation callback that answers prompts with the password collected once via
  `getpass.getpass`; `pam_authenticate` → 0 means success; `pam_end` always called.
- libpam missing / not loadable → False (fail closed). This satisfies the documented
  "su/PAM" claim via the PAM half; no subprocess, no sudoer requirement.

## 5. Config changes

- `config set` choices gain `dangerous-mode` (`main.py:157`), value validated to
  `on|off`, written to the active profile's section (same code path as domain/account).
- New reader `config.get_dangerous_mode(profile) -> bool`, default False when absent.
- `config show` prints the flag, in red bold when `on`
  (`위험 모드: on — 주문 시스템 인증 비활성화됨`).
- Env vars deliberately NOT supported for this flag (config-file only), consistent with
  the existing rule that security-relevant settings can't come from the environment.

## 6. Error handling & messages

- Auth failure: `err_console` → `시스템 인증 실패 — 주문이 실행되지 않았습니다.` exit 3.
- Auth unavailable (headless, unknown platform, glue error): `err_console` →
  `시스템 인증을 사용할 수 없습니다. 대화형 환경에서 실행하거나 'kiwoom config set
  dangerous-mode on'으로 비활성화하세요. (프로필: {profile})` exit 3.
- y/n prompt declined: unchanged (`click.Abort`, exit 1).
- No API request is ever sent when the gate does not pass.

## 7. Documentation updates

- SECURITY.md: add fail-closed + exit-3 behavior; note Linux mechanism is PAM
  (drop "su" from the claim); keep the dangerous-mode warning.
- CLAUDE.md: update Linux mechanism wording (`su/PAM` → `PAM`).
- README: `--confirm` section gains a note that automation additionally needs
  `config set dangerous-mode on`; flag as breaking change in the next release notes.

## 8. Testing (~10 new tests, `tests/test_sysauth.py`)

All tests mock at the `sysauth.system_authenticate` boundary (and `click.confirm`);
no real OS auth in CI. Platform glue itself is exercised manually per-OS.

- dangerous-mode off + `--confirm` → `system_authenticate` **called** (the core guarantee)
- dangerous-mode on → not called; order proceeds
- auth returns False → exit 3 and `KiwoomClient.request` never invoked
- auth raises → same fail-closed result
- `--confirm` skips the y/n prompt but not auth; no `--confirm` shows prompt first
- gate applies to a stock, a credit, and a gold order command (sample each group)
- read-only gold/condition commands unaffected
- `config set dangerous-mode on` writes the active profile's section;
  `get_dangerous_mode` defaults False
- preview renders before the prompt (output-order assertion)
- regression: existing 40 tests pass unchanged

`ruff check kiwoom_cli/` must pass.

## 9. Files touched

- **New:** `kiwoom_cli/sysauth.py`, `tests/test_sysauth.py`
- **Modified:** `kiwoom_cli/commands/order.py` (12 gate calls + preview reorder),
  `kiwoom_cli/main.py` (config set choice + config show line),
  `kiwoom_cli/config.py` (`get_dangerous_mode`), SECURITY.md, README.md, CLAUDE.md
- **Unchanged:** client, auth/token flow, secure_store, all other command groups

## 10. Out of scope

- Auth-session caching / grace periods
- Gating anything besides the 12 order commands (e.g. future `account exchange apply`
  is specced separately in the US-stocks design)
- Windows Hello biometric UI (LogonUser password check only, per the documented claim)
