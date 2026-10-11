"""화단 진입과 Window 좌표 이동을 순차 실행한다. 좌표 오프셋은 적용하지 않는다."""
from dataclasses import dataclass
import math
from typing import Callable, Any


@dataclass(frozen=True)
class Section:
    entry: tuple[float, float]
    entry_yaw: float
    exit: tuple[float, float]
    exit_yaw: float


def load_sections(config: dict, graph: Any) -> dict[str, Section]:
    """진입/이탈 위치는 환경 그래프의 명시적 노드에서 읽는다."""
    sections = {}
    for key, value in config.get('sections', {}).items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError('화단 ID가 비어 있음')
        def endpoint(prefix: str) -> tuple[tuple[float, float], float]:
            point = graph.nodes[value[prefix + '_node']]
            heading = graph.nodes[value[prefix + '_heading_node']]
            if math.dist(point, heading) < 1e-6:
                raise ValueError('방향 기준 노드는 위치 노드와 달라야 함')
            return point, math.atan2(heading[1]-point[1], heading[0]-point[0])
        entry, ey = endpoint('entry')
        exit_xy, xyaw = endpoint('exit')
        sections[key] = Section(entry, ey, exit_xy, xyaw)
    if not sections:
        raise ValueError('단계별 이동에는 화단 진입/이탈 설정이 필요함')
    return sections


class StagedNavigation:
    """동시에 한 작업만 실행하는 HarvestMission이 소유하는 화단 문맥."""
    def __init__(self, approach: Any, work: Any, sections: dict[str, Section],
                 current_xy: Callable, check: Callable, record: Callable,
                 continuity_m: float, *, exit_navigator: Any = None, resume_current: Callable | None = None) -> None:
        self.approach, self.work, self.sections = approach, work, sections
        # 기존 호출은 작업 제어기를 그대로 사용하며 명시적 이탈 제어기만 분리한다.
        self.exit_navigator = work if exit_navigator is None else exit_navigator
        self.current_xy, self.check, self.record = current_xy, check, record
        self.continuity_m = continuity_m
        self.resume_current = resume_current
        self.current_section = None
        self.last_arrival = None
        self.active = None

    def navigate(self, section_id: str, xy: tuple, yaw: float) -> Any:
        if section_id not in self.sections:
            raise ValueError('등록되지 않은 section_id: ' + section_id)
        # 재시작 또는 외부 이동 뒤에는 이전 화단 진입 상태를 재사용하지 않는다.
        if self.last_arrival is not None and math.dist(self.current_xy(), self.last_arrival) > self.continuity_m:
            self.current_section = self.last_arrival = None
        target = self.sections[section_id]
        try:
            # 매 요청의 현재 위치를 검증해 재시작/실패 뒤에도 진입점으로 되돌아가지 않는다.
            if self.resume_current is not None and self.resume_current(section_id, xy, yaw):
                self.record(dict(phase='SECTION_RESUME', section_id=section_id, target_xy=list(xy)))
                self.current_section = section_id
            if self.current_section != section_id:
                if self.current_section is not None:
                    old = self.sections[self.current_section]
                    self._move(self.exit_navigator, 'SECTION_EXIT', self.current_section, old.exit, old.exit_yaw)
                    self.current_section = self.last_arrival = None
                self._move(self.approach, 'SECTION_APPROACH', section_id, target.entry, target.entry_yaw)
                self.current_section = section_id
            result = self._move(self.work, 'WINDOW_MOVE', section_id, xy, yaw)
            self.check()
            self.last_arrival = tuple(self.current_xy())
            return result
        except BaseException:
            self.current_section = self.last_arrival = None
            raise

    def _move(self, navigator: Any, phase: str, section_id: str, xy: tuple, yaw: float) -> Any:
        self.check()
        self.record(dict(phase=phase, section_id=section_id, target_xy=list(xy), target_yaw=yaw))
        self.active = navigator
        navigator.preflight_navigation()
        result = navigator.navigate(xy, yaw)
        self.check()
        self.active = None
        return result

    def cancel_nav(self) -> None:
        self.current_section = self.last_arrival = None
        if self.active is not None:
            self.active.cancel_nav()
            self.active = None

