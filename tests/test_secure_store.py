"""Tests for SecureStore encrypted credential storage."""
from kiwoom_cli.secure_store import SecureStore, SecureStoreError, SecureStoreLocked
import pytest


@pytest.fixture
def store_data():
    """Shared in-memory dict used by the store fixture."""
    return {}


@pytest.fixture
def store(monkeypatch, store_data):
    """Create a SecureStore with an in-memory keyring backend."""
    import keyring
    store = SecureStore("test-service")
    monkeypatch.setattr(keyring, "get_password", lambda svc, key: store_data.get(f"{svc}:{key}"))
    monkeypatch.setattr(keyring, "set_password", lambda svc, key, val: store_data.__setitem__(f"{svc}:{key}", val))
    monkeypatch.setattr(keyring, "delete_password", lambda svc, key: store_data.pop(f"{svc}:{key}", None))
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


# ============================================================
#  Additional strict coverage
# ============================================================


def test_roundtrip_utf8_value(store):
    """UTF-8 Korean text and emoji values survive encryption roundtrip."""
    store.setup("pass")
    value = "비밀번호🔒테스트"
    store.set("utf8_key", value)
    assert store.get("utf8_key") == value


def test_roundtrip_large_value(store):
    """8 KB value survives roundtrip."""
    store.setup("pass")
    value = "A" * 8192
    store.set("large_key", value)
    assert store.get("large_key") == value


def test_delete_nonexistent_is_noop(store):
    """Deleting a nonexistent key does not raise."""
    store.setup("pass")
    store.delete("never_set")  # should not raise


def test_persistence_across_instances(monkeypatch, store_data):
    """Data stored in one instance is decryptable by a fresh instance with same password."""
    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda svc, key: store_data.get(f"{svc}:{key}"))
    monkeypatch.setattr(keyring, "set_password", lambda svc, key, val: store_data.__setitem__(f"{svc}:{key}", val))
    monkeypatch.setattr(keyring, "delete_password", lambda svc, key: store_data.pop(f"{svc}:{key}", None))

    store_a = SecureStore("persist-test")
    store_a.setup("shared-pw")
    store_a.set("shared_key", "shared-value")

    store_b = SecureStore("persist-test")
    assert store_b.unlock("shared-pw") is True
    assert store_b.get("shared_key") == "shared-value"


def test_resetup_changes_encryption_key(store):
    """Calling setup() twice with different passwords changes the salt."""
    store.setup("password-one")
    store.set("k", "v1")
    original_value = store.get("k")

    # Re-setup with different password generates new salt
    store.setup("password-two")
    # Old ciphertext can no longer be decrypted (new key, different salt)
    # _verify will work because it was re-encrypted, but old "k" won't
    assert store.get("k") is None or store.get("k") != original_value


def test_unlock_before_setup_raises(store):
    """Calling unlock() on un-initialized store raises SecureStoreError."""
    with pytest.raises(SecureStoreError):
        store.unlock("anything")


def test_delete_swallows_keyring_error(monkeypatch, store_data):
    """PasswordDeleteError from keyring.delete_password is silently caught."""
    import keyring
    import keyring.errors

    def failing_delete(svc, key):
        raise keyring.errors.PasswordDeleteError("simulated")

    monkeypatch.setattr(keyring, "get_password", lambda svc, key: store_data.get(f"{svc}:{key}"))
    monkeypatch.setattr(keyring, "set_password", lambda svc, key, val: store_data.__setitem__(f"{svc}:{key}", val))
    monkeypatch.setattr(keyring, "delete_password", failing_delete)

    store = SecureStore("test-service")
    store.delete("anything")  # should not raise
