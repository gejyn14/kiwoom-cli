"""Rich formatters for Kiwoom API responses."""

from __future__ import annotations

import csv
import sys
from typing import Any, NoReturn

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import envelope
from .output import console, err_console


def _get_format() -> str:
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.obj:
        return ctx.obj.get("format", "table")
    return "table"


def human(renderable: Any) -> None:
    """사람이 읽는 출력 (미리보기, 안내 메시지 등).

    table 모드에서는 stdout, json/csv 모드에서는 stderr로 출력해
    stdout이 단일 파싱 가능 문서로 유지되도록 한다.
    """
    if _get_format() == "table":
        console.print(renderable)
    else:
        err_console.print(renderable)


def fail_input(message: str, *, code: str = "INVALID_INPUT") -> NoReturn:
    """입력 오류 계약 종료: table=stderr 빨간 메시지, json/csv=envelope 오류. exit 1.

    커맨드 본문에서 err_console.print + SystemExit(1) 패턴 대신 사용한다 —
    json 모드에서 stdout이 비는(에이전트가 분기할 수 없는) 종료를 막는다.
    """
    if _get_format() == "table":
        err_console.print(f"[red]{message}[/]")
    else:
        envelope.emit(error=envelope.error_body(message, code=code, retryable=False))
    raise SystemExit(1)


def fail_api(message: str, *, code: str = "UPSTREAM_ERROR") -> NoReturn:
    """API 계열 오류 계약 종료: table=stderr 빨간 메시지, json/csv=envelope 오류. exit 2.

    통합 명령(국내+미국)에서 양쪽 모두 실패한 경우처럼, 전역 핸들러를 타지
    않는 API 실패 경로에서 사용한다 — json 모드 stdout이 비지 않게 한다.
    """
    if _get_format() == "table":
        err_console.print(f"[red]{message}[/]")
    else:
        envelope.emit(error=envelope.error_body(message, code=code, retryable=False))
    raise SystemExit(2)


def _output_json(data: Any) -> None:
    """Write a Kiwoom API response as an enveloped JSON document to stdout.

    data는 정규화(normalize_record)된 타입 있는 필드로 변환되고, 원본은
    data.raw에 보존됩니다. API 응답이 아닌 페이로드(dry-run, validate 등)는
    envelope.emit을 직접 호출하므로 이 경로를 타지 않습니다.
    """
    from . import normalize  # 순환 import 회피 (normalize가 필드 분류를 여기서 가져감)

    if isinstance(data, dict):
        clean = {k: v for k, v in data.items() if k not in ("return_code", "return_msg")}
        doc = normalize.normalize_record(clean)
        doc["raw"] = clean
        envelope.emit(data=doc)
    elif isinstance(data, list):
        envelope.emit(data={
            "items": [normalize.normalize_record(x) if isinstance(x, dict) else x for x in data],
            "raw": data,
        })
    else:
        envelope.emit(data=data)


def _output_csv(rows: list[dict], keys: list[str] | None = None) -> None:
    """Write rows as CSV to stdout."""
    if not rows:
        return
    if keys is None:
        keys = list(dict.fromkeys(k for r in rows for k in r))
    w = csv.DictWriter(sys.stdout, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in keys})


def _flat_dict(data: dict) -> list[dict]:
    """Flatten a dict with scalar values into a single-row list for CSV."""
    clean = {k: v for k, v in data.items()
             if not isinstance(v, (list, dict)) and k not in ("return_code", "return_msg")}
    return [clean] if clean else []


def _sign_color(value: str) -> str:
    """Return color based on sign: red for positive (상승), blue for negative (하락)."""
    s = value.strip()
    if s.startswith("-"):
        return "blue"
    v = s.lstrip("+").lstrip("0")
    if v and (v[:1].isdigit() or v[:1] == "."):
        return "red"
    return "white"


def _fmt_number(value: str, strip_sign: bool = False) -> str:
    """Format a number string with commas, stripping leading zeros.

    Args:
        strip_sign: If True, remove the +/- prefix. Use for absolute value
            fields where Kiwoom uses +/- only as a direction indicator
            (e.g. cur_prc, open_pric, high_pric, etc.).
    """
    v = value.strip()
    if not v:
        return "-"
    sign = ""
    if v.startswith(("+", "-")):
        sign = v[0]
        v = v[1:]
    v = v.lstrip("0") or "0"
    if strip_sign:
        sign = ""
    try:
        return sign + f"{int(v):,}"
    except ValueError:
        try:
            return sign + f"{float(v):,.2f}"
        except ValueError:
            return v if strip_sign else value


def _fmt_usd(value: str, strip_sign: bool = False) -> str:
    """Format a USD decimal string: commas, up to 4 decimals, trailing zeros stripped.

    Kiwoom US APIs return prices with up to 4 decimals ("213.0400", "0.0012").
    _fmt_number would force 2 decimals and mangle penny stocks; this preserves them.
    """
    v = value.strip()
    if not v:
        return "-"
    sign = ""
    if v.startswith(("+", "-")):
        sign = v[0]
        v = v[1:]
    if strip_sign:
        sign = ""
    v = v.lstrip("0") or "0"
    try:
        if "." not in v:
            return sign + f"{int(v):,}"
        s = f"{float(v):,.4f}".rstrip("0").rstrip(".")
        return sign + (s or "0")
    except ValueError:
        return value


