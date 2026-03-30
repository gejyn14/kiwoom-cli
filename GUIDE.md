# kiwoom-cli 사용 가이드

키움증권 REST API를 터미널에서 사용하기 위한 CLI 도구.

## 설치

```bash
pip install -e .
```

## 초기 설정

키움 Open API에서 발급받은 appkey와 secretkey가 필요합니다.

```bash
# 초기 설정 (대화형 입력)
kiwoom config setup

# 설정 확인
kiwoom config show

# 도메인 변경 (prod: 실거래, mock: 모의투자)
kiwoom config domain mock
```

설정 파일: `~/.kiwoom/config.toml`

## 인증

API 호출 전 반드시 토큰을 발급받아야 합니다.

```bash
kiwoom auth login      # 토큰 발급
kiwoom auth status     # 토큰 상태 확인
kiwoom auth logout     # 토큰 폐기
```

토큰 저장 위치: `~/.kiwoom/token`

---

## 종목 조회 (stock)

### 기본 정보

```bash
kiwoom stock info 005930         # 삼성전자 기본정보 (PER, PBR, 시가총액 등)
kiwoom stock price 005930        # 현재가 한 줄 출력
kiwoom stock detail 005930       # 종목정보 상세
kiwoom stock orderbook 005930    # 10단계 호가창
kiwoom stock daily 005930        # 일별 시세
kiwoom stock daily 005930 --type week   # 주별 시세
kiwoom stock timeprice 005930    # 시분 시세
kiwoom stock daily-price 005930 --date 20260301  # 특정일 일별주가
kiwoom stock after-hours 005930  # 시간외단일가
kiwoom stock quote-info 005930   # 시세표성정보
```

### 체결/거래원

```bash
kiwoom stock exec 005930         # 체결정보
kiwoom stock trader 005930       # 거래원
kiwoom stock today-exec 005930   # 당일 체결 (--day today/prev, --type tick/min)
kiwoom stock today-volume 005930 # 당일/전일 체결량
kiwoom stock tick-strength 005930  # 체결강도 시간별
kiwoom stock daily-strength 005930 # 체결강도 일별
```

### 외국인/기관

```bash
kiwoom stock foreign 005930      # 외국인 매매동향
kiwoom stock institution 005930  # 기관 매매동향
```

### 공매도/대차거래

```bash
kiwoom stock short 005930 --from 20260101 --to 20260330  # 공매도 추이
kiwoom stock lending trend       # 대차거래 추이
kiwoom stock lending top10 --from 20260301  # 대차거래 상위10
kiwoom stock lending by-stock 005930       # 종목별 대차거래 추이
kiwoom stock lending detail --date 20260301 --market kospi  # 대차거래 내역
```

### 차트

```bash
kiwoom stock chart tick 005930 --scope 1        # 1틱 차트
kiwoom stock chart minute 005930 --scope 5      # 5분봉
kiwoom stock chart day 005930 --date 20260301   # 일봉
kiwoom stock chart week 005930 --date 20260301  # 주봉
kiwoom stock chart month 005930 --date 20260301 # 월봉
kiwoom stock chart year 005930 --date 20260301  # 년봉
```

### 투자자 매매

```bash
kiwoom stock investor daily-trade --from 20260301 --to 20260330  # 일별기관매매종목
kiwoom stock investor stock-institution 005930 --from 20260301 --to 20260330  # 종목별기관매매추이
kiwoom stock investor daily-by-investor --from 20260301 --to 20260330  # 투자자별일별매매
kiwoom stock investor by-stock 005930 --date 20260301  # 종목별투자자기관별
kiwoom stock investor intraday --market all     # 장중투자자별매매
kiwoom stock investor consecutive --period 5 --market kospi  # 기관/외국인 연속매매현황
kiwoom stock investor program-top               # 프로그램 순매수 상위50
```

### 분석

```bash
kiwoom stock analysis daily-detail 005930 --from 20260301  # 일별거래상세
kiwoom stock analysis volume-renewal             # 거래량갱신
kiwoom stock analysis price-cluster              # 매물대집중
kiwoom stock analysis per-rank --type low-per    # 고저PER
kiwoom stock analysis vi-trigger                 # VI 발동종목
kiwoom stock analysis broker-stock 001 005930 --from 20260301 --to 20260330  # 증권사별종목매매동향
```

