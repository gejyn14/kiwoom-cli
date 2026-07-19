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
# MARKET_SEARCH({kospi:0, kosdaq:10, k-otc:30, konex:50, etf:8, elw:3})는
# 어디에서도 참조되지 않는 죽은 상수라 제거했다. 배선된 적이 없어 값을
# 고정할 테스트를 붙일 수도 없으면서, MARKET_KOSPI_KOSDAQ 등 살아 있는
# mrkt_tp 코드북들과 키만 겹쳐(kosdaq이 "1"이 아니라 "10") 잘못 재사용될
# 표면만 넓히고 있었다. 다시 필요해지면 그때 해당 api_id 스펙을 워크북에서
# 직접 확인하고 그 api_id 이름으로 새로 만들 것.
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
# ka10059는 Task 34a에서 실제로 연결됐다(stock.py). ka10060(chart
# investor)/ka10064(chart intraday-investor)는 Task 34b에서 워크북 확인 후
# 연결됐다(character-for-character 동일: "0:순매수, 1:매수, 2:매도").
#
# *** 이 상수는 api_id 4개가 공유한다. 한쪽 스펙만 바뀌면 이 상수를 제자리에서
# 고치지 말고 분리할 것 — 제자리 수정은 나머지 셋을 조용히 함께 오염시킨다. ***
TRDE_TP_NET_BUY_BUY_SELL = {"net-buy": "0", "buy": "1", "sell": "2"}

# amt_qty_tp(금액수량구분)도 API마다 극성이 다르다(표준 1:금액,2:수량 vs
# ka10051/ka10131의 0:금액,1:수량) — 그런데 두 코드북의 키 집합(amount/
# quantity)이 완전히 같아서, trde_tp와 달리 이름만 봐서는 극성을 구분할
# 수 없다. 그래서 이름 자체에 코드 값을 새긴다: 이 상수는 1:금액,2:수량
# 전용이며, 0:금액,1:수량 짝은 별도로 `AMT_QTY_TP_0_1`이라는 이름을 예약해
# 둔다(ka10051 이관 시 이 이름으로 추가할 것 — 절대 이 상수를 재사용하지 말 것).
#
# *** 이 상수는 api_id 12개가 공유한다. 고치기 전에 12곳 전부를 확인할 것.
# (줄번호는 편집마다 바로 어긋나므로 적지 않는다 — api_id로 grep할 것.) ***
#   market.py   ka10065  amt_qty_tp   (Task 31c에서 추가)
#   market.py   ka90009  amt_qty_tp   (Task 31c에서 추가)
#   market.py   ka90005  amt_qty_tp
#   market.py   ka90007  amt_qty_tp   (Task 33에서 추가)
#   market.py   ka90008  amt_qty_tp   (Task 33에서 추가)
#   market.py   ka90010  amt_qty_tp
#   stock.py    ka10066  amt_qty_tp
#   stock.py    ka10059  amt_qty_tp   (Task 34a에서 추가)
#   stock.py    ka10061  amt_qty_tp   (Task 34a에서 추가)
#   stock.py    ka90003  amt_qty_tp   (Task 34b, program-top에서 추가)
#   stock.py    ka10060  amt_qty_tp   (Task 34b, chart investor에서 추가)
#   stock.py    ka10064  amt_qty_tp   (Task 34b, chart intraday-investor에서 추가)
# 열두 시트 모두 요청 코드북은 1:금액, 2:수량으로 동일하다. 다만 표기까지 같지는
# 않다 — ka90009 시트는 "1:금액(천만), 2:수량(천)"으로 적혀 있는데, 괄호 안은
# 응답 단위 주석이지 요청 코드가 아니다. required 여부도 갈린다(ka10065는
# Required=N, ka90009/ka90007/ka90008은 Required=Y). 값이 같으니 공유는
# 정당하지만, 나중에 한 api_id의 스펙만 바뀌면 이 상수를 제자리에서 고치지
# 말고 분리할 것 — 제자리 수정은 나머지 열하나를 조용히 함께 오염시킨다.
#
# ka90013(종목일별프로그램매매추이)도 같은 필드·값을 쓰지만 스펙상
# Required=N이고 기존 기본값이 빈 문자열 ""이다(Required=Y인 위 7곳은 전부
# 기본값이 "1") — 빈 문자열은 이 2-값 매핑에 없어 그대로 감싸면 기본 호출이
# BadParameter로 깨진다. 억지로 기본값을 "1"/"2"로 바꾸면 전송 바이트가
# 바뀌므로(빈 문자열은 스펙상 합법적인 "생략" 값), ka90013의 --unit은 이번
# 태스크에서 raw 텍스트로 남긴다(market.py, ka90013 참고).
AMT_QTY_TP_1_2 = {"amount": "1", "quantity": "2"}

# AMT_QTY_TP_1_2와 키 집합(amount/quantity)은 같지만 극성이 다른 짝(0:금액,
# 1:수량) — ka10131(stock.py, 기관외국인연속매매현황)/ka10051(market.py,
# 업종별투자자순매수)이 공유한다. 워크북에서 두 시트가 같은 매핑임을 확인했다.
# 표기까지 같지는 않다 — ka10051은 "금액:0, 수량:1", ka10131은 "0:금액, 1:수량"으로
# 라벨과 코드의 순서가 반대다. 값 대응이 같을 뿐이다. 절대 AMT_QTY_TP_1_2와 합치지
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
# trde_tp 코드북들과는 완전히 별개 필드이니 혼용 금지. Task 34b가 추가한
# PROGRAM_TOP_SIDE({net-sell:1,net-buy:2})의 진짜 부분집합이다(클로저
# 스크립트로 확인, net-buy:2가 겹친다) — "net-sell" 거부 테스트로 방어.
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
# 짝: AMT_QTY_TP_1_2(12곳), AMT_QTY_TP_0_1(ka10051/ka10131). 이 상수는 1곳: ka10063.
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

