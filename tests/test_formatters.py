"""Tests for formatters."""

import json

import click
import pytest

from kiwoom_cli.formatters import (
    _fmt_number,
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
