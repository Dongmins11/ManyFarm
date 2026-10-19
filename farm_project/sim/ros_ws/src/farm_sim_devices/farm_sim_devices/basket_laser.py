"""바구니 입구의 평행 3빔 차단으로 익명 통과를 센다. 물체 종류·방향·안착은 모른다."""
from typing import Any, Mapping, Sequence
import math
import numpy as np


class PassageCounter:
    """배출 시도마다 한 번: 어느 빔이든 차단 → 전부 연속 비차단이면 한 개다.

    여러 빔의 동시 차단과 짧은 재차단은 하나의 통과로 묶는다.
    초기 차단/시간초과는 성공이 아니며 다음 시도는 명시적인 arm이 필요하다.
    """

    def __init__(self, clear_s: float, timeout_s: float) -> None:
        if not (math.isfinite(clear_s) and math.isfinite(timeout_s) and 0 < clear_s < timeout_s):
            raise ValueError('빔 비차단 확인 시간과 통과 제한시간을 확인하세요.')
        self.clear_s, self.timeout_s = clear_s, timeout_s
        self.total = 0
        self.disarm()

    def disarm(self) -> None:
        self.state = 'DISARMED'
        self._clear_since = self._started = self._last = None
        self._beams_seen = set()

    def arm(self) -> None:
        self.disarm()
        self.state = 'CLEARING'

    def update(self, blocked: Sequence[bool], now: float) -> dict | None:
        """물리 시각(초)과 세 빔의 차단 bool만 입력받는다."""
        if len(blocked) != 3 or any(type(b) is not bool for b in blocked) or not math.isfinite(now):
            raise ValueError('유한한 시각과 세 bool 빔 입력이 필요합니다.')
        if self._last is not None and now <= self._last:
            raise ValueError('센서 시각은 증가해야 합니다.')
        self._last = now
        if self.state in ('DISARMED', 'COUNTED', 'REJECTED'):
            return None
        if self._started is not None and now-self._started > self.timeout_s:
            self.state = 'REJECTED'
            return None
        hit = any(blocked)
        if self.state == 'CLEARING':
            if hit:
                self._clear_since = None
            elif self._clear_since is None:
                self._clear_since = now
            elif now-self._clear_since+1e-9 >= self.clear_s:
                self.state = 'READY'
        elif self.state == 'READY':
            if hit:
                self.state, self._started = 'BLOCKED', now
                self._beams_seen.update(i+1 for i, b in enumerate(blocked) if b)
        elif self.state in ('BLOCKED', 'EXIT_CLEAR'):
            if hit:
                self.state, self._clear_since = 'BLOCKED', None
                self._beams_seen.update(i+1 for i, b in enumerate(blocked) if b)
            elif self.state == 'BLOCKED':
                self.state, self._clear_since = 'EXIT_CLEAR', now
            elif now-self._clear_since+1e-9 >= self.clear_s:
                self.total += 1
                self.state = 'COUNTED'
                return dict(sequence=self.total, stamp_s=now, entered_s=self._started,
                    source='basket_parallel_lasers', beams_seen=sorted(self._beams_seen),
                    direction_confirmed=False, identity_confirmed=False)
        return None


def beam_segments(box_min: Sequence[float], box_max: Sequence[float], settings: Mapping) -> tuple[np.ndarray, np.ndarray]:
    """박스 좌표계의 광축 끝점(m). 자산 생성과 런타임 배치 검사에 같은 식을 쓴다."""
    lo, hi = np.asarray(box_min, float), np.asarray(box_max, float)
    fractions = np.asarray(settings['x_fractions'], float)
    height, inset = float(settings['height_offset_m']), float(settings['end_inset_m'])
    if (lo.shape != (3,) or hi.shape != (3,) or not np.isfinite([lo, hi]).all()
            or np.any(lo >= hi) or fractions.shape != (3,) or not np.isfinite(fractions).all()
            or not np.all(np.diff(fractions) > 0) or not np.all((fractions > 0) & (fractions < 1))
            or not math.isfinite(height) or not lo[2] < hi[2]+height <= hi[2]
            or not 0 < inset < (hi[1]-lo[1])/2):
        raise ValueError('세 레이저의 간격·높이·끝점 설정이 유효하지 않습니다.')
    starts = np.array([[lo[0]+f*(hi[0]-lo[0]), lo[1]+inset, hi[2]+height] for f in fractions])
    ends = starts.copy(); ends[:, 1] = hi[1]-inset
    return starts, ends


