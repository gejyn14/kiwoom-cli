# US Stock Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US stock trading (29 REST APIs) folded natively into the existing command tree — `kiwoom order buy NVDA 10 --price 213.04` works exactly like a Korean order, and `kiwoom account balance` shows one unified KR+US account view.

**Architecture:** Symbol-shape auto-detection routes commands (6-digit numeric → KR, alpha ticker → US) with `--exchange` as override. US logic lives in a new `kiwoom_cli/commands/us/` package as plain functions; existing Click commands gain a thin dispatch branch at the top. Account views merge both markets by default with `--market kr|us` filters and graceful degradation. Exchange codes auto-resolve via usa10098 with a JSON file cache.

**Tech Stack:** Python 3.10+, Click, httpx (existing KiwoomClient), Rich, pytest + CliRunner + tests/fakes.FakeKiwoomClient.

**Spec:** `docs/superpowers/specs/2026-07-03-us-stock-trading-design.md` (approved, rev 2 + post-review edits). Order safety = existing interactive confirm + `--confirm` ONLY (Touch ID / system auth was rejected — do not add it).

## Global Constraints

- Python 3.10 compatibility (no 3.11+-only syntax; `from __future__ import annotations` in every new module).
- Zero new runtime dependencies.
- Branch: `feature/us-stock-trading` (already checked out). Baseline: **155 tests green**, ruff clean.
- Venv at `.venv` — always `.venv/bin/pytest` and `.venv/bin/ruff` (bare commands not on PATH).
- `ruff check kiwoom_cli/` must pass after every task.
- Option maps live in constants modules — NO inline dicts inside functions (project convention).
- All user-facing text Korean; exit codes 0=성공, 1=입력오류, 2=API오류, 3=인증필요.
- Color convention: 상승=red, 하락=blue (`_sign_color`).
- US exchange CLI values are lowercase `nasdaq|nyse|amex` (human-readable convention); API codes `ND|NY|NA`; `%`=all (list APIs only).
- Existing KR behavior MUST NOT change: default `--exchange` resolution stays KRX, KR order bodies stay integer-price strings, all 155 existing tests pass unmodified.
- Every US API call goes through the existing `c.request("api_id", {body})` — never raw httpx.
- Commit trailer: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- `docs/` is gitignored — plan/spec commits need `git add -f`. Never commit CLAUDE.md or `.serena/`.
- New tests go in `tests/test_us.py` (Tasks 1–8) and `tests/test_us_account.py` (Tasks 9–11).

## File Structure

```
kiwoom_cli/
├── api_spec.py                 # MODIFY: +29 US API registrations
├── formatters.py               # MODIFY: _fmt_usd, _USD_FIELDS, labels, print_unified_balance
└── commands/
    ├── order.py                # MODIFY: dispatch + float price + --stop + broadened --exchange
    ├── stock.py                # MODIFY: dispatch in info/price/orderbook/search/chart*
    ├── account.py              # MODIFY: --market unified views + exchange subgroup wiring
    └── us/
        ├── __init__.py         # re-exports ops modules + exchange_group
        ├── _constants.py       # US_EXCHANGE, KR_EXCHANGE, US_ORDER_TYPES (+allowed sets)
        ├── detect.py           # is_us_symbol, resolve_us_exchange + file cache
        ├── order_ops.py        # buy/sell/modify/cancel/orderable
        ├── stock_ops.py        # info/price/orderbook/search/chart
        ├── account_ops.py      # fetch_balance + US account section printers
        └── exchange.py         # `account exchange` Click subgroup (rate/estimate/apply)
```

---

### Task 1: Register 29 US APIs in `api_spec.py`

**Files:**
- Modify: `kiwoom_cli/api_spec.py` (append new section before the closing `}` of `API_REGISTRY`)
- Test: `tests/test_us.py` (new file)

**Interfaces:**
- Produces: `API_REGISTRY` entries for every `usa*`/`ust*` ID below. All later tasks call `c.request()` with these IDs.

- [ ] **Step 1: Write the failing test**

Create `tests/test_us.py`:

```python
"""Tests for US stock trading (kiwoom_cli/commands/us/)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.api_spec import API_REGISTRY
from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


# ============================================================
#  Task 1: API registry
# ============================================================

US_API_URLS = {
    "ust20000": "/api/us/ordr", "ust20001": "/api/us/ordr",
    "ust20002": "/api/us/ordr", "ust20003": "/api/us/ordr",
    "ust31490": "/api/us/ordr",
    "ust21070": "/api/us/acnt", "ust21160": "/api/us/acnt",
    "ust21110": "/api/us/acnt", "ust21530": "/api/us/acnt",
    "ust21170": "/api/us/acnt", "ust21050": "/api/us/acnt",
    "ust21150": "/api/us/acnt", "ust21510": "/api/us/acnt",
    "ust21180": "/api/us/acnt", "ust21100": "/api/us/acnt",
    "usa10098": "/api/us/stkinfo", "usa10099": "/api/us/stkinfo",
    "usa10100": "/api/us/stkinfo",
    "usa20100": "/api/us/mrkcond", "usa20101": "/api/us/mrkcond",
    "usa06010": "/api/us/chart", "usa06011": "/api/us/chart",
    "usa06012": "/api/us/chart", "usa06013": "/api/us/chart",
    "usa06014": "/api/us/chart", "usa06015": "/api/us/chart",
    "ust31300": "/api/us/exchange", "ust31301": "/api/us/exchange",
    "ust31302": "/api/us/exchange",
}


def test_us_apis_registered():
    for api_id, url in US_API_URLS.items():
        assert api_id in API_REGISTRY, f"{api_id} missing"
        assert API_REGISTRY[api_id][0] == url, f"{api_id} wrong URL"


def test_us_apis_have_korean_descriptions():
    for api_id in US_API_URLS:
        desc = API_REGISTRY[api_id][1]
        assert desc, f"{api_id} has empty description"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_us.py -v`
Expected: FAIL — `AssertionError: ust20000 missing`

- [ ] **Step 3: Implement**

In `kiwoom_cli/api_spec.py`, inside `API_REGISTRY` just before its closing `}`, append:

```python
    # === 미국주식 주문 (US Orders) ===
    "ust20000": ("/api/us/ordr", "미국주식 매수 주문"),
    "ust20001": ("/api/us/ordr", "미국주식 매도 주문"),
    "ust20002": ("/api/us/ordr", "미국주식 정정 주문"),
    "ust20003": ("/api/us/ordr", "미국주식 취소 주문"),
    "ust31490": ("/api/us/ordr", "미국주식 주문가능수량"),
    # === 미국주식 계좌 (US Account) ===
    "ust21070": ("/api/us/acnt", "미국주식 원장잔고확인"),
    "ust21160": ("/api/us/acnt", "미국주식 예수금 상세"),
    "ust21110": ("/api/us/acnt", "해외주식 예수금"),
    "ust21530": ("/api/us/acnt", "미국주식 실현손익"),
    "ust21170": ("/api/us/acnt", "미국주식 당일 종목별 실현손익"),
    "ust21050": ("/api/us/acnt", "미국주식 원장 미체결"),
    "ust21150": ("/api/us/acnt", "미국주식 일별 주문체결내역"),
    "ust21510": ("/api/us/acnt", "미국주식 당일 주문체결 확인"),
    "ust21180": ("/api/us/acnt", "미국주식 기간별 주문내역"),
    "ust21100": ("/api/us/acnt", "미국주식 거래내역"),
    # === 미국주식 종목정보 (US Stock Info) ===
    "usa10098": ("/api/us/stkinfo", "미국주식 거래소구분 조회"),
    "usa10099": ("/api/us/stkinfo", "미국주식 종목리스트"),
    "usa10100": ("/api/us/stkinfo", "미국주식 종목 조회"),
    # === 미국주식 시세 (US Quotes) ===
    "usa20100": ("/api/us/mrkcond", "미국주식 현재가 종목정보"),
    "usa20101": ("/api/us/mrkcond", "미국주식 현재가 10호가"),
    # === 미국주식 차트 (US Charts) ===
    "usa06010": ("/api/us/chart", "미국주식 틱 차트"),
    "usa06011": ("/api/us/chart", "미국주식 분 차트"),
    "usa06012": ("/api/us/chart", "미국주식 일 차트"),
    "usa06013": ("/api/us/chart", "미국주식 주 차트"),
    "usa06014": ("/api/us/chart", "미국주식 월 차트"),
    "usa06015": ("/api/us/chart", "미국주식 년 차트"),
    # === 환전 (FX) ===
    "ust31300": ("/api/us/exchange", "환전 예상 금액 조회"),
    "ust31301": ("/api/us/exchange", "환율 조회"),
    "ust31302": ("/api/us/exchange", "환전 신청"),
```

Also update the docstring/count comment at the top of `api_spec.py` if it mentions a total (188 → 217).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: 2 new PASS, 155 baseline PASS (157 total), ruff clean.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/api_spec.py tests/test_us.py
git commit -m "feat(us): register 29 US stock/FX API IDs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `us/_constants.py` + symbol detection (`us/detect.py`)

**Files:**
- Create: `kiwoom_cli/commands/us/__init__.py`, `kiwoom_cli/commands/us/_constants.py`, `kiwoom_cli/commands/us/detect.py`
- Test: `tests/test_us.py` (append)

**Interfaces:**
- Produces: `US_EXCHANGE: dict[str, str]` (`{"nasdaq": "ND", "nyse": "NY", "amex": "NA"}`), `US_EXCHANGE_ALL` (+`"all": "%"`), `KR_EXCHANGE: frozenset` (`{"KRX","NXT","SOR"}`), `US_ORDER_TYPES: dict[str, str]`, `US_BUY_TYPES: frozenset`, `US_SELL_TYPES: frozenset`, `US_STOP_TYPES: frozenset` — all in `kiwoom_cli/commands/us/_constants.py`.
- Produces: `is_us_symbol(code: str, exchange: str | None = None) -> bool` in `kiwoom_cli/commands/us/detect.py`. Tasks 5–10 dispatch on it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us.py`:

```python
# ============================================================
#  Task 2: constants + symbol detection
# ============================================================

from kiwoom_cli.commands.us._constants import (  # noqa: E402
    US_BUY_TYPES,
    US_EXCHANGE,
    US_ORDER_TYPES,
    US_SELL_TYPES,
    US_STOP_TYPES,
)
from kiwoom_cli.commands.us.detect import is_us_symbol  # noqa: E402


@pytest.mark.parametrize("code,exchange,expected", [
    ("005930", None, False),          # 6-digit numeric → KR
    ("NVDA", None, True),             # alpha ticker → US
    ("AAPL", None, True),
    ("BRK.B", None, True),            # dotted ticker → US
    ("12345", None, True),            # 5 digits → not KR shape → US
    ("005930", "nasdaq", True),       # explicit US override wins
    ("NVDA", "KRX", False),           # explicit KR override wins
    ("NVDA", "SOR", False),
    ("TSLA", "amex", True),
])
def test_is_us_symbol(code, exchange, expected):
    assert is_us_symbol(code, exchange) is expected


