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


def test_client_init_loads_from_config_and_auth(monkeypatch):
    from kiwoom_cli import client as client_mod
    monkeypatch.setattr(client_mod.config, "get_domain", lambda profile=None: "https://mock.test")
    monkeypatch.setattr(client_mod.auth, "load_token", lambda profile=None: "stored-token")
    c = client_mod.KiwoomClient()
    try:
        assert c.domain == "https://mock.test"
        assert c.token == "stored-token"
    finally:
        c.close()


def test_issue_token_saves_and_returns(mock_client, monkeypatch):
    client, httpx_mock = mock_client
    from kiwoom_cli import client as client_mod
    saved = {}
    monkeypatch.setattr(
        client_mod.auth, "save_token",
        lambda t, profile=None: saved.update({"token": t, "profile": profile}),
    )
    httpx_mock.add_response(
        url="https://mock.test/oauth2/token",
        json={"token": "new-token-xyz", "return_code": 0},
    )
    token = client.issue_token(appkey="ak123", secretkey="sk456")
    assert token == "new-token-xyz"
    assert client.token == "new-token-xyz"
    assert saved["token"] == "new-token-xyz"
    req = httpx_mock.get_request()
    body = req.content.decode()
    assert "ak123" in body and "sk456" in body
    assert "client_credentials" in body


def test_revoke_token_clears_state(mock_client, monkeypatch):
    client, httpx_mock = mock_client
    from kiwoom_cli import client as client_mod
    monkeypatch.setattr(client_mod.config, "get_appkey", lambda profile=None: "ak123")
    monkeypatch.setattr(client_mod.config, "get_secretkey", lambda profile=None: "sk456")
    deleted = {}
    monkeypatch.setattr(
        client_mod.auth, "delete_token",
        lambda profile=None: deleted.update({"called": True, "profile": profile}),
    )
    httpx_mock.add_response(
        url="https://mock.test/oauth2/revoke",
        json={"return_code": 0},
    )
    client.revoke_token()
    assert client.token is None
    assert deleted["called"] is True
