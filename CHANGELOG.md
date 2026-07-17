# Changelog

## [Unreleased] — 에이전트 계약 강화 (Tier-2)

**Breaking (json 모드만)**: `config set`/`config use`의 오류·성공 출력이
envelope로 바뀝니다 (기존엔 `-f json`에서도 일반 텍스트/에러였습니다).
`TOKEN_EXPIRED`(upstream 8005)의 exit code가 2 → **3**으로 바뀝니다
(인증 오류로 재분류 — 재로그인 필요를 exit code만으로 구분 가능).

### Added
- 전역 `--next-key <값>` / `--all-pages` — 페이지네이션을 명시적으로 제어.
  `--all-pages`는 `cont-yn`이 끝날 때까지 반복해 리스트 필드를 병합(최대
  50페이지, 상한 도달 시 stderr 안내 + `meta.cont` 유지). 둘은 함께 쓸 수
  없음(UsageError). 주문 전송 명령은 두 플래그를 조용히 무시(방어적).
- `kiwoom describe --paths` — 경로+한줄설명 평면 목록만 반환하는 저비용
  발견 모드. `--depth N`으로 하위 명령 재귀 깊이 제한(전체 스키마 모드에서만
  적용되며 `--paths`와 함께 쓰면 무시됨).
- `meta.fields_unmatched` — `--fields`로 지정한 키 중 하나라도 매칭되지 않으면
  (부분 매칭 포함) 매칭 실패한 키 목록을 반환(오타 감지).
- `market` 명령 docstring에 사용 API ID 명시(예: `순위 정보 조회. (ka10016)`)
  — `describe`의 `help` 필드에서 바로 확인 가능.
- `config setup`/`config set`/`config use`/`account list`/`stream types`가
  json/csv 모드에서 대화형 프롬프트 없이 동작하고 envelope로 응답.
- 신규 오류 코드: `NOT_CONFIGURED`(설정 필요, exit 1), `LEDGER_BUSY`(멱등성
  원장 잠금 경합 — 재시도, retryable, exit 2).

### Fixed
- 입력 오류(잘못된 인자/옵션 등)를 json/csv 모드에서 `err_console` 직접
  출력 대신 전부 `fail_input` envelope로 통일(29개 지점) — stdout이 항상
  파싱 가능한 단일 문서가 되도록.
- `httpx.RequestError`(타임아웃 등 `ConnectError` 외 전송 오류)를
  `NETWORK_ERROR`(retryable)로 분류 — 이전엔 처리되지 않아 traceback이
  노출될 수 있었음.
- `kiwoom stream *`의 `websockets` 미설치 시 오류가 json 모드에서
  `DEPENDENCY_MISSING`으로 exit 1 (이전엔 메시지만 출력하고 exit 0), `--raw`를
  json 모드와 함께 쓰면 `INVALID_INPUT`으로 exit 1.
- Ctrl+C로 스트림 종료 시 안내 메시지가 stderr로 출력(stdout 오염 방지).
- `order validate buy|sell`이 `--price`/`--type` 추론 규칙(`_resolve_order_type`)을
  실제 주문 경로와 동일하게 적용 — 사전점검과 실제 전송의 판정이 어긋나지 않음.

## v2.5.1 (2026-07-17) — 주문 안전 패치

### Fixed — 주문 안전 (v2.5.0 전수 리뷰 Tier 1)
- 모든 주문 명령(주식/신용/금현물/미국)에서 주문 **미리보기가 확인 프롬프트보다 먼저** 표시되도록 수정. 미국 주문은 자동 판별된 거래소까지 확인 전에 표시.
- `--price` 지정 + `--type` 미지정 시 **limit으로 추론** (기존: 조용히 시장가 전송). `--price` + 시장가 계열 `--type`은 INVALID_INPUT으로 거부.
- `account exchange apply`(환전)가 공용 confirm_gate를 사용하도록 수정 — json/csv 모드에서 프롬프트 없이 CONFIRMATION_REQUIRED(exit 1), `--yes` 별칭 추가.
- 멱등성 원장 강화: `--client-order-id`가 주문 내용 fingerprint에 바인딩되어 같은 키+다른 주문은 **IDEMPOTENCY_CONFLICT**(exit 1)로 거부. 조회→전송→기록 구간 파일 잠금으로 동시 실행 시 중복 주문 방지.
- `stream`/`watch`가 `--profile`과 `KIWOOM_DOMAIN`을 REST 경로와 동일하게 존중 (기존: 항상 기본 프로필/설정 도메인으로 접속).

