"""Shared lookup maps and option types for CLI value -> API value conversion."""

import click


class HumanChoice(click.Choice):
    """사람이 읽는 선택지 — 원시 API 코드도 하위호환으로 허용.

    mapping: human 이름 -> API 코드. convert()는 항상 API 코드를 반환하므로
    커맨드 본문은 값을 그대로 body에 넣으면 된다. --help/describe에는
    human 이름만 노출된다.
    """

    def __init__(self, mapping: dict[str, str]):
        super().__init__(list(mapping))
        self.mapping = mapping

    def convert(self, value, param, ctx):
        if value in self.mapping.values():
            return value
        return self.mapping[super().convert(value, param, ctx)]


MARKET_ALL = {"all": "000", "kospi": "001", "kosdaq": "101"}
MARKET_TWO = {"kospi": "001", "kosdaq": "101"}
MARKET_KOSPI_KOSDAQ = {"kospi": "0", "kosdaq": "1"}
MARKET_PROGRAM = {"kospi": "P00101", "kosdaq": "P10102"}
MARKET_SEARCH = {"kospi": "0", "kosdaq": "10", "k-otc": "30", "konex": "50", "etf": "8", "elw": "3"}
EXCHANGE_TWO = {"KRX": "1", "NXT": "2"}
EXCHANGE_ALL = {"KRX": "1", "NXT": "2", "all": "3"}
# stex_tp with "all"=0 (used by ka10075/ka10076/ka10085); distinct from EXCHANGE_ALL where "all"=3.
EXCHANGE_ALL_ZERO = {"all": "0", "KRX": "1", "NXT": "2"}

# ── HumanChoice 매핑 (Tier 3: 숫자코드 옵션의 human-readable 전환) ──
DELIST_QRY = {"all": "0", "exclude": "1"}                # 상장폐지조회구분
TRADE_SIDE = {"all": "0", "sell": "1", "buy": "2"}       # 매매/매도수구분
ALL_STOCK_QRY = {"all": "0", "stock": "1"}               # 전체종목/조회구분(0=전체,1=종목)
ORDER_DETAIL_QRY = {"order": "1", "reverse": "2", "unfilled": "3", "filled": "4"}
ASSET_TYPE = {"all": "0", "stock": "1", "bond": "2"}     # 주식채권구분
MARKET_STATUS_KOSPI = {"all": "0", "kospi": "1", "kosdaq": "2"}
FILLED_QRY = {"all": "0", "filled": "1"}                 # 조회구분(0=전체,1=체결)
HOLDINGS_EVAL_QRY = {"sum": "1", "each": "2"}            # 조회구분(1=합산,2=개별)
TRANSACTION_TYPE = {                                     # kt00015 구분
    "all": "0", "cash": "1", "securities": "2", "trade": "3",
    "buy": "4", "sell": "5", "deposit": "6", "withdraw": "7",
}
PRODUCT_TYPE = {"all": "0", "stock": "1"}                # 상품구분
ODD_LOT_QRY = {"same-day-buy": "1", "all": "2"}          # 단주구분
CASH_CREDIT = {"all": "0", "cash": "1", "credit": "2"}   # 현금신용구분
HOT_PERIOD = {"1m": "1", "10m": "2", "1h": "3", "today": "4", "30s": "5"}  # ka00198

# kt50000/kt50001(금현물 매수/매도) trde_tp — 국내주식 ORDER_TYPES(order.py)의 18종
# 중 딱 3개만 받는다(스펙: docs/미국 REST API 문서.xlsx kt50000/kt50001 시트,
# trde_tp 설명 "00:보통, 10:보통(IOC), 20:보통(FOK)"). 셋 다 지정가(보통) 계열
# 이라 금현물에는 시장가가 없다. ioc/fok 이름은 이 코드베이스가 국내주식 주문에
# 이미 쓰는 이름을 그대로 재사용한다 — "limit-ioc"/"limit-fok"로 바꾸면 지금도
# 정상 동작하는(trde_tp가 이미 올바른) 두 호출을 깨뜨리고 금현물만 다른 이름
# 체계를 쓰게 된다. kt50002/kt50003(정정/취소)은 trde_tp 필드 자체가 없어
# 여기 포함하지 않는다.
GOLD_ORDER_TYPES = {"limit": "00", "ioc": "10", "fok": "20"}

# trde_tp(매매구분)는 API마다 최소 4개의 서로 다른 코드북을 쓴다(0/1/2 순서와
# 극성이 전부 다름). "trde_tp니까 하나로 합치자"는 절대 금지 — 이름에 코드
# 집합을 새겨서 다른 codebook과 절대 재사용되지 않게 한다.
# 그룹③ (0:순매수, 1:매수, 2:매도) — ka10059/ka10060/ka10064/ka10066.
TRDE_TP_NET_BUY_BUY_SELL = {"net-buy": "0", "buy": "1", "sell": "2"}

# amt_qty_tp(금액수량구분)도 API마다 극성이 다르다(표준 1:금액,2:수량 vs
# ka10051/ka10131의 0:금액,1:수량) — 그런데 두 코드북의 키 집합(amount/
# quantity)이 완전히 같아서, trde_tp와 달리 이름만 봐서는 극성을 구분할
# 수 없다. 그래서 이름 자체에 코드 값을 새긴다: 이 상수는 1:금액,2:수량
# 전용이며, 0:금액,1:수량 짝은 별도로 `AMT_QTY_TP_0_1`이라는 이름을 예약해
# 둔다(ka10051 이관 시 이 이름으로 추가할 것 — 절대 이 상수를 재사용하지 말 것).
#
# *** 이 상수는 api_id 5개가 공유한다. 고치기 전에 5곳 전부를 확인할 것. ***
#   market.py:776   ka10065  amt_qty_tp   (Task 31c에서 추가)
#   market.py:822   ka90009  amt_qty_tp   (Task 31c에서 추가)
#   market.py:1666  ka90005  amt_qty_tp
#   market.py:1740  ka90010  amt_qty_tp
#   stock.py:1221   ka10066  amt_qty_tp
# 다섯 시트 모두 요청 코드북은 1:금액, 2:수량으로 동일하다. 다만 표기까지 같지는
# 않다 — ka90009 시트는 "1:금액(천만), 2:수량(천)"으로 적혀 있는데, 괄호 안은
# 응답 단위 주석이지 요청 코드가 아니다. required 여부도 갈린다(ka10065는
# Required=N, ka90009는 Required=Y). 값이 같으니 공유는 정당하지만, 나중에 한
# api_id의 스펙만 바뀌면 이 상수를 제자리에서 고치지 말고 분리할 것 —
# 제자리 수정은 나머지 넷을 조용히 함께 오염시킨다.
AMT_QTY_TP_1_2 = {"amount": "1", "quantity": "2"}

# AMT_QTY_TP_1_2와 키 집합(amount/quantity)은 같지만 극성이 다른 짝(0:금액,
# 1:수량) — ka10131(stock.py, 기관외국인연속매매현황)/ka10051(market.py,
# 업종별투자자순매수, Task 32에서 이관)이 공유한다(워크북으로 character-
# for-character 동일 확인: "금액:0, 수량:1"). 절대 AMT_QTY_TP_1_2와 합치지
# 말 것 — 키 집합이 같아 합쳐도 조용히 통과하고, 극성만 뒤집힌 값이 나간다.
#
# *** 이 상수는 api_id 2개가 공유한다. 한쪽 스펙만 바뀌면 이 상수를 제자리에서
# 고치지 말고 분리할 것 — 제자리 수정은 나머지 하나를 조용히 함께 오염시킨다. ***
AMT_QTY_TP_0_1 = {"amount": "0", "quantity": "1"}

# ka10131(stock.py) 전용 — dt(기간) 필드. 값이 순수 일수 시퀀스가 아니라
# 1=최근일(문자 그대로 "1일"이 아님), 0=시작일자/종료일자로 조회(기간모드
# 전환)까지 섞인 코드북. 다른 dt 클러스터(PERIOD_TODAY_PREV_5_60,
# ka10038의 off-by-1 코드북 등)와 값 집합이 전혀 달라 절대 합치지 말 것.
PERIOD_RECENT_OR_RANGE = {
    "recent": "1", "3d": "3", "5d": "5", "10d": "10", "20d": "20",
    "120d": "120", "range": "0",
}

# ka10131(stock.py) 전용 — netslmt_tp(순매수구분)는 스펙상 "2:순매수(고정값)"
# 하나뿐이라 다른 선택지가 없다. 다른 endpoint의 순매수/순매도 계열
# trde_tp 코드북들과는 완전히 별개 필드이니 혼용 금지.
NETSLMT_TP_NET_BUY_ONLY = {"net-buy": "2"}

# ka10131(stock.py) 전용 — stk_inds_tp(종목업종구분).
STK_INDS_TP = {"stock": "0", "sector": "1"}

# ka10063(stock.py, 장중투자자별매매) 전용 — invsr(투자자별). 기존 기본값
# "1000"은 ka10058 invsr_tp 코드북을 복붙한 것으로, ka10063 스펙(Length=1)에는
# 존재하지 않는 값이었다. 이름은 kwcli `--investor`를 그대로 따른다.
INTRADAY_INVESTOR = {
    "foreign": "6", "institution": "7", "investment-trust": "1", "insurance": "0",
    "bank": "2", "pension": "3", "state": "4", "other-corporate": "5",
}

