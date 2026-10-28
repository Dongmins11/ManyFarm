"""농장 프레임에서 원본 HCR 제어/Modbus를 구동하는 시뮬 장치 어댑터."""
import importlib.util
import json
from pathlib import Path
import time
import uuid

import numpy as np


class SorterRuntime:
    def __init__(self, scene: object, robots: list[dict], session: str) -> None:
        from hcr_sim.link import SimHCRLink
        self.scene, self.robots, self.session = scene, robots, session
        self.ctl = scene.ctl
        self.link = SimHCRLink(scene.settings['modbus_port'])
        source = scene.root / scene.settings['source_workspace'] / 'src/sorting_station/hcr/zone_preview.py'
        spec = importlib.util.spec_from_file_location('hcr_farm_vision', source)
        self.vision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.vision)
        self.vision.validate_rois(scene.rois, scene.cfg['camera']['width'], scene.cfg['camera']['height'])
        self.trackers = {n: self.vision.Stable(.3) for n in 'ABCD'}
        self.states = dict.fromkeys('ABCD', 'WAIT')
        self.ready = False
        self.camera_session = uuid.uuid4().hex
        self.last_camera = -1.
        self.counter = 0
        self.remote, self.ack, self.done = 1, 0, 0
        self.command = 0
        self.last_active = False
        self.scan_after = 0.
        self.deposited = False
        self.request_id = None
        self.pending = None
        self.deposit_result = None
        self.last_log = -1.
        self.last_image = -1.
        self.events = (scene.output / 'integration_events.jsonl').open('w')
        self.record('initialized', station_to_world=scene.transform.tolist())
        self.fixture = scene.settings.get('fixture_fruit_paths', [])
        if self.fixture:
            # 명시한 통합 시험 초기 적재이며 수확 성공 기록으로 사용하지 않는다.
            self.load_fixture()

    def record(self, event: str, **values: object) -> None:
        self.events.write(json.dumps(dict(event=event, wall=time.time(), session=self.session, **values), ensure_ascii=False)+'\n')
        self.events.flush()

    def write(self, name: str, value: dict) -> None:
        file = self.scene.output / name
        tmp = file.with_suffix('.tmp')
        tmp.write_text(json.dumps(value, ensure_ascii=False))
        tmp.replace(file)

    def transport(self) -> dict:
        return next(r for r in self.robots if r['cfg']['robot_id'] == self.scene.settings['transport_robot_id'])

    def cargo_pose(self) -> np.ndarray:
        from pxr import UsdGeom
        robot = self.transport()
        bodies = [p for p in self.scene.stage.Traverse() if p.GetName() == 'cargo_box'
                  and str(p.GetPath()).startswith(robot['path'])]
        if len(bodies) != 1:
            raise ValueError('기존 운송 cargo_box가 하나여야 합니다.')
        return np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(bodies[0])).T

    def load_fixture(self) -> None:
        from scipy.spatial.transform import Rotation
        pose = self.cargo_pose()
        if len(self.fixture) > 4:
            raise ValueError('단독 초기 적재 fixture는 최대4개; 실제 배치는 별도 manifest 필요')
        local = np.array([[-.15 + .06*(i//2), -.06 + .12*(i%2), .08] for i in range(len(self.fixture))])
        positions = local @ pose[:3, :3].T + pose[:3, 3]
        quat = Rotation.from_matrix(pose[:3, :3]).as_quat()[[3, 0, 1, 2]]
        self.scene.physics.attachments.relocate_detached(self.fixture, positions,
            np.tile(quat, (len(positions), 1)), fixture=True)
        self.record('fixture_loaded', paths=self.fixture, actual_harvest_tested=False)

    def deposit(self, now: float) -> None:
        from hcr_sim.model import lane_centers, ramp_surface_z
        request_file = self.scene.output / 'deposit_request.json'
        try:
            request = json.loads(request_file.read_text())
        except (OSError, ValueError):
            return
        if request.get('request_id') == self.request_id:
            return
        self.request_id = request.get('request_id')
        try:
            if request.get('session') != self.session or not self.request_id:
                raise ValueError('현재 시뮬 세션의 투입 요청 필요')
            if self.deposited or self.pending or self.ctl.phase not in ('IDLE', 'SCANNING'):
                raise ValueError('현재 배치는 투입중/선별중/이미투입됨')
            robot = self.transport()
            if np.linalg.norm(robot['base'].robot.get_linear_velocity()[:2]) >= .005 or abs(robot['base'].robot.get_angular_velocity()[2]) >= .02:
                raise ValueError('차체 정지 필요')
            position = robot['base'].pose()[0]
            local = self.scene.rotation.inv().apply(position-self.scene.origin)
            if not .70 < local[0] < 1.30 or abs(local[1]) > .30:
                raise ValueError('선별장 투입면 앞 도킹 위치가 아님: '+str(local.tolist()))
            paths = request['fruit_paths']
            if not paths or len(paths) != len(set(paths)):
                raise ValueError('실제 적재 prim 목록 필요')
            attachments=self.scene.physics.attachments
            indices=np.array([attachments.paths.index(path) for path in paths],dtype=np.int32)
            actual=attachments.current_positions()[indices]
            cargo=self.cargo_pose()
            inside=(actual-cargo[:3,3])@cargo[:3,:3]
            if not (np.all(inside[:,0]>-.33) and np.all(inside[:,0]<.03)
                    and np.all(np.abs(inside[:,1])<.17)
                    and np.all(inside[:,2]>-.03) and np.all(inside[:,2]<.25)):
                raise ValueError('적재 목록 중 운송 바구니 안에 없는 과실이 있음')
            # 기존 과실만 이동하며 줄기 부착 여부를 다시 검사한다.
            lanes = list(lane_centers(self.scene.cfg).values())
            positions = []
            for i, path in enumerate(paths):
                prim = self.scene.stage.GetPrimAtPath(path)
                if prim.GetAttribute('crop:color').Get() not in ('red', 'yellow'):
                    raise ValueError('선별 대상 과실이 아님')
                x = self.scene.cfg['intake']['low_x'] + .07 + (i//4)*.11
                if x > .65:
                    raise ValueError('배치가 레인 투입 용량을 초과함')
                z = ramp_surface_z(self.scene.cfg, x) + self.scene.cfg['physics']['pepper_length']/2 + .005
                positions.append(self.scene.origin+self.scene.rotation.apply([x, lanes[i%4], z]))
            quat = self.scene.rotation.as_quat()[[3, 0, 1, 2]]
            self.scene.physics.attachments.relocate_detached(paths, np.array(positions), np.tile(quat, (len(paths), 1)))
            self.scene.bind(paths)
            self.pending = dict(request_id=self.request_id, task_id=request['task_id'], paths=paths, at=now)
            self.record('virtual_deposit', **self.pending, mechanism_physics=False)
        except Exception as exc:
            self.deposit_result = dict(request_id=self.request_id, success=False, error=str(exc))
            self.record('deposit_rejected', **self.deposit_result)

    def before_frame(self, now: float, dt: float, playing: bool = True) -> None:
        if not playing:
            if self.remote == 2:
                self.ctl.fail('SIM_PAUSED_DURING_SORT')
            self.link.status(4 if self.ctl.error else 0, self.ack, self.done, 1 if self.ctl.error else 0)
            return
        self.deposit(now)
        if self.pending and now-self.pending['at'] >= self.scene.settings['deposit_settle_s']:
            coords = [f['object'].data.root_pos_w[0].numpy() for f in self.scene.fruits]
            okay = all(.23 < p[0] < .72 and abs(p[1]) < .253 and .04 < p[2] < .40 for p in coords)
            self.deposited = okay
            self.deposit_result = dict(request_id=self.pending['request_id'], success=okay,
                fruit_paths=self.pending['paths'], count=len(coords), error='' if okay else 'FRUIT_OUTSIDE_LANES')
            self.record('deposit_result', **self.deposit_result)
            self.pending = None
        if self.link.error:
            self.ctl.fail(self.link.error)
        if self.link.latest is not None:
            command, job, request, active, heartbeat = self.link.latest
            if active and not self.last_active:
                self.ctl.counts = [0, 0]
            self.last_active = bool(active)
            if self.ctl.error:
                self.remote = 4
            elif self.remote == 1 and active and request and job != self.done and self.ready:
                if not self.deposited or command not in (11,12,21,22,31,32,41,42):
                    self.ctl.fail('NO_VALID_INPUT_BATCH')
                    self.remote = 4
                else:
                    self.ack, self.command, self.remote = job, command, 2
                    self.ctl.active = True
            elif self.remote == 2 and self.ctl.phase in ('IDLE', 'SCANNING') and not request:
                if command != self.command or not active or job != self.ack:
                    self.ctl.fail('REQUEST_CHANGED_AFTER_ACK')
                else:
                    self.ctl.choose('ABCD'[command//10-1], 'RED' if command%10==1 else 'YELLOW', now, self.ack)
            elif self.ctl.phase == 'DONE' and self.remote == 2:
                self.remote, self.done = 3, self.ack
            elif self.remote == 3 and command == 0 and request == 0:
                self.remote = 1
                self.ctl.ready_again(now)
                self.scan_after = now+.5
        previous_q = self.ctl.q.copy()
        self.ctl.tick(now, self.ready and now >= self.scan_after and self.deposited, self.states, allow_select=False)
        self.scene.command(dt, previous_q)
        self.link.status(self.remote if self.ready or self.remote != 1 else 0, self.ack, self.done, 1 if self.ctl.error else 0)

    def after_frame(self, now: float) -> None:
        import cv2
        frame = self.scene.camera.get_current_frame()
        stamp = float(frame.get('rendering_time', -1.))
        rgba = frame.get('rgba', frame.get('rgb'))
        if rgba is None:
            rgba = self.scene.camera.get_rgba()
        if stamp > self.last_camera and np.shape(rgba)[:2] == (self.scene.cfg['camera']['height'], self.scene.cfg['camera']['width']):
            self.last_camera = stamp
            bgr = np.ascontiguousarray(np.asarray(rgba)[:, :, :3][:, :, ::-1])
            self.states = {n:self.trackers[n].update(self.vision.classify(bgr[y:y+h,x:x+w],.08,90,60)[0], now)
                for n,(x,y,w,h) in self.scene.rois.items()}
            self.counter += 1
            self.ready = True
            self.write('state.json', dict(monotonic=time.monotonic(), timestamp=time.time(), ready=True,
                camera_session=self.camera_session, counter=self.counter, zone_states=self.states, simulation=True))
            if now-self.last_image >= 1.:
                cv2.imwrite(str(self.scene.output/'camera_rgb.png'),bgr)
                self.last_image = now
        if now-self.last_log >= .2:
            self.last_log = now
            self.write('runtime.json', dict(session=self.session, sim_time=now, ready=self.ready,
                phase=self.ctl.phase, counts=self.ctl.counts, error=self.ctl.error,
                deposited=self.deposited, deposit_result=self.deposit_result, roi_states=self.states))
            self.write('physical_report.json', self.scene.report())
            lidar=self.transport().get('lidar')
            if lidar is not None and hasattr(lidar,'front_diagnostic'):
                self.record('front_lidar',sim_time=now,**lidar.front_diagnostic)

    def close(self) -> None:
        self.write('physical_report.json', self.scene.report())
        self.ctl.release()
        self.ctl.restore_collisions()
        self.link.close()
        self.scene.camera.pause()
        self.events.close()
