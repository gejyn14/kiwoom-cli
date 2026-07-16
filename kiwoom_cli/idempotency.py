"""Idempotency ledger for order mutations.

`--client-order-id`로 전달된 키를 프로필+환경별 append-only JSONL 원장에
기록한다. 같은 키로 재실행하면 주문을 재전송하지 않고 저장된 응답을 반환해
재시도(네트워크 단절, 에이전트 재실행)로 인한 중복 주문을 방지한다.

원장 위치: <config dir>/idempotency/<profile>-<env>.jsonl
줄 형식: {"key", "api_id", "ord_no", "response", "ts"}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config, envelope


def _ledger_file() -> Path:
    meta = envelope.build_meta()
    return config.CONFIG_FILE.parent / "idempotency" / f"{meta['profile']}-{meta['env']}.jsonl"


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


def record(key: str, api_id: str, response: dict[str, Any]) -> None:
    """전송 성공한 주문 응답을 원장에 append."""
    ledger = _ledger_file()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "key": key,
        "api_id": api_id,
        "ord_no": response.get("ord_no", ""),
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
