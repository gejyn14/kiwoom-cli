"""Tests for kiwoom_cli.auth — keyring-backed token storage."""

import keyring

from kiwoom_cli import auth


def test_save_token_stores_in_keyring():
    auth.save_token("abc123", profile="test-profile")
    assert keyring.get_password(auth.KEYRING_SERVICE, "test-profile:token") == "abc123"