### Added
- 신용/금현물 주문에 `--dry-run`, `--client-order-id` 지원 (주식/미국 주문과 동일한 안전장치).

## v2.5.0 (2026-07-17) — 에이전트 네이티브: 정규화 데이터·NDJSON 스트리밍·녹화/히스토리

**기존 `-f json` 소비자에게 breaking change**입니다 — API 응답의 `data`가
정규화된 타입 있는 필드(canonical 영문 이름, 숫자는 number)로 바뀌고 원본은
`data.raw`로 이동했습니다 (리스트 응답은 `{"items": [...], "raw": [...]}`).
기존 키를 그대로 쓰던 스크립트는 `data.raw`에서 읽거나 canonical 이름으로
옮기면 됩니다. table/csv 모드와 exit code 계약(0/1/2/3)은 변경 없습니다.

### Added
- **정규화된 json data**: `cur_prc→price`, `stk_cd→symbol`, `flu_rt→change_pct` 등
  canonical 이름 + 타입 변환(부호 문자열 파싱 불필요), ABS 필드는
  `change_direction`(up/down) 동반, 날짜/시각은 ISO-8601(+09:00).
- **전역 `--fields a,b`**: json `data`(및 내부 리스트 요소)를 지정 키로 투영하고
  `raw`를 제거 — 에이전트 토큰 절약.
- **`kiwoom describe [명령...]`**: 명령 트리/인자/옵션(타입·기본값·choices)
  자기서술. 도움말 파싱 대신 스키마로.
- **NDJSON 스트리밍**: `-f json`에서 모든 `stream` 명령이 REAL 이벤트당 compact
  envelope 한 줄을 출력. 종료조건 `--max-events N` / `--duration 30s|5m|2h` /
  `--until <ISO-8601>` 도달 시 exit 0. ws 오류는 envelope 오류 한 줄 + exit 2(인증 3).
- **녹화와 히스토리**: 모든 `stream` 명령의 `--record [경로]`가 이벤트를 NDJSON
  파일로 저장 (기본 `~/.kiwoom/data/<심볼>_<날짜>.ndjson`). `history list` /
  `history query CODE --from --to [--type]` / `history export CODE --dest
  sqlite|csv|parquet`.
- **AGENTS.md**: envelope·오류코드·안전장치·스트리밍의 기계 계약 문서.
- **benchmark/litmus.sh** + `docs/vs-official.md`: 모의투자 대상 재현 가능한
  litmus loop 증명 스크립트와 공식 CLI(kwcli) 대비 비교 문서. README 최상단에
  "AI-agent native" 섹션.

## v2.4.0 (2026-07-16) — 에이전트 안전 주문 (dry-run · validate · 멱등성)

### Added
- **`--dry-run`** (buy/sell/modify/cancel): 전송 없이 전송될 body를 출력. `--confirm`보다 우선.
- **`order validate buy|sell`**: read-only 사전점검 (symbol_ok / market_open /
  sufficient_balance / price_ok). 실패 시 `VALIDATION_FAILED` + exit 1.
- **`--client-order-id` 멱등키**: 같은 키 재실행 시 재전송 없이 이전 응답을
  반환 (`idempotent_replay: true`). 원장: `~/.kiwoom/idempotency/<프로필>-<환경>.jsonl`.
- **구조화된 확인 게이트**: json/csv 모드에서 `--confirm` 없는 주문은 프롬프트
  대신 `CONFIRMATION_REQUIRED` 오류 + exit 1로 즉시 반환 (에이전트가 멈추지 않음).

### Fixed
- 미국주식 `stock info`의 `stex_tp` 오류 수정.
- 키체인 접근 불가 환경 안내가 `KIWOOM_TOKEN` 경로를 정확히 가리키도록 수정.

## v2.3.0 (2026-07-16) — JSON 응답 envelope v1

`-f json`의 모든 응답(성공/실패)이 하나의 안정적인 envelope로 통일됩니다. **기존 `-f json` 소비자에게는 breaking change**입니다 — 본문이 `data` 필드 아래로 이동했습니다 (`jq '.[]'` → `jq '.data[]'`). table/csv 모드와 exit code 계약(0/1/2/3)은 변경 없습니다.

