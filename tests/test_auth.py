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