### 검색/리스트

```bash
kiwoom stock search --market 0        # 코스피 종목 리스트
kiwoom stock search --market 10       # 코스닥 종목 리스트
kiwoom stock watchlist "005930|000660"  # 관심종목 조회
kiwoom stock brokers                   # 회원사(증권사) 리스트
```

### 신용매매

```bash
kiwoom stock credit trend 005930 --date 20260301 --type loan  # 신용매매동향
kiwoom stock credit available   # 신용융자 가능종목
kiwoom stock credit inquiry     # 신용융자 가능문의
```

---

## 계좌 (account)

### 기본 조회

```bash
kiwoom account list              # 계좌번호 조회
kiwoom account balance           # 계좌 평가현황 (보유종목, 손익 포함)
kiwoom account deposit           # 예수금 상세현황
kiwoom account asset             # 추정자산
kiwoom account today             # 당일현황
kiwoom account margin-detail     # 증거금 세부내역
```

### 수익률

```bash
kiwoom account returns summary              # 계좌 수익률
kiwoom account returns daily-balance        # 일별 잔고수익률
kiwoom account returns daily-detail --from 20260301 --to 20260330  # 일별 수익률 상세
kiwoom account returns daily-asset --from 20260301 --to 20260330   # 일별 예탁자산
```

### 실현손익

```bash
kiwoom account pnl today 005930             # 당일 실현손익
kiwoom account pnl by-date --from 20260301  # 일자별 실현손익 (일자 기준)
kiwoom account pnl by-period --from 20260301 --to 20260330  # 기간별 실현손익
kiwoom account pnl daily --from 20260301 --to 20260330      # 일자별 실현손익
```

### 주문/체결 조회

```bash
kiwoom account orders pending    # 미체결 주문
kiwoom account orders executed   # 체결 내역
kiwoom account orders detail     # 주문체결내역 상세
kiwoom account orders status     # 주문체결현황
kiwoom account orders split-detail 0000123  # 분할주문 상세
```

### 보유/잔고

```bash
kiwoom account holdings eval     # 계좌평가 잔고내역
kiwoom account holdings settled  # 체결잔고
kiwoom account holdings next-settle  # 익일결제예정
```

### 주문 가능

```bash
kiwoom account orderable amount 005930 --trade buy --price 70000  # 주문 가능 금액
kiwoom account orderable margin-qty 005930    # 증거금율별 주문가능수량
kiwoom account orderable credit-qty 005930    # 신용보증금율별 주문가능수량
```

### 거래내역

```bash
kiwoom account history transactions --from 20260301 --to 20260330  # 위탁종합거래내역
kiwoom account history journal     # 당일 매매일지
```

---

## 주문 (order)

모든 주문 명령에는 `--confirm` 플래그가 필수입니다.

### 주식 주문

```bash
# 시장가 매수
kiwoom order buy 005930 10 --type market --confirm

# 지정가 매수
kiwoom order buy 005930 10 --price 70000 --type limit --confirm

# 시장가 매도
kiwoom order sell 005930 10 --type market --confirm

# 정정 (원주문번호, 종목코드, 수량, 가격)
kiwoom order modify 0000139 005930 1 70000 --confirm

# 취소 (0=전량)
kiwoom order cancel 0000140 005930 --qty 0 --confirm
```

주문유형 옵션: `limit`, `market`, `conditional`, `after-hours`, `pre-market`, `single`, `best`, `first`, `ioc`, `market-ioc`, `best-ioc`, `fok`, `market-fok`, `best-fok`, `stop`, `mid`, `mid-ioc`, `mid-fok`

### 신용 주문

```bash
kiwoom order credit buy 005930 10 --type market --confirm
kiwoom order credit sell 005930 10 --type market --confirm
kiwoom order credit modify 0000139 005930 1 70000 --confirm
kiwoom order credit cancel 0000140 005930 --confirm
```

### 금현물 주문

