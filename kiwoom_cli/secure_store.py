"""Secure credential store with system password verification.

Credentials are encrypted with a key derived from the system password,
then stored in the OS keychain. Even if keychain is accessed directly
(e.g. via keyring.get_password), the values are encrypted and useless
without the system password.

Usage:
    store = SecureStore("my-app")
    store.setup("password123")          # Initialize with system password
    store.set("appkey", "secret-value") # Encrypt + store in keychain
    store.unlock("password123")         # Unlock for this session
    value = store.get("appkey")         # Decrypt + return
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets

import keyring


class SecureStoreError(Exception):
    pass


class SecureStoreLocked(SecureStoreError):
    pass


class SecureStore:
    """Encrypted credential store backed by OS keychain.

    Values are encrypted with AES-like XOR cipher keyed by a password-derived
    key. The encryption key never touches disk — it exists only in memory
    after unlock.
    """

    def __init__(self, service: str):
        self.service = service
        self._key: bytes | None = None

    @property
    def is_initialized(self) -> bool:
        """Check if store has been set up (salt exists)."""
        return keyring.get_password(self.service, "_salt") is not None

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    def setup(self, password: str) -> None:
        """Initialize the store with a password. Generates a new salt."""
        salt = secrets.token_hex(32)
        keyring.set_password(self.service, "_salt", salt)
        self._key = self._derive_key(password, salt)
        # Store a verification token to check password correctness later
        verify = self._encrypt(b"kiwoom-cli-verify")
        keyring.set_password(self.service, "_verify", verify)

    def unlock(self, password: str) -> bool:
        """Unlock the store for this session. Returns True if password is correct."""
        salt = keyring.get_password(self.service, "_salt")
        if not salt:
            raise SecureStoreError("Store not initialized. Run: kiwoom config setup")
        self._key = self._derive_key(password, salt)
        # Verify password correctness
        verify = keyring.get_password(self.service, "_verify")
        if not verify:
            return False
        try:
            decrypted = self._decrypt(verify)
            if decrypted != b"kiwoom-cli-verify":
                self._key = None
                return False
            return True
        except Exception:
            self._key = None
            return False

    def lock(self) -> None:
        """Lock the store, clearing the encryption key from memory."""
        self._key = None

    def set(self, name: str, value: str) -> None:
        """Encrypt and store a credential."""
        if not self._key:
            raise SecureStoreLocked("Store is locked. Call unlock() first.")
        encrypted = self._encrypt(value.encode("utf-8"))
        keyring.set_password(self.service, name, encrypted)

    def get(self, name: str) -> str | None:
        """Retrieve and decrypt a credential."""
        if not self._key:
            raise SecureStoreLocked("Store is locked. Call unlock() first.")
        encrypted = keyring.get_password(self.service, name)
        if encrypted is None:
            return None
        try:
            return self._decrypt(encrypted).decode("utf-8")
        except Exception:
            return None

    def delete(self, name: str) -> None:
        """Delete a credential."""
        try:
            keyring.delete_password(self.service, name)
        except keyring.errors.PasswordDeleteError:
            pass

    def _derive_key(self, password: str, salt: str) -> bytes:
        """Derive encryption key from password + salt using PBKDF2."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100_000,
            dklen=32,
        )

    def _encrypt(self, data: bytes) -> str:
        """Encrypt data with the derived key."""
        assert self._key is not None
        iv = os.urandom(16)
        encrypted = bytes(a ^ b for a, b in zip(data, self._expand_key(len(data), iv)))
        payload = {"iv": base64.b64encode(iv).decode(), "data": base64.b64encode(encrypted).decode()}
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def _decrypt(self, token: str) -> bytes:
        """Decrypt data with the derived key."""
        assert self._key is not None
        payload = json.loads(base64.b64decode(token))
        iv = base64.b64decode(payload["iv"])
        encrypted = base64.b64decode(payload["data"])
        return bytes(a ^ b for a, b in zip(encrypted, self._expand_key(len(encrypted), iv)))

    def _expand_key(self, length: int, iv: bytes) -> bytes:
        """Expand key to match data length using HMAC-based stream."""
        result = b""
        counter = 0
        while len(result) < length:
            block = hashlib.sha256(self._key + iv + counter.to_bytes(4, "big")).digest()
            result += block
            counter += 1
        return result[:length]
