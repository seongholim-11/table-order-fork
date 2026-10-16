"""더미 파일들이 함께 쓰는 작은 도구 (시각 만들기, seed JSON 읽기)."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SEED = Path(__file__).resolve().parents[1] / "seed"


def _ago(**delta) -> str:
    return (datetime.now(timezone.utc) - timedelta(**delta)).isoformat(timespec="seconds")


def _json(name: str):
    return json.loads((_SEED / name).read_text(encoding="utf-8"))

