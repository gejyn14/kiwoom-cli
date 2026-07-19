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
# (docs/superpowers/plans/2026-07-18-humanreadable-inventory.md 참고)
TRDE_TP_NET_BUY_BUY_SELL = {"net-buy": "0", "buy": "1", "sell": "2"}

# amt_qty_tp(금액수량구분)도 API마다 극성이 다르다(표준 1:금액,2:수량 vs
# ka10051/ka10131의 0:금액,1:수량) — 그런데 두 코드북의 키 집합(amount/
# quantity)이 완전히 같아서, trde_tp와 달리 이름만 봐서는 극성을 구분할
# 수 없다. 그래서 이름 자체에 코드 값을 새긴다: 이 상수는 1:금액,2:수량
# 전용(13곳, ka10066 포함)이며, 0:금액,1:수량 짝은 별도로
# `AMT_QTY_TP_0_1`이라는 이름을 예약해 둔다(ka10051/ka10131 이관 시 이
# 이름으로 추가할 것 — 절대 이 상수를 재사용하지 말 것). 두 코드북 및
# 다른 amt_qty_tp 변형 전체 목록은
# docs/superpowers/plans/2026-07-18-humanreadable-inventory.md의 "절대
# 합치면 안 되는" 절(C4) 참고.
AMT_QTY_TP_1_2 = {"amount": "1", "quantity": "2"}
