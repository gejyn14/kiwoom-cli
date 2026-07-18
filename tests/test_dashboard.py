"""Tests for dashboard command formatting (kiwoom_cli/commands/dashboard.py)."""

from __future__ import annotations

from kiwoom_cli.commands.dashboard import _build_movers_table
from kiwoom_cli.output import console


def test_movers_table_strips_direction_sign_from_price(capsys):
    """하락 종목의 현재가는 음수로 표시되지 않는다 (부호는 방향지시자)."""
    console.print(_build_movers_table([{
        "stk_cd": "005930", "stk_nm": "삼성전자",
        "cur_prc": "-68000", "pred_pre": "-1000", "flu_rt": "-1.41",
        "trde_qty": "10000000",
    }]))
    out = capsys.readouterr().out
    assert "-68,000" not in out, "현재가에 방향지시자 부호가 그대로 노출됨"
    assert "68,000" in out
