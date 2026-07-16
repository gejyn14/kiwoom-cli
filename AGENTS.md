# AGENTS.md — kiwoom-cli를 도구로 쓰는 에이전트를 위한 계약

kiwoom-cli는 AI 에이전트가 파싱 없이 안전하게 쓰도록 설계된 키움증권 CLI입니다.
이 문서는 기계가 의존해도 되는 **안정 계약**만 다룹니다.

## 기본 규칙

- 항상 `-f json`으로 호출하세요. stdout은 **단일 JSON 문서** 하나만 담습니다
  (진행 메시지·미리보기는 전부 stderr).
- json/csv 모드는 **절대 대화형 프롬프트를 띄우지 않습니다** — 확인이 필요한
  명령을 `--confirm` 없이 호출하면 즉시 `CONFIRMATION_REQUIRED` 오류(exit 1)로
  응답합니다. 세션이 입력 대기로 멈추는 일이 없습니다.
- 명령 스키마는 `kiwoom describe [명령...] -f json`으로 조회하세요 (아래 참고).

## Envelope (schema v1)

```json
{
  "ok": true,
  "schema": "v1",
  "data": { "...": "정규화된 필드", "raw": { "...": "원본 응답" } },
  "meta": { "profile": "default", "env": "mock", "cont": null },
  "error": null
}
```

- `ok` — `error === null`과 동치.
- `data` — 성공 페이로드. API 응답은 **정규화된 타입 필드** + 원본(`data.raw`).
  리스트형 응답은 `{"items": [...], "raw": [...]}`.
- `meta.env` — `"mock"`(모의투자) 또는 `"prod"`(실거래). **주문 전 반드시 확인하세요.**
- `meta.cont` — 연속조회 커서. 값이 있으면 `--next-key <값>`으로 다음 페이지.
- `error` — `{"code", "retryable", "message", "upstream_code", "details"?}`.

## 정규화된 데이터 (data)

키움 API는 모든 값이 문자열이고 가격류의 +/-는 부호가 아니라 **방향지시자**입니다
("+70000" = 70000원, 상승). `data`는 이를 해석해 타입 있는 값으로 제공합니다:

| 정규 필드 | 원본 | 의미 |
|---|---|---|
| `symbol` | stk_cd | 종목코드 (문자열) |
| `name` | stk_nm | 종목명 |
| `price` | cur_prc | 현재가 (숫자, 부호 제거) |
| `change_direction` | cur_prc의 부호 | `"up"` / `"down"` (부호 있을 때만) |
| `change` | pred_pre | 전일대비 (부호 있는 숫자) |
| `change_pct` | flu_rt | 등락율 % (부호 있는 숫자) |
| `volume` | trde_qty | 거래량 |
| `qty` | rmnd_qty | 보유수량 |
| `avg_price` | avg_prc | 평균단가 |
| `eval_amount` | evlt_amt | 평가금액 |
| `pl_amount` | pl_amt | 손익금액 (부호 실제) |
| `pl_pct` | pl_rt | 손익율 % |
| `order_no` | ord_no | 주문번호 (문자열) |
| `dt` / `tm` / `cntr_tm` | 동일 | ISO-8601 (`2026-07-16`, `15:30:45+09:00`) |

- 방향지시 필드(가격류)는 절대값 + `<필드>_direction` 동반 키로 분리됩니다.
- 알 수 없는 키는 원래 이름·값 그대로 통과합니다.
- 원본 인코딩이 필요하면 `data.raw`를 읽으세요.

## --fields — 토큰 절약 투영

```bash
kiwoom -f json --fields symbol,price,change_pct stock info 005930
kiwoom -f json --fields symbol,qty account balance --market kr
```

`data`(및 내부 모든 리스트의 각 요소)를 지정한 키로만 투영하고 `data.raw`를
제거합니다. 대량 조회 시 응답 토큰을 크게 줄입니다.

## Exit codes

| code | 의미 | 대응 |
|---|---|---|
| 0 | 성공 | — |
| 1 | 입력 오류 (인자, CONFIRMATION_REQUIRED, VALIDATION_FAILED) | 호출 수정 |
| 2 | API/네트워크 오류 | `error.retryable` 확인 후 재시도 판단 |
| 3 | 인증 필요 (토큰 없음/만료) | `kiwoom auth login` 또는 `KIWOOM_TOKEN` |

## Error codes (`error.code`)

