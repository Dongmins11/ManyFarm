"""과실 꼭지의 attachment4/response6 물리만 계산합니다. 단위는 SI입니다.

인수 원본 harvest_rl/attachment_60hz.py의 coupled_wrench를 NumPy로 옮겼습니다. 파지·정책·업무 성공 판정은 포함하지 않습니다.
response6는 중력 예측을 포함한 6×6 결합식을 사용하며 중력 보상력을 더하지 않습니다.
"""
from dataclasses import dataclass, fields
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class StemSettings:
    """원본 snapshot의 줄기 설정. 질량은 kg, 거리 m, 시간 s입니다."""

    attachment_version: int = 4
    stem_response_version: int = 6
    mass: float = .009
    spring_k: float = 60.
    spring_d: float = 4.2
    angular_k: float = .015
    angular_d: float = .002
    stem_vertical_stiffness: float = 40.
    lateral_stiffness_ratio: float = .25
    valid_pull_distance: float = .012
    stem_max_extension: float = .040
    tension_hold_s: float = .040
    hook_opening_m: float = .025

    @classmethod
    def from_mapping(cls, values: Mapping) -> "StemSettings":
        result = cls(**{field.name: values[field.name] for field in fields(cls) if field.name in values})
        if (result.attachment_version, result.stem_response_version) != (4, 6):
            raise ValueError('줄기 어댑터는 attachment4/response6만 지원합니다.')
        for field in fields(cls):
            value = getattr(result, field.name)
            if not np.isfinite(value) or value < 0:
                raise ValueError('유한한 음수 아닌 줄기 설정이 필요합니다: ' + field.name)
        for key in ('mass', 'spring_k', 'stem_vertical_stiffness', 'valid_pull_distance',
                    'stem_max_extension', 'tension_hold_s', 'hook_opening_m'):
            if getattr(result, key) <= 0:
                raise ValueError('양수 줄기 설정이 필요합니다: ' + key)
        return result


@dataclass(frozen=True)
class StemStep:
    """한 물리 tick의 COM 외력/토크와 결합 결과. 힘 N, 토크 N·m."""

    force: np.ndarray
    torque: np.ndarray
    attached: np.ndarray
    timer: np.ndarray
    tension: np.ndarray
    extension: np.ndarray
    displacement: np.ndarray
    raw_tension: np.ndarray
    force_exceeded: np.ndarray
    hook_opened: np.ndarray
    max_extension_exceeded: np.ndarray


def quaternion_matrix(quaternion: np.ndarray) -> np.ndarray:
    """scalar-first (w,x,y,z) quaternion을 회전행렬로 변환합니다."""
    q = np.asarray(quaternion, dtype=float)
    if q.shape[-1] != 4 or not np.isfinite(q).all():
        raise ValueError('유한한 wxyz quaternion이 필요합니다.')
    norm = np.linalg.norm(q, axis=-1, keepdims=True)
    if np.any(norm < 1e-12):
        raise ValueError('영 quaternion은 허용되지 않습니다.')
    w, x, y, z = np.moveaxis(q / norm, -1, 0)
    return np.stack((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
                     2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
                     2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)), axis=-1).reshape(q.shape[:-1]+(3, 3))