```bash
kiwoom order gold buy M04020000 1 --type market --confirm
kiwoom order gold sell M04020000 1 --type market --confirm
kiwoom order gold modify 0000139 M04020000 1 500000 --confirm
kiwoom order gold cancel 0000140 M04020000 --confirm

# 금현물 계좌 조회
kiwoom order gold balance          # 잔고
kiwoom order gold deposit          # 예수금
kiwoom order gold pending          # 미체결
kiwoom order gold executions       # 주문체결조회
kiwoom order gold executions-all   # 주문체결전체조회
kiwoom order gold history          # 거래내역
```

### 조건검색

```bash
kiwoom order condition list                   # 조건검색식 목록
kiwoom order condition search 001 --confirm   # 조건검색 실행
kiwoom order condition realtime 001 --confirm # 실시간 조건검색
kiwoom order condition stop 001 --confirm     # 실시간 해제
```

---

## 시장 정보 (market)

### 순위

```bash
kiwoom market rank volume          # 거래량 상위
kiwoom market rank amount          # 거래대금 상위
kiwoom market rank change          # 등락률 상위
kiwoom market rank surge           # 가격 급등락
kiwoom market rank hot             # 실시간 조회 순위
kiwoom market rank limit           # 상하한가
kiwoom market rank new-highlow     # 신고저가
kiwoom market rank near-highlow    # 고저가 근접
kiwoom market rank volume-surge    # 거래량 급증
kiwoom market rank orderbook-top   # 호가잔량 상위
kiwoom market rank orderbook-surge # 호가잔량 급증
kiwoom market rank credit-ratio    # 신용비율 상위
kiwoom market rank expected-change # 예상체결 등락률
kiwoom market rank prev-volume     # 전일 거래량 상위
kiwoom market rank foreign-period  # 외인 기간별 매매 상위
kiwoom market rank foreign-consecutive  # 외인 연속순매매 상위
kiwoom market rank foreign-exhaust      # 외인 한도소진율 상위
kiwoom market rank foreign-broker       # 외국계 창구 매매 상위
kiwoom market rank foreign-inst         # 외국인/기관 매매 상위
kiwoom market rank investor-top         # 장중 투자자별 매매 상위
kiwoom market rank broker-by-stock 005930  # 종목별 증권사 순위
kiwoom market rank broker-top 001       # 증권사별 매매 상위
kiwoom market rank major-trader 005930  # 당일 주요 거래원
kiwoom market rank net-buyer 005930     # 순매수 거래원 순위
kiwoom market rank top-exit 005930      # 당일 상위 이탈원
kiwoom market rank same-net-trade --from 20260301  # 동일 순매매 순위
kiwoom market rank afterhours-change    # 시간외 등락율 순위
```

### 업종

```bash
kiwoom market sector current 001 --market kospi  # 업종 현재가 (001=종합)
kiwoom market sector stocks 001                  # 업종별 주가
kiwoom market sector index                       # 전업종 지수
kiwoom market sector daily 001                   # 업종 현재가 일별
kiwoom market sector codes                       # 업종코드 리스트
kiwoom market sector program 005930              # 업종 프로그램매매
kiwoom market sector investor                    # 업종별 투자자 순매수

# 업종 차트
kiwoom market sector chart day 001 --date 20260301
kiwoom market sector chart minute 001 --scope 5
```

### 테마

```bash
kiwoom market theme groups             # 테마 그룹 목록
kiwoom market theme stocks THEMA001    # 테마 구성종목
```

### ETF

```bash
kiwoom market etf info 069500          # ETF 종목정보
kiwoom market etf returns 069500       # ETF 수익률
kiwoom market etf all                  # ETF 전체 시세
kiwoom market etf daily 069500         # ETF 일별추이
kiwoom market etf time-trend 069500    # ETF 시간대별 추이
kiwoom market etf time-exec 069500     # ETF 시간대별 체결
kiwoom market etf daily-exec 069500    # ETF 일자별 체결
```

### ELW

```bash
kiwoom market elw detail 580001        # ELW 종목 상세정보
kiwoom market elw sensitivity 580001   # ELW 민감도 지표
kiwoom market elw surge                # ELW 가격 급등락
kiwoom market elw change-rank          # ELW 등락율 순위
kiwoom market elw search               # ELW 조건검색
kiwoom market elw disparity            # ELW 괴리율
kiwoom market elw broker-top           # 거래원별 ELW 순매매 상위
```