# dt(기간, 5/10/20/40/60/120). 값→라벨이 단위접미사 부착만으로 유도되는
# 폐쇄집합이라 I2 규칙("수량은 raw 유지")을 적용해 raw 텍스트로 되돌릴
# 후보처럼 보이지만, 이 자리는 v2.11.0에 이미 HumanChoice로 배포됐다 —
# 되돌리면 배포된 검증을 걷어내 잘못된 값이 exit 0으로 조용히 통과하게
# 된다. **I2 규칙보다 이 예외가 우선한다. raw로 되돌리지 말 것.**
#
# ka10042(market.py rank net-buyer)와 ka10043(stock.py trader-analysis)의
# 워크북 Description이 character-for-character 동일함을 확인하고 공유한다
# (둘 다 "5:5일, 10:10일, 20:20일, 40:40일, 60:60일, 120:120일").
#
# *** 이 상수는 api_id 2개가 공유한다. 한쪽 스펙만 바뀌면 이 상수를 제자리에서
# 고치지 말고 분리할 것 — 제자리 수정은 나머지 하나를 조용히 함께
# 오염시킨다(TRADER_ANALYSIS_DATE_MODE와 동일한 분리 원칙).
TRADER_ANALYSIS_PERIOD_5_120 = {
    "5d": "5", "10d": "10", "20d": "20", "40d": "40", "60d": "60", "120d": "120",
}

# 거래종료ELW제외/거래종료제외 — 0:포함,1:제외. elw_surge(ka30001, 필드
# trde_end_elwskip)/elw_broker_top(ka30002, trde_end_elwskip)/elw_disparity
# (ka30004, trde_end_elwskip)/elw_change_rank(ka30009, trde_end_skip)/
# elw_balance_rank(ka30010, trde_end_skip) 5개 api_id가 공유한다 — 필드명은
# trde_end_elwskip/trde_end_skip 두 가지고, 스펙 Description 문구도 세
# 가지로 갈린다. 같은 것은 **값 대응**뿐이다(5개 시트 전부 0=포함, 1=제외):
#   ka30001/ka30002  "0:포함, 1:제외"
#   ka30004          "1:거래종료ELW제외, 0:거래종료ELW포함"
#   ka30009/ka30010  "1:거래종료제외, 0:거래종료포함"
# (종전 이 자리에는 5개 시트가 "character-for-character 동일"하다고 적혀
# 있었으나 사실이 아니다 — 워크북 재확인 결과 위 세 형태다. 공유 자체는
# 값 대응이 같으므로 여전히 정당하다.)
# 이전 판(ELW_BROKER_END_SKIP)은 "1곳: ka30002, 나머지 4곳은 검증/적용 안
# 됨"이라고 예약해 뒀는데 이번 태스크(Task 33)가 그 별도 작업이라 5곳
# 전부로 넓혔다.
#
# *** 이 상수는 api_id 5개가 공유한다. 한쪽 스펙만 바뀌면 이 상수를 제자리
# 에서 고치지 말고 분리할 것 — 제자리 수정은 나머지 넷을 조용히 함께
# 오염시킨다. ***
EXCLUDE_ENDED_ELW = {"include": "0", "exclude": "1"}

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

# ── ka40001/ka40004(market etf 수익율·전체시세) HumanChoice 전환
# (Task 33) ─────────────────────────────────────────────────────────

# ka40001(ETF수익율) 전용 — dt(기간, 0:1주,1:1달,2:6개월,3:1년). 1곳: ka40001.
ETF_RETURNS_PERIOD = {"week": "0", "month": "1", "six-months": "2", "year": "3"}

# ka40004(ETF전체시세) 전용 — txon_type(과세유형, 6개 값). 1곳: ka40004.
ETF_ALL_TAX_TYPE = {
    "all": "0", "tax-free": "1", "holding-tax": "2", "company": "3",
    "foreign": "4", "foreign-tax-free": "5",
}

# ka40004(ETF전체시세) 전용 — navpre(NAV대비, 0:전체,1:NAV>전일종가,
# 2:NAV<전일종가). 1곳: ka40004.
ETF_ALL_NAV = {"all": "0", "nav-gt-close": "1", "nav-lt-close": "2"}

# ka40004(ETF전체시세) 전용 — txon_yn(과세여부, 0:전체,1:과세,2:비과세).
# 1곳: ka40004.
ETF_ALL_TAXABLE = {"all": "0", "taxable": "1", "tax-free": "2"}

# ka40004(ETF전체시세)의 mngmcomp(운용사)/trace_idex(추적지수코드)는 스펙에
# 예시 몇 개("0000:전체" 등)+"기타운용사" 카테고리만 있고 전체 코드표가 없는
# 개방형 목록이다 — kwcli도 값 매핑 없이 자유 코드로 둔다. 미확인이라 이번
# 태스크에서 전환하지 않고 raw 텍스트로 남긴다(market.py의 --company/--index).

