"""코드북 상수 드리프트 테스트 (constant-drift test).

_constants.py의 코드북 상수들은 api_id마다 독립이고, 값 집합이 같아 보여도
절대 합쳐서는 안 된다(CLAUDE.md "코드북 상수는 절대 합치지 않는다"). 이
파일은 그 규칙을 **전수**로 강제한다.

세 개의 클로저 술어(closure predicate)로 위험 쌍을 분류한다. 술어 1·2는
이전 태스크들이 애드혹 스크립트로 돌리던 것이고, 술어 3은 이번(D7)에
추가됐다. 세 술어 모두 **양방향**으로 계산한다 — A⊂B와 B⊂A는 다른 질문이다.

  (1) strict (key,value) subset : A의 모든 항목이 B에 있고 A != B
        -> 순서 있음. 순서쌍 118개(전부 단방향, 양방향 0 — 정의상 불가능).
           비순서쌍으로는 118쌍.
  (2) keys(A) ⊆ keys(B) 인데 공유 키의 값이 다름 (극성 뒤집힘)
        -> 순서 있음. 순서쌍 202개 = 단방향 110 + 양방향 46쌍.
           비순서쌍으로는 156쌍. 양방향 46쌍은 키 집합이 완전히 같고 값만
           다른 순수 극성 해저드다.
  (3) 부분 겹침 + **양쪽 모두** 배타 키를 가짐, 공유 키 3개 이상,
      공유 키의 값이 전부 일치 (= 합쳐도 기존 값이 하나도 안 변해서
      값 고정 테스트로는 절대 안 잡히는 완전 무성(silent) 병합)
        -> 대칭. 78쌍. 78쌍 전부 양쪽이 실제 커맨드에 배선돼 있다.

**해저드 쌍 총계는 352다** (비순서쌍 기준: 118 ∪ 156 ∪ 78, 세 집합은 실제로
서로소라 합집합이 단순 합과 같다. 값이 원래 동일한 120쌍은 애초에 어느
술어에도 걸리지 않으므로 따로 뺄 것이 없다). D7 리포트와 이 파일이 여러 번
적었던 "356"은 근거 없는 숫자였다 — CLAUDE.md가 경고하는 정밀 과장 부류다.

술어 3은 이전 세션이 "인스턴스가 하나뿐"이라며 미뤘던 것인데, 그 수치는
찾아보지 않아서 생긴 착시였다. 실제로는 78쌍이고, 가장 조밀한 쌍은
RANK_CHANGE_STK_CND <-> STOCK_CONDITION (공유 14키 전부 값 일치, 배타 키
각각 1개)다.

── 이 파일이 실제로 막는 것과 막지 못하는 것 ──────────────────────────
**양쪽을 합치는(union) 병합**(A와 B를 둘 다 합집합으로 바꾸는 것)은 두 상수를
서로 같게 만들므로 test_no_codebook_constants_are_accidentally_merged 하나가
352쌍 전부를 잡는다. 476개 병합을 전부 수행해 확인했다(mutation sweep,
EXCHANGE_TWO 제거 전 173개 기준): 술어 1에서 25쌍, 술어 2에서 9쌍, 술어 3에서
20쌍, 합계 54쌍이 다른 테스트를 전부 통과해 **조용히** 지나갔고 그 54쌍을
이 불변식이 잡는다.

**단, "어떤 병합이든 두 상수가 같아진다"는 참이 아니다.** 한쪽만 넓히는
경우(`A = {**A, **B}` — "빠진 키만 A에 채워 넣자"는 자연스러운 수정)는 A가
B와 같아지지 않으므로 동치 불변식에 걸리지 않는다. 실측: 그런 한쪽 확장 중
**12쌍**은 이 파일의 세 테스트를 **전부** 통과한다.

    ACCOUNT_EXCHANGE_WITH_SOR |= EXCHANGE_ALL / EXCHANGE_ALL_ZERO
    INSTANT_VOLUME_MARKET     |= CREDIT_MARKET / MARKET_KOSPI_KOSDAQ
                                 / MARKET_PROGRAM / MARKET_TWO
    MARKET_ALL                |= MARKET_KOSPI_KOSDAQ / MARKET_PROGRAM
    MARKET_STATUS_KOSPI       |= MARKET_KOSPI_KOSDAQ / MARKET_PROGRAM / MARKET_TWO
    TRDE_TP_NET_BUY_BUY_SELL  |= NETSLMT_TP_NET_BUY_ONLY

첫 번째는 계좌 거래소 값을 KRX/NXT/% 체계에서 1/2/3 체계로 갈아치우는, 실제로
위험한 변형이다. **12쌍 전부 스위트 전체로는 잡힌다** — 12개를 하나씩 심어
전부 확인했고, 각각 다른 파일의 값 고정 테스트가 2~8건씩 실패한다. 즉 지금
구멍은 없다. 다만 그 방어는 이 파일 혼자가 아니라 (a) 동치 불변식,
(b) `vanished` 검사, (c) 고정된 술어 3 인벤토리, (d) 다른 파일의 전송 body
값 고정이 **함께** 만들어낸다. 이 파일 하나가 다 막는다고 읽지 말 것.

값이 원래부터 완전히 동일한 120쌍은 원리상 어떤 테스트로도 구분할 수
없다(합쳐도 아무 값이 안 바뀐다). 그래서 억지 테스트를 만들지 않고
아래 allowlist에 명시적으로 등록해 이름 규약에만 맡긴다 — 대신 목록에
없는 새 동치 쌍이 생기면 즉시 실패한다.
"""

