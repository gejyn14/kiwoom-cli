"""Tests for formatters."""

import json

import click
import pytest

from kiwoom_cli.formatters import (
    _CLASSIFIED_FIELDS,
    _CODE_FIELDS,
    _fmt_number,
    _flat_dict,
    _sign_color,
    print_generic_table,
    print_stock_info,
    print_chart_data,
)


def test_fmt_number_with_commas():
    assert _fmt_number("1234567") == "1,234,567"
    assert _fmt_number("+1234567") == "+1,234,567"
    assert _fmt_number("-1234567") == "-1,234,567"


def test_fmt_number_empty():
    assert _fmt_number("") == "-"
    assert _fmt_number("   ") == "-"


def test_fmt_number_small():
    assert _fmt_number("0") == "0"
    assert _fmt_number("42") == "42"


def test_fmt_number_strip_sign_on_fallback():
    """_fmt_number strips the sign even when input can't be parsed numerically."""
    assert _fmt_number("+abc", strip_sign=True) == "abc"
    assert _fmt_number("-abc", strip_sign=True) == "abc"
    # Without strip_sign, the original value is returned unchanged
    assert _fmt_number("+abc") == "+abc"


def test_sign_color_positive():
    assert _sign_color("+100") == "red"
    assert _sign_color("+0.5") == "red"


def test_sign_color_negative():
    assert _sign_color("-100") == "blue"
    assert _sign_color("-0.5") == "blue"


def test_sign_color_zero():
    assert _sign_color("0") == "white"


def _make_ctx(fmt: str):
    """Create a Click context with format setting."""
    ctx = click.Context(click.Command("test"), obj={"format": fmt})
    return ctx