# ── ka30001/ka30004/ka30005/ka30009/ka30010(market elw 가격급등락·괴리율·
# 조건검색·등락율순위·잔량순위) HumanChoice 전환 (Task 33) ──────────────
# ka30002(elw broker-top)는 Tranche B에서 이미 전부 HumanChoice였다 —
# --exclude-expired만 위 EXCLUDE_ENDED_ELW 공유 상수로 갈아탔다(신규 상수
# 추가 아님, 위 섹션 참고).

# ka30001(ELW가격급등락) 전용 — flu_tp(등락구분, 1:급등,2:급락). 값은
# SURGE_DIRECTION(ka10019, flu_tp)과 완전히 동일하다(구분 불가 쌍,
# superset-closure 스크립트로 확인) — api_id가 달라 이름은 분리 유지.
# 1곳: ka30001.
ELW_SURGE_DIRECTION = {"rise": "1", "fall": "2"}

# ka30001(ELW가격급등락) 전용 — tm_tp(시간구분, 1:분전,2:일전). 값은
# SURGE_TIME_UNIT(ka10019, tm_tp)과 완전히 동일하다(구분 불가 쌍) — api_id가
# 달라 이름은 분리 유지. 1곳: ka30001.
ELW_SURGE_TIME_UNIT = {"minute": "1", "day": "2"}

# ka30001(ELW가격급등락) 전용 — trde_qty_tp(거래량구분, 7개 값, 무패딩).
# VOLUME_RANK_QTY_TYPE(ka10030)의 진짜 부분집합이다(5k/200k가 빠짐,
# superset-closure 스크립트로 확인) — 절대 그쪽을 여기 재사용하지 말 것
# ("5k"/"200k" 이름은 ka30001에서 거부돼야 한다). 1곳: ka30001.
ELW_SURGE_QTY_TYPE = {
    "all": "0", "10k": "10", "50k": "50", "100k": "100",
    "300k": "300", "500k": "500", "1000k": "1000",
}

# ka30001/ka30004(ELW가격급등락/ELW괴리율) 공용 — rght_tp(권리구분, 3자리
# zero-pad, EX 포함 8개 값). 두 시트의 **값 대응**이 동일함을 워크북에서
# 확인했다. 문구까지 같지는 않다 — ka30001은 "000:전체, 001:콜, ...",
# ka30004는 콜론 뒤에 공백이 붙은 "000: 전체, 001: 콜, ..."이다(종전 이
# 자리에는 두 시트가 "character-for-character 동일"하다고 적혀 있었으나
# 사실이 아니다. 값 대응이 같으므로 공유 자체는 여전히 정당하다). ka30009/ka30010의 ELW_RANK_RIGHT_TYPE_3DIGIT(EX가
# 없는 7개 값)의 진짜 상위집합이므로 절대 그쪽과 합치지 말 것 — "ex" 이름은
# ka30009/ka30010에서 거부돼야 한다. ka30005의 ELW_RIGHT_TYPE_1DIGIT(무패딩)
# 와도 자릿수가 달라 절대 합치지 말 것.
#
# *** 이 상수는 api_id 2개가 공유한다. 한쪽 스펙만 바뀌면 이 상수를 제자리
# 에서 고치지 말고 분리할 것. ***
ELW_RIGHT_TYPE_3DIGIT = {
    "all": "000", "call": "001", "put": "002", "dc": "003", "dp": "004",
    "ex": "005", "early-call": "006", "early-put": "007",
}

# ka30005(ELW조건검색) 전용 — rght_tp(권리구분, 무패딩 단일 숫자, EX 포함
# 8개 값). ELW_RIGHT_TYPE_3DIGIT과 라벨·값 대응은 같으나 자릿수(3자리
# zero-pad vs 무패딩)가 달라 절대 합치지 말 것. 1곳: ka30005.
ELW_RIGHT_TYPE_1DIGIT = {
    "all": "0", "call": "1", "put": "2", "dc": "3", "dp": "4",
    "ex": "5", "early-call": "6", "early-put": "7",
}

# ka30005(ELW조건검색) 전용 — sort_tp(정렬구분, 0:정렬없음,1:상승율순,
# 2:상승폭순,3:하락율순,4:하락폭순,5:거래량순,6:거래대금순,7:잔존일순).
# 1곳: ka30005.
ELW_SEARCH_SORT = {
    "none": "0", "rise-rate": "1", "rise-price": "2", "fall-rate": "3",
    "fall-price": "4", "volume": "5", "amount": "6", "days-left": "7",
}

# ka30009(ELW등락율순위) 전용 — sort_tp(정렬구분, 1:상승률,2:상승폭,
# 3:하락률,4:하락폭). RANK_CHANGE_SORT(ka10027)/AFTERHOURS_CHANGE_SORT
# (ka10098)의 진짜 부분집합이다(둘 다 flat:5가 더 있음, superset-closure
# 스크립트로 확인) — 절대 그쪽 상수를 여기 재사용하지 말 것("flat" 이름은
# ka30009에서 거부돼야 한다). 1곳: ka30009.
ELW_CHANGE_RANK_SORT = {
    "rise-rate": "1", "rise-price": "2", "fall-rate": "3", "fall-price": "4",
}