def test_us_order_type_codes():
    assert US_ORDER_TYPES == {
        "limit": "00", "market": "03",
        "vwap-limit": "26", "twap-limit": "27",
        "loc": "30", "moc": "33",
        "stop-limit": "34", "stop": "35",
        "vwap": "36", "twap": "37",
    }
    assert US_STOP_TYPES == frozenset({"stop", "stop-limit"})
    # buy has NO moc/stop/stop-limit
    assert US_BUY_TYPES == frozenset(
        {"limit", "market", "vwap-limit", "twap-limit", "loc", "vwap", "twap"}
    )
    assert US_SELL_TYPES == US_BUY_TYPES | frozenset({"moc", "stop", "stop-limit"})
    assert US_EXCHANGE == {"nasdaq": "ND", "nyse": "NY", "amex": "NA"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kiwoom_cli.commands.us'`

- [ ] **Step 3: Implement**

Create `kiwoom_cli/commands/us/__init__.py`:

```python
"""US stock trading — plain ops functions dispatched from the shared commands."""
```

Create `kiwoom_cli/commands/us/_constants.py`:

```python
"""Shared lookup maps for US stock commands."""

from __future__ import annotations

# CLI value -> API stex_tp code
US_EXCHANGE = {"nasdaq": "ND", "nyse": "NY", "amex": "NA"}
# list-type APIs accept % (전체)
US_EXCHANGE_ALL = {**US_EXCHANGE, "all": "%"}

# Korean exchange CLI values (existing convention in order.py/account.py)
KR_EXCHANGE = frozenset({"KRX", "NXT", "SOR"})

# CLI value -> trde_tp code (ust20000/ust20001)
US_ORDER_TYPES = {
    "limit": "00",       # 지정가
    "market": "03",      # 시장가
    "vwap-limit": "26",  # VWAP 지정가
    "twap-limit": "27",  # TWAP 지정가
    "loc": "30",         # Limit On Close
    "moc": "33",         # Market On Close (매도 전용)
    "stop-limit": "34",  # Stop Limit (매도 전용, --stop + --price)
    "stop": "35",        # Stop Market (매도 전용, --stop)
    "vwap": "36",        # VWAP 시장가
    "twap": "37",        # TWAP 시장가
}

# 매도 전용 유형 (ust20000 매수는 미지원)
US_SELL_ONLY_TYPES = frozenset({"moc", "stop", "stop-limit"})
US_BUY_TYPES = frozenset(US_ORDER_TYPES) - US_SELL_ONLY_TYPES
US_SELL_TYPES = frozenset(US_ORDER_TYPES)
US_STOP_TYPES = frozenset({"stop", "stop-limit"})
```

Create `kiwoom_cli/commands/us/detect.py`:

```python
"""US symbol detection and exchange resolution."""

from __future__ import annotations

import json

from ... import config
from ...output import err_console
from ._constants import KR_EXCHANGE, US_EXCHANGE

_CACHE_FILENAME = "us_exchanges.json"


def is_us_symbol(code: str, exchange: str | None = None) -> bool:
    """미국 종목 여부 판별.

    규칙: 6자리 숫자 → 한국, 그 외 → 미국. --exchange 값이 명시되면 그것이 우선.
    """
    if exchange in US_EXCHANGE:
        return True
    if exchange in KR_EXCHANGE:
        return False
    return not (len(code) == 6 and code.isdigit())
```

(`resolve_us_exchange` comes in Task 3 — do not add it yet. The `err_console`/`json`/`config` imports are used there; if ruff flags them as unused in this task, add them in Task 3 instead and keep only `KR_EXCHANGE, US_EXCHANGE` imports now.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/commands/us/ tests/test_us.py
git commit -m "feat(us): add us package with constants and symbol detection

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Exchange resolution via usa10098 + file cache

**Files:**
- Modify: `kiwoom_cli/commands/us/detect.py`
- Test: `tests/test_us.py` (append)

**Interfaces:**
- Consumes: `US_EXCHANGE` (Task 2); `config.CACHE_DIR`, `config.ensure_cache_dir()` (existing); a client object with `.request(api_id, body)`.
- Produces: `resolve_us_exchange(client, code: str, exchange: str | None = None) -> str` (returns `ND|NY|NA`), `UsExchangeError(Exception)`. Used by order_ops (Task 5/6) and stock_ops (Task 7/8).

usa10098 contract: request `{"stk_cd": code}`; response `{"list": [{"stex_tp": "ND", "stk_cd": "NVDA", "stk_nm": ..., ...}, ...]}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us.py`:

```python
# ============================================================
#  Task 3: exchange resolution + cache
# ============================================================

from kiwoom_cli.commands.us import detect  # noqa: E402


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """Point the exchange cache at a temp dir."""
    monkeypatch.setattr("kiwoom_cli.config.CACHE_DIR", tmp_path)
    return tmp_path / "us_exchanges.json"


def _fake_with_10098(entries):
    fake = FakeKiwoomClient()
    fake.set_response("usa10098", {"return_code": 0, "list": entries})
    return fake


def test_resolve_explicit_exchange_skips_api(tmp_cache):
    fake = FakeKiwoomClient()
    assert detect.resolve_us_exchange(fake, "NVDA", "nasdaq") == "ND"
    assert fake.calls == []  # no API hit


def test_resolve_via_usa10098_and_writes_cache(tmp_cache):
    fake = _fake_with_10098([{"stex_tp": "ND", "stk_cd": "NVDA"}])
    assert detect.resolve_us_exchange(fake, "NVDA") == "ND"
    assert fake.calls == [("usa10098", {"stk_cd": "NVDA"})]
    assert tmp_cache.exists()


def test_resolve_uses_cache_on_second_call(tmp_cache):
    fake = _fake_with_10098([{"stex_tp": "NY", "stk_cd": "KO"}])
    assert detect.resolve_us_exchange(fake, "KO") == "NY"
    fake2 = FakeKiwoomClient()  # would return default junk if called
    assert detect.resolve_us_exchange(fake2, "KO") == "NY"
    assert fake2.calls == []  # served from cache


def test_resolve_lowercases_nothing_uppercases_code(tmp_cache):
    fake = _fake_with_10098([{"stex_tp": "ND", "stk_cd": "NVDA"}])
    assert detect.resolve_us_exchange(fake, "nvda") == "ND"
    assert fake.calls[0][1] == {"stk_cd": "NVDA"}


def test_resolve_ambiguous_raises(tmp_cache):
    fake = _fake_with_10098([
        {"stex_tp": "ND", "stk_cd": "DUAL"},
        {"stex_tp": "NY", "stk_cd": "DUAL"},
    ])
    with pytest.raises(detect.UsExchangeError):
        detect.resolve_us_exchange(fake, "DUAL")


def test_resolve_not_found_raises(tmp_cache):
    fake = _fake_with_10098([])
    with pytest.raises(detect.UsExchangeError):
        detect.resolve_us_exchange(fake, "ZZZZ")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us.py -v -k resolve`
Expected: FAIL — `AttributeError: module ... has no attribute 'resolve_us_exchange'`

- [ ] **Step 3: Implement**

Append to `kiwoom_cli/commands/us/detect.py` (and ensure the imports `import json`, `from ... import config` are present at the top):

```python
class UsExchangeError(Exception):
    """거래소를 확정할 수 없음 (미등록 또는 복수 상장). --exchange로 지정 필요."""


def _cache_file():
    return config.CACHE_DIR / _CACHE_FILENAME


def _load_cache() -> dict[str, str]:
    f = _cache_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    config.ensure_cache_dir()
    _cache_file().write_text(
        json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8"
    )


def resolve_us_exchange(client, code: str, exchange: str | None = None) -> str:
    """종목의 거래소 코드(ND/NY/NA)를 확정한다.

    우선순위: 명시된 --exchange > 파일 캐시 > usa10098 조회 (결과는 캐시에 저장).
    복수 상장이거나 조회 결과가 없으면 UsExchangeError.
    """
    if exchange in US_EXCHANGE:
        return US_EXCHANGE[exchange]
    symbol = code.upper()
    cache = _load_cache()
    if symbol in cache:
        return cache[symbol]
    data, _ = client.request("usa10098", {"stk_cd": symbol})
    entries = [
        e for e in data.get("list", []) or []
        if e.get("stk_cd", "").upper() == symbol
    ]
    exchanges = {e.get("stex_tp") for e in entries if e.get("stex_tp")}
    if len(exchanges) != 1:
        raise UsExchangeError(
            f"'{symbol}'의 거래소를 확정할 수 없습니다 "
            f"(조회 결과 {len(exchanges)}건). --exchange nasdaq|nyse|amex 로 지정하세요."
        )
    stex_tp = exchanges.pop()
    cache[symbol] = stex_tp
    _save_cache(cache)
    return stex_tp
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/commands/us/detect.py tests/test_us.py
git commit -m "feat(us): resolve ticker exchange via usa10098 with file cache

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Formatter support — `_fmt_usd`, `_USD_FIELDS`, US labels

**Files:**
- Modify: `kiwoom_cli/formatters.py`
- Test: `tests/test_us.py` (append)

**Interfaces:**
- Produces: `_fmt_usd(value: str, strip_sign: bool = False) -> str` — commas + up to 4 decimals with trailing zeros stripped (`"213.0400"` → `"213.04"`, `"0.0012"` → `"0.0012"`, `"70000"` → `"70,000"`).
- Produces: `_USD_FIELDS: frozenset` routed first in `_smart_fmt`; extended `_FIELD_LABELS`; extended `_ABS_FIELDS`.
- Used by `print_generic_table` (existing) and `print_unified_balance` (Task 9).

**Do NOT change `_fmt_number` itself** — property tests pin its behavior. `_fmt_usd` is a new sibling.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us.py`:

```python
# ============================================================
#  Task 4: USD formatting
# ============================================================

from kiwoom_cli.formatters import _fmt_usd, _smart_fmt  # noqa: E402


@pytest.mark.parametrize("value,expected", [
    ("213.0400", "213.04"),
    ("0.0012", "0.0012"),
    ("1234.5000", "1,234.5"),
    ("70000", "70,000"),          # int stays int-formatted
    ("000001234", "1,234"),       # 0-padded
    ("+213.0400", "+213.04"),     # sign kept by default
    ("-0.5000", "-0.5"),
    ("", "-"),
    ("abc", "abc"),               # non-numeric passthrough
])
def test_fmt_usd(value, expected):
    assert _fmt_usd(value) == expected


def test_fmt_usd_strip_sign():
    assert _fmt_usd("+213.0400", strip_sign=True) == "213.04"
    assert _fmt_usd("-213.0400", strip_sign=True) == "213.04"


def test_smart_fmt_routes_usd_price_fields():
    # now_pric is a USD direction-indicator field: sign stripped, 4 decimals kept
    assert _smart_fmt("+213.0400", "now_pric") == "213.04"
    # pred_pre is signed USD
    assert _smart_fmt("-1.2500", "pred_pre") == "-1.25"
    # existing KR behavior unchanged for a non-USD field
    assert _smart_fmt("+70000", "cur_prc") == "70,000"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us.py -v -k usd`
Expected: FAIL — `ImportError: cannot import name '_fmt_usd'`

- [ ] **Step 3: Implement**

In `kiwoom_cli/formatters.py`, add directly after `_fmt_number` (around line 90):

```python
def _fmt_usd(value: str, strip_sign: bool = False) -> str:
    """Format a USD decimal string: commas, up to 4 decimals, trailing zeros stripped.

    Kiwoom US APIs return prices with up to 4 decimals ("213.0400", "0.0012").
    _fmt_number would force 2 decimals and mangle penny stocks; this preserves them.
    """
    v = value.strip()
    if not v:
        return "-"
    sign = ""
    if v.startswith(("+", "-")):
        sign = v[0]
        v = v[1:]
    if strip_sign:
        sign = ""
    v = v.lstrip("0") or "0"
    try:
        if "." not in v:
            return sign + f"{int(v):,}"
        s = f"{float(v):,.4f}".rstrip("0").rstrip(".")
        return sign + (s or "0")
    except ValueError:
        return value
```

Add after `_SIGNED_FIELDS` (around line 118):

```python
# USD decimal fields (up to 4 decimals). Routed to _fmt_usd by _smart_fmt.
# Direction-indicator USD prices additionally live in _ABS_FIELDS (sign stripped).
_USD_FIELDS = frozenset({
    "now_pric", "frgn_stk_book_uv", "cntr_uv", "stop_pric",
    "fpr_sel_bid", "fpr_buy_bid",
    "sel_1bid", "sel_2bid", "sel_3bid", "sel_4bid", "sel_5bid",
    "sel_6bid", "sel_7bid", "sel_8bid", "sel_9bid", "sel_10bid",
    "buy_1bid", "buy_2bid", "buy_3bid", "buy_4bid", "buy_5bid",
    "buy_6bid", "buy_7bid", "buy_8bid", "buy_9bid", "buy_10bid",
    "pre_open_pric", "pre_high_pric", "pre_low_pric", "base_close_pric",
    "fc_entra", "fc_uncl_amt", "pred_pre",
    "aplc_exrt", "sell_aplc_exrt", "buy_aplc_exrt", "usd_exch_rate",
    "exch_rate", "base_exrt", "spcl_bf_exrt",
    "sell_expc_amt", "buy_expc_amt", "sell_crnc_exmn_alow_amt",
    "buy_crnc_exmn_alow_amt", "fc_exmn_alow_amt",
})
```

Extend `_ABS_FIELDS` (add these members to the existing frozenset — these are direction-indicator prices whose sign must be stripped):

```python
    "now_pric", "frgn_stk_book_uv", "cntr_uv", "stop_pric",
    "fpr_sel_bid", "fpr_buy_bid",
    "sel_1bid", "sel_2bid", "sel_3bid", "sel_4bid", "sel_5bid",
    "sel_6bid", "sel_7bid", "sel_8bid", "sel_9bid", "sel_10bid",
    "buy_1bid", "buy_2bid", "buy_3bid", "buy_4bid", "buy_5bid",
    "buy_6bid", "buy_7bid", "buy_8bid", "buy_9bid", "buy_10bid",
    "poss_qty", "sell_alowq",
```

Replace `_smart_fmt` with:

```python
def _smart_fmt(value: str, field_key: str) -> str:
    """Format a value based on the field type."""
    if field_key in _USD_FIELDS:
        return _fmt_usd(value, strip_sign=field_key in _ABS_FIELDS)
    if field_key in _ABS_FIELDS:
        return _fmt_number(value, strip_sign=True)
    return _fmt_number(value)
```

Extend `_FIELD_LABELS` (append inside the existing dict):

```python
    # === 미국주식 (US) ===
    "frgn_stk_nm": "종목명",
    "stk_enm": "영문명",
    "stex_nm": "거래소",
    "crnc_code": "통화",
    "natn_nm": "국가",
    "mkgb": "거래소명",
    "upgb": "업종",
    "poss_qty": "보유수량",
    "sell_alowq": "매도가능",
    "frgn_stk_book_uv": "매입단가",
    "now_pric": "현재가",
    "evlt_amt_krw": "평가금액(원)",
    "pl_amt_krw": "손익금액(원)",
    "now_pric_krw": "현재가(원)",
    "frgn_stk_book_uv_krw": "매입단가(원)",
    "frgn_stk_book_amt": "매입금액",
    "frgn_stk_book_amt_krw": "매입금액(원)",
    "fc_entra": "외화예수금",
    "fc_uncl_amt": "외화미수금",
    "krw_entra": "원화예수금",
    "won_entr": "원화예수금",
    "trst_prof_ch": "사용증거금",
    "usd_exch_rate": "매도환율(USD)",
    "exch_rate": "환율",
    "aplc_exrt": "적용환율",
    "sell_aplc_exrt": "매도적용환율",
    "buy_aplc_exrt": "매수적용환율",
    "exrt_tp_nm": "환율구분",
    "exrt_spcl_rt": "환율우대율",
    "sell_expc_amt": "매도예상금액",
    "buy_expc_amt": "매수예상금액",
    "frgn_trde_nm": "매매구분",
    "slby_tp_nm": "매도수구분",
    "ord_remnq": "주문잔량",
    "cntr_uv": "체결단가",
    "cntr_qty": "체결수량",
    "stop_pric": "STOP가격",
    "ord_stat": "주문상태",
    "ord_time": "주문시간",
    "ord_cntr_tp": "주문종류",
    "tot_evlt_amt": "총평가금액",
    "tot_prch_amt": "총매입금액",
    "tot_pl_amt": "총손익금액",
    "tot_pl_rt": "총수익률",
    "tdy_pl_amt": "당일실현손익",
    "tot_evlt_amt_krw": "총평가금액(원)",
    "tot_prch_amt_krw": "총매입금액(원)",
    "tot_pl_amt_krw": "총손익금액(원)",
```

(If any key above already exists in `_FIELD_LABELS`, skip the duplicate — do not redefine keys.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS (formatter property tests included — `_fmt_number` untouched), ruff clean.

- [ ] **Step 5: Commit**

```bash
git add kiwoom_cli/formatters.py tests/test_us.py
git commit -m "feat(us): USD 4-decimal formatting path and US field labels

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: US order ops (buy/sell) + `order.py` dispatch, float price, `--stop`

**Files:**
- Create: `kiwoom_cli/commands/us/order_ops.py`
- Modify: `kiwoom_cli/commands/order.py` (`buy` at ~line 116, `sell` at ~line 146)
- Test: `tests/test_us.py` (append)

**Interfaces:**
- Consumes: `resolve_us_exchange`, `UsExchangeError`, `is_us_symbol` (Tasks 2–3); `US_ORDER_TYPES`, `US_BUY_TYPES`, `US_SELL_TYPES`, `US_STOP_TYPES`, `US_SELL_ONLY_TYPES` (Task 2); `print_order_result` (existing).
- Produces in `order_ops`: `fmt_us_price(price: float) -> str`; `buy(code, qty, price, order_type, exchange, confirm) -> None`; `sell(code, qty, price, order_type, exchange, stop, confirm) -> None`. All raise `SystemExit(1)` on input errors, `SystemExit(2)` via existing client error path.
- Produces in `order.py`: `--price`/`PRICE` become `type=float`; `--exchange` choice becomes `["KRX","NXT","SOR","nasdaq","nyse","amex"]` with `default=None` (KR path falls back to `"KRX"`); `--type` choice becomes the union of KR and US names; `sell` gains `--stop` (float, default 0). Task 6 repeats this pattern for modify/cancel.

**Both existing KR tests and bodies must stay byte-identical in behavior:** KR body sends `str(int(price))`, default exchange `KRX`, `trde_tp` from `ORDER_TYPES`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us.py`:

```python
# ============================================================
#  Task 5: US buy/sell orders + dispatch
# ============================================================


@pytest.fixture
def us_fake(monkeypatch, tmp_cache):
    """FakeKiwoomClient injected into both order.py and us ops modules."""
    fake = FakeKiwoomClient()
    fake.set_response("usa10098", {"return_code": 0, "list": [{"stex_tp": "ND", "stk_cd": "NVDA"}]})
    monkeypatch.setattr("kiwoom_cli.commands.order.KiwoomClient", lambda *a, **k: fake)
    monkeypatch.setattr("kiwoom_cli.commands.us.order_ops.KiwoomClient", lambda *a, **k: fake)
    return fake


def _order_calls(fake, api_id):
    return [c for c in fake.calls if c[0] == api_id]


def test_us_buy_auto_detect_and_resolve(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "buy", "NVDA", "10", "--price", "213.04", "--type", "limit", "--confirm"]
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "ust20000") == [(
        "ust20000",
        {"stex_tp": "ND", "stk_cd": "NVDA", "ord_qty": "10", "ord_uv": "213.04", "trde_tp": "00"},
    )]


def test_us_buy_explicit_exchange_skips_resolution(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "buy", "TSLA", "1", "--exchange", "nasdaq", "--confirm"]
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "usa10098") == []
    body = _order_calls(us_fake, "ust20000")[0][1]
    assert body["stex_tp"] == "ND"
    assert body["trde_tp"] == "03"  # default market
    assert body["ord_uv"] == ""     # market order → empty price


def test_us_buy_rejects_sell_only_type(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "buy", "NVDA", "1", "--type", "moc", "--confirm"]
    )
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20000") == []


def test_us_sell_stop_limit_body(runner, us_fake):
    result = runner.invoke(
        cli,
        ["order", "sell", "NVDA", "5", "--type", "stop-limit",
         "--price", "200.5", "--stop", "199.9900", "--confirm"],
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "ust20001") == [(
        "ust20001",
        {"stex_tp": "ND", "stk_cd": "NVDA", "ord_qty": "5",
         "ord_uv": "200.5", "stop_pric": "199.99", "trde_tp": "34"},
    )]


def test_us_sell_stop_type_requires_stop_price(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "sell", "NVDA", "5", "--type", "stop", "--confirm"]
    )
    assert result.exit_code == 1


def test_kr_buy_unchanged_and_fractional_price_rejected(runner, us_fake):
    ok = runner.invoke(
        cli, ["order", "buy", "005930", "10", "--price", "70000", "--type", "limit", "--confirm"]
    )
    assert ok.exit_code == 0
    body = _order_calls(us_fake, "kt10000")[0][1]
    assert body["ord_uv"] == "70000" and body["dmst_stex_tp"] == "KRX"

    bad = runner.invoke(
        cli, ["order", "buy", "005930", "10", "--price", "70000.5", "--confirm"]
    )
    assert bad.exit_code == 1


def test_kr_sell_rejects_stop_option(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "sell", "005930", "1", "--stop", "100.0", "--confirm"]
    )
    assert result.exit_code == 1


def test_us_buy_kr_order_type_rejected(runner, us_fake):
    # KR-only type name on US path → exit 1
    result = runner.invoke(
        cli, ["order", "buy", "NVDA", "1", "--type", "fok", "--confirm"]
    )
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us.py -v -k "us_buy or us_sell or kr_buy or kr_sell"`
Expected: FAIL — `ModuleNotFoundError` for `us.order_ops` (fixture) and/or Click usage errors for unknown options.

- [ ] **Step 3: Create `kiwoom_cli/commands/us/order_ops.py`**

```python
"""US order operations, dispatched from commands/order.py."""

from __future__ import annotations

import click
from rich.panel import Panel

from ...client import KiwoomClient
from ...formatters import print_order_result
from ...output import console, err_console
from ._constants import (
    US_ORDER_TYPES,
    US_SELL_ONLY_TYPES,
    US_STOP_TYPES,
)
from .detect import UsExchangeError, resolve_us_exchange

_EXCHANGE_NAMES = {"ND": "NASDAQ", "NY": "NYSE", "NA": "AMEX"}


def fmt_us_price(price: float) -> str:
    """소수점 4자리까지, 뒤 0 제거. 0이면 빈 문자열(시장가)."""
    if not price:
        return ""
    return f"{price:.4f}".rstrip("0").rstrip(".")


def _validate_us_type(order_type: str, side: str) -> str:
    """CLI 주문유형 → trde_tp 코드. 미지원이면 exit 1."""
    if order_type not in US_ORDER_TYPES:
        err_console.print(f"[red]미국주식에서 지원하지 않는 주문유형입니다: {order_type}[/]")
        raise SystemExit(1)
    if side == "buy" and order_type in US_SELL_ONLY_TYPES:
        err_console.print(f"[red]'{order_type}'은(는) 매도 전용 주문유형입니다 (매수 미지원).[/]")
        raise SystemExit(1)
    return US_ORDER_TYPES[order_type]


def _confirm_gate(confirm: bool) -> None:
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)


def _show_us_preview(action: str, code: str, qty: int, price: float,
                     order_type: str, stex_tp: str, stop: float = 0) -> None:
    price_str = f"${fmt_us_price(price)}" if price else "시장가"
    body = (
        f"[bold]{action} 주문 (미국)[/]\n\n"
        f"  종목코드: {code}\n"
        f"  수량: {qty:,}\n"
        f"  가격: {price_str}\n"
        f"  유형: {order_type}\n"
        f"  거래소: {_EXCHANGE_NAMES.get(stex_tp, stex_tp)}"
    )
    if stop:
        body += f"\n  STOP가격: ${fmt_us_price(stop)}"
    console.print(Panel(body, title="주문 확인", border_style="yellow"))


def _resolve_or_exit(client, code: str, exchange: str | None) -> str:
    try:
        return resolve_us_exchange(client, code, exchange)
    except UsExchangeError as e:
        err_console.print(f"[red]{e}[/]")
        raise SystemExit(1) from None


def buy(code: str, qty: int, price: float, order_type: str,
        exchange: str | None, confirm: bool) -> None:
    """미국주식 매수 (ust20000)."""
    trde_tp = _validate_us_type(order_type, "buy")
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("매수", code, qty, price, order_type, stex_tp)
        data, _ = c.request("ust20000", {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "ord_qty": str(qty),
            "ord_uv": fmt_us_price(price),
            "trde_tp": trde_tp,
        })
        print_order_result(data, "매수")


def sell(code: str, qty: int, price: float, order_type: str,
         exchange: str | None, stop: float, confirm: bool) -> None:
    """미국주식 매도 (ust20001)."""
    trde_tp = _validate_us_type(order_type, "sell")
    if order_type in US_STOP_TYPES and not stop:
        err_console.print(f"[red]'{order_type}' 주문에는 --stop 가격이 필요합니다.[/]")
        raise SystemExit(1)
    if stop and order_type not in US_STOP_TYPES:
        err_console.print("[red]--stop은 stop/stop-limit 주문에서만 사용합니다.[/]")
        raise SystemExit(1)
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("매도", code, qty, price, order_type, stex_tp, stop)
        body = {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "ord_qty": str(qty),
            "ord_uv": fmt_us_price(price),
            "trde_tp": trde_tp,
        }
        if stop:
            body["stop_pric"] = fmt_us_price(stop)
        data, _ = c.request("ust20001", body)
        print_order_result(data, "매도")
```

- [ ] **Step 4: Modify `kiwoom_cli/commands/order.py`**

Add imports after the existing ones:

```python
from ..output import err_console
from .us import order_ops as us_order_ops
from .us._constants import US_ORDER_TYPES
from .us.detect import is_us_symbol
```

Add module-level shared pieces after `ORDER_TYPES`:

```python
# 국내+미국 주문유형 CLI 이름 합집합 (경로별로 재검증)
ALL_ORDER_TYPES = sorted(set(ORDER_TYPES) | set(US_ORDER_TYPES))
ORDER_EXCHANGES = ["KRX", "NXT", "SOR", "nasdaq", "nyse", "amex"]


def _kr_price_or_exit(price: float) -> int:
    """국내 주문 가격은 정수(원). 소수점 입력 시 exit 1."""
    if price != int(price):
        err_console.print("[red]국내 주문 가격은 정수(원)여야 합니다.[/]")
        raise SystemExit(1)
    return int(price)


def _kr_type_or_exit(order_type: str) -> str:
    if order_type not in ORDER_TYPES:
        err_console.print(f"[red]국내주식에서 지원하지 않는 주문유형입니다: {order_type}[/]")
        raise SystemExit(1)
    return ORDER_TYPES[order_type]
```

Rewrite `buy` (keep the command body's KR API call identical in effect):

```python
@order.command("buy")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략, 미국주식은 소수점 4자리까지)")
@click.option("--type", "order_type", default="market", type=click.Choice(ALL_ORDER_TYPES), help="주문유형")
@click.option("--exchange", "exchange", default=None, type=click.Choice(ORDER_EXCHANGES), help="거래소 (기본: 국내 KRX / 미국 자동판별)")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격 (국내 전용)")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def buy(code: str, qty: int, price: float, order_type: str, exchange: str | None, cond_uv: int, confirm: bool):
    """주식 매수주문 (국내 kt10000 / 미국 ust20000).

    예: kiwoom order buy 005930 10 --price 70000 --type limit --confirm
        kiwoom order buy NVDA 10 --price 213.04 --confirm
    """
    if is_us_symbol(code, exchange):
        return us_order_ops.buy(code, qty, price, order_type, exchange, confirm)

    dmst_stex_tp = exchange or "KRX"
    trde_tp = _kr_type_or_exit(order_type)
    kr_price = _kr_price_or_exit(price)
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("매수", code, qty, kr_price, order_type, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10000", {
            "dmst_stex_tp": dmst_stex_tp,
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(kr_price) if kr_price else "",
            "trde_tp": trde_tp,
            "cond_uv": str(cond_uv) if cond_uv else "",
        })
        print_order_result(data, "매수")
```

Rewrite `sell` the same way, adding `--stop`:

```python
@order.command("sell")
@click.argument("code")
@click.argument("qty", type=int)
@click.option("--price", type=float, default=0, help="주문가격 (시장가 주문시 생략, 미국주식은 소수점 4자리까지)")
@click.option("--type", "order_type", default="market", type=click.Choice(ALL_ORDER_TYPES), help="주문유형")
@click.option("--exchange", "exchange", default=None, type=click.Choice(ORDER_EXCHANGES), help="거래소 (기본: 국내 KRX / 미국 자동판별)")
@click.option("--cond-price", "cond_uv", type=int, default=0, help="조건부가격 (국내 전용)")
@click.option("--stop", "stop", type=float, default=0, help="STOP가격 (미국 stop/stop-limit 전용)")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 주문 실행")
def sell(code: str, qty: int, price: float, order_type: str, exchange: str | None, cond_uv: int, stop: float, confirm: bool):
    """주식 매도주문 (국내 kt10001 / 미국 ust20001).

    예: kiwoom order sell 005930 10 --type market --confirm
        kiwoom order sell NVDA 5 --type stop-limit --price 200.5 --stop 199.99 --confirm
    """
    if is_us_symbol(code, exchange):
        return us_order_ops.sell(code, qty, price, order_type, exchange, stop, confirm)

    if stop:
        err_console.print("[red]--stop은 미국주식 매도에서만 사용합니다.[/]")
        raise SystemExit(1)
    dmst_stex_tp = exchange or "KRX"
    trde_tp = _kr_type_or_exit(order_type)
    kr_price = _kr_price_or_exit(price)
    if not confirm:
        click.confirm("주문을 실행하시겠습니까?", abort=True)

    _show_order_preview("매도", code, qty, kr_price, order_type, dmst_stex_tp)

    with KiwoomClient() as c:
        data, _ = c.request("kt10001", {
            "dmst_stex_tp": dmst_stex_tp,
            "stk_cd": code,
            "ord_qty": str(qty),
            "ord_uv": str(kr_price) if kr_price else "",
            "trde_tp": trde_tp,
            "cond_uv": str(cond_uv) if cond_uv else "",
        })
        print_order_result(data, "매도")
```

**Verify against the current file:** the KR `sell` body above must match the existing one exactly (API ID kt10001, same fields) — copy the current file's body if it differs. `_show_order_preview` signature takes `price: int` — the KR path now passes `kr_price` (int), so no change to the helper is needed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS — especially `tests/test_order.py` unchanged (KR bodies identical). Ruff clean.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/us/order_ops.py kiwoom_cli/commands/order.py tests/test_us.py
git commit -m "feat(us): US buy/sell orders with auto-detection, decimal prices, --stop

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: US modify/cancel/orderable + dispatch

**Files:**
- Modify: `kiwoom_cli/commands/us/order_ops.py` (append), `kiwoom_cli/commands/order.py` (`modify` ~line 176, `cancel` ~line 206), `kiwoom_cli/commands/account.py` (orderable US path — see note)
- Test: `tests/test_us.py` (append)

**Interfaces:**
- Consumes: Task 5's helpers (`fmt_us_price`, `_confirm_gate`, `_resolve_or_exit`, `_EXCHANGE_NAMES`).
- Produces: `order_ops.modify(orig_order_no, code, qty, price, exchange, stop, confirm)`, `order_ops.cancel(orig_order_no, code, qty, exchange, confirm)`, `order_ops.orderable(code, price, exchange)`.

US semantics (from spec §5 + Excel): modify (ust20002) is **price-only** — QTY positional is accepted but NOT sent; print notice `수량 변경 미지원 — 전량 가격정정`. Cancel (ust20003) is **full-remaining only** — a nonzero qty on the US path exits 1.

**Before coding, read the CURRENT `modify` and `cancel` signatures in `order.py`** (positional args and their order: `modify ORIG_ORDER_NO CODE QTY PRICE`, `cancel ORIG_ORDER_NO CODE [QTY]`) and preserve them exactly; only change `PRICE` to `type=float`, broaden `--exchange` to `ORDER_EXCHANGES` with `default=None`, and add `--stop` to `modify`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us.py`:

```python
# ============================================================
#  Task 6: US modify/cancel/orderable
# ============================================================


def test_us_modify_price_only_no_qty_sent(runner, us_fake):
    result = runner.invoke(
        cli,
        ["order", "modify", "000000123", "NVDA", "5", "215.5", "--confirm"],
    )
    assert result.exit_code == 0
    assert "전량" in result.output  # 수량 변경 미지원 notice
    calls = _order_calls(us_fake, "ust20002")
    assert calls == [(
        "ust20002",
        {"orig_ord_no": "000000123", "stex_tp": "ND", "stk_cd": "NVDA", "mdfy_uv": "215.5"},
    )]


def test_us_modify_stop_limit_sends_stop_pric(runner, us_fake):
    result = runner.invoke(
        cli,
        ["order", "modify", "000000123", "NVDA", "5", "215.5", "--stop", "210.0", "--confirm"],
    )
    assert result.exit_code == 0
    body = _order_calls(us_fake, "ust20002")[0][1]
    assert body["stop_pric"] == "210"


def test_us_cancel_full_remaining(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "cancel", "000000123", "NVDA", "--confirm"]
    )
    assert result.exit_code == 0
    assert _order_calls(us_fake, "ust20003") == [(
        "ust20003",
        {"orig_ord_no": "000000123", "stex_tp": "ND", "stk_cd": "NVDA"},
    )]


def test_us_cancel_rejects_partial_qty(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "cancel", "000000123", "NVDA", "3", "--confirm"]
    )
    assert result.exit_code == 1
    assert _order_calls(us_fake, "ust20003") == []


def test_kr_modify_unchanged(runner, us_fake):
    result = runner.invoke(
        cli, ["order", "modify", "0000139", "005930", "1", "70000", "--confirm"]
    )
    assert result.exit_code == 0
    assert len(_order_calls(us_fake, "kt10002")) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us.py -v -k "modify or cancel"`
Expected: new US tests FAIL (US symbols currently hit the KR path or Click rejects float PRICE).

- [ ] **Step 3: Append to `kiwoom_cli/commands/us/order_ops.py`**

```python
def modify(orig_order_no: str, code: str, qty: int, price: float,
           exchange: str | None, stop: float, confirm: bool) -> None:
    """미국주식 정정 (ust20002) — 가격 정정만 지원, 항상 잔량 전체."""
    console.print("[yellow]미국주식 정정은 수량 변경 미지원 — 전량 가격정정으로 처리됩니다.[/]")
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("정정", code, 0, price, "limit", stex_tp, stop)
        body = {
            "orig_ord_no": orig_order_no,
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "mdfy_uv": fmt_us_price(price),
        }
        if stop:
            body["stop_pric"] = fmt_us_price(stop)
        data, _ = c.request("ust20002", body)
        print_order_result(data, "정정")


def cancel(orig_order_no: str, code: str, qty: int,
           exchange: str | None, confirm: bool) -> None:
    """미국주식 취소 (ust20003) — 잔량 전체 취소만 지원."""
    if qty:
        err_console.print("[red]미국주식은 부분 취소를 지원하지 않습니다 (수량 지정 불가, 전량 취소만 가능).[/]")
        raise SystemExit(1)
    _confirm_gate(confirm)
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        _show_us_preview("취소", code, 0, 0, "-", stex_tp)
        data, _ = c.request("ust20003", {
            "orig_ord_no": orig_order_no,
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
        })
        print_order_result(data, "취소")


def orderable(code: str, price: float, exchange: str | None) -> None:
    """미국주식 주문가능수량 (ust31490)."""
    from ...formatters import print_generic_table

    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        data, _ = c.request("ust31490", {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "uv": fmt_us_price(price),
        })
        print_generic_table(data, title=f"{code.upper()} 주문가능수량 (미국)")
```

**Note on `_show_us_preview` qty display:** it renders `수량: 0` for modify/cancel. Improve it: change the helper so `qty=0` renders `전량`:

```python
    qty_str = f"{qty:,}" if qty else "전량"
```
and use `f"  수량: {qty_str}\n"` in the panel body (update the Task 5 helper in place).

- [ ] **Step 4: Modify `order.py` `modify` and `cancel`**

`modify` — change decorators: `PRICE` argument `type=float`; `--exchange` → `type=click.Choice(ORDER_EXCHANGES), default=None`; add `--stop` float default 0. Body becomes:

```python
    if is_us_symbol(code, exchange):
        return us_order_ops.modify(orig_order_no, code, qty, price, exchange, stop, confirm)
    if stop:
        err_console.print("[red]--stop은 미국주식에서만 사용합니다.[/]")
        raise SystemExit(1)
    dmst_stex_tp = exchange or "KRX"
    kr_price = _kr_price_or_exit(price)
    # ... existing confirm + preview + kt10002 body, with str(kr_price)
```

`cancel` — `--exchange` → `ORDER_EXCHANGES`, `default=None`. Body becomes:

```python
    if is_us_symbol(code, exchange):
        return us_order_ops.cancel(orig_order_no, code, qty, exchange, confirm)
    dmst_stex_tp = exchange or "KRX"
    # ... existing confirm + preview + kt10003 body unchanged
```

Keep every existing KR field and API ID exactly as the current file has them (read them before editing — do not trust this plan's memory of the kt10002/kt10003 bodies; only inject the dispatch and exchange default).

**Orderable dispatch:** find the existing `account orderable` KR command (`grep -n "orderable" kiwoom_cli/commands/account.py`). If it takes a CODE argument and a `--price` option, add the same two-line dispatch at the top (`if is_us_symbol(code, exchange): return us_order_ops.orderable(code, price, exchange)`) and broaden/add its `--exchange` option to include US values, converting `--price` to float with the KR int guard. If the existing signature differs meaningfully (e.g., no price option), instead register a US-only fallback: skip modifying it, and note in your report that `account orderable` US folding was skipped and why — the reviewer will adjudicate.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/us/order_ops.py kiwoom_cli/commands/order.py kiwoom_cli/commands/account.py tests/test_us.py
git commit -m "feat(us): US modify/cancel/orderable with price-only modify semantics

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: US stock info/price/orderbook/search + `stock.py` dispatch

**Files:**
- Create: `kiwoom_cli/commands/us/stock_ops.py`
- Modify: `kiwoom_cli/commands/stock.py` (`info` ~line 35, `price` ~line 44, `orderbook` ~line 57, `search` ~line 234)
- Test: `tests/test_us.py` (append)

**Interfaces:**
- Consumes: `resolve_us_exchange`, `UsExchangeError`, `is_us_symbol`, `US_EXCHANGE`, `US_EXCHANGE_ALL`; `print_generic_table`, `print_api_response` (existing).
- Produces: `stock_ops.info(code, exchange)`, `stock_ops.price(code, exchange)`, `stock_ops.orderbook(code, exchange)`, `stock_ops.search(keyword, exchange)`.

API contracts: usa10100 `{stk_cd, stex_tp?}` → flat dict (stk_nm, stk_enm, mkgb, upgb…). usa20100/usa20101 `{stex_tp, stk_cd}` (stex_tp required → resolve). usa10099 `{stex_tp}` (`%`=all) → `{"list": [...]}`; filter client-side by keyword against stk_cd/stk_nm/stk_enm (case-insensitive substring).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us.py`:

```python
# ============================================================
#  Task 7: US stock info/price/orderbook/search
# ============================================================


@pytest.fixture
def us_stock_fake(monkeypatch, tmp_cache):
    fake = FakeKiwoomClient()
    fake.set_response("usa10098", {"return_code": 0, "list": [{"stex_tp": "ND", "stk_cd": "NVDA"}]})
    fake.set_response("usa10100", {"return_code": 0, "stk_cd": "NVDA", "stk_nm": "엔비디아", "mkgb": "NASDAQ"})
    fake.set_response("usa20100", {"return_code": 0, "stk_cd": "NVDA", "cur_prc": "+213.0400"})
    fake.set_response("usa20101", {"return_code": 0, "stk_cd": "NVDA", "sel_1bid": "+213.0500"})
    fake.set_response("usa10099", {"return_code": 0, "list": [
        {"stk_cd": "NVDA", "stk_nm": "엔비디아", "stk_enm": "NVIDIA Corp", "stex_tp": "ND"},
        {"stk_cd": "AAPL", "stk_nm": "애플", "stk_enm": "Apple Inc", "stex_tp": "ND"},
    ]})
    monkeypatch.setattr("kiwoom_cli.commands.stock.KiwoomClient", lambda *a, **k: fake)
    monkeypatch.setattr("kiwoom_cli.commands.us.stock_ops.KiwoomClient", lambda *a, **k: fake)
    return fake


def test_us_stock_info_dispatch(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "info", "NVDA"])
    assert result.exit_code == 0
    assert ("usa10100", {"stk_cd": "NVDA"}) in us_stock_fake.calls


def test_us_stock_price_resolves_exchange(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "price", "NVDA"])
    assert result.exit_code == 0
    assert ("usa20100", {"stex_tp": "ND", "stk_cd": "NVDA"}) in us_stock_fake.calls


def test_us_stock_orderbook(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "orderbook", "NVDA", "--exchange", "nasdaq"])
    assert result.exit_code == 0
    assert ("usa20101", {"stex_tp": "ND", "stk_cd": "NVDA"}) in us_stock_fake.calls


def test_kr_stock_info_unchanged(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "info", "005930"])
    assert result.exit_code == 0
    assert us_stock_fake.calls[0][0] == "ka10001"


def test_us_stock_search_filters_keyword(runner, us_stock_fake):
    result = runner.invoke(cli, ["stock", "search", "apple", "--market", "us"])
    assert result.exit_code == 0
    assert ("usa10099", {"stex_tp": "%"}) in us_stock_fake.calls
    assert "AAPL" in result.output
    assert "NVDA" not in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us.py -v -k us_stock`
Expected: FAIL — `ModuleNotFoundError` for `us.stock_ops`, wrong API IDs called.

- [ ] **Step 3: Create `kiwoom_cli/commands/us/stock_ops.py`**

```python
"""US stock info/quote/search/chart operations, dispatched from commands/stock.py."""

from __future__ import annotations

from ...client import KiwoomClient
from ...formatters import _find_list, print_chart_data, print_generic_table
from ...output import err_console
from ._constants import US_EXCHANGE, US_EXCHANGE_ALL
from .detect import UsExchangeError, resolve_us_exchange


def _resolve_or_exit(client, code: str, exchange: str | None) -> str:
    try:
        return resolve_us_exchange(client, code, exchange)
    except UsExchangeError as e:
        err_console.print(f"[red]{e}[/]")
        raise SystemExit(1) from None


def info(code: str, exchange: str | None) -> None:
    """미국주식 종목 조회 (usa10100)."""
    body = {"stk_cd": code.upper()}
    if exchange in US_EXCHANGE:
        body["stex_tp"] = US_EXCHANGE[exchange]
    with KiwoomClient() as c:
        data, _ = c.request("usa10100", body)
        print_generic_table(data, title=f"{code.upper()} 종목정보 (미국)")


def price(code: str, exchange: str | None) -> None:
    """미국주식 현재가 (usa20100)."""
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        data, _ = c.request("usa20100", {"stex_tp": stex_tp, "stk_cd": code.upper()})
        print_generic_table(data, title=f"{code.upper()} 현재가 (미국)")


def orderbook(code: str, exchange: str | None) -> None:
    """미국주식 10호가 (usa20101)."""
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        data, _ = c.request("usa20101", {"stex_tp": stex_tp, "stk_cd": code.upper()})
        print_generic_table(data, title=f"{code.upper()} 호가 (미국)")


def search(keyword: str | None, exchange: str | None) -> None:
    """미국주식 종목 검색 (usa10099 리스트를 키워드로 필터)."""
    stex_tp = US_EXCHANGE_ALL.get(exchange or "all", "%")
    with KiwoomClient() as c:
        data, _ = c.request("usa10099", {"stex_tp": stex_tp})
        items = data.get("list", []) or []
        if keyword:
            kw = keyword.lower()
            items = [
                i for i in items
                if kw in i.get("stk_cd", "").lower()
                or kw in i.get("stk_nm", "").lower()
                or kw in i.get("stk_enm", "").lower()
            ]
        if not items:
            err_console.print("[yellow]검색 결과가 없습니다.[/]")
            return
        print_generic_table(items, title=f"미국주식 검색: {keyword or '전체'}")
```

- [ ] **Step 4: Modify `kiwoom_cli/commands/stock.py`**

Add imports:

```python
from .us import stock_ops as us_stock_ops
from .us.detect import is_us_symbol
```

`info`, `price`, `orderbook` each gain an `--exchange` option and a dispatch line. Pattern (apply to all three; keep the KR body untouched):

```python
@stock.command("info")
@click.argument("code")
@click.option("--exchange", "exchange", default=None, type=click.Choice(["nasdaq", "nyse", "amex"]), help="미국 거래소 (미국 종목 강제 라우팅)")
def info(code: str, exchange: str | None):
    """종목 기본정보 (국내 ka10001 / 미국 usa10100)."""
    if is_us_symbol(code, exchange):
        return us_stock_ops.info(code, exchange)
    # ... existing KR body unchanged
```

`search` — extend the existing `--market` choice with `"us"` and add `--exchange`:

The current option is `type=click.Choice(...)` over `MARKET_SEARCH` keys — change to `list(MARKET_SEARCH) + ["us"]` (build the list next to the decorator, or extend where the choices are defined). Add `--exchange` with `type=click.Choice(["nasdaq", "nyse", "amex", "all"]), default="all"`. At the top of the body:

```python
    if mrkt_tp == "us":
        return us_stock_ops.search(keyword, exchange)
```

(KR path ignores `exchange`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS (KR stock tests unchanged), ruff clean.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/us/stock_ops.py kiwoom_cli/commands/stock.py tests/test_us.py
git commit -m "feat(us): US stock info/price/orderbook/search with auto-dispatch

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: US charts (usa06010–15) + chart dispatch + `--krw`

**Files:**
- Modify: `kiwoom_cli/commands/us/stock_ops.py` (append `chart`), `kiwoom_cli/commands/stock.py` (six `chart` commands, lines ~1274–1420)
- Test: `tests/test_us.py` (append)

**Interfaces:**
- Consumes: Task 7's `_resolve_or_exit`; `print_chart_data`, `_find_list` (already imported in stock_ops).
- Produces: `stock_ops.chart(kind, code, exchange, tic_scope="1", strt_dt="", adjusted="0", krw=False)` where `kind ∈ {"tick","minute","day","week","month","year"}`.

API mapping: tick usa06010 `{stex_tp, stk_cd, tic_scope, upd_stkpc_tp, exrt_appl_tp}`; minute usa06011 adds `strt_dt`; day/week/month/year usa06012–15 `{stex_tp, stk_cd, strt_dt, upd_stkpc_tp, exrt_appl_tp}`. Response list key: `result_list` (found via `_find_list`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us.py`:

```python
# ============================================================
#  Task 8: US charts
# ============================================================


def test_us_chart_day_dispatch(runner, us_stock_fake):
    us_stock_fake.set_response("usa06012", {"return_code": 0, "result_list": [
        {"dt": "20260714", "cur_prc": "213.0400", "open_pric": "210.0000",
         "high_pric": "214.0000", "low_pric": "209.5000", "acc_trde_qty": "1000"},
    ]})
    result = runner.invoke(
        cli, ["stock", "chart", "day", "NVDA", "--base-date", "20260714"]
    )
    assert result.exit_code == 0
    assert ("usa06012", {
        "stex_tp": "ND", "stk_cd": "NVDA", "strt_dt": "20260714",
        "upd_stkpc_tp": "0", "exrt_appl_tp": "0",
    }) in us_stock_fake.calls


def test_us_chart_tick_with_krw(runner, us_stock_fake):
    us_stock_fake.set_response("usa06010", {"return_code": 0, "result_list": []})
    result = runner.invoke(
        cli, ["stock", "chart", "tick", "NVDA", "--range", "5", "--krw"]
    )
    assert result.exit_code == 0
    assert ("usa06010", {
        "stex_tp": "ND", "stk_cd": "NVDA", "tic_scope": "5",
        "upd_stkpc_tp": "0", "exrt_appl_tp": "1",
    }) in us_stock_fake.calls


def test_us_chart_minute_sends_strt_dt(runner, us_stock_fake):
    us_stock_fake.set_response("usa06011", {"return_code": 0, "result_list": []})
    result = runner.invoke(
        cli, ["stock", "chart", "minute", "NVDA", "--interval", "5", "--base-date", "20260714"]
    )
    assert result.exit_code == 0
    body = [c for c in us_stock_fake.calls if c[0] == "usa06011"][0][1]
    assert body["strt_dt"] == "20260714" and body["tic_scope"] == "5"


def test_kr_chart_rejects_krw(runner, us_stock_fake):
    result = runner.invoke(
        cli, ["stock", "chart", "day", "005930", "--base-date", "20260714", "--krw"]
    )
    assert result.exit_code == 1


def test_kr_chart_day_unchanged(runner, us_stock_fake):
    result = runner.invoke(
        cli, ["stock", "chart", "day", "005930", "--base-date", "20260714"]
    )
    assert result.exit_code == 0
    assert us_stock_fake.calls[0] == ("ka10081", {
        "stk_cd": "005930", "base_dt": "20260714", "upd_stkpc_tp": "0",
    })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us.py -v -k chart`
Expected: FAIL — no `--krw` option, US symbol hits ka10081.

- [ ] **Step 3: Append `chart` to `kiwoom_cli/commands/us/stock_ops.py`**

```python
_CHART_APIS = {
    "tick": "usa06010",
    "minute": "usa06011",
    "day": "usa06012",
    "week": "usa06013",
    "month": "usa06014",
    "year": "usa06015",
}

_CHART_TITLES = {
    "tick": "틱", "minute": "분봉", "day": "일봉",
    "week": "주봉", "month": "월봉", "year": "년봉",
}


def chart(kind: str, code: str, exchange: str | None, tic_scope: str = "1",
          strt_dt: str = "", adjusted: str = "0", krw: bool = False) -> None:
    """미국주식 차트 (usa06010~usa06015)."""
    api_id = _CHART_APIS[kind]
    with KiwoomClient() as c:
        stex_tp = _resolve_or_exit(c, code, exchange)
        body = {
            "stex_tp": stex_tp,
            "stk_cd": code.upper(),
            "upd_stkpc_tp": adjusted,
            "exrt_appl_tp": "1" if krw else "0",
        }
        if kind == "tick":
            body["tic_scope"] = tic_scope
        elif kind == "minute":
            body["tic_scope"] = tic_scope
            if strt_dt:
                body["strt_dt"] = strt_dt
        else:
            body["strt_dt"] = strt_dt
        data, _ = c.request(api_id, body)
        items = _find_list(data)
        title = f"{code.upper()} {_CHART_TITLES[kind]} 차트 (미국)"
        if isinstance(items, list):
            print_chart_data(items, title=title)
        else:
            print_generic_table(data, title=title)
```

- [ ] **Step 4: Modify the six chart commands in `stock.py`**

Every chart command gains two options and a dispatch. Shown for `day` — apply the same pattern to all six (`tick` passes `tic_scope=tic_scope` and no `strt_dt`; `minute` passes both `tic_scope` and `strt_dt=base_dt`; `week`/`month`/`year` mirror `day` with their own `kind`):

```python
@chart.command("day")
@click.argument("code")
@click.option("--base-date", "base_dt", required=True, help="기준일자 (YYYYMMDD, 미국은 시작일자로 사용)")
@click.option(
    "--adjusted", "upd_stkpc_tp",
    type=click.Choice(["0", "1"]),
    default="0",
    help="수정주가구분 (0=미적용, 1=적용)",
)
@click.option("--exchange", "exchange", default=None, type=click.Choice(["nasdaq", "nyse", "amex"]), help="미국 거래소")
@click.option("--krw", "krw", is_flag=True, help="원화 환산 (미국 전용)")
def chart_day(code: str, base_dt: str, upd_stkpc_tp: str, exchange: str | None, krw: bool):
    """일봉 차트 조회 (국내 ka10081 / 미국 usa06012)."""
    if is_us_symbol(code, exchange):
        return us_stock_ops.chart("day", code, exchange, strt_dt=base_dt,
                                  adjusted=upd_stkpc_tp, krw=krw)
    if krw:
        err_console.print("[red]--krw는 미국주식에서만 사용합니다.[/]")
        raise SystemExit(1)
    # ... existing KR body unchanged (ka10081)
```

`tick` (no base_dt in KR — pass `tic_scope` only):

```python
    if is_us_symbol(code, exchange):
        return us_stock_ops.chart("tick", code, exchange, tic_scope=tic_scope,
                                  adjusted=upd_stkpc_tp, krw=krw)
```

`minute` (KR has optional `--base-date` already):

```python
    if is_us_symbol(code, exchange):
        return us_stock_ops.chart("minute", code, exchange, tic_scope=tic_scope,
                                  strt_dt=base_dt, adjusted=upd_stkpc_tp, krw=krw)
```

Add `from ..output import err_console` to stock.py imports if not present (check first — it may already import from `..output`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS (KR chart tests unchanged), ruff clean.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/us/stock_ops.py kiwoom_cli/commands/stock.py tests/test_us.py
git commit -m "feat(us): US chart routing for all six timeframes with --krw

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Unified account balance (`print_unified_balance` + `--market`)

**Files:**
- Create: `kiwoom_cli/commands/us/account_ops.py`
- Modify: `kiwoom_cli/formatters.py` (append `print_unified_balance`), `kiwoom_cli/commands/account.py` (`balance` at line 46)
- Test: `tests/test_us_account.py` (new file)

**Interfaces:**
- Consumes: `_fmt_number`, `_fmt_usd`, `_sign_color`, `_calc_eval_pl`, `_find_list`, `console` (formatters); `US_EXCHANGE` (Task 2).
- Produces: `account_ops.fetch_balance(client, stex_tp: str | None = None) -> dict` (raises on API error); `formatters.print_unified_balance(kr_data: dict | None, us_data: dict | None) -> None`.

Data shapes: KR kt00004 → summary keys `entr, tot_pur_amt, tot_est_amt, …` + holdings list `stk_acnt_evlt_prst` (`stk_cd, stk_nm, rmnd_qty, avg_prc, cur_prc, evlt_amt, pl_amt, pl_rt`). US ust21070 → summary `tot_evlt_amt, tot_pl_amt, tot_evlt_amt_krw, tot_pl_amt_krw, tot_prch_amt` + `result_list` (`stk_cd, frgn_stk_nm, poss_qty, frgn_stk_book_uv, now_pric, evlt_amt, pl_amt, pl_rt, evlt_amt_krw, pl_amt_krw, stex_nm, crnc_code`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_us_account.py`:

```python
"""Tests for unified KR+US account views."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from tests.fakes import FakeKiwoomClient

KR_BALANCE = {
    "return_code": 0,
    "acnt_nm": "테스트",
    "entr": "000001000000",
    "tot_pur_amt": "000007000000",
    "tot_est_amt": "000007230000",
    "aset_evlt_amt": "000008230000",
    "tdy_lspft": "0",
    "tdy_lspft_rt": "0.00",
    "stk_acnt_evlt_prst": [{
        "stk_cd": "A005930", "stk_nm": "삼성전자", "rmnd_qty": "000000100",
        "avg_prc": "000070000", "cur_prc": "000072300",
        "evlt_amt": "0007230000", "pl_amt": "000230000", "pl_rt": "3.28",
    }],
}

US_BALANCE = {
    "return_code": 0,
    "crnc_code": "USD",
    "tot_evlt_amt": "2130.40",
    "tot_prch_amt": "1952.00",
    "tot_pl_amt": "178.40",
    "tot_pl_rt": "9.13",
    "tot_evlt_amt_krw": "000002943100",
    "tot_pl_amt_krw": "000000246500",
    "result_list": [{
        "stex_nm": "NASDAQ", "crnc_code": "USD", "stk_cd": "NVDA",
        "frgn_stk_nm": "엔비디아", "poss_qty": "000000010",
        "frgn_stk_book_uv": "195.2000", "now_pric": "213.0400",
        "evlt_amt": "2130.40", "pl_amt": "178.40", "pl_rt": "9.13",
        "evlt_amt_krw": "000002943100", "pl_amt_krw": "000000246500",
    }],
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def acct_fake(monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response("kt00004", KR_BALANCE)
    fake.set_response("ust21070", US_BALANCE)
    monkeypatch.setattr("kiwoom_cli.commands.account.KiwoomClient", lambda *a, **k: fake)
    monkeypatch.setattr("kiwoom_cli.commands.us.account_ops.KiwoomClient", lambda *a, **k: fake)
    return fake


def _apis(fake):
    return [c[0] for c in fake.calls]


def test_balance_unified_calls_both(runner, acct_fake):
    result = runner.invoke(cli, ["account", "balance"])
    assert result.exit_code == 0
    assert "kt00004" in _apis(acct_fake) and "ust21070" in _apis(acct_fake)
    # both markets rendered
    assert "삼성전자" in result.output
    assert "NVDA" in result.output or "엔비디아" in result.output
    # KRW grand total = 7,230,000 + 2,943,100
    assert "10,173,100" in result.output.replace(" ", "")


def test_balance_market_kr_skips_us(runner, acct_fake):
    result = runner.invoke(cli, ["account", "balance", "--market", "kr"])
    assert result.exit_code == 0
    assert "ust21070" not in _apis(acct_fake)


def test_balance_market_us_skips_kr(runner, acct_fake):
    result = runner.invoke(cli, ["account", "balance", "--market", "us"])
    assert result.exit_code == 0
    assert "kt00004" not in _apis(acct_fake)
    assert "NVDA" in result.output or "엔비디아" in result.output


def test_balance_us_failure_degrades_gracefully(runner, acct_fake, monkeypatch):
    from kiwoom_cli.client import KiwoomAPIError

    orig = acct_fake.request

    def failing(api_id, body=None, **kw):
        if api_id == "ust21070":
            raise KiwoomAPIError(500, "US account not enabled")
        return orig(api_id, body, **kw)

    monkeypatch.setattr(acct_fake, "request", failing)
    result = runner.invoke(cli, ["account", "balance"])
    assert result.exit_code == 0          # KR still renders
    assert "삼성전자" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us_account.py -v`
Expected: FAIL — no `--market` option; only kt00004 called.

- [ ] **Step 3: Create `kiwoom_cli/commands/us/account_ops.py`**

```python
"""US account operations, dispatched from commands/account.py."""

from __future__ import annotations

from ...client import KiwoomClient
from ...formatters import print_generic_table
from ._constants import US_EXCHANGE


def fetch_balance(client, stex_tp: str | None = None) -> dict:
    """미국주식 원장잔고 (ust21070). 예외는 호출측에서 처리."""
    body: dict = {}
    if stex_tp:
        body["stex_tp"] = stex_tp
    data, _ = client.request("ust21070", body)
    return data
```

(More printers are appended in Task 10; keep `US_EXCHANGE`/`print_generic_table`/`KiwoomClient` imports only if used in this task — add them in Task 10 otherwise, so ruff stays clean.)

- [ ] **Step 4: Append `print_unified_balance` to `kiwoom_cli/formatters.py`**

```python
def print_unified_balance(kr_data: dict[str, Any] | None, us_data: dict[str, Any] | None) -> None:
    """국내(kt00004) + 미국(ust21070) 통합 계좌 평가현황."""
    fmt = _get_format()
    if fmt == "json":
        _output_json({"kr": kr_data, "us": us_data})
        return
    if fmt == "csv":
        rows: list[dict] = []
        if kr_data:
            for h in kr_data.get("stk_acnt_evlt_prst", []) or []:
                rows.append({"market": "KR", **h})
        if us_data:
            for h in _find_list(us_data) or []:
                rows.append({"market": "US", **h})
        _output_csv(rows)
        return

    def _pad_int(v: str) -> int:
        try:
            return int(str(v).lstrip("+-").lstrip("0") or "0")
        except ValueError:
            return 0

    table = Table(title="🌏 통합 계좌평가현황", border_style="dim")
    table.add_column("시장", style="dim")
    table.add_column("종목")
    table.add_column("수량", justify="right")
    table.add_column("매입가", justify="right")
    table.add_column("현재가", justify="right")
    table.add_column("평가금액", justify="right")
    table.add_column("손익", justify="right")
    table.add_column("수익률", justify="right")

    if kr_data:
        for h in kr_data.get("stk_acnt_evlt_prst", []) or []:
            pl = h.get("pl_amt", "0")
            color = _sign_color(pl)
            table.add_row(
                "KRX",
                h.get("stk_nm", ""),
                _fmt_number(h.get("rmnd_qty", "")),
                _fmt_number(h.get("avg_prc", "")),
                _fmt_number(h.get("cur_prc", "")),
                f"₩{_fmt_number(h.get('evlt_amt', ''))}",
                Text(_fmt_number(pl), style=color),
                Text(h.get("pl_rt", "0") + "%", style=color),
            )
    if us_data:
        for h in _find_list(us_data) or []:
            pl = h.get("pl_amt", "0")
            color = _sign_color(pl)
            table.add_row(
                h.get("stex_nm", "US"),
                h.get("frgn_stk_nm", "") or h.get("stk_cd", ""),
                _fmt_number(h.get("poss_qty", ""), strip_sign=True),
                f"${_fmt_usd(h.get('frgn_stk_book_uv', ''), strip_sign=True)}",
                f"${_fmt_usd(h.get('now_pric', ''), strip_sign=True)}",
                f"${_fmt_usd(h.get('evlt_amt', ''))}\n(₩{_fmt_number(h.get('evlt_amt_krw', ''))})",
                Text(
                    f"{_fmt_usd(pl)}\n(₩{_fmt_number(h.get('pl_amt_krw', ''))})",
                    style=color,
                ),
                Text(h.get("pl_rt", "0") + "%", style=color),
            )
    console.print(table)

    # 소계 + 원화 총계
    kr_total = _pad_int(kr_data.get("tot_est_amt", "0")) if kr_data else 0
    us_total_krw = _pad_int(us_data.get("tot_evlt_amt_krw", "0")) if us_data else 0
    summary = Table(show_header=False, border_style="dim")
    summary.add_column("항목", style="cyan", width=20)
    summary.add_column("값", justify="right")
    if kr_data:
        _, kr_pl_str, kr_pl_rt, kr_color = _calc_eval_pl(kr_data)
        summary.add_row("KRW 소계", Text(f"₩{kr_total:,} ({kr_pl_str})", style=kr_color))
    if us_data:
        us_pl = us_data.get("tot_pl_amt", "0")
        us_color = _sign_color(us_pl)
        summary.add_row(
            "USD 소계",
            Text(
                f"${_fmt_usd(us_data.get('tot_evlt_amt', '0'))} ({_fmt_usd(us_pl)})",
                style=us_color,
            ),
        )
    summary.add_row("총평가액 (KRW)", Text(f"₩{kr_total + us_total_krw:,}", style="bold"))
    console.print(summary)
```

(`Table`, `Text`, `console`, `Any` are already imported in formatters.py — verify, don't re-import.)

- [ ] **Step 5: Rewire `account balance` in `kiwoom_cli/commands/account.py`**

Add imports:

```python
from ..client import KiwoomAPIError
from ..formatters import print_unified_balance
from ..output import err_console
from .us import account_ops as us_account_ops
```

(Check what account.py already imports from `..formatters` and `..output` and extend those lines instead of duplicating.)

Replace the `balance` command:

```python
@account.command("balance")
@click.option("--market", "market", default="all", type=click.Choice(["all", "kr", "us"]), help="시장 (all=통합, kr=국내, us=미국)")
@click.option("--exchange", "dmst_stex_tp", default="KRX", type=click.Choice(["KRX", "NXT"]), help="국내 거래소 구분")
@click.option("--delist", "qry_tp", default="0", type=click.Choice(["0", "1"]), help="상장폐지조회구분 (0=전체, 1=제외)")
def balance(market: str, dmst_stex_tp: str, qry_tp: str):
    """계좌 평가현황 — 국내+미국 통합 (kt00004 + ust21070)."""
    kr_data = us_data = None
    with KiwoomClient() as c:
        if market in ("all", "kr"):
            try:
                kr_data, _ = c.request("kt00004", {"qry_tp": qry_tp, "dmst_stex_tp": dmst_stex_tp})
            except KiwoomAPIError as e:
                if market == "kr":
                    raise
                err_console.print(f"[dim]국내 잔고 조회 실패: {e}[/]")
        if market in ("all", "us"):
            try:
                us_data = us_account_ops.fetch_balance(c)
            except KiwoomAPIError as e:
                if market == "us":
                    raise
                err_console.print(f"[dim]미국 잔고 조회 실패 (미국주식 미개설 계좌일 수 있음): {e}[/]")
    if market == "kr":
        print_account_eval(kr_data or {})
    else:
        print_unified_balance(kr_data, us_data)
```

**Check how `KiwoomAPIError` propagates through the existing CLI error handling** (`grep -n "KiwoomAPIError" kiwoom_cli/main.py kiwoom_cli/client.py`) — if commands normally let it bubble to a top-level handler that prints and exits 2, the `raise` branches above are correct.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us_account.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS. Note `tests/test_account.py` has existing balance tests — if any asserted the old single-market output, they must still pass because KR fields render identically inside the unified table; if one fails on exact output, STOP and report (do not silently edit old tests).

- [ ] **Step 7: Commit**

```bash
git add kiwoom_cli/commands/us/account_ops.py kiwoom_cli/formatters.py kiwoom_cli/commands/account.py tests/test_us_account.py
git commit -m "feat(us): unified KR+US account balance with KRW grand total

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Unified deposit / pnl / orders / history with `--market`

**Files:**
- Modify: `kiwoom_cli/commands/us/account_ops.py` (append printers), `kiwoom_cli/commands/account.py` (`deposit` line ~56, `pnl today` ~151, `orders pending` ~205, `history transactions` ~430)
- Test: `tests/test_us_account.py` (append)

**Interfaces:**
- Consumes: existing KR bodies (ka10077, ka10075, kt00015, kt00001), `print_generic_table`, `_find_list`, `print_pending_orders`.
- Produces in `account_ops`: `print_deposit_us(client)`, `print_pnl_today_us(client, fc_krw: str)`, `print_pending_us(client, slby_tp: str, stk_cd: str)`, `print_history_us(client, strt_dt: str, end_dt: str, tp: str)`.

Unified pattern for each command: `--market all|kr|us` (default `all`); `all` renders the KR section then the US section, each wrapped in try/except `KiwoomAPIError` with a dim `err_console` note; `kr`/`us` runs only that side and lets errors propagate.

US API bodies: deposit ust21160 `{}`; pnl-today ust21170 `{"fc_krw_tp": fc_krw}` (`"0"`=외화 default); pending ust21050 `{"slby_tp": slby_tp, "stk_cd": stk_cd}` (omit empty stk_cd; slby_tp `0/1/2` matches KR `--trade` values); history ust21100 `{"strt_dt", "end_dt", "tp"}` (KR `--type` values `0–5` pass through; `6`/`7` are KR-only → on `--market us` exit 1, on `all` skip US with a note).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us_account.py`:

```python
# ============================================================
#  Task 10: deposit / pnl / orders / history --market
# ============================================================


@pytest.fixture
def acct_fake_full(acct_fake):
    acct_fake.set_response("kt00001", {"return_code": 0, "entr": "000001000000"})
    acct_fake.set_response("ust21160", {"return_code": 0, "won_entr": "000001000000", "d0_usd_fx_entr": "1234.56"})
    acct_fake.set_response("ka10077", {"return_code": 0, "tot_pl_amt": "1000"})
    acct_fake.set_response("ust21170", {"return_code": 0, "crnc_code": "USD", "tdy_pl_amt": "12.3400", "result_list": []})
    acct_fake.set_response("ka10075", {"return_code": 0, "oso": []})
    acct_fake.set_response("ust21050", {"return_code": 0, "result_list": [
        {"ord_no": "000000123", "stk_cd": "NVDA", "frgn_stk_nm": "엔비디아",
         "ord_qty": "000000010", "ord_uv": "213.0400", "ord_remnq": "000000010",
         "slby_tp_nm": "매수", "ord_stat": "접수"},
    ]})
    acct_fake.set_response("kt00015", {"return_code": 0, "trst_list": []})
    acct_fake.set_response("ust21100", {"return_code": 0, "sell_sum": "0", "buy_sum": "0", "result_list": []})
    return acct_fake


def test_deposit_unified(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "deposit"])
    assert result.exit_code == 0
    assert "kt00001" in _apis(acct_fake_full) and "ust21160" in _apis(acct_fake_full)


def test_deposit_market_us_only(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "deposit", "--market", "us"])
    assert result.exit_code == 0
    assert "kt00001" not in _apis(acct_fake_full)


def test_pnl_today_us_no_code_needed(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "pnl", "today", "--market", "us"])
    assert result.exit_code == 0
    assert ("ust21170", {"fc_krw_tp": "0"}) in acct_fake_full.calls


def test_pnl_today_kr_still_requires_code(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "pnl", "today", "005930", "--market", "kr"])
    assert result.exit_code == 0
    assert ("ka10077", {"stk_cd": "005930"}) in acct_fake_full.calls
    bad = runner.invoke(cli, ["account", "pnl", "today", "--market", "kr"])
    assert bad.exit_code == 1


def test_orders_pending_unified(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "orders", "pending"])
    assert result.exit_code == 0
    assert "ka10075" in _apis(acct_fake_full) and "ust21050" in _apis(acct_fake_full)
    assert "NVDA" in result.output or "엔비디아" in result.output


def test_orders_pending_trade_maps_to_slby(runner, acct_fake_full):
    result = runner.invoke(cli, ["account", "orders", "pending", "--trade", "2", "--market", "us"])
    assert result.exit_code == 0
    body = [c for c in acct_fake_full.calls if c[0] == "ust21050"][0][1]
    assert body["slby_tp"] == "2"


def test_history_transactions_unified(runner, acct_fake_full):
    result = runner.invoke(
        cli, ["account", "history", "transactions", "--from", "20260701", "--to", "20260715"]
    )
    assert result.exit_code == 0
    assert "kt00015" in _apis(acct_fake_full) and "ust21100" in _apis(acct_fake_full)
    us_body = [c for c in acct_fake_full.calls if c[0] == "ust21100"][0][1]
    assert us_body == {"strt_dt": "20260701", "end_dt": "20260715", "tp": "0"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us_account.py -v -k "deposit or pnl or pending or history"`
Expected: FAIL — no `--market` options, US APIs never called, `pnl today` requires CODE positionally.

- [ ] **Step 3: Append printers to `kiwoom_cli/commands/us/account_ops.py`**

```python
def print_deposit_us(client) -> None:
    """미국주식 예수금 상세 (ust21160)."""
    data, _ = client.request("ust21160", {})
    print_generic_table(data, title="미국주식 예수금")


def print_pnl_today_us(client, fc_krw: str = "0") -> None:
    """미국주식 당일 종목별 실현손익 (ust21170)."""
    data, _ = client.request("ust21170", {"fc_krw_tp": fc_krw})
    print_generic_table(data, title="미국주식 당일 실현손익")


def print_pending_us(client, slby_tp: str = "0", stk_cd: str = "") -> None:
    """미국주식 원장 미체결 (ust21050)."""
    body: dict = {"slby_tp": slby_tp}
    if stk_cd:
        body["stk_cd"] = stk_cd.upper()
    data, _ = client.request("ust21050", body)
    print_generic_table(data, title="미국주식 미체결")


def print_history_us(client, strt_dt: str, end_dt: str, tp: str = "0") -> None:
    """미국주식 거래내역 (ust21100)."""
    data, _ = client.request("ust21100", {"strt_dt": strt_dt, "end_dt": end_dt, "tp": tp})
    print_generic_table(data, title="미국주식 거래내역")
```

- [ ] **Step 4: Rewire the four commands in `account.py`**

Shared helper at module level (after the imports):

```python
def _run_unified(market: str, kr_fn, us_fn) -> None:
    """국내/미국 섹션을 순차 실행. all이면 한쪽 실패는 경고로 강등."""
    if market in ("all", "kr"):
        try:
            kr_fn()
        except KiwoomAPIError as e:
            if market == "kr":
                raise
            err_console.print(f"[dim]국내 조회 실패: {e}[/]")
    if market in ("all", "us"):
        try:
            us_fn()
        except KiwoomAPIError as e:
            if market == "us":
                raise
            err_console.print(f"[dim]미국 조회 실패 (미국주식 미개설 계좌일 수 있음): {e}[/]")
```

`deposit`:

```python
@account.command("deposit")
@click.option("--market", "market", default="all", type=click.Choice(["all", "kr", "us"]), help="시장")
@click.option("--type", "qry_type", type=click.Choice(["estimate", "normal"]), default="estimate", help="조회구분 (국내 전용)")
def deposit(market: str, qry_type: str):
    """예수금 상세 — 국내+미국 (kt00001 + ust21160)."""
    tp_map = {"estimate": "3", "normal": "2"}
    with KiwoomClient() as c:
        _run_unified(
            market,
            lambda: print_deposit(c.request("kt00001", {"qry_tp": tp_map[qry_type]})[0]),
            lambda: us_account_ops.print_deposit_us(c),
        )
```

`pnl today` — make CODE optional:

```python
@pnl.command("today")
@click.argument("code", required=False)
@click.option("--market", "market", default="all", type=click.Choice(["all", "kr", "us"]), help="시장")
@click.option("--krw", "fc_krw", is_flag=True, help="미국 손익을 원화로 표시")
def pnl_today(code: str | None, market: str, fc_krw: bool):
    """당일 실현손익 — 국내(종목코드 필수 ka10077) + 미국(ust21170)."""
    if market == "kr" and not code:
        err_console.print("[red]국내 당일 실현손익은 종목코드가 필요합니다.[/]")
        raise SystemExit(1)

    def kr():
        if not code:
            err_console.print("[dim]국내 섹션 생략 (종목코드 미지정).[/]")
            return
        with KiwoomClient() as c:
            data, _ = c.request("ka10077", {"stk_cd": code})
            print_generic_table(data, title="당일 실현손익 상세")

    def us():
        with KiwoomClient() as c:
            us_account_ops.print_pnl_today_us(c, "1" if fc_krw else "0")

    _run_unified(market, kr, us)
```

`orders pending` — add `--market`, keep all KR options; after the existing KR block wrap both:

```python
@orders.command("pending")
@click.option("--market", "market", default="all", type=click.Choice(["all", "kr", "us"]), help="시장")
@click.option("--all-stocks", "all_stk_tp", default="0", type=click.Choice(["0", "1"]), help="전체종목구분 (국내 전용)")
@click.option("--trade", "trde_tp", default="0", type=click.Choice(["0", "1", "2"]), help="매매구분 (0=전체, 1=매도, 2=매수)")
@click.option("--code", "stk_cd", default="", help="종목코드 (미입력시 전체)")
@click.option("--exchange", "stex_tp", default="all", type=click.Choice(["all", "KRX", "NXT"]), help="국내 거래소구분")
def orders_pending(market: str, all_stk_tp: str, trde_tp: str, stk_cd: str, stex_tp: str):
    """미체결 주문 — 국내(ka10075) + 미국(ust21050)."""
    def kr():
        with KiwoomClient() as c:
            body: dict = {
                "all_stk_tp": all_stk_tp,
                "trde_tp": trde_tp,
                "stex_tp": EXCHANGE_ALL_ZERO[stex_tp],
            }
            if stk_cd and not stk_cd.isalpha():
                body["stk_cd"] = stk_cd
            data, _ = c.request("ka10075", body)
            items = _find_list(data)
            if isinstance(items, list):
                print_pending_orders(items)
            else:
                print_generic_table(data, title="미체결")

    def us():
        with KiwoomClient() as c:
            us_account_ops.print_pending_us(c, trde_tp, stk_cd if stk_cd.isalpha() else "")

    _run_unified(market, kr, us)
```

`history transactions` — add `--market`; KR body unchanged; US section:

```python
    def us():
        if tp in ("6", "7"):
            err_console.print("[dim]미국 섹션 생략 (입금/출금 구분은 국내 전용).[/]")
            return
        with KiwoomClient() as c:
            us_account_ops.print_history_us(c, strt_dt, end_dt, tp)
```

with `--market us` + `tp in ("6","7")` → `err_console` red message + `SystemExit(1)` before the sections run. Wire `_run_unified(market, kr, us)` where `kr()` holds the existing kt00015 body verbatim.

**Also wire two more US account APIs (same `--market` pattern):**

`pnl by-period` (KR ka10073) gains `--market` and a US section using ust21530:

```python
def print_pnl_period_us(client, strt_dt: str, end_dt: str, fc_krw: str = "0") -> None:
    """미국주식 기간 실현손익 (ust21530)."""
    data, _ = client.request("ust21530", {"strt_dt": strt_dt, "end_dt": end_dt, "fc_krw_tp": fc_krw})
    print_generic_table(data, title="미국주식 실현손익")
```

(append to `account_ops.py`; the KR section keeps the ka10073 body verbatim, `--code` applies to KR only — pass alpha codes to neither, note with dim message.)

`orders executed` (KR ka10076) gains `--market` and a US section using ust21510:

```python
def print_executed_us(client, slby_tp: str = "0", stk_cd: str = "") -> None:
    """미국주식 당일 주문체결 확인 (ust21510)."""
    body: dict = {"slby_tp": slby_tp}
    if stk_cd:
        body["stk_cd"] = stk_cd.upper()
    data, _ = client.request("ust21510", body)
    print_generic_table(data, title="미국주식 당일 체결")
```

(KR `--side sell_tp` value maps directly to US `slby_tp` — same 0/1/2 semantics; alpha `--code` goes to the US call only, numeric to KR only, same `isalpha()` split as `orders pending`.)

Add two tests:

```python
def test_pnl_by_period_unified(runner, acct_fake_full):
    acct_fake_full.set_response("ka10073", {"return_code": 0})
    acct_fake_full.set_response("ust21530", {"return_code": 0, "tot_pl_amt": "10.00", "result_list": []})
    result = runner.invoke(
        cli, ["account", "pnl", "by-period", "--from", "20260701", "--to", "20260715"]
    )
    assert result.exit_code == 0
    assert ("ust21530", {"strt_dt": "20260701", "end_dt": "20260715", "fc_krw_tp": "0"}) in acct_fake_full.calls


def test_orders_executed_unified(runner, acct_fake_full):
    acct_fake_full.set_response("ka10076", {"return_code": 0, "cntr": []})
    acct_fake_full.set_response("ust21510", {"return_code": 0, "result_list": []})
    result = runner.invoke(cli, ["account", "orders", "executed"])
    assert result.exit_code == 0
    assert "ka10076" in _apis(acct_fake_full) and "ust21510" in _apis(acct_fake_full)
```

**Registered but CLI-deferred (state this in your report, it is intentional):** ust21150 (일별 주문체결내역) and ust21180 (기간별 주문내역) are API-registered (Task 1) but get no CLI wiring in this pass — they functionally overlap ust21050/ust21510 and their KR analogs (`orders detail`/`orders status`) have KR-specific option sets. A follow-up pass can fold them in.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us_account.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS. `tests/test_account.py` deposit/pending tests must still pass — the KR bodies are unchanged and `--market` defaults to `all`, so KR APIs are still called with identical bodies. If an old test asserts the EXACT total call list (KR-only) and now sees an extra US call, STOP and report to the controller (do not edit the old test yourself).

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/us/account_ops.py kiwoom_cli/commands/account.py tests/test_us_account.py
git commit -m "feat(us): unified deposit/pnl/orders/history with --market filter

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: FX subgroup — `account exchange rate|estimate|apply`

**Files:**
- Create: `kiwoom_cli/commands/us/exchange.py`
- Modify: `kiwoom_cli/commands/account.py` (wire subgroup), `kiwoom_cli/commands/us/__init__.py` (re-export)
- Test: `tests/test_us_account.py` (append)

**Interfaces:**
- Consumes: `print_generic_table`, `console`, `err_console`, `KiwoomClient`.
- Produces: `exchange_group` (a `click.Group` named `"exchange"`), wired via `account.add_command(exchange_group)`.

API contracts: ust31301 rate `{"exch_tp": "1"|"2"}`; ust31300 estimate `{"exch_tp", "fc_exmn_amt"}`; ust31302 apply `{"exch_tp", "fc_exmn_amt"}` — **apply moves real money → preview panel + `click.confirm` unless `--confirm`** (same gate as orders).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_us_account.py`:

```python
# ============================================================
#  Task 11: account exchange (FX)
# ============================================================


@pytest.fixture
def fx_fake(monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response("ust31301", {"return_code": 0, "aplc_exrt": "1381.500000", "sell_aplc_exrt": "1380.50", "buy_aplc_exrt": "1382.50"})
    fake.set_response("ust31300", {"return_code": 0, "aplc_exrt": "1381.500000", "buy_expc_amt": "723.85"})
    fake.set_response("ust31302", {"return_code": 0, "krw_exmn_amt": "000001000000", "buy_fc_amt": "723.85"})
    monkeypatch.setattr("kiwoom_cli.commands.us.exchange.KiwoomClient", lambda *a, **k: fake)
    return fake


def test_fx_rate(runner, fx_fake):
    result = runner.invoke(cli, ["account", "exchange", "rate"])
    assert result.exit_code == 0
    assert ("ust31301", {"exch_tp": "1"}) in fx_fake.calls


def test_fx_rate_usd_krw_direction(runner, fx_fake):
    result = runner.invoke(cli, ["account", "exchange", "rate", "--direction", "usd-krw"])
    assert result.exit_code == 0
    assert ("ust31301", {"exch_tp": "2"}) in fx_fake.calls


def test_fx_estimate(runner, fx_fake):
    result = runner.invoke(cli, ["account", "exchange", "estimate", "1000000"])
    assert result.exit_code == 0
    assert ("ust31300", {"exch_tp": "1", "fc_exmn_amt": "1000000"}) in fx_fake.calls


def test_fx_apply_requires_confirm_prompt(runner, fx_fake):
    declined = runner.invoke(cli, ["account", "exchange", "apply", "1000000"], input="n\n")
    assert declined.exit_code != 0
    assert [c for c in fx_fake.calls if c[0] == "ust31302"] == []

    accepted = runner.invoke(cli, ["account", "exchange", "apply", "1000000", "--confirm"])
    assert accepted.exit_code == 0
    assert ("ust31302", {"exch_tp": "1", "fc_exmn_amt": "1000000"}) in fx_fake.calls
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_us_account.py -v -k fx`
Expected: FAIL — `No such command 'exchange'`.

- [ ] **Step 3: Create `kiwoom_cli/commands/us/exchange.py`**

```python
"""환전 명령 (account exchange) — ust31300/ust31301/ust31302."""

from __future__ import annotations

import click
from rich.panel import Panel

from ...client import KiwoomClient
from ...formatters import print_generic_table
from ...output import console

DIRECTION = {"krw-usd": "1", "usd-krw": "2"}
_DIRECTION_LABELS = {"krw-usd": "원화 → 달러", "usd-krw": "달러 → 원화"}


@click.group("exchange")
def exchange_group():
    """환전 (환율/예상금액/신청)."""


@exchange_group.command("rate")
@click.option("--direction", "direction", default="krw-usd", type=click.Choice(list(DIRECTION)), help="환전 방향")
def fx_rate(direction: str):
    """환율 조회 (ust31301)."""
    with KiwoomClient() as c:
        data, _ = c.request("ust31301", {"exch_tp": DIRECTION[direction]})
        print_generic_table(data, title=f"환율 ({_DIRECTION_LABELS[direction]})")


@exchange_group.command("estimate")
@click.argument("amount", type=int)
@click.option("--direction", "direction", default="krw-usd", type=click.Choice(list(DIRECTION)), help="환전 방향")
def fx_estimate(amount: int, direction: str):
    """환전 예상 금액 조회 (ust31300). AMOUNT는 매도통화 기준."""
    with KiwoomClient() as c:
        data, _ = c.request("ust31300", {
            "exch_tp": DIRECTION[direction],
            "fc_exmn_amt": str(amount),
        })
        print_generic_table(data, title=f"환전 예상 ({_DIRECTION_LABELS[direction]})")


@exchange_group.command("apply")
@click.argument("amount", type=int)
@click.option("--direction", "direction", default="krw-usd", type=click.Choice(list(DIRECTION)), help="환전 방향")
@click.option("--confirm", is_flag=True, help="확인 프롬프트 없이 실행")
def fx_apply(amount: int, direction: str, confirm: bool):
    """환전 신청 (ust31302). 실제 자금이 이동합니다."""
    unit = "원" if direction == "krw-usd" else "달러"
    console.print(Panel(
        f"[bold]환전 신청[/]\n\n"
        f"  방향: {_DIRECTION_LABELS[direction]}\n"
        f"  금액: {amount:,}{unit}",
        title="환전 확인",
        border_style="yellow",
    ))
    if not confirm:
        click.confirm("환전을 신청하시겠습니까?", abort=True)
    with KiwoomClient() as c:
        data, _ = c.request("ust31302", {
            "exch_tp": DIRECTION[direction],
            "fc_exmn_amt": str(amount),
        })
        print_generic_table(data, title="환전 신청 결과")
```

- [ ] **Step 4: Wire into `account.py` and `us/__init__.py`**

`kiwoom_cli/commands/us/__init__.py`:

```python
"""US stock trading — plain ops functions dispatched from the shared commands."""

from .exchange import exchange_group

__all__ = ["exchange_group"]
```

At the bottom of `kiwoom_cli/commands/account.py`:

```python
from .us.exchange import exchange_group  # noqa: E402

account.add_command(exchange_group)
```

(If ruff complains about the import position, move it to the top imports and only keep `account.add_command(exchange_group)` at the bottom.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_us_account.py -v && .venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_cli/commands/us/exchange.py kiwoom_cli/commands/us/__init__.py kiwoom_cli/commands/account.py tests/test_us_account.py
git commit -m "feat(us): account exchange subgroup (rate/estimate/apply) with confirm gate

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Docs + full-suite verification

**Files:**
- Modify: `README.md`, `CLAUDE.md` (local only — gitignored, do not commit), `docs/superpowers/specs/2026-07-03-us-stock-trading-design.md` (mark implemented)

**Interfaces:** none (docs only).

- [ ] **Step 1: README.md**

Add a `## 미국주식 (US Stocks)` section after the main usage section (locate with `grep -n "^## " README.md`), containing:

```markdown
## 미국주식 (US Stocks)

티커를 입력하면 자동으로 미국 시장으로 라우팅됩니다 (6자리 숫자 = 국내, 알파벳 = 미국).

```bash
kiwoom order buy NVDA 10 --price 213.04           # 매수 (거래소 자동 판별)
kiwoom order sell NVDA 5 --type stop-limit --price 200.5 --stop 199.99 --confirm
kiwoom stock price NVDA                            # 현재가
kiwoom stock chart day NVDA --base-date 20260701   # 일봉
kiwoom stock search apple --market us              # 종목 검색
kiwoom account balance                             # 국내+미국 통합 잔고 (원화 총계)
kiwoom account balance --market us                 # 미국만
kiwoom account exchange rate                       # 환율
kiwoom account exchange apply 1000000 --confirm    # 원화 → 달러 환전
```

- 거래소(`--exchange nasdaq|nyse|amex`)는 자동 판별되며, 복수 상장 종목만 직접 지정이 필요합니다.
- 미국 주문 유형: limit/market/vwap/twap/vwap-limit/twap-limit/loc (매수·매도), moc/stop/stop-limit (매도 전용).
- 정정은 가격만 가능(전량), 취소는 전량 취소만 지원됩니다 (키움 API 제약).
- 계좌 조회 명령(`balance/deposit/pnl/orders/history`)은 기본 통합 표시이며 `--market kr|us`로 필터링합니다.
```

- [ ] **Step 2: CLAUDE.md (local edit, NOT committed)**

In the Architecture tree add under `commands/`:

```
    ├── us/            # 미국주식 (detect/order_ops/stock_ops/account_ops/exchange, 29 APIs)
```

In Conventions add:

```
- 미국주식: 6자리 숫자=국내, 알파벳 티커=미국 자동 라우팅. 거래소 자동판별(usa10098+캐시). --market kr|us 필터
```

Update the API count line (207 → 236: 217 REST + 19 WebSocket) if present.

- [ ] **Step 3: Mark the spec implemented**

In `docs/superpowers/specs/2026-07-03-us-stock-trading-design.md` change the Status line to `**Status:** Implemented (feature/us-stock-trading)`.

- [ ] **Step 4: Final verification**

Run: `.venv/bin/pytest tests/ -q && .venv/bin/ruff check kiwoom_cli/`
Expected: all PASS (155 baseline + ~40 new), ruff clean.

Smoke-check the CLI surface (no API calls — help screens only):

```bash
.venv/bin/python -m kiwoom_cli.main --help >/dev/null 2>&1 || .venv/bin/kiwoom --help
.venv/bin/kiwoom order buy --help
.venv/bin/kiwoom account balance --help
.venv/bin/kiwoom account exchange --help
.venv/bin/kiwoom stock chart day --help
```

Expected: each prints the updated help (US examples, `--market`, `--krw`, `--stop` visible), exit 0.

- [ ] **Step 5: Commit**

```bash
git add README.md
git add -f docs/superpowers/specs/2026-07-03-us-stock-trading-design.md
git commit -m "docs(us): document US stock trading and unified account views

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Post-plan (controller, NOT the implementer)

After all 12 tasks pass their reviews and the final whole-branch review is clean:

1. Push branch, open PR to `main` (PR body: feature summary, breaking-change check — there is none: KR behavior unchanged; `--exchange` default changed from `"KRX"` to auto-resolution that still lands on KRX for KR symbols).
2. Release (user directive 2026-07-15): bump `kiwoom_cli/__init__.py` `__version__` to `2.0.0` (this auto-dispatches kiwoom-release-checker per project config), write release notes covering the US-stocks feature, merge PR after CI, tag `v2.0.0`. **The `v*` tag push triggers PyPI auto-deploy — get an explicit go/no-go from the user immediately before pushing the tag.** Note: the user's license-relicense plan ties v2.0 to a license change — ASK the user whether the relicense happens in this release before tagging.
3. Follow-ups already on the user's roadmap (do not build now): `spec search`-style discovery commands, global `--json` machine mode, Claude Code/Codex plugin.
