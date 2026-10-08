"""수확 활동들의 주변 영역과 공유 PhysicsScene의 필요한 주기를 결정한다.

물리 활성화는 시뮬 부하 관리용이다. 과실 정답을 로봇 목표/수확 성공으로 보내지 않는다.
"""
from dataclasses import dataclass
import math
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class RegionSettings:
    """거리 m, 속도 m/s·rad/s, 지속시간 시뮬 초, 주기 Hz."""

    idle_hz: int = 60
    harvest_hz: int = 480
    activation_radius_m: float = .8
    retention_radius_m: float = 1.
    settled_linear_m_s: float = .01
    settled_angular_rad_s: float = .1
    settled_seconds: float = .6

    @classmethod
    def from_mapping(cls, value: Mapping, render_hz: float) -> 'RegionSettings':
        if isinstance(render_hz, bool) or not isinstance(render_hz, (int, float)) or not math.isfinite(render_hz) or render_hz <= 0:
            raise ValueError('render_hz는 유한한 양수여야 합니다.')
        settings = cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})
        for key, number in vars(settings).items():
            if isinstance(number, bool) or not isinstance(number, (float, int)) or not math.isfinite(number) or number <= 0:
                raise ValueError('adaptive.'+key+'는 유한한 양수여야 합니다.')
        for hz in (settings.idle_hz, settings.harvest_hz):
            if hz % 60 != 0 or not math.isclose(hz/render_hz, round(hz/render_hz)) or hz < render_hz:
                raise ValueError('adaptive 물리는 60Hz와 렌더 주기의 양의 정수 배여야 합니다.')
        if settings.harvest_hz < settings.idle_hz or settings.retention_radius_m < settings.activation_radius_m:
            raise ValueError('수확 주기/유지 반경은 유휴 주기/활성 반경 이상이어야 합니다.')
        return settings


class HarvestRegions:
    """여러 로봇의 영역을 합치고 모든 활동이 끝난 뒤에만 낮은 주기를 요청한다."""

    def __init__(self, settings: RegionSettings) -> None:
        self.settings = settings
        self.quiet_since: float | None = None
        self.last_time: float | None = None

    def select(self, positions: np.ndarray, centers: Mapping[str, np.ndarray], active: np.ndarray) -> np.ndarray:
        """원래 과실 인덱스를 반환한다. 기존 활성 과실에는 바깥 반경을 적용한다."""
        positions, active = np.asarray(positions, dtype=float), np.asarray(active, dtype=bool)
        if positions.shape != (len(active), 3) or not np.isfinite(positions).all():
            raise ValueError('과실 위치/활성 배열을 확인하세요.')
        selected = np.zeros(len(active), dtype=bool)
        radius = np.where(active, self.settings.retention_radius_m, self.settings.activation_radius_m)
        for center in centers.values():
            point = np.asarray(center, dtype=float)
            if point.shape != (3,) or not np.isfinite(point).all():
                raise ValueError('수확 작업 중심은 유한한 world 3차원 위치여야 합니다.')
            selected |= np.linalg.norm(positions-point, axis=1) <= radius
        return np.flatnonzero(selected)

    def required_hz(self, now: float, *, requested: bool, attached_active: bool,
                    detached_velocities: np.ndarray) -> int:
        """분리 과실은 고정하지 않는다. 충분히 정지했을 때만 저주기 동역학을 허용한다."""
        velocity = np.asarray(detached_velocities, dtype=float).reshape(-1, 6)
        if not math.isfinite(now) or not np.isfinite(velocity).all() or (self.last_time is not None and now < self.last_time):
            raise ValueError('과실 속도와 단조 시뮬 시간을 확인하세요.')
        self.last_time = now
        moving = (np.any(np.linalg.norm(velocity[:, :3], axis=1) > self.settings.settled_linear_m_s)
                  or np.any(np.linalg.norm(velocity[:, 3:], axis=1) > self.settings.settled_angular_rad_s))
        if requested or attached_active or moving:
            self.quiet_since = None
            return self.settings.harvest_hz
        if not len(velocity):
            return self.settings.idle_hz
        if self.quiet_since is None:
            self.quiet_since = now
        return (self.settings.idle_hz if now-self.quiet_since >= self.settings.settled_seconds-1e-9
                else self.settings.harvest_hz)