# ka30009/ka30010(ELW등락율순위/ELW잔량순위) 공용 — rght_tp(권리구분,
# 3자리 zero-pad, EX가 빠진 7개 값). ELW_RIGHT_TYPE_3DIGIT 참고(짝 — 그쪽의
# 진짜 부분집합, 절대 합치지 말 것).
#
# *** 이 상수는 api_id 2개가 공유한다. 한쪽 스펙만 바뀌면 이 상수를 제자리
# 에서 고치지 말고 분리할 것. ***
ELW_RANK_RIGHT_TYPE_3DIGIT = {
    "all": "000", "call": "001", "put": "002", "dc": "003", "dp": "004",
    "early-call": "006", "early-put": "007",
}

# ka30010(ELW잔량순위) 전용 — sort_tp(정렬구분, 1:순매수잔량상위,
# 2:순매도잔량상위). 값은 ORDERBOOK_SURGE_SIDE(ka10021, trde_tp)와 완전히
# 동일하다(구분 불가 쌍) — 필드명·api_id가 달라 이름은 분리 유지.
# 1곳: ka30010.
ELW_BALANCE_RANK_SORT = {"buy-balance": "1", "sell-balance": "2"}

# ka30001/ka30002/ka30004/ka30005의 isscomp_cd(발행사코드)/bsis_aset_cd
# (기초자산코드)/lpcd(LP코드)는 스펙에 예시 5~6개 발행사/지수만 있고 전체
# 코드표가 없는 개방형 목록이다(사실상 종목/지수 코드 조회 필드) — kwcli도
# 값 매핑 없이 자유 코드로 둔다. 미확인이라 이번 태스크에서 전환하지 않는다.

# ── ka50079/ka50081/ka50082/ka50083(market gold 틱·일·주·월봉차트)
# HumanChoice 전환 (Task 33) ─────────────────────────────────────────
#
# upd_stkpc_tp(수정주가구분, 0 or 1) — 4개 API가 공유한다. ka50080(분봉
# 차트)도 같은 필드·값이지만 스펙상 Required=N이고 기존 기본값이 빈 문자열
# ""이다(Required=Y인 나머지 4개는 기본값이 "0") — HumanChoice 매핑에 ""이
# 없어 그대로 감싸면 기본 호출이 BadParameter로 깨지고, 억지로 기본값을
# "0"/"1"로 바꾸면 전송 바이트가 바뀐다(빈 문자열은 스펙상 합법적인 "생략"
# 값이라 다른 태스크에서 나온 zero-pad 결함과 달리 교정 대상이 아니다).
# 그래서 ka50080의 --price-type만 이번 태스크에서 raw 텍스트로 남긴다
# (market.py, ka50080 참고). ka50091/ka50092/ka50101의 tic_scope는 값과 라벨이
# 동일한 자기서술적 수량 프리셋이라 애초에 전환 대상이 아니다(브리프 판정
# "수량").
#
# *** 이 상수는 api_id 4개가 공유한다(ka50079/81/82/83). ka50080은 위 이유로
# 제외. 한쪽 스펙만 바뀌면 이 상수를 제자리에서 고치지 말고 분리할 것. ***
#
# CHART_ADJUSTED_PRICE(stock.py chart 서브그룹, ka10079/80/81/82/83/94, Task
# 34b)와 값이 완전히 동일하다({raw:0, adjusted:1}) — 구분 불가 클러스터.
# 금현물(gold)과 국내주식(stock) chart는 별개 상품군이라 절대 합치지 말 것.
GOLD_PRICE_TYPE = {"raw": "0", "adjusted": "1"}

# ── ka10086/ka10084/ka10055/ka10025/ka10028/ka10052/ka10054/ka10011/
# ka10044/ka10045/ka10058/ka10059/ka10061(stock 일별주가~투자자별매매,
# 거래원·VI·신주인수권) HumanChoice 전환 (Task 34a) ──────────────────────
#
# ka10063(intraday)/ka10066(after-close)/ka10131(consecutive)/ka10043
# (trader-analysis)/kt20016(credit-available)은 이번 태스크 이전에 이미
# 전환돼 있었다(선행 fix 커밋들) — 손대지 않는다. ka10043의 --days(dt)는
# 한 차례 raw 텍스트로 되돌렸다가 리뷰에서 HumanChoice로 원복했고,
# market.py의 ka10042(net-buyer --period)도 같은 상수를 공유하도록 함께
# 전환했다 — TRADER_ANALYSIS_PERIOD_5_120은 **제거되지 않았고 지금 두 곳이
# 쓰고 있다**(정의부 주석 참고).

# ka10086(일별주가) 전용 — indc_tp(표시구분, 0:수량,1:금액). AMT_QTY_TP_0_1
# (0:금액,1:수량)과 키 집합(quantity/amount)은 같지만 극성이 정확히
# **반대**다 — 절대 합치지 말 것. 1곳: ka10086.
DAILY_PRICE_DISPLAY = {"quantity": "0", "amount": "1"}

# ka10084(당일전일체결)/ka10055(당일전일체결량) 공용 — tdy_pred(당일전일,
# 1:당일,2:전일). 두 시트 모두 워크북에서 character-for-character 동일함을
# 확인했다(ka10084 "당일:1, 전일:2", ka10055 "1:당일, 2:전일"). 다른
# today/previous 계열 상수(PERIOD_TODAY_PREV_5_60, TRADER_ANALYSIS_POSITION,
# FOREIGN_CONSECUTIVE_BASE_DATE — 전부 today:0/previous:1)와는 극성이
# 반대이니 절대 합치지 말 것.
#
# *** 이 상수는 api_id 2개가 공유한다(ka10084/ka10055). 한쪽 스펙만 바뀌면
# 이 상수를 제자리에서 고치지 말고 분리할 것. ***
TODAY_PREV_1_2 = {"today": "1", "previous": "2"}