# amt_qty_tp의 세 번째 코드북. 여기서 "1"은 금액과 수량을 동시에 주는 단일
# 허용값이고, AMT_QTY_TP_1_2의 "1"(=금액, 수량은 2)과 의미가 다르다.
# 키 집합이 달라 재사용하면 즉시 KeyError가 나지만, 그래도 절대 합치지 말 것.
# 짝: AMT_QTY_TP_1_2(13곳), AMT_QTY_TP_0_1(ka10051/ka10131). 이 상수는 1곳: ka10063.
AMT_QTY_TP_COMBINED = {"combined": "1"}

# ka10063(stock.py) 전용, 2곳 — frgn_all(외국계전체)/smtm_netprps_tp(동시순매수구분)
# 공용. 둘 다 스펙상 "yes"->"1"(체크), "no"->"0"(미체크)인 동일 코드북.
# stock.py에는 이 밖에도 의미가 다른 click.Choice(["0","1"]) 옵션이 여럿
# 있다(indc_tp, tdy_pred/tic_min, cur_prc_entry, updown_incls, qry_dt_tp/pot_tp
# 등) — 이름에 극성(1=yes/0=no)과 값을 박아 넣은 것은 그것들과 절대 합치지
# 말라는 뜻이다. 절대 합치지 말 것.
CHECK_YES_1_NO_0 = {"yes": "1", "no": "0"}

# kt20016 mrkt_deal_tp(시장거래구분). 코스피=1, 코스닥=0 으로
# MARKET_KOSPI_KOSDAQ(kospi:0, kosdaq:1)과 극성이 정확히 **반대**다.
# 전체가 "%"인 것도 이 엔드포인트 고유. 1곳: kt20016. 절대 합치지 말 것.
CREDIT_MARKET = {"all": "%", "kospi": "1", "kosdaq": "0"}

# kt20016 crd_stk_grde_tp(신용종목등급구분). kwcli --credit-grade 값과 동일.
CREDIT_GRADE = {"all": "%", "a": "A", "b": "B", "c": "C", "d": "D", "e": "E"}

# ka90005/ka90010(프로그램매매추이요청 시간대별/일자별) 전용 — mrkt_tp가
# 거래소(stex_tp)와 **연동된** 10자리 코드(스펙: docs/미국 REST API 문서.xlsx
# 두 시트의 mrkt_tp Description). 같은 필드명 mrkt_tp를 쓰고 같은 P-코드 계열을
# 쓰지만 구조가 다른 형제가 있다: MARKET_PROGRAM(ka90003/ka90004)은 stex_tp와
# 무관한 평면 매핑 {kospi:P00101, kosdaq:P10102}이다. 절대 합치지 말 것 —
# 이쪽은 2단 dict(시장 -> 거래소구분값("1"/"2"/"3") -> P코드)다.
#
# 코스닥 + 거래소구분값 3(통합): ka90005 시트는 "P101_AL02", ka90010 시트는
# "P001_AL02"로 적어 두 API 스펙이 서로 모순된다. 이 모순은 워크북뿐 아니라
# 키움 공식 GitHub 저장소의 kiwoom_docs/시세.md, Postman 컬렉션, examples
# 스크립트, kiwoom_api_spec.json에도 동일하게 나타나 — 즉 한쪽 오타가 모든
# 소스에 그대로 전파되어 있어 키움 자체 소스로는 어느 쪽이 맞는지 판정할 수
# 없다. 사용자 결정(2026-07-19): 코스닥 코드가 전부 "P101_" 접두사를 쓰고
# "P001_"은 코스피 접두사이므로, "P001_AL02"(코스피 접두사에 코스닥 접미사가
# 섞인 형태)를 오타로 보고 두 API 모두 "P101_AL02"로 통일한다. 이것은 판단이지
# 검증된 사실이 아니다 — 키움이 문서를 정정하거나 실제 호출로 재확인되기
# 전까지는 추정이다.
PROGRAM_MARKET_BY_EXCHANGE = {
    "kospi": {"1": "P00101", "2": "P001_NX01", "3": "P001_AL01"},
    "kosdaq": {"1": "P10102", "2": "P101_NX02", "3": "P101_AL02"},
}

# ka90005/ka90010 전용 — min_tic_tp(분틱구분). 두 API 스펙 시트 모두
# "0:틱, 1:분"으로 동일하다(docs/미국 REST API 문서.xlsx, 두 시트 확인).
MIN_TIC_TP = {"tick": "0", "minute": "1"}

# ── ka10030(rank volume)/ka10032(rank amount)/ka10038(broker-by-stock)
# /ka30002(elw broker-top) 파라미터 교정 ─────────────────────────────────

# ka10030(rank volume) mang_stk_incls — 이름은 "관리종목포함"이지만 실제로는
# 15종 종목필터다(스펙: docs/미국 REST API 문서.xlsx ka10030 시트). 형제
# ka10032의 mang_stk_incls는 진짜 boolean이고 극성도 반대다({0:미포함,
# 1:포함}). 같은 필드명, 다른 코드북 — 절대 합치지 말 것.
# 1곳: ka10030(rank volume, 옵션명 --stock-condition). 짝: MANAGED_STOCK_INCLUDE(ka10032).
#
# 이름(STOCK_CONDITION=종목조건)에 낚이지 말 것: 종목조건의 진짜 필드명은
# stk_cnd이고, 이 상수가 담는 값은 stk_cnd가 아니라 mang_stk_incls(관리종목포함)다.
# stk_cnd는 market.py의 ~10개 커맨드(rank_new_highlow, rank_limit,
# rank_near_highlow, rank_surge, rank_orderbook_top, rank_orderbook_surge,
# rank_balance_rate_surge, rank_volume_surge, rank_change, rank_expected_change,
# rank_credit_ratio, rank_afterhours_change 등)에서 raw 텍스트로 그대로
# 전달되는 완전히 다른 필드이며, 이 상수의 코드북과 무관하다. 나중에 stk_cnd를
# HumanChoice로 바꾸는 작업을 하게 되면 이 STOCK_CONDITION을 재사용하지 말고
# 별도 상수를 새로 정의할 것 — 여기 값(mang_stk_incls 코드)을 stk_cnd에 넣으면
# 조용히 잘못된 조회 조건이 전송된다.
STOCK_CONDITION = {
    "include-managed": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-liquidation": "11", "exclude-managed-preferred": "4",
    "exclude-margin-100": "5", "only-margin-100": "6", "only-margin-60": "13",
    "only-margin-50": "12", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9", "exclude-etf": "14", "exclude-spac": "15",
    "exclude-etf-etn": "16",
}

# ka10032(rank amount) mang_stk_incls — 진짜 boolean. ka10030과 극성이 반대이므로
# STOCK_CONDITION과 절대 합치지 말 것. 1곳: ka10032(rank amount, 옵션명 --include-managed 유지).
MANAGED_STOCK_INCLUDE = {"no": "0", "yes": "1"}

# ka10030(rank volume) 전용 — sort_tp(정렬구분). market.py 안에서 sort_tp/sort는
# 20곳 넘게 재사용되며 endpoint마다 값이 전부 다르다(예: rank_limit의
# sort_tp는 1=종목코드순, rank_foreign_broker의 sort_tp는 1=금액). 이 상수는
# ka10030 전용 값(1:거래량,2:거래회전율,3:거래대금)이며 다른 sort_tp/sort
# 옵션(이번 태스크 범위 밖, 원시 텍스트 그대로 유지)과 절대 합치지 말 것.
VOLUME_RANK_SORT = {"volume": "1", "turnover": "2", "amount": "3"}

# ka10030(rank volume) 전용 — crd_tp(신용구분). kt20016의 CREDIT_GRADE(all/a..e)
# 와 이름은 비슷해 보이나 값 집합이 다르다(여기는 all-financing/short 포함,
# e 없음). 다른 커맨드의 crd_cnd(신용조건, market.py 여러 곳, 미확인/미변환)
# 와도 필드명이 달라 구분되지만 혹시라도 재사용하지 말 것. 1곳: ka10030.
VOLUME_RANK_CREDIT_TYPE = {
    "all": "0", "all-financing": "9", "a": "1", "b": "2", "c": "3", "d": "4", "short": "8",
}

# ka10030(rank volume) 전용 — trde_qty_tp(거래량구분, 9개 값: 200/300 포함).
# 스펙 원문은 500 코드의 설명을 "500만주이상"(5,000,000)으로 적어 1000 코드
# "백만주이상"(1,000,000)보다 커지는 산술 역전이 있다 — 다른 항목들은 모두
# "코드값*1000주"로 일관되므로(5→5천, 10→1만, ... 300→30만) 이 한 항목만
# 스펙 문구가 어긋난 것이다. 키움 공식 kwcli의 maps/arguments.csv가
# rankings today-volume(=ka10030) --volume-condition을 9개 값 전부 우리와
# 동일하게(500k=500 포함) 매핑하고 있어 확인된 사실이다. market.py의 다른
# trde_qty_tp/--vol-type 옵션(ka10033/ka10039/ka30002 등)은 값 집합이 전부
# 달라 절대 합치지 말 것. 1곳: ka10030.
VOLUME_RANK_QTY_TYPE = {
    "all": "0", "5k": "5", "10k": "10", "50k": "50", "100k": "100",
    "200k": "200", "300k": "300", "500k": "500", "1000k": "1000",
}

