"""Existing Waffle URDF: prescribed base/joint motion, free payload contacts."""
import math
import numpy as np
from scipy.spatial.transform import Rotation
from .model import ramp_surface_z
from .transport_asset import spawn_transport, URDF


class Transport:
    def __init__(self, cfg, fruits):
        self.asset, self.usd_path, self.geometry = spawn_transport(cfg)
        self.cfg, self.c, self.fruits = cfg, cfg['transport'], fruits
        self.phase = 'LOADING' if self.c.get('payload_layout', 'random') == 'random' else 'WAIT_START'
        self.since = 0
        self.error = ''
        self.events = []
        self.angle = 0
        self.gate = 0
        self.x = self.c['start_front_x']
        self.dump_snapshot = None
        self.rock_remaining = int(self.c.get('rock_cycles', 0))
        self.start_requested = False
        self.loading_stable_since = None
        self.loading_snapshot = None

    def initialize(self):
        self.asset['initialize']()

    @property
    def ready(self):
        return self.phase == 'READY'

    def start(self, now):
        if self.phase == 'LOADING':
            self.start_requested = True
        elif self.phase == 'WAIT_START':
            self.enter('APPROACH', now)

    def loading_status(self):
        g, bodies = self.geometry, []
        c = g['config']
        axis = np.array([self.x, 0., g['cargo_zero'][2]])
        yaw = np.diag([-1., -1., 1.])
        for f in self.fruits:
            data = f['object'].data
            p = data.root_pos_w[0].cpu().numpy()
            q = data.root_quat_w[0].cpu().numpy()
            rotation = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
            points = (f['loading_points'] @ rotation.T + p - axis) @ yaw.T
            lo, hi = points.min(axis=0), points.max(axis=0)
            # Actual collision hull vertices, not just the root or bounding box.
            tolerance = .004
            inside = bool(lo[0] >= -c['box_length'] + c['wall_thickness'] - tolerance
                and hi[0] <= -c['wall_thickness'] + tolerance
                and lo[1] >= -c['box_width']/2 + c['wall_thickness'] - tolerance
                and hi[1] <= c['box_width']/2 - c['wall_thickness'] + tolerance
                and lo[2] >= g['floor_top'] - tolerance and hi[2] <= c['box_height'] + tolerance)
            bodies.append(dict(inside=inside, xyz=p.tolist(), quat_wxyz=q.tolist(),
                bounds_cargo=[lo.tolist(), hi.tolist()],
                linear_speed=float(np.linalg.norm(data.root_lin_vel_w[0].cpu().numpy())),
                angular_speed=float(np.linalg.norm(data.root_ang_vel_w[0].cpu().numpy()))))
        return dict(all_inside=all(b['inside'] for b in bodies), bodies=bodies,
            settled=all(b['linear_speed'] < .035 and b['angular_speed'] < .4 for b in bodies))

    def enter(self, phase, now):
        self.phase, self.since = phase, now
        self.events.append(dict(phase=phase, time=now))
        if phase == 'READY':
            self.dump_snapshot = dict(time=now, total=len(self.fruits),
                all_on_intake=self.all_on_intake(),
                payload_xyz=[f['object'].data.root_pos_w[0].cpu().tolist() for f in self.fruits])
        print('TRANSPORT', phase, f't={now:.2f}', flush=True)

    def all_on_intake(self):
        r = self.cfg['intake']
        high = r['low_x'] + math.sqrt(r['slope_length']**2-r['rise']**2)
        axis = np.array([self.x, 0., self.geometry['cargo_zero'][2]])
        box_rotation = np.diag([-1., -1., 1.]) @ Rotation.from_euler('y', self.angle).as_matrix()
        for f in self.fruits:
            x,y,z = f['object'].data.root_pos_w[0].cpu().numpy()
            surface = ramp_surface_z(self.cfg, x)
            if not (r['low_x']-.025 < x < high+.015 and abs(y) < r['width']/2
                    and surface-.01 < z < surface+.16):
                return False
            q = f['object'].data.root_quat_w[0].cpu().numpy()
            fruit_rotation = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
            world_points = f['loading_points'] @ fruit_rotation.T + [x, y, z]
            cargo_points = (world_points - axis) @ box_rotation
            # The original front plane is cargo-local X=0. Intake proximity
            # alone can include peppers still sitting on the tilted box floor.
            if cargo_points[:, 0].min() <= 0:
                return False
        return True

    def tick(self, now):
        elapsed = now-self.since
        c = self.c
        def smooth(t):
            t = np.clip(t,0,1)
            return float(t*t*(3-2*t))
        if self.phase == 'LOADING':
            status = self.loading_status()
            if elapsed >= self.c.get('loading_seconds', 4.) and status['all_inside'] and status['settled']:
                if self.loading_stable_since is None:
                    self.loading_stable_since = now
                if now - self.loading_stable_since >= .5:
                    self.loading_snapshot = dict(time=now, **status)
                    self.enter('WAIT_START', now)
                    if self.start_requested:
                        self.enter('APPROACH', now)
            else:
                self.loading_stable_since = None
                if elapsed >= self.c.get('loading_timeout_seconds', 12.):
                    self.error = 'TRANSPORT_LOADING_FAILED: cargo did not settle inside original box'
                    self.enter('ERROR', now)
        elif self.phase == 'APPROACH':
            self.x = c['start_front_x'] + (c['staging_front_x']-c['start_front_x'])*smooth(elapsed/c['approach_seconds'])
            if elapsed >= c['approach_seconds']:
                self.enter('OPEN_GATE',now)
        elif self.phase == 'OPEN_GATE':
            self.gate = self.geometry['limits']['side_lid_joint']*smooth(elapsed/c['gate_seconds'])
            if elapsed >= c['gate_seconds']:
                self.enter('DOCK',now)
        elif self.phase == 'DOCK':
            self.x = c['staging_front_x'] + (c['dock_front_x']-c['staging_front_x'])*smooth(elapsed/c['dock_seconds'])
            if elapsed >= c['dock_seconds']:
                self.enter('TIP',now)
        elif self.phase == 'TIP':
            self.angle = math.radians(c['tip_deg'])*smooth(elapsed/c['tip_seconds'])
            if elapsed >= c['tip_seconds']:
                self.enter('DUMP',now)
        elif self.phase == 'DUMP':
            if elapsed >= c['dump_seconds']:
                self.enter('SETTLE',now)
        elif self.phase == 'SETTLE':
            if elapsed >= c['settle_seconds'] and self.all_on_intake():
                self.enter('READY',now)
            elif elapsed >= c['settle_seconds'] and self.rock_remaining > 0:
                self.rock_remaining -= 1
                self.enter('ROCK_DOWN',now)
            elif elapsed >= c['timeout_seconds']:
                self.error = 'TRANSPORT_DUMP_INCOMPLETE: inspect original box / intake'
                self.enter('ERROR',now)
        elif self.phase == 'ROCK_DOWN':
            high, low = math.radians(c['tip_deg']), math.radians(c['rock_min_deg'])
            self.angle = high + (low-high)*smooth(elapsed/c['rock_seconds'])
            if elapsed >= c['rock_seconds']:
                self.enter('ROCK_UP',now)
        elif self.phase == 'ROCK_UP':
            high, low = math.radians(c['tip_deg']), math.radians(c['rock_min_deg'])
            self.angle = low + (high-low)*smooth(elapsed/c['rock_seconds'])
            if elapsed >= c['rock_seconds']:
                self.enter('DUMP',now)
        self.asset['set_pose'](self.x,self.angle,self.gate)

    def report(self):
        return dict(phase=self.phase,error=self.error,events=self.events,
                    dump_snapshot=self.dump_snapshot,
                    loading_snapshot=self.loading_snapshot,
                    payload_layout=self.c.get('payload_layout', 'random'),
                    payload_seed=self.c.get('payload_seed', 43),
                    source_urdf=str(URDF),usd_path=self.usd_path,
                    box_angle_deg=math.degrees(self.angle),free_rigid_body_dump=True,
                    scripted_navigation=True,scripted_cargo_joints=True,kinematic_links=self.asset['bodies'],
                    joint_targets=self.asset['joints'].copy(),
                    payload_xyz=[f['object'].data.root_pos_w[0].cpu().tolist() for f in self.fruits])