# ka10084(당일전일체결) 전용 — tic_min(틱분, 0:틱,1:분). MIN_TIC_TP
# (ka90005/ka90010, 필드명 min_tic_tp)과 값은 같으나 필드명 자체가 다르고
# api_id도 다르다 — 절대 합치지 말 것. 1곳: ka10084.
TODAY_EXEC_TIC_MIN = {"tick": "0", "minute": "1"}

# ka10025(매물대집중) 전용 — cur_prc_entry(현재가진입, 0:미포함,1:포함).
# CHECK_YES_1_NO_0(ka10063 전용, 재사용 금지 예약됨)과 값은 같으나 그
# 상수의 주석이 이 필드를 명시적으로 예약 제외해 뒀다 — 별도 이름을 쓴다.
# 1곳: ka10025.
PRICE_CLUSTER_CUR_PRC_ENTRY = {"yes": "1", "no": "0"}

# ka10028(시가대비등락률) 전용 — sort_tp(정렬구분, 1:시가,2:고가,3:저가,
# 4:기준가). 다른 sort_tp/sort 계열(market.py 20여 곳, 값이 API마다 전부
# 다름)과 값 집합이 겹치지 않지만 그래도 API별 분리 원칙을 따른다.
# 1곳: ka10028.
OPEN_CHANGE_SORT = {"open": "1", "high": "2", "low": "3", "base": "4"}

# ka10028(시가대비등락률) 전용 — trde_qty_cnd(거래량조건, 4자리 zero-pad,
# 6개 값). **와이어 값 결함 수정**: 기존 기본값 raw "0"은 4자리 스펙
# 어디에도 없는 값이었다("0000"이 전체조회). HumanChoice 전환과 함께
# 기본값을 "0000"으로 교정했다 — 이 자리는 표기 전환이 아니라 전송
# 바이트가 바뀌는 fix다(CHANGELOG 기재 대상). RANK_CHANGE_QTY_CND
# (ka10027, 9개 값)와 값 집합이 달라 절대 합치지 말 것. 1곳: ka10028.
OPEN_CHANGE_QTY_CND = {
    "all": "0000", "10k": "0010", "50k": "0050",
    "100k": "0100", "500k": "0500", "1000k": "1000",
}

# ka10028(시가대비등락률) 전용 — updown_incls(상하한포함, 0:미포함,
# 1:포함). CHECK_YES_1_NO_0 재사용 금지(그 상수 주석에 이 필드가 명시적
# 예약 제외돼 있음) — 별도 이름을 쓴다. 1곳: ka10028.
OPEN_CHANGE_INCLUDE_LIMIT = {"yes": "1", "no": "0"}

# ka10028(시가대비등락률) 전용 — stk_cnd(종목조건, 9개 값). 전환 전 자유
# 텍스트였다 — HumanChoice 전환은 breaking(제약 8). RANK_CHANGE_STK_CND
# (ka10027)/EXPECTED_CHANGE_STK_CND(ka10029)/AFTERHOURS_CHANGE_STK_CND
# (ka10098, 전부 15~16개 값)의 진짜 부분집합이다(superset-closure 스크립트로
# 확인) — 절대 그쪽 상수를 여기 재사용하지 말 것("exclude-liquidation"/
# "only-margin-50"/"only-margin-60"/"exclude-etf"/"exclude-spac"/
# "exclude-etf-etn" 이름은 ka10028에서 거부돼야 한다). 1곳: ka10028.
OPEN_CHANGE_STK_CND = {
    "all": "0", "exclude-managed": "1", "exclude-preferred": "3",
    "exclude-managed-preferred": "4", "exclude-margin-100": "5",
    "only-margin-100": "6", "only-margin-40": "7", "only-margin-30": "8",
    "only-margin-20": "9",
}

# ka10028(시가대비등락률) 전용 — crd_cnd(신용조건, 7개 값). 전환 전 자유
# 텍스트였다 — breaking(제약 8). NEW_HIGH_LOW_CREDIT_CND 등 7값짜리
# crd_cnd 클러스터와 값이 완전히 동일하다(구분 불가). EXPECTED_CHANGE_CREDIT_CND
# (ka10029)/AFTERHOURS_CHANGE_CREDIT_CND(ka10098, 9개 값)의 진짜 부분집합
# 이기도 하니 그쪽과 절대 합치지 말 것. 1곳: ka10028.
OPEN_CHANGE_CREDIT_CND = {
    "all": "0", "a": "1", "b": "2", "c": "3", "d": "4", "e": "7", "all-financing": "9",
}

# ka10028(시가대비등락률) 전용 — trde_prica_cnd(거래대금조건, 12개 값).
# 전환 전 자유 텍스트였다 — breaking(제약 8). RANK_CHANGE_AMOUNT_CND
# (ka10027, trde_prica_cnd 필드)와 값이 완전히 동일하다(구분 불가 쌍,
# superset-closure 스크립트로 확인). **극성 해저드**: VOLUME_RANK_AMOUNT_TYPE
# (ka10030)의 키 집합을 진짜 포함하지만 "50m" 값이 다르다(여기 5 vs
# 거기 4) — 절대 그쪽과 합치지 말 것, "50m"은 반드시 리터럴로 핀 고정.
# 1곳: ka10028.
OPEN_CHANGE_AMOUNT_CND = {
    "all": "0", "30m": "3", "50m": "5", "100m": "10", "300m": "30",
    "500m": "50", "1b": "100", "3b": "300", "5b": "500", "10b": "1000",
    "30b": "3000", "50b": "5000",
}

