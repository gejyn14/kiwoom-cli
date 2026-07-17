"""Tier-4 security regression tests (file permissions, profile allowlist, raw-api gate)."""

from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from kiwoom_cli import config
from kiwoom_cli.main import cli

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """CONFIG_DIR/CONFIG_FILE/CACHE_DIR를 tmp로 격리하고 프로필/도메인 env를 제거한다."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


def _mode(path):
    return path.stat().st_mode & 0o777


# ── Task 1: permission helpers + config hardening ────────


@posix_only
def test_ensure_config_dir_is_0700(isolated_config):
    config.ensure_config_dir()
    assert _mode(isolated_config) == 0o700


@posix_only
def test_ensure_config_dir_tightens_existing_0755(isolated_config):
    isolated_config.chmod(0o755)
    config.ensure_config_dir()
    assert _mode(isolated_config) == 0o700


@posix_only
def test_save_config_writes_0600_toml(isolated_config):
    config.save_config({"general": {"default_profile": "default"}})
    assert _mode(isolated_config / "config.toml") == 0o600


@posix_only
def test_ensure_cache_dir_is_0700(isolated_config):
    config.ensure_cache_dir()
    assert _mode(isolated_config / "cache") == 0o700
    assert _mode(isolated_config) == 0o700


@posix_only
def test_harden_permissions_tightens_existing_tree(isolated_config):
    # 기존 설치본 흉내: 느슨한 권한으로 미리 생성
    (isolated_config / "idempotency").mkdir(mode=0o755)
    ledger = isolated_config / "idempotency" / "default-mock.jsonl"
    ledger.write_text("{}\n")
    ledger.chmod(0o644)
    cfg_file = isolated_config / "config.toml"
    cfg_file.write_text("")
    cfg_file.chmod(0o644)
    isolated_config.chmod(0o755)

    config.harden_permissions()

    assert _mode(isolated_config) == 0o700
    assert _mode(isolated_config / "idempotency") == 0o700
    assert _mode(ledger) == 0o600
    assert _mode(cfg_file) == 0o600


@posix_only
def test_harden_permissions_noop_when_dir_missing(isolated_config):
    # CONFIG_DIR가 없어도 예외 없이 통과해야 한다 (아무것도 생성하지 않음)
    missing = isolated_config / "nope"
    orig = config.CONFIG_DIR
    config.CONFIG_DIR = missing
    try:
        config.harden_permissions()
    finally:
        config.CONFIG_DIR = orig
    assert not missing.exists()


@posix_only
def test_cli_run_hardens_existing_install(runner, isolated_config):
    """아무 커맨드나 한 번 실행하면 기존 0755 디렉토리가 조여진다."""
    isolated_config.chmod(0o755)
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert _mode(isolated_config) == 0o700


# ── Task 2: ledger + recorder permissions ────────────────

from kiwoom_cli import idempotency
from kiwoom_cli.recorder import NdjsonRecorder


@posix_only
def test_ledger_record_creates_0700_dir_and_0600_file(isolated_config):
    idempotency.record("key1", "kt10000", {"ord_no": "1"}, fingerprint="ab")
    ledger_dir = isolated_config / "idempotency"
    files = list(ledger_dir.glob("*.jsonl"))
    assert len(files) == 1
    assert _mode(ledger_dir) == 0o700
    assert _mode(files[0]) == 0o600


@posix_only
def test_ledger_lock_file_is_0600(isolated_config):
    with idempotency.locked():
        pass
    locks = list((isolated_config / "idempotency").glob("*.lock"))
    assert len(locks) == 1
    assert _mode(locks[0]) == 0o600


@posix_only
def test_recorder_default_layout_is_0700_0600(isolated_config):
    rec = NdjsonRecorder()
    path = rec.write({"type": "0B", "symbol": "005930", "price": 1})
    rec.close()
    assert _mode(path) == 0o600
    assert _mode(path.parent) == 0o700


@posix_only
def test_recorder_explicit_path_left_alone(isolated_config, tmp_path_factory):
    """사용자가 지정한 --record 경로의 디렉토리 권한은 건드리지 않는다."""
    shared = tmp_path_factory.mktemp("shared")
    shared.chmod(0o755)
    rec = NdjsonRecorder(shared / "out.ndjson")
    rec.write({"type": "0B", "symbol": "005930", "price": 1})
    rec.close()
    assert _mode(shared) == 0o755
