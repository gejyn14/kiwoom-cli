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
])
def test_generic_table_strips_direction_sign_on_newly_classified_abs_fields(capsys, field, raw, expected):
    """Task 3b에서 새로 _ABS_FIELDS에 편입된 필드들도 방향지시자 부호를 노출하지 않는다."""
    print_generic_table([{"stk_cd": "005930", field: raw}])
    out = capsys.readouterr().out
    assert raw not in out, f"{field}에 방향지시자 부호가 그대로 노출됨"
    assert expected in out