# ka10028(시가대비등락률) 전용 — flu_cnd(등락조건, 1:상위,2:하위).
# 1곳: ka10028.
OPEN_CHANGE_DIRECTION = {"top": "1", "bottom": "2"}

# ka10052(거래원순간거래량) 전용 — mrkt_tp(시장구분, 0:전체,1:코스피,
# 2:코스닥,3:종목). 표준 MARKET_ALL(000/001/101)과도, sector 계열의
# 0/1/2(코스피/코스닥/코스피200)와도 값 순서 자체가 달라 절대 재사용
# 금지 — mrkt_tp의 4번째 서로 다른 코드북(브리프 해저드 표 참고).
# 1곳: ka10052.
INSTANT_VOLUME_MARKET = {"all": "0", "kospi": "1", "kosdaq": "2", "stock": "3"}

# ka10052(거래원순간거래량) 전용 — qty_tp(수량구분). 스펙 코드 3, 5는
# 워크북·kwcli 모두 라벨이 비어 있다(추측 금지) — 매핑에서 제외하고
# raw 텍스트로 남긴다(별도 상수 없음, stock.py 참고).

# ka10052(거래원순간거래량) 전용 — pric_tp(가격구분, 7개 값, 전부
# 라벨 있음). 전환 전 자유 텍스트였다 — breaking(제약 8). 1곳: ka10052.
INSTANT_VOLUME_PRICE_TYPE = {
    "all": "0", "under-1k": "1", "over-1k": "8", "1k-2k": "2",
    "2k-5k": "3", "5k-10k": "4", "over-10k": "5",
}

# ka10054(VI발동종목) 전용 — bf_mkrt_tp(장전구분, 0:전체,1:정규시장,
# 2:시간외단일가). 1곳: ka10054.
VI_TRIGGER_SESSION = {"all": "0", "regular": "1", "after-hours": "2"}

# ka10054(VI발동종목) 전용 — motn_tp(발동구분, 0:전체,1:정적VI,2:동적VI,
# 3:동적+정적). 1곳: ka10054.
VI_TRIGGER_TYPE = {"all": "0", "static": "1", "dynamic": "2", "both": "3"}

# ka10054(VI발동종목) 전용 — skip_stk(제외종목)는 9자리 비트마스크다(자리별
# 우선주/관리종목/투자경고·위험/투자주의/환기종목/단기과열종목/증거금100%/
# ETF/ETN, 자리별 0=포함,1=제외) — 단일 dict 매핑 불가. kwcli도 값 매핑
# 없는 자유 문자열로 둔다. raw 텍스트로 남긴다(별도 상수 없음).

# ka10054(VI발동종목) 전용 — trde_qty_tp(거래량구분)/trde_prica_tp
# (거래대금구분) 공용. 둘 다 스펙상 0:사용안함,1:사용인 동일 코드북
# (같은 api_id 안에서 의미가 같은 필터-사용여부 플래그). 전환 전 둘 다
# 자유 텍스트였다 — breaking(제약 8). CHECK_YES_1_NO_0 재사용 금지(그
# 상수 주석 참고, ka10063 전용으로 예약됨) — 별도 이름을 쓴다.
# 1곳(2개 필드): ka10054.
VI_TRIGGER_USE_FILTER = {"yes": "1", "no": "0"}

# ka10054(VI발동종목) 전용 — motn_drc(발동방향, 0:전체,1:상승,2:하락).
# 1곳: ka10054.
VI_TRIGGER_DIRECTION = {"all": "0", "rise": "1", "fall": "2"}

# ka10011(신주인수권전체시세) 전용 — newstk_recvrht_tp(신주인수권구분,
# 00:전체,05:신주인수권증권,07:신주인수권증서). 1곳: ka10011.
WARRANT_TYPE = {"all": "00", "warrant-security": "05", "warrant-certificate": "07"}

# ka10044(일별기관매매종목) 전용 — trde_tp(매매구분, 1:순매도,2:순매수).
# 그룹②(net-sell:1,net-buy:2) 극성 — FOREIGN_CONSECUTIVE_SIDE(ka10035)와
# 값이 완전히 동일하다(구분 불가 쌍). FOREIGN_PERIOD_SIDE(ka10034,
# net-trade:3 추가)의 진짜 부분집합이기도 하니 그쪽과 절대 합치지 말 것
# ("net-trade" 이름은 ka10044에서 거부돼야 한다). 브리프의 공용 이름
# `TRDE_TP_NET_SELL_FIRST` 제안은 그룹②/③을 뒤섞을 위험이 있어 채택하지
# 않고 API별 전용 이름을 쓴다(브리프 merge-hazard 절 참고). 1곳: ka10044.
INVESTOR_DAILY_TRADE_SIDE = {"net-sell": "1", "net-buy": "2"}

# ka10045(종목별기관매매추이) 전용 — orgn_prsm_unp_tp(기관추정단가구분)/
# for_prsm_unp_tp(외인추정단가구분) 공용. 둘 다 스펙상 1:매수단가,
# 2:매도단가인 동일 코드북(같은 api_id 안에서 의미가 같은 추정단가
# 기준 필드). 1곳(2개 필드): ka10045.
INST_FOREIGN_PRICE_TYPE = {"buy": "1", "sell": "2"}

