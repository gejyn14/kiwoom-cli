"""Tests for kiwoom_cli/normalize.py, --fields projection, and describe."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from kiwoom_cli.normalize import normalize_record, parse_signed
from tests.fakes import FakeKiwoomClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_stock(monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response("ka10001", {
        "stk_cd": "005930",
        "stk_nm": "삼성전자",
        "cur_prc": "+70000",
        "flu_rt": "-1.45",
        "trde_qty": "0012345",
        "return_code": 0,
    })
    monkeypatch.setattr("kiwoom_cli.commands.stock.KiwoomClient", lambda *a, **k: fake)
    return fake


# ============================================================
#  parse_signed
# ============================================================


@pytest.mark.parametrize("raw,expected", [
    ("0", (0, "flat")),
    ("", (None, "flat")),
    ("+0.0012", (0.0012, "up")),      # USD 페니스톡
    ("-1.45", (-1.45, "down")),
    ("+00070000", (70000, "up")),     # 선행 0 제거
    ("70000", (70000, "flat")),       # 부호 없음 = 방향정보 없음
    ("-0", (0, "flat")),              # 0은 부호와 무관하게 flat
    ("abc", (None, "flat")),          # 숫자 아님
    (None, (None, "flat")),
])
def test_parse_signed(raw, expected):
    assert parse_signed(raw) == expected


def test_parse_signed_types():
    """정수는 int, 소수는 float."""
    v, _ = parse_signed("+70000")
    assert isinstance(v, int)
    v, _ = parse_signed("+0.0012")
    assert isinstance(v, float)


# ============================================================
#  normalize_record
# ============================================================


def test_normalize_record_maps_canonical_names():
    out = normalize_record({
        "stk_cd": "005930",
        "stk_nm": "삼성전자",
        "cur_prc": "+70000",
        "flu_rt": "-1.45",
        "pred_pre": "+1000",
        "trde_qty": "0012345",
        "ord_no": "0000777",
    })
    assert out["symbol"] == "005930"
    assert out["name"] == "삼성전자"
    assert out["price"] == 70000                # 부호 제거된 절대값
    assert out["change_direction"] == "up"      # 방향은 동반 키로
    assert out["change_pct"] == -1.45           # _SIGNED_FIELDS: 부호 유지
    assert out["change"] == 1000
    assert out["volume"] == 12345
    assert out["order_no"] == "0000777"         # 코드 필드는 문자열 유지


def test_normalize_record_recurses_into_lists():
    out = normalize_record({
        "stk_acnt_evlt_prst": [
            {"stk_cd": "A005930", "rmnd_qty": "000000000010",
             "avg_prc": "68000", "pl_amt": "-500", "pl_rt": "-0.7"},
        ],
    })
    h = out["stk_acnt_evlt_prst"][0]
    # 잔고 응답의 'A005930'은 시장구분 접두사가 붙은 국내 종목코드다. 여기서
    # 접두사를 벗기지 않으면 이 값을 그대로 --code에 넣은 사용자가 미국 경로로
    # 라우팅된다 (원본은 data.raw에 그대로 남는다).
    assert h["symbol"] == "005930"
    assert h["qty"] == 10
    assert h["avg_price"] == 68000
    assert h["pl_amount"] == -500
    assert h["pl_pct"] == -0.7


@pytest.mark.parametrize("raw,expected", [
    ("A005930", "005930"),   # 영문 1자 + 숫자 6자리 → 접두사 제거
    ("Q123456", "123456"),
    ("005930", "005930"),    # 접두사 없음 → 그대로
    ("NVDA", "NVDA"),        # 미국 티커 — 선행 영문자를 벗기면 VDA가 된다
    ("TSLA", "TSLA"),
    ("F", "F"),              # 1글자 티커 — 무조건 벗기면 빈 문자열이 된다
    ("A", "A"),
    ("BRK.B", "BRK.B"),
    ("A00593", "A00593"),    # 숫자 5자리 → 국내 모양 아님
    ("A0059301", "A0059301"),  # 숫자 7자리
    ("AB005930", "AB005930"),  # 영문 2자
    ("M04020000", "M04020000"),  # 금현물 코드 (영문 1자 + 숫자 8자리)
])
def test_normalize_record_strips_only_kr_market_prefix(raw, expected):
    """접두사 제거는 '영문 1자 + 숫자 6자리' 모양에만 적용된다.

    normalize_ws_values의 '9001' 처리처럼 선행 영문자를 무조건 벗기면
    NVDA -> VDA, F -> '' 로 미국 티커가 깨진다. 그 패턴을 여기로 옮겨오지
    않았는지 티커 쪽 케이스가 감시한다.
    """
    assert normalize_record({"stk_cd": raw})["symbol"] == expected


def test_normalize_record_unknown_keys_pass_through():
    out = normalize_record({"totally_unknown": "xyz", "another": "123"})
    assert out == {"totally_unknown": "xyz", "another": "123"}


def test_normalize_record_datetime_fields():
    out = normalize_record({"dt": "20260716", "cntr_tm": "153045", "tm": "0901"})
    assert out["dt"] == "2026-07-16"
    assert out["cntr_tm"] == "15:30:45+09:00"
    assert out["tm"] == "0901"  # 형식 불일치(4자리)는 원본 유지


def test_normalize_record_14_digit_timestamp():
    out = normalize_record({"cntr_tm": "20260716153045"})
    assert out["cntr_tm"] == "2026-07-16T15:30:45+09:00"


# ============================================================
#  Task 3b classification -> -f json impact (review Finding 2)
#
#  formatters._ABS_FIELDS/_SIGNED_FIELDS feed _NUMERIC_FIELDS here, so every
#  field newly classified in Task 3b also changes -f json output: string ->
#  number, plus a new "<field>_direction" key for _ABS_FIELDS members that
#  carried a sign. This is a breaking change for -f json consumers of these
#  fields (see CHANGELOG "Unreleased").
# ============================================================


def test_normalize_record_task_3b_abs_field_strips_direction_and_types_number():
    """sel_bid (_ABS_FIELDS, Task 3b): string '-96' -> int 96 + sel_bid_direction."""
    out = normalize_record({"sel_bid": "-96"})
    assert out["sel_bid"] == 96
    assert isinstance(out["sel_bid"], int)
    assert out["sel_bid_direction"] == "down"


def test_normalize_record_task_3b_signed_field_keeps_sign_and_types_number():
    """pred_pre_n (_SIGNED_FIELDS, Task 3b): string '-278.47' -> float -278.47, no direction key."""
    out = normalize_record({"pred_pre_n": "-278.47"})
    assert out["pred_pre_n"] == -278.47
    assert isinstance(out["pred_pre_n"], float)
    assert "pred_pre_n_direction" not in out


def test_normalize_record_task_3b_n_family_field_types_number():
    """trde_qty_n (_ABS_FIELDS, Task 3b): string '890' -> int 890 (no sign in source,
    so no direction key — but the string->int type change alone is still breaking
    for -f json consumers who expected a string)."""
    out = normalize_record({"trde_qty_n": "890"})
    assert out["trde_qty_n"] == 890
    assert isinstance(out["trde_qty_n"], int)
    assert "trde_qty_n_direction" not in out

    out_signed = normalize_record({"trde_qty_n": "+890"})
    assert out_signed["trde_qty_n"] == 890
    assert out_signed["trde_qty_n_direction"] == "up"


# ============================================================
#  Envelope integration (data = normalized + raw)
# ============================================================


def test_stock_info_json_has_typed_fields_and_raw(runner, fake_stock):
    result = runner.invoke(cli, ["-f", "json", "stock", "info", "005930"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    data = doc["data"]
    assert data["price"] == 70000 and isinstance(data["price"], int)
    assert data["change_direction"] == "up"
    assert data["change_pct"] == -1.45
    assert data["volume"] == 12345
    assert data["raw"]["cur_prc"] == "+70000"   # 원본 인코딩 보존
    assert "return_code" not in data["raw"]


# ============================================================
#  --fields projection
# ============================================================


def test_fields_projects_data_and_drops_raw(runner, fake_stock):
    result = runner.invoke(
        cli, ["-f", "json", "--fields", "symbol,price", "stock", "info", "005930"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data == {"symbol": "005930", "price": 70000}


def test_fields_projects_list_elements(runner, monkeypatch):
    fake = FakeKiwoomClient()
    fake.set_response("kt00004", {
        "acnt_nm": "테스트",
        "stk_acnt_evlt_prst": [
            {"stk_cd": "005930", "stk_nm": "삼성전자", "rmnd_qty": "10", "pl_amt": "-500"},
            {"stk_cd": "000660", "stk_nm": "SK하이닉스", "rmnd_qty": "3", "pl_amt": "+200"},
        ],
        "return_code": 0,
    })
    monkeypatch.setattr("kiwoom_cli.commands.account.KiwoomClient", lambda *a, **k: fake)

    result = runner.invoke(
        cli,
        ["-f", "json", "--fields", "symbol,qty", "account", "balance", "--market", "kr"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert "raw" not in data
    assert data["stk_acnt_evlt_prst"] == [
        {"symbol": "005930", "qty": 10},
        {"symbol": "000660", "qty": 3},
    ]


# ============================================================
#  describe
# ============================================================


def test_describe_order_buy_json_lists_dry_run(runner):
    result = runner.invoke(cli, ["-f", "json", "describe", "order", "buy"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    spec = doc["data"]
    assert spec["path"] == "kiwoom order buy"
    arg_names = [a["name"] for a in spec["arguments"]]
    assert arg_names == ["code", "qty"]
    all_opts = {o for opt in spec["options"] for o in opt["opts"]}
    assert "--dry-run" in all_opts
    assert "--client-order-id" in all_opts
    assert "--yes" in all_opts
    type_opt = next(o for o in spec["options"] if o["name"] == "order_type")
    assert "limit" in type_opt["choices"]


def test_describe_full_tree_includes_groups(runner):
    result = runner.invoke(cli, ["-f", "json", "describe"])
    assert result.exit_code == 0
    spec = json.loads(result.stdout)["data"]
    assert spec["path"] == "kiwoom"
    names = [s["path"] for s in spec["subcommands"]]
    assert "kiwoom order" in names
    assert "kiwoom stock" in names


def test_describe_unknown_command_is_input_error(runner):
    result = runner.invoke(cli, ["describe", "nope"])
    assert result.exit_code == 1


def test_describe_table_mode_renders(runner):
    result = runner.invoke(cli, ["describe", "order", "validate"])
    assert result.exit_code == 0
    assert "kiwoom order validate" in result.output
