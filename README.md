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

## 왜 kiwoom-cli인가

- **236개 API 전체 지원** — REST 217개 + WebSocket 실시간 19종. 시세·차트·계좌·주문·순위·업종·테마·ETF·ELW·금현물·미국주식까지 키움 REST API를 빠짐없이 커버합니다.
- **프롬프트 제로** — 인증정보는 OS 키체인에 저장되고, 어떤 명령도 비밀번호를 묻지 않습니다. `gh`/`aws`/`docker`와 같은 모델. 크론잡, CI, AI 에이전트가 그대로 돌립니다.
- **AI 에이전트 퍼스트** — 구조화된 JSON 출력(`-f json`), 일관된 exit code(0/1/2/3), 주문 확인 게이트(`--confirm`). Claude Code, 자동매매 스크립트에 바로 연결됩니다.
- **미국주식 자동 라우팅** — `005930`은 국내로, `NVDA`는 미국으로. 거래소(NASDAQ/NYSE/AMEX)도 자동 판별. 국내+미국 통합 잔고를 원화 총계로 보여줍니다.
- **사람에게도 친절** — Rich 테이블, 상승=빨강/하락=파랑 색상, 실시간 TUI 대시보드, shell 자동완성.
- **246개 테스트 + CI** — Python 3.10–3.13 매트릭스, CodeQL 정적 분석.

> 📖 **전체 문서는 [Wiki](https://github.com/gejyn14/kiwoom-cli/wiki)에서** — 설치 가이드, 명령어 레퍼런스, 미국주식·AI 에이전트·멀티 프로필 가이드, 릴리스 노트.

## 최근 업데이트

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
```

- 어떤 명령도 비밀번호·생체인증을 요구하지 않으므로 에이전트 세션이 중간에 멈추지 않습니다.
- 페이지네이션(연속조회)은 자동 처리 — 에이전트가 커서를 관리할 필요가 없습니다.
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

주문은 실행 전 미리보기 + 대화형 확인이 기본입니다. 자동화 시에만 `--confirm`으로 스킵하세요.

```bash
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
# jq로 필터링
kiwoom -f json market rank volume | jq '.[].stk_nm'

# CSV를 파일로 저장
kiwoom -f csv stock daily 005930 > samsung_daily.csv
```

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