### Added
- **JSON envelope v1**: `{"ok": bool, "schema": "v1", "data": ..., "meta": {...}, "error": ...}`. `meta`에 해석된 프로필, 도메인(prod/mock), 연속조회 커서(`cont`) 포함.
- **타입화된 에러**: `error`가 `{"code", "retryable", "message", "upstream_code"}` — 키움 공식 오류코드 32개 + HTTP 401/429/5xx를 stable enum(`TOKEN_EXPIRED`, `RATE_LIMITED`, `INVALID_INPUT`, `NOT_FOUND` 등)으로 분류. 에이전트가 메시지 파싱 없이 `error.code`로 분기하고 `retryable`로 재시도를 결정할 수 있습니다. README에 전체 코드 표.
- **연속조회(페이지네이션) 커서 노출**: 응답에 다음 페이지가 있으면 `meta.cont.next_key`로 노출되고, `kiwoom api <api_id> <body> --next-key <커서>`로 다음 페이지를 조회합니다.
- `auth login`/`auth logout`/`config profiles`도 json 모드에서 envelope를 출력합니다. login 응답의 토큰 원문은 env 모드에서만 포함됩니다.
- CLI 인자/옵션 오류도 json 모드에서 `INVALID_INPUT` envelope로 출력됩니다 (exit 1 유지). `api --raw`는 json 모드에서 envelope로 감싸되 `data`에 원본을 그대로 담습니다.

### Fixed
- **`auth login` 실패가 exit 0으로 삼켜지던 버그**: 발급 실패 시 exit 2와 에러 envelope(table 모드는 에러 메시지)를 반환합니다.

## v2.2.1 (2026-07-16) — 에러 처리 개선

v2.2.0 실배포 테스트(샌드박스 셸)에서 발견된 두 이슈를 수정했습니다.

### Fixed
- **키체인 접근 불가 시 크래시 수정**: 키체인이 잠겨 있거나 비대화형 세션이라 쓸 수 없을 때(`config setup`, `auth login` 등) raw traceback 대신 친절한 안내(KIWOOM_TOKEN 환경변수 경로)를 출력하고 exit 1로 종료합니다. v2.1.1은 읽기 실패만 graceful했습니다.
- **토큰 부재 시 exit code 계약 준수**: 토큰이 없으면 요청을 보내기 전에 감지하여 문서화된 exit 3(인증필요) + `kiwoom auth login` 힌트를 출력합니다 (기존: authorization 헤더 없이 요청 후 서버 거절 → exit 2). `-f json`에서는 단일 JSON 에러 문서를 출력합니다.

## v2.2.0 (2026-07-16) — 키체인 없는 환경 지원

### Added
- **`KIWOOM_TOKEN` 환경변수**: OS 키체인에 접근할 수 없는 환경(샌드박스 셸, CI, 컨테이너, AI 에이전트)에서 접근토큰을 환경변수로 전달할 수 있습니다. 설정 시 키체인 토큰보다 우선하며, `auth status`가 토큰 출처(키체인/환경변수)를 표시합니다. appkey/secretkey는 계속 환경변수를 지원하지 않습니다 — 만료·폐기 가능한 접근토큰만 키체인 밖으로 나갑니다.
- **토큰 저장 방식 선택 (`token_storage`)**: `config setup`에서 keychain(기본)/env 중 선택합니다. env 모드에서는 `auth login`이 토큰을 키체인에 저장하지 않고 `export KIWOOM_TOKEN=...` 명령을 출력해 사용자가 직접 관리합니다. 이후 전환은 `kiwoom config set token_storage keychain|env`.

## v2.1.1 (2026-07-16) — 자동화 안정성

### Fixed
- **stdout 순수성**: `-f json`/`-f csv` 모드에서 stdout이 항상 단일 파싱 가능 문서가 되도록 수정. 주문/환전 미리보기 패널·확인 프롬프트·안내 메시지·스트리밍 배너는 stderr로 출력됩니다 (table 모드는 변경 없음). `auth status`/`config show`가 `-f json`에서 JSON 문서를 출력합니다.
- **잠긴/없는 키체인에서 크래시 수정**: 헤드리스 서버, CI, 샌드박스 셸에서 `config show`, `auth status` 등 읽기 명령이 KeyringError 트레이스백 대신 "미설정"으로 정상 동작합니다.
- **exit code 계약 준수**: 잘못된 인자(옵션 값, 누락 인자)가 문서화된 대로 1을 반환합니다 (기존에는 Click 기본값 2로 API 오류와 구분 불가).
- `kiwoom api`: API 오류 시 사람용 텍스트 + exit 0 대신 전역 핸들러를 통해 JSON 에러 문서 + exit 2를 반환합니다.

## v2.1.0 (2026-07-15) — 비밀번호 프롬프트 제거

