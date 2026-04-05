"""Tests for KiwoomClient."""


import httpx
import pytest

from kiwoom_cli.client import KiwoomClient, KiwoomAPIError


@pytest.fixture
def mock_client(httpx_mock):
    """Create a KiwoomClient pointing at a mock."""
    client = KiwoomClient(domain="https://mock.test", token="test-token")
    yield client, httpx_mock
    client.close()


def test_request_success(mock_client):
    client, httpx_mock = mock_client
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"stk_nm": "삼성전자", "return_code": 0, "return_msg": "OK"},
    )
    data, headers = client.request("ka10001", {"stk_cd": "005930"})
    assert data["stk_nm"] == "삼성전자"


def test_request_api_error(mock_client):
    client, httpx_mock = mock_client
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"return_code": -1, "return_msg": "잘못된 요청입니다"},
    )
    with pytest.raises(KiwoomAPIError) as exc_info:
        client.request("ka10001", {"stk_cd": "INVALID"})
    assert exc_info.value.code == -1
    assert "잘못된 요청" in exc_info.value.msg


def test_request_http_error(mock_client):
    client, httpx_mock = mock_client
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        status_code=500,
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.request("ka10001", {"stk_cd": "005930"})


def test_request_sends_auth_headers(mock_client):
    client, httpx_mock = mock_client
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"return_code": 0},
    )
    client.request("ka10001", {"stk_cd": "005930"})
    req = httpx_mock.get_request()
    assert req.headers["authorization"] == "Bearer test-token"
    assert req.headers["api-id"] == "ka10001"


def test_request_pagination_headers(mock_client):
    client, httpx_mock = mock_client
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"return_code": 0},
        headers={"cont-yn": "Y", "next-key": "abc123"},
    )
    _, resp_headers = client.request("ka10001", {"stk_cd": "005930"})
    assert resp_headers["cont-yn"] == "Y"
    assert resp_headers["next-key"] == "abc123"


def test_request_all_paginates(mock_client):
    client, httpx_mock = mock_client
    # Page 1
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"page": 1, "return_code": 0},
        headers={"cont-yn": "Y", "next-key": "key2"},
    )
    # Page 2
    httpx_mock.add_response(
        url="https://mock.test/api/dostk/stkinfo",
        json={"page": 2, "return_code": 0},
        headers={"cont-yn": "N", "next-key": ""},
    )
    results = client.request_all("ka10001", {"stk_cd": "005930"})
    assert len(results) == 2
    assert results[0]["page"] == 1
    assert results[1]["page"] == 2


def test_request_all_respects_max_pages(mock_client):
    client, httpx_mock = mock_client
    for i in range(2):
        httpx_mock.add_response(
            url="https://mock.test/api/dostk/stkinfo",
            json={"page": i, "return_code": 0},
            headers={"cont-yn": "Y", "next-key": f"key{i+1}"},
        )
    results = client.request_all("ka10001", {"stk_cd": "005930"}, max_pages=2)
    assert len(results) == 2
    assert results[0]["page"] == 0
    assert results[1]["page"] == 1