# ka10058(투자자별일별매매종목) 전용 — trde_tp(매매구분, 순매도:1,
# 순매수:2). 그룹② 극성 — INVESTOR_DAILY_TRADE_SIDE(ka10044)/
# FOREIGN_CONSECUTIVE_SIDE(ka10035)와 값이 완전히 동일하다(구분 불가
# 클러스터). FOREIGN_PERIOD_SIDE(ka10034)의 진짜 부분집합이기도 하니
# 절대 합치지 말 것. 1곳: ka10058.
DAILY_BY_INVESTOR_TRADE_SIDE = {"net-sell": "1", "net-buy": "2"}

# ka10058(투자자별일별매매종목) 전용 — invsr_tp(투자자구분, 12개 값,
# 4자리). 전환 전 자유 텍스트였다 — breaking(제약 8). INVESTOR_TOP_ORGN
# (ka10065, 11개 값)과 겹치는 키(foreign/financial-investment/
# investment-trust/other-financial/bank/insurance/pension/state/
# other-corporate/institution 10개)는 값이 전부 동일하지만, 이 상수만
# individual(8000)/private-fund(3100)이 있고 저쪽만 foreign-broker(9100)가
# 있어 어느 쪽도 다른 쪽의 진짜 부분집합이 아니다(키 집합이 서로 다름) —
# 그래도 "투자자구분 3계통" 해저드(브리프 참고, invsr_tp/invsr_tp/invsr는
# 와이어 코드가 API마다 다름)에 해당하니 절대 합치지 말 것. 1곳: ka10058.
DAILY_BY_INVESTOR_TYPE = {
    "individual": "8000", "foreign": "9000", "financial-investment": "1000",
    "investment-trust": "3000", "private-fund": "3100", "other-financial": "5000",
    "bank": "4000", "insurance": "2000", "pension": "6000", "state": "7000",
    "other-corporate": "7100", "institution": "9999",
}

# ka10059(종목별투자자기관별)/ka10061(종목별투자자기관별합계)/ka10060(chart
# investor, Task 34b에서 워크북 확인 후 추가) 공용 — unit_tp(단위구분,
# 1000:천주,1:단주). 세 시트 모두 워크북에서 character-for-character
# 동일함을 확인했다. SAME_NET_TRADE_UNIT(ka10062, 값은 같으나 필드명·
# api_id가 다름)과는 절대 합치지 말 것.
#
# *** 이 상수는 api_id 3개가 공유한다(ka10059/ka10061/ka10060). 한쪽
# 스펙만 바뀌면 이 상수를 제자리에서 고치지 말고 분리할 것 — 제자리 수정은
# 나머지 둘을 조용히 함께 오염시킨다. ***
INVESTOR_BY_STOCK_UNIT = {"thousand": "1000", "share": "1"}

# ka10061(종목별투자자기관별합계) 전용 — trde_tp(매매구분). 스펙에는
# "0:순매수" 단일값만 있는데 기존 코드는 click.Choice(["0","1","2"])로
# 스펙에 없는 1/2까지 받고 있었다 — HumanChoice({"net-buy":"0"})로 좁히면
# 그 두 값이 거부된다. 이미 click.Choice였던 자리가 값 집합이 줄어드는
# 경우라 breaking이다(제약 8 마지막 문단). 1곳: ka10061.
BY_STOCK_TOTAL_TRADE_SIDE = {"net-buy": "0"}

# ka10059(종목별투자자기관별)/ka10061(종목별투자자기관별합계) amt_qty_tp
# (금액수량구분, 1:금액,2:수량)/ka10059 trde_tp(매매구분, 0:순매수,1:매수,
# 2:매도)는 AMT_QTY_TP_1_2/TRDE_TP_NET_BUY_BUY_SELL을 공유한다(위
# 두 상수의 커플링 주석에 이미 두 api_id가 예약돼 있었다) — 별도 상수를
# 만들지 않는다. AMT_QTY_TP_1_2는 이제 9곳(기존 7 + ka10059/ka10061)이
# 공유한다(Task 34b가 여기에 ka90003/ka10060/ka10064 세 곳을 추가로 얹어
# 12곳이 됐다 — 위 AMT_QTY_TP_1_2 정의부 커플링 주석 참고).

# ── Task 34b — stock program_top/chart_*/lending HumanChoice 전환 ──────

# ka90003(프로그램순매수상위50) 전용 — trde_upper_tp(매매상위구분,
# 1:순매도상위, 2:순매수상위). 값 집합이 BROKER_BY_STOCK_SIDE(ka10038)/
# FOREIGN_CONSECUTIVE_SIDE(ka10035)/INVESTOR_DAILY_TRADE_SIDE(ka10044)/
# DAILY_BY_INVESTOR_TRADE_SIDE(ka10058)와 완전히 동일해 어떤 테스트로도
# 구분할 수 없다(구분 불가 클러스터) — 그래도 필드명(trde_upper_tp vs
# qry_tp/dt/trde_tp)과 api_id가 전부 다른 별개 개념이니 절대 합치지 말 것.
# ELW_BROKER_SIDE(ka30002, {net-buy:1,net-sell:2})/FOREIGN_BROKER_SIDE
# (ka10039)/BROKER_TOP_SIDE(ka10039 다른 필드)/SAME_NET_TRADE_SIDE(ka10062)/
# INVESTOR_TOP_SIDE(ka10065)와는 키 집합은 같고 값이 정반대(극성 해저드,
# 클로저 스크립트로 5개 전부 확인) — 기본값이 아닌 이름까지 wire 값을
# 리터럴로 고정하는 테스트로 방어한다(하나를 고정하면 나머지 넷도 같은
# 극성 검사로 함께 막힌다). PROGRAM_TOP_SIDE는 FOREIGN_PERIOD_SIDE(ka10034,
# {net-sell:1,net-buy:2,net-trade:3})의 진짜 부분집합이기도 하다 — "net-trade"
# 거부 테스트로 방어. 1곳: ka90003(옵션명 --trade 유지).
PROGRAM_TOP_SIDE = {"net-sell": "1", "net-buy": "2"}

