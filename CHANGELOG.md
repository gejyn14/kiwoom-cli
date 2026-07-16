# Changelog

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
