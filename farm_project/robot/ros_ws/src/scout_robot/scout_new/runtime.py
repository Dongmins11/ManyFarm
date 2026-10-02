"""시각, JSON 저장 및 작업 중단을 공통으로 사용합니다."""
from __future__ import annotations
from .mission_types import JsonObject
import json
from pathlib import Path
from datetime import datetime, timezone

def utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_json(path: str | Path, data: JsonObject) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
    tmp.replace(path)

class MissionCanceled(RuntimeError):
    pass