from __future__ import annotations

import itertools

from kiwoom_cli.commands import _constants


def _codebook_mappings() -> dict[str, dict[str, str]]:
    """_constants.py의 문자열->문자열 코드북 매핑 전부."""
    return {
        name: value
        for name in dir(_constants)
        if not name.startswith("_")
        and isinstance(value := getattr(_constants, name), dict)
        and value
        and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
    }


_KNOWN_IDENTICAL_PAIRS = frozenset({
    ("AFTERHOURS_CHANGE_CREDIT_CND", "EXPECTED_CHANGE_CREDIT_CND"),
    ("AFTERHOURS_CHANGE_SORT", "RANK_CHANGE_SORT"),
    ("ALL_STOCK_QRY", "PRODUCT_TYPE"),
    ("AMT_QTY_TP_1_2", "FOREIGN_BROKER_SORT"),
    ("BALANCE_RATE_STK_CND", "CREDIT_RATIO_STK_CND"),
    ("BALANCE_RATE_STK_CND", "ORDERBOOK_SURGE_STK_CND"),
    ("BALANCE_RATE_STK_CND", "ORDERBOOK_TOP_STK_CND"),
    ("BROKER_BY_STOCK_SIDE", "DAILY_BY_INVESTOR_TRADE_SIDE"),
    ("BROKER_BY_STOCK_SIDE", "FOREIGN_CONSECUTIVE_SIDE"),
    ("BROKER_BY_STOCK_SIDE", "INVESTOR_DAILY_TRADE_SIDE"),
    ("BROKER_BY_STOCK_SIDE", "PROGRAM_TOP_SIDE"),
    ("BROKER_TOP_QTY_TYPE", "ELW_BROKER_QTY_TYPE"),
    ("BROKER_TOP_SIDE", "ELW_BROKER_SIDE"),
    ("BROKER_TOP_SIDE", "INVESTOR_TOP_SIDE"),
    ("BROKER_TOP_SIDE", "SAME_NET_TRADE_SIDE"),
    ("CHART_ADJUSTED_PRICE", "GOLD_PRICE_TYPE"),
    ("CHECK_YES_1_NO_0", "CREDIT_RATIO_INCLUDE_LIMIT"),
    ("CHECK_YES_1_NO_0", "FOREIGN_INST_DATE_INCLUDE"),
    ("CHECK_YES_1_NO_0", "MANAGED_STOCK_INCLUDE"),
    ("CHECK_YES_1_NO_0", "NEW_HIGH_LOW_INCLUDE_LIMIT"),
    ("CHECK_YES_1_NO_0", "OPEN_CHANGE_INCLUDE_LIMIT"),
    ("CHECK_YES_1_NO_0", "PRICE_CLUSTER_CUR_PRC_ENTRY"),
    ("CHECK_YES_1_NO_0", "RANK_CHANGE_INCLUDE_LIMIT"),
    ("CHECK_YES_1_NO_0", "SURGE_INCLUDE_LIMIT"),
    ("CHECK_YES_1_NO_0", "VI_TRIGGER_USE_FILTER"),
    ("CREDIT_RATIO_CREDIT_CND", "LIMIT_MOVE_CREDIT_CND"),
    ("CREDIT_RATIO_CREDIT_CND", "NEAR_HIGHLOW_CREDIT_CND"),
    ("CREDIT_RATIO_CREDIT_CND", "NEW_HIGH_LOW_CREDIT_CND"),
    ("CREDIT_RATIO_CREDIT_CND", "OPEN_CHANGE_CREDIT_CND"),
    ("CREDIT_RATIO_CREDIT_CND", "ORDERBOOK_TOP_CREDIT_CND"),
    ("CREDIT_RATIO_CREDIT_CND", "RANK_CHANGE_CREDIT_CND"),
    ("CREDIT_RATIO_CREDIT_CND", "SURGE_CREDIT_CND"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "FOREIGN_INST_DATE_INCLUDE"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "MANAGED_STOCK_INCLUDE"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "NEW_HIGH_LOW_INCLUDE_LIMIT"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "OPEN_CHANGE_INCLUDE_LIMIT"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "PRICE_CLUSTER_CUR_PRC_ENTRY"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "RANK_CHANGE_INCLUDE_LIMIT"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "SURGE_INCLUDE_LIMIT"),
    ("CREDIT_RATIO_INCLUDE_LIMIT", "VI_TRIGGER_USE_FILTER"),
    ("CREDIT_RATIO_STK_CND", "ORDERBOOK_SURGE_STK_CND"),
    ("CREDIT_RATIO_STK_CND", "ORDERBOOK_TOP_STK_CND"),
    ("DAILY_BY_INVESTOR_TRADE_SIDE", "FOREIGN_CONSECUTIVE_SIDE"),
    ("DAILY_BY_INVESTOR_TRADE_SIDE", "INVESTOR_DAILY_TRADE_SIDE"),
    ("DAILY_BY_INVESTOR_TRADE_SIDE", "PROGRAM_TOP_SIDE"),
    ("ELW_BALANCE_RANK_SORT", "ORDERBOOK_SURGE_SIDE"),
    ("ELW_BROKER_SIDE", "INVESTOR_TOP_SIDE"),
    ("ELW_BROKER_SIDE", "SAME_NET_TRADE_SIDE"),
    ("ELW_SURGE_DIRECTION", "SURGE_DIRECTION"),
    ("ELW_SURGE_TIME_UNIT", "SURGE_TIME_UNIT"),
    ("EXPECTED_CHANGE_PRICE_CND", "RANK_CHANGE_PRICE_CND"),
    ("EXPECTED_CHANGE_STK_CND", "RANK_CHANGE_STK_CND"),
    ("FOREIGN_CONSECUTIVE_BASE_DATE", "TRADER_ANALYSIS_POSITION"),
    ("FOREIGN_CONSECUTIVE_SIDE", "INVESTOR_DAILY_TRADE_SIDE"),
    ("FOREIGN_CONSECUTIVE_SIDE", "PROGRAM_TOP_SIDE"),
    ("FOREIGN_INST_DATE_INCLUDE", "MANAGED_STOCK_INCLUDE"),
    ("FOREIGN_INST_DATE_INCLUDE", "NEW_HIGH_LOW_INCLUDE_LIMIT"),
    ("FOREIGN_INST_DATE_INCLUDE", "OPEN_CHANGE_INCLUDE_LIMIT"),
    ("FOREIGN_INST_DATE_INCLUDE", "PRICE_CLUSTER_CUR_PRC_ENTRY"),
    ("FOREIGN_INST_DATE_INCLUDE", "RANK_CHANGE_INCLUDE_LIMIT"),
    ("FOREIGN_INST_DATE_INCLUDE", "SURGE_INCLUDE_LIMIT"),
    ("FOREIGN_INST_DATE_INCLUDE", "VI_TRIGGER_USE_FILTER"),
    ("INVESTOR_BY_STOCK_UNIT", "SAME_NET_TRADE_UNIT"),
    ("INVESTOR_DAILY_TRADE_SIDE", "PROGRAM_TOP_SIDE"),
    ("INVESTOR_TOP_SIDE", "SAME_NET_TRADE_SIDE"),
    ("LIMIT_MOVE_CREDIT_CND", "NEAR_HIGHLOW_CREDIT_CND"),
    ("LIMIT_MOVE_CREDIT_CND", "NEW_HIGH_LOW_CREDIT_CND"),
    ("LIMIT_MOVE_CREDIT_CND", "OPEN_CHANGE_CREDIT_CND"),
    ("LIMIT_MOVE_CREDIT_CND", "ORDERBOOK_TOP_CREDIT_CND"),
    ("LIMIT_MOVE_CREDIT_CND", "RANK_CHANGE_CREDIT_CND"),
    ("LIMIT_MOVE_CREDIT_CND", "SURGE_CREDIT_CND"),
    ("LIMIT_MOVE_PRICE_CND", "SURGE_PRICE_CND"),
    ("LIMIT_MOVE_QTY_TYPE_5DIGIT", "NEAR_HIGHLOW_QTY_TYPE_5DIGIT"),
    ("LIMIT_MOVE_QTY_TYPE_5DIGIT", "NEW_HIGH_LOW_QTY_TYPE_5DIGIT"),
    ("LIMIT_MOVE_QTY_TYPE_5DIGIT", "SURGE_QTY_TYPE_5DIGIT"),
    ("MANAGED_STOCK_INCLUDE", "NEW_HIGH_LOW_INCLUDE_LIMIT"),
    ("MANAGED_STOCK_INCLUDE", "OPEN_CHANGE_INCLUDE_LIMIT"),
    ("MANAGED_STOCK_INCLUDE", "PRICE_CLUSTER_CUR_PRC_ENTRY"),
    ("MANAGED_STOCK_INCLUDE", "RANK_CHANGE_INCLUDE_LIMIT"),
    ("MANAGED_STOCK_INCLUDE", "SURGE_INCLUDE_LIMIT"),
    ("MANAGED_STOCK_INCLUDE", "VI_TRIGGER_USE_FILTER"),
    ("MIN_TIC_TP", "TODAY_EXEC_TIC_MIN"),
    ("NEAR_HIGHLOW_CREDIT_CND", "NEW_HIGH_LOW_CREDIT_CND"),
    ("NEAR_HIGHLOW_CREDIT_CND", "OPEN_CHANGE_CREDIT_CND"),
    ("NEAR_HIGHLOW_CREDIT_CND", "ORDERBOOK_TOP_CREDIT_CND"),
    ("NEAR_HIGHLOW_CREDIT_CND", "RANK_CHANGE_CREDIT_CND"),
    ("NEAR_HIGHLOW_CREDIT_CND", "SURGE_CREDIT_CND"),
    ("NEAR_HIGHLOW_QTY_TYPE_5DIGIT", "NEW_HIGH_LOW_QTY_TYPE_5DIGIT"),
    ("NEAR_HIGHLOW_QTY_TYPE_5DIGIT", "SURGE_QTY_TYPE_5DIGIT"),
    ("NEAR_HIGHLOW_STK_CND", "NEW_HIGH_LOW_STK_CND"),
    ("NEAR_HIGHLOW_STK_CND", "SURGE_STK_CND"),
    ("NEW_HIGH_LOW_CREDIT_CND", "OPEN_CHANGE_CREDIT_CND"),
    ("NEW_HIGH_LOW_CREDIT_CND", "ORDERBOOK_TOP_CREDIT_CND"),
    ("NEW_HIGH_LOW_CREDIT_CND", "RANK_CHANGE_CREDIT_CND"),
    ("NEW_HIGH_LOW_CREDIT_CND", "SURGE_CREDIT_CND"),
    ("NEW_HIGH_LOW_INCLUDE_LIMIT", "OPEN_CHANGE_INCLUDE_LIMIT"),
    ("NEW_HIGH_LOW_INCLUDE_LIMIT", "PRICE_CLUSTER_CUR_PRC_ENTRY"),
    ("NEW_HIGH_LOW_INCLUDE_LIMIT", "RANK_CHANGE_INCLUDE_LIMIT"),
    ("NEW_HIGH_LOW_INCLUDE_LIMIT", "SURGE_INCLUDE_LIMIT"),
    ("NEW_HIGH_LOW_INCLUDE_LIMIT", "VI_TRIGGER_USE_FILTER"),
    ("NEW_HIGH_LOW_QTY_TYPE_5DIGIT", "SURGE_QTY_TYPE_5DIGIT"),
    ("NEW_HIGH_LOW_STK_CND", "SURGE_STK_CND"),
    ("OPEN_CHANGE_AMOUNT_CND", "RANK_CHANGE_AMOUNT_CND"),
    ("OPEN_CHANGE_CREDIT_CND", "ORDERBOOK_TOP_CREDIT_CND"),
    ("OPEN_CHANGE_CREDIT_CND", "RANK_CHANGE_CREDIT_CND"),
    ("OPEN_CHANGE_CREDIT_CND", "SURGE_CREDIT_CND"),
    ("OPEN_CHANGE_INCLUDE_LIMIT", "PRICE_CLUSTER_CUR_PRC_ENTRY"),
    ("OPEN_CHANGE_INCLUDE_LIMIT", "RANK_CHANGE_INCLUDE_LIMIT"),
    ("OPEN_CHANGE_INCLUDE_LIMIT", "SURGE_INCLUDE_LIMIT"),
    ("OPEN_CHANGE_INCLUDE_LIMIT", "VI_TRIGGER_USE_FILTER"),
    ("ORDERBOOK_SURGE_STK_CND", "ORDERBOOK_TOP_STK_CND"),
    ("ORDERBOOK_TOP_CREDIT_CND", "RANK_CHANGE_CREDIT_CND"),
    ("ORDERBOOK_TOP_CREDIT_CND", "SURGE_CREDIT_CND"),
    ("PRICE_CLUSTER_CUR_PRC_ENTRY", "RANK_CHANGE_INCLUDE_LIMIT"),
    ("PRICE_CLUSTER_CUR_PRC_ENTRY", "SURGE_INCLUDE_LIMIT"),
    ("PRICE_CLUSTER_CUR_PRC_ENTRY", "VI_TRIGGER_USE_FILTER"),
    ("RANK_CHANGE_CREDIT_CND", "SURGE_CREDIT_CND"),
    ("RANK_CHANGE_INCLUDE_LIMIT", "SURGE_INCLUDE_LIMIT"),
    ("RANK_CHANGE_INCLUDE_LIMIT", "VI_TRIGGER_USE_FILTER"),
    ("SURGE_INCLUDE_LIMIT", "VI_TRIGGER_USE_FILTER"),
})

