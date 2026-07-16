"""NDJSON 스트림 레코더 — --record 옵션으로 실시간 이벤트를 파일에 저장.

기본 레이아웃: <config dir>/data/<symbol>_<YYYY-MM-DD>.ndjson (심볼별 파일,
계좌성 타입 00/04는 심볼 대신 타입명). 명시 경로를 주면 모든 이벤트를
한 파일에 기록한다. history 명령 그룹이 이 파일들을 다시 읽는다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO

from . import config

KST = timezone(timedelta(hours=9))

# 계좌 단위 실시간 타입 — 심볼이 있어도 타입명으로 파일 구분
ACCOUNT_TYPES = frozenset({"00", "04"})


def data_dir() -> Path:
    """기본 레코딩 디렉토리: <config dir>/data."""
    return config.CONFIG_FILE.parent / "data"


class NdjsonRecorder:
    """이벤트를 NDJSON 파일에 추가 기록. 파일별 이벤트 수를 counts에 추적.

    line-buffered(buffering=1)로 열어 크래시 시 최대 현재 한 줄만 유실된다.
    """

    def __init__(self, path: str | Path | None = None):
        self._single = Path(path) if path else None
        self._files: dict[Path, TextIO] = {}
        self.counts: dict[Path, int] = {}

    def path_for(self, event: dict[str, Any]) -> Path:
        """이벤트가 기록될 파일 경로 (명시 경로 또는 기본 레이아웃)."""
        if self._single is not None:
            return self._single
        if event.get("type") in ACCOUNT_TYPES:
            key = event.get("type_name") or event["type"]
        else:
            key = event.get("symbol") or event.get("type_name") or "stream"
        date = datetime.now(KST).strftime("%Y-%m-%d")
        return data_dir() / f"{key}_{date}.ndjson"

    def write(self, event: dict[str, Any]) -> Path:
        """이벤트 한 건을 JSON 한 줄로 append. 기록된 파일 경로를 반환."""
        path = self.path_for(event)
        f = self._files.get(path)
        if f is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            f = open(path, "a", buffering=1, encoding="utf-8")
            self._files[path] = f
            self.counts.setdefault(path, 0)
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.counts[path] += 1
        return path

    def close(self) -> None:
        for f in self._files.values():
            f.close()
        self._files.clear()