# Fields where +/- is a direction indicator, not the actual sign.
# These represent absolute values (prices, amounts, quantities).
_ABS_FIELDS = frozenset({
    "cur_prc", "open_pric", "high_pric", "low_pric", "close_pric",
    "strt_pric", "base_pric", "upl_pric", "lst_pric",
    "oyr_hgst", "oyr_lwst", "250hgst", "250lwst",
    "sel_fpr_bid", "buy_fpr_bid", "exp_cntr_pric",
    "avg_prc", "evlt_amt", "pur_amt", "repl_pric",
    "mac", "fav", "cap", "flo_stk", "dstr_stk",
    "entr", "d2_entra", "tot_est_amt", "aset_evlt_amt",
    "tot_pur_amt", "prsm_dpst_aset_amt",
    "rmnd_qty", "ord_qty", "ord_uv", "mdfy_uv",
    "trde_qty", "acc_trde_qty", "now_trde_qty",
    # WebSocket field IDs (시세: 현재가/시고저/호가, 누적거래량·대금)
    "10", "16", "17", "18", "27", "28", "13", "14",
    # WebSocket field IDs (주문/잔고: 수량·가격·금액)
    "900", "901", "902", "903", "910", "911", "920",
    "930", "931", "932", "933", "941",
    "now_pric", "frgn_stk_book_uv", "cntr_uv", "stop_pric",
    "fpr_sel_bid", "fpr_buy_bid",
    "sel_1bid", "sel_2bid", "sel_3bid", "sel_4bid", "sel_5bid",
    "sel_6bid", "sel_7bid", "sel_8bid", "sel_9bid", "sel_10bid",
    "buy_1bid", "buy_2bid", "buy_3bid", "buy_4bid", "buy_5bid",
    "buy_6bid", "buy_7bid", "buy_8bid", "buy_9bid", "buy_10bid",
    "poss_qty", "sell_alowq",
    # Task 3b — 스펙 Response Example에서 +/- 방향지시자를 확인한 호가·체결가 필드.
    # sel_bid(ka10016/17/18/24/26/29/32/34 등 13개), buy_bid(12개): "매도호가"/"매수호가"
    "sel_bid", "buy_bid",
    # cntr_pric(체결가, ka10055/50010/50092/50101 등에서 "+" 확인)
    "cntr_pric",
    # pri_sel_bid_unit/pri_buy_bid_unit(ka10003/ka10084 등에서 +/- 확인)
    "pri_sel_bid_unit", "pri_buy_bid_unit",
    # wonju_pric(원주가격, ka40006/ka40007 예시 "-10")
    "wonju_pric",
    # past_curr_prc(과거현재가, ka00198 예시 "+70700")
    "past_curr_prc",
    # 52wk_hgst_pric/52wk_lwst_pric(ka20001/ka20009 예시 "+3001.91"/"-1608.07")
    "52wk_hgst_pric", "52wk_lwst_pric",
    # tdy_high_pric/tdy_low_pric(당일고가/당일저가, ka10018 예시 +/- 확인)
    "tdy_high_pric", "tdy_low_pric",
    # ka10095(관심종목정보) 호가 1~5단계: 예시에서 "+" 확인. buy_5th_bid만 예시값이
    # "121700"으로 부호 없이 나타나지만, 같은 object의 나머지 9개 호가 필드(sel_1th_bid~
    # sel_5th_bid, buy_1th_bid~buy_4th_bid)가 모두 signed이고 매수호가는 어떤 경우에도
    # 음수가 될 수 없으므로 부호 제거는 안전하다 — 4개만 벗기고 5번째만 방향지시자를
    # 노출하면 그 자체로 버그처럼 보인다 (리뷰 Finding 3, 문서 예시가 진짜여도 안전한 판단).
    "sel_1th_bid", "sel_2th_bid", "sel_3th_bid", "sel_4th_bid", "sel_5th_bid",
    "buy_1th_bid", "buy_2th_bid", "buy_3th_bid", "buy_4th_bid", "buy_5th_bid",
    # cur_prc_n(지수현재가 짝필드, ka20001/ka20009/ka40008 예시 +/- 확인).
    # _get_label이 "_n" 접미사를 떼고 base 라벨을 쓰지만 멤버십 검사는 원본 키로
    # 하므로 별도 등록 필요 (base cur_prc와 동일 취급).
    #
    # 불변식(리뷰 Finding 4에서 확인): _get_label()은 "_n"으로 끝나는 아무 키에나
    # 접미사를 떼는 *일반* fallback을 쓰지만, 이 멤버십 검사(_ABS_FIELDS/_SIGNED_FIELDS)는
    # 하드코딩된 개별 키 나열이라 라벨 fallback과 동기화돼 있지 않다. 오늘은 스펙에
    # "_n" 접미사 필드가 정확히 10개뿐이고(직접 재검증함) 그중 가격류 5개(cur_prc_n/
    # trde_qty_n/acc_trde_qty_n 및 아래 _SIGNED_FIELDS의 pred_pre_n/flu_rt_n)만 여기
    # 등록돼 있어 문제가 없지만 — 향후 새 "_n" 가격 필드가 스펙에 추가되면 라벨은
    # 정상 표시되면서 부호는 조용히 그대로 새어나갈 수 있다.
    "cur_prc_n",
    # trde_qty_n/acc_trde_qty_n: base(trde_qty/acc_trde_qty)가 이미 ABS이므로 짝필드도
    # 동일 취급 — 스펙 예시에서 +/- 부호가 관측된 적은 없는 수량 필드다(근거 없이 base를
    # 따라간 것으로, 형제 필드 정황 증거로 편입한 buy_5th_bid와는 다른 기준). "부호가
    # 없으니 벗겨도 no-op"이라는 주장은 틀렸다: normalize.py를 거치면 문자열 "890"이
    # 정수 890으로 타입 자체가 바뀌므로 -f json 소비자에게는 실질적인 변화다 (Finding 4).
    "trde_qty_n", "acc_trde_qty_n",
})

# Fields where +/- is meaningful (changes, rates).
_SIGNED_FIELDS = frozenset({
    "pred_pre", "flu_rt", "pre_rt", "pl_amt", "pl_rt",
    "tdy_lspft", "lspft", "tdy_lspft_rt", "lspft_rt", "lspft_ratio",
    "11", "12", "15",  # WebSocket: 전일대비, 등락율, 거래량(+매수/-매도)
    "938", "940", "950", "951",  # WebSocket: 당일순매수수량, 당일총매도손익, 당일실현손익(율)
    # Task 3b — pred_pre_n/flu_rt_n: base(pred_pre/flu_rt)가 실제 등락폭·등락율(부호가
    # 곧 값)이므로 짝필드(ka20001/ka20009/ka40008 지수)도 동일하게 부호 보존
    "pred_pre_n", "flu_rt_n",
})