class TestGenericTableJson:
    def test_list_json(self, capsys):
        data = [{"stk_cd": "005930", "stk_nm": "삼성전자"}]
        with _make_ctx("json"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        # 리스트 응답: data.items = 정규화, data.raw = 원본
        assert parsed["data"]["items"][0]["name"] == "삼성전자"
        assert parsed["data"]["items"][0]["symbol"] == "005930"
        assert parsed["data"]["raw"][0]["stk_nm"] == "삼성전자"

    def test_dict_json(self, capsys):
        data = {"stk_cd": "005930", "return_code": 0, "return_msg": "OK"}
        with _make_ctx("json"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["data"]["symbol"] == "005930"
        assert "return_code" not in parsed["data"]["raw"]
        assert "return_code" not in parsed["data"]

    def test_empty_list_json(self, capsys):
        with _make_ctx("json"):
            print_generic_table([], title="test")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["data"] == {"items": [], "raw": []}


class TestGenericTableCsv:
    def test_list_csv(self, capsys):
        data = [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
        with _make_ctx("csv"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        lines = [line.rstrip("\r") for line in out.strip().split("\n")]
        assert lines[0] == "a,b"
        assert lines[1] == "1,2"
        assert lines[2] == "3,4"


class TestGenericTableColumnUnion:
    """감사 확인 #21/N29 — 컬럼 집합을 첫 행 키만으로 정하면 이후 행에만
    존재하는 고유 키가 모든 행에서 사라진다 (테이블·CSV 둘 다)."""

    def test_table_mode_shows_key_unique_to_second_row(self, capsys):
        data = [
            {"a": "1"},
            {"a": "2", "b": "unique-value"},
        ]
        print_generic_table(data, title="test")
        out = capsys.readouterr().out
        assert "unique-value" in out

    def test_csv_mode_shows_key_unique_to_second_row(self, capsys):
        data = [
            {"a": "1"},
            {"a": "2", "b": "unique-value"},
        ]
        with _make_ctx("csv"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        lines = [line.rstrip("\r") for line in out.strip().split("\n")]
        assert lines[0] == "a,b"
        assert lines[1] == "1,"
        assert lines[2] == "2,unique-value"


class TestStockInfoJson:
    def test_json_output(self, capsys):
        data = {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "70000",
            "return_code": 0,
            "return_msg": "OK",
        }
        with _make_ctx("json"):
            print_stock_info(data)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["data"]["name"] == "삼성전자"
        assert parsed["data"]["price"] == 70000  # 문자열 "70000" → int
        assert "return_code" not in parsed["data"]
        assert "return_code" not in parsed["data"]["raw"]


class TestChartDataJson:
    def test_json_output(self, capsys):
        items = [
            {"date": "20260101", "open_pric": "100", "close_pric": "110"},
        ]
        with _make_ctx("json"):
            print_chart_data(items, title="test")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert len(parsed["data"]["items"]) == 1
        assert parsed["data"]["items"][0]["date"] == "20260101"  # date는 dt가 아니므로 통과
        assert parsed["data"]["raw"][0]["open_pric"] == "100"


def test_account_balance_strips_direction_sign_from_price(capsys):
    """하락 종목의 현재가는 음수로 표시되지 않는다 (부호는 방향지시자)."""
    from kiwoom_cli.formatters import print_account_eval
    print_account_eval({
        "entr": "1000000", "tot_pur_amt": "7000000", "tot_est_amt": "6800000",
        "stk_acnt_evlt_prst": [{
            "stk_cd": "A005930", "stk_nm": "삼성전자", "rmnd_qty": "100",
            "avg_prc": "70000", "cur_prc": "-68000", "evlt_amt": "6800000",
            "pl_amt": "-200000", "pl_rt": "-2.86",
        }],
    })
    out = capsys.readouterr().out
    assert "-68,000" not in out, "현재가에 방향지시자 부호가 그대로 노출됨"
    assert "68,000" in out


@pytest.mark.parametrize("raw,expected", [("-980", "980"), ("-85", "85")])
def test_generic_table_strips_sign_on_short_prices(capsys, raw, expected):
    """4자 이하 가격(ELW·저가주)도 방향지시자 부호를 제거한다."""
    print_generic_table([{"stk_cd": "900110", "stk_nm": "저가주", "cur_prc": raw}])
    out = capsys.readouterr().out
    assert raw not in out
    assert expected in out


def test_generic_table_preserves_leading_zero_on_unclassified_code_field(capsys):
    """_ABS_FIELDS/_SIGNED_FIELDS/_USD_FIELDS 어디에도 없는 숫자형 코드 필드(예: 업종코드)는
    수량이 아니므로 길이 게이트를 없애도 앞자리 0이 사라지면 안 된다."""
    print_generic_table([{"inds_cd": "001", "inds_nm": "종합(KOSPI)"}])
    out = capsys.readouterr().out
    assert "001" in out


def test_generic_table_scalar_dict_strips_sign_on_short_price(capsys):
    """스칼라 dict 경로(:827)도 리스트 경로와 동일하게 4자 이하 가격의 부호를 제거한다."""
    print_generic_table({"stk_cd": "900110", "stk_nm": "저가주", "cur_prc": "-85"})
    out = capsys.readouterr().out
    assert "-85" not in out
    assert "85" in out


def test_unified_balance_strips_direction_sign_from_price(capsys):
    """통합 계좌현황(print_unified_balance)의 현재가도 방향지시자 부호를 노출하지 않는다."""
    from kiwoom_cli.formatters import print_unified_balance
    print_unified_balance(
        {
            "tot_pur_amt": "7000000", "tot_est_amt": "6800000",
            "stk_acnt_evlt_prst": [{
                "stk_cd": "A005930", "stk_nm": "삼성전자", "rmnd_qty": "100",
                "avg_prc": "70000", "cur_prc": "-68000", "evlt_amt": "6800000",
                "pl_amt": "-200000", "pl_rt": "-2.86",
            }],
        },
        None,
    )
    out = capsys.readouterr().out
    assert "-68,000" not in out, "현재가에 방향지시자 부호가 그대로 노출됨"
    assert "68,000" in out


# ── Task 3b: _ABS_FIELDS/_SIGNED_FIELDS 분류 누락 (호가·체결가 방향지시자) ──


def test_elw_row_strips_direction_sign_from_quote_and_execution_fields(capsys):
    """버그 재현: ELW 행에서 현재가만 고쳐지고 매도호가/매수호가/체결가는 여전히
    방향지시자 부호(-)가 노출됨 (종목코드 57JBHW 예시). sel_bid/buy_bid/cntr_pric는
    스펙 예시(ka10016/ka10017/ka10024/ka10055 등)에서 +/- 방향지시자가 확인되었다."""
    print_generic_table([{
        "stk_cd": "57JBHW", "cur_prc": "-95",
        "sel_bid": "-96", "buy_bid": "-94", "cntr_pric": "-93",
    }])
    out = capsys.readouterr().out
    for bad in ("-96", "-94", "-93"):
        assert bad not in out, f"{bad}에 방향지시자 부호가 그대로 노출됨"
    assert "96" in out
    assert "94" in out
    assert "93" in out


def test_generic_table_strips_sign_on_cur_prc_n_despite_label_stripping(capsys):
    """_get_label은 '_n' 접미사를 떼고 cur_prc_n을 '현재가'로 표시하지만, 멤버십 검사는
    원본 키(cur_prc_n)로 이뤄져야 한다 (ka20001/ka20009 지수 현재가 짝필드).
    스펙 예시: ka20001 cur_prc_n "-2394.49"."""
    print_generic_table([{"stk_cd": "201060", "cur_prc_n": "-2394.49"}])
    out = capsys.readouterr().out
    assert "-2394.49" not in out and "-2,394.49" not in out
    assert "2,394.49" in out


def test_generic_table_keeps_real_sign_on_pred_pre_n(capsys):
    """pred_pre_n은 전일대비(pred_pre)의 짝필드로, 방향지시자가 아닌 실제 등락폭이므로
    부호를 보존해야 한다 (_SIGNED_FIELDS). 스펙 예시: ka20001 pred_pre_n "-2394.49" 형태."""
    print_generic_table([{"stk_cd": "201060", "pred_pre_n": "-2394.49"}])
    out = capsys.readouterr().out
    assert "-2,394.49" in out, "실제 등락폭 부호가 사라짐"


@pytest.mark.parametrize("field,raw,expected", [
    ("pri_sel_bid_unit", "-96", "96"),
    ("pri_buy_bid_unit", "-94", "94"),
    ("wonju_pric", "-10", "10"),
    ("past_curr_prc", "-70700", "70,700"),
    ("52wk_hgst_pric", "-3001", "3,001"),
    ("52wk_lwst_pric", "-1608", "1,608"),
    ("tdy_high_pric", "-7470", "7,470"),
    ("tdy_low_pric", "-10060", "10,060"),
    ("sel_1th_bid", "-156700", "156,700"),
    ("buy_1th_bid", "-156600", "156,600"),
    ("buy_5th_bid", "+121700", "121,700"),  # Finding 3: asymmetry fix, siblings all signed
])
def test_generic_table_strips_direction_sign_on_newly_classified_abs_fields(capsys, field, raw, expected):
    """Task 3b에서 새로 _ABS_FIELDS에 편입된 필드들도 방향지시자 부호를 노출하지 않는다.

    부호 있는 콤마 포맷(예: "-70,700")까지 명시적으로 검사해야 한다 — 5자리 이상
    값은 미분류 상태에서도 fallback 경로(_needs_fmt의 길이 휴리스틱)를 통해 콤마가
    붙은 "-70,700" 형태로 렌더링된다. 콤마 없는 원본 문자열("-70700")만 검사하면 그
    substring인 콤마 버전이 항상 포함돼 있어 분류 여부와 무관하게 늘 통과하는
    무의미한(vacuous) 테스트가 된다 (리뷰 Finding 1 — 10개 중 7개가 이 상태였음).
    """
    print_generic_table([{"stk_cd": "005930", field: raw}])
    out = capsys.readouterr().out
    sign = raw[0]
    signed_expected = f"{sign}{expected}"
    assert signed_expected not in out, (
        f"{field}에 방향지시자 부호가 포함된 콤마 포맷({signed_expected})이 그대로 노출됨"
    )
    assert expected in out


# ── Task 4: 날짜·시간 필드가 금액처럼 콤마 포매팅됨 (N31) ──


def test_date_and_time_fields_are_not_comma_formatted(capsys):
    """8자리 날짜(YYYYMMDD)/6자리 시각(HHMMSS)이 _needs_fmt의 길이 휴리스틱
    (숫자처럼 보이고 5자 이상)을 통과해 콤마로 묶이면 안 된다."""
    print_generic_table([{"dt": "20260716", "ord_tm": "093012", "cur_prc": "70000"}])
    out = capsys.readouterr().out
    assert "20,260,716" not in out
    assert "20260716" in out
    assert "93,012" not in out
    assert "70,000" in out, "일반 가격 필드의 포매팅은 유지되어야 함"


def test_date_and_time_n_suffixed_fields_are_not_comma_formatted(capsys):
    """_get_label은 '_n' 접미사를 떼고 라벨을 표시하지만(dt_n -> 일자, tm_n -> 시간),
    멤버십 검사(_CODE_FIELDS)는 원본 키로 이뤄진다 — dt/tm만 등록하면 dt_n/tm_n은
    날짜/시간처럼 보이면서 콤마 포매팅에서는 새어나간다 (ka20001/ka20009 지수 짝필드,
    dt_n 예시 "20241122", tm_n 예시 "143000")."""
    print_generic_table([{"stk_cd": "201060", "dt_n": "20241122", "tm_n": "143000"}])
    out = capsys.readouterr().out
    assert "20,241,122" not in out
    assert "20241122" in out
    assert "143,000" not in out
    assert "143000" in out


# ── Task 4b: 리뷰가 지적한 28개 날짜/시간 필드 (sweep 불완전) ──


def test_leading_zero_date_time_fields_are_not_truncated(capsys):
    """가장 심각한 두 케이스: exp_tm/elwexpr_dt/trde_strt_dt는 선행 0을 가진 값이 실제로
    관측된다 (ka50087 exp_tm "085957", ka30012 elwexpr_dt "00000000"/만기 없음 sentinel,
    ka10007 trde_strt_dt "00000000"). _fmt_number는 콤마 포맷 전에 lstrip("0")을 하므로
    분류 누락 시 콤마 형태를 넘어 값 자체가 사라진다("085957"->"85,957", "00000000"->"0")."""
    print_generic_table([{
        "stk_cd": "005930",
        "exp_tm": "085957",
        "elwexpr_dt": "00000000",
        "trde_strt_dt": "00000000",
    }])
    out = capsys.readouterr().out
    assert "85,957" not in out
    assert "085957" in out
    # elwexpr_dt/trde_strt_dt 둘 다 "00000000" 그대로 보여야 한다 — 분류 누락 시
    # lstrip("0")으로 빈 문자열이 되어 "0" 한 글자로 뭉개진다("00000000" 자체가
    # 사라지므로 in-substring 검사만으로 충분히 검증됨).
    assert out.count("00000000") == 2, "elwexpr_dt/trde_strt_dt 둘 다 0으로 뭉개지면 안 됨"


@pytest.mark.parametrize("field,raw", [
    ("bid_req_base_tm", "162000"),  # ka10004/ka10087 호가잔량기준시간
    ("regDay", "20091204"),  # ka10099/ka10100 상장일 (camelCase, legacy 필드명)
    ("bid_tm", "164000"),  # ka10095 호가시간
    ("52wk_hgst_pric_dt", "20241004"),  # ka20001/ka20009/usa20100 52주최고가일
    ("52wk_lwst_pric_dt", "20241031"),  # ka20001/ka20009/usa20100 52주최저가일
    ("oyr_hgst_dt", "20260514"),  # usa20100 연중최고가일
    ("oyr_lwst_dt", "20260330"),  # usa20100 연중최저가일
    ("setl_dt", "20241126"),  # kt00008 결제일자
    ("d0_setl_dt", "20260626"),  # ust21160 D0 국내결제일자
    ("d1_setl_dt", "20260629"),  # ust21160 D1 국내결제일자
    ("d2_setl_dt", "20260630"),  # ust21160 D2 국내결제일자
    ("d3_setl_dt", "20260701"),  # ust21160 D3 국내결제일자
    ("d4_setl_dt", "20260702"),  # ust21160 D4 국내결제일자
    ("bus_dt", "20260624"),  # usa06010/usa06011 영업일자
    ("trde_cntr_proc_time", "172311"),  # ka10054 매매체결처리시각
    ("virelis_time", "172511"),  # ka10054 VI해제시각
    ("sel_scesn_tm", "154706"),  # ka10040/ka10053 매도이탈시간
    ("buy_scesn_tm", "151615"),  # ka10040/ka10053 매수이탈시간
    ("deal_dt", "20260511"),  # kt50032/ust21100 거래일자
    ("sell_dt", "20260611"),  # ust21530 매도일자
    ("exec_dt", "20241216"),  # ka30012 행사일
    ("fin_trde_dt", "20241212"),  # ka30005 최종거래일
    ("flo_dt", "20240320"),  # ka30005 상장일
    ("cnfm_tm", "153045"),  # kt00007/kt50031 확인시간 (desc HH:mm:ss, 예시값은 spec에서 항상 공백 — 대표값)
    ("elwfin_trde_dt", "20241212"),  # ka30012 ELW최종거래일
    ("elwflo_dt", "20240124"),  # ka30012 ELW상장일
    ("elwpay_dt", "20241218"),  # ka30012 ELW지급일
    ("lpsuply_end_dt", "20241212"),  # ka30012 LP공급종료일
    ("lpinitlast_suply_dt", "20241212"),  # ka30005 LP초종공급일
    ("hgst_pric_dt", "20241031"),  # ka10007 최고가일 (desc=YYYYMMDD, spec 예시는 공백 — 대표값)
    ("lwst_pric_dt", "20241031"),  # ka10007 최저가일 (위와 동일 사유)
    ("250hgst_pric_dt", "20241004"),  # ka10001 250최고가일 (desc=YYYYMMDD, spec 예시 자체가 손상됨 — 대표값)
    ("250lwst_pric_dt", "20241031"),  # ka10001 250최저가일 (위와 동일 사유)
    ("ord_dt", "20260605"),  # ust21180 주문일
    ("expires_dt", "20241107083713"),  # au10001 만료일 (14자리 YYYYMMDDHHmmss, raw `kiwoom api au10001` 경유시 노출)
])
def test_task_4b_date_time_fields_are_not_comma_formatted(capsys, field, raw):
    """Task 4b — 리뷰(Finding 2)가 지적한 28개 필드 + 자체 스윕으로 추가 발견한 필드들.
    docs/미국 REST API 문서.xlsx(339시트, 216/217 커버)를 1차 소스로 스펙 Response
    Example/Description을 개별 확인함 — 상세 근거는 task-4b-report.md 참고."""
    print_generic_table([{"stk_cd": "005930", field: raw}])
    out = capsys.readouterr().out
    # _fmt_number가 미분류 상태에서 실제로 만들어낼 값(선행 0 제거 후 콤마 그룹핑)을
    # 그대로 재현해 검사한다 — n자리마다 콤마를 넣는 식의 근사치가 아니라 실제 알고리즘
    # (lstrip("0") or "0" 후 int()의 3자리 콤마 그룹핑)과 동일해야 오탐/누락이 없다.
    bad = f"{int(raw.lstrip('0') or '0'):,}"
    assert bad not in out, f"{field}에 콤마 포맷({bad})이 노출됨"
    assert raw in out


# ── Task 4b 감사 후속조치: 잘못 기각됐던 필드 4건 ──


@pytest.mark.parametrize("field,raw", [
    ("qry_tm", "093015"),  # ka10040/ka10053 조회시간. 형제 필드 qry_dt는 이미 등록돼
    # 있어 둘 다 없으면 같은 오브젝트 안에서 렌더링이 갈린다(qry_dt="20260718"은
    # 원본 그대로, qry_tm="093015"는 "93,015"로 콤마 포맷되는 불일치).
    ("base_pric_tm", "153045"),  # ka90008/ka90013 기준가시간(desc "HHmmss"). 기각
    # 근거였던 ka30001의 "기준가(11/21)" 값은 애초에 isdigit()이 아니라 게이트를
    # 통과하지 못하므로 멤버십과 무관하게 안전 — 기각이 보호하는 건 없었다.
    ("fr_dt", "20241111"),  # kt00016 Request 평가시작일(desc "YYYYMMDD"). 같은 키가
    # ka30012 Response 평가시작일자로도 쓰인다.
    ("to_dt", "20241125"),  # kt00016 Request 평가종료일(desc "YYYYMMDD"). 같은 키가
    # ka30012 Response 평가종료일자로도 쓰인다.
])
def test_audit_fix_rejected_fields_are_not_comma_formatted(capsys, field, raw):
    """리뷰가 지적한 4건 — 이전 라운드가 근거 부족/오독으로 잘못 기각했던 필드.
    qry_tm(Finding 1): qry_dt의 형제 필드인데 누락돼 있었음.
    base_pric_tm(Finding 2): 기각 근거(ka30001의 텍스트 값)가 애초에 isdigit() 게이트를
    통과 못해 기각이 아무것도 보호하지 못했음 — ka90008/ka90013의 실제 HHmmss 값이 노출됨.
    fr_dt/to_dt(Finding 3): "스펙 전체에서 예시값이 채워진 적이 없다"는 기각 코멘트가
    사실과 다름 — kt00016/ust21650 Request에 desc="YYYYMMDD"인 실제 날짜값이 있음."""
    print_generic_table([{"stk_cd": "005930", field: raw}])
    out = capsys.readouterr().out
    bad = f"{int(raw.lstrip('0') or '0'):,}"
    assert bad not in out, f"{field}에 콤마 포맷({bad})이 노출됨"
    assert raw in out


def test_code_fields_and_classified_fields_are_disjoint():
    """_needs_fmt는 _CLASSIFIED_FIELDS 멤버십을 _CODE_FIELDS보다 먼저 검사한다
    (formatters.py의 _needs_fmt 참고) — 두 집합에 동시에 속한 키가 있으면
    _CODE_FIELDS 등록이 조용히 무효화된다. _CODE_FIELDS가 17->55개로 늘어난
    지금, 이 불변식을 명시적으로 지켜야 한다."""
    assert (_CODE_FIELDS & _CLASSIFIED_FIELDS) == frozenset()


# ── Task 21: csv 모드에서 스칼라 요약 블록 소실 (감사 확인 #17/#18/N33) ──


class TestFlatDict:
    """`_flat_dict`은 CSV 출력을 위해 dict 하나를 한 줄짜리 row로 평탄화한다."""

    def test_scalar_only(self):
        assert _flat_dict({"a": "1", "b": "2"}) == [{"a": "1", "b": "2"}]

    def test_drops_return_code_and_msg(self):
        assert _flat_dict({"a": "1", "return_code": 0, "return_msg": "OK"}) == [{"a": "1"}]

    def test_drops_list_values(self):
        assert _flat_dict({"a": "1", "items": [1, 2]}) == [{"a": "1"}]

    def test_recurses_one_level_into_dict_with_dot_prefix(self):
        result = _flat_dict({"acnt_nm": "홍길동", "info": {"entr": "1000000"}})
        assert result == [{"acnt_nm": "홍길동", "info.entr": "1000000"}]

    def test_all_values_are_dicts_still_produces_a_row(self):
        """감사 버그의 핵심: 값이 전부 dict이면 예전엔 []를 반환해 0바이트 출력이 됐다."""
        result = _flat_dict({"info": {"a": "1", "b": "2"}})
        assert result == [{"info.a": "1", "info.b": "2"}]

    def test_recursion_stops_after_one_level(self):
        """명시된 스코프: 한 단계만 재귀 — 중첩 dict/list 안의 dict/list는 버려진다."""
        result = _flat_dict({"info": {"a": "1", "nested": {"x": "1"}, "deep_list": [1]}})
        assert result == [{"info.a": "1"}]

    def test_only_containers_with_no_scalars_returns_empty(self):
        """리스트만 있고 재귀할 dict도 없으면 여전히 빈 리스트 — 호출부가 리스트를 따로 출력한다."""
        assert _flat_dict({"items": [1, 2]}) == []

    def test_empty_dict_returns_empty(self):
        """회귀 고정용 — 빈 dict는 애초에 반복할 게 없으니 [] (falsification 테스트 아님)."""
        assert _flat_dict({}) == []

    def test_dict_of_empty_dicts_returns_empty(self):
        """회귀 고정용 — 중첩 dict가 스칼라를 하나도 안 갖고 있으면 여전히 [] (falsification 테스트 아님)."""
        assert _flat_dict({"info": {}}) == []

    def test_collision_last_write_wins(self):
        """실제 API 데이터에서는 나올 수 없는 형태(dot이 든 리터럴 키)지만, 문서화된
        저하 모드(last-write-wins)를 명시적으로 고정해둔다."""
        result = _flat_dict({"a.x": 1, "a": {"x": 2}})
        assert result == [{"a.x": 2}]


class TestGenericTableCsvScalarSummary:
    """print_generic_table의 csv 분기 — 리스트가 있어도 스칼라/딕트 요약이 사라지면 안 된다."""

    def test_mixed_list_and_scalars_emits_both(self, capsys):
        """account balance류 payload: 계좌 요약(스칼라) + 보유종목(리스트)."""
        data = {
            "acnt_nm": "홍길동",
            "entr": "1000000",
            "stk_acnt_evlt_prst": [{"stk_cd": "005930", "stk_nm": "삼성전자"}],
        }
        with _make_ctx("csv"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        assert "홍길동" in out, "스칼라 요약(계좌명)이 리스트 때문에 통째로 사라짐"
        assert "1000000" in out
        assert "005930" in out
        assert "삼성전자" in out

    def test_mixed_list_and_scalars_summary_comes_first(self, capsys):
        """table 모드(print_generic_table dict 분기)가 이미 스칼라 요약 -> 리스트 순서이므로
        csv 모드도 동일한 순서를 따른다 (기존 관례 일치)."""
        data = {
            "acnt_nm": "홍길동",
            "stk_acnt_evlt_prst": [{"stk_cd": "005930"}],
        }
        with _make_ctx("csv"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        lines = [line.rstrip("\r") for line in out.strip("\n").split("\n")]
        assert lines[0] == "acnt_nm"
        assert lines[1] == "홍길동"

    def test_all_values_are_containers_is_not_zero_bytes(self, capsys):
        """감사 버그의 두번째 절반: dict 값이 전부 dict/list이면 이전엔 0바이트+exit 0이었다."""
        data = {
            "acnt_info": {"acnt_nm": "홍길동", "entr": "1000000"},
        }
        with _make_ctx("csv"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        assert out != "", "스칼라 요약이 전혀 없어 0바이트 출력됨"
        assert "홍길동" in out
        assert "1000000" in out


class TestAccountEvalCsvScalarSummary:
    """print_account_eval의 csv 분기 — 보유종목(리스트)이 있어도 계좌 요약(스칼라)이
    사라지면 안 된다 (감사 브리프의 원래 예시: account balance의 예수금/총매입금액)."""

    def test_holdings_present_emits_both_summary_and_holdings(self, capsys):
        """보유종목이 있는(가장 흔한) 케이스에서도 예수금/총매입금액 요약이 함께 나와야 한다."""
        from kiwoom_cli.formatters import print_account_eval
        data = {
            "acnt_nm": "홍길동",
            "entr": "1000000",
            "tot_pur_amt": "7000000",
            "stk_acnt_evlt_prst": [
                {"stk_cd": "005930", "stk_nm": "삼성전자"},
            ],
        }
        with _make_ctx("csv"):
            print_account_eval(data)
        out = capsys.readouterr().out
        assert "홍길동" in out, "보유종목이 있으면 계좌 요약(계좌명)이 통째로 사라짐"
        assert "1000000" in out, "보유종목이 있으면 예수금 요약이 통째로 사라짐"
        assert "7000000" in out, "보유종목이 있으면 총매입금액 요약이 통째로 사라짐"
        assert "005930" in out
        assert "삼성전자" in out

    def test_summary_comes_before_holdings(self, capsys):
        """print_generic_table csv 분기와 동일한 순서(스칼라 요약 -> 리스트)를 따른다."""
        from kiwoom_cli.formatters import print_account_eval
        data = {
            "acnt_nm": "홍길동",
            "stk_acnt_evlt_prst": [{"stk_cd": "005930"}],
        }
        with _make_ctx("csv"):
            print_account_eval(data)
        out = capsys.readouterr().out
        lines = [line.rstrip("\r") for line in out.strip("\n").split("\n")]
        assert lines[0] == "acnt_nm"
        assert lines[1] == "홍길동"

    def test_no_holdings_still_emits_summary(self, capsys):
        """보유종목이 없는 경우는 dd136aa 이전에도 정상 동작했다 — 회귀가 아님을 확인."""
        from kiwoom_cli.formatters import print_account_eval
        data = {"acnt_nm": "홍길동", "entr": "1000000", "stk_acnt_evlt_prst": []}
        with _make_ctx("csv"):
            print_account_eval(data)
        out = capsys.readouterr().out
        assert "홍길동" in out
        assert "1000000" in out


class TestCsvEmptyBlockSeparator:
    """IMPORTANT 4: 빈 리스트 블록은 아무 것도 안 담고 있어도 구분용 빈 줄을
    하나 남겼다 — 성공 호출인데도 EOF 직전에 빈 레코드가 남는 문제. 또한 두 개
    이상의 비어있지 않은 리스트 블록은 서로 붙어 나왔다 — 헤더 행이 뒤섞인다."""

    def test_empty_list_produces_no_trailing_blank_line(self, capsys):
        """{"a": 1, "items": []}: 요약 뒤에 빈 리스트 때문에 남는 빈 줄이 없어야 한다."""
        data = {"a": 1, "items": []}
        with _make_ctx("csv"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        assert out == "a\r\n1\r\n", f"빈 리스트 블록이 dangling blank line을 남김: {out!r}"

    def test_two_non_empty_lists_separated_by_exactly_one_blank_line(self, capsys):
        """리스트 타입 키가 2개 이상이고 모두 비어있지 않으면, 두 블록 사이에
        빈 줄이 정확히 하나 있어야 한다 (이전엔 이어 붙어 나왔다)."""
        data = {
            "xs": [{"p": 1}],
            "ys": [{"q": 2}],
        }
        with _make_ctx("csv"):
            print_generic_table(data, title="test")
        out = capsys.readouterr().out
        assert out == "p\r\n1\r\n\r\nq\r\n2\r\n", f"블록 사이 구분이 예상과 다름: {out!r}"
