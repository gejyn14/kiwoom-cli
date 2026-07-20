"""환전 명령 (account exchange) — ust31300/ust31301/ust31302."""

from __future__ import annotations

import click
from rich.panel import Panel

from ...client import KiwoomClient
from ...formatters import human, print_generic_table
from .._mutation import confirm_gate, suppress_pagination

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


# 환전금액 하한. ust31300/ust31302 스펙상 fc_exmn_amt는 "매도통화기준 환전금액"
# (Length 12, ust31302에서는 Required=Y)이며 음수·0은 의미가 없다 — 이전에는
# `-500000`이 fc_exmn_amt="-500000"으로 그대로 전송되고 확인 패널은 이를
# "-500,000원"으로 정상인 양 렌더링했다.
#
# kwcli는 이 필드에 대해 침묵한다: 키움이 배포하는 CLI에는 미국 API가 단 하나도
# 없어(ust*/usa* 0건) 환전 명령 자체가 존재하지 않는다. 침묵은 "무엇이든
# 허용된다"는 근거가 아니므로, 근거는 워크북 스펙과 도메인 의미에 둔다.
_AMOUNT = click.IntRange(min=1)


@exchange_group.command("estimate")
@click.argument("amount", type=_AMOUNT)
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
@click.argument("amount", type=_AMOUNT)
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
    suppress_pagination()  # 환전은 실제 자금 이동 — --all-pages로 재전송하면 안 됨 (감사 N6)
    with KiwoomClient() as c:
        data, _ = c.request("ust31302", {
            "exch_tp": DIRECTION[direction],
            "fc_exmn_amt": str(amount),
        })
        print_generic_table(data, title="환전 신청 결과")