# Code fields that should never be number-formatted. 날짜(YYYYMMDD)/시각(HHMMSS)
# 필드. print_generic_table은 API 응답(Response)만 그리고 요청 바디는 거치지
# 않으므로, 아래 각 항목은 Response 필드 기준으로 검증했다. expires_dt(au10001)만
# 별도 표기가 있는데, 이는 Request/Response 구분의 예외가 아니라 — au10001의
# expires_dt는 정상적인 Response 필드다 — 렌더링 경로의 예외다(client.py가
# 직접 처리해 보통 이 게이트를 타지 않고, raw `kiwoom api au10001`로만 도달함;
# 아래 개별 항목 참고). 스펙 전체(미구현 API 포함, 339시트)에서 "dt" 필드는
# 49개 시트에서 일자(YYYYMMDD)로, 3개 시트(usa26410/usa26413/usa26414)에서
# 연도(YYYY)로 쓰인다.
_CODE_FIELDS = frozenset({
    "stk_cd", "ord_no",
    "symbol", "order_no",  # 정규화 canonical 이름 (history 등 이벤트 테이블)
    "dt", "date", "tm",
    "ord_tm", "cntr_tm", "cntr_dt", "trde_dt",
    "qry_dt", "qry_tm",  # ka10040/ka10053 조회일자/조회시간(같은 오브젝트의 형제
    # 필드쌍). 실제 예시값은 둘 다 3자리 이하 잡음("012"/"017"/"050" 등)이고 desc도
    # 비어 있어 개별 근거는 약하지만 정확히 동일하게 약하다 — 한쪽만 등록하면 같은
    # 오브젝트 안에서 렌더링이 갈리므로 둘 다 포함(오늘은 길이<=4라 무해, 값이
    # 길어지면 실질적 불일치가 됨).
    "expr_dt", "loan_dt", "crd_loan_dt",
    "dt_n", "tm_n",  # ka20001/ka20009 지수 짝필드. _get_label()은 "_n" 접미사를 떼고
    # base 라벨(일자/시간)로 표시하지만 이 멤버십 검사는 원본 키로 하므로 별도 등록
    # 필요 (cur_prc_n과 동일 패턴, 위 _ABS_FIELDS 블록의 불변식 주석 참고).
    #
    # "dt"는 Response 바디에서는 예외 없이 일자(YYYYMMDD) — kiwoom-cli가 구현한
    # 217개 API 중 46개가 한글명 "일자"로 쓰고 "연도"로 쓰는 구현 API는 0개다.
    # Request 바디에서는 일부 순위류 API(ka10016/34/36/37/38/39/42/43/131,
    # ka30002, ka40001)에서 "기간"(조회 기간 코드: 5/10/20/60/120/250 등)을
    # 의미하지만, 요청 파라미터로만 나타나고 print_generic_table은 응답만 그리므로
    # 이 플랫 셋에 안전하게 함께 둘 수 있다 — 기간 코드값은 최대 3자리라 길이 게이트
    # 자체를 넘지 못해 어차피 무해하다.
    #
    # 제외한 후보:
    # - base_dt("기준일자") — 구현된 217개 API에서는 17개(ka10051/ka10080~83/
    #   ka10094/ka10170/ka20005~08/ka20019/ka30003/ka50012/ka50081~83) 모두
    #   Request 전용이고 그 Response 바디에는 등장하지 않는다 — 이 게이트가 다루는
    #   표시 경로(API 응답 렌더링)에 도달할 수 없어 제외. 스펙 전체(미구현 API
    #   포함) 관점에서는 usa21670/usa21680/usa21690(기준일 — 값이 시트마다 다름:
    #   usa21670 "20260503"=YYYYMMDD, usa21680 "202605"=YYYYMM, usa21690
    #   "2026"=연도만), usa24110/usa24111(최고/최저일시), usa24120/usa24121
    #   (기준일자, 예 "20260508") 7개 US 시트에서 Response 필드로도 쓰이지만,
    #   전부 API_REGISTRY에 없는(미구현) API라 이 코드베이스에서 base_dt가
    #   Response로 렌더링될 경로는 없다.
    # - rgt_dt — 스펙 전체(Request/Response 불문)에 해당 키가 존재하지 않음
    #   (브리프의 오기로 추정).
    "exp_tm",  # ka50087 예상 체결 시간, 예 "085957"(HHmmss, 선행 0 유실 사례)
    "elwexpr_dt",  # ka10095 ELW만기일, 예 "00000000"(만기 없음 0 sentinel)
    "bid_req_base_tm",  # ka10004/ka10087 호가잔량기준시간, 예 "162000"(HHmmss)
    "regDay",  # ka10099/ka10100 상장일, 예 "20091204" (camelCase 원본 필드명)
    "bid_tm",  # ka10095 호가시간 "164000"(HHmmss) / usa20101 "08:16"(HH:mm)
    "52wk_hgst_pric_dt", "52wk_lwst_pric_dt",  # ka20001/ka20009/usa20100, 예 "20241004"/"20241031"
    "oyr_hgst_dt", "oyr_lwst_dt",  # usa20100 연중최고/최저가일, 예 "20260514"/"20260330"
    "setl_dt",  # kt00008 결제일자, 예 "20241126"
    "d0_setl_dt", "d1_setl_dt", "d2_setl_dt", "d3_setl_dt", "d4_setl_dt",  # ust21160 D0~D4 국내결제일자
    "bus_dt",  # usa06010/usa06011 영업일자, 예 "20260624"
    "trde_cntr_proc_time", "virelis_time",  # ka10054 매매체결처리시각/VI해제시각, 예 "172311"/"172511"
    "sel_scesn_tm", "buy_scesn_tm",  # ka10040/ka10053 매도/매수이탈시간, 예 "154706"/"151615"
    "deal_dt",  # kt50032/ust21100 거래일자, 예 "20260511"
    "sell_dt",  # ust21530 매도일자, 예 "20260611"
    "cnfm_tm",  # kt00007/kt50031 확인시간(desc "HH:mm:ss"). 두 API 모두 스펙 예시는
    # 공백이지만 desc가 명시적이고 모순되는 값이 없어 등록.
    "exec_dt",  # ka30012 행사일, 예 "20241216"
    "fin_trde_dt", "flo_dt",  # ka30005 최종거래일/상장일(elw 접두사 없는 원본 키), 예 "20241212"/"20240320"
    "elwfin_trde_dt", "elwflo_dt", "elwpay_dt", "lpsuply_end_dt",  # ka30012, 예 "20241212"/"20240124"/"20241218"/"20241212"
    "lpinitlast_suply_dt",  # ka30005 LP초종공급일, 예 "20241212"
    "trde_strt_dt",  # ka10007 거래시작일, 예 "00000000" (만기 없음과 동일한 0 sentinel)
    "ord_dt",  # ust21180 주문일, 예 "20260605"
    "expires_dt",  # au10001(OAuth 토큰발급) 만료일, 예 "20241107083713"(YYYYMMDDHHmmss).
    # client.py의 issue_token()이 직접 다뤄 보통은 print_generic_table을 거치지
    # 않지만, raw `kiwoom api au10001 '{}'`(table 모드)는 이 경로를 그대로 탄다.
    #
    # 아래 둘은 desc가 명시적으로 "YYYYMMDD"이고 동일 목적의 자매 필드
    # (52wk_hgst_pric_dt 등)가 확인돼 있어 편입했지만, 이 API 자신의 Response
    # Example만으로는 직접 확인되지 않는다 — 근거가 간접적임을 밝혀둔다.
    "hgst_pric_dt", "lwst_pric_dt",  # ka10007 최고가일/최저가일. 예시가 항상 공백("")
    "250hgst_pric_dt", "250lwst_pric_dt",  # ka10001 250최고가일/최저가일. 이 API의
    # Response Example 자체가 손상돼 있다(같은 예시에서 upl_pric/base_pric에는
    # 날짜값이, 250hgst_pric_dt/250lwst_pric_dt에는 "3"/"0.00"이 들어있음 — 컬럼이
    # 밀린 문서 오류로 보임. docs/키움 REST API 문서.xlsx에도 동일하게 손상돼 있어
    # 파싱 오류가 아니라 스펙 문서 자체의 결함으로 확인함).
    "base_pric_tm",  # ka90008/ka90013 기준가시간, desc "HHmmss"(예시는 공백). 같은
    # 키가 ka30001에도 있으나 값이 "기준가(11/21)" 같은 텍스트 라벨이라 애초에
    # isdigit() 게이트를 통과 못해 멤버십과 무관하게 안전하다 — 세 API가 이 플랫
    # 셋을 공유하므로, ka90008/ka90013 쪽 실제 HHmmss 값을 지키기 위해 포함한다.
    "fr_dt", "to_dt",  # ka30012 평가시작일자/평가종료일자(desc 없음, 이 API 자신의
    # 예시는 항상 공백). 같은 키가 kt00016(desc "YYYYMMDD", 예 "20241111"/
    # "20241125")과 ust21650(desc "YYYYMMDD", 예 "20260501"/"20260507")에서
    # 실제 날짜값으로 확인됨 — 그 두 API에서는 Request 전용이라 이 게이트와 무관
    # 하지만, 동일 키가 ka30012에서는 Response 필드이므로 그 경로로 렌더링될 수
    # 있어 포함한다.
    #
    # 검토했으나 제외: fr_tm/evlt_end_tm(ka30012 평가시작/종료시간) — desc가 없고
    # 예시도 항상 공백이며, fr_dt/to_dt와 달리 스펙 전체(339 + 209시트)를 통틀어
    # 이 두 키가 등장하는 곳이 ka30012 하나뿐이라 대조할 자매 필드가 없다 — 근거
    # 부족으로 제외.
})

# USD decimal fields (up to 4 decimals). Routed to _fmt_usd by _smart_fmt.
# Direction-indicator USD prices additionally live in _ABS_FIELDS (sign stripped).
_USD_FIELDS = frozenset({
    "now_pric", "frgn_stk_book_uv", "cntr_uv", "stop_pric",
    "fpr_sel_bid", "fpr_buy_bid",
    "sel_1bid", "sel_2bid", "sel_3bid", "sel_4bid", "sel_5bid",
    "sel_6bid", "sel_7bid", "sel_8bid", "sel_9bid", "sel_10bid",
    "buy_1bid", "buy_2bid", "buy_3bid", "buy_4bid", "buy_5bid",
    "buy_6bid", "buy_7bid", "buy_8bid", "buy_9bid", "buy_10bid",
    "pre_open_pric", "pre_high_pric", "pre_low_pric", "base_close_pric",
    "fc_entra", "fc_uncl_amt", "pred_pre",
    "aplc_exrt", "sell_aplc_exrt", "buy_aplc_exrt", "usd_exch_rate",
    "exch_rate", "base_exrt", "spcl_bf_exrt",
    "sell_expc_amt", "buy_expc_amt", "sell_crnc_exmn_alow_amt",
    "buy_crnc_exmn_alow_amt", "fc_exmn_alow_amt",
    # USD in US responses (KRW twin: pl_amt_krw); integer path renders
    # identically to _fmt_number, so KR pl_amt output is unchanged.
    "pl_amt",
})


