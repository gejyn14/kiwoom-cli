"""Tests for KiwoomClient."""


import httpx
import pytest

from kiwoom_cli import client as client_mod
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


def test_client_init_loads_from_config_and_auth(monkeypatch):
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
    assert deleted["profile"] is None


# ── revoke_token: 어느 토큰을 폐기하고 어느 것을 지우는가 ──────────────
#
# auth.load_token은 KIWOOM_TOKEN을 키체인보다 먼저 반환한다. 예전에는 그
# env 토큰으로 revoke를 보낸 뒤 무조건 키체인의 {profile}:token을 지웠다 —
# 방금 폐기한 것과 다른, 아직 살아 있는 토큰을 지워 폐기 불가능하게 만들었다.


@pytest.fixture
def revoke_setup(monkeypatch, httpx_mock, tmp_path):
    """revoke 호출에 필요한 키/응답만 준비. 토큰 출처는 각 테스트가 정한다."""
    import keyring

    from kiwoom_cli import config

    # CONFIG_FILE을 격리하지 않으면 resolve_profile()이 사용자의 실제
    # ~/.kiwoom/config.toml에서 default_profile을 읽는다 (여기서 실제로
    # "default"가 아닌 값이 나와 테스트가 엉뚱한 키를 보고 있었다).
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(client_mod.config, "get_appkey", lambda profile=None: "ak123")
    monkeypatch.setattr(client_mod.config, "get_secretkey", lambda profile=None: "sk456")
    monkeypatch.delenv("KIWOOM_TOKEN", raising=False)
    keyring.set_password(config.KEYRING_SERVICE, "default:appkey", "ak123")
    httpx_mock.add_response(
        url="https://mock.test/oauth2/revoke", json={"return_code": 0},
    )

    def _keychain_token():
        return keyring.get_password(config.KEYRING_SERVICE, "default:token")

    return _keychain_token


def _revoke(**kwargs):
    client = KiwoomClient(domain="https://mock.test", **kwargs)
    try:
        return client, client.revoke_token()
    finally:
        client.close()


def _posted_token(httpx_mock) -> str:
    import json as _json

    return _json.loads(httpx_mock.get_request().content)["token"]


def test_revoke_env_token_keeps_different_keychain_token(
    revoke_setup, httpx_mock, monkeypatch,
):
    """env O / 키체인 O(다른 값) — 핵심 회귀. env 토큰을 폐기하되 키체인의
    별개 토큰은 건드리지 않는다. 지워버리면 그 토큰은 영영 폐기 불가다."""
    import keyring

    from kiwoom_cli import config

    monkeypatch.setenv("KIWOOM_TOKEN", "env-token")
    keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")

    client, outcome = _revoke()

    assert _posted_token(httpx_mock) == "env-token", "폐기 대상이 env 토큰이 아니다"
    assert revoke_setup() == "keychain-token", "폐기하지 않은 키체인 토큰이 삭제됐다"
    assert outcome["token_source"] == "env"
    assert outcome["keychain_token_deleted"] is False
    assert client.token is None


def test_revoke_env_token_with_empty_keychain(revoke_setup, httpx_mock, monkeypatch):
    """env O / 키체인 X — 키체인 접근이 없는 샌드박스/CI 경로. 조용히 성공."""
    monkeypatch.setenv("KIWOOM_TOKEN", "env-token")

    client, outcome = _revoke()

    assert _posted_token(httpx_mock) == "env-token"
    assert revoke_setup() is None
    assert outcome["token_source"] == "env"
    assert outcome["keychain_token_deleted"] is False


def test_revoke_keychain_token_deletes_it(revoke_setup, httpx_mock):
    """env X / 키체인 O — 기존 동작 유지. 폐기한 그 토큰을 키체인에서 제거."""
    import keyring

    from kiwoom_cli import config

    keyring.set_password(config.KEYRING_SERVICE, "default:token", "keychain-token")

    client, outcome = _revoke()

    assert _posted_token(httpx_mock) == "keychain-token"
    assert revoke_setup() is None, "폐기한 토큰이 키체인에 남았다"
    assert outcome["token_source"] == "keychain"
    assert outcome["keychain_token_deleted"] is True


def test_revoke_without_any_token_raises(revoke_setup, httpx_mock):
    """env X / 키체인 X — 폐기할 것이 없다. 요청도 나가지 않는다."""
    import click as _click

    httpx_mock.reset()
    with pytest.raises(_click.ClickException):
        _revoke()


def test_revoke_env_token_equal_to_keychain_token_deletes_it(
    revoke_setup, httpx_mock, monkeypatch,
):
    """env O / 키체인 O(같은 값) — 키체인이 방금 폐기한 바로 그 토큰을 들고
    있으므로 지운다. 안 지우면 auth status가 죽은 토큰을 유효한 것처럼 보고한다."""
    import keyring

    from kiwoom_cli import config

    monkeypatch.setenv("KIWOOM_TOKEN", "same-token")
    keyring.set_password(config.KEYRING_SERVICE, "default:token", "same-token")

    client, outcome = _revoke()

    assert _posted_token(httpx_mock) == "same-token"
    assert revoke_setup() is None, "폐기한 토큰과 동일한 키체인 항목이 남았다"
    assert outcome["token_source"] == "env"
    assert outcome["keychain_token_deleted"] is True
