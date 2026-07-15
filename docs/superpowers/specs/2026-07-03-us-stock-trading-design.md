# US Stock Trading — Design Spec

**Date:** 2026-07-03 (rev 2)
**Status:** Implemented (feature/us-stock-trading)
**Target release:** v2.0 (US-stocks release)

## 1. Goal

Add US stock trading to kiwoom-cli so it feels **native to the existing command tree**, not a
segregated add-on. A US order must be exactly as short to type as a Korean one:

```
kiwoom order buy NVDA 10 --price 213.04      # US
kiwoom order buy 005930 10 --price 70000     # Korean
```

The account must read as **one account**, showing Korean and US holdings together with a
single KRW total.

## 2. Scope

### In scope (trading core — ~24 REST APIs)

| Area | US APIs | Folds into |
|---|---|---|
| Orders | ust20000/1/2/3, ust31490 | `order buy/sell/modify/cancel`, `account orderable` |
| Account view | ust21070, ust21160/ust21110, ust21530/ust21170, ust21050/ust21150/ust21510/ust21180, ust21100 | `account balance/deposit/pnl/orders/history` |
| Symbol lookup | usa10098, usa10099, usa10100 | `stock info/search` + exchange resolution |
| Quote | usa20100, usa20101 | `stock price`, `stock orderbook` |
| Charts | usa06010-15 | `stock chart tick/minute/day/week/month/year` |
| FX (US-only) | ust31300, ust31301, ust31302 | new `account exchange` subgroup |

### Out of scope (deferred to a later pass, same patterns apply)

Rankings (`usa2xxxx`, 60+), sector (`usa23xxx`), watchlist (`usa20200/1`), condition search
(`usa2028x/9x`), account return-history (`usa216xx`), research (`usa24300`), quarter chart
(usa06016 — no Korean sibling), year-over-year change tables, and all US WebSocket streaming
(F4/F5/FE/FT). None require rework of what this spec builds.

## 3. Routing — how a command knows it's US

Three mechanisms, chosen per command shape:

### 3a. Symbol-bearing commands → auto-detect
Applies to `order buy/sell/modify/cancel`, `stock info/price/orderbook`, `stock chart *`.

- **Rule:** a 6-digit all-numeric code → Korean (existing path). Anything else (alpha ticker)
  → US.
- **Override:** `--exchange` disambiguates. It accepts Korean values (`KRX`, `NXT`, `SOR`) and
  US values (`nasdaq`, `nyse`, `amex`). A US value forces US routing regardless of symbol
  shape.
- **Exchange resolution for US orders:** US APIs require `stex_tp` (NA/ND/NY). When the user
  does not pass `--exchange`, resolve it via **usa10098** (거래소구분 조회): `NVDA` → `ND`.
  Resolutions are cached in `~/.kiwoom/cache/us_exchanges.json` (same pattern as the existing
  `stock sync` cache at `~/.kiwoom/cache/stocks.json`), so repeat trades on the same ticker
  skip the lookup. On multiple listings or no match, fail with a clear message asking for
  `--exchange`.

Detection helper (`commands/us/detect.py`):
```python
def is_us_symbol(code: str, exchange: str | None) -> bool:
    if exchange in US_EXCHANGE:      # explicit US override
        return True
    if exchange in KR_EXCHANGE:      # explicit KR override
        return False
    return not (len(code) == 6 and code.isdigit())
```

### 3b. Account-level views → unified by default
Applies to `account balance/deposit/pnl/orders/history`. There is no symbol to detect from, so
these show **both markets merged by default**, with `--market kr|us` to filter to one (which
also skips the other API call).

### 3c. US-only FX → new subgroup
`account exchange rate|estimate|apply` (ust31301/31300/31302). No Korean analog.

## 4. Unified account view

`account balance` calls **kt00004** (Korean, existing) and **ust21070** (US) and renders one
table. The US API returns KRW-converted values per holding (`evlt_amt_krw`, `pl_amt_krw`,
`now_pric_krw`, `frgn_stk_book_uv_krw`), so a true combined KRW total needs **no separate FX
call**.

Target rendering:
```
계좌 평가현황                                         총평가액  ₩152,340,900
─────────────────────────────────────────────────────────────────────────
시장    종목          수량    매입가     현재가     평가금액        손익      수익률
KRX     삼성전자       100   70,000    72,300    ₩7,230,000    +230,000   +3.28%
NASDAQ  NVDA           10  $195.20   $213.04    $2,130.40    +$178.40   +9.13%
                                                  (₩2,943,100)  (+246,500)
─────────────────────────────────────────────────────────────────────────
KRW 소계  ₩15,980,000 (-20,000)    │    USD 소계  $3,967.90 (+$272.90)
```

