"""Tests for order safety mechanisms: idempotency, fingerprints, locks.

Validates idempotency ledger (kiwoom_cli/idempotency.py) with fingerprints,
locks, and record signatures to prevent duplicate orders under retries
and concurrent sends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kiwoom_cli import idempotency


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: Any) -> None:
    """Isolate idempotency ledger to a temporary directory per test.

    Mocks envelope.build_meta() to return a stable test profile/env,
    and patches config.CONFIG_FILE to point to tmp_path.
    """
    # Set up temporary config directory
    test_config_dir = tmp_path / "config"
    test_config_dir.mkdir(parents=True, exist_ok=True)

    # Mock CONFIG_FILE to point to temp directory
    monkeypatch.setattr("kiwoom_cli.config.CONFIG_FILE", test_config_dir / "config.toml")

    # Mock envelope.build_meta() to return consistent test values
    def mock_build_meta() -> dict[str, Any]:
        return {"profile": "test", "env": "mock", "cont": None}

    monkeypatch.setattr("kiwoom_cli.envelope.build_meta", mock_build_meta)
    monkeypatch.setattr("kiwoom_cli.idempotency.envelope.build_meta", mock_build_meta)


# ── Task 1: idempotency core ─────────────────────────────

def test_fingerprint_stable_and_body_sensitive():
    fp1 = idempotency.fingerprint("kt10000", {"stk_cd": "005930", "ord_qty": "10"})
    fp2 = idempotency.fingerprint("kt10000", {"ord_qty": "10", "stk_cd": "005930"})
    fp3 = idempotency.fingerprint("kt10000", {"stk_cd": "005930", "ord_qty": "11"})
    fp4 = idempotency.fingerprint("kt10001", {"stk_cd": "005930", "ord_qty": "10"})
    assert fp1 == fp2
    assert fp1 != fp3
    assert fp1 != fp4
    assert len(fp1) == 16


def test_record_stores_fingerprint(isolated_env):
    idempotency.record("k1", "kt10000", {"ord_no": "42", "return_code": 0},
                       fingerprint="abc123")
    hit = idempotency.lookup("k1")
    assert hit is not None
    assert hit["fingerprint"] == "abc123"
    assert hit["response"]["ord_no"] == "42"


def test_record_without_fingerprint_is_legacy_compatible(isolated_env):
    idempotency.record("k2", "kt10000", {"ord_no": "43", "return_code": 0})
    hit = idempotency.lookup("k2")
    assert hit is not None
    assert hit["fingerprint"] is None


def test_locked_creates_lock_file_and_yields(isolated_env):
    with idempotency.locked():
        pass
    lock = idempotency._ledger_file().with_suffix(".lock")
    assert lock.exists()
