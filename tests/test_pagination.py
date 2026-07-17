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
