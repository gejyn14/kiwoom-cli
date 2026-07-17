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


# ── Task 3: profile-name allowlist ───────────────────────


def test_valid_profile_names_accepted():
    for name in ("default", "My_Profile-2", "a", "A" * 64):
        assert config.is_valid_profile_name(name)


def test_invalid_profile_names_rejected():
    for name in ("", "../evil", "a/b", "a\\b", "a.b", "한글", "a b", "A" * 65, "default\n"):
        assert not config.is_valid_profile_name(name)


def test_cli_rejects_traversal_profile_flag(runner, isolated_config):
    result = runner.invoke(cli, ["-f", "json", "-p", "../evil", "config", "show"])
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_cli_rejects_traversal_profile_env(runner, isolated_config, monkeypatch):
    monkeypatch.setenv("KIWOOM_PROFILE", "../../etc/passwd")
    result = runner.invoke(cli, ["-f", "json", "config", "show"])
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_config_setup_rejects_traversal_profile(runner, isolated_config):
    result = runner.invoke(cli, [
        "-f", "json", "config", "setup",
        "--profile", "a/b", "--appkey", "k", "--secretkey", "s",
    ])
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["error"]["code"] == "INVALID_INPUT"


def test_valid_profile_flag_still_works(runner, isolated_config):
    result = runner.invoke(cli, ["-p", "my_profile-2", "config", "show"])
    assert result.exit_code == 0


# ── Task 4: raw api mutation gate ────────────────────────

from tests.fakes import FakeKiwoomClient


@pytest.fixture
def fake_client(monkeypatch):
    fake = FakeKiwoomClient()
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda: fake)
    return fake


def test_raw_api_order_blocked_without_confirm_json(runner, isolated_config, fake_client):
    result = runner.invoke(cli, [
        "-f", "json", "api", "kt10000",
        '{"dmst_stex_tp":"KRX","stk_cd":"005930","ord_qty":"1","ord_uv":"","trde_tp":"3","cond_uv":""}',
    ])
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert fake_client.calls == []  # 전송되지 않아야 한다


def test_raw_api_order_sent_with_confirm(runner, isolated_config, fake_client):
    result = runner.invoke(cli, [
        "-f", "json", "api", "kt10000", '{"stk_cd":"005930"}', "--confirm",
    ])
    assert result.exit_code == 0
    assert [c[0] for c in fake_client.calls] == ["kt10000"]


def test_raw_api_readonly_needs_no_confirm(runner, isolated_config, fake_client):
    result = runner.invoke(cli, ["-f", "json", "api", "ka10001", '{"stk_cd":"005930"}'])
    assert result.exit_code == 0
    assert [c[0] for c in fake_client.calls] == ["ka10001"]


def test_raw_api_table_prompt_abort_sends_nothing(runner, isolated_config, fake_client):
    result = runner.invoke(cli, ["api", "kt10000", '{"stk_cd":"005930"}'], input="n\n")
    assert result.exit_code != 0
    assert fake_client.calls == []


def test_raw_api_table_shows_body_before_prompt(runner, isolated_config, fake_client):
    """미리보기(body)가 프롬프트보다 먼저 stderr에 출력되어야 한다 (Tier-1 불변식)."""
    result = runner.invoke(cli, ["api", "kt10003", '{"orig_ord_no":"7"}'], input="y\n")
    assert result.exit_code == 0
    assert "kt10003" in result.output
    assert "orig_ord_no" in result.output


def test_mutation_apis_cover_all_order_ids():
    from kiwoom_cli.api_spec import MUTATION_APIS
    expected = {
        "kt10000", "kt10001", "kt10002", "kt10003",
        "kt10006", "kt10007", "kt10008", "kt10009",
        "kt50000", "kt50001", "kt50002", "kt50003",
        "ust20000", "ust20001", "ust20002", "ust20003",
        "ust31302",
    }
    assert MUTATION_APIS == frozenset(expected)