### 금현물

```bash
kiwoom market gold price               # 금현물 시세정보
kiwoom market gold orderbook           # 금현물 호가
kiwoom market gold executions          # 금현물 체결 추이
kiwoom market gold daily               # 금현물 일별 추이
kiwoom market gold expected            # 금현물 예상 체결
kiwoom market gold investors           # 금현물 투자자 현황
kiwoom market gold chart-day --date 20260301  # 금현물 일봉 차트
```

### 프로그램 매매

```bash
kiwoom market program time-trend --date 20260301   # 시간대별 추이
kiwoom market program daily-trend --date 20260301  # 일자별 추이
kiwoom market program cumulative --date 20260301   # 누적 추이
kiwoom market program arbitrage-balance --date 20260301  # 차익잔고 추이
kiwoom market program stock-time 005930 --date 20260301  # 종목 시간별
kiwoom market program stock-daily 005930           # 종목 일별
```

---

## 실시간 스트리밍 (stream)

WebSocket을 통해 실시간 시세를 수신합니다. Ctrl+C로 종료.

```bash
# 주식 시세
kiwoom stream quote 005930             # 주식체결 실시간
kiwoom stream price 005930             # 주식기세 (현재가, 등락율)
kiwoom stream orderbook 005930         # 호가잔량 실시간
kiwoom stream best-bid 005930          # 최우선호가
kiwoom stream expected 005930          # 예상체결
kiwoom stream after-hours 005930       # 시간외호가
kiwoom stream stock-info 005930        # 종목정보 변동

# 거래원/프로그램
kiwoom stream trader 005930            # 당일거래원
kiwoom stream program 005930           # 종목프로그램매매

# 계좌 (종목코드 불필요)
kiwoom stream order                    # 주문체결 실시간
kiwoom stream balance                  # 잔고 실시간

# 업종/지수
kiwoom stream sector-index 001         # 업종지수
kiwoom stream sector-change 001        # 업종등락

# ETF/ELW
kiwoom stream etf-nav 069500           # ETF NAV
kiwoom stream elw-theory 580001        # ELW 이론가
kiwoom stream elw-indicator 580001     # ELW 지표

# 기타
kiwoom stream gold M04020000           # 국제금환산가격
kiwoom stream market-time              # 장시작/마감 시간
kiwoom stream vi 005930                # VI 발동/해제

# 복수 종목 동시 수신
kiwoom stream quote 005930 000660 035420

# 체결+호가 동시 수신
kiwoom stream multi 005930

# 커스텀 타입 조합
kiwoom stream custom 0B,0D,0H 005930

# 타입 코드 목록 확인
kiwoom stream types

# JSON 원본 출력
kiwoom stream quote 005930 --raw
```

---

## Raw API

207개 전체 API를 직접 호출할 수 있습니다.

```bash
# JSON body를 직접 전달
kiwoom api ka10001 '{"stk_cd":"005930"}'

# JSON 원본 출력
kiwoom api ka10001 '{"stk_cd":"005930"}' --raw
```

---

## 공통 옵션

대부분의 명령에서 사용 가능한 필터 옵션:

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--market` | 시장구분 (kospi/kosdaq/all) | 전체 |
| `--exchange` | 거래소 (KRX/NXT/SOR) | KRX |
| `--from`, `--to` | 조회기간 (YYYYMMDD) | - |
| `--date` | 조회일자 (YYYYMMDD) | 오늘 |
| `--type` | 조회/주문 유형 | 명령별 상이 |

## 팁

- `kiwoom <명령> --help`로 각 명령의 상세 옵션을 확인할 수 있습니다.
- 모의투자 환경에서 먼저 테스트하세요: `kiwoom config domain mock`
- 연속조회(페이지네이션)는 자동으로 처리됩니다.
- 종목코드는 6자리 숫자입니다 (예: 005930 = 삼성전자).
- 금현물 종목코드: M04020000 (1kg), M04020100 (미니 100g).
