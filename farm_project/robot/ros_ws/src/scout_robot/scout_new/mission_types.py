"""작업 데이터. ROS 필드 이름·단위는 기존 인터페이스를 유지합니다."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

from farm_interfaces.msg import HarvestTask
from rclpy.action.server import ServerGoalHandle
from scout_robot.survey_core import StraightBed, Survey

if TYPE_CHECKING:
    from .observer import SurveyObserver

# 기존 설정·영상 RPC·JSON 보고서의 확장 가능한 필드입니다.
JsonObject = dict[str, Any]
MovePurpose = Literal['section_start', 'observation', 'section_exit']


@dataclass
class Observation:
    """한 프레임 등록 결과. 위치는 map m, stamp_ns는 ROS 시각 ns입니다."""
    response: JsonObject
    transform: list[list[float]]  # pose_frame → map 4×4 변환
    accepted: list[JsonObject]
    ignored: list[JsonObject]
    ids: list[str]


@dataclass
class MissionContext:
    """미션 한 건의 공유 데이터. State가 바뀌어도 이 객체는 유지됩니다."""
    goal: ServerGoalHandle
    session: str
    folder: Path
    report: JsonObject
    started_wall: float  # monotonic 초: 경과 시간 측정용
    worker: SurveyObserver | None = None  # 준비 전/정리 후 None
    prepared: bool = False
    section_index: int = 0
    segment_index: int = 0
    bed: StraightBed | None = None  # 첫 구역 선택 전 None
    survey: Survey | None = None
    design: JsonObject = field(default_factory=dict)
    current_segment: JsonObject | None = None
    observation: Observation | None = None
    camera_session: str | None = None
    stamp: int = 0  # 정지 확인 odom의 ROS 시각 ns
    segment_started: float = 0.0
    capture_started: float = 0.0
    tail_started: float = 0.0
    section_reported: bool = False
    tasks: list[HarvestTask] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    completed_segments: int = 0
    total_tasks: int = 0
    total_fruits: int = 0
    segment_expected_count: int = 0

    @property
    def section(self) -> str:
        return self.goal.request.section_ids[self.section_index]

    @property
    def segment(self) -> JsonObject:
        return self.design['segments'][self.segment_index]

    @property
    def segment_id(self) -> str:
        return self.segment['segment_id']

    @property
    def last_segment(self) -> bool:
        return self.segment_index + 1 == len(self.design['segments'])