def _smart_fmt(value: str, field_key: str) -> str:
    """Format a value based on the field type."""
    if field_key in _USD_FIELDS:
        return _fmt_usd(value, strip_sign=field_key in _ABS_FIELDS)
    if field_key in _ABS_FIELDS:
        return _fmt_number(value, strip_sign=True)
    return _fmt_number(value)


# Union of every field _smart_fmt knows how to classify. Fields in this set
# always bypass the length-gated fallback below (see _needs_fmt).
_CLASSIFIED_FIELDS = _USD_FIELDS | _ABS_FIELDS | _SIGNED_FIELDS


def _needs_fmt(k: str, v: str) -> bool:
    """Whether print_generic_table should route a cell through _smart_fmt.

    Classified fields (_USD_FIELDS/_ABS_FIELDS/_SIGNED_FIELDS — the project's
    source of truth for numeric field types) always go through _smart_fmt,
    regardless of value length. Everything else falls back to the historical
    heuristic (numeric-looking and >4 chars, excluding known code fields) so
    unclassified short numeric codes (e.g. leading-zero business codes like
    inds_cd) keep their pre-existing raw rendering.
    """
    if k in _CLASSIFIED_FIELDS:
        return True
    return k not in _CODE_FIELDS and v.lstrip("+-").isdigit() and len(v) > 4


def _find_list(data: dict) -> list | None:
    """Find the first list value in API response."""
    for k, v in data.items():
        if isinstance(v, list) and k not in ("return_code", "return_msg"):
            return v
    return None


def print_api_response(data: dict | list, title: str = "결과") -> None:
    """Print API response, extracting list if present."""
    if isinstance(data, dict):
        items = _find_list(data)
        if items is not None:
            print_generic_table(items, title=title)
            return
    print_generic_table(data, title=title)


def _calc_eval_pl(data: dict) -> tuple[int, str, str, str]:
    """Calculate evaluation P&L. Returns (amount, amount_str, rate_str, color)."""
    try:
        evlt = int(data.get("tot_est_amt", "0").lstrip("0") or "0")
        pur = int(data.get("tot_pur_amt", "0").lstrip("0") or "0")
        eval_pl = evlt - pur
        eval_pl_rt = (eval_pl / pur * 100) if pur else 0
        eval_pl_str = f"+{eval_pl:,}" if eval_pl > 0 else f"{eval_pl:,}"
        eval_pl_rt_str = f"{eval_pl_rt:+.2f}"
    except (ValueError, ZeroDivisionError):
        eval_pl = 0
        eval_pl_str = "-"
        eval_pl_rt_str = "0.00"
    color = "red" if eval_pl > 0 else ("blue" if eval_pl < 0 else "white")
    return eval_pl, eval_pl_str, eval_pl_rt_str, color


def print_stock_info(data: dict[str, Any]) -> None:
    """Format stock basic info (ka10001)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    t = Table(title=f"📊 {data.get('stk_nm', '')} ({data.get('stk_cd', '')})", show_header=False, border_style="dim")
    t.add_column("항목", style="cyan", width=20)
    t.add_column("값", width=30)

    cur = data.get("cur_prc", "0")
    change = data.get("pred_pre", "0")
    rate = data.get("flu_rt", "0")
    color = _sign_color(cur)

    t.add_row("현재가", Text(_fmt_number(cur, strip_sign=True), style=f"bold {color}"))
    t.add_row("전일대비", Text(f"{_fmt_number(change)} ({rate}%)", style=color))
    t.add_row("거래량", _fmt_number(data.get("trde_qty", ""), strip_sign=True))
    t.add_row("시가", _fmt_number(data.get("open_pric", ""), strip_sign=True))
    t.add_row("고가", _fmt_number(data.get("high_pric", ""), strip_sign=True))
    t.add_row("저가", _fmt_number(data.get("low_pric", ""), strip_sign=True))
    t.add_row("", "")
    t.add_row("시가총액", _fmt_number(data.get("mac", ""), strip_sign=True) + "억")
    t.add_row("PER", data.get("per", "-") or "-")
    t.add_row("PBR", data.get("pbr", "-") or "-")
    t.add_row("EPS", _fmt_number(data.get("eps", ""), strip_sign=True))
    t.add_row("BPS", _fmt_number(data.get("bps", ""), strip_sign=True))
    t.add_row("ROE", data.get("roe", "-") or "-")
    t.add_row("", "")
    t.add_row("52주 최고", _fmt_number(data.get("oyr_hgst", ""), strip_sign=True))
    t.add_row("52주 최저", _fmt_number(data.get("oyr_lwst", ""), strip_sign=True))
    t.add_row("상장주식수", _fmt_number(data.get("flo_stk", "")))
    t.add_row("외인소진률", data.get("for_exh_rt", "-") or "-")
    console.print(t)


def print_orderbook(data: dict[str, Any]) -> None:
    """Format 10-level orderbook (ka10004)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    t = Table(title="📋 호가창", border_style="dim")
    t.add_column("매도잔량", justify="right", style="blue", width=12)
    t.add_column("매도호가", justify="right", style="blue", width=10)
    t.add_column("매수호가", justify="right", style="red", width=10)
    t.add_column("매수잔량", justify="right", style="red", width=12)

    # Sell side (10 -> 1, top to bottom)
    sell_rows = []
    for i in range(10, 0, -1):
        suffix = "th" if i > 1 else ""
        if i == 1:
            bid_key = "sel_fpr_bid"
            qty_key = "sel_fpr_req"
        else:
            bid_key = f"sel_{i}{suffix}_pre_bid"
            qty_key = f"sel_{i}{suffix}_pre_req"
        sell_rows.append((_fmt_number(data.get(qty_key, "0")), _fmt_number(data.get(bid_key, "0"))))

    buy_rows = []
    for i in range(1, 11):
        suffix = "th"
        if i == 1:
            bid_key = "buy_fpr_bid"
            qty_key = "buy_fpr_req"
        else:
            bid_key = f"buy_{i}{suffix}_pre_bid"
            qty_key = f"buy_{i}{suffix}_pre_req"
        buy_rows.append((_fmt_number(data.get(bid_key, "0")), _fmt_number(data.get(qty_key, "0"))))

    for qty, price in sell_rows:
        t.add_row(qty, price, "", "")
    t.add_row("─" * 12, "─" * 10, "─" * 10, "─" * 12, style="dim")
    for price, qty in buy_rows:
        t.add_row("", "", price, qty)

    t.add_row("", "", "", "")
    t.add_row(
        f"[bold blue]{_fmt_number(data.get('tot_sel_req', '0'))}[/]",
        "[bold]총매도[/]",
        "[bold]총매수[/]",
        f"[bold red]{_fmt_number(data.get('tot_buy_req', '0'))}[/]",
    )
    console.print(t)


