"""성공한 window 도착 허용거리를 진입 판정에 전달한다. 단위 m."""
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WindowEntryReference:
    window_id: str
    xy: tuple[float, float]
    position_limit: float

    @classmethod
    def from_arrival(cls, goal: Any, arrival: dict) -> 'WindowEntryReference':
        task = goal.harvest_task
        xy = (float(task.goal_pose.position.x), float(task.goal_pose.position.y))
        measurement = arrival['measurement']
        limit = measurement['position_tolerance_m']
        if (measurement.get('accepted') is not True or isinstance(limit, bool)
                or not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit <= 0):
            raise ValueError('성공한 window 도착 결과와 유효한 위치 허용오차가 필요합니다.')
        measured_goal = measurement['goal_map']
        if (not all(math.isfinite(v) for v in xy)
                or (measured_goal['x'], measured_goal['y']) != xy):
            raise ValueError('window 목표와 도착 결과 좌표가 일치하지 않습니다.')
        return cls(str(task.window_id), xy, float(limit))

    def check_position(self, current_xy: tuple[float, float]) -> None:
        error = math.hypot(current_xy[0]-self.xy[0], current_xy[1]-self.xy[1])
        if not math.isfinite(error) or error > self.position_limit:
            raise RuntimeError(
                f'현재 위치가 window 진입 허용범위 밖입니다: window={self.window_id}, '
                f'current=({current_xy[0]:.6f}, {current_xy[1]:.6f}), '
                f'goal=({self.xy[0]:.6f}, {self.xy[1]:.6f}), '
                f'error_m={error:.6f}, limit_m={self.position_limit:.6f}')