| code | retryable | 의미 |
|---|---|---|
| `CONFIRMATION_REQUIRED` | ✗ | 변이 명령에 `--confirm`/`--yes` 누락 (json/csv 모드) |
| `VALIDATION_FAILED` | ✗ | `order validate` 실패 — 실패 항목은 `error.details` |
| `AUTH_REQUIRED` | ✗ | 토큰 없음. 키체인 불가 환경이면 메시지가 `KIWOOM_TOKEN` 안내 |
| `TOKEN_EXPIRED` | ✗ | 재로그인 필요 |
| `INVALID_INPUT` | ✗ | 파라미터 형식/누락 (upstream 1511/1512/1517/2) |
| `INVALID_API` | ✗ | 잘못된 API ID |
| `NOT_FOUND` | ✗ | 종목/시장 없음 |
| `RATE_LIMITED` | ✓(1700) | 호출 제한 — backoff 후 재시도 |
| `ENV_MISMATCH` | ✗ | 실전/모의 불일치 (appkey/token) |
| `IP_MISMATCH` | ✗ | 발급 IP와 요청 IP 다름 |
| `INVALID_CREDENTIALS` / `TOKEN_ISSUE_FAILED` / `TOKEN_REVOKE_FAILED` | ✗ | 키/발급 문제 |
| `KEYCHAIN_UNAVAILABLE` | ✗ | OS 키체인 접근 불가 — `KIWOOM_TOKEN` 사용 |
| `NETWORK_ERROR` | ✓ | 연결 실패 |
| `UPSTREAM_ERROR` | ✓/✗ | 분류되지 않은 서버 오류 (`upstream_code` 참고) |

## 주문 안전장치

| 플래그 | 효과 |
|---|---|
| `--confirm` / `--yes` | 확인 게이트 통과 (없으면 json/csv에서 `CONFIRMATION_REQUIRED`) |
| `--dry-run` | 전송될 body를 그대로 출력, **아무것도 전송하지 않음**. `--confirm`보다 우선 |
| `--client-order-id KEY` | 멱등키. 같은 키 재실행 → 재전송 없이 이전 응답 + `idempotent_replay: true` |
| `order validate buy\|sell CODE QTY` | read-only 사전점검: `symbol_ok` / `market_open`(KST 시계 휴리스틱, `heuristic: true`) / `sufficient_balance` / `price_ok` |

권장 주문 순서: **validate → --dry-run → --confirm --client-order-id**.
항상 `meta.env`를 확인하고, 실거래(`prod`)에서는 dry-run을 생략하지 마세요.

## describe — CLI 자기서술

```bash
kiwoom describe -f json                 # 전체 명령 트리
kiwoom describe order buy -f json       # 단일 명령 스키마
```

명령별로 `path` / `help` / `arguments[]` / `options[]`(opts, type, default,
required, choices, is_flag)를 반환합니다. 도움말 파싱 대신 이걸 쓰세요.

## 인증 (비대화형 환경)

키체인 접근이 불가한 샌드박스/CI/에이전트 환경에서는 사용자 터미널에서 발급한
토큰을 `KIWOOM_TOKEN` 환경변수로 전달받으세요. appkey/secretkey는 환경변수를
지원하지 않습니다(의도된 제약). `KIWOOM_DOMAIN`(prod/mock), `KIWOOM_PROFILE`,
`KIWOOM_ACCOUNT`도 환경변수로 지정 가능합니다.

## Litmus loop — 전체 흐름 예시

각 단계는 이전 단계의 stdout JSON만으로 구동됩니다 (전부 `-f json`):

```bash
# 1. 시세 — 타입 있는 필드 (파싱 불필요)
$ kiwoom -f json --fields symbol,price,change_direction stock info 005930
{"ok": true, "data": {"symbol": "005930", "price": 70000, "change_direction": "up"}, ...}

# 2. 사전점검 (read-only, 주문 미전송)
$ kiwoom -f json order validate buy 005930 10 --price 70000
{"ok": true, "data": {"valid": true, "checks": {"symbol_ok": true, "market_open": true,
 "sufficient_balance": true, "price_ok": true}, "est_cost": 700000, "heuristic": true}, ...}

# 3. dry-run — 전송될 body 확인 (미전송)
$ kiwoom -f json order buy 005930 10 --price 70000 --type limit --dry-run
{"ok": true, "data": {"would_send": true, "api_id": "kt10000", "est_cost": 700000,
 "currency": "KRW", "env": "mock", "body": {"stk_cd": "005930", "ord_qty": "10", ...}}, ...}

# 4. 실제 주문 — 멱등키와 함께
$ kiwoom -f json order buy 005930 10 --price 70000 --type limit --confirm --client-order-id run-42
{"ok": true, "data": {"order_no": "0000777", "raw": {...}}, ...}

# 4b. 재시도해도 안전 — 같은 키는 재전송하지 않음
$ kiwoom -f json order buy 005930 10 --price 70000 --type limit --confirm --client-order-id run-42
{"ok": true, "data": {"order_no": "0000777", "idempotent_replay": true, ...}, ...}

# 5. 미체결 확인
$ kiwoom -f json --fields order_no,symbol account orders pending --market kr

# 6. 잔고 확인
$ kiwoom -f json --fields symbol,qty,pl_amount account balance --market kr
```

실패 시 분기: `.ok`가 false면 `.error.code`로 스위치 —
`CONFIRMATION_REQUIRED` → `--confirm` 추가, `AUTH_REQUIRED`(exit 3) → 재인증,
`RATE_LIMITED` + `retryable: true` → backoff 재시도, `VALIDATION_FAILED` →
`error.details`의 실패 체크를 해소한 뒤 재시도.