# ka10030(rank volume) 전용 — pric_tp(가격구분, 11개 값). market.py의 다른
# pric_tp/pric_cnd 옵션(ka10019/ka10023/ka10027/ka10029 등)은 값 집합이
# 미확인이거나 달라 절대 합치지 말 것. 1곳: ka10030.
VOLUME_RANK_PRICE_TYPE = {
    "all": "0", "under-1k": "1", "over-1k": "2", "1k-2k": "3", "2k-5k": "4",
    "over-5k": "5", "5k-10k": "6", "under-10k": "10", "over-10k": "7",
    "over-50k": "8", "over-100k": "9",
}

# ka10030(rank volume) 전용 — trde_prica_tp(거래대금구분, 13개 값). 4 코드가
# "5천만원이상"(50m)인 것은 1/3/10/30/50 계열의 "1-3-5×10^n" 패턴과 일치해
# 오타가 아니다(다른 rank_change의 trde_prica_cnd와는 필드명이 달라 구분됨).
# 1곳: ka10030.
VOLUME_RANK_AMOUNT_TYPE = {
    "all": "0", "10m": "1", "30m": "3", "50m": "4", "100m": "10",
    "300m": "30", "500m": "50", "1b": "100", "3b": "300", "5b": "500",
    "10b": "1000", "30b": "3000", "50b": "5000",
}

# ka10030(rank volume) 전용 — mrkt_open_tp(장운영구분). 1곳: ka10030.
VOLUME_RANK_SESSION = {"all": "0", "regular": "1", "pre-open": "2", "after-hours": "3"}

# ka10038(broker-by-stock) 전용 — qry_tp(조회구분). 여기서는 1=순매도다.
# trde_tp/qry_tp 계열은 API마다 극성이 뒤집히는 것으로 이미 등록된 해저드
# (TRDE_TP_NET_BUY_BUY_SELL 등 참고) — ka30002의 ELW_BROKER_SIDE(1=순매수)와
# 정반대이므로 절대 합치지 말 것. 1곳: ka10038(옵션명 --type 유지).
BROKER_BY_STOCK_SIDE = {"net-sell": "1", "net-buy": "2"}

# ka10038(broker-by-stock) 전용 — dt(기간). off-by-one 코드북(5일=4, 10일=9,
# 120일=119처럼 하루씩 어긋난다). 5일=5인 일반 기간 코드북(ELW_BROKER_PERIOD 등)
# 과 절대 합치지 말 것. 1곳: ka10038. --from/--to와 동시 지정 불가(빈 값이면
# body에서 dt 키 자체를 제외해야 한다 — 스펙: "시작일자와 종료일자로 조회를
# 원하는 경우 기간(dt)값은 빈값으로 설정").
PERIOD_DAYS_OFF_BY_ONE = {
    "previous": "1", "5d": "4", "10d": "9", "20d": "19",
    "40d": "39", "60d": "59", "120d": "119",
}

# ka30002(elw broker-top) 전용 — trde_qty_tp(거래량구분, 7개 값: 0/5/10/50/
# 100/500/1000). ka10030의 VOLUME_RANK_QTY_TYPE(9개 값, 200/300 포함)과
# 값 집합이 달라 절대 합치지 말 것. 1곳: ka30002.
ELW_BROKER_QTY_TYPE = {
    "all": "0", "5k": "5", "10k": "10", "50k": "50",
    "100k": "100", "500k": "500", "1000k": "1000",
}

# ka30002(elw broker-top) 전용 — trde_tp(매매구분). 여기서는 1=순매수다.
# ka10038의 BROKER_BY_STOCK_SIDE(1=순매도)와 정반대 극성이고, 기존
# TRDE_TP_NET_BUY_BUY_SELL(0:순매수,1:매수,2:매도)과도 값 집합이 다르다 —
# 재사용 금지, 절대 합치지 말 것. 1곳: ka30002(옵션명 --type 유지).
ELW_BROKER_SIDE = {"net-buy": "1", "net-sell": "2"}

# ka30002(elw broker-top) 전용 — dt(기간). 여기서는 5일=5(off-by-one 아님).
# ka10038의 PERIOD_DAYS_OFF_BY_ONE(5일=4)과 값 집합이 달라 절대 합치지 말 것.
# 1곳: ka30002.
ELW_BROKER_PERIOD = {"previous": "1", "5d": "5", "10d": "10", "40d": "40", "60d": "60"}

# ── ka10043(trader-analysis, 거래원매물대분석)
# qry_dt_tp/pot_tp/sort_base/dt 파라미터 교정 ─────────────────────────────

# qry_dt_tp(조회기간구분). Task 31c에서 market.py의 ka10042(rank net-buyer)도
# 워크북으로 character-for-character 동일함을 확인해 이 상수를 공유하도록
# 전환했다 — **이 상수는 지금 2개 api_id(ka10043 stock.py, ka10042
# market.py)가 공유한다.** 나중에 한쪽 스펙만 바뀌면 이 상수를 제자리에서
# 고치지 말고 분리할 것 — 제자리 수정은 나머지 하나를 조용히 함께 오염시킨다.
TRADER_ANALYSIS_DATE_MODE = {"period": "0", "start-end": "1"}

# pot_tp(시점구분, 0:당일,1:전일). Task 31c에서 market.py의 ka10042도 워크북
# 확인 후 공유하도록 전환했다 — **이 상수는 지금 2개 api_id(ka10043, ka10042)가
# 공유한다.** 분리 원칙은 TRADER_ANALYSIS_DATE_MODE와 동일.
#
# **cross-field 해저드**: 값 집합(today:0, previous:1)이 PERIOD_TODAY_PREV_5_60
# (ka10034/36/37의 dt)과 BROKER_TOP_PERIOD(ka10039의 dt) 양쪽 모두의 진짜
# 부분집합이다(superset-closure 스크립트로 확인, FOREIGN_CONSECUTIVE_BASE_DATE와
# 동일한 해저드 패턴) — 필드 자체가 다른데(pot_tp vs dt) 흔한 today/previous
# 키 이름 때문에 "today/previous 상수 통합" 리팩터가 이 상수를 그 두 상수 중
# 하나로 잘못 흡수하기 쉽다. 절대 합치지 말 것.
TRADER_ANALYSIS_POSITION = {"today": "0", "previous": "1"}

# sort_base(정렬기준, 1:종가순,2:날짜순). Task 31c에서 market.py의 ka10042도
# 워크북 확인 후 공유하도록 전환했다 — **이 상수는 지금 2개 api_id(ka10043,
# ka10042)가 공유한다.** 분리 원칙은 TRADER_ANALYSIS_DATE_MODE와 동일.
TRADER_ANALYSIS_SORT = {"close": "1", "date": "2"}

# ka10043 전용 — dt(기간). 이 API는 5일=5로 코드가 일수와 그대로 일치한다
# (off-by-one 아님). 이름에 값 범위(5_120)를 새긴 이유: ka10038의
# PERIOD_DAYS_OFF_BY_ONE(5일=4, 10일=9, ..., 120일=119로 하루씩 어긋남)과
# 키 집합(5d/10d/20d/40d/60d/120d)까지 비슷해서 이름만으로는 두 코드북이
# 구분되지 않기 때문이다 — 절대 PERIOD_DAYS_OFF_BY_ONE과 합치지 말 것.
# ka30002의 ELW_BROKER_PERIOD(5일=5로 값은 같으나 previous 키가 섞여 있고
# 20d/120d가 없어 키 집합이 다름)와도 값 집합이 달라 재사용 금지.
# 1곳: ka10043.
TRADER_ANALYSIS_PERIOD_5_120 = {
    "5d": "5", "10d": "10", "20d": "20", "40d": "40", "60d": "60", "120d": "120",
}

# ka30002(elw broker-top) 전용 — trde_end_elwskip(거래종료ELW제외).
# 0=포함,1=제외. elw_surge(ka30001)/elw_disparity(ka30004)/elw_change_rank
# (ka30009)/elw_balance_rank(ka30010)도 동일한 trde_end_elwskip/trde_end_skip
# 필드를 같은 값(0=포함,1=제외)으로 쓰지만 이번 태스크 범위 밖이라 그대로
# 원시 텍스트로 남아 있다 — 이 상수를 그쪽에 재사용해도 값은 맞겠으나 아직
# 검증/적용하지 않았으니 별도 작업으로 남긴다. 1곳: ka30002.
ELW_BROKER_END_SKIP = {"include": "0", "exclude": "1"}

# ── ka10016~ka10023(market rank 신고저가~거래량급증) HumanChoice 전환
# (Task 31a) ──────────────────────────────────────────────────────────
#
# trde_qty_tp(거래량구분)에 대한 중요 발견: 이 8개 커맨드 전부에서 현재
# --vol-type의 기본값이 raw "0"인데, 8개 API의 trde_qty_tp 스펙 값은 전부
# "0"을 포함하지 않는다(ka10016/17/18/19는 5자리 zero-pad "00000"이 전체조회,
# ka10020은 4자리 "0000", ka10021/22/23은 "전체" 개념 자체가 없이 "5"~"1000"
# 최솟값부터 시작). 즉 현재 기본 호출은 스펙에 없는 코드를 보내고 있는
# 사전 존재 결함으로 보인다(docs/미국 REST API 문서.xlsx 8개 시트 + kwcli
# arguments.csv로 이중 확인). HumanChoice로 감싸면 이 "0"이 매핑에 없어
# 기본 호출 자체가 BadParameter로 깨진다(실측 확인함) — 값을 스펙에 맞는
# 코드로 바꾸면 전송값이 바뀌므로 규칙 1(표기만 바꾼다) 위반이다. 그래서
# trde_qty_tp는 8개 커맨드 전부에서 이번 태스크 범위에서 제외하고 raw
# 텍스트로 남긴다 — 값 자체를 고치는 것은 별도 버그 수정 작업(Tranche B류)
# 소관이다. 상세는 task-31a-report.md 참고.

