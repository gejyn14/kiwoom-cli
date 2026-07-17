# kiwoom-cli

**키움증권 REST API 전체를 터미널에서.** 시세 조회부터 주문, 실시간 스트리밍, 미국주식까지 — 명령어 하나로.

[![PyPI](https://img.shields.io/pypi/v/kiwoom-cli)](https://pypi.org/project/kiwoom-cli/)
[![Python](https://img.shields.io/pypi/pyversions/kiwoom-cli)](https://pypi.org/project/kiwoom-cli/)
[![CI](https://github.com/gejyn14/kiwoom-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/gejyn14/kiwoom-cli/actions/workflows/ci.yml)
[![Downloads](https://img.shields.io/pypi/dm/kiwoom-cli)](https://pypi.org/project/kiwoom-cli/)
[![License](https://img.shields.io/badge/license-Source--Available-blue)](LICENSE)

```bash
pip install kiwoom-cli
```

```bash
$ kiwoom stock price 005930          # 삼성전자 현재가
$ kiwoom order buy NVDA 10 --price 213.04   # 미국주식도 그대로
$ kiwoom -f json account balance | jq       # AI 에이전트·스크립트 친화
```

## AI-agent native

모든 명령이 `-f json`에서 **하나의 안정된 envelope**를 stdout에 출력한다
(진행 메시지는 전부 stderr — stdout은 항상 파싱 가능한 단일 문서):

```json
{"ok": true, "schema": "v1",
 "data": {"symbol": "005930", "price": 70000, "change_direction": "up"},
 "meta": {"profile": "default", "env": "mock", "cont": null},
 "error": null}
```

`data`는 타입 있는 정규화 필드(부호 문자열 파싱 불필요), `error.code`는
안정적인 enum 32종(`retryable` 포함), exit code는 0=성공 / 1=입력 / 2=API /
3=인증으로 고정 — 에이전트가 문자열이 아니라 계약으로 분기한다.

**주문 안전장치** — 에이전트가 돈을 다루는 경로 전체에 가드가 있다:

```bash
kiwoom -f json order validate buy 005930 10          # read-only 사전점검
kiwoom -f json order buy 005930 10 --price 70000 --dry-run   # 전송될 body만 확인
kiwoom -f json order buy 005930 10 --price 70000 --confirm --client-order-id run-42
# 같은 키 재실행 → 재전송 없이 이전 응답 (idempotent_replay: true)
```

`--confirm` 없이 json 모드로 주문하면 프롬프트에 멈추는 대신 구조화된
`CONFIRMATION_REQUIRED` 오류로 즉시 반환된다 — 에이전트가 걸려서 죽지 않는다.

**에이전트 퀵스타트**:

```bash
price=$(kiwoom -f json --fields price stock info 005930 | jq .data.price)
kiwoom -f json stream quote 005930 --max-events 10           # NDJSON 10줄 후 exit 0
kiwoom stream quote 005930 --record --duration 30m           # 녹화 → history query/export
kiwoom describe order buy -f json                            # 명령 스키마 자기서술
```

- 기계 계약 전체(envelope·error code·litmus loop): **[AGENTS.md](AGENTS.md)**
- 재현 가능한 증명 스크립트(모의투자): **[benchmark/litmus.sh](benchmark/litmus.sh)**
- 공식 CLI(kwcli)와의 정직한 비교: **[docs/vs-official.md](docs/vs-official.md)**

## 왜 kiwoom-cli인가

- **236개 API 전체 지원** — REST 217개 + WebSocket 실시간 19종. 시세·차트·계좌·주문·순위·업종·테마·ETF·ELW·금현물·미국주식까지 키움 REST API를 빠짐없이 커버합니다.
- **프롬프트 제로** — 인증정보는 OS 키체인에 저장되고, 어떤 명령도 비밀번호를 묻지 않습니다. `gh`/`aws`/`docker`와 같은 모델. 크론잡, CI, AI 에이전트가 그대로 돌립니다.
- **AI 에이전트 퍼스트** — 구조화된 JSON 출력(`-f json`), 일관된 exit code(0/1/2/3), 주문 확인 게이트(`--confirm`). Claude Code, 자동매매 스크립트에 바로 연결됩니다.
- **미국주식 자동 라우팅** — `005930`은 국내로, `NVDA`는 미국으로. 거래소(NASDAQ/NYSE/AMEX)도 자동 판별. 국내+미국 통합 잔고를 원화 총계로 보여줍니다.
- **사람에게도 친절** — Rich 테이블, 상승=빨강/하락=파랑 색상, 실시간 TUI 대시보드, shell 자동완성.
- **246개 테스트 + CI** — Python 3.10–3.13 매트릭스, CodeQL 정적 분석.

> 📖 **전체 문서는 [Wiki](https://github.com/gejyn14/kiwoom-cli/wiki)에서** — 설치 가이드, 명령어 레퍼런스, 미국주식·AI 에이전트·멀티 프로필 가이드, 릴리스 노트.

## 최근 업데이트

### v2.5 — 에이전트 네이티브: 정규화 데이터·NDJSON 스트리밍·녹화 (2026-07)

`-f json`의 `data`가 정규화된 타입 있는 필드로 바뀌고 원본은 `data.raw`로
이동했습니다 (**기존 `-f json` 소비자에게는 breaking** — 기존 키는 `data.raw`
아래에 그대로 있습니다). 전역 `--fields` 투영, `kiwoom describe` 자기서술,
NDJSON 스트리밍(`--max-events`/`--duration`/`--until` 종료조건),
`--record` 녹화 + `history query/export`, [AGENTS.md](AGENTS.md) 기계 계약이
추가됐습니다. 위 [AI-agent native](#ai-agent-native) 섹션 참고.

### v2.1 — 비밀번호 프롬프트 완전 제거 (2026-07)

앱 자체 암호화 계층을 걷어내고 모든 인증정보를 OS 키체인에 직접 저장합니다. `config setup`, `auth login` 어디서도 더 이상 비밀번호를 묻지 않습니다. 기존 사용자는 업그레이드 후 `kiwoom config setup` 한 번만 다시 실행하면 됩니다.

### v2.0 — 미국주식 지원 (2026-07)

미국주식 29개 엔드포인트를 기존 명령 체계에 그대로 통합했습니다. 티커만 입력하면 시장을 자동 판별하므로 미국 주문도 국내 주문과 똑같이 짧습니다. 소수점 가격, stop/stop-limit/vwap/twap 주문유형, 환전(`account exchange`), 국내+미국 통합 계좌 뷰를 지원합니다.

전체 변경 내역: [CHANGELOG](CHANGELOG.md) · [Wiki 릴리스 노트](https://github.com/gejyn14/kiwoom-cli/wiki/Release-Notes)

## 시작하기

[키움증권 REST API](https://openapi.kiwoom.com)에서 appkey/secretkey를 발급받은 뒤:

```bash
# 1. 초기 설정 (appkey, secretkey → OS 키체인)
#    토큰 저장 방식도 여기서 선택: keychain (기본) 또는 env (KIWOOM_TOKEN 직접 관리)
kiwoom config setup

# 2. 토큰 발급
kiwoom auth login

# 3. 끝. 이후 모든 명령은 프롬프트 없이 동작
kiwoom stock info 005930
```

### 모의투자 vs 실거래

`config setup` 시 도메인을 선택합니다. 이후 변경:

```bash
kiwoom config domain mock   # 모의투자 (기본값, 테스트용)
kiwoom config domain prod   # 실거래

kiwoom config show          # 현재 설정 확인
```

모의투자는 KRX만 지원됩니다. 실거래 전환 후에는 `kiwoom auth login`으로 토큰을 재발급하세요.

### 환경변수 설정

도메인, 계좌번호, 프로필, 토큰은 환경변수로도 설정 가능합니다.

```bash
export KIWOOM_DOMAIN="prod"       # prod 또는 mock
export KIWOOM_ACCOUNT="1234567"   # 선택
export KIWOOM_PROFILE="isa"       # 선택
export KIWOOM_TOKEN="..."         # 선택: 키체인 대신 사용할 접근토큰 (샌드박스/CI용)
```

appkey/secretkey는 보안을 위해 환경변수를 지원하지 않습니다. 반드시 `kiwoom config setup`으로 OS 키체인에 저장하세요. `KIWOOM_TOKEN`은 만료·폐기 가능한 접근토큰만 담는 통로로, 키체인에 접근할 수 없는 환경(샌드박스, CI, AI 에이전트)에서 사용합니다 — 설정 시 키체인 토큰보다 우선합니다.

### 토큰 저장 방식 (keychain vs env)

`config setup`에서 토큰 저장 방식을 선택합니다.

- **keychain** (기본): `auth login`이 토큰을 OS 키체인에 저장합니다. 본인 터미널에서 쓰는 일반적인 방식.
- **env**: 토큰을 키체인에 저장하지 않습니다. `auth login`이 토큰과 `export KIWOOM_TOKEN=...` 명령을 출력하면 셸에서 실행하세요. 키체인 접근이 불가능한 환경(샌드박스, CI, 컨테이너)이 주 작업 환경일 때 적합합니다.

이후 전환은 `kiwoom config set token_storage keychain|env`.

### 멀티 프로필

계좌별로 다른 appkey/secretkey를 사용할 수 있습니다.

```bash
# 프로필별 설정
kiwoom config setup --profile default   # 메인계좌
kiwoom config setup --profile isa       # ISA계좌

# 프로필 설정 변경
kiwoom config set domain prod           # 도메인 변경
kiwoom config set account 1234567       # 계좌번호 설정
kiwoom -p isa config set domain mock    # 특정 프로필

# 프로필 전환 / 목록
kiwoom config use isa
kiwoom config profiles

# 특정 프로필로 사용
kiwoom -p isa account balance
kiwoom -p isa auth login
```

## AI 에이전트와 함께 쓰기

kiwoom-cli는 AI 에이전트가 도구로 쓰는 것을 처음부터 염두에 두고 설계됐습니다.

```bash
# 구조화된 JSON — 파싱이 필요 없는 출력
kiwoom -f json stock info 005930
kiwoom -f json market rank volume | jq '.[].stk_nm'

# 일관된 exit code — 0=성공, 1=입력오류, 2=API오류, 3=인증필요
kiwoom stock price 005930 || echo "재시도 또는 재인증"

# 주문은 기본 확인 게이트, 자동화 시에만 --confirm으로 명시적 스킵
kiwoom order buy 005930 10 --type market --confirm

# 주문 3단 안전장치: 사전점검 → dry-run → 멱등 주문
kiwoom -f json order validate buy 005930 10 --price 70000
kiwoom -f json order buy 005930 10 --price 70000 --type limit --dry-run
kiwoom -f json order buy 005930 10 --price 70000 --type limit --confirm --client-order-id run-42
```

- 어떤 명령도 비밀번호·생체인증을 요구하지 않으므로 에이전트 세션이 중간에 멈추지 않습니다. json/csv 모드에서는 확인 프롬프트 대신 `CONFIRMATION_REQUIRED` 오류(exit 1)로 응답합니다.
- 페이지네이션(연속조회)은 전역 `--all-pages`(끝까지 자동 수집·리스트 병합) 또는 `--next-key <값>`(특정 페이지부터 재조회)로 명시 제어합니다 — 커서를 직접 다루지 않아도 됩니다.
- `kiwoom describe --paths -f json`으로 전체 명령 경로를 저비용에 훑어본 뒤, 필요한 명령만 `kiwoom describe <경로> -f json`으로 상세 스키마를 조회하세요.
- 자세한 패턴은 [Wiki: AI 에이전트 가이드](https://github.com/gejyn14/kiwoom-cli/wiki/AI-Agents) 참고.

### 샌드박스 환경 (키체인 접근 불가)

샌드박스 셸, CI, 컨테이너에서는 OS 키체인을 읽을 수 없습니다. 이때는 본인 터미널에서 토큰을 발급받아 `KIWOOM_TOKEN`으로 전달하세요 — appkey/secretkey는 키체인 밖으로 나가지 않고, 토큰은 만료·폐기 가능합니다.

```bash
# 본인 터미널에서 (하루 1회 정도) — env 모드라면 login이 export 명령을 그대로 출력
kiwoom config set token_storage env
kiwoom auth login
export KIWOOM_TOKEN='...'   # login 출력의 export 라인을 복사해 실행

# 이 셸에서 에이전트를 실행하면 환경변수가 상속되어 모든 명령이 동작
kiwoom auth status   # 토큰 있음 (환경변수 KIWOOM_TOKEN)
```

keychain 모드를 유지하면서 일회성으로 꺼내 쓰려면:

```bash
export KIWOOM_TOKEN=$(security find-generic-password -s kiwoom-cli -a "default:token" -w)  # macOS
```

## 명령어 구조

```
kiwoom [--format table|json|csv] [--no-color] [-p 프로필]
├── config      설정 (setup / show / domain / profiles)
├── auth        인증 (login / logout / status)
├── stock       종목 조회 (info / orderbook / chart / compare ...)
├── account     계좌 조회 (balance / deposit / returns / pnl ...)
├── order       주문 (buy / sell / modify / cancel / credit / gold)
├── market      시장 정보 (rank / sector / theme / etf / elw / gold)
├── stream      실시간 스트리밍 (quote / orderbook / order / vi ...)
├── watch       실시간 종목 모니터링 (TUI)
├── dashboard   대시보드 (계좌 + 거래량 상위 한눈에)
└── api         Raw API 호출
```

---

## stock - 종목 조회

```bash
kiwoom stock info 005930              # 기본정보 (PER, PBR, 시가총액 등)
kiwoom stock price 005930             # 현재가 한 줄
kiwoom stock orderbook 005930         # 10단계 호가창
kiwoom stock daily 005930             # 일별 시세
kiwoom stock daily 005930 --type week # 주별 시세
kiwoom stock exec 005930              # 체결정보
kiwoom stock trader 005930            # 거래원
kiwoom stock foreign 005930           # 외국인 매매동향
kiwoom stock institution 005930       # 기관 매매동향
kiwoom stock short 005930 --from 20260101 --to 20260330  # 공매도 추이
kiwoom stock sync                        # 전 시장 종목 리스트 다운로드 (캐시)
kiwoom stock search 삼성                 # 캐시에서 종목 검색
kiwoom stock search 삼성 --market kospi  # 코스피만 필터
kiwoom stock watchlist "005930|000660" # 관심종목
kiwoom stock compare 005930 000660     # 종목 비교 (최대 여러 종목)
```

### 차트

```bash
kiwoom stock chart tick 005930 --range 1        # 틱
kiwoom stock chart minute 005930 --interval 5    # 5분봉
kiwoom stock chart day 005930 --base-date 20260301   # 일봉
kiwoom stock chart week 005930 --base-date 20260301  # 주봉
kiwoom stock chart month 005930 --base-date 20260301 # 월봉
kiwoom stock chart year 005930 --base-date 20260301  # 년봉
```

### 투자자/분석

```bash
kiwoom stock investor daily-trade --from 20260301 --to 20260330
kiwoom stock investor by-stock 005930 --date 20260301
kiwoom stock investor program-top
kiwoom stock analysis vi-trigger
kiwoom stock analysis per-rank --type low-per
kiwoom stock lending trend
kiwoom stock credit trend 005930 --date 20260301 --type loan
```

<details>
<summary>전체 stock 하위 명령어</summary>

| 명령             | 설명                                                  |
| ---------------- | ----------------------------------------------------- |
| `info`           | 종목 기본정보                                         |
| `price`          | 현재가 한 줄                                          |
| `detail`         | 종목정보 상세                                         |
| `orderbook`      | 10단계 호가창                                         |
| `daily`          | 일/주/월별 시세                                       |
| `timeprice`      | 시분 시세                                             |
| `daily-price`    | 일별주가                                              |
| `after-hours`    | 시간외단일가                                          |
| `quote-info`     | 시세표성정보                                          |
| `exec`           | 체결정보                                              |
| `trader`         | 거래원                                                |
| `today-exec`     | 당일/전일 체결                                        |
| `today-volume`   | 당일/전일 체결량                                      |
| `tick-strength`  | 체결강도 시간별                                       |
| `daily-strength` | 체결강도 일별                                         |
| `foreign`        | 외국인 매매동향                                       |
| `institution`    | 기관 매매동향                                         |
| `short`          | 공매도 추이                                           |
| `sync`           | 전 시장 종목 리스트 다운로드 (캐시 저장)              |
| `search`         | 종목 검색 (캐시 기반, 시장/유형 필터)                 |
| `watchlist`      | 관심종목                                              |
| `brokers`        | 회원사 리스트                                         |
| `compare`        | 복수 종목 비교                                        |
| `chart *`        | 틱/분봉/일봉/주봉/월봉/년봉, 투자자별 차트            |
| `investor *`     | 기관매매, 투자자별매매, 프로그램매매 등 10개          |
| `analysis *`     | 거래상세, 거래량갱신, 매물대, PER, VI, 증권사 등 10개 |
| `lending *`      | 대차거래 추이/상위/종목별/내역                        |
| `credit *`       | 신용매매동향, 신용융자 가능                           |

</details>

---

## account - 계좌 조회

```bash
kiwoom account list                # 계좌번호
kiwoom account balance             # 잔고 + 보유종목 + 손익 (국내+미국 통합)
kiwoom account deposit             # 예수금
kiwoom account asset               # 추정자산
kiwoom account today               # 당일현황
kiwoom account returns summary     # 수익률
kiwoom account pnl today 005930    # 당일 실현손익
kiwoom account orders pending      # 미체결 주문
kiwoom account orders executed     # 체결 내역
kiwoom account holdings eval       # 잔고내역
kiwoom account orderable amount 005930 --side buy --price 70000
```

<details>
<summary>전체 account 하위 명령어</summary>

| 그룹        | 명령            | 설명                |
| ----------- | --------------- | ------------------- |
| -           | `list`          | 계좌번호 조회       |
| -           | `balance`       | 계좌 평가현황       |
| -           | `deposit`       | 예수금 상세         |
| -           | `asset`         | 추정자산            |
| -           | `today`         | 당일현황            |
| -           | `margin-detail` | 증거금 세부내역     |
| `returns`   | `summary`       | 계좌 수익률         |
| `returns`   | `daily-balance` | 일별 잔고수익률     |
| `returns`   | `daily-detail`  | 일별 수익률 상세    |
| `returns`   | `daily-asset`   | 일별 예탁자산       |
| `pnl`       | `today`         | 당일 실현손익       |
| `pnl`       | `by-date`       | 일자별 실현손익     |
| `pnl`       | `by-period`     | 기간별 실현손익     |
| `pnl`       | `daily`         | 일자별 실현손익     |
| `orders`    | `pending`       | 미체결 주문         |
| `orders`    | `executed`      | 체결 내역           |
| `orders`    | `detail`        | 주문체결 상세       |
| `orders`    | `status`        | 주문체결 현황       |
| `orders`    | `split-detail`  | 분할주문 상세       |
| `holdings`  | `eval`          | 계좌평가 잔고       |
| `holdings`  | `settled`       | 체결잔고            |
| `holdings`  | `next-settle`   | 익일결제예정        |
| `orderable` | `amount`        | 주문가능 금액       |
| `orderable` | `margin-qty`    | 증거금율별 수량     |
| `orderable` | `credit-qty`    | 신용보증금율별 수량 |
| `exchange`  | `rate`          | 환율 조회           |
| `exchange`  | `estimate`      | 환전 예상금액       |
| `exchange`  | `apply`         | 환전 신청           |
| `history`   | `transactions`  | 위탁종합 거래내역   |
| `history`   | `journal`       | 당일 매매일지       |

</details>

---

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

자세한 가이드: [Wiki: 미국주식](https://github.com/gejyn14/kiwoom-cli/wiki/US-Stocks)

---

## order - 주문

주문은 실행 전 미리보기 + 대화형 확인이 기본입니다. 자동화 시에만 `--confirm`(별칭 `--yes`)으로 스킵하세요. `-f json`/`-f csv` 모드는 절대 프롬프트하지 않습니다 — `--confirm` 없이 실행하면 `CONFIRMATION_REQUIRED` 오류(exit 1)로 응답해 에이전트 세션이 멈추지 않습니다.

```bash
# 안전장치 (에이전트/자동화)
kiwoom order validate buy 005930 10 --price 70000 -f json        # 사전점검 (주문 미전송)
kiwoom order buy 005930 10 --price 70000 --type limit --dry-run  # 전송될 내용만 확인 (미전송)
kiwoom order buy 005930 10 --price 70000 --type limit --confirm --client-order-id run-42  # 멱등 주문

# 주식
kiwoom order buy 005930 10 --type market --confirm          # 시장가 매수
kiwoom order buy 005930 10 --price 70000 --type limit --confirm  # 지정가 매수
kiwoom order sell 005930 10 --type market --confirm         # 매도
kiwoom order modify 0000139 005930 1 70000 --confirm        # 정정
kiwoom order cancel 0000140 005930 --confirm                # 취소

# 신용
kiwoom order credit buy 005930 10 --type market --confirm
kiwoom order credit sell 005930 10 --type market --confirm

# 금현물
kiwoom order gold buy M04020000 1 --type market --confirm
kiwoom order gold balance             # 잔고
kiwoom order gold pending             # 미체결

# 조건검색
kiwoom order condition list
kiwoom order condition search 001 --confirm
```

주문유형: `limit` `market` `conditional` `after-hours` `pre-market` `single` `best` `first` `ioc` `market-ioc` `best-ioc` `fok` `market-fok` `best-fok` `stop` `mid` `mid-ioc` `mid-fok`

`--price`를 지정하고 `--type`을 생략하면 지정가(limit)로 주문됩니다. 시장가 주문은 `--price` 없이 실행하세요.

### 주문 안전장치 (v2.4)

- `--dry-run` — 실제 전송될 request body를 그대로 출력하고 아무것도 전송하지 않습니다. `--confirm`보다 우선합니다. 시장가 주문은 현재가를 조회해 예상비용(`est_cost`)을 계산합니다.
- `--client-order-id KEY` — 멱등성 키. 같은 키로 재실행하면 재전송 없이 이전 응답을 반환합니다(`idempotent_replay: true`). 네트워크 단절·에이전트 재시도로 인한 중복 주문을 방지합니다. 원장: `~/.kiwoom/idempotency/<프로필>-<환경>.jsonl`
- `order validate buy|sell CODE QTY` — read-only 사전점검. `symbol_ok` / `market_open`(KST 시계 휴리스틱, 공휴일 미감지) / `sufficient_balance` / `price_ok`를 점검하고, 실패 시 `VALIDATION_FAILED` + 실패 항목을 `error.details`에 담아 exit 1. 국내 주식 전용.

---

## market - 시장 정보

### 순위

```bash
kiwoom market rank volume           # 거래량 상위
kiwoom market rank amount           # 거래대금 상위
kiwoom market rank change           # 등락률 상위
kiwoom market rank surge            # 가격 급등락
kiwoom market rank hot              # 실시간 조회 순위
kiwoom market rank limit            # 상하한가
kiwoom market rank foreign-period   # 외인 기간별 매매
kiwoom market rank foreign-inst     # 외국인/기관 매매
```

<details>
<summary>전체 rank 명령어 (28개)</summary>

`volume` `prev-volume` `amount` `change` `expected-change` `surge` `hot` `limit` `new-highlow` `near-highlow` `volume-surge` `orderbook-top` `orderbook-surge` `balance-rate-surge` `credit-ratio` `foreign-period` `foreign-consecutive` `foreign-exhaust` `foreign-broker` `foreign-inst` `investor-top` `broker-by-stock` `broker-top` `major-trader` `net-buyer` `top-exit` `same-net-trade` `afterhours-change`

</details>

### 업종 / 테마 / ETF / ELW / 금현물 / 프로그램

```bash
kiwoom market sector current 001        # 업종 현재가
kiwoom market sector index              # 전업종 지수
kiwoom market sector chart day 001 --date 20260301

kiwoom market theme groups              # 테마 그룹
kiwoom market theme stocks THEMA001     # 테마 구성종목

kiwoom market etf all                   # ETF 전체 시세
kiwoom market etf info 069500           # ETF 종목정보

kiwoom market elw detail 580001         # ELW 상세정보
kiwoom market elw search                # ELW 조건검색

kiwoom market gold price                # 금현물 시세
kiwoom market gold orderbook            # 금현물 호가

kiwoom market program time-trend --date 20260301
kiwoom market program stock-daily 005930
```

---

## stream - 실시간 스트리밍

WebSocket 실시간 시세. Ctrl+C로 종료.

```bash
kiwoom stream quote 005930              # 체결 실시간
kiwoom stream orderbook 005930          # 호가 실시간
kiwoom stream order                     # 주문체결 (계좌)
kiwoom stream balance                   # 잔고 변동 (계좌)
kiwoom stream vi 005930                 # VI 발동/해제
kiwoom stream multi 005930              # 체결+호가 동시
kiwoom stream quote 005930 000660 035420  # 복수 종목
kiwoom stream custom 0B,0D 005930       # 타입 직접 지정
kiwoom stream types                     # 타입 코드 목록
```

| 코드 | 명령            | 설명         |
| ---- | --------------- | ------------ |
| 00   | `order`         | 주문체결     |
| 04   | `balance`       | 잔고         |
| 0A   | `price`         | 주식기세     |
| 0B   | `quote`         | 주식체결     |
| 0C   | `best-bid`      | 우선호가     |
| 0D   | `orderbook`     | 호가잔량     |
| 0E   | `after-hours`   | 시간외호가   |
| 0F   | `trader`        | 당일거래원   |
| 0G   | `etf-nav`       | ETF NAV      |
| 0H   | `expected`      | 예상체결     |
| 0I   | `gold`          | 국제금환산   |
| 0J   | `sector-index`  | 업종지수     |
| 0U   | `sector-change` | 업종등락     |
| 0g   | `stock-info`    | 종목정보     |
| 0m   | `elw-theory`    | ELW 이론가   |
| 0s   | `market-time`   | 장시작시간   |
| 0u   | `elw-indicator` | ELW 지표     |
| 0w   | `program`       | 프로그램매매 |
| 1h   | `vi`            | VI발동/해제  |

### 녹화와 조회 (Recording & history)

모든 stream 명령에 `--record`를 붙이면 수신 이벤트를 NDJSON 파일로 저장한다
(출력 형식과 무관 — 테이블을 보면서도 기록된다). 경로를 생략하면
`~/.kiwoom/data/<심볼>_<날짜>.ndjson`에 심볼별로 쌓이고, 경로를 주면 한 파일에 모인다.
저장된 데이터는 `history`로 다시 읽는다.

```bash
# 1. 캡처 — 장중 30분간 체결 실시간을 녹화
kiwoom stream quote 005930 --record --duration 30m

# 2. 조회 — 시각 범위/타입으로 필터 (파일은 한 줄씩 스트리밍으로 읽음)
kiwoom history list                     # 녹화 파일 목록 (심볼·날짜·건수·시작/종료 ts)
kiwoom history query 005930 --from 2026-07-16T10:00:00 --to 2026-07-16T10:30:00 --type 0B

# 3. 내보내기 — sqlite/csv (parquet은 pandas+pyarrow 설치 시)
kiwoom history export 005930 --dest sqlite --out samsung.sqlite
kiwoom history export 005930 --dest csv --from 2026-07-16T09:00:00 --to 2026-07-16T15:30:00
```

sqlite 내보내기는 `events(ts, symbol, type, price, volume, raw_json)` 테이블과
`(symbol, ts)` 인덱스를 만든다.

---

## dashboard / Raw API

```bash
kiwoom dashboard                        # 계좌 요약 + 거래량 상위 한눈에

kiwoom api ka10001 '{"stk_cd":"005930"}'        # Raw API — 테이블 출력
kiwoom api ka10001 '{"stk_cd":"005930"}' --raw   # JSON 원본
```

---

## 출력 형식

모든 명령에 `-f` / `--format` 옵션 사용 가능:

```bash
kiwoom stock info 005930                # 기본: Rich 테이블
kiwoom -f json stock info 005930        # JSON (파이핑, AI 에이전트용)
kiwoom -f csv stock daily 005930        # CSV (엑셀, 데이터 분석용)
kiwoom --no-color stock info 005930     # 색상 없이 (파일 저장용)
```

```bash
# jq로 필터링 (본문은 .data 아래)
kiwoom -f json market rank volume | jq '.data[].stk_nm'

# CSV를 파일로 저장
kiwoom -f csv stock daily 005930 > samsung_daily.csv
```

### JSON 응답 envelope (v1)

`-f json`의 모든 응답은 성공/실패 모두 하나의 안정적인 envelope로 감쌉니다. table/csv 모드는 그대로입니다.

```json
{
  "ok": true,
  "schema": "v1",
  "data": { "stk_nm": "삼성전자", "cur_prc": "+70000" },
  "meta": { "profile": "default", "env": "prod", "cont": { "next_key": "..." } },
  "error": null
}
```

- `data` — 기존 응답 본문 그대로 (`return_code`/`return_msg`만 제거)
- `meta.profile` / `meta.env` — 해석된 프로필과 도메인(`prod`/`mock`)
- `meta.cont` — 연속조회 커서. 값이 있으면 다음 페이지가 존재: `kiwoom api <api_id> <body> --next-key <meta.cont.next_key>`
- 실패 시 `ok: false`, `data: null`이고 `error`에 안정적인 코드가 담깁니다:

```json
{ "code": "TOKEN_EXPIRED", "retryable": false, "message": "Token이 유효하지 않습니다", "upstream_code": 8005 }
```

`error.code`는 키움 오류코드/HTTP 상태를 분류한 stable enum입니다 — 에이전트는 메시지 문자열 대신 이 코드로 분기하세요:

| code | retryable | 의미 (upstream) |
| --- | :---: | --- |
| `INVALID_INPUT` | X | 입력 값/필수 파라미터 오류 (2, 1511, 1512, 1517) |
| `INVALID_API` | X | 잘못된 API ID (1501, 1504, 1505) |
| `NOT_FOUND` | X | 시장/종목 정보 없음 (1901, 1902) |
| `AUTH_REQUIRED` | X | 인증 헤더/토큰 누락 (1513~1516, 토큰 미보유 시 로컬 감지) |
| `TOKEN_EXPIRED` | X | 토큰 무효·만료 (8005, HTTP 401) |
| `TOKEN_ISSUE_FAILED` | X | 토큰 발급 실패 (8003, 8006, 8009, 8011, 8012) |
| `TOKEN_REVOKE_FAILED` | X | 토큰 폐기 실패 (8015, 8016) |
| `INVALID_CREDENTIALS` | X | appkey/secretkey 검증 실패 (8001, 8002, 8020) |
| `IP_MISMATCH` | X | 발급 IP와 요청 IP 불일치 (8010) |
| `ENV_MISMATCH` | X | 실전/모의 구분 불일치 (8030, 8031) |
| `DEVICE_AUTH_FAILED` | X | 단말기 인증 실패 (8040, 8050, 8103) |
| `RATE_LIMITED` | 1700·429는 O | 요청 개수 초과 (1700, HTTP 429) / 재귀 호출 제한 (1687) |
| `NETWORK_ERROR` | O | API 서버 연결 실패 |
| `KEYCHAIN_UNAVAILABLE` | X | OS 키체인 접근 불가 (샌드박스/CI) |
| `NOT_CONFIGURED` | X | `config setup` 미실행 (CLI 로컬 감지) |
| `DEPENDENCY_MISSING` | X | 선택적 패키지 미설치 (예: `websockets` 없이 `stream`) |
| `LEDGER_BUSY` | O | 멱등성 원장 잠금 경합 — 재시도 (exit 2) |
| `UPSTREAM_ERROR` | 5xx·1999는 O | 미분류 업스트림 오류 (기본값) |

CLI 수준의 인자/옵션 오류(잘못된 값, 인자 누락 등)도 json 모드에서는 `INVALID_INPUT` envelope로 출력됩니다 (`upstream_code: null`, exit 1). `kiwoom api --raw`는 json 모드에서도 envelope로 감싸되 `data`에 응답 원본을 그대로(`return_code` 포함) 담습니다. `auth login`은 json 모드에서 `{profile, token_storage, saved, token}`을 반환하며, `token` 원문은 env 모드에서만 포함됩니다.

exit code 계약은 그대로입니다 (0=성공, 1=입력오류, 2=API오류, 3=인증필요).

## Shell 자동완성

```bash
# Bash
eval "$(_KIWOOM_COMPLETE=bash_source kiwoom)"

# Zsh
eval "$(_KIWOOM_COMPLETE=zsh_source kiwoom)"

# Fish
eval (env _KIWOOM_COMPLETE=fish_source kiwoom)
```

## Exit Codes

| 코드 | 의미                    |
| ---- | ----------------------- |
| 0    | 성공                    |
| 1    | 입력 오류 (잘못된 인자) |
| 2    | API/네트워크 오류       |
| 3    | 인증 필요 (토큰 만료)   |

## 보안

모든 인증정보(appkey, secretkey, 토큰)는 **OS 키체인**(macOS Keychain / Windows Credential Manager / Linux Secret Service)에 저장됩니다. 파일로 존재하지 않으며, 키체인이 디스크 저장 시 암호화를 담당합니다. `gh`, `aws`, `docker` CLI와 동일한 모델입니다.

| 항목               | 저장 방식                                  | 프롬프트 |
| ------------------ | ------------------------------------------ | :------: |
| appkey / secretkey | OS 키체인                                  |    X     |
| 토큰               | OS 키체인 또는 KIWOOM_TOKEN 환경변수 (선택) |    X     |
| config.toml        | 도메인, 계좌번호, 토큰 저장 방식만         |    X     |

- 모든 명령어는 비밀번호/생체인증 프롬프트 없이 동작 (AI 에이전트·자동화 친화적)
- 앱 자체 암호화 계층은 의도적으로 두지 않음 — 추가 계층은 명령마다 잠금 해제 프롬프트를 요구하게 되어 CLI 사용성을 해침
- v2.0 이하에서 업그레이드한 경우: 암호화 저장소 형식이 제거되어 `kiwoom config setup`을 한 번 다시 실행해야 합니다
- 주문은 기본적으로 미리보기 + 대화형 확인을 거칩니다 (`--confirm`으로 스킵)

자세한 내용: [Wiki: 보안 모델](https://github.com/gejyn14/kiwoom-cli/wiki/Security) · [SECURITY.md](SECURITY.md)

## 참고

| 항목             | 값                                       |
| ---------------- | ---------------------------------------- |
| 설정 파일        | `~/.kiwoom/config.toml` (도메인, 계좌, 토큰 저장 방식만) |
| appkey/secretkey | OS 키체인                                |
| 토큰             | OS 키체인 또는 KIWOOM_TOKEN 환경변수 (setup에서 선택) |
| 캐시 디렉터리    | `~/.kiwoom/cache/`                       |
| 운영 도메인      | `https://api.kiwoom.com`                 |
| 모의투자 도메인  | `https://mockapi.kiwoom.com`             |
| WebSocket        | `wss://api.kiwoom.com:10000`             |

- `kiwoom <명령> --help`로 상세 옵션 확인
- 모의투자 먼저 테스트: `kiwoom config domain mock`
- 연속조회(페이지네이션) 자동 처리
- 종목코드 6자리: `005930` (삼성전자)
- 금현물: `M04020000` (1kg), `M04020100` (미니 100g)

## License

kiwoom-cli **Source-Available License, Version 1.0** — see [LICENSE](LICENSE).

- **Individuals** (natural persons, on their own behalf): free to use, modify, and distribute for any purpose, including profit (e.g. trading your own account). Attribution only; no source-disclosure obligation.
- **Organizations, unmodified use for profit**: require a commercial license.
- **Organizations, modified use for profit**: either buy a commercial license (source may stay closed) or publish your entire codebase under this same license — and in both cases deliver the full modified source to the Licensor.

Versions released before v2.0 remain available under the MIT License. For commercial licensing, contact ge.jyn14@gmail.com — see [COMMERCIAL.md](COMMERCIAL.md).