def _quaternion_error(current: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """원본과 동일한 current * conjugate(reference)의 scalar/vector 성분."""
    q = np.asarray(current, dtype=float)
    r = np.asarray(reference, dtype=float)
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    r = r / np.linalg.norm(r, axis=-1, keepdims=True)
    scalar = (q*r).sum(axis=-1)
    vector = -q[:, :1]*r[:, 1:] + r[:, :1]*q[:, 1:] - np.cross(q[:, 1:], r[:, 1:])
    return scalar, vector


def stem_step(settings: StemSettings, *, displacement: np.ndarray, tip_velocity: np.ndarray,
              lever: np.ndarray, inverse_inertia_world: np.ndarray, tension_axis_world: np.ndarray,
              orientation_wxyz: np.ndarray, rest_orientation_wxyz: np.ndarray,
              angular_velocity: np.ndarray, attached: np.ndarray, timer: np.ndarray,
              thresholds: np.ndarray, dt_s: float, gyroscopic_forces: np.ndarray | bool = False) -> StemStep:
    """월드 좌표의 N개 꼭지 외력과 연속 이탈 타이머를 한 tick 진행합니다.

    displacement는 초기 고정 앵커에서 현재 꼭지까지, lever는 COM에서 꼭지까지입니다.
    반환 힘은 COM에, 반환 토크는 COM 주위에 적용합니다. 분리 후 외력은 0입니다.
    """
    if not np.isfinite(dt_s) or not np.isclose(dt_s, 1/60, rtol=0., atol=1e-12):
        raise ValueError('response6 물리 주기는 정확히 60Hz여야 합니다.')
    attached = np.asarray(attached, dtype=bool)
    if attached.ndim != 1:
        raise ValueError('attached는 과실별 1차원 배열이어야 합니다.')
    n = len(attached)
    arrays = dict(displacement=(displacement, (n, 3)), velocity=(tip_velocity, (n, 3)),
                  lever=(lever, (n, 3)), inertia=(inverse_inertia_world, (n, 3, 3)),
                  axis=(tension_axis_world, (n, 3)), current=(orientation_wxyz, (n, 4)),
                  rest=(rest_orientation_wxyz, (n, 4)), omega=(angular_velocity, (n, 3)),
                  timer=(timer, (n,)), thresholds=(thresholds, (n,)))
    data = {}
    for name, (value, shape) in arrays.items():
        value = np.asarray(value, dtype=float)
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError('줄기 입력 shape/유한값 오류: ' + name)
        data[name] = value
    if np.any(data['thresholds'] <= 0) or np.any(data['timer'] < 0):
        raise ValueError('분리 임계힘은 양수, 타이머는 음수 아니어야 합니다.')
    for key in ('current', 'rest'):
        if np.any(np.linalg.norm(data[key], axis=-1) < 1e-12):
            raise ValueError('영 quaternion은 허용되지 않습니다.')
    axis_norm = np.linalg.norm(data['axis'], axis=-1, keepdims=True)
    if np.any(axis_norm < 1e-12):
        raise ValueError('인장축은 영벡터가 아니어야 합니다.')
    axis = data['axis']/axis_norm
    vertical = np.array([0., 0., 1.]) - axis[:, 2:3]*axis
    vertical /= np.maximum(np.linalg.norm(vertical, axis=-1, keepdims=True), 1e-8)
    eye = np.eye(3)
    stiffness = settings.spring_k * (settings.lateral_stiffness_ratio*eye
        + (1-settings.lateral_stiffness_ratio)*axis[:, :, None]*axis[:, None, :])
    stiffness += (settings.stem_vertical_stiffness-settings.spring_k*settings.lateral_stiffness_ratio)*vertical[:, :, None]*vertical[:, None, :]
    skew = np.zeros((n, 3, 3))
    x, y, z = data['lever'].T
    skew[:, 0, 1], skew[:, 0, 2] = -z, y
    skew[:, 1, 0], skew[:, 1, 2] = z, -x
    skew[:, 2, 0], skew[:, 2, 1] = -y, x
    inertia = data['inertia']
    mobility = np.concatenate((
        np.concatenate((eye/settings.mass-skew@inertia@skew, -skew@inertia), axis=-1),
        np.concatenate((inertia@skew, inertia), axis=-1)), axis=-2)
    stiffness6 = np.zeros((n, 6, 6))
    stiffness6[:, :3, :3] = stiffness
    stiffness6[:, 3:, 3:] = settings.angular_k*eye
    effective = np.diag([settings.spring_d]*3+[settings.angular_d]*3)+dt_s*stiffness6
    scalar, vector = _quaternion_error(data['current'], data['rest'])
    orientation_error = 2*vector*np.sign(scalar)[:, None]
    position6 = np.concatenate((data['displacement'], orientation_error), axis=-1)
    velocity6 = np.concatenate((data['velocity'], data['omega']), axis=-1)
    gyro = -(inertia @ np.cross(data['omega'],
        (np.linalg.inv(inertia) @ data['omega'][..., None])[..., 0])[..., None])[..., 0]
    gyro *= np.asarray(gyroscopic_forces)[..., None]
    free_point = np.array([0., 0., -9.81])+np.cross(data['omega'], np.cross(data['omega'], data['lever']))
    free_point -= (skew @ gyro[..., None])[..., 0]
    free6 = np.concatenate((free_point, gyro), axis=-1)
    rhs = -(stiffness6 @ position6[..., None] + effective @ (velocity6+dt_s*free6)[..., None])
    wrench = np.linalg.solve(np.eye(6)+dt_s*effective@mobility, rhs)[..., 0]
    elastic, restoring = wrench[:, :3], wrench[:, 3:]
    extension = (data['displacement']*axis).sum(-1)
    tension = np.maximum(-(elastic*axis).sum(-1), 0.)
    length = np.linalg.norm(data['displacement'], axis=-1)
    magnitude = np.linalg.norm(elastic, axis=-1)
    raw_tension = tension.copy()
    force_exceeded = (raw_tension > data['thresholds']) & (extension > settings.valid_pull_distance)
    hook_opened = extension >= settings.hook_opening_m
    max_extension_exceeded = length >= settings.stem_max_extension
    exceeded = force_exceeded.copy()
    exceeded |= (length >= settings.stem_max_extension) & (magnitude > 2*data['thresholds'])
    exceeded |= hook_opened | max_extension_exceeded
    elastic *= np.minimum(1., data['thresholds']/np.maximum(magnitude, 1e-9))[:, None]
    tension = np.maximum(-(elastic*axis).sum(-1), 0.)
    new_timer = np.where(attached & exceeded, data['timer']+dt_s, 0.)
    remaining = attached & (new_timer < settings.tension_hold_s)
    force = elastic*remaining[:, None]
    torque = np.cross(data['lever'], force) + restoring*remaining[:, None]
    if not np.isfinite(force).all() or not np.isfinite(torque).all():
        raise FloatingPointError('줄기 외력 계산 결과가 유한하지 않습니다.')
    # raw_tension은 분리 판정 전 계산값, tension은 힘 한도로 제한한 복원력 성분이다.
    return StemStep(force, torque, remaining, new_timer, tension, extension, length,
                    raw_tension, force_exceeded, hook_opened, max_extension_exceeded)