# ka10016(신고저가) 전용 — ntl_tp(신고저구분). 1곳: ka10016.
NEW_HIGH_LOW_KIND = {"new-high": "1", "new-low": "2"}

# ka10016(신고저가) 전용 — high_low_close_tp(고저종구분). 1곳: ka10016.
NEW_HIGH_LOW_BASIS = {"high-low": "1", "close": "2"}

# ka10016(신고저가) 전용 — stk_cnd(종목조건, 7개 값: all/exclude-managed/
# exclude-preferred/exclude-margin-100/only-margin-100/only-margin-40/
# only-margin-30). ka10018/ka10019의 stk_cnd와 값 집합이 동일해 보이나(스펙
# 상으로도 동일) 이번 태스크는 "값 집합이 같아 보인다고 합치지 마라"는 규칙을
# 그대로 따라 API별로 분리해 둔다 — 나중에 합치는 것은 별도 판단. 짝:
# NEAR_HIGHLOW_STK_CND(ka10018), SURGE_STK_CND(ka10019). 절대 자동으로
# 합치지 말고, 합치려면 재검증부터 할 것.
NEW_HIGH_LOW_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-margin-100": "5", "only-margin-100": "6",
    "only-margin-40": "7", "only-margin-30": "8",
}

# ka10016(신고저가) 전용 — crd_cnd(신용조건, 7개 값). ka10017/18/19/20의
# crd_cnd와 값 집합이 동일해 보이나 위와 동일한 이유로 API별로 분리.
# 짝: LIMIT_MOVE_CREDIT_CND(ka10017), NEAR_HIGHLOW_CREDIT_CND(ka10018),
# SURGE_CREDIT_CND(ka10019), ORDERBOOK_TOP_CREDIT_CND(ka10020).
NEW_HIGH_LOW_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10016(신고저가) 전용 — updown_incls(상하한포함, 0:미포함,1:포함).
# ka10019의 updown_incls와 값 집합이 동일해 보이나 API별로 분리.
# 짝: SURGE_INCLUDE_LIMIT(ka10019).
NEW_HIGH_LOW_INCLUDE_LIMIT = {"yes": "1", "no": "0"}

# ka10017(상하한가) 전용 — updown_tp(상하한구분, 7개 값). 1곳: ka10017.
LIMIT_MOVE_DIRECTION = {
    "upper": "1", "rise": "2", "flat": "3", "lower": "4",
    "fall": "5", "prev-upper": "6", "prev-lower": "7",
}

# ka10017(상하한가) 전용 — sort_tp(정렬구분, 3개 값). 1곳: ka10017.
LIMIT_MOVE_SORT = {"code": "1", "count": "2", "change-rate": "3"}

# ka10017(상하한가) 전용 — stk_cnd(종목조건, 10개 값: NEW_HIGH_LOW_STK_CND의
# 7개 값에 exclude-managed-preferred(4)/only-margin-20(9)/
# exclude-managed-preferred-alert(10)가 추가된 상위집합). 1곳: ka10017.
LIMIT_MOVE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-managed-preferred": "4", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9", "exclude-managed-preferred-alert": "10",
}

# ka10017(상하한가) 전용 — crd_cnd(신용조건, 7개 값). NEW_HIGH_LOW_CREDIT_CND
# 참고(짝 목록).
LIMIT_MOVE_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10017(상하한가) 전용 — trde_gold_tp(매매금구분, 7개 값). ka10019의
# pric_cnd와 값 집합·라벨이 동일해 보이나 필드명 자체가 다르다
# (trde_gold_tp vs pric_cnd) — 절대 합치지 말 것. 짝: SURGE_PRICE_CND(ka10019).
LIMIT_MOVE_PRICE_CND = {
    "all": "0", "under-1k": "1", "1k-2k": "2", "2k-3k": "3",
    "5k-10k": "4", "over-10k": "5", "over-1k": "8",
}

# ka10018(고저가근접) 전용 — high_low_tp(고저구분). 1곳: ka10018.
NEAR_HIGHLOW_KIND = {"high": "1", "low": "2"}

# ka10018(고저가근접) 전용 — stk_cnd(종목조건, 7개 값). NEW_HIGH_LOW_STK_CND
# 참고(짝 목록). 1곳: ka10018.
NEAR_HIGHLOW_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-margin-100": "5", "only-margin-100": "6",
    "only-margin-40": "7", "only-margin-30": "8",
}

# ka10018(고저가근접) 전용 — crd_cnd(신용조건, 7개 값). NEW_HIGH_LOW_CREDIT_CND
# 참고(짝 목록). 1곳: ka10018.
NEAR_HIGHLOW_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10019(가격급등락) 전용 — flu_tp(등락구분). 1곳: ka10019.
SURGE_DIRECTION = {"rise": "1", "fall": "2"}

# ka10019(가격급등락) 전용 — tm_tp(시간구분, 1:분전,2:일전). ka10023의
# tm_tp(1:분,2:전일)와 필드명은 같지만 라벨 의미가 달라(분전/일전 vs
# 분/전일) 별도 상수로 유지. 짝: VOLUME_SURGE_TIME_UNIT(ka10023).
SURGE_TIME_UNIT = {"minute": "1", "day": "2"}

# ka10019(가격급등락) 전용 — stk_cnd(종목조건, 7개 값). NEW_HIGH_LOW_STK_CND
# 참고(짝 목록). 1곳: ka10019.
SURGE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-margin-100": "5", "only-margin-100": "6",
    "only-margin-40": "7", "only-margin-30": "8",
}

# ka10019(가격급등락) 전용 — crd_cnd(신용조건, 7개 값). NEW_HIGH_LOW_CREDIT_CND
# 참고(짝 목록). 1곳: ka10019.
SURGE_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10019(가격급등락) 전용 — pric_cnd(가격조건, 7개 값). LIMIT_MOVE_PRICE_CND
# 참고(짝 — 값·라벨은 같으나 필드명이 다름, 절대 합치지 말 것). 1곳: ka10019.
SURGE_PRICE_CND = {
    "all": "0", "under-1k": "1", "1k-2k": "2", "2k-3k": "3",
    "5k-10k": "4", "over-10k": "5", "over-1k": "8",
}

# ka10019(가격급등락) 전용 — updown_incls(상하한포함). NEW_HIGH_LOW_INCLUDE_LIMIT
# 참고(짝 목록). 1곳: ka10019.
SURGE_INCLUDE_LIMIT = {"yes": "1", "no": "0"}

# ka10020(호가잔량상위) 전용 — sort_tp(정렬구분, 4개 값). 1곳: ka10020.
ORDERBOOK_TOP_SORT = {
    "net-buy-balance": "1", "net-sell-balance": "2", "buy-ratio": "3", "sell-ratio": "4",
}

# ka10020(호가잔량상위) 전용 — stk_cnd(종목조건, 7개 값: NEW_HIGH_LOW_STK_CND와
# 달리 "3"(exclude-preferred)이 없고 "9"(only-margin-20)이 있다). ka10021/22의
# stk_cnd와 값 집합이 동일해 보이나 API별로 분리. 짝:
# ORDERBOOK_SURGE_STK_CND(ka10021), BALANCE_RATE_STK_CND(ka10022).
ORDERBOOK_TOP_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9",
}

# ka10020(호가잔량상위) 전용 — crd_cnd(신용조건, 7개 값). NEW_HIGH_LOW_CREDIT_CND
# 참고(짝 목록). 1곳: ka10020.
ORDERBOOK_TOP_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10021(호가잔량급증) 전용 — trde_tp(매매구분, 1:매수잔량,2:매도잔량).
# 매수/매도 "잔량" 자체를 뜻하며 순매수/순매도 개념이 아니다 — 기존
# TRDE_TP_* 그룹들과 절대 합치지 말 것(이미 _constants.py 상단 주석에 그룹④로
# 예약돼 있었으나 실제 상수는 아직 없었음, 이번에 추가). 1곳: ka10021.
ORDERBOOK_SURGE_SIDE = {"buy-balance": "1", "sell-balance": "2"}

# ka10021(호가잔량급증) 전용 — sort_tp(정렬구분, 1:급증량,2:급증률). 1곳: ka10021.
ORDERBOOK_SURGE_SORT = {"spike-quantity": "1", "spike-rate": "2"}

# ka10021(호가잔량급증) 전용 — stk_cnd(종목조건, 7개 값). ORDERBOOK_TOP_STK_CND
# 참고(짝 목록). 1곳: ka10021.
ORDERBOOK_SURGE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9",
}

# ka10022(잔량율급증) 전용 — rt_tp(비율구분, 1:매수/매도비율,2:매도/매수비율).
# 1곳: ka10022.
BALANCE_RATE_TYPE = {"buy-to-sell": "1", "sell-to-buy": "2"}

# ka10022(잔량율급증) 전용 — stk_cnd(종목조건, 7개 값). ORDERBOOK_TOP_STK_CND
# 참고(짝 목록). 1곳: ka10022.
BALANCE_RATE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9",
}

# ka10023(거래량급증) 전용 — sort_tp(정렬구분, 1:급증량,2:급증률,3:급감량,
# 4:급감률). 1곳: ka10023.
VOLUME_SURGE_SORT = {
    "spike-quantity": "1", "spike-rate": "2", "drop-quantity": "3", "drop-rate": "4",
}

