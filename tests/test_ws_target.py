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


def test_build_meta_env_matches_domain_key(isolated_config, monkeypatch):
    from kiwoom_cli import envelope

    monkeypatch.setenv("KIWOOM_DOMAIN", "nonsense")
    config.CONFIG_FILE.write_bytes(
        b'[general]\ndefault_profile = "default"\n\n'
        b'[profiles.default]\ndomain = "prod"\n'
    )
    meta = envelope.build_meta()
    assert meta["env"] == config.get_domain_key() == "mock"


class TestResolveProfileHonorsClickContext:
    """resolve_profile의 docstring은 CLI --profile을 1순위로 문서화하지만
    구현은 그것을 읽지 않았다. 호출자가 넘겨줄 때만 반영돼, 넘기지 않는
    호출부(us/detect.py)가 조용히 다른 프로필로 해석했다."""

    def test_ctx_profile_beats_default_profile(self, monkeypatch, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            '[general]\ndefault_profile = "sim"\n'
            '[profiles.sim]\ndomain = "mock"\n'
            '[profiles.live]\ndomain = "prod"\n'
        )
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", cfg)
        monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
        monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
        with click.Context(click.Command("x"), obj={"profile": "live"}):
            assert config.resolve_profile() == "live"
            assert config.get_domain_key() == "prod"

    def test_explicit_arg_still_wins_over_ctx(self, monkeypatch, tmp_path):
        """명시 인자가 최우선. ctx가 그것을 덮으면 안 된다."""
        cfg = tmp_path / "config.toml"
        cfg.write_text('[general]\ndefault_profile = "sim"\n[profiles.sim]\ndomain = "mock"\n')
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", cfg)
        monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
        with click.Context(click.Command("x"), obj={"profile": "live"}):
            assert config.resolve_profile("explicit") == "explicit"

    def test_env_var_beats_ctx_absent_flag(self, monkeypatch, tmp_path):
        """ctx.obj['profile']가 None이면(플래그 미지정) KIWOOM_PROFILE로 내려간다."""
        cfg = tmp_path / "config.toml"
        cfg.write_text('[general]\ndefault_profile = "sim"\n[profiles.sim]\ndomain = "mock"\n')
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", cfg)
        monkeypatch.setenv("KIWOOM_PROFILE", "fromenv")
        with click.Context(click.Command("x"), obj={"profile": None}):
            assert config.resolve_profile() == "fromenv"

    def test_no_context_still_works(self, monkeypatch, tmp_path):
        """Click 컨텍스트 밖(테스트·라이브러리 사용)에서도 죽지 않는다."""
        cfg = tmp_path / "config.toml"
        cfg.write_text('[general]\ndefault_profile = "sim"\n[profiles.sim]\ndomain = "mock"\n')
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", cfg)
        monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
        assert config.resolve_profile() == "sim"

    def test_empty_ctx_obj_tolerated(self, monkeypatch, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text('[general]\ndefault_profile = "sim"\n[profiles.sim]\ndomain = "mock"\n')
        monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", cfg)
        monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
        with click.Context(click.Command("x"), obj={}):
            assert config.resolve_profile() == "sim"
        with click.Context(click.Command("x"), obj=None):
            assert config.resolve_profile() == "sim"
