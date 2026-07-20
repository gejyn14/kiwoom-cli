"""스트리밍 NDJSON 출력 + 종료 조건 테스트 (실제 websocket 없음)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from kiwoom_cli.main import cli
from kiwoom_cli.normalize import WS_FIELD_NAMES, normalize_ws_values
from kiwoom_cli.streaming import (
    KST,
    _emit_line,
    handle_message,
    new_stream_state,
    parse_duration,
    parse_until,
    should_stop,
)


@pytest.fixture
def runner():
    return CliRunner()


# ── 필드 ID 이름 맵 (공유 상수) ──────────────────────


class TestWsFieldNames:
    def test_map_moved_to_shared_constant(self):
        assert WS_FIELD_NAMES["10"] == "현재가"
        assert WS_FIELD_NAMES["12"] == "등락율"
        assert WS_FIELD_NAMES["908"] == "주문체결시간"


# ── normalize_ws_values ──────────────────────────────


class TestNormalizeWsValues:
    def test_quote_fields_typed_and_named(self):
        out = normalize_ws_values({
            "10": "+70000",
            "11": "+500",
            "12": "+0.72",
            "13": "123456",
            "15": "-10",
            "20": "153000",
            "302": "삼성전자",
        })
        assert out["price"] == 70000
        assert out["change_direction"] == "up"
        assert out["change"] == 500
        assert out["change_pct"] == 0.72
        assert out["acc_volume"] == 123456
        assert out["volume"] == -10  # 15는 부호 유의미 (+매수/-매도)
        assert out["ts"] == "15:30:00+09:00"
        assert out["name"] == "삼성전자"

    def test_abs_field_down_direction(self):
        out = normalize_ws_values({"10": "-70000"})
        assert out["price"] == 70000
        assert out["change_direction"] == "down"

    def test_order_fields_korean_fallback(self):
        out = normalize_ws_values({
            "9001": "A005930",
            "900": "10",
            "910": "+70500",
            "913": "체결",
            "908": "20260716153000",
        })
        assert out["symbol"] == "005930"  # 선행 A 제거
        assert out["주문수량"] == 10
        assert out["체결가"] == 70500
        assert out["주문상태"] == "체결"
        assert out["ts"] == "2026-07-16T15:30:00+09:00"

    def test_empty_string_passes_through(self):
        out = normalize_ws_values({"10": ""})
        assert out["price"] == ""

    def test_unknown_id_passes_through(self):
        out = normalize_ws_values({"9999": "x"})
        assert out["9999"] == "x"


# ── 0D 주식호가잔량 ───────────────────────────────────

# docs/미국 REST API 문서.xlsx 시트 '주식호가잔량(0D)'의 Response Example을
# 그대로 옮긴 것 (kwcli 0.1.1이 동봉한 kiwoom_api_spec.json의 같은 API 항목과
# 필드별로 대조해 일치를 확인했다). 10단계 전체 + 21(호가시간)만 남기고
# 직전대비(81~100)·총잔량·LP·KRX/NXT 계열은 이 청크 범위 밖이라 뺐다.
_SPEC_0D_VALUES = {
    "21": "165207",
    "41": "-20800", "61": "82", "51": "-20700", "71": "23847",
    "42": "+20900", "62": "393", "52": "-20650", "72": "834748",
    "43": "+21000", "63": "674739", "53": "-20600", "73": "2145799",
    "44": "+21050", "64": "2055055", "54": "-20550", "74": "2134689",
    "45": "+21100", "65": "1998461", "55": "-20500", "75": "1982298",
    "46": "+21150", "66": "1932347", "56": "-20450", "76": "1853788",
    "47": "+21200", "67": "1723333", "57": "-20400", "77": "1687992",
    "48": "+21250", "68": "1621835", "58": "-20350", "78": "1467869",
    "49": "+21300", "69": "1373291", "59": "-20300", "79": "1259995",
    "50": "+21350", "70": "1242991", "60": "-20250", "80": "1062405",
    "13": "30379650",
}


def spec_0d_frame(item: str = "005930") -> dict:
    """스펙 Response Example 그대로의 0D REAL 프레임 (서버가 보내는 모양)."""
    return {
        "trnm": "REAL",
        "data": [{
            "type": "0D", "name": "주식호가잔량", "item": item,
            "values": dict(_SPEC_0D_VALUES),
        }],
    }


class TestQuoteBook0D:
    """0D는 21(호가시간)/41~80(10단계 호가·수량)이 전부 미등록이라
    ts=None + 숫자 ID 그대로 + 부호 붙은 가격이 새어나갔다."""

    def test_ts_from_field_21(self):
        out = normalize_ws_values({"21": "165207"})
        assert out["ts"] == "16:52:07+09:00"

    def test_ask_and_bid_are_not_swapped(self):
        """41=매도호가1(ask), 51=매수호가1(bid). 스펙 예시에서 ask는 오름차순
        (20800→21350), bid는 내림차순(20700→20250)이고 ask1 > bid1이다.
        방향을 뒤집으면 이 부등식이 깨진다."""
        out = normalize_ws_values(dict(_SPEC_0D_VALUES))
        asks = [out[f"ask{i}"] for i in range(1, 11)]
        bids = [out[f"bid{i}"] for i in range(1, 11)]
        assert asks == [20800, 20900, 21000, 21050, 21100,
                        21150, 21200, 21250, 21300, 21350]
        assert bids == [20700, 20650, 20600, 20550, 20500,
                        20450, 20400, 20350, 20300, 20250]
        assert asks[0] > bids[0]
        assert asks == sorted(asks) and bids == sorted(bids, reverse=True)

    def test_quantities_typed_and_side_correct(self):
        """61~70=매도호가수량, 71~80=매수호가수량. 값이 서로 다른 1단계로
        측을 판별한다 (82 vs 23847)."""
        out = normalize_ws_values(dict(_SPEC_0D_VALUES))
        assert out["ask_qty1"] == 82
        assert out["bid_qty1"] == 23847
        assert out["ask_qty10"] == 1242991
        assert out["bid_qty10"] == 1062405
        assert all(isinstance(out[f"ask_qty{i}"], int) for i in range(1, 11))
        assert all(isinstance(out[f"bid_qty{i}"], int) for i in range(1, 11))

    def test_prices_are_positive_sign_is_direction(self):
        """41의 '-20800'과 42의 '+20900'은 방향지시자다. 부호를 값으로 믿으면
        1호가가 -20800원이라는 말이 되고 ask 정렬도 뒤집힌다."""
        out = normalize_ws_values(dict(_SPEC_0D_VALUES))
        assert out["ask1"] == 20800, "매도호가1이 음수로 새어나옴"
        assert out["ask2"] == 20900
        assert out["ask1_direction"] == "down"
        assert out["ask2_direction"] == "up"
        assert all(out[f"ask{i}"] > 0 for i in range(1, 11))
        assert all(out[f"bid{i}"] > 0 for i in range(1, 11))

    def test_quantities_are_signed_not_abs(self):
        """수량(61~80)은 _ABS_FIELDS가 아니라 _SIGNED_FIELDS로 분류돼야 한다.

        스펙 값에는 부호가 없어서 두 분류의 동작이 같다 — 그래서 스펙 값만
        넣는 테스트는 분류를 전혀 고정하지 못한다(실제로 ABS로 옮기는 변조가
        전체 테스트를 통과했다). 두 분류가 갈라지는 유일한 입력인 '부호 붙은
        수량'을 일부러 넣어 고정한다. 스펙상 나오지 않는 값이지만, 나왔을 때
        ABS는 abs()로 정보를 버리고 *_direction을 만들어내는 반면 SIGNED는
        값을 그대로 보존한다 — 그 차이가 이 분류를 고른 이유 자체다.
        """
        out = normalize_ws_values({"61": "-82", "71": "+23847"})
        assert out["ask_qty1"] == -82, "수량이 abs()로 뭉개짐 (ABS 분류로 넘어감)"
        assert out["bid_qty1"] == 23847
        qty_dirs = [k for k in out if k.endswith("_direction")]
        assert qty_dirs == [], f"수량에 방향 동반 키가 생김: {qty_dirs}"

    def test_prices_stay_abs_even_when_quantities_are_signed(self):
        """가격(41~60)은 반대로 ABS여야 한다 — 두 분류가 뒤섞이지 않았는지."""
        out = normalize_ws_values({"41": "-20800", "61": "-82"})
        assert out["ask1"] == 20800 and out["ask1_direction"] == "down"
        assert out["ask_qty1"] == -82

    def test_no_bare_numeric_ids_remain(self):
        out = normalize_ws_values(dict(_SPEC_0D_VALUES))
        leftover = sorted(k for k in out if k.isdigit())
        assert leftover == [], f"정규화되지 않은 숫자 ID: {leftover}"

    def test_end_to_end_real_frame(self):
        """서버 프레임 -> handle_message. 정규화된 dict에서 출발하지 않는다."""
        events = handle_message(spec_0d_frame(), {})
        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "0D"
        assert ev["symbol"] == "005930"
        assert ev["ts"] == "16:52:07+09:00", "0D 이벤트 ts가 비어 있음"
        assert ev["ask1"] == 20800 and ev["bid1"] == 20700
        assert ev["ask_qty1"] == 82 and ev["bid_qty1"] == 23847
        assert ev["acc_volume"] == 30379650


# ── FT 미국주식 10호가 ────────────────────────────────

# docs/미국 REST API 문서.xlsx 시트 '미국주식 10호가(FT)'의 Response Example
# 원문. FT는 0D와 **같은 필드 ID 체계**를 쓴다 (21 시간, 41~50 매도N호가,
# 51~60 매수N호가, 61~70 매도N호가잔량, 71~80 매수N호가잔량). 0D와 다른 점은
# 가격이 원화 정수가 아니라 달러 소수(4자리)이고, values 바깥에 거래소코드
# stexTp가 붙는다는 것.
_SPEC_FT_ASKS = ["+198.5400", "+198.6100", "+198.6200", "+198.6300", "+198.6500",
                 "+198.6600", "+198.6700", "+198.6800", "+198.7200", "+198.7400"]
_SPEC_FT_BIDS = ["+198.4800", "+198.4700", "+198.4600", "+198.4500", "+198.4400",
                 "+198.4300", "+198.4200", "+198.4100", "+198.4000", "+198.3700"]
_SPEC_FT_ASK_QTY = ["2", "20", "139", "20", "250", "28", "20", "20", "90", "1"]
_SPEC_FT_BID_QTY = ["22", "1", "2", "115", "16", "20", "1", "118", "122", "20"]

_SPEC_FT_VALUES = {"21": "215300"}
for _i in range(10):
    _SPEC_FT_VALUES[str(41 + _i)] = _SPEC_FT_ASKS[_i]
    _SPEC_FT_VALUES[str(51 + _i)] = _SPEC_FT_BIDS[_i]
    _SPEC_FT_VALUES[str(61 + _i)] = _SPEC_FT_ASK_QTY[_i]
    _SPEC_FT_VALUES[str(71 + _i)] = _SPEC_FT_BID_QTY[_i]
# 직전대비 81~100은 스펙 예시에서 선행 공백이 붙은 " 0"으로 온다 (원문 그대로).
for _i in range(81, 101):
    _SPEC_FT_VALUES[str(_i)] = " 0"
_SPEC_FT_VALUES.update({"121": "590", "122": " 0", "125": "437", "126": " 0"})
del _i


def spec_ft_frame(item: str = "NVDA") -> dict:
    """스펙 Response Example 그대로의 FT REAL 프레임 (서버가 보내는 모양).

    0D와 달리 entry에 stexTp(거래소코드)가 형제 키로 붙는다.
    """
    return {
        "trnm": "REAL",
        "data": [{
            "type": "FT", "name": "미국10호가", "item": item, "stexTp": "ND",
            "values": dict(_SPEC_FT_VALUES),
        }],
    }


class TestQuoteBookFT:
    """FT(미국주식 10호가). 필드 ID는 0D와 완전히 같아 D2에서 이미 매핑됐고,
    남은 결함은 US 고유 요소(타입명 미등록, 거래소코드 유실)다."""

    def test_ft_reuses_0d_field_id_layout(self):
        """FT와 0D가 같은 ID를 공유한다는 사실 자체를 고정한다.

        누군가 한쪽만 보고 41~80을 재배치하면 다른 쪽이 조용히 망가진다.
        분류 상수는 api_id 문맥이 없으므로 이 공유는 되돌릴 수 없는 결합이다.
        """
        from kiwoom_cli.normalize import WS_CANONICAL
        for i in range(10):
            assert WS_CANONICAL[str(41 + i)] == f"ask{i + 1}"
            assert WS_CANONICAL[str(51 + i)] == f"bid{i + 1}"
            assert WS_CANONICAL[str(61 + i)] == f"ask_qty{i + 1}"
            assert WS_CANONICAL[str(71 + i)] == f"bid_qty{i + 1}"
        assert WS_CANONICAL["21"] == "ts"

    def test_ask_and_bid_not_swapped_numerically(self):
        """한글 필드명만 믿지 않고 값으로 검증한다 (0D와 같은 판정 기준).
        매도는 오름차순, 매수는 내림차순, ask1 > bid1."""
        out = normalize_ws_values(dict(_SPEC_FT_VALUES))
        asks = [out[f"ask{i}"] for i in range(1, 11)]
        bids = [out[f"bid{i}"] for i in range(1, 11)]
        assert asks == [198.54, 198.61, 198.62, 198.63, 198.65,
                        198.66, 198.67, 198.68, 198.72, 198.74]
        assert bids == [198.48, 198.47, 198.46, 198.45, 198.44,
                        198.43, 198.42, 198.41, 198.40, 198.37]
        assert asks[0] > bids[0], "ask1이 bid1보다 낮다 — 매도/매수가 뒤바뀜"
        assert asks == sorted(asks), "매도호가가 오름차순이 아님"
        assert bids == sorted(bids, reverse=True), "매수호가가 내림차순이 아님"

    def test_decimal_prices_survive_as_floats(self):
        """0D(원화 정수)와 달리 FT는 달러 소수다. int로 뭉개지면 안 된다."""
        out = normalize_ws_values(dict(_SPEC_FT_VALUES))
        assert isinstance(out["ask1"], float)
        assert out["ask1"] == 198.54

    def test_sub_cent_precision_not_truncated(self):
        """페니 주식($0.0012)의 4자리 소수가 2자리로 잘리면 안 된다.
        정규화 경로는 문자열이 아니라 float를 내므로 소수 자릿수가 보존된다."""
        out = normalize_ws_values({"41": "+0.0012", "51": "+0.0011"})
        assert out["ask1"] == 0.0012
        assert out["bid1"] == 0.0011

    def test_quantities_are_ints(self):
        out = normalize_ws_values(dict(_SPEC_FT_VALUES))
        assert out["ask_qty1"] == 2 and out["bid_qty1"] == 22
        assert all(isinstance(out[f"ask_qty{i}"], int) for i in range(1, 11))
        assert all(isinstance(out[f"bid_qty{i}"], int) for i in range(1, 11))

    def test_type_name_is_resolved(self):
        """REALTIME_TYPES에 FT가 없어 모든 US 호가 이벤트가 '?'로 나갔다."""
        ev = handle_message(spec_ft_frame(), {})[0]
        assert ev["type_name"] != "?", "FT 타입명이 REALTIME_TYPES에 없음"
        assert ev["type_name"] == "미국주식 10호가"

    def test_exchange_code_preserved(self):
        """stexTp(거래소코드)는 values 바깥 형제 키라 handle_message가 통째로
        버렸다. 미국주식은 같은 티커가 거래소별로 갈리므로 유실되면 안 된다."""
        ev = handle_message(spec_ft_frame(), {})[0]
        assert ev.get("exchange") == "ND", "거래소코드(stexTp)가 유실됨"

    def test_korean_frame_has_no_exchange_key(self):
        """국내 프레임에는 stexTp가 없다 — 없는데 키를 만들어내면 안 된다."""
        ev = handle_message(spec_0d_frame(), {})[0]
        assert "exchange" not in ev

    def test_ft_is_not_advertised_as_subscribable(self):
        """FT는 표시 전용이다 — 구독 가능 목록에 넣으면 안 된다.

        run_stream은 /api/dostk/websocket에 고정돼 있고 US 실시간은
        /api/us/websocket이라 프레임이 오지 않는다. REALTIME_TYPES에 넣으면
        `stream custom FT`가 검증을 통과해 국내 소켓에서 무한정 매달린다.
        두 맵을 합치면 이 테스트가 깨진다.
        """
        from kiwoom_cli.streaming import REALTIME_TYPES, US_REALTIME_TYPES
        assert "FT" not in REALTIME_TYPES, "FT가 구독 가능 목록에 들어감"
        assert "FT" in US_REALTIME_TYPES
        assert not (set(REALTIME_TYPES) & set(US_REALTIME_TYPES)), "두 맵이 겹침"
        # `stream custom FT`는 여전히 거부돼야 한다 (지원하지 않는 것이 사실이므로)
        result = CliRunner().invoke(cli, ["stream", "custom", "FT", "NVDA"])
        assert result.exit_code != 0
        assert "FT" in result.output

    def test_end_to_end_real_frame(self):
        """서버 프레임 -> handle_message. 정규화된 dict에서 출발하지 않는다."""
        events = handle_message(spec_ft_frame(), {})
        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "FT"
        assert ev["type_name"] == "미국주식 10호가"
        assert ev["symbol"] == "NVDA"
        assert ev["exchange"] == "ND"
        assert ev["ts"] == "21:53:00+09:00"
        assert ev["ask1"] == 198.54 and ev["bid1"] == 198.48
        assert ev["ask_qty1"] == 2 and ev["bid_qty1"] == 22
        assert not [k for k in ev if k.isdigit() and 41 <= int(k) <= 80]


# ── handle_message ────────────────────────────────────


def _real_msg(values=None, type_code="0B", item="005930"):
    return {
        "trnm": "REAL",
        "data": [{"type": type_code, "item": item, "values": values or {"10": "+70000"}}],
    }


class TestHandleMessage:
    def test_real_message_normalized_event(self):
        state = new_stream_state()
        events = handle_message(_real_msg({"10": "+70000", "12": "+0.72", "20": "153000"}), state)
        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "0B"
        assert ev["type_name"] == "주식체결"
        assert ev["symbol"] == "005930"
        assert ev["ts"] == "15:30:00+09:00"
        assert ev["price"] == 70000
        assert ev["change_pct"] == 0.72
        assert state["event_count"] == 1

    def test_ping_returns_empty(self):
        state = new_stream_state()
        assert handle_message({"trnm": "PING"}, state) == []
        assert state["event_count"] == 0

    def test_system_returns_empty(self):
        state = new_stream_state()
        assert handle_message({"trnm": "SYSTEM", "message": "hi", "code": "0"}, state) == []

    def test_registration_ack_returns_empty(self):
        state = new_stream_state()
        assert handle_message({"trnm": "REG", "return_code": 0}, state) == []

    def test_values_as_list_unwrapped(self):
        state = new_stream_state()
        msg = {"trnm": "REAL", "data": [{"type": "0B", "item": "005930", "values": [{"10": "+100"}]}]}
        events = handle_message(msg, state)
        assert events[0]["price"] == 100

    def test_symbol_falls_back_to_9001(self):
        state = new_stream_state()
        msg = {"trnm": "REAL", "data": [{"type": "00", "item": "", "values": {"9001": "A005930"}}]}
        events = handle_message(msg, state)
        assert events[0]["symbol"] == "005930"

    def test_max_events_truncates_entries(self):
        state = new_stream_state(max_events=3)
        entries = [{"type": "0B", "item": "005930", "values": {"10": "+1"}}] * 5
        events = handle_message({"trnm": "REAL", "data": entries}, state)
        assert len(events) == 3
        assert state["event_count"] == 3


# ── parse_duration / parse_until ─────────────────────


class TestParseDuration:
    @pytest.mark.parametrize("text,expected", [("30s", 30), ("5m", 300), ("2h", 7200)])
    def test_valid(self, text, expected):
        assert parse_duration(text) == expected

    @pytest.mark.parametrize("text", ["abc", "5x", "", "s", "1.5h", "-30s"])
    def test_invalid_raises_usage_error(self, text):
        with pytest.raises(click.UsageError):
            parse_duration(text)


class TestParseUntil:
    def test_naive_assumes_kst(self):
        dt = parse_until("2026-07-16T16:00:00")
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=9)

    def test_explicit_offset_preserved(self):
        dt = parse_until("2026-07-16T16:00:00+00:00")
        assert dt.utcoffset() == timedelta(0)

    def test_invalid_raises_usage_error(self):
        with pytest.raises(click.UsageError):
            parse_until("not-a-date")


# ── 종료 조건 (new_stream_state / should_stop) ───────


class TestStopConditions:
    def test_no_conditions_never_stops(self):
        state = new_stream_state()
        state["event_count"] = 1000
        assert should_stop(state, now=datetime.now(KST)) is False

    def test_max_events_reached(self):
        state = new_stream_state(max_events=3)
        state["event_count"] = 3
        assert should_stop(state) is True
        state["event_count"] = 2
        assert should_stop(state) is False

    def test_duration_deadline(self):
        base = datetime(2026, 7, 16, 15, 0, 0, tzinfo=KST)
        state = new_stream_state(duration="30s", now=base)
        assert state["deadline"] == base + timedelta(seconds=30)
        assert should_stop(state, now=base + timedelta(seconds=29)) is False
        assert should_stop(state, now=base + timedelta(seconds=30)) is True

    def test_until_deadline(self):
        base = datetime(2026, 7, 16, 15, 0, 0, tzinfo=KST)
        state = new_stream_state(until="2026-07-16T16:00:00", now=base)
        assert should_stop(state, now=base) is False
        assert should_stop(state, now=datetime(2026, 7, 16, 16, 0, 0, tzinfo=KST)) is True

    def test_duration_and_until_earliest_wins(self):
        base = datetime(2026, 7, 16, 15, 0, 0, tzinfo=KST)
        state = new_stream_state(duration="30s", until="2026-07-16T16:00:00", now=base)
        assert state["deadline"] == base + timedelta(seconds=30)


# ── NDJSON 출력 (_emit_line) ─────────────────────────


class TestEmitLine:
    def test_event_is_single_compact_line(self, capsys):
        _emit_line({"type": "0B", "price": 70000}, meta={})
        out = capsys.readouterr().out
        assert out.count("\n") == 1
        doc = json.loads(out)
        assert doc["ok"] is True
        assert doc["schema"] == "v1"
        assert doc["data"]["price"] == 70000
        assert doc["error"] is None
        assert "raw" not in doc["data"]

    def test_fields_projection(self, capsys):
        _emit_line({"type": "0B", "price": 70000, "volume": 5}, meta={}, fields=["price"])
        doc = json.loads(capsys.readouterr().out)
        assert doc["data"] == {"price": 70000}

    def test_error_line(self, capsys):
        from kiwoom_cli.envelope import error_body

        _emit_line(error=error_body("연결 종료", code="UPSTREAM_ERROR", retryable=True), meta={})
        doc = json.loads(capsys.readouterr().out)
        assert doc["ok"] is False
        assert doc["data"] is None
        assert doc["error"]["code"] == "UPSTREAM_ERROR"


# ── done-check 하네스: --max-events 3 → 정확히 3줄 ───


class TestMaxEventsHarness:
    def test_three_events_three_lines_then_stop(self, capsys):
        state = new_stream_state(max_events=3)
        stopped = False
        for _ in range(5):  # 3개 이후 도착하는 메시지는 소비되지 않아야 함
            events = handle_message(_real_msg(), state)
            for ev in events:
                _emit_line(ev, meta={})
            if should_stop(state):
                stopped = True
                break
        assert stopped
        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
        assert len(lines) == 3
        for ln in lines:
            doc = json.loads(ln)
            assert doc["ok"] is True
            assert doc["data"]["type"] == "0B"
            assert doc["data"]["price"] == 70000


# ── CLI 옵션 배선 ─────────────────────────────────────


class TestStreamCommandOptions:
    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_quote_passes_stop_options(self, mock_run, runner):
        result = runner.invoke(cli, [
            "-f", "json", "stream", "quote", "005930",
            "--max-events", "3", "--duration", "30s", "--until", "2026-07-16T16:00:00",
        ])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["0B"], ["005930"],
            raw=False, max_events=3, duration="30s", until="2026-07-16T16:00:00",
            record=None,
        )

    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_account_command_has_options(self, mock_run, runner):
        result = runner.invoke(cli, ["stream", "order", "--max-events", "1"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["00"], [], raw=False, max_events=1, duration=None, until=None,
            record=None,
        )

    @patch("kiwoom_cli.commands.stream.run_stream")
    def test_custom_passes_types_and_options(self, mock_run, runner):
        result = runner.invoke(cli, ["stream", "custom", "0B,0D", "005930", "--duration", "5m"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["0B", "0D"], ["005930"],
            raw=False, max_events=None, duration="5m", until=None,
            record=None,
        )

    def test_bad_duration_exits_1_before_connecting(self, runner):
        result = runner.invoke(cli, ["stream", "quote", "005930", "--duration", "abc"])
        assert result.exit_code == 1

    def test_bad_max_events_exits_1(self, runner):
        result = runner.invoke(cli, ["stream", "quote", "005930", "--max-events", "0"])
        assert result.exit_code == 1


# ============================================================
#  Task 22: LOGIN/REG 핸드셰이크 — 실패 감지, 종료 코드, 프레임 순서
#
#  실측(.superpowers/sdd/task-22-login-frame-evidence.md):
#    LOGIN 응답 = {"trnm":"LOGIN","return_code":805004,"return_msg":"..."}
#    return_code는 int. code/message는 SYSTEM 프레임에만 있다.
#    prod는 LOGIN 응답 뒤에 SYSTEM 프레임을 보내지만 mock은 보내지 않는다.
# ============================================================

LOGIN_OK = {"trnm": "LOGIN", "return_code": 0, "return_msg": "정상"}
LOGIN_FAIL = {
    "trnm": "LOGIN",
    "return_code": 805004,
    "return_msg": "토큰 인증에 실패했습니다. 접속을 종료합니다 [CODE=8005, MESSAGE=Token이 유효하지 않습니다]",
}
SYSTEM_FRAME = {"trnm": "SYSTEM", "code": "R10004", "message": "접속허용요청(토큰)이 들어오지 않았습니다"}
REG_OK = {"trnm": "REG", "return_code": 0, "return_msg": "정상"}
REG_FAIL = {"trnm": "REG", "return_code": 1, "return_msg": "등록 종목수 초과"}


@pytest.fixture
def ws_env(monkeypatch):
    """가짜 websockets 모듈 + 토큰/도메인 고정. 실제 소켓·키체인·config 접근 없음."""
    import sys

    from tests.fakes import FakeWebsocketsModule, FakeWebSocket

    def _install(frames, *, connect_exc=None, **ws_kwargs):
        ws = FakeWebSocket(frames, **ws_kwargs)
        monkeypatch.setitem(
            sys.modules, "websockets", FakeWebsocketsModule(ws, connect_exc=connect_exc)
        )
        return ws

    monkeypatch.setattr(
        "kiwoom_cli.streaming.resolve_ws_target", lambda: ("default", "wss://test.invalid")
    )
    monkeypatch.setattr("kiwoom_cli.streaming.auth.load_token", lambda profile=None: "tok")
    return _install


def _run(runner, ws_env, frames, *, fmt="table"):
    ws_env(frames)
    args = ["stream", "quote", "005930"]
    if fmt != "table":
        args = ["-f", fmt, *args]
    return runner.invoke(cli, args)


class TestStreamLoginFailure:
    def test_table_mode_exits_auth(self, runner, ws_env):
        """인증 실패는 table 모드에서도 exit 3 (기존: return_code를 못 읽어 '인증 성공' 후 exit 0)."""
        result = _run(runner, ws_env, [LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "인증 실패" in result.output
        assert "8005" in result.output
        assert "인증 성공" not in result.output

    def test_json_mode_exits_auth_with_envelope(self, runner, ws_env):
        result = _run(runner, ws_env, [LOGIN_FAIL], fmt="json")
        assert result.exit_code == 3, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs, result.output
        assert docs[-1]["ok"] is False
        assert docs[-1]["error"]["code"] == "AUTH_REQUIRED"

    def test_return_code_is_int_not_string(self, runner, ws_env):
        """실측상 return_code는 int다. 문자열 비교(rc != "0")로 짜면 성공도 실패로 읽힌다."""
        result = _run(runner, ws_env, [LOGIN_OK, REG_OK])
        assert result.exit_code == 0, result.output
        assert "인증 성공" in result.output

    def test_string_return_code_also_accepted(self, runner, ws_env):
        result = _run(runner, ws_env, [{"trnm": "LOGIN", "return_code": "0"}, REG_OK])
        assert result.exit_code == 0, result.output
        assert "인증 성공" in result.output


class TestStreamLoginFrameOrder:
    def test_system_frame_before_login_ack_is_skipped(self, runner, ws_env):
        """prod 전용 동작: SYSTEM이 먼저 와도 LOGIN ack를 놓치지 않는다.

        SYSTEM을 ack로 오독해도 exit 3이 나오므로 종료 코드만으로는 구분되지 않는다.
        실제로 뒤의 LOGIN 프레임을 읽었는지는 return_msg 내용(8005)으로 고정한다.
        """
        result = _run(runner, ws_env, [SYSTEM_FRAME, LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "인증 실패" in result.output
        assert "8005" in result.output, "SYSTEM 프레임을 LOGIN ack로 오독했다"
        assert "시스템: 접속허용요청" in result.output, "건너뛴 SYSTEM 프레임이 표시되지 않았다"

    def test_ping_before_login_ack_is_echoed_and_skipped(self, runner, ws_env):
        ws = ws_env([{"trnm": "PING"}, LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 0, result.output
        assert "인증 성공" in result.output
        assert ws.sent_trnms() == ["LOGIN", "PING", "REG"]

    def test_skip_loop_is_bounded(self, runner, ws_env):
        """서버가 SYSTEM만 계속 보내도 매달리지 않고 인증 오류로 끝난다."""
        ws = ws_env([SYSTEM_FRAME] * 40 + [LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 3, result.output
        assert ws.frames, "건너뛰기 루프가 큐 전체를 소비했다 = 상한이 없다"


class TestStreamRegistrationFailure:
    def test_table_mode_exits_api(self, runner, ws_env):
        """등록 실패는 table 모드에서도 exit 2 (기존: 빨간 글씨 후 continue → 미구독 소켓)."""
        result = _run(runner, ws_env, [LOGIN_OK, REG_FAIL])
        assert result.exit_code == 2, result.output
        assert "등록 종목수 초과" in result.output

    def test_json_mode_exits_api(self, runner, ws_env):
        result = _run(runner, ws_env, [LOGIN_OK, REG_FAIL], fmt="json")
        assert result.exit_code == 2, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["error"]["code"] == "UPSTREAM_ERROR"

    def test_success_path_streams_real_events(self, runner, ws_env):
        result = _run(runner, ws_env, [LOGIN_OK, REG_OK, _real_msg()], fmt="json")
        assert result.exit_code == 0, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["data"]["price"] == 70000


class TestStreamMissingToken:
    def test_table_mode_exits_auth(self, runner, ws_env, monkeypatch):
        """토큰 없음도 table/json 양쪽에서 exit 3 (기존 table: 메시지 후 exit 0)."""
        ws_env([])
        monkeypatch.setattr("kiwoom_cli.streaming.auth.load_token", lambda profile=None: None)
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 3, result.output
        assert "토큰이 없습니다" in result.output

    def test_json_mode_exits_auth(self, runner, ws_env, monkeypatch):
        ws_env([])
        monkeypatch.setattr("kiwoom_cli.streaming.auth.load_token", lambda profile=None: None)
        result = runner.invoke(cli, ["-f", "json", "stream", "quote", "005930"])
        assert result.exit_code == 3, result.output


# ============================================================
#  Chunk D1 리뷰 수정 — 바깥 예외 핸들러의 종료 코드 (F1/F2/F3/F5)
#
#  이전에는 table 모드가 ConnectionClosed / ConnectionRefusedError / 일반 예외
#  모두에서 (0, None)을 반환했다. json 모드만 2를 내서 $?로 분기하는 쪽에는
#  거부된 연결과 예기치 못한 오류가 '성공한 스트림'으로 보였다.
# ============================================================


class TestStreamOuterExceptionExitCodes:
    def test_connection_refused_exits_api_table(self, runner, ws_env):
        """거부된 연결은 table 모드에서도 exit 2 (기존: 메시지만 찍고 exit 0)."""
        ws_env([], connect_exc=ConnectionRefusedError("refused"))
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 2, result.output
        assert "WebSocket 연결 실패" in result.output

    def test_connection_refused_exits_api_json(self, runner, ws_env):
        ws_env([], connect_exc=ConnectionRefusedError("refused"))
        result = runner.invoke(cli, ["-f", "json", "stream", "quote", "005930"])
        assert result.exit_code == 2, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["error"]["code"] == "NETWORK_ERROR"

    def test_unexpected_exception_exits_api_table(self, runner, ws_env):
        """예기치 못한 예외도 table 모드에서 exit 2 (기존: exit 0)."""
        result = _run(runner, ws_env, [LOGIN_OK, REG_OK, ValueError("깨진 소켓")])
        assert result.exit_code == 2, result.output
        assert "깨진 소켓" in result.output

    def test_unexpected_exception_exits_api_json(self, runner, ws_env):
        result = _run(runner, ws_env, [LOGIN_OK, REG_OK, ValueError("깨진 소켓")], fmt="json")
        assert result.exit_code == 2, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["error"]["code"] == "UPSTREAM_ERROR"

    def test_abnormal_close_exits_api_table(self, runner, ws_env):
        """1006 같은 비정상 종료는 정상 종료와 달리 실패다 (ConnectionClosedError)."""
        from tests.fakes import FakeConnectionClosedError

        result = _run(
            runner, ws_env,
            [LOGIN_OK, REG_OK, _real_msg(), FakeConnectionClosedError("1006 abnormal")],
        )
        assert result.exit_code == 2, result.output
        assert "비정상" in result.output or "연결 종료" in result.output

    def test_abnormal_close_exits_api_json(self, runner, ws_env):
        from tests.fakes import FakeConnectionClosedError

        result = _run(
            runner, ws_env,
            [LOGIN_OK, REG_OK, FakeConnectionClosedError("1006 abnormal")],
            fmt="json",
        )
        assert result.exit_code == 2, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["error"]["code"] == "UPSTREAM_ERROR"

    def test_normal_close_in_recv_loop_exits_zero(self, runner, ws_env):
        """F5 대조군: 서버의 정상 종료는 수신 루프가 직접 처리해 exit 0으로 끝난다.

        이게 통과해야 위 EXIT_API 갈래들이 '정상 종료까지 실패로 만든 것'이 아님이
        증명된다. (구현자가 바깥 핸들러 수정을 미룬 근거가 바로 이 경로였는데,
        수신 루프가 ConnectionClosedOK를 이미 잡고 break하므로 근거가 성립하지 않는다.)
        """
        result = _run(runner, ws_env, [LOGIN_OK, REG_OK, _real_msg()])
        assert result.exit_code == 0, result.output

    def test_normal_close_on_ping_echo_exits_zero(self, runner, ws_env):
        """수신 루프 밖(PING 에코 send)의 정상 종료는 바깥 OK 갈래가 0으로 처리한다."""
        from tests.fakes import FakeConnectionClosedOK

        ws_env(
            [LOGIN_OK, REG_OK, {"trnm": "PING"}],
            send_exc=FakeConnectionClosedOK("1000 bye"),
            fail_send_after=2,  # LOGIN·REG 전송은 성공, PING 에코에서 닫힘
        )
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 0, result.output

    def test_abnormal_close_on_ping_echo_exits_api(self, runner, ws_env):
        """같은 자리라도 비정상 종료면 2. OK/Error를 한 갈래로 합치면 위 테스트와 충돌한다."""
        from tests.fakes import FakeConnectionClosedError

        ws_env(
            [LOGIN_OK, REG_OK, {"trnm": "PING"}],
            send_exc=FakeConnectionClosedError("1006 abnormal"),
            fail_send_after=2,
        )
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 2, result.output


class TestStreamHandshakeClose:
    """F2: 서버가 LOGIN에 답하지 않고 끊으면 인증되지 않은 세션이다 → 절대 exit 0 금지."""

    def test_handshake_close_exits_auth_table(self, runner, ws_env):
        result = _run(runner, ws_env, [])  # 첫 recv부터 ConnectionClosedOK
        assert result.exit_code == 3, result.output
        assert "인증 응답을 받기 전에 연결이 끊겼습니다" in result.output
        assert "인증 성공" not in result.output

    def test_handshake_close_exits_auth_json(self, runner, ws_env):
        result = _run(runner, ws_env, [], fmt="json")
        assert result.exit_code == 3, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        assert docs[-1]["error"]["code"] == "AUTH_REQUIRED"

    def test_handshake_close_after_system_frame_still_auth(self, runner, ws_env):
        """SYSTEM만 한 줄 던지고 끊는 실제 prod 거절 패턴."""
        result = _run(runner, ws_env, [SYSTEM_FRAME])
        assert result.exit_code == 3, result.output


class TestStreamHandshakeBuffering:
    """F4: ack 전에 도착한 데이터 프레임을 버리지 않는다."""

    def test_real_frame_before_login_ack_is_not_lost(self, runner, ws_env):
        result = _run(
            runner, ws_env,
            [_real_msg({"10": "+99999"}), LOGIN_OK, REG_OK],
            fmt="json",
        )
        assert result.exit_code == 0, result.output
        docs = [json.loads(ln) for ln in result.output.splitlines() if ln.startswith("{")]
        prices = [d["data"]["price"] for d in docs if d.get("data")]
        assert 99999 in prices, "핸드셰이크 중 도착한 REAL 프레임이 버려졌다"

    def test_ping_budget_is_separate_from_chatter_budget(self, runner, ws_env):
        """F8: 킵얼라이브 PING 10번이 잡담 예산을 소진해 인증 실패가 나면 안 된다."""
        ws = ws_env([{"trnm": "PING"}] * 10 + [LOGIN_OK, REG_OK])
        result = runner.invoke(cli, ["stream", "quote", "005930"])
        assert result.exit_code == 0, result.output
        assert "인증 성공" in result.output
        assert ws.sent_trnms().count("PING") == 10


class TestStreamAckSlotDiscipline:
    """F7: 다른 자리의 ack를 이 자리 ack로 소비하지 않는다."""

    def test_reg_ack_is_not_consumed_as_login_ack(self, runner, ws_env):
        """REG 응답이 LOGIN 자리에 오면 그걸 인증 결과로 읽지 않고 진짜 LOGIN을 기다린다."""
        result = _run(runner, ws_env, [REG_FAIL, LOGIN_FAIL])
        assert result.exit_code == 3, result.output
        assert "8005" in result.output, "REG 프레임을 LOGIN ack로 오독했다"
        assert "인증 실패: 등록 종목수 초과" not in result.output
