"""Tests for order safety mechanisms: idempotency, fingerprints, locks.

Validates idempotency ledger (kiwoom_cli/idempotency.py) with fingerprints,
locks, and record signatures to prevent duplicate orders under retries
and concurrent sends.
"""

from __future__ import annotations

import json  # noqa: F401
from pathlib import Path
from typing import Any  # noqa: F401
from unittest.mock import MagicMock, patch  # noqa: F401

import click  # noqa: F401
import pytest
from click.testing import CliRunner

from kiwoom_cli import config, idempotency
from kiwoom_cli.main import cli  # noqa: F401


@pytest.fixture
def runner():
    """Click CLI runner for integration tests."""
    return CliRunner()


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch) -> Path:
    """config/ledger를 tmp로 격리하고 프로필/도메인 env를 제거한다."""
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    monkeypatch.delenv("KIWOOM_PROFILE", raising=False)
    monkeypatch.delenv("KIWOOM_DOMAIN", raising=False)
    return tmp_path


def _mock_kiwoom_client(request_fn):
    """Helper to inject a fake KiwoomClient for testing."""
    fake = MagicMock()
    fake.request.side_effect = request_fn
    return fake


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
