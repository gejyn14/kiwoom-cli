"""Shared test fixtures.

Provides an in-memory keyring backend for CI environments (Linux)
where no system keyring is available, and neutralizes the developer's
own KIWOOM_* environment so the suite never reads real credentials.
"""

import os

import keyring
import pytest
from keyring.backend import KeyringBackend


class InMemoryKeyring(KeyringBackend):
    """Simple in-memory keyring for testing."""

    priority = 100  # High priority to override system backends
    _data: dict[str, dict[str, str]] = {}

    def set_password(self, servicename: str, username: str, password: str) -> None:
        self._data.setdefault(servicename, {})[username] = password

    def get_password(self, servicename: str, username: str) -> str | None:
        return self._data.get(servicename, {}).get(username)

    def delete_password(self, servicename: str, username: str) -> None:
        if servicename in self._data:
            self._data[servicename].pop(username, None)


# Set as default backend before any test runs
keyring.set_keyring(InMemoryKeyring())


@pytest.fixture(autouse=True)
def clean_kiwoom_env(monkeypatch):
    """KIWOOM_* 환경변수를 매 테스트 시작 전에 지운다.

    InMemoryKeyring이 OS 키체인을 대신하는 것과 같은 이유다: 테스트가 실행하는
    사람의 실제 설정을 읽으면 안 된다. v2.15.0에서 appkey/secretkey가 환경변수를
    지원하게 되자 개발자 셸에 떠 있던 KIWOOM_APPKEY가 즉시 12개 테스트를
    깨뜨렸다 — 종전에는 그 변수들이 코드에서 무시됐기 때문에 우연히 조용했다.

    환경변수 동작을 검증하는 테스트는 monkeypatch.setenv로 직접 설정한다
    (autouse 픽스처가 먼저 돌고 테스트 본문이 나중에 덮으므로 문제없다).
    """
    for name in [k for k in os.environ if k.startswith("KIWOOM_")]:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def keyring_reset():
    """Clear InMemoryKeyring state before and after each test.

    InMemoryKeyring._data is class-level and persists across tests.
    This fixture prevents state bleed between tests.
    """
    InMemoryKeyring._data.clear()
    yield
    InMemoryKeyring._data.clear()