# ka10023(거래량급증) 전용 — tm_tp(시간구분, 1:분,2:전일). SURGE_TIME_UNIT
# 참고(짝 — 필드명은 같으나 라벨 의미가 달라 절대 합치지 말 것). 1곳: ka10023.
VOLUME_SURGE_TIME_UNIT = {"minute": "1", "previous-day": "2"}

# ka10023(거래량급증) 전용 — stk_cnd(종목조건, 17개 값 — 이 8개 커맨드 중
# 가장 큰 사다리, ETF/ETN/스팩 제외 옵션까지 포함). 1곳: ka10023.
VOLUME_SURGE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-liquidation": "11", "exclude-managed-preferred": "4",
    "exclude-margin-100": "5", "only-margin-100": "6", "only-margin-60": "13",
    "only-margin-50": "12", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9", "exclude-etn": "17", "exclude-etf": "14",
    "exclude-etf-etn": "18", "exclude-spac": "15", "exclude-etf-etn-spac": "20",
}

# ka10023(거래량급증) 전용 — pric_tp(가격구분, 6개 값). market.py의 다른
# pric_tp/pric_cnd 옵션(ka10019/ka10027/ka10029 등, 미확인 또는 다른 값 집합)
# 과 절대 합치지 말 것. 1곳: ka10023.
VOLUME_SURGE_PRICE_TYPE = {
    "all": "0", "over-50k": "2", "over-10k": "5", "over-5k": "6",
    "over-1k": "8", "over-100k": "9",
}


# ── Task 31a-fix: trde_qty_tp(--vol-type) 8개 코드북 ────────────────
# 8개 전부 Required=Y라 키 자체를 생략할 수 없다(ka10038 dt처럼 omit 불가).
# 그리고 8개의 wire 값 폭이 전부 다르다 — 5자리 zero-pad / 4자리 zero-pad /
# 무패딩 정수. 키 집합(all/10k/50k/...)만 보면 똑같아 보이지만 실제 전송
# 바이트가 달라, 이름에 자릿수를 박아 둔다. 절대 합치지 말 것.
#
# ka10016/17/18/19 공용처럼 보이지만 API별로 나눠 둔다(값이 같아도 스펙이
# 각각 독립이라 한쪽이 바뀌면 나머지가 조용히 오염된다).

# ka10016(rank new-highlow) 전용 — trde_qty_tp(거래량구분, 5자리 zero-pad).
# 짝: LIMIT_MOVE_QTY_TYPE_5DIGIT / NEAR_HIGHLOW_QTY_TYPE_5DIGIT /
# SURGE_QTY_TYPE_5DIGIT (값 동일하지만 절대 합치지 말 것). 1곳: ka10016.
NEW_HIGH_LOW_QTY_TYPE_5DIGIT = {
    "all": "00000", "10k": "00010", "50k": "00050", "100k": "00100",
    "150k": "00150", "200k": "00200", "300k": "00300", "500k": "00500",
    "1000k": "01000",
}

# ka10017(rank limit) 전용 — trde_qty_tp(거래량구분, 5자리 zero-pad).
# 짝: NEW_HIGH_LOW_QTY_TYPE_5DIGIT / NEAR_HIGHLOW_QTY_TYPE_5DIGIT /
# SURGE_QTY_TYPE_5DIGIT. 1곳: ka10017. 절대 합치지 말 것.
LIMIT_MOVE_QTY_TYPE_5DIGIT = {
    "all": "00000", "10k": "00010", "50k": "00050", "100k": "00100",
    "150k": "00150", "200k": "00200", "300k": "00300", "500k": "00500",
    "1000k": "01000",
}

# ka10018(rank near-highlow) 전용 — trde_qty_tp(거래량구분, 5자리 zero-pad).
# 짝: NEW_HIGH_LOW_QTY_TYPE_5DIGIT / LIMIT_MOVE_QTY_TYPE_5DIGIT /
# SURGE_QTY_TYPE_5DIGIT. 1곳: ka10018. 절대 합치지 말 것.
NEAR_HIGHLOW_QTY_TYPE_5DIGIT = {
    "all": "00000", "10k": "00010", "50k": "00050", "100k": "00100",
    "150k": "00150", "200k": "00200", "300k": "00300", "500k": "00500",
    "1000k": "01000",
}

# ka10019(rank surge) 전용 — trde_qty_tp(거래량구분, 5자리 zero-pad).
# 스펙 Length 칸은 4로 적혀 있으나 값 목록은 전부 5자리다(스펙 오타로 판단,
# kwcli도 5자리를 보낸다). 짝: NEW_HIGH_LOW_QTY_TYPE_5DIGIT /
# LIMIT_MOVE_QTY_TYPE_5DIGIT / NEAR_HIGHLOW_QTY_TYPE_5DIGIT. 1곳: ka10019.
# 절대 합치지 말 것.
SURGE_QTY_TYPE_5DIGIT = {
    "all": "00000", "10k": "00010", "50k": "00050", "100k": "00100",
    "150k": "00150", "200k": "00200", "300k": "00300", "500k": "00500",
    "1000k": "01000",
}

# ka10020(rank orderbook-top) 전용 — trde_qty_tp(거래량구분, 4자리 zero-pad
# 인데 마지막 100k만 5자리 "00100"이다 — 스펙·kwcli 양쪽이 동일하게 이렇게
# 적혀 있어 그대로 따른다). "전체" 개념이 없고 최하단이 0000(장시작전,
# 0주이상)이라 사실상 무필터 자리다. 위 5자리 4형제와 자릿수가 달라 절대
# 합치지 말 것. 1곳: ka10020.
ORDERBOOK_TOP_QTY_TYPE_4DIGIT = {
    "preopen": "0000", "10k": "0010", "50k": "0050", "100k": "00100",
}

# ka10021(rank orderbook-surge) 전용 — trde_qty_tp(거래량구분, 무패딩 정수).
# "전체" 개념이 없다 — 최하단이 1(천주이상)이다. 짝:
# BALANCE_RATE_QTY_TYPE_BARE / VOLUME_SURGE_QTY_TYPE_BARE (여기만 1k가 있다).
# 1곳: ka10021. 절대 합치지 말 것.
ORDERBOOK_SURGE_QTY_TYPE_BARE = {
    "1k": "1", "5k": "5", "10k": "10", "50k": "50", "100k": "100",
}

# ka10022(rank balance-rate-surge) 전용 — trde_qty_tp(거래량구분, 무패딩
# 정수). "전체" 개념이 없다 — 최하단이 5(5천주이상)이다. 짝:
# ORDERBOOK_SURGE_QTY_TYPE_BARE(1k 있음) / VOLUME_SURGE_QTY_TYPE_BARE(200k
# 이상까지 있음). 1곳: ka10022. 절대 합치지 말 것.
BALANCE_RATE_QTY_TYPE_BARE = {
    "5k": "5", "10k": "10", "50k": "50", "100k": "100",
}

# ka10023(rank volume-surge) 전용 — trde_qty_tp(거래량구분, 무패딩 정수).
# "전체" 개념이 없다 — 최하단이 5(5천주이상)이다. ka10030의
# VOLUME_RANK_QTY_TYPE은 여기에 "all":"0"이 더 붙은 9개 값이라 겉보기엔
# 상위집합이지만, ka10023에는 "0"이 스펙에 없다 — 절대 합치지 말 것.
# 짝: ORDERBOOK_SURGE_QTY_TYPE_BARE / BALANCE_RATE_QTY_TYPE_BARE. 1곳: ka10023.
VOLUME_SURGE_QTY_TYPE_BARE = {
    "5k": "5", "10k": "10", "50k": "50", "100k": "100",
    "200k": "200", "300k": "300", "500k": "500", "1000k": "1000",
}

# ── ka10027~ka10039(market rank 등락률상위~증권사별매매상위) HumanChoice
# 전환 (Task 31b) ─────────────────────────────────────────────────────
#
# ka10030/ka10032/ka10038은 Tranche B에서 이미 전환됐다(VOLUME_RANK_*,
# MANAGED_STOCK_INCLUDE, STOCK_CONDITION, BROKER_BY_STOCK_SIDE,
# PERIOD_DAYS_OFF_BY_ONE — 위 섹션 참고) — 이 태스크는 손대지 않는다.
#
# 이번 청크에서도 31a와 동일한 패턴이 계속 나타난다: 값 집합이 같아 보이는
# stk_cnd/crd_cnd/pric_cnd/updown_incls 자리를 API별로 전부 분리했다.
# 그 중 일부(RANK_CHANGE_STK_CND/EXPECTED_CHANGE_STK_CND,
# RANK_CHANGE_PRICE_CND/EXPECTED_CHANGE_PRICE_CND,
# RANK_CHANGE_CREDIT_CND/CREDIT_RATIO_CREDIT_CND,
# RANK_CHANGE_INCLUDE_LIMIT/CREDIT_RATIO_INCLUDE_LIMIT)는 값이 정말로
# 100% 동일해서 어떤 테스트로도 서로 바꿔치기를 잡아낼 수 없다 — 이름
# 규약과 이 주석이 유일한 방어선이다(task-31b-report.md "구분 불가" 참고).

# ka10027(전일대비등락률상위) 전용 — sort_tp(정렬구분, 5개 값). ka10029의
# EXPECTED_CHANGE_SORT와 rise-rate/rise-price/fall-rate 3개 키가 겹치지만
# fall-rate의 값이 다르다(ka10027=3, ka10029=4) — 절대 합치지 말 것.
# 1곳: ka10027.
RANK_CHANGE_SORT = {
    "rise-rate": "1", "rise-price": "2", "fall-rate": "3",
    "fall-price": "4", "flat": "5",
}