def print_account_eval(data: dict[str, Any]) -> None:
    """Format account evaluation (kt00004)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        holdings = data.get("stk_acnt_evlt_prst", [])
        if holdings:
            _output_csv(holdings)
        else:
            _output_csv(_flat_dict(data))
        return
    summary = Table(title="💰 계좌평가현황", show_header=False, border_style="dim")
    summary.add_column("항목", style="cyan", width=20)
    summary.add_column("값", width=25)

    summary.add_row("계좌명", data.get("acnt_nm", ""))
    summary.add_row("예수금", _fmt_number(data.get("entr", "")))
    summary.add_row("D+2 예수금", _fmt_number(data.get("d2_entra", "")))
    summary.add_row("총매입금액", _fmt_number(data.get("tot_pur_amt", "")))
    summary.add_row("유가잔고평가액", _fmt_number(data.get("tot_est_amt", "")))
    summary.add_row("예탁자산평가액", _fmt_number(data.get("aset_evlt_amt", "")))
    summary.add_row("추정예탁자산", _fmt_number(data.get("prsm_dpst_aset_amt", "")))

    # 평가손익 = 유가잔고평가액 - 총매입금액
    _, eval_pl_str, eval_pl_rt_str, eval_color = _calc_eval_pl(data)
    summary.add_row("평가손익", Text(eval_pl_str, style=eval_color))
    summary.add_row("평가손익율", Text(eval_pl_rt_str + "%", style=eval_color))
    pl_color = _sign_color(data.get("tdy_lspft", "0"))
    summary.add_row("당일실현손익", Text(_fmt_number(data.get("tdy_lspft", "")), style=pl_color))
    summary.add_row("당일실현손익율", Text(data.get("tdy_lspft_rt", "0") + "%", style=pl_color))
    console.print(summary)

    holdings = data.get("stk_acnt_evlt_prst", [])
    if holdings:
        ht = Table(title="📦 보유종목", border_style="dim")
        ht.add_column("종목코드", style="dim")
        ht.add_column("종목명")
        ht.add_column("보유수량", justify="right")
        ht.add_column("평균단가", justify="right")
        ht.add_column("현재가", justify="right")
        ht.add_column("평가금액", justify="right")
        ht.add_column("손익금액", justify="right")
        ht.add_column("손익율", justify="right")

        for h in holdings:
            pl = h.get("pl_amt", "0")
            color = _sign_color(pl)
            ht.add_row(
                h.get("stk_cd", ""),
                h.get("stk_nm", ""),
                _fmt_number(h.get("rmnd_qty", "")),
                _fmt_number(h.get("avg_prc", "")),
                _fmt_number(h.get("cur_prc", ""), strip_sign=True),
                _fmt_number(h.get("evlt_amt", "")),
                Text(_fmt_number(pl), style=color),
                Text(h.get("pl_rt", "0") + "%", style=color),
            )
        console.print(ht)


def print_order_result(data: dict[str, Any], action: str = "주문") -> None:
    """Format order response."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    msg = data.get("return_msg", "")
    ord_no = data.get("ord_no", "")
    console.print(Panel(
        f"[bold green]✓ {action} 완료[/]\n\n"
        f"  주문번호: [bold]{ord_no}[/]\n"
        f"  메시지: {msg}",
        border_style="green",
    ))


def print_pending_orders(items: list[dict[str, Any]]) -> None:
    """Format pending orders list (ka10075)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(items)
        return
    if fmt == "csv":
        _output_csv(items)
        return
    if not items:
        console.print("[dim]미체결 주문이 없습니다.[/]")
        return

    t = Table(title="📝 미체결 주문", border_style="dim")
    t.add_column("주문번호")
    t.add_column("종목명")
    t.add_column("구분")
    t.add_column("주문수량", justify="right")
    t.add_column("주문가격", justify="right")
    t.add_column("미체결수량", justify="right")
    t.add_column("주문시간")

    for item in items:
        t.add_row(
            item.get("ord_no", ""),
            item.get("stk_nm", ""),
            item.get("buy_sell_tp", ""),
            _fmt_number(item.get("ord_qty", "")),
            _fmt_number(item.get("ord_uv", "")),
            _fmt_number(item.get("uncn_qty", "")),
            item.get("ord_tm", ""),
        )
    console.print(t)


# 터미널 테이블 표시 상한. 초과분은 잘리되 반드시 안내 문구를 출력한다.
_TABLE_ROW_CAP = 50
_CHART_ROW_CAP = 30


def print_chart_data(items: list[dict[str, Any]], title: str = "차트") -> None:
    """Format chart data (OHLCV)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(items)
        return
    if fmt == "csv":
        _output_csv(items)
        return
    if not items:
        console.print("[dim]데이터가 없습니다.[/]")
        return

    t = Table(title=f"📈 {title}", border_style="dim")
    t.add_column("일자", style="dim")
    t.add_column("시가", justify="right")
    t.add_column("고가", justify="right", style="red")
    t.add_column("저가", justify="right", style="blue")
    t.add_column("종가", justify="right")
    t.add_column("거래량", justify="right")

    for item in items[:_CHART_ROW_CAP]:
        t.add_row(
            item.get("dt", item.get("date", "")),
            _fmt_number(item.get("open_pric", item.get("strt_pric", "")), strip_sign=True),
            _fmt_number(item.get("high_pric", ""), strip_sign=True),
            _fmt_number(item.get("low_pric", ""), strip_sign=True),
            _fmt_number(item.get("close_pric", item.get("cls_pric", item.get("cur_prc", ""))), strip_sign=True),
            _fmt_number(item.get("trde_qty", item.get("acml_trde_qty", "")), strip_sign=True),
        )
    console.print(t)
    if len(items) > _CHART_ROW_CAP:
        console.print(
            f"[dim]{len(items)}행 중 {_CHART_ROW_CAP}행 표시 — 전체 데이터는 -f json 또는 -f csv 사용[/]"
        )


