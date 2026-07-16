"""Tests for formatters."""

import json

import click

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
