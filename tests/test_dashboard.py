"""Tests for dashboard command formatting (kiwoom_cli/commands/dashboard.py)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from kiwoom_cli.client import KiwoomAPIError
from kiwoom_cli.commands.dashboard import _build_movers_table
from kiwoom_cli.main import cli
from kiwoom_cli.output import console
from tests.fakes import FakeKiwoomClient


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


# ============================================================
#  Task 17: partial/total upstream failure must not be reported
#  as success (account.py's _unified_structured is the reference
#  pattern: explicit null for a failed side, fail_api when all fail)
# ============================================================

ACCOUNT_RESPONSE = {
    "return_code": 0,
    "acnt_nm": "테스트",
    "entr": "000001000000",
    "tot_pur_amt": "000007000000",
    "tot_est_amt": "000007230000",
    "aset_evlt_amt": "000008230000",
}

MOVERS_RESPONSE = {
    "return_code": 0,
    "tdy_trde_qty_upper": [
        {
            "stk_cd": "005930", "stk_nm": "삼성전자",
            "cur_prc": "72000", "pred_pre": "1000", "flu_rt": "1.41",
            "trde_qty": "10000000",
        },
    ],
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_client(monkeypatch):
    """Inject FakeKiwoomClient into dashboard module."""
    fake = FakeKiwoomClient()
    monkeypatch.setattr(
        "kiwoom_cli.commands.dashboard.KiwoomClient",
        lambda *args, **kwargs: fake,
    )
    return fake


def _make_selectively_failing(fake, *, fail_account=False, fail_movers=False):
    """Wrap fake.request so kt00004/ka10030 raise KiwoomAPIError on demand."""
    orig = fake.request

    def failing(api_id, body=None, **kw):
        if api_id == "kt00004" and fail_account:
            raise KiwoomAPIError(500, "계좌 조회 실패(테스트)")
        if api_id == "ka10030" and fail_movers:
            raise KiwoomAPIError(500, "거래량 조회 실패(테스트)")
        return orig(api_id, body, **kw)

    fake.request = failing


def test_dashboard_both_fail_exits_2_with_upstream_error(runner, fake_client):
    """양쪽 API 모두 실패하면 exit 2 + error.code == UPSTREAM_ERROR (조용한 성공 금지)."""
    _make_selectively_failing(fake_client, fail_account=True, fail_movers=True)

    result = runner.invoke(cli, ["-f", "json", "dashboard"])

    assert result.exit_code == 2
    doc = json.loads(result.stdout)
    assert doc["ok"] is False
    assert doc["data"] is None
    assert doc["error"]["code"] == "UPSTREAM_ERROR"


def test_dashboard_account_only_fails_reports_explicit_null(runner, fake_client):
    """계좌만 실패하면 data['account']는 None이지만 키 자체는 존재해야 한다."""
    fake_client.set_response("ka10030", MOVERS_RESPONSE)
    _make_selectively_failing(fake_client, fail_account=True, fail_movers=False)

    result = runner.invoke(cli, ["-f", "json", "dashboard"])

    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    assert "account" in doc["data"]
    assert doc["data"]["account"] is None
    assert len(doc["data"]["top_volume"]) == 1


def test_dashboard_both_fail_table_mode_exits_2_on_stderr(runner, fake_client):
    """table 모드에서도 양쪽 모두 실패하면 exit 2 + 빨간 stderr 메시지 (조용한 성공 금지).

    account.py의 _run_unified와 동일한 계약: table 모드도 json/csv와 마찬가지로
    exit 2로 종료해야 한다 (AGENTS.md 179-181, "table 모드도 동일한 경우
    빨간 stderr 메시지와 함께 exit 2로 종료합니다").
    """
    _make_selectively_failing(fake_client, fail_account=True, fail_movers=True)

    result = runner.invoke(cli, ["dashboard"])

    assert result.exit_code == 2
    assert "모두 실패" in result.stderr
    assert result.stdout == ""


def test_dashboard_table_mode_success_renders_both_panels(runner, fake_client):
    """table 모드에서 양쪽 다 성공하면 exit 0 + 계좌 요약/거래량 상위 패널이 모두 렌더링된다."""
    fake_client.set_response("kt00004", ACCOUNT_RESPONSE)
    fake_client.set_response("ka10030", MOVERS_RESPONSE)

    result = runner.invoke(cli, ["dashboard"])

    assert result.exit_code == 0
    assert "계좌 요약" in result.stdout
    assert "당일 거래량 상위" in result.stdout
    assert "삼성전자" in result.stdout


def test_dashboard_table_mode_account_only_fails_degrades_gracefully(runner, fake_client):
    """table 모드에서 계좌만 실패하면 exit 0(2 아님) + stderr 경고 + 거래량 쪽은 정상 렌더링된다."""
    fake_client.set_response("ka10030", MOVERS_RESPONSE)
    _make_selectively_failing(fake_client, fail_account=True, fail_movers=False)

    result = runner.invoke(cli, ["dashboard"])

    assert result.exit_code == 0
    assert "계좌 조회 실패" in result.stderr
    assert "당일 거래량 상위" in result.stdout
    assert "삼성전자" in result.stdout


def test_dashboard_movers_only_fails_reports_explicit_null(runner, fake_client):
    """거래량 상위만 실패하면 data['top_volume']는 None이지만 키 자체는 존재해야 한다 (계좌 실패의 대칭 케이스)."""
    fake_client.set_response("kt00004", ACCOUNT_RESPONSE)
    _make_selectively_failing(fake_client, fail_account=False, fail_movers=True)

    result = runner.invoke(cli, ["-f", "json", "dashboard"])

    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    assert doc["data"]["account"]["acnt_nm"] == "테스트"
    assert "top_volume" in doc["data"]
    assert doc["data"]["top_volume"] is None


def test_dashboard_success_json_shape_unchanged(runner, fake_client):
    """양쪽 다 성공하면 기존 json 모양(account dict + top_volume list)이 유지된다."""
    fake_client.set_response("kt00004", ACCOUNT_RESPONSE)
    fake_client.set_response("ka10030", MOVERS_RESPONSE)

    result = runner.invoke(cli, ["-f", "json", "dashboard"])

    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["ok"] is True
    assert doc["data"]["account"]["acnt_nm"] == "테스트"
    assert len(doc["data"]["top_volume"]) == 1
    assert doc["data"]["top_volume"][0]["name"] == "삼성전자"


# ── D9/H4: dashboard와 market rank volume이 같은 목록을 봐야 한다 ────


def test_dashboard_top_volume_uses_same_exchange_as_market_rank_volume(
    runner, fake_client, monkeypatch,
):
    """dashboard의 ka10030 호출이 `market rank volume` 기본값과 같은 거래소를 쓴다.

    D7이 ka10030의 --exchange 기본값을 통합(3)으로 옮겼을 때 dashboard만
    "1"(KRX)로 하드코딩돼 남았다. 같은 "당일 거래량 상위"가 두 명령에서
    다르게 나오는 상태였다.

    옵션 선언이 아니라 **전송된 body**로 비교한다 — 선언만 보면 커맨드 본문의
    하드코딩을 볼 수 없다.
    """
    fake_client.set_response("kt00004", ACCOUNT_RESPONSE)
    fake_client.set_response("ka10030", MOVERS_RESPONSE)
    assert runner.invoke(cli, ["-f", "json", "dashboard"]).exit_code == 0
    dash_body = dict(next(b for a, b in fake_client.calls if a == "ka10030"))

    market_fake = FakeKiwoomClient()
    market_fake.set_response("ka10030", MOVERS_RESPONSE)
    monkeypatch.setattr(
        "kiwoom_cli.commands.market.KiwoomClient",
        lambda *a, **kw: market_fake,
    )
    assert runner.invoke(cli, ["-f", "json", "market", "rank", "volume"]).exit_code == 0
    rank_body = dict(next(b for a, b in market_fake.calls if a == "ka10030"))

    assert dash_body["stex_tp"] == rank_body["stex_tp"], (
        f"dashboard={dash_body['stex_tp']!r} vs market rank volume="
        f"{rank_body['stex_tp']!r} — 같은 목록이 두 명령에서 갈린다"
    )
    # 남아 있는 차이를 **명시적으로** 고정한다. 조용히 두면 다음 드리프트가
    # "원래 다르던 것"에 섞여 안 보인다. mang_stk_incls 차이는 D7 이전부터
    # 있던 dashboard의 선택이고, 그 외 필드는 전부 같아야 한다.
    assert dash_body["mang_stk_incls"] == "1"   # exclude-managed (dashboard 선택)
    assert rank_body["mang_stk_incls"] == "0"   # include-managed (market 기본값)
    assert {k: v for k, v in dash_body.items() if k != "mang_stk_incls"} == \
           {k: v for k, v in rank_body.items() if k != "mang_stk_incls"}
