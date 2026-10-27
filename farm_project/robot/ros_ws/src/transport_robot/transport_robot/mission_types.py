"""운송 작업 데이터. 관제 규약과 내부 주행 시험의 완료 범위를 구분한다."""
from dataclasses import dataclass
from typing import Any
from datetime import datetime, timezone


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionCanceled(RuntimeError):
    pass


@dataclass(frozen=True)
class Request:
    task_id: str
    kind: str
    xy: tuple[float,float]
    yaw: float
    station_id: str = ''
    transfer_id: str = ''
    harvest_robot_id: str = ''
    target_marker_id: int = -1
    docking_marker_id: int = -1
    profile_id: str = ''
    clearance_xy: tuple[float,float] | None = None
    clearance_yaw: float | None = None
    dock_only_trial: bool = False
    entry_stage: bool = False


@dataclass(frozen=True)
class Outcome:
    result_code: str
    error_code: str = 'NONE'
    error_message: str = ''
    arrived: bool = False
    docked: bool = False
