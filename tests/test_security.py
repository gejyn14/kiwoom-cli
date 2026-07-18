"""Tier-4 security regression tests (file permissions, profile allowlist, raw-api gate)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from kiwoom_cli import config, idempotency
from kiwoom_cli.main import cli
from kiwoom_cli.recorder import NdjsonRecorder
from tests.fakes import FakeKiwoomClient

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
def test_harden_permissions_survives_chmod_permission_error(isolated_config, monkeypatch, runner):
    """foreign-owned 파일 등으로 chmod가 OSError를 내도 전체 명령이 죽으면 안 된다."""
    config.ensure_config_dir()

    def _raise(self, mode):
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(Path, "chmod", _raise)

    # 직접 호출해도 예외가 새지 않아야 한다.
    config.harden_permissions()

    # 루트 콜백 경유(매 명령 실행)에서도 동일하게 살아남아야 한다.
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0


@posix_only
def test_cli_run_hardens_existing_install(runner, isolated_config):
    """아무 커맨드나 한 번 실행하면 기존 0755 디렉토리가 조여진다."""
    isolated_config.chmod(0o755)
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert _mode(isolated_config) == 0o700


# ── Task 2: ledger + recorder permissions ────────────────


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


def test_config_use_rejects_traversal_profile(runner, isolated_config):
    """config use는 allowlist 검사를 프로필 존재 검사보다 먼저 해야 한다.

    "../evil"는 allowlist에도 걸리고(무효 문자) 프로필 목록에도 없다(존재하지 않음) —
    두 경로 모두 INVALID_INPUT/exit 1이라 code만으로는 어느 검사가 실행됐는지
    구분되지 않으므로, allowlist 전용 메시지("영문자/숫자/하이픈/언더스코어")가
    나왔는지까지 확인해 존재-검사 메시지("찾을 수 없습니다")로 새는 회귀를 잡는다.
    """
    result = runner.invoke(cli, ["-f", "json", "config", "use", "../evil"])
    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["ok"] is False
    assert doc["error"]["code"] == "INVALID_INPUT"
    assert "영문자/숫자/하이픈/언더스코어" in doc["error"]["message"]
    assert "찾을 수 없습니다" not in doc["error"]["message"]


def test_valid_profile_flag_still_works(runner, isolated_config):
    result = runner.invoke(cli, ["-p", "my_profile-2", "config", "show"])
    assert result.exit_code == 0


# ── Task 4: raw api mutation gate ────────────────────────


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


def test_raw_api_mutation_ignores_global_all_pages(runner, isolated_config, monkeypatch):
    """--all-pages 지정 + 주문성 API cont-yn=Y 응답 → 재전송 없이 정확히 1회만 호출."""
    captured: dict = {}

    class SnapshotClient(FakeKiwoomClient):
        def request(self, api_id, body=None, **kwargs):
            ctx = click.get_current_context(silent=True)
            captured["all_pages"] = ctx.obj.get("all_pages") if ctx and ctx.obj else None
            return super().request(api_id, body, **kwargs)

    fake = SnapshotClient()
    fake.set_response("kt10000", {"return_code": 0}, {"cont-yn": "Y", "next-key": "K"})
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda: fake)

    result = runner.invoke(cli, [
        "-f", "json", "--all-pages", "api", "kt10000", '{"stk_cd":"005930"}', "--confirm",
    ])
    assert result.exit_code == 0
    assert len(fake.calls) == 1
    # confirm_gate 통과 후 mutation 분기가 ctx.obj["all_pages"]를 False로 되돌렸어야 한다.
    assert captured["all_pages"] is False


def test_raw_api_mutation_clears_global_next_key(runner, isolated_config, monkeypatch):
    """전역 --next-key 지정 + 주문성 API → mutation 분기에서 ctx.obj의 next_key가 제거된다."""
    captured: dict = {}

    class SnapshotClient(FakeKiwoomClient):
        def request(self, api_id, body=None, **kwargs):
            ctx = click.get_current_context(silent=True)
            captured["has_next_key"] = bool(ctx and ctx.obj and ("next_key" in ctx.obj))
            return super().request(api_id, body, **kwargs)

    fake = SnapshotClient()
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda: fake)

    result = runner.invoke(cli, [
        "-f", "json", "--next-key", "PREV", "api", "kt10000", '{"stk_cd":"005930"}', "--confirm",
    ])
    assert result.exit_code == 0
    assert len(fake.calls) == 1
    assert captured["has_next_key"] is False


def test_raw_api_readonly_all_pages_unaffected(runner, isolated_config, monkeypatch):
    """읽기전용 api id는 전역 --all-pages 처리를 그대로 유지한다 (ctx.obj 건드리지 않음)."""
    captured: dict = {}

    class SnapshotClient(FakeKiwoomClient):
        def request(self, api_id, body=None, **kwargs):
            ctx = click.get_current_context(silent=True)
            captured["all_pages"] = ctx.obj.get("all_pages") if ctx and ctx.obj else None
            return super().request(api_id, body, **kwargs)

    fake = SnapshotClient()
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda: fake)

    result = runner.invoke(cli, [
        "-f", "json", "--all-pages", "api", "ka10001", '{"stk_cd":"005930"}',
    ])
    assert result.exit_code == 0
    assert captured["all_pages"] is True


def test_raw_api_mutation_suppresses_cont_hint(runner, isolated_config, monkeypatch):
    """변이 API가 cont-yn: Y를 반환해도 raw api의 "연속조회 가능" stderr 힌트가 뜨면
    안 된다 — meta.cont는 이미 항상 null로 고정되는데(Task 6b), 이 힌트는 raw 응답
    헤더를 직접 보고 meta.cont/ctx.obj와 무관한 별도 채널로 "이어서 실행하라"고
    안내해 왔다 (Task 6b 리포트의 concerns에서 지적된 결함)."""
    fake = FakeKiwoomClient()
    fake.set_response("kt10000", {"return_code": 0}, {"cont-yn": "Y", "next-key": "K"})
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda: fake)

    result = runner.invoke(cli, [
        "api", "kt10000", '{"stk_cd":"005930"}', "--confirm",
    ])
    assert result.exit_code == 0, result.output
    assert "연속조회 가능" not in result.output


def test_raw_api_readonly_still_shows_cont_hint(runner, isolated_config, monkeypatch):
    """대조군: 읽기 전용 API가 실제로 연속조회 가능한 경우 힌트는 그대로 유지되어야
    한다 — 변이 억제가 읽기 전용 힌트 계약까지 깨면 원래 결함보다 더 나쁘다."""
    fake = FakeKiwoomClient()
    fake.set_response("ka10001", {"return_code": 0}, {"cont-yn": "Y", "next-key": "K"})
    monkeypatch.setattr("kiwoom_cli.main.KiwoomClient", lambda: fake)

    result = runner.invoke(cli, ["api", "ka10001", '{"stk_cd":"005930"}'])
    assert result.exit_code == 0, result.output
    assert "연속조회 가능" in result.output


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
