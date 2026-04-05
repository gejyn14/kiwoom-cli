"""Tests for kiwoom_cli.auth — keyring-backed token storage."""

import keyring

from kiwoom_cli import auth


def test_save_token_stores_in_keyring():
    auth.save_token("abc123", profile="test-profile")
    assert keyring.get_password(auth.KEYRING_SERVICE, "test-profile:token") == "abc123"


def test_load_token_returns_stored_value():
    auth.save_token("xyz789", profile="test-profile")
    assert auth.load_token(profile="test-profile") == "xyz789"


def test_load_token_returns_none_when_missing():
    assert auth.load_token(profile="nonexistent") is None


def test_delete_token_removes_stored_value():
    auth.save_token("to-delete", profile="test-profile")
    assert auth.load_token(profile="test-profile") == "to-delete"
    auth.delete_token(profile="test-profile")
    assert auth.load_token(profile="test-profile") is None


def test_delete_token_missing_key_is_noop():
    auth.delete_token(profile="never-existed")  # must not raise
