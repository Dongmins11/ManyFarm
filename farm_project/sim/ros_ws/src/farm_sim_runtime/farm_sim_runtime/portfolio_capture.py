"""실제 작업 중 외부 시점 PNG를 저장한다. 센서/제어 입력에는 연결하지 않는다."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


class PortfolioCapture:
    def __init__(self, output: Path, session: str) -> None:
        self.output = output
        output.mkdir(parents=True, exist_ok=True)
        self.session = session
        self.camera = None
        self.pending = None
        self.counts = dict(harvest=0, handoff=0, sorting=0)
        self.last = dict.fromkeys(self.counts, -100.)
        self.failed = False

    def candidates(self, robots: list, sorter: object, monitor: object) -> dict:
        """작업 상태와 실제 평가값으로 장면을 선택한다. 성공 판정은 하지 않는다."""
        values = {}
        harvest = next((r for r in robots if r['arm'] is not None), None)
        if harvest is not None:
            arm = harvest['arm'].telemetry()
            if arm.get('status') == 'RUNNING' and arm.get('stage') in ('HARVEST', 'WAIT_BOX'):
                values['harvest'] = dict(arm=arm, transform=harvest['T_world_base'].tolist())
        if monitor is not None and monitor.latest and monitor.latest.get('hold_pass'):
            # 실제 배출 기구의 동작 사진이 아닌, 두 바구니 정렬 유지 장면이다.
            values['handoff'] = dict(alignment=monitor.latest,
                transforms={role: monitor.robots[rid]['T_world_base'].tolist()
                            for role, rid in monitor.ids.items()},
                meaning='actual basket alignment; cargo transfer is virtual')
        if sorter is not None and sorter.deposited and sorter.ctl.phase in (
                'APPROACH', 'DESCEND', 'CLOSE', 'LIFT', 'TRANSFER', 'OPEN', 'VERIFY_BIN'):
            values['sorting'] = dict(phase=sorter.ctl.phase, counts=list(sorter.ctl.counts),
                                    transform=sorter.scene.transform.tolist())
        return values

    def view(self, kind: str, evidence: dict, index: int) -> tuple:
        if kind == 'handoff':
            transforms = [np.asarray(t) for t in evidence['transforms'].values()]
            center = np.mean([t[:3, 3] for t in transforms], axis=0)
            rotation = transforms[0][:3, :3]
            offset = [2.1 if index % 2 == 0 else -2.1, -2.3, 1.7]
        else:
            transform = np.asarray(evidence['transform'])
            center, rotation = transform[:3, 3].copy(), transform[:3, :3]
            offset = [1.8 if index % 2 == 0 else -1.8, -2.2, 1.7]
            if kind == 'sorting':offset = [2.5 if index % 2 == 0 else -2.5, -2.8, 2.2]
        target = center + np.array([0., 0., .65])
        return center + rotation @ np.asarray(offset), target

    def active(self, enabled: bool) -> None:
        if self.camera is not None:
            (self.camera.resume if enabled else self.camera.pause)()
            self.camera._render_product.hydra_texture.set_updates_enabled(enabled)

    def update(self, now: float, robots: list, sorter: object, monitor: object) -> None:
        """기존 렌더 프레임만 사용한다. 촬영 오류는 시험 실패로 전파하지 않는다."""
        if self.failed:return
        try:
            self._update(now, robots, sorter, monitor)
        except Exception as exc:
            self.failed = True
            try:self.active(False)
            except Exception:pass
            (self.output/'capture_error.json').write_text(json.dumps(dict(
                error=repr(exc), sim_time_s=now, session=self.session))+'\n')
            print('[portfolio_capture] disabled: '+repr(exc), flush=True)

    def _update(self, now: float, robots: list, sorter: object, monitor: object) -> None:
        from scipy.spatial.transform import Rotation
        from PIL import Image
        candidates = self.candidates(robots, sorter, monitor)
        if self.pending:
            pending = self.pending
            kind = pending['kind']
            if kind not in candidates or now-pending['started_sim_s'] > 3.:
                self.active(False);self.pending = None
                return
            frame = self.camera.get_current_frame()
            # 카메라 이동 전 영상을 저장하지 않도록 새 렌더 프레임을 기다린다.
            if float(frame.get('rendering_time', 0)) <= pending['started_sim_s']+.15:return
            rgb = self.camera.get_rgb()
            if rgb is None or rgb.shape != (1080, 1920, 3) or np.std(rgb) < 1.:return
            name = f'{kind}-{self.counts[kind]+1:02d}'
            Image.fromarray(np.asarray(rgb, dtype=np.uint8)).save(self.output/(name+'.png'))
            metadata = dict(pending, session=self.session, sim_time_s=now,
                rendering_time_s=float(frame['rendering_time']), evidence=candidates[kind],
                captured_at=datetime.now(timezone.utc).isoformat(), scope='live simulation external camera',
                resolution=[1920, 1080], overlay=False)
            (self.output/(name+'.json')).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
            self.counts[kind] += 1;self.last[kind] = now
            self.active(False);self.pending = None
            print('[portfolio_capture] saved '+str(self.output/(name+'.png')), flush=True)
            return
        kind = next((k for k in candidates if self.counts[k] < 6 and now-self.last[k] >= 4.), None)
        if kind is None:return
        if self.camera is None:
            from isaacsim.sensors.camera import Camera
            self.camera = Camera('/World/PortfolioCamera', name='portfolio_camera',
                                 frequency=30, resolution=(1920, 1080))
            self.camera.initialize()
            self.camera.set_focal_length(24.)
            self.camera.set_horizontal_aperture(36.)
            self.camera.set_clipping_range(.03, 100.)
        eye, target = self.view(kind, candidates[kind], self.counts[kind])
        forward = target-eye;forward /= np.linalg.norm(forward)
        right = np.cross(forward, [0., 0., 1.]);right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        quaternion = Rotation.from_matrix(np.column_stack((right, up, -forward))).as_quat()[[3,0,1,2]]
        self.camera.set_world_pose(eye, quaternion, camera_axes='usd')
        self.pending = dict(kind=kind, started_sim_s=now, eye_world_m=eye.tolist(), target_world_m=target.tolist())
        self.active(True)