# ka10027(전일대비등락률상위) 전용 — trde_qty_cnd(거래량조건, 4자리
# zero-pad, 9개 값). **와이어 값 결함 수정**: 기존 기본값 raw "0"은 4자리
# 스펙 어디에도 없는 값이었다("0000"이 전체조회). HumanChoice 전환과 함께
# 기본값을 "0000"으로 교정했다 — 이 자리는 표기 전환이 아니라 전송 바이트가
# 바뀌는 fix다(CHANGELOG 기재 대상, task-31b-report.md 참고). 1곳: ka10027.
RANK_CHANGE_QTY_CND = {
    "all": "0000", "10k": "0010", "50k": "0050", "100k": "0100",
    "150k": "0150", "200k": "0200", "300k": "0300", "500k": "0500",
    "1000k": "1000",
}

# ka10027(전일대비등락률상위) 전용 — stk_cnd(종목조건, 15개 값). ka10029의
# EXPECTED_CHANGE_STK_CND와 값이 완전히 동일하다(워크북으로 이중 확인) —
# 구분 불가 쌍이니 절대 자동으로 합치지 말 것. 1곳: ka10027.
RANK_CHANGE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-managed-preferred": "4", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9", "exclude-liquidation": "11", "only-margin-50": "12",
    "only-margin-60": "13", "exclude-etf": "14", "exclude-spac": "15",
    "exclude-etf-etn": "16",
}

# ka10027(전일대비등락률상위) 전용 — crd_cnd(신용조건, 7개 값). ka10033의
# CREDIT_RATIO_CREDIT_CND와 값이 완전히 동일하다 — 구분 불가 쌍. ka10029의
# EXPECTED_CHANGE_CREDIT_CND(9개 값, exclude-overlimit/short 추가)는 상위집합
# 이므로 절대 합치지 말 것. 1곳: ka10027.
RANK_CHANGE_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10027(전일대비등락률상위) 전용 — updown_incls(상하한포함). CREDIT_RATIO_INCLUDE_LIMIT
# 와 값이 완전히 동일하다(둘 다 yes:1,no:0) — 구분 불가 쌍. 1곳: ka10027.
RANK_CHANGE_INCLUDE_LIMIT = {"yes": "1", "no": "0"}

# ka10027(전일대비등락률상위) 전용 — pric_cnd(가격조건, 8개 값). ka10029의
# EXPECTED_CHANGE_PRICE_CND와 값이 완전히 동일하다 — 구분 불가 쌍. 1곳: ka10027.
RANK_CHANGE_PRICE_CND = {
    "all": "0", "under-1k": "1", "1k-2k": "2", "2k-5k": "3", "5k-10k": "4",
    "over-10k": "5", "over-1k": "8", "under-10k": "10",
}

# ka10027(전일대비등락률상위) 전용 — trde_prica_cnd(거래대금조건, 12개 값).
# 필드명 자체가 다른 커맨드의 pric_cnd/trde_qty_cnd와 겹치지 않으니 혼동
# 위험은 낮지만, 그래도 API별 분리 원칙을 그대로 따른다. 1곳: ka10027.
RANK_CHANGE_AMOUNT_CND = {
    "all": "0", "30m": "3", "50m": "5", "100m": "10", "300m": "30",
    "500m": "50", "1b": "100", "3b": "300", "5b": "500", "10b": "1000",
    "30b": "3000", "50b": "5000",
}

# ka10029(예상체결등락률상위) 전용 — sort_tp(정렬구분, 8개 값). RANK_CHANGE_SORT
# 참고(짝 — fall-rate 값이 다름, 절대 합치지 말 것). 1곳: ka10029.
EXPECTED_CHANGE_SORT = {
    "rise-rate": "1", "rise-price": "2", "flat": "3", "fall-rate": "4",
    "fall-price": "5", "volume": "6", "upper-limit": "7", "lower-limit": "8",
}

# ka10029(예상체결등락률상위) 전용 — trde_qty_cnd(거래량조건, 7개 값,
# 무패딩). 스펙 원문이 "1;천주이상"(세미콜론 오타, ka10034류와 동일 패턴)
# 이라 "1"=1천주이상을 빠뜨리기 쉽다 — 워크북으로 직접 확인해 포함시켰다.
# RANK_CHANGE_QTY_CND(ka10027, 4자리 zero-pad)와 자릿수부터 다르니 절대
# 합치지 말 것. 1곳: ka10029.
EXPECTED_CHANGE_QTY_CND = {
    "all": "0", "1k": "1", "3k": "3", "5k": "5", "10k": "10",
    "50k": "50", "100k": "100",
}

# ka10029(예상체결등락률상위) 전용 — stk_cnd(종목조건, 15개 값). RANK_CHANGE_STK_CND
# 참고(짝 — 값 완전 동일, 구분 불가). 1곳: ka10029.
EXPECTED_CHANGE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-managed-preferred": "4", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9", "exclude-liquidation": "11", "only-margin-50": "12",
    "only-margin-60": "13", "exclude-etf": "14", "exclude-spac": "15",
    "exclude-etf-etn": "16",
}

# ka10029(예상체결등락률상위) 전용 — crd_cnd(신용조건, 9개 값: RANK_CHANGE_CREDIT_CND
# 의 7개에 exclude-overlimit(5)/short(8)가 추가된 상위집합). 절대 합치지
# 말 것. 1곳: ka10029.
EXPECTED_CHANGE_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4",
    "exclude-overlimit": "5", "e": "7", "short": "8", "all-financing": "9",
}

# ka10029(예상체결등락률상위) 전용 — pric_cnd(가격조건, 8개 값). RANK_CHANGE_PRICE_CND
# 참고(짝 — 값 완전 동일, 구분 불가). 1곳: ka10029.
EXPECTED_CHANGE_PRICE_CND = {
    "all": "0", "under-1k": "1", "1k-2k": "2", "2k-5k": "3", "5k-10k": "4",
    "over-10k": "5", "over-1k": "8", "under-10k": "10",
}

# ka10031(전일거래량상위) 전용 — qry_tp(조회구분, 1:전일거래량,2:전일거래대금).
# 1곳: ka10031. rank_strt/rank_end(순위시작/끝)는 자유입력 수량이라 미전환.
PREV_VOLUME_KIND = {"volume": "1", "amount": "2"}

# ka10033(신용비율상위) 전용 — trde_qty_tp(거래량구분, 8개 값, 무패딩).
# ka10039의 BROKER_TOP_QTY_TYPE(all,5k,10k,50k,100k,500k,1000k, 200k/300k
# 없음)과 ka10030의 VOLUME_RANK_QTY_TYPE(9개 값)과 값 집합이 달라 절대
# 합치지 말 것. 1곳: ka10033.
CREDIT_RATIO_QTY_TYPE = {
    "all": "0", "10k": "10", "50k": "50", "100k": "100", "200k": "200",
    "300k": "300", "500k": "500", "1000k": "1000",
}

# ka10033(신용비율상위) 전용 — stk_cnd(종목조건, 7개 값 — RANK_CHANGE_STK_CND
# 의 15개 값 중 all/exclude-managed/exclude-margin-100/only-margin-100/
# only-margin-40/only-margin-30/only-margin-20 7개만 남긴 부분집합). 절대
# 합치지 말 것. 1곳: ka10033.
CREDIT_RATIO_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9",
}

# ka10033(신용비율상위) 전용 — updown_incls(상하한포함). RANK_CHANGE_INCLUDE_LIMIT
# 참고(짝 — 값 완전 동일, 구분 불가). 1곳: ka10033.
CREDIT_RATIO_INCLUDE_LIMIT = {"yes": "1", "no": "0"}

