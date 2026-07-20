"""Idempotency ledger for order mutations.

`--client-order-id`로 전달된 키를 프로필+환경별 append-only JSONL 원장에
기록한다. 같은 키로 재실행하면 주문을 재전송하지 않고 저장된 응답을 반환해
재시도(네트워크 단절, 에이전트 재실행)로 인한 중복 주문을 방지한다.

원장 위치: <config dir>/idempotency/<profile>-<env>.jsonl
줄 형식: {"key", "api_id", "ord_no", "fingerprint", "status", "response", "ts"}
status: "inflight"(전송 직전 기록, 응답 미도착) | "done"(전송 완료) |
"rejected"(업스트림이 구조적으로 거부했거나 애초에 도달하지 못함 — 주문 미실행,
같은 키 재전송 안전). 키 없음(v2.4~v2.8 원장)은 "done"으로 간주 — 하위호환.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import config, envelope

# 원장 정리 기본 보존기간. 90일 지난 **종결된** 키는 재사용되지 않는다고 본다.
DEFAULT_MAX_AGE_DAYS = 90


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


def record_inflight(key: str, api_id: str, fingerprint: str) -> None:
    """전송 직전에 in-flight 표식을 남긴다.

    전송 후 응답을 받지 못해도(타임아웃·연결 끊김) 원장에 흔적이 남으므로,
    같은 키로 재시도할 때 재전송 대신 '결과 불명'을 보고할 수 있다.
    """
    ledger = _ledger_file()
    config.ensure_config_dir()
    config.secure_dir(ledger.parent)
    rec = {
        "key": key,
        "api_id": api_id,
        "ord_no": "",
        "fingerprint": fingerprint,
        "response": None,
        "status": "inflight",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    config.secure_file(ledger)


def record_rejected(key: str, api_id: str, fingerprint: str | None = None) -> None:
    """주문이 실행되지 않았다고 확신할 수 있는 시도를 종결 기록한다 (재전송 가능 상태로 남긴다).

    두 가지 경우에 호출된다:
    - `KiwoomAPIError`(잔고 부족, 호가 오류, 장 마감, 잘못된 종목 등 return_code != 0):
      업스트림에 도달은 했지만 구조적으로 거부되어 실행되지 않았다.
    - `KiwoomAuthError` 등, 실제 HTTP 전송(self._http.post) 이전 지점에서만 발생함이
      코드 구조상 보장되는 예외: 업스트림에 도달조차 하지 못했다.

    두 경우 모두 결과 불명(in-flight)이 아니다 — 같은 키로 재시도할 때 재전송을
    막을 이유가 없다. "inflight"로 영구히 막히는 것을 방지하기 위해 in-flight
    기록 위에 이 종결 레코드를 남긴다.
    """
    ledger = _ledger_file()
    config.ensure_config_dir()
    config.secure_dir(ledger.parent)
    rec = {
        "key": key,
        "api_id": api_id,
        "ord_no": "",
        "fingerprint": fingerprint,
        "status": "rejected",
        "response": None,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    config.secure_file(ledger)


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
        "status": "done",
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    config.secure_file(ledger)


# ── 원장 정리 ─────────────────────────────────────────
#
# 원장은 append-only라 파일도 lookup()의 선형 스캔도 무한히 자란다.
#
# 트리거를 왜 수동 명령 하나로 두었나 (record()에서 확률적으로 돌리는 안 기각):
#   원장이 잘리면 lookup()이 None을 반환하고, 그 결과는 이미 체결됐을 수 있는
#   주문의 재전송이다. 즉 실패의 대가가 "파일이 크다"와 비교가 안 된다.
#   확률적 재작성은 그 위험을 (1) 주문 실행 도중에, (2) 무작위로, (3) 조용히
#   터뜨린다 — 재현도 사후 추적도 불가능한 형태다. 게다가 record()는 이미
#   주문이 전송·수락된 뒤에 호출되므로, 그 지점에서 하는 추가 작업은 전부
#   "응답은 받았는데 기록에 실패" 창을 넓히는 쪽으로만 작용한다.
#   반대로 방치의 대가는 작다: --client-order-id를 쓴 주문만 기록되고 한 줄이
#   200바이트 남짓이라, 수천 건이 쌓여도 수백 KB이고 선형 스캔은 무시할 수준이다.
#   대가가 비대칭이므로 결정론적이고 감사 가능한 수동 실행으로 둔다.
#   (남는 위험: 아무도 실행하지 않는다. 파일이 커도 무해하다는 위 근거가
#    그 위험을 받아들일 수 있게 만든다.)


def _parse_ts(rec: dict[str, Any]) -> datetime | None:
    ts = rec.get("ts")
    if not isinstance(ts, str):
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def prune(max_age_days: int = DEFAULT_MAX_AGE_DAYS, *,
          dry_run: bool = False) -> dict[str, Any]:
    """종결된 지 max_age_days가 지난 키를 원장에서 제거한다.

    **줄 단위가 아니라 키 단위로 판단한다.** lookup()은 키별 마지막 레코드만
    돌려주므로, 키의 최종 상태가 판단 근거이고 그 앞의 줄들은 이력일 뿐이다.

      - 최종 레코드가 "inflight"인 키: 나이와 무관하게 통째로 보존한다.
        주문이 브로커에 닿았을 수 있다는 유일한 증거이고, 지우면 재실행이
        실제 주문을 다시 쏜다.
      - 최종 레코드가 종결("done"/"rejected"/구버전 무상태)이고 그 시각이
        기준보다 오래된 키: 통째로 제거한다.
      - 그 외(최근 키, 파싱 불가능한 줄, key 없음, ts 없음·해석 불가): 보존한다.
        지울 근거가 없으면 남기는 쪽이 안전하다.

    크래시 안전성: 임시 파일에 전부 쓰고 fsync한 뒤 os.replace로 갈아끼운다.
    os.replace는 원자적이므로 어느 시점에 죽어도 원장은 '이전 전체' 또는
    '이후 전체'다 — 잘린 중간 상태가 존재하지 않는다. 디렉터리도 fsync해
    이름 바꾸기 자체를 내구화한다. 전 구간을 기존 locked()로 감싸 동시에
    도는 주문의 조회→전송→기록 구간과 겹치지 않게 한다.

    locked()는 재진입 불가다 — 주문 경로(_mutation.send_order) 안에서
    호출하지 말 것. 수동 명령 전용이다.
    """
    if max_age_days < 1:
        raise ValueError("max_age_days는 1 이상이어야 합니다.")

    ledger = _ledger_file()
    empty = {"ledger": str(ledger), "kept_keys": 0, "removed_keys": 0,
             "kept_lines": 0, "removed_lines": 0, "dry_run": dry_run}
    if not ledger.exists():
        return empty

    with locked():
        if not ledger.exists():  # 잠금 획득 사이에 사라졌을 수 있다
            return empty
        with open(ledger, encoding="utf-8") as f:
            raw_lines = f.read().splitlines()

        # 1차 스캔: 키별 최종 레코드를 찾는다.
        final: dict[str, dict[str, Any]] = {}
        parsed: list[tuple[str, str | None]] = []  # (원본 줄, 귀속 키 or None)
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                parsed.append((line, None))
                continue
            key = rec.get("key") if isinstance(rec, dict) else None
            if not isinstance(key, str) or not key:
                parsed.append((line, None))
                continue
            final[key] = rec
            parsed.append((line, key))

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        doomed = set()
        for key, rec in final.items():
            if rec.get("status", "done") == "inflight":
                continue  # 결과 불명 — 영구 보존
            ts = _parse_ts(rec)
            if ts is not None and ts < cutoff:
                doomed.add(key)

        kept = [line for line, key in parsed if key not in doomed]
        stats = {
            "ledger": str(ledger),
            "kept_keys": len(final) - len(doomed),
            "removed_keys": len(doomed),
            "kept_lines": len(kept),
            "removed_lines": len(parsed) - len(kept),
            "dry_run": dry_run,
        }
        if dry_run or not doomed:
            return stats

        tmp = ledger.with_name(ledger.name + ".prune.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                config.secure_file(tmp)
                for line in kept:
                    f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ledger)
        except BaseException:
            # 실패하면 원장은 손대지 않은 상태 그대로다. 임시 파일만 치운다.
            tmp.unlink(missing_ok=True)
            raise
        try:
            dir_fd = os.open(ledger.parent, os.O_RDONLY)
        except OSError:  # pragma: no cover  (Windows 등)
            pass
        else:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        config.secure_file(ledger)
        return stats
