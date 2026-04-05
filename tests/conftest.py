"""Shared test fixtures.

Provides an in-memory keyring backend for CI environments (Linux)
where no system keyring is available.
"""

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
def keyring_reset():
    """Clear InMemoryKeyring state before and after each test.

    InMemoryKeyring._data is class-level and persists across tests.
    This fixture prevents state bleed between tests.
    """
    InMemoryKeyring._data.clear()
    yield
    InMemoryKeyring._data.clear()