# ka10079(틱차트)/ka10080(분봉차트)/ka10081(일봉차트)/ka10082(주봉차트)/
# ka10083(월봉차트)/ka10094(년봉차트) 공용 — upd_stkpc_tp(수정주가구분,
# 0 or 1). 여섯 시트의 **값 대응**이 동일한 2-값 코드북이라 하나로
# 공유한다(31b가 ka10034/36/37의 dt를 공유했던 것과 같은 패턴). Description
# 문구까지 같지는 않다 — 다섯 시트는 "0 or 1" 여섯 글자뿐이지만 ka10081만
# 같은 칸에 수정주가 적용 방법을 설명하는 문단이 이어져 370자다(삼성전자
# 액면분할 예시로 "1"=수정주가적용, 미기재(0)=미적용임을 설명한다). 종전
# 이 자리에는 여섯 시트가 "character-for-character 동일"하다고 적혀 있었으나
# 사실이 아니다. 값 대응이 같으므로 공유 자체는 여전히 정당하다.
#
# *** 이 상수는 국내 api_id 6개가 공유하고, 거기에 더해 미국주식 차트
# usa06010~usa06015에도 도달한다. `stock chart day --exchange amex`처럼
# 미국으로 라우팅되면 이 매핑을 거친 upd_stkpc_tp가 usa06012로 전송된다
# (us/stock_ops.chart 참고). 미국 스펙에서도 0/1이 합법이라 현재 전송
# 바이트에는 문제가 없지만, 이 상수를 고칠 때 확인해야 할 사이트는
# 6개가 아니라 6개 + usa06010~15다. 한쪽 스펙만 바뀌면 이 상수를 제자리
# 에서 고치지 말고 분리할 것 — 제자리 수정은 나머지 전부를 조용히 함께
# 오염시킨다. ***
#
# GOLD_PRICE_TYPE(market.py gold 틱·일·주·월봉차트, ka50079/81/82/83)과
# 값이 완전히 동일하다({raw:0, adjusted:1}) — 구분 불가 클러스터. 금현물과
# 국내주식은 별개 상품군이라 절대 합치지 말 것.
CHART_ADJUSTED_PRICE = {"raw": "0", "adjusted": "1"}

# ── Task 36 — account.py 거래소 구분 (dmst_stex_tp) ─────────────────
#
# 사용자 결정 E-1: 계획서 원문은 {"all":"%","KRX":"1",...}처럼 전송값
# 자체를 숫자코드로 바꾸라고 했지만, 이 필드는 현재 "%"/"KRX"/"NXT"/"SOR"
# 리터럴을 dmst_stex_tp에 그대로 전송한다. 트랜치 E는 표기만 바꾸는
# 트랜치이므로 전송값은 절대 바꾸지 않는다 — "all"만 추가하고 나머지 값은
# 그대로 둔다.
#
# kt00007(orders_detail)/kt00009(orders_status) 전용 — SOR 포함 4값.
# ACCOUNT_EXCHANGE_NO_SOR(키·값 둘 다 진부분집합, SOR 제외)과 절대 합치지
# 말 것 — kt00015는 SOR을 스펙에서 지원하지 않는다.
#
# *** 이 상수는 api_id 2개가 공유한다(kt00007/kt00009). 한쪽 스펙만 바뀌면
# 이 상수를 제자리에서 고치지 말고 분리할 것. ***
#
# 키 집합만 보면 EXCHANGE_ALL({KRX,NXT,all})/EXCHANGE_ALL_ZERO(동일 키)와
# 같아 보이지만 값 스킴이 전혀 다르다(저 둘은 숫자코드 "1"/"2"/"3"·"0",
# 여기는 리터럴 "KRX"/"NXT"/"%") — 극성/스킴이 달라 절대 합치지 말 것.
ACCOUNT_EXCHANGE_WITH_SOR = {"all": "%", "KRX": "KRX", "NXT": "NXT", "SOR": "SOR"}

# kt00015(history_transactions) 전용 — SOR 없음 3값. ACCOUNT_EXCHANGE_WITH_SOR의
# 진짜 부분집합이지만 kt00015 스펙에 SOR이 없으므로 절대 합치지 말 것 —
# 합치면 kt00015가 스펙에 없는 SOR을 받아들이게 된다. 키 집합이
# EXCHANGE_ALL/EXCHANGE_ALL_ZERO와 같아 보이는 함정도 위 WITH_SOR 주석과
# 동일하게 적용된다(값 스킴이 다름, 절대 합치지 말 것).
ACCOUNT_EXCHANGE_NO_SOR = {"all": "%", "KRX": "KRX", "NXT": "NXT"}
