"""stream/watch가 --profile과 KIWOOM_DOMAIN을 REST 경로와 동일하게 존중하는지 검증."""

from __future__ import annotations

import click
import pytest

from kiwoom_cli import config, streaming


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


def test_get_domain_key_env_wins(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "prod")
    assert config.get_domain_key() == "prod"


def test_get_domain_key_invalid_env_forces_mock(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "nonsense")
    assert config.get_domain_key() == "mock"


def test_get_domain_still_matches_key(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "prod")
    assert config.get_domain() == config.DOMAINS["prod"]


def test_resolve_ws_target_honors_env(isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_DOMAIN", "prod")
    profile, ws_url = streaming.resolve_ws_target()
    assert profile == "default"
    assert ws_url == streaming.WS_DOMAINS["prod"]


def test_resolve_ws_target_uses_ctx_profile(isolated_config):
    cfg_file = config.CONFIG_FILE
    cfg_file.write_bytes(
        b'[general]\ndefault_profile = "default"\n\n'
        b'[profiles.default]\ndomain = "mock"\n\n'
        b'[profiles.live]\ndomain = "prod"\n'
    )
    ctx = click.Context(click.Command("stream"), obj={"profile": "live"})
    with ctx:
        profile, ws_url = streaming.resolve_ws_target()
    assert profile == "live"
    assert ws_url == streaming.WS_DOMAINS["prod"]
