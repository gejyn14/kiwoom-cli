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
# 전용(13곳, ka10066 포함)이며, 0:금액,1:수량 짝은 별도로
# `AMT_QTY_TP_0_1`이라는 이름을 예약해 둔다(ka10051/ka10131 이관 시 이
# 이름으로 추가할 것 — 절대 이 상수를 재사용하지 말 것).
AMT_QTY_TP_1_2 = {"amount": "1", "quantity": "2"}

# AMT_QTY_TP_1_2와 키 집합(amount/quantity)은 같지만 극성이 다른 짝(0:금액,
# 1:수량) — ka10131(stock.py, 기관외국인연속매매현황)에서 사용. ka10051
# (market.py:651, 업종별투자자순매수)도 같은 코드북이나 아직 이관 전이라
# 이 상수를 쓰지 않는다(별도 작업 대상). 절대 AMT_QTY_TP_1_2와 합치지 말 것 —
# 키 집합이 같아 합쳐도 조용히 통과하고, 극성만 뒤집힌 값이 나간다.
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

# ka10043 전용 — qry_dt_tp(조회기간구분). market.py의 ka10042(rank net-buyer)도
# 같은 필드명·값 집합(0:기간,1:일자)을 쓰는 것으로 보이나 아직 이관 전이라
# 이 상수를 쓰지 않는다(별도 작업 대상, market.py는 이번 태스크 범위 밖).
# 1곳: ka10043.
TRADER_ANALYSIS_DATE_MODE = {"period": "0", "start-end": "1"}

# ka10043 전용 — pot_tp(시점구분, 0:당일,1:전일). market.py의 ka10042도 같은
# 필드명·값 집합을 쓰는 것으로 보이나 아직 이관 전이라 이 상수를 쓰지 않는다.
# 1곳: ka10043.
TRADER_ANALYSIS_POSITION = {"today": "0", "previous": "1"}

# ka10043 전용 — sort_base(정렬기준, 1:종가순,2:날짜순). market.py의 ka10042도
# 같은 필드명·값 집합을 쓰는 것으로 보이나 아직 이관 전이라 이 상수를 쓰지 않는다.
# 1곳: ka10043.
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