_FIELD_LABELS: dict[str, str] = {
    # 기본 시세
    "stk_cd": "종목코드", "stk_nm": "종목명", "cur_prc": "현재가",
    "pred_pre": "전일대비", "pred_pre_sig": "전일대비기호", "pre_sig": "대비기호",
    "flu_rt": "등락율", "flu_sig": "등락기호", "pre_rt": "대비율",
    "pred_rt": "전일비", "stk_cnd": "종목조건", "stk_cls": "종목분류",
    "stk_infr": "종목정보", "state": "종목상태", "rank": "순위",
    "market": "시장", "type": "종류",
    # 가격
    "open_pric": "시가", "high_pric": "고가", "low_pric": "저가",
    "close_pric": "종가", "base_pric": "기준가", "upl_pric": "상한가",
    "lst_pric": "하한가", "pred_close_pric": "전일종가", "repl_pric": "대용가",
    "exp_cntr_pric": "예상체결가", "exp_cntr_qty": "예상체결량",
    "fav": "액면가", "mac": "시가총액", "cap": "자본금",
    "52wk_hgst_pric": "52주최고가", "52wk_lwst_pric": "52주최저가",
    "52wk_hgst_pric_dt": "52주최고가일", "52wk_lwst_pric_dt": "52주최저가일",
    # 거래
    "trde_qty": "거래량", "trde_amt": "거래금액", "trde_prica": "거래대금",
    "acc_trde_qty": "누적거래량", "acc_trde_prica": "누적거래대금",
    "trde_tern_rt": "거래회전율", "pred_trde_qty": "전일거래량",
    "opmr_trde_qty": "장중거래량", "af_mkrt_trde_qty": "장후거래량",
    "bf_mkrt_trde_qty": "장전거래량", "now_trde_qty": "거래량",
    "trde_pre": "전일거래량대비", "trde_wght": "매매비중",
    # 체결
    "cntr_qty": "체결량", "cntr_pric": "체결가", "cntr_uv": "체결단가",
    "cntr_str": "체결강도", "cntr_tm": "체결시간", "cntr_dt": "체결일",
    "cntr_no": "체결번호", "cntr_trde_qty": "체결량",
    "cntr_str_5min": "체결강도5분", "cntr_str_20min": "체결강도20분",
    "cntr_str_60min": "체결강도60분",
    # 호가
    "sel_fpr_bid": "매도호가", "buy_fpr_bid": "매수호가",
    "sel_bid": "매도호가", "buy_bid": "매수호가",
    "sel_req": "매도잔량", "buy_req": "매수잔량",
    "tot_sel_req": "총매도잔량", "tot_buy_req": "총매수잔량",
    "netprps_req": "순매수잔량", "sdnin_qty": "급증수량", "sdnin_rt": "급증률",
    # 주문
    "ord_no": "주문번호", "ord_qty": "주문수량", "ord_uv": "주문가격",
    "ord_pric": "주문가격", "ord_tm": "주문시간", "ord_stt": "주문상태",
    "ord_remnq": "주문잔량", "ord_alowa": "주문가능현금",
    "ord_alow_amt": "주문가능금액", "ord_pos_repl": "주문가능대용",
    "orig_ord_no": "원주문번호", "io_tp_nm": "주문구분",
    "oso_qty": "미체결수량", "cncl_qty": "취소수량", "mdfy_qty": "정정수량",
    "sell_tp": "매도/수구분", "trde_tp": "매매구분",
    "cond_uv": "스톱가", "stop_pric": "스톱가",
    # 계좌/잔고
    "acnt_nm": "계좌명", "rmnd_qty": "보유수량", "avg_prc": "평균단가",
    "evlt_amt": "평가금액", "pl_amt": "손익금액", "pl_rt": "손익율",
    "evltv_prft": "평가손익", "prft_rt": "수익률", "tot_prft_rt": "수익률",
    "tot_evlt_pl": "총평가손익", "dt_prft_rt": "기간수익률",
    "entr": "예수금", "d2_entra": "D+2추정예수금",
    "tot_pur_amt": "총매입금액", "tot_est_amt": "유가잔고평가액",
    "prsm_dpst_aset_amt": "추정예탁자산", "tot_evlt_amt": "총평가금액",
    "pur_amt": "매입금액", "pur_pric": "매입가", "buy_uv": "매입단가",
    "pur_cmsn": "매입수수료", "sell_cmsn": "매도수수료", "sum_cmsn": "총수수료",
    "repl_amt": "대용금", "pymn_alow_amt": "출금가능금액",
    "rmnd": "잔고주수", "remn_amt": "잔고금액", "setl_remn": "결제잔고",
    "trde_able_qty": "매매가능수량", "poss_rt": "보유비중",
    "cmsn": "수수료", "tax": "세금",
    "tdy_trde_cmsn": "당일매매수수료", "tdy_trde_tax": "당일매매세금",
    "tdy_sel_pl": "당일매도손익", "profa_ch": "증거금현금",
    "tot_loan_amt": "총대출금액", "tot_crd_loan_amt": "총신용대출금액",
    "tot_crd_ls_amt": "총신용이자금액",
    "crd_tp_nm": "신용구분명", "crd_loan_dt": "신용대출일",
    "pred_buyq": "전일매수수량", "pred_sellq": "전일매도수량",
    "tdy_buyq": "당일매수수량", "tdy_sellq": "당일매도수량",
    "aset_evlt_amt": "예탁자산평가액", "acnt_evlt_remn_indv_tot": "계좌평가잔고상세",
    "stk_acnt_evlt_prst": "보유종목",
    # 매수/매도
    "buy_qty": "매수수량", "sell_qty": "매도수량",
    "buy_amt": "매수금액", "sell_amt": "매도금액",
    "netprps_qty": "순매수수량", "netprps_amt": "순매수금액",
    "netprps": "순매수", "nettrde_qty": "순매매수량", "nettrde_amt": "순매매금액",
    "buy_trde_qty": "매수거래량", "sel_trde_qty": "매도거래량",
    # 투자자
    "ind_invsr": "개인투자자", "frgnr_invsr": "외국인투자자",
    "orgn": "기관계", "fnnc_invt": "금융투자", "insrnc": "보험",
    "invtrt": "투신", "penfnd_etc": "연기금등", "samo_fund": "사모펀드",
    "etc_fnnc": "기타금융", "etc_corp": "기타법인", "bank": "은행",
    "ind_netprps": "개인순매수", "for_netprps": "외인순매수",
    "orgn_netprps": "기관순매수", "for_netprps_qty": "외인순매수수량",
    "orgn_netprps_qty": "기관순매수수량",
    "for_poss": "외인보유", "for_wght": "외인비중",
    "limit_exh_rt": "한도소진율",
    # 신용/대차
    "crd_rt": "신용비율", "crd_remn_rt": "신용잔고율", "crd_tp": "신용구분",
    "loan_dt": "대출일", "dbrt_trde_cntrcnt": "대차거래체결주수",
    "dbrt_trde_rpy": "대차거래상환주수", "dbrt_trde_irds": "대차거래증감",
    "nrpy_loan": "미상환융자금",
    # 프로그램매매
    "prm": "프로그램", "prm_buy_amt": "프로그램매수금액",
    "prm_sell_amt": "프로그램매도금액", "prm_netprps_amt": "프로그램순매수금액",
    "prm_buy_qty": "프로그램매수수량", "prm_sell_qty": "프로그램매도수량",
    "prm_netprps_qty": "프로그램순매수수량",
    "dfrt_trde_buy": "차익거래매수", "dfrt_trde_sel": "차익거래매도",
    "dfrt_trde_netprps": "차익거래순매수",
    "ndiffpro_trde_buy": "비차익거래매수", "ndiffpro_trde_sel": "비차익거래매도",
    "ndiffpro_trde_netprps": "비차익거래순매수",
    # 업종
    "inds_cd": "업종코드", "rising": "상승", "fall": "하락", "stdns": "보합",
    # ELW/ETF
    "nav": "NAV", "dispty_rt": "괴리율", "trace_eor_rt": "추적오차율",
    "delta": "델타", "gam": "감마", "theta": "쎄타", "vega": "베가",
    "iv": "IV", "theory_pric": "이론가", "exec_pric": "행사가격",
    "expr_dt": "만기일", "srvive_dys": "잔존일수",
    "isscomp_nm": "발행사명", "base_aset_nm": "기초자산명",
    # 거래원
    "sel_trde_ori_1": "매도거래원1", "sel_trde_ori_2": "매도거래원2",
    "sel_trde_ori_3": "매도거래원3", "sel_trde_ori_4": "매도거래원4",
    "sel_trde_ori_5": "매도거래원5",
    "buy_trde_ori_1": "매수거래원1", "buy_trde_ori_2": "매수거래원2",
    "buy_trde_ori_3": "매수거래원3", "buy_trde_ori_4": "매수거래원4",
    "buy_trde_ori_5": "매수거래원5",
    "mmcm_nm": "회원사명",
    # 날짜/시간
    "dt": "일자", "date": "일자", "tm": "시간",
    "qry_dt": "조회일자", "trde_dt": "매매일자",
    # 업종 추가
    "inds_nm": "업종명", "upl": "상한", "lst": "하한",
    "flo_stk_num": "유통주식수", "wght": "비중", "kospi200": "KOSPI200",
    "pre_smbol": "대비부호",
    # 순위
    "now_rank": "현재순위", "pred_rank": "전일순위", "bigd_rank": "대형주순위",
    "rank_chg": "순위변동", "rank_chg_sign": "순위변동기호",
    "cnt": "건수", "tot": "합계", "drng": "기간",
    # 전일/기준 대비
    "pred_pre_1": "전일대비1", "pred_pre_2": "전일대비2", "pred_pre_3": "전일대비3",
    "pred_dvida": "전일거래대금",
    "prev_base_chgr": "전일기준변동율", "prev_base_sign": "전일기준기호",
    "base_comp_chgr": "기준대비변동율", "base_comp_sign": "기준대비기호",
    "past_curr_prc": "과거현재가",
    # 장구분별 시세
    "opmr_pred_rt": "장중전일비", "opmr_trde_amt": "장중거래대금",
    "opmr_trde_rt": "장중거래비율",
    "af_mkrt_pred_rt": "장후전일비", "af_mkrt_trde_amt": "장후거래대금",
    "af_mkrt_trde_rt": "장후거래비율",
    "bf_mkrt_pred_rt": "장전전일비", "bf_mkrt_trde_amt": "장전거래대금",
    "bf_mkrt_trde_rt": "장전거래비율",
    # 투자자 순매수
    "frgnr_netprps": "외국인순매수", "insrnc_netprps": "보험순매수",
    "invtrt_netprps": "투신순매수", "bank_netprps": "은행순매수",
    "samo_fund_netprps": "사모펀드순매수", "endw_netprps": "기금순매수",
    "etc_corp_netprps": "기타법인순매수", "sc_netprps": "증권순매수",
    "natn_netprps": "국가순매수", "jnsinkm_netprps": "연기금순매수",
    "native_trmt_frgnr_netprps": "내국인대우외인순매수",
    # 외인/기관 상세
    "for_netprps_amt": "외인순매수금액",
    "for_netprps_stk_cd": "외인순매수종목코드", "for_netprps_stk_nm": "외인순매수종목명",
    "for_netslmt_amt": "외인순매도금액", "for_netslmt_qty": "외인순매도수량",
    "for_netslmt_stk_cd": "외인순매도종목코드", "for_netslmt_stk_nm": "외인순매도종목명",
    "orgn_netprps_amt": "기관순매수금액",
    "orgn_netprps_stk_cd": "기관순매수종목코드", "orgn_netprps_stk_nm": "기관순매수종목명",
    "orgn_netslmt_amt": "기관순매도금액", "orgn_netslmt_qty": "기관순매도수량",
    "orgn_netslmt_stk_cd": "기관순매도종목코드", "orgn_netslmt_stk_nm": "기관순매도종목명",
    # 프로그램매매 추가
    "dfrt_trde_acc": "차익거래누적", "dfrt_trde_tdy": "차익거래당일",
    "ndiffpro_trde_acc": "비차익거래누적", "ndiffpro_trde_tdy": "비차익거래당일",
    "all_acc": "전체누적", "all_tdy": "전체당일",
    # ETF 추가
    "trace_flu_rt": "추적등락율", "trace_idex": "추적지수",
    "trace_idex_cd": "추적지수코드", "trace_idex_nm": "추적지수명",
    "basis": "베이시스", "dvid_bf_base": "배당전기준가", "txbs": "세전",
    # 순위/테마 추가
    "base_limit_exh_rt": "기준한도소진율", "base_pre": "기준대비",
    "buy_tot_req": "매수총잔량", "sel_tot_req": "매도총잔량",
    "exh_rt_incrs": "소진율증가", "fall_stk_num": "하락종목수",
    "rising_stk_num": "상승종목수", "stk_num": "종목수",
    "gain_pos_stkcnt": "보유종목수", "poss_stkcnt": "보유종목수",
    "jmp_rt": "급등률", "main_stk": "주력종목",
    "netslmt": "순매도", "sel_qty": "매도수량",
    "pred_trde_qty_pre_rt": "전일거래량대비율", "prev_trde_qty": "전일거래량",
    "tdy_close_pric": "당일종가", "tdy_close_pric_flu_rt": "당일종가등락율",
    "tdy_high_pric": "당일고가", "tdy_low_pric": "당일저가",
    "thema_grp_cd": "테마그룹코드", "thema_nm": "테마명",
    # 기타
    "dm1": "연속일1", "dm2": "연속일2", "dm3": "연속일3",
    "pipe1": "구분1", "pipe2": "구분2", "pipe3": "구분3",
    # === 미국주식 (US) ===
    "frgn_stk_nm": "종목명",
    "stk_enm": "영문명",
    "stex_nm": "거래소",
    "crnc_code": "통화",
    "natn_nm": "국가",
    "mkgb": "거래소명",
    "upgb": "업종",
    "poss_qty": "보유수량",
    "sell_alowq": "매도가능",
    "frgn_stk_book_uv": "매입단가",
    "now_pric": "현재가",
    "evlt_amt_krw": "평가금액(원)",
    "pl_amt_krw": "손익금액(원)",
    "now_pric_krw": "현재가(원)",
    "frgn_stk_book_uv_krw": "매입단가(원)",
    "frgn_stk_book_amt": "매입금액",
    "frgn_stk_book_amt_krw": "매입금액(원)",
    "fc_entra": "외화예수금",
    "fc_uncl_amt": "외화미수금",
    "krw_entra": "원화예수금",
    "won_entr": "원화예수금",
    "trst_prof_ch": "사용증거금",
    "usd_exch_rate": "매도환율(USD)",
    "exch_rate": "환율",
    "aplc_exrt": "적용환율",
    "sell_aplc_exrt": "매도적용환율",
    "buy_aplc_exrt": "매수적용환율",
    "exrt_tp_nm": "환율구분",
    "exrt_spcl_rt": "환율우대율",
    "sell_expc_amt": "매도예상금액",
    "buy_expc_amt": "매수예상금액",
    "frgn_trde_nm": "매매구분",
    "slby_tp_nm": "매도수구분",
    "ord_stat": "주문상태",
    "ord_time": "주문시간",
    "ord_cntr_tp": "주문종류",
    "tot_prch_amt": "총매입금액",
    "tot_pl_amt": "총손익금액",
    "tot_pl_rt": "총수익률",
    "tdy_pl_amt": "당일실현손익",
    "tot_evlt_amt_krw": "총평가금액(원)",
    "tot_prch_amt_krw": "총매입금액(원)",
    "tot_pl_amt_krw": "총손익금액(원)",
}