**Normalization.** Each source maps to a common holding row:
`{market, symbol, name, qty, avg_price, cur_price, eval_amt, pl_amt, pl_rt, currency, eval_krw, pl_krw}`.
Korean rows have `currency=KRW` and `eval_krw == eval_amt`; US rows carry native USD plus the
KRW-converted line. A new `formatters.print_unified_balance(kr_data, us_data)` renders the
table, per-currency subtotals, and the KRW grand total.

**Degradation.** If `--market kr`, skip the US call. If `--market us`, skip the Korean call.
If an unfiltered call to one market fails or returns empty (e.g. no US account enabled),
render the other market and print a quiet note (`err_console`) rather than aborting. Same
unified-default + `--market` filter + graceful degradation pattern applies to `deposit`,
`pnl`, `orders`, and `history`.

## 5. US-specific command details

### Order type map (`US_ORDER_TYPES`, `trde_tp`)

Buy (ust20000) and sell (ust20001) support **different** type sets. Buy has no stop price
field at all.

| CLI value | Code | Meaning | Buy | Sell |
|---|---|---|---|---|
| `limit` | 00 | 지정가 | ✔ | ✔ |
| `market` | 03 | 시장가 | ✔ | ✔ |
| `vwap-limit` | 26 | VWAP 지정가 | ✔ | ✔ |
| `twap-limit` | 27 | TWAP 지정가 | ✔ | ✔ |
| `loc` | 30 | Limit On Close | ✔ | ✔ |
| `vwap` | 36 | VWAP 시장가 | ✔ | ✔ |
| `twap` | 37 | TWAP 시장가 | ✔ | ✔ |
| `moc` | 33 | Market On Close | ✘ | ✔ |
| `stop` | 35 | Stop Market (needs `--stop`) | ✘ | ✔ |
| `stop-limit` | 34 | Stop Limit (needs `--stop` + `--price`) | ✘ | ✔ |

`order buy` with `moc`/`stop`/`stop-limit` on the US path exits with code 1 and a clear
message (sell-only per the API). `--stop` is a new float option on `order sell` and
`order modify`; the KR path rejects it.

### Exchange map (`US_EXCHANGE`, `stex_tp`)
`nasdaq → ND`, `nyse → NY`, `amex → NA`, `all → %` (list APIs only). `KR_EXCHANGE` covers the
existing `KRX/NXT/SOR` values. Both live in `commands/us/_constants.py`.

### Prices are decimal
US prices are decimal strings with up to 4 decimals (`"213.04"`, penny stocks `"0.0012"`).
The shared `--price` option and `PRICE` positional change from `type=int` to `type=float`;
the KR path validates the value is a whole number (else exit 1) and sends `str(int(price))`,
preserving current domestic behavior. The US path sends the decimal string with trailing
zeros stripped.

### Modify / cancel semantics differ from domestic
- **US modify (ust20002) is price-only** — there is no quantity param; the API modifies the
  full remaining quantity. The shared signature `order modify ORIG CODE QTY PRICE` keeps its
  positional QTY, but the US path prints a notice (수량 변경 미지원 — 전량 가격정정) and
  shows 전량 in the preview; QTY is not sent.
- **US cancel (ust20003) is full-remaining only** — no partial cancel. If `--qty` is passed on
  the US path, exit 1 with a message (partial cancel unsupported for US).

### Order body construction
- Buy (ust20000): `stex_tp, stk_cd, ord_qty, ord_uv, trde_tp`
- Sell (ust20001): adds `stop_pric` (required when `trde_tp` in {34, 35})
- Modify (ust20002): `orig_ord_no, stex_tp, stk_cd, mdfy_uv, stop_pric`
- Cancel (ust20003): `orig_ord_no, stex_tp, stk_cd`
- Orderable qty (ust31490): `stex_tp, stk_cd, uv` → US path of
  `account orderable margin-qty <CODE> --price`

### Order safety
Mirror the domestic pattern: Rich preview panel + interactive `click.confirm` unless
`--confirm`. `account exchange apply` (moves money) gets the same confirm gate. This is the
only order-safety gate — OS-level system authentication (Touch ID etc.) was considered and
deliberately rejected as too much friction for a CLI and unusable by AI agents.

## 6. Chart mapping

`stock chart {tick,minute,day,week,month,year}` gains US routing (auto-detect by symbol):

| CLI | US API | US request params |
|---|---|---|
| tick | usa06010 | `stex_tp, stk_cd, tic_scope, upd_stkpc_tp, exrt_appl_tp` |
| minute | usa06011 | + `strt_dt` |
| day | usa06012 | `stex_tp, stk_cd, strt_dt, upd_stkpc_tp, exrt_appl_tp` |
| week | usa06013 | 〃 |
| month | usa06014 | 〃 |
| year | usa06015 | 〃 |

