# kiwoom-cli

키움증권 REST API를 터미널에서 사용하기 위한 CLI 도구.

- 207개 API 전체 지원 (188 REST + 19 WebSocket 실시간)
- 종목 조회, 호가, 차트, 계좌, 주문, 순위, 업종, 테마, ETF, ELW, 금현물
- Rich 테이블 출력, 자동 페이지네이션, 실시간 스트리밍

## 설치

```bash
git clone https://github.com/gejyn14/kiwoom-cli.git
cd kiwoom-cli
pip install -e .
```

## 시작하기

```bash
# 1. 초기 설정 (키움 Open API에서 발급받은 appkey, secretkey 입력)
kiwoom config setup

# 2. 토큰 발급
kiwoom auth login

# 3. 사용
kiwoom stock info 005930
```

## 명령어 구조

```
kiwoom
├── config    설정 (setup / show / domain)
├── auth      인증 (login / logout / status)
├── stock     종목 조회
├── account   계좌 조회
├── order     주문
├── market    시장 정보
├── stream    실시간 스트리밍
└── api       Raw API 호출
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
kiwoom stock search --market 0        # 코스피 종목 리스트
kiwoom stock watchlist "005930|000660" # 관심종목
```

### 차트

```bash
kiwoom stock chart tick 005930 --range 1        # 틱
kiwoom stock chart minute 005930 --range 5      # 5분봉
kiwoom stock chart day 005930 --date 20260301   # 일봉
kiwoom stock chart week 005930 --date 20260301  # 주봉
kiwoom stock chart month 005930 --date 20260301 # 월봉
kiwoom stock chart year 005930 --date 20260301  # 년봉
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

| 명령 | 설명 |
|------|------|
| `info` | 종목 기본정보 |
| `price` | 현재가 한 줄 |
| `detail` | 종목정보 상세 |
| `orderbook` | 10단계 호가창 |
| `daily` | 일/주/월별 시세 |
| `timeprice` | 시분 시세 |
| `daily-price` | 일별주가 |
| `after-hours` | 시간외단일가 |
| `quote-info` | 시세표성정보 |
| `exec` | 체결정보 |
| `trader` | 거래원 |
| `today-exec` | 당일/전일 체결 |
| `today-volume` | 당일/전일 체결량 |
| `tick-strength` | 체결강도 시간별 |
| `daily-strength` | 체결강도 일별 |
| `foreign` | 외국인 매매동향 |
| `institution` | 기관 매매동향 |
| `short` | 공매도 추이 |
| `search` | 종목 리스트/검색 |
| `watchlist` | 관심종목 |
| `brokers` | 회원사 리스트 |
| `chart *` | 틱/분봉/일봉/주봉/월봉/년봉, 투자자별 차트 |
| `investor *` | 기관매매, 투자자별매매, 프로그램매매 등 10개 |
| `analysis *` | 거래상세, 거래량갱신, 매물대, PER, VI, 증권사 등 10개 |
| `lending *` | 대차거래 추이/상위/종목별/내역 |
| `credit *` | 신용매매동향, 신용융자 가능 |

</details>

---

## account - 계좌 조회

```bash
kiwoom account list                # 계좌번호
kiwoom account balance             # 잔고 + 보유종목 + 손익
kiwoom account deposit             # 예수금
kiwoom account asset               # 추정자산
kiwoom account today               # 당일현황
kiwoom account returns summary     # 수익률
kiwoom account pnl today 005930    # 당일 실현손익
kiwoom account orders pending      # 미체결 주문
kiwoom account orders executed     # 체결 내역
kiwoom account holdings eval       # 잔고내역
kiwoom account orderable amount 005930 --trade buy --price 70000
```

<details>
<summary>전체 account 하위 명령어</summary>

| 그룹 | 명령 | 설명 |
|------|------|------|
| - | `list` | 계좌번호 조회 |
| - | `balance` | 계좌 평가현황 |
| - | `deposit` | 예수금 상세 |
| - | `asset` | 추정자산 |
| - | `today` | 당일현황 |
| - | `margin-detail` | 증거금 세부내역 |
| `returns` | `summary` | 계좌 수익률 |
| `returns` | `daily-balance` | 일별 잔고수익률 |
| `returns` | `daily-detail` | 일별 수익률 상세 |
| `returns` | `daily-asset` | 일별 예탁자산 |
| `pnl` | `today` | 당일 실현손익 |
| `pnl` | `by-date` | 일자별 실현손익 |
| `pnl` | `by-period` | 기간별 실현손익 |
| `pnl` | `daily` | 일자별 실현손익 |
| `orders` | `pending` | 미체결 주문 |
| `orders` | `executed` | 체결 내역 |
| `orders` | `detail` | 주문체결 상세 |
| `orders` | `status` | 주문체결 현황 |
| `orders` | `split-detail` | 분할주문 상세 |
| `holdings` | `eval` | 계좌평가 잔고 |
| `holdings` | `settled` | 체결잔고 |
| `holdings` | `next-settle` | 익일결제예정 |
| `orderable` | `amount` | 주문가능 금액 |
| `orderable` | `margin-qty` | 증거금율별 수량 |
| `orderable` | `credit-qty` | 신용보증금율별 수량 |
| `history` | `transactions` | 위탁종합 거래내역 |
| `history` | `journal` | 당일 매매일지 |

</details>

---

## order - 주문

모든 주문에 `--confirm` 필수.

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
kiwoom order gold balance    # 잔고
kiwoom order gold pending    # 미체결

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

| 코드 | 명령 | 설명 |
|------|------|------|
| 00 | `order` | 주문체결 |
| 04 | `balance` | 잔고 |
| 0A | `price` | 주식기세 |
| 0B | `quote` | 주식체결 |
| 0C | `best-bid` | 우선호가 |
| 0D | `orderbook` | 호가잔량 |
| 0E | `after-hours` | 시간외호가 |
| 0F | `trader` | 당일거래원 |
| 0G | `etf-nav` | ETF NAV |
| 0H | `expected` | 예상체결 |
| 0I | `gold` | 국제금환산 |
| 0J | `sector-index` | 업종지수 |
| 0U | `sector-change` | 업종등락 |
| 0g | `stock-info` | 종목정보 |
| 0m | `elw-theory` | ELW 이론가 |
| 0s | `market-time` | 장시작시간 |
| 0u | `elw-indicator` | ELW 지표 |
| 0w | `program` | 프로그램매매 |
| 1h | `vi` | VI발동/해제 |

---

## Raw API

```bash
kiwoom api ka10001 '{"stk_cd":"005930"}'        # 테이블 출력
kiwoom api ka10001 '{"stk_cd":"005930"}' --raw   # JSON 원본
```

---

## 참고

| 항목 | 값 |
|------|------|
| 설정 파일 | `~/.kiwoom/config.toml` |
| 토큰 파일 | `~/.kiwoom/token` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` |
| WebSocket | `wss://api.kiwoom.com:10000` |

- `kiwoom <명령> --help`로 상세 옵션 확인
- 모의투자 먼저 테스트: `kiwoom config domain mock`
- 연속조회(페이지네이션) 자동 처리
- 종목코드 6자리: `005930` (삼성전자)
- 금현물: `M04020000` (1kg), `M04020100` (미니 100g)