def _get_label(key: str) -> str:
    """Get Korean label for an API field key, with _n suffix fallback."""
    label = _FIELD_LABELS.get(key)
    if label:
        return label
    if key.endswith("_n") and len(key) > 2:
        return _FIELD_LABELS.get(key[:-2], key)
    return key


def print_generic_table(data: dict[str, Any] | list, title: str = "결과") -> None:
    """Generic formatter for any API response. Respects --format option."""
    fmt = _get_format()

    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        if isinstance(data, list):
            _output_csv(data)
        elif isinstance(data, dict):
            # Flatten: output lists first, then scalars
            lists = {k: v for k, v in data.items() if isinstance(v, list)}
            if lists:
                for lv in lists.values():
                    _output_csv(lv)
            else:
                _output_csv(_flat_dict(data))
        return

    # Table mode (default)
    if isinstance(data, list):
        if not data:
            console.print("[dim]데이터가 없습니다.[/]")
            return
        all_keys = list(dict.fromkeys(k for item in data[:_TABLE_ROW_CAP] for k in item))
        keys = [
            k for k in all_keys
            if any(str(item.get(k, "")).strip() for item in data[:_TABLE_ROW_CAP])
        ]
        if not keys:
            keys = all_keys

        t = Table(title=title, border_style="dim", show_lines=False)
        for k in keys:
            label = _get_label(k)
            justify = "right" if k in (
                "cur_prc", "pred_pre", "flu_rt", "trde_qty", "trde_amt",
                "open_pric", "high_pric", "low_pric", "close_pric",
                "ord_qty", "ord_uv", "rmnd_qty", "avg_prc", "evlt_amt",
                "pl_amt", "pl_rt", "acc_trde_qty", "cntr_trde_qty",
                "now_trde_qty", "pre_rt",
            ) else "left"
            t.add_column(label, justify=justify)
        for item in data[:_TABLE_ROW_CAP]:
            row = []
            for k in keys:
                v = str(item.get(k, ""))
                if _needs_fmt(k, v):
                    row.append(_smart_fmt(v, k))
                else:
                    row.append(v)
            t.add_row(*row)
        console.print(t)
        if len(data) > _TABLE_ROW_CAP:
            console.print(
                f"[dim]{len(data)}행 중 {_TABLE_ROW_CAP}행 표시 — 전체 데이터는 -f json 또는 -f csv 사용[/]"
            )
    elif isinstance(data, dict):
        scalar = {k: v for k, v in data.items() if not isinstance(v, (list, dict)) and k not in ("return_code", "return_msg")}
        lists = {k: v for k, v in data.items() if isinstance(v, list)}

        if scalar:
            t = Table(title=title, show_header=False, border_style="dim")
            t.add_column("항목", style="cyan", width=25)
            t.add_column("값", width=35)
            for k, v in scalar.items():
                label = _get_label(k)
                sv = str(v)
                if _needs_fmt(k, sv):
                    sv = _smart_fmt(sv, k)
                t.add_row(label, sv)
            console.print(t)

        for list_key, list_val in lists.items():
            list_title = _get_label(list_key)
            print_generic_table(list_val, title=list_title)