_KNOWN_PARTIAL_OVERLAP_PAIRS = frozenset({
    ("AFTERHOURS_CHANGE_SORT", "ELW_SEARCH_SORT"),
    ("AFTERHOURS_CHANGE_STK_CND", "LIMIT_MOVE_STK_CND"),
    ("BALANCE_RATE_QTY_TYPE_BARE", "CREDIT_RATIO_QTY_TYPE"),
    ("BALANCE_RATE_QTY_TYPE_BARE", "ELW_SURGE_QTY_TYPE"),
    ("BALANCE_RATE_STK_CND", "NEAR_HIGHLOW_STK_CND"),
    ("BALANCE_RATE_STK_CND", "NEW_HIGH_LOW_STK_CND"),
    ("BALANCE_RATE_STK_CND", "STOCK_CONDITION"),
    ("BALANCE_RATE_STK_CND", "SURGE_STK_CND"),
    ("BROKER_TOP_PERIOD", "ELW_BROKER_PERIOD"),
    ("BROKER_TOP_PERIOD", "TRADER_ANALYSIS_PERIOD_5_120"),
    ("BROKER_TOP_QTY_TYPE", "CREDIT_RATIO_QTY_TYPE"),
    ("BROKER_TOP_QTY_TYPE", "ELW_SURGE_QTY_TYPE"),
    ("BROKER_TOP_QTY_TYPE", "EXPECTED_CHANGE_QTY_CND"),
    ("BROKER_TOP_QTY_TYPE", "ORDERBOOK_SURGE_QTY_TYPE_BARE"),
    ("BROKER_TOP_QTY_TYPE", "VOLUME_SURGE_QTY_TYPE_BARE"),
    ("CREDIT_RATIO_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("CREDIT_RATIO_QTY_TYPE", "ELW_BROKER_QTY_TYPE"),
    ("CREDIT_RATIO_QTY_TYPE", "EXPECTED_CHANGE_QTY_CND"),
    ("CREDIT_RATIO_QTY_TYPE", "ORDERBOOK_SURGE_QTY_TYPE_BARE"),
    ("CREDIT_RATIO_QTY_TYPE", "VOLUME_SURGE_QTY_TYPE_BARE"),
    ("CREDIT_RATIO_STK_CND", "NEAR_HIGHLOW_STK_CND"),
    ("CREDIT_RATIO_STK_CND", "NEW_HIGH_LOW_STK_CND"),
    ("CREDIT_RATIO_STK_CND", "STOCK_CONDITION"),
    ("CREDIT_RATIO_STK_CND", "SURGE_STK_CND"),
    ("DAILY_BY_INVESTOR_TYPE", "INVESTOR_TOP_ORGN"),
    ("ELW_BROKER_PERIOD", "PERIOD_TODAY_PREV_5_60"),
    ("ELW_BROKER_PERIOD", "TRADER_ANALYSIS_PERIOD_5_120"),
    ("ELW_BROKER_QTY_TYPE", "ELW_SURGE_QTY_TYPE"),
    ("ELW_BROKER_QTY_TYPE", "EXPECTED_CHANGE_QTY_CND"),
    ("ELW_BROKER_QTY_TYPE", "ORDERBOOK_SURGE_QTY_TYPE_BARE"),
    ("ELW_BROKER_QTY_TYPE", "VOLUME_SURGE_QTY_TYPE_BARE"),
    ("ELW_SEARCH_SORT", "RANK_CHANGE_SORT"),
    ("ELW_SURGE_QTY_TYPE", "EXPECTED_CHANGE_QTY_CND"),
    ("ELW_SURGE_QTY_TYPE", "ORDERBOOK_SURGE_QTY_TYPE_BARE"),
    ("ELW_SURGE_QTY_TYPE", "VOLUME_SURGE_QTY_TYPE_BARE"),
    ("EXPECTED_CHANGE_PRICE_CND", "LIMIT_MOVE_PRICE_CND"),
    ("EXPECTED_CHANGE_PRICE_CND", "SURGE_PRICE_CND"),
    ("EXPECTED_CHANGE_PRICE_CND", "VOLUME_SURGE_PRICE_TYPE"),
    ("EXPECTED_CHANGE_QTY_CND", "VOLUME_RANK_QTY_TYPE"),
    ("EXPECTED_CHANGE_QTY_CND", "VOLUME_SURGE_QTY_TYPE_BARE"),
    ("EXPECTED_CHANGE_STK_CND", "LIMIT_MOVE_STK_CND"),
    ("EXPECTED_CHANGE_STK_CND", "STOCK_CONDITION"),
    ("INSTANT_VOLUME_PRICE_TYPE", "LIMIT_MOVE_PRICE_CND"),
    ("INSTANT_VOLUME_PRICE_TYPE", "SURGE_PRICE_CND"),
    ("INSTANT_VOLUME_PRICE_TYPE", "VOLUME_SURGE_PRICE_TYPE"),
    ("LIMIT_MOVE_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("LIMIT_MOVE_PRICE_CND", "RANK_CHANGE_PRICE_CND"),
    ("LIMIT_MOVE_PRICE_CND", "VOLUME_SURGE_PRICE_TYPE"),
    ("LIMIT_MOVE_STK_CND", "RANK_CHANGE_STK_CND"),
    ("LIMIT_MOVE_STK_CND", "STOCK_CONDITION"),
    ("LIMIT_MOVE_STK_CND", "VOLUME_SURGE_STK_CND"),
    ("NEAR_HIGHLOW_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("NEAR_HIGHLOW_STK_CND", "ORDERBOOK_SURGE_STK_CND"),
    ("NEAR_HIGHLOW_STK_CND", "ORDERBOOK_TOP_STK_CND"),
    ("NEAR_HIGHLOW_STK_CND", "STOCK_CONDITION"),
    ("NEW_HIGH_LOW_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("NEW_HIGH_LOW_STK_CND", "ORDERBOOK_SURGE_STK_CND"),
    ("NEW_HIGH_LOW_STK_CND", "ORDERBOOK_TOP_STK_CND"),
    ("NEW_HIGH_LOW_STK_CND", "STOCK_CONDITION"),
    ("OPEN_CHANGE_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("OPEN_CHANGE_STK_CND", "STOCK_CONDITION"),
    ("ORDERBOOK_SURGE_QTY_TYPE_BARE", "VOLUME_RANK_QTY_TYPE"),
    ("ORDERBOOK_SURGE_QTY_TYPE_BARE", "VOLUME_SURGE_QTY_TYPE_BARE"),
    ("ORDERBOOK_SURGE_STK_CND", "STOCK_CONDITION"),
    ("ORDERBOOK_SURGE_STK_CND", "SURGE_STK_CND"),
    ("ORDERBOOK_TOP_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("ORDERBOOK_TOP_STK_CND", "STOCK_CONDITION"),
    ("ORDERBOOK_TOP_STK_CND", "SURGE_STK_CND"),
    ("PERIOD_RECENT_OR_RANGE", "PERIOD_TODAY_PREV_5_60"),
    ("PERIOD_RECENT_OR_RANGE", "TRADER_ANALYSIS_PERIOD_5_120"),
    ("PERIOD_TODAY_PREV_5_60", "TRADER_ANALYSIS_PERIOD_5_120"),
    ("RANK_CHANGE_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("RANK_CHANGE_PRICE_CND", "SURGE_PRICE_CND"),
    ("RANK_CHANGE_PRICE_CND", "VOLUME_SURGE_PRICE_TYPE"),
    ("RANK_CHANGE_STK_CND", "STOCK_CONDITION"),
    ("STOCK_CONDITION", "SURGE_STK_CND"),
    ("SURGE_CREDIT_CND", "VOLUME_RANK_CREDIT_TYPE"),
    ("SURGE_PRICE_CND", "VOLUME_SURGE_PRICE_TYPE"),
})

def _predicate1_strict_subset(a: dict, b: dict) -> bool:
    """(1) A의 모든 (키,값)이 B에 있고 A != B. 순서 있음."""
    return a.items() <= b.items() and a != b


def _predicate2_keys_subset_values_differ(a: dict, b: dict) -> bool:
    """(2) keys(A) ⊆ keys(B)인데 공유 키의 값이 하나라도 다름. 순서 있음."""
    return set(a) <= set(b) and any(a[k] != b[k] for k in a)


def _predicate3_partial_overlap(a: dict, b: dict) -> bool:
    """(3) 양쪽 다 배타 키가 있고, 공유 키 3개 이상이 값까지 전부 일치. 대칭.

    이 형태의 병합은 기존 값을 하나도 바꾸지 않으므로 값 고정 테스트가
    원리상 잡지 못한다 — 배타 키가 사라지는 것으로만 감지된다.
    """
    ka, kb = set(a), set(b)
    shared = ka & kb
    return (
        bool(shared)
        and bool(ka - kb)
        and bool(kb - ka)
        and len(shared) >= 3
        and all(a[k] == b[k] for k in shared)
    )


def test_no_codebook_constants_are_accidentally_merged():
    """이름이 다른 두 코드북이 같은 값 집합을 갖게 되면 실패한다.

    **양쪽을 합집합으로 바꾸는 병합**은 두 상수를 동치로 만들기 때문에, 이
    한 줄짜리 불변식이 술어 1/2/3이 잡아내는 352쌍 전부를 그 형태에 한해
    방어한다. 476개 병합을 실제로 수행해 확인했고, 그 중 54쌍은 이 테스트가
    없으면 기존 스위트를 전부 통과해 조용히 지나간다.

    한쪽만 넓히는 확장(`A = {**A, **B}`)은 A != B로 남아 여기 걸리지 않는다.
    그런 확장 12쌍은 이 파일 전체를 통과하며, 다른 파일의 값 고정 테스트가
    막는다 (모듈 독스트링 참고). 이 테스트 하나를 전수 방어로 읽지 말 것.

    새로 동치 쌍이 생겼다면 둘 중 하나다:
      (a) 코드북을 잘못 합쳤다 -> 되돌릴 것.
      (b) 원래 값이 같은 별개 api_id 코드북을 새로 추가했다
          -> _KNOWN_IDENTICAL_PAIRS에 등록하고, 정의부 주석에
             형제 상수와 "절대 합치지 말 것"을 적을 것.
    """
    maps = _codebook_mappings()
    equal_pairs = {
        (x, y)
        for x, y in itertools.combinations(sorted(maps), 2)
        if maps[x] == maps[y]
    }
    unexpected = equal_pairs - _KNOWN_IDENTICAL_PAIRS
    assert unexpected == set(), (
        "코드북 상수가 합쳐졌거나 값이 같아졌다 — 절대 합치지 말 것: "
        f"{sorted(unexpected)}"
    )
    vanished = _KNOWN_IDENTICAL_PAIRS - equal_pairs
    assert vanished == set(), (
        "동치였던 쌍이 갈라졌다. 의도한 분리라면 allowlist에서 지울 것: "
        f"{sorted(vanished)}"
    )


def test_predicate3_partial_overlap_inventory_is_frozen():
    """술어 3(부분 겹침 + 양쪽 배타 키) 쌍 목록을 고정한다.

    이 관계는 값 고정 테스트로 잡히지 않는 무성 병합 위험을 뜻한다.
    목록이 바뀌면(새 상수 추가로 늘거나, 병합으로 줄거나) 반드시 사람이
    검토해야 한다 — 줄어드는 쪽이 특히 위험하다(병합됐다는 뜻).
    """
    maps = _codebook_mappings()
    found = {
        (x, y)
        for x, y in itertools.combinations(sorted(maps), 2)
        if _predicate3_partial_overlap(maps[x], maps[y])
    }
    assert found == _KNOWN_PARTIAL_OVERLAP_PAIRS, (
        f"새로 생긴 술어3 쌍: {sorted(found - _KNOWN_PARTIAL_OVERLAP_PAIRS)} / "
        f"사라진 술어3 쌍(병합 의심): {sorted(_KNOWN_PARTIAL_OVERLAP_PAIRS - found)}"
    )


def test_closure_predicates_run_in_both_directions():
    """세 술어의 관계 개수를 **양방향**으로 고정한다.

    이전 청크들은 항상 new ⊆ existing 한 방향만 계산했다. A⊂B와 B⊂A는
    다른 질문이고, 술어 2는 실제로 양방향으로 성립하는 쌍이 46개 있다
    (키 집합이 완전히 같고 값만 뒤집힌 순수 극성 해저드).
    """
    maps = _codebook_mappings()
    names = sorted(maps)
    p1 = [
        (x, y) for x, y in itertools.permutations(names, 2)
        if _predicate1_strict_subset(maps[x], maps[y])
    ]
    p2 = [
        (x, y) for x, y in itertools.permutations(names, 2)
        if _predicate2_keys_subset_values_differ(maps[x], maps[y])
    ]

    def split(hits):
        s = set(hits)
        both = {(x, y) for x, y in s if (y, x) in s}
        return len(s - both), len(both) // 2

    assert len(maps) == 172
    assert len(p1) == 118
    assert split(p1) == (118, 0)   # strict subset은 양방향이 정의상 불가능
    assert len(p2) == 202
    assert split(p2) == (110, 46)  # 46쌍은 키 집합 동일 + 값만 다름