The existing shared `--adjusted` option (`upd_stkpc_tp`, default `0` = 미적용, matching
domestic) passes through to the US body. New US-only option `--krw` (`exrt_appl_tp`, default
0); the KR path rejects it. Existing domestic options that have no US equivalent are ignored
on the US path with a notice only when explicitly set.

## 7. Formatting changes (`formatters.py`)

1. **USD-aware number path.** Current `_fmt_number` forces 2 decimals and would mangle
   `"0.0012"`. Add a path preserving up to 4 decimals with trailing zeros stripped for USD
   price fields; KRW-converted and share-quantity fields keep integer formatting.
2. **US field labels.** Extend `_FIELD_LABELS` with the US response fields used by the specced
   commands (`fc_entra` 외화예수금, `frgn_stk_nm` 종목명, `evlt_amt_krw` 평가금액(원),
   `trst_prof_ch` 사용증거금, `aplc_exrt` 적용환율, …).
3. **US price fields → `_ABS_FIELDS`.** US direction-indicator price fields (`now_pric`,
   `sel_Nbid`, `buy_Nbid`, …; many already present from domestic) so +/- renders as direction,
   matching convention.
4. **`print_unified_balance()`** — new renderer for §4.

## 8. Code structure & isolation

New package `kiwoom_cli/commands/us/` holds US logic as **plain functions**, not competing
Click commands. Existing Click commands gain a thin dispatch branch at the top:

```python
# in order.py buy()
if is_us_symbol(code, exchange):
    return us_order_ops.buy(code, qty, price, order_type, exchange, confirm)
# ... existing Korean path unchanged
```

```
kiwoom_cli/commands/us/
├── __init__.py       # re-exports ops + the `account exchange` group
├── _constants.py     # US_EXCHANGE, KR_EXCHANGE, US_ORDER_TYPES (+ buy/sell allowed sets)
├── detect.py         # is_us_symbol(), resolve_us_exchange(client, code) + file cache
├── order_ops.py      # buy/sell/modify/cancel/orderable
├── account_ops.py    # balance/deposit/pnl/orders/history (+ merge helpers)
├── stock_ops.py      # info/price/orderbook/search/chart
└── exchange.py       # `account exchange` Click subgroup (rate/estimate/apply)
```

**Unchanged:** `client.py`, `config.py`, `auth.py`, domain/profile system. US APIs use the
same appkey/secret/account/token and the same host (`api.kiwoom.com` /
`mockapi.kiwoom.com`). Among shared modules only `api_spec.py` (register ~24 IDs) and
`formatters.py` (§7) change; `commands/account.py` wires the `account exchange` subgroup
(`account.add_command(...)`) — `main.py` is untouched.

Files modified: `api_spec.py`, `formatters.py`, `commands/order.py` (dispatch + float price +
`--stop` + broadened `--exchange`), `commands/stock.py` (dispatch), `commands/account.py`
(unified views + `--market` + exchange subgroup), `main.py`. New: the `commands/us/` package.

## 9. Testing

Mirror the existing 40-test pattern (mocked `KiwoomClient.request`):

- **Detection:** `is_us_symbol` for numeric vs alpha vs `--exchange` override; exchange
  resolution hits usa10098, uses/writes the file cache, errors on ambiguity.
- **Order body construction:** each order type → correct `trde_tp`; decimal price → correct
  string; KR path rejects fractional prices; buy rejects sell-only types; sell STOP types
  require `--stop`; US modify sends no qty; US cancel rejects `--qty`.
- **Unified account:** KR + US fixture merge → one row set, correct KRW grand total;
  `--market` filters skip the right call; one-market failure degrades gracefully.
- **Formatters:** USD 4-decimal fields render without loss; `print_unified_balance` on real
  response shapes doesn't crash.
- **FX:** rate/estimate/apply body construction; `apply` respects `--confirm`.
- **Regression:** existing domestic order tests still pass unchanged (int prices, KRX default).

~20–25 new tests. `ruff check kiwoom_cli/` must pass.

## 10. Open questions / assumptions

- **Assumption:** trading-core scope (§2), not full 125-API parity, in this pass.
- **Assumption:** the same Kiwoom account/token covers KR and US; no config changes. Verify on
  first mock call.
- **Resolved:** order system auth (Touch ID) was considered and rejected (§5); SECURITY.md and
  CLAUDE.md corrected to describe the interactive confirm gate as the only order-safety mechanism.