# ka10033(신용비율상위) 전용 — crd_cnd(신용조건, 7개 값). RANK_CHANGE_CREDIT_CND
# 참고(짝 — 값 완전 동일, 구분 불가). 1곳: ka10033.
CREDIT_RATIO_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10034/ka10036/ka10037(외인기간별매매상위/외인한도소진율증가상위/
# 외국계창구매매상위) 3곳 공용 — dt(기간, 0:당일,1:전일,5:5일,10:10일,
# 20:20일,60:60일). 스펙 원문은 "10;10일"(세미콜론 오타)로 세 시트 전부
# 동일하게 적혀 있다(docs/미국 REST API 문서.xlsx로 확인) — `,`/`:` 파싱
# 시 "10"이 누락되기 쉬우니 주의. 세 API가 값이 100% 동일해 이번 태스크
# 안에서 하나로 수렴시켰다(이전 판이 예약해 둔 이름을 그대로 사용,
# _constants.py 상단 AMT_QTY_TP_0_1 주석 옆 참고). ka10038의
# PERIOD_DAYS_OFF_BY_ONE(off-by-one)이나 ka10039의 BROKER_TOP_PERIOD
# (20d 없음)와는 값 집합이 달라 그쪽과는 절대 합치지 말 것.
# 이 상수는 이 파일에서 유일하게 3개 API(ka10034/ka10036/ka10037)를 동시에
# 서빙한다 — 지금은 워크북상 세 시트의 dt 값 집합이 character-for-character
# 동일함이 확인됐지만, 나중에 키움이 셋 중 하나만 개정하면 여기를 제자리에서
# 고치지 말고 그 API 전용 상수로 갈라낼 것 — 제자리 수정은 나머지 두 API를
# 조용히 함께 오염시킨다.
PERIOD_TODAY_PREV_5_60 = {
    "today": "0", "previous": "1", "5d": "5", "10d": "10", "20d": "20", "60d": "60",
}

# ka10034(외인기간별매매상위) 전용 — trde_tp(매매구분, 1:순매도,2:순매수,
# 3:순매매). ka10035의 FOREIGN_CONSECUTIVE_SIDE(net-sell:1,net-buy:2)는
# net-trade가 없는 부분집합 — 절대 합치지 말 것. 1곳: ka10034.
FOREIGN_PERIOD_SIDE = {"net-sell": "1", "net-buy": "2", "net-trade": "3"}

# ka10035(외인연속순매매상위) 전용 — trde_tp(구분, 1:연속순매도,2:연속순매수).
# FOREIGN_PERIOD_SIDE(ka10034)의 부분집합처럼 보이나 라벨 의미가 다르고
# (단발 순매도/순매수 vs 연속), ka10034에는 있는 net-trade(3)가 이쪽엔
# 없다 — 절대 합치지 말 것. 1곳: ka10035.
FOREIGN_CONSECUTIVE_SIDE = {"net-sell": "1", "net-buy": "2"}

# ka10035(외인연속순매매상위) 전용 — base_dt_tp(기준일구분, 0:당일기준,
# 1:전일기준). 1곳: ka10035. **cross-field 해저드**: 값 집합(today:0,
# previous:1)이 PERIOD_TODAY_PREV_5_60(ka10034/36/37의 dt)과
# BROKER_TOP_PERIOD(ka10039의 dt) 양쪽 모두의 진짜 부분집합이다 — 필드
# 자체가 다른데(base_dt_tp vs dt) 흔한 today/previous 키 이름 때문에
# "today/previous 상수 통합" 리팩터가 이 상수를 그 두 상수 중 하나로 잘못
# 흡수하기 쉽다. 절대 합치지 말 것.
FOREIGN_CONSECUTIVE_BASE_DATE = {"today": "0", "previous": "1"}

# ka10037(외국계창구매매상위) 전용 — trde_tp(매매구분, 1:순매수,2:순매도,
# 3:매수,4:매도). ka10039의 BROKER_TOP_SIDE(net-buy:1,net-sell:2)는 buy/
# sell 단독값이 없는 부분집합 — 절대 합치지 말 것. 1곳: ka10037.
FOREIGN_BROKER_SIDE = {"net-buy": "1", "net-sell": "2", "buy": "3", "sell": "4"}

# ka10037(외국계창구매매상위) 전용 — sort_tp(정렬구분, 1:금액,2:수량). 1곳: ka10037.
FOREIGN_BROKER_SORT = {"amount": "1", "quantity": "2"}

# ka10039(증권사별매매상위) 전용 — trde_qty_tp(거래량구분, 7개 값, 무패딩).
# ka30002의 ELW_BROKER_QTY_TYPE과 값이 완전히 동일하다(구분 불가 쌍) —
# api_id가 달라 이름은 반드시 분리 유지. CREDIT_RATIO_QTY_TYPE(ka10033,
# 200k/300k 있음)과는 값 집합이 달라 그쪽과는 절대 합치지 말 것. 1곳: ka10039.
BROKER_TOP_QTY_TYPE = {
    "all": "0", "5k": "5", "10k": "10", "50k": "50", "100k": "100",
    "500k": "500", "1000k": "1000",
}

# ka10039(증권사별매매상위) 전용 — trde_tp(매매구분, 1:순매수,2:순매도).
# ka30002의 ELW_BROKER_SIDE와 값이 완전히 동일하다(구분 불가 쌍). FOREIGN_BROKER_SIDE
# (ka10037)의 부분집합이기도 하니 그쪽과도 절대 합치지 말 것. 1곳: ka10039.
BROKER_TOP_SIDE = {"net-buy": "1", "net-sell": "2"}

# ka10039(증권사별매매상위) 전용 — dt(기간, 0:당일,1:전일,5:5일,10:10일,
# 60:60일 — 20일이 없다). PERIOD_TODAY_PREV_5_60(ka10034/36/37)의 부분집합
# 처럼 보이지만 20d가 빠져 있어 값 집합이 다르다 — 절대 합치지 말 것.
# 1곳: ka10039.
BROKER_TOP_PERIOD = {
    "today": "0", "previous": "1", "5d": "5", "10d": "10", "60d": "60",
}

# ── ka10042~ka90009(market rank 순매수거래원순위~외국인기관매매상위)
# HumanChoice 전환 (Task 31c) ────────────────────────────────────────
#
# ka10042(net-buyer)의 qry_dt_tp/pot_tp/sort_base는 워크북으로
# character-for-character 동일함을 확인해 TRADER_ANALYSIS_DATE_MODE/
# TRADER_ANALYSIS_POSITION/TRADER_ANALYSIS_SORT(위 ka10043 섹션)를
# 공유하도록 전환했다 — 새 상수를 추가하지 않았다. ka10042의 dt(기간)는
# I2 규칙(값→라벨이 단위접미사 부착만으로 유도되는 폐쇄집합은 수량 유지)에
# 따라 이번 태스크에서 전환하지 않고 raw 텍스트로 남긴다(브리프 판정 그대로).

# ka10062(동일순매매순위) 전용 — trde_tp(매매구분, 1:순매수,2:순매도).
# 값은 BROKER_TOP_SIDE(ka10039)/ELW_BROKER_SIDE(ka30002)/INVESTOR_TOP_SIDE
# (ka10065)와 완전히 동일하다(구분 불가 쌍, superset-closure 스크립트로
# 확인) — api_id가 달라 이름은 반드시 분리 유지. FOREIGN_BROKER_SIDE
# (ka10037, buy/sell 단독값 포함)의 진짜 부분집합이기도 하니 그쪽과 절대
# 합치지 말 것. 1곳: ka10062.
SAME_NET_TRADE_SIDE = {"net-buy": "1", "net-sell": "2"}

# ka10062(동일순매매순위) 전용 — sort_cnd(정렬조건, 1:수량,2:금액). 극성
# 주의: AMT_QTY_TP_1_2(1:금액,2:수량)와 키 집합(amount/quantity)은 같지만
# 코드가 정반대다 — 절대 그쪽과 합치지 말 것. 1곳: ka10062.
SAME_NET_TRADE_SORT = {"quantity": "1", "amount": "2"}

# ka10062(동일순매매순위) 전용 — unit_tp(단위구분, 1:단주,1000:천주). 1곳:
# ka10062.
SAME_NET_TRADE_UNIT = {"share": "1", "thousand": "1000"}

# ka10065(장중투자자별매매상위) 전용 — trde_tp(매매구분, 1:순매수,2:순매도).
# SAME_NET_TRADE_SIDE(ka10062)/BROKER_TOP_SIDE(ka10039)/ELW_BROKER_SIDE
# (ka30002)와 값이 완전히 동일하다(구분 불가 쌍, superset-closure 스크립트로
# 확인) — api_id별 이름 분리 유지. FOREIGN_BROKER_SIDE(ka10037)의 진짜
# 부분집합이기도 하니 그쪽과 절대 합치지 말 것. 1곳: ka10065.
INVESTOR_TOP_SIDE = {"net-buy": "1", "net-sell": "2"}

# ka10065(장중투자자별매매상위) 전용 — orgn_tp(기관구분, 11개 값, 4자리).
# 개념은 "투자자구분"이지만 와이어 코드가 invsr_tp(ka10058)/invsr(ka10063)와
# 전혀 다르다 — 절대 그쪽과 합치지 말 것(브리프 "투자자구분 3계통" 해저드
# 참고). 1곳: ka10065.
INVESTOR_TOP_ORGN = {
    "foreign": "9000", "foreign-broker": "9100", "financial-investment": "1000",
    "investment-trust": "3000", "other-financial": "5000", "bank": "4000",
    "insurance": "2000", "pension": "6000", "state": "7000",
    "other-corporate": "7100", "institution": "9999",
}

# ka10065(장중투자자별매매상위) amt_qty_tp(금액수량구분, N=선택, 1:금액,
# 2:수량)는 AMT_QTY_TP_1_2를 공유한다(위 AMT_QTY_TP_1_2 주석의 커플링
# 명시 참고) — 별도 상수를 만들지 않는다.

# ka10098(시간외단일가등락율순위) 전용 — sort_base(정렬기준, 5개 값).
# RANK_CHANGE_SORT(ka10027, 필드명 sort_tp)와 값이 완전히 동일하다(구분
# 불가 쌍, superset-closure 스크립트로 확인) — 필드명 자체가 다르고 api_id도
# 달라 절대 합치지 말 것. 1곳: ka10098.
AFTERHOURS_CHANGE_SORT = {
    "rise-rate": "1", "rise-price": "2", "fall-rate": "3",
    "fall-price": "4", "flat": "5",
}

# ka10098(시간외단일가등락율순위) 전용 — stk_cnd(종목조건, 16개 값, 2자리).
# 코드 "2"(정리매매종목제외)가 이 API 고유값이다 — RANK_CHANGE_STK_CND/
# EXPECTED_CHANGE_STK_CND는 정리매매종목제외를 코드 "11"로 쓰고(값 자체가
# 다름), VOLUME_SURGE_STK_CND는 exclude-etf-etn을 코드 "18"로 쓴다(이쪽은
# "16") — 겉보기엔 비슷해도 (key,value) 쌍이 일치하지 않아 다른 stk_cnd
# 상수 어느 것과도 절대 합치지 말 것. superset-closure 스크립트 확인 결과
# 이 상수는 NEW_HIGH_LOW_STK_CND/NEAR_HIGHLOW_STK_CND/SURGE_STK_CND/
# ORDERBOOK_TOP_STK_CND/ORDERBOOK_SURGE_STK_CND/BALANCE_RATE_STK_CND/
# CREDIT_RATIO_STK_CND(7개, 전부 7-값 부분집합류)의 진짜 상위집합이다 —
# 이 방향(작은 것 → 이 상수로 바꿔치기)의 위험은 그 7개 상수들 각자의 기존
# 테스트가 이미 방어한다(exclude-preferred 등 이 상수에도 포함된 이름으로
# 거부 테스트가 걸려 있음). 1곳: ka10098.
AFTERHOURS_CHANGE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-liquidation": "2",
    "exclude-preferred": "3", "exclude-managed-preferred": "4",
    "exclude-margin-100": "5", "only-margin-100": "6", "only-margin-50": "12",
    "only-margin-60": "13", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9", "exclude-etf": "14", "exclude-spac": "15",
    "exclude-etf-etn": "16", "exclude-etn": "17",
}

