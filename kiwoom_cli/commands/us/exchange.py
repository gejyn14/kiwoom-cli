"""환전 명령 (account exchange) — ust31300/ust31301/ust31302."""

from __future__ import annotations

import click
from rich.panel import Panel

from ...client import KiwoomClient
from ...formatters import human, print_generic_table
from .._mutation import confirm_gate

DIRECTION = {"krw-usd": "1", "usd-krw": "2"}
_DIRECTION_LABELS = {"krw-usd": "원화 → 달러", "usd-krw": "달러 → 원화"}


@click.group("exchange")
def exchange_group():
    """환전 (환율/예상금액/신청)."""


@exchange_group.command("rate")
@click.option("--direction", "direction", default="krw-usd", type=click.Choice(list(DIRECTION)), help="환전 방향")
def fx_rate(direction: str):
    """환율 조회 (ust31301)."""
    with KiwoomClient() as c:
        data, _ = c.request("ust31301", {"exch_tp": DIRECTION[direction]})
        print_generic_table(data, title=f"환율 ({_DIRECTION_LABELS[direction]})")


@exchange_group.command("estimate")
@click.argument("amount", type=int)
@click.option("--direction", "direction", default="krw-usd", type=click.Choice(list(DIRECTION)), help="환전 방향")
def fx_estimate(amount: int, direction: str):
    """환전 예상 금액 조회 (ust31300). AMOUNT는 매도통화 기준."""
    with KiwoomClient() as c:
        data, _ = c.request("ust31300", {
            "exch_tp": DIRECTION[direction],
            "fc_exmn_amt": str(amount),
        })
        print_generic_table(data, title=f"환전 예상 ({_DIRECTION_LABELS[direction]})")


@exchange_group.command("apply")
@click.argument("amount", type=int)
@click.option("--direction", "direction", default="krw-usd", type=click.Choice(list(DIRECTION)), help="환전 방향")
@click.option("--confirm", "--yes", "confirm", is_flag=True, help="확인 프롬프트 없이 실행")
def fx_apply(amount: int, direction: str, confirm: bool):
    """환전 신청 (ust31302). 실제 자금이 이동합니다."""
    unit = "원" if direction == "krw-usd" else "달러"
    human(Panel(
        f"[bold]환전 신청[/]\n\n"
        f"  방향: {_DIRECTION_LABELS[direction]}\n"
        f"  금액: {amount:,}{unit}",
        title="환전 확인",
        border_style="yellow",
    ))
    confirm_gate(confirm)
    with KiwoomClient() as c:
        data, _ = c.request("ust31302", {
            "exch_tp": DIRECTION[direction],
            "fc_exmn_amt": str(amount),
        })
        print_generic_table(data, title="환전 신청 결과")