class BasketLaserSensor:
    """USD에 저장된 광축에서 실제 PhysX ray를 쏜다. 이름/색/목표 ID로 필터하지 않는다.

    센서 링크는 로봇 USD의 base_link/BasketLasers에 영구 저장된다.
    매 tick 실제 팔 장착점 pose로 광축을 변환하며 세션에는 빔 색만 덮어쓴다.
    반사율·전자 지연을 모사하지 않는 이상적인 투과 센서다.
    """

    def __init__(self, world: Any, device: Any, settings: Mapping) -> None:
        from omni.physx import get_physx_scene_query_interface
        from pxr import UsdGeom
        self.device, self.query = device, get_physx_scene_query_interface()
        self.counter = PassageCounter(float(settings['clear_s']), float(settings['passage_timeout_s']))
        self._world, self._lines, self._visual_blocked = world, [], None
        self.last = None
        cache = UsdGeom.XformCache()
        mount = world.stage.GetPrimAtPath(device._mount_path)
        inverse = np.linalg.inv(np.asarray(cache.GetLocalToWorldTransform(mount)).T)
        starts, ends = [], []
        root = device.robot_path+'/base_link/BasketLasers'
        for i in range(1, 4):
            for side, values in (('emitter', starts), ('receiver', ends)):
                path = f'{root}/basket_laser_{i}_{side}/optical'
                prim = world.stage.GetPrimAtPath(path)
                if not prim:
                    raise ValueError('영구 레이저 장착 프림 없음: '+path)
                local = inverse @ np.asarray(cache.GetLocalToWorldTransform(prim)).T
                values.append(local[:3, 3])
            line = UsdGeom.BasisCurves(world.stage.GetPrimAtPath(f'{root}/beam_{i}'))
            if not line:
                raise ValueError('레이저 빔 표시 프림 없음: '+root)
            self._lines.append(line.GetDisplayColorAttr())
        self.origins, self.ends = np.asarray(starts), np.asarray(ends)
        expected_start, expected_end = beam_segments(device.config['box_min'], device.config['box_max'], settings)
        offset = np.asarray(device.config['policy_arm_position_m'])
        if not (np.allclose(self.origins+offset, expected_start, atol=1e-5)
                and np.allclose(self.ends+offset, expected_end, atol=1e-5)):
            raise ValueError('USD 레이저 광축과 설정 불일치: build_basket_laser_assets.py로 자산을 갱신하세요.')

    def sample(self, now: float) -> dict | None:
        """세 광축의 실제 차단을 합쳐 익명 통과 이벤트를 반환한다."""
        import carb
        from pxr import Usd
        transform = self.device.arm_world_transform()
        blocked = []
        for start, end in zip(self.origins, self.ends):
            origin = transform[:3, :3] @ start+transform[:3, 3]
            delta = transform[:3, :3] @ (end-start)
            length = float(np.linalg.norm(delta))
            blocked.append(bool(self.query.raycast_any(carb.Float3(*map(float, origin)),
                carb.Float3(*map(float, delta/length)), length, bothSides=True)))
        if blocked != self._visual_blocked:
            with Usd.EditContext(self._world.stage, self._world.stage.GetSessionLayer()):
                for attr, hit in zip(self._lines, blocked):
                    attr.Set([(1., .05, .02) if hit else (0., 1., .2)])
            self._visual_blocked = blocked
        event = self.counter.update(blocked, now)
        self.last = dict(stamp_s=now, blocked=blocked, state=self.counter.state, total=self.counter.total)
        return event
