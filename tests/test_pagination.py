"""전역 --next-key / --all-pages 페이지네이션 계약 테스트 (client 레벨, pytest-httpx)."""

from __future__ import annotations

import click
import pytest

from kiwoom_cli.client import KiwoomClient


@pytest.fixture
def client(httpx_mock):
    c = KiwoomClient(domain="https://mock.test", token="test-token")
    yield c, httpx_mock
    c.close()


def _page(items, cont=""):
    return {
        "json": {"acnt_evlt_prst": items, "return_code": 0},
        "headers": {"cont-yn": "Y" if cont else "N", "next-key": cont},
    }


def test_all_pages_merges_lists(client):
    c, httpx_mock = client
    p1, p2 = _page([{"n": "1"}], cont="K2"), _page([{"n": "2"}])
    httpx_mock.add_response(json=p1["json"], headers=p1["headers"])
    httpx_mock.add_response(json=p2["json"], headers=p2["headers"])
    ctx = click.Context(click.Command("x"), obj={"all_pages": True})
    with ctx:
        data, headers = c.request("kt00004", {"qry_tp": "0"})
    assert [r["n"] for r in data["acnt_evlt_prst"]] == ["1", "2"]
    assert headers["cont-yn"] != "Y"
    assert ctx.obj["last_cont"] is None


def test_next_key_injected_once(client):
    c, httpx_mock = client
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    ctx = click.Context(click.Command("x"), obj={"next_key": "CURSOR1"})
    with ctx:
        c.request("kt00004", {})
        c.request("kt00004", {})   # 두 번째 요청에는 주입되지 않아야 함
    reqs = httpx_mock.get_requests()
    assert reqs[0].headers.get("next-key") == "CURSOR1"
    assert reqs[0].headers.get("cont-yn") == "Y"
    assert "next-key" not in reqs[1].headers


def test_explicit_cursor_beats_ctx(client):
    c, httpx_mock = client
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    ctx = click.Context(click.Command("x"), obj={"next_key": "CTX"})
    with ctx:
        c.request("kt00004", {}, cont_yn="Y", next_key="EXPLICIT")
    assert httpx_mock.get_requests()[0].headers.get("next-key") == "EXPLICIT"
    assert ctx.obj["next_key"] == "CTX"   # 소비되지 않음


def test_internal_request_skips_global_cursor(client):
    c, httpx_mock = client
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    httpx_mock.add_response(json={"return_code": 0}, headers={"cont-yn": "N", "next-key": ""})
    ctx = click.Context(click.Command("x"), obj={"next_key": "CURSOR1"})
    with ctx:
        c.request("usa10098", {}, internal=True)   # 판별 보조 호출 — 커서 미소비
        c.request("usa20100", {})                  # 본 조회가 커서를 소비
    reqs = httpx_mock.get_requests()
    assert "next-key" not in reqs[0].headers
    assert reqs[1].headers.get("next-key") == "CURSOR1"
    assert reqs[1].headers.get("cont-yn") == "Y"


def test_internal_request_skips_all_pages(client):
    c, httpx_mock = client
    p = _page([{"n": "1"}], cont="K2")
    httpx_mock.add_response(json=p["json"], headers=p["headers"])
    ctx = click.Context(click.Command("x"), obj={"all_pages": True})
    with ctx:
        data, headers = c.request("usa10098", {}, internal=True)
    assert len(httpx_mock.get_requests()) == 1     # 반복 조회 없음
    assert headers["cont-yn"] == "Y"


def test_all_pages_cap_stops_at_50(client, capsys):
    c, httpx_mock = client
    for i in range(50):
        p = _page([{"n": str(i)}], cont=f"K{i + 1}")
        httpx_mock.add_response(json=p["json"], headers=p["headers"])
    ctx = click.Context(click.Command("x"), obj={"all_pages": True})
    with ctx:
        data, headers = c.request("kt00004", {})
    assert len(httpx_mock.get_requests()) == 50    # 1 + 49회 반복에서 상한
    assert len(data["acnt_evlt_prst"]) == 50
    assert headers["cont-yn"] == "Y"               # 상한 도달 — meta.cont로 계속 가능
    assert "상한" in capsys.readouterr().err


def test_internal_request_does_not_record_last_cont(client):
    c, httpx_mock = client
    p1 = _page([{"n": "1"}], cont="MAIN_CURSOR")
    p2 = _page([{"n": "2"}], cont="AUX_CURSOR")
    httpx_mock.add_response(json=p1["json"], headers=p1["headers"])
    httpx_mock.add_response(json=p2["json"], headers=p2["headers"])
    ctx = click.Context(click.Command("x"), obj={})
    with ctx:
        c.request("kt00004", {})                     # 본 조회가 last_cont 기록
        c.request("usa10098", {}, internal=True)     # 보조 호출은 덮어쓰지 않음
    assert ctx.obj["last_cont"] == {"next_key": "MAIN_CURSOR"}