### Changed
- **인증정보 저장 방식 변경 (breaking)**: 앱 자체 비밀번호/Fernet 암호화 계층을 제거하고 appkey/secretkey를 OS 키체인에 직접 저장합니다. `config setup`, `auth login`, `auth logout`에서 더 이상 비밀번호를 묻지 않습니다 — 모든 명령이 프롬프트 없이 동작합니다 (AI 에이전트/자동화 친화).
- 기존 사용자는 업그레이드 후 `kiwoom config setup`을 한 번 다시 실행해야 합니다 (이전 암호화 형식 자동 감지 + 안내 메시지 표시).

### Removed
- `cryptography` 의존성 제거.

## v2.0.0 (2026-07-15) — 미국주식 지원

키움 REST API의 미국주식 29개 엔드포인트를 기존 명령 체계에 그대로 통합한 메이저 릴리스입니다.
티커만 입력하면 시장을 자동 판별하므로, 미국 주문도 국내 주문과 똑같이 짧게 입력합니다.

> ⚠️ **라이선스 변경 (MIT → Source-Available)** — v2.0.0부터 **kiwoom-cli Source-Available License, Version 1.0**을 적용합니다.
> **개인**은 영리 목적(자기 계좌 매매 등)을 포함해 자유롭게 사용/수정/배포 가능(출처 표기만).
> **조직**이 영리 목적으로 사용할 경우 상용 라이선스가 필요하며, 수정 후 영리 사용 시에는 상용 라이선스를 구매하거나 전체 코드를 동일 라이선스로 공개해야 합니다(어느 경우든 수정 소스를 Licensor에게 전달).
> v2.0 이전 릴리스는 계속 MIT로 제공됩니다. 자세한 내용은 [LICENSE](LICENSE)·[COMMERCIAL.md](COMMERCIAL.md) 참조.

### 새 기능

- **자동 시장 라우팅** — 6자리 숫자(005930)는 국내, 알파벳 티커(NVDA, BRK.B)는 미국으로 자동 판별. `--exchange nasdaq|nyse|amex`로 강제 지정 가능
- **미국주식 주문** — `order buy/sell/modify/cancel`이 미국 티커를 그대로 지원
  - 소수점 가격 (`--price 213.04`, 페니스톡 `0.0012`까지)
  - 미국 전용 주문유형: vwap/twap/vwap-limit/twap-limit/loc (매수·매도), moc/stop/stop-limit (매도 전용, `--stop` 가격)
  - 정정은 가격만(전량), 취소는 전량만 — 키움 API 제약을 명확한 안내와 함께 처리
- **거래소 자동 판별** — usa10098 조회 + `~/.kiwoom/cache/us_exchanges.json` 캐시. 복수 상장 종목만 `--exchange` 필요
- **통합 계좌 뷰** — `account balance`가 국내+미국을 한 테이블로: 종목별 USD/원화 병기, 통화별 소계, 원화 총평가액. `deposit/pnl/orders/history`도 동일하게 통합 (`--market kr|us`로 필터, 한쪽 실패 시 경고 후 나머지 표시)
- **미국 시세/차트** — `stock info/price/orderbook/search`(`--market us`)와 `stock chart tick~year` 6종 (`--krw` 원화 환산 옵션)
- **환전** — 새 `account exchange rate|estimate|apply` 서브그룹 (환율 조회/예상금액/신청, apply는 확인 게이트 필수)
- **주문가능수량** — `account orderable margin-qty NVDA --price 213.04`
- **USD 포매팅** — 소수점 4자리 보존, 후행 0 제거, 방향 부호 규칙 유지
- **AI/자동화 친화** — 통합 명령의 `--format json`이 단일 `{"kr", "us"}` 문서를 출력, exit code 계약 유지 (0=성공, 1=입력오류, 2=API오류)

### 변경 사항

- `order buy/sell/modify`의 `--price`/`PRICE`가 정수→실수 타입으로 변경 (국내 경로는 정수만 허용, 동작 동일)
- `account balance/deposit/pnl/orders/history`가 기본적으로 국내+미국 통합 표시 (`--market kr`로 기존 국내 전용 동작)
- SECURITY.md의 주문 안전 설명을 실제 동작(미리보기 + 대화형 확인 + `--confirm`)에 맞게 정정

### 내부

- 신규 패키지 `kiwoom_cli/commands/us/` (detect/order_ops/stock_ops/account_ops/exchange)
- API 레지스트리 188 → 217개 (REST), 테스트 155 → 245개
