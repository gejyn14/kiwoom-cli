"""Idempotency ledger for order mutations.

`--client-order-id`로 전달된 키를 프로필+환경별 append-only JSONL 원장에
기록한다. 같은 키로 재실행하면 주문을 재전송하지 않고 저장된 응답을 반환해
재시도(네트워크 단절, 에이전트 재실행)로 인한 중복 주문을 방지한다.

원장 위치: <config dir>/idempotency/<profile>-<env>.jsonl
줄 형식: {"key", "api_id", "ord_no", "fingerprint", "response", "ts"}
"""

from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config, envelope


def _ledger_file() -> Path:
    meta = envelope.build_meta()
    return config.CONFIG_FILE.parent / "idempotency" / f"{meta['profile']}-{meta['env']}.jsonl"


def fingerprint(api_id: str, body: dict[str, Any]) -> str:
    """주문 내용 지문. 같은 키가 다른 주문 내용에 재사용되는 것을 감지한다."""
    canon = json.dumps({"api_id": api_id, "body": body},
                       sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


class LedgerLockBusy(Exception):
    """원장 잠금을 제한시간 내 획득하지 못함 (Windows msvcrt ~10초 재시도 후)."""


if sys.platform == "win32":  # pragma: no cover
    import msvcrt

    def _acquire(f) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _release(f) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _acquire(f) -> None:
        fcntl.flock(f, fcntl.LOCK_EX)

    def _release(f) -> None:
        fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def locked():
    """원장 파일 잠금 — 조회→전송→기록 구간을 프로세스 간 직렬화한다.

    같은 --client-order-id로 동시에 두 프로세스가 진입해 둘 다 미기록 상태를
    보고 둘 다 전송하는 중복 주문을 막는다. 프로필+환경 원장 단위 잠금이므로
    같은 프로필의 서로 다른 주문도 잠금 구간 동안 직렬화된다 (정확성 우선).
    재진입 불가(같은 프로세스에서 중첩 사용 시 데드락) — send_order 외에서 사용하지 말 것.
    """
    ledger = _ledger_file()
    config.ensure_config_dir()
    config.secure_dir(ledger.parent)
    lock_path = ledger.with_suffix(".lock")
    with open(lock_path, "a+", encoding="utf-8") as f:
        config.secure_file(lock_path)
        try:
            _acquire(f)
        except OSError as e:
            raise LedgerLockBusy(str(e)) from e
        try:
            yield
        finally:
            _release(f)


def lookup(key: str) -> dict[str, Any] | None:
    """키에 해당하는 가장 최근 기록을 반환. 없으면 None."""
    ledger = _ledger_file()
    if not ledger.exists():
        return None
    hit: dict[str, Any] | None = None
    with open(ledger, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("key") == key:
                hit = rec
    return hit


def record(key: str, api_id: str, response: dict[str, Any],
           fingerprint: str | None = None) -> None:
    """전송 성공한 주문 응답을 원장에 append."""
    ledger = _ledger_file()
    config.ensure_config_dir()
    config.secure_dir(ledger.parent)
    rec = {
        "key": key,
        "api_id": api_id,
        "ord_no": response.get("ord_no", ""),
        "fingerprint": fingerprint,
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    config.secure_file(ledger)