# ka10098(시간외단일가등락율순위) 전용 — trde_qty_cnd(거래량조건, 8개 값,
# 5자리). 스펙 원문이 "100;천주이상"(세미콜론 오타)라 "100"=1천주이상을
# 빠뜨리기 쉽다 — 워크북·kwcli 이중 확인으로 포함시켰다. kwcli는 이 자리를
# `100`/`500`/`1000`처럼 코드값 그대로 이름으로 쓰지만(all=0;100=10;500=50;
# 1000=100;5k=500;10k=1000;50k=5000;100k=10000), 값이 우리 쪽 다른
# trde_qty_cnd류와 헷갈리는 것을 피하려고 여기서는 `100+`/`500+`/`1k+`처럼
# 하한을 명시하는 이름을 쓴다(값은 kwcli와 완전히 동일, 이름만 다름).
# 다른 trde_qty_cnd 사이트(RANK_CHANGE_QTY_CND는 4자리 zero-pad, 값 집합도
# 다름)와 절대 합치지 말 것. superset-closure 스크립트 확인 결과 다른
# 어떤 상수와도 (key,value) 관계가 없다. 1곳: ka10098.
AFTERHOURS_CHANGE_QTY_CND = {
    "all": "0", "100+": "10", "500+": "50", "1k+": "100", "5k+": "500",
    "10k+": "1000", "50k+": "5000", "100k+": "10000",
}

# ka10098(시간외단일가등락율순위) 전용 — crd_cnd(신용조건, 9개 값).
# EXPECTED_CHANGE_CREDIT_CND(ka10029)와 값이 완전히 동일하다(구분 불가
# 쌍, superset-closure 스크립트로 확인). RANK_CHANGE_CREDIT_CND(ka10027)/
# CREDIT_RATIO_CREDIT_CND(ka10033)를 포함해 총 8개 7값짜리 crd_cnd 상수의
# 진짜 상위집합이기도 하니 그쪽들과 절대 합치지 말 것(이 방향의 위험은 그
# 상수들 각자의 기존 테스트가 이미 방어한다). 1곳: ka10098.
AFTERHOURS_CHANGE_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4",
    "exclude-overlimit": "5", "e": "7", "short": "8", "all-financing": "9",
}

# ka10098(시간외단일가등락율순위) 전용 — trde_prica(거래대금, 12개 값,
# 5자리). **와이어 값 함정**: RANK_CHANGE_AMOUNT_CND(ka10027,
# trde_prica_cnd 필드)와 라벨 형태(all/30m/50m/.../50b)가 비슷해 보이지만
# 스케일이 한 자리 다르다 — 예를 들어 코드 "10"은 RANK_CHANGE_AMOUNT_CND에서
# "100m"(1억원)을 뜻하지만 여기서는 "10m"(1천만원)을 뜻한다. 워크북 원문
# 라벨(0:전체조회,5:5백만원이상,10:1천만원이상,...,10000:100억원이상)과
# kwcli(all=0;5m=5;10m=10;30m=30;50m=50;100m=100;300m=300;500m=500;
# 1b=1000;3b=3000;5b=5000;10b=10000)로 이중 확인했다. 필드명 자체도
# trde_prica(여기) vs trde_prica_cnd(ka10027)로 달라 혼동 위험은 낮지만,
# 라벨 유사성만으로 RANK_CHANGE_AMOUNT_CND와 절대 합치지 말 것.
# superset-closure 스크립트 확인 결과 다른 어떤 상수와도 (key,value) 관계가
# 없다. 1곳: ka10098.
AFTERHOURS_CHANGE_AMOUNT_CND = {
    "all": "0", "5m": "5", "10m": "10", "30m": "30", "50m": "50",
    "100m": "100", "300m": "300", "500m": "500", "1b": "1000",
    "3b": "3000", "5b": "5000", "10b": "10000",
}

# ka90009(외국인기관매매상위) amt_qty_tp(금액수량구분, Required=Y, 1:금액,
# 2:수량)는 AMT_QTY_TP_1_2를 공유한다(위 AMT_QTY_TP_1_2 주석의 커플링
# 명시 참고) — 별도 상수를 만들지 않는다.

# ka90009(외국인기관매매상위) 전용 — qry_dt_tp(조회일자구분, 0:조회일자
# 미포함, 1:조회일자 포함). 값은 CHECK_YES_1_NO_0(yes:1,no:0)과 완전히
# 동일하지만, CHECK_YES_1_NO_0의 주석이 "stock.py의 qry_dt_tp/pot_tp 등과
# 절대 합치지 말 것"이라고 이미 명시적으로 예약해 둔 이름이라 재사용하지
# 않는다 — 이 API 전용 이름을 새로 쓴다. superset-closure 스크립트 확인
# 결과 CHECK_YES_1_NO_0/MANAGED_STOCK_INCLUDE/NEW_HIGH_LOW_INCLUDE_LIMIT/
# SURGE_INCLUDE_LIMIT/RANK_CHANGE_INCLUDE_LIMIT/CREDIT_RATIO_INCLUDE_LIMIT
# 전부와 값이 동일한 구분 불가 클러스터(2값 yes/no 계열은 전부 이렇다) —
# 이름 규약이 유일한 방어선이다. 1곳: ka90009.
FOREIGN_INST_DATE_INCLUDE = {"yes": "1", "no": "0"}

# ── ka10051/ka20001/ka20002/ka20009/ka10101/ka90001(market sector·theme)
# HumanChoice 전환 (Task 32) ─────────────────────────────────────────

# ka10051(업종별투자자순매수) amt_qty_tp(금액수량구분, 0:금액,1:수량)는
# AMT_QTY_TP_0_1을 공유한다(위 AMT_QTY_TP_0_1 주석의 커플링 명시 참고) —
# 별도 상수를 만들지 않는다.

# ka20001(업종현재가)/ka20002(업종별주가)/ka20009(업종현재가일별) 3곳
# 공용 — mrkt_tp(시장구분, 0:코스피,1:코스닥,2:코스피200). 워크북에서 세
# 시트 모두 "0:코스피, 1:코스닥, 2:코스피200"으로 character-for-character
# 동일함을 확인했다. 기존 MARKET_KOSPI_KOSDAQ(kospi:0,kosdaq:1)의 진짜
# 상위집합이지만(코스피200 값 2가 추가) 그쪽을 재사용하지 않는다 — 그러면
# kospi200 이름이 없어 BadParameter가 난다. ka10101(sector_codes)의
# SECTOR_CODES_MARKET(0/1/2/4/7)의 진짜 부분집합이기도 하다 — 절대 그쪽과
# 합치지 말 것(코스피100/KRX100 이름이 여기선 거부돼야 한다).
#
# *** 이 상수는 api_id 3개가 공유한다. 한쪽 스펙만 바뀌면 이 상수를
# 제자리에서 고치지 말고 분리할 것 — 제자리 수정은 나머지 둘을 조용히
# 함께 오염시킨다. ***
SECTOR_PRICE_MARKET = {"kospi": "0", "kosdaq": "1", "kospi200": "2"}

# ka10101(업종코드리스트) 전용 — mrkt_tp(시장구분, 5개 값: 0:코스피(거래소),
# 1:코스닥,2:KOSPI200,4:KOSPI100,7:KRX100(통합지수)). SECTOR_PRICE_MARKET
# (ka20001/02/09)의 kospi/kosdaq/kospi200 3개 값을 그대로 포함하는 진짜
# 상위집합이지만 api_id가 달라 절대 합치지 말 것 — kospi100/krx100 이름은
# SECTOR_PRICE_MARKET 쪽에서 거부돼야 한다. 1곳: ka10101.
SECTOR_CODES_MARKET = {
    "kospi": "0", "kosdaq": "1", "kospi200": "2", "kospi100": "4", "krx100": "7",
}

# ka90001(테마그룹별) 전용 — qry_tp(검색구분, 0:전체검색,1:테마검색,
# 2:종목검색). 1곳: ka90001.
THEME_LOOKUP_KIND = {"all": "0", "theme": "1", "stock": "2"}

# ka90001(테마그룹별) 전용 — flu_pl_amt_tp(등락수익구분, 1:상위기간수익률,
# 2:하위기간수익률,3:상위등락률,4:하위등락률). 1곳: ka90001.
THEME_LOOKUP_SORT = {
    "profit-top": "1", "profit-bottom": "2", "change-top": "3", "change-bottom": "4",
}
