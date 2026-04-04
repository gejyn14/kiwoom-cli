"""Tests for SecureStore encrypted credential storage."""
from kiwoom_cli.secure_store import SecureStore, SecureStoreLocked
import pytest

@pytest.fixture
def store(tmp_path, monkeypatch):
    """Create a SecureStore with a temporary keyring backend."""
    import keyring
    # Use a dict-based in-memory backend for testing
    store = SecureStore("test-service")
    _data = {}
    monkeypatch.setattr(keyring, "get_password", lambda svc, key: _data.get(f"{svc}:{key}"))
    monkeypatch.setattr(keyring, "set_password", lambda svc, key, val: _data.__setitem__(f"{svc}:{key}", val))
    monkeypatch.setattr(keyring, "delete_password", lambda svc, key: _data.pop(f"{svc}:{key}", None))
    return store

def test_setup_and_unlock(store):
    store.setup("mypassword")
    assert store.is_initialized
    store.lock()
    assert not store.is_unlocked
    assert store.unlock("mypassword")
    assert store.is_unlocked

def test_wrong_password(store):
    store.setup("correct")
    store.lock()
    assert not store.unlock("wrong")

def test_set_get_roundtrip(store):
    store.setup("pass123")
    store.set("appkey", "secret-value-123")
    store.set("secretkey", "another-secret")
    assert store.get("appkey") == "secret-value-123"
    assert store.get("secretkey") == "another-secret"

def test_locked_access_raises(store):
    store.setup("pass")
    store.set("key", "val")
    store.lock()
    with pytest.raises(SecureStoreLocked):
        store.get("key")
    with pytest.raises(SecureStoreLocked):
        store.set("key", "val2")

def test_get_nonexistent_returns_none(store):
    store.setup("pass")
    assert store.get("nonexistent") is None

def test_delete(store):
    store.setup("pass")
    store.set("key", "val")
    store.delete("key")
    assert store.get("key") is None