def print_deposit(data: dict[str, Any]) -> None:
    """Format deposit info (kt00001)."""
    fmt = _get_format()
    if fmt == "json":
        _output_json(data)
        return
    if fmt == "csv":
        _output_csv(_flat_dict(data))
        return
    t = Table(title="💵 예수금 상세현황", show_header=False, border_style="dim")
    t.add_column("항목", style="cyan", width=25)
    t.add_column("금액", width=20, justify="right")

    fields = [
        ("entr", "예수금"),
        ("ord_alow_amt", "주문가능금액"),
        ("pymn_alow_amt", "출금가능금액"),
        ("profa_ch", "주식증거금현금"),
        ("repl_amt", "대용금평가액"),
        ("ch_uncla", "현금미수금"),
        ("ch_uncla_tot", "현금미수금합계"),
    ]
    for key, label in fields:
        val = data.get(key, "")
        if val:
            t.add_row(label, _fmt_number(val))
    console.print(t)


def print_unified_balance(kr_data: dict[str, Any] | None, us_data: dict[str, Any] | None) -> None:
    """국내(kt00004) + 미국(ust21070) 통합 계좌 평가현황."""
    fmt = _get_format()
    if fmt == "json":
        _output_json({"kr": kr_data, "us": us_data})
        return
    if fmt == "csv":
        keys = [
            "market", "symbol", "name", "qty", "avg_price", "cur_price",
            "eval_amt", "pl_amt", "pl_rt", "currency", "eval_krw", "pl_krw",
        ]
        rows: list[dict] = []
        if kr_data:
            for h in kr_data.get("stk_acnt_evlt_prst", []) or []:
                rows.append({
                    "market": "KR",
                    "symbol": h.get("stk_cd", ""),
                    "name": h.get("stk_nm", ""),
                    "qty": h.get("rmnd_qty", ""),
                    "avg_price": h.get("avg_prc", ""),
                    "cur_price": h.get("cur_prc", ""),
                    "eval_amt": h.get("evlt_amt", ""),
                    "pl_amt": h.get("pl_amt", ""),
                    "pl_rt": h.get("pl_rt", ""),
                    "currency": "KRW",
                    "eval_krw": h.get("evlt_amt", ""),
                    "pl_krw": h.get("pl_amt", ""),
                })
        if us_data:
            for h in _find_list(us_data) or []:
                rows.append({
                    "market": "US",
                    "symbol": h.get("stk_cd", ""),
                    "name": h.get("frgn_stk_nm", ""),
                    "qty": h.get("poss_qty", ""),
                    "avg_price": h.get("frgn_stk_book_uv", ""),
                    "cur_price": h.get("now_pric", ""),
                    "eval_amt": h.get("evlt_amt", ""),
                    "pl_amt": h.get("pl_amt", ""),
                    "pl_rt": h.get("pl_rt", ""),
                    "currency": h.get("crnc_code") or "USD",
                    "eval_krw": h.get("evlt_amt_krw", ""),
                    "pl_krw": h.get("pl_amt_krw", ""),
                })
        _output_csv(rows, keys)
        return

    def _pad_int(v: str) -> int:
        try:
            return int(str(v).lstrip("+-").lstrip("0") or "0")
        except ValueError:
            return 0

    table = Table(title="🌏 통합 계좌평가현황", border_style="dim")
    table.add_column("시장", style="dim")
    table.add_column("종목")
    table.add_column("수량", justify="right")
    table.add_column("매입가", justify="right")
    table.add_column("현재가", justify="right")
    table.add_column("평가금액", justify="right")
    table.add_column("손익", justify="right")
    table.add_column("수익률", justify="right")

    if kr_data:
        for h in kr_data.get("stk_acnt_evlt_prst", []) or []:
            pl = h.get("pl_amt", "0")
            color = _sign_color(pl)
            table.add_row(
                "KRX",
                h.get("stk_nm", ""),
                _fmt_number(h.get("rmnd_qty", "")),
                _fmt_number(h.get("avg_prc", "")),
                _fmt_number(h.get("cur_prc", ""), strip_sign=True),
                f"₩{_fmt_number(h.get('evlt_amt', ''))}",
                Text(_fmt_number(pl), style=color),
                Text(h.get("pl_rt", "0") + "%", style=color),
            )
    if us_data:
        for h in _find_list(us_data) or []:
            pl = h.get("pl_amt", "0")
            color = _sign_color(pl)
            table.add_row(
                h.get("stex_nm", "US"),
                h.get("frgn_stk_nm", "") or h.get("stk_cd", ""),
                _fmt_number(h.get("poss_qty", ""), strip_sign=True),
                f"${_fmt_usd(h.get('frgn_stk_book_uv', ''), strip_sign=True)}",
                f"${_fmt_usd(h.get('now_pric', ''), strip_sign=True)}",
                f"${_fmt_usd(h.get('evlt_amt', ''))}\n(₩{_fmt_number(h.get('evlt_amt_krw', ''))})",
                Text(
                    f"{_fmt_usd(pl)}\n(₩{_fmt_number(h.get('pl_amt_krw', ''))})",
                    style=color,
                ),
                Text(h.get("pl_rt", "0") + "%", style=color),
            )
    console.print(table)

    # 소계 + 원화 총계
    kr_total = _pad_int(kr_data.get("tot_est_amt", "0")) if kr_data else 0
    us_total_krw = _pad_int(us_data.get("tot_evlt_amt_krw", "0")) if us_data else 0
    summary = Table(show_header=False, border_style="dim")
    summary.add_column("항목", style="cyan", width=20)
    summary.add_column("값", justify="right")
    if kr_data:
        _, kr_pl_str, kr_pl_rt, kr_color = _calc_eval_pl(kr_data)
        summary.add_row("KRW 소계", Text(f"₩{kr_total:,} ({kr_pl_str})", style=kr_color))
    if us_data:
        us_pl = us_data.get("tot_pl_amt", "0")
        us_color = _sign_color(us_pl)
        summary.add_row(
            "USD 소계",
            Text(
                f"${_fmt_usd(us_data.get('tot_evlt_amt', '0'))} ({_fmt_usd(us_pl)})",
                style=us_color,
            ),
        )
    summary.add_row("총평가액 (KRW)", Text(f"₩{kr_total + us_total_krw:,}", style="bold"))
    console.print(summary)
