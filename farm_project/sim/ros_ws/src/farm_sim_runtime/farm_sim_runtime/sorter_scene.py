"""HCR 기능 근사 모델을 농장 World 안에 배치하고 기존 과실 view를 바인딩한다."""
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


class LocalBody:
    """원본 HCR의 로컬 좌표 계약을 유지하는 기존 PhysX 과실 읽기 어댑터."""
    def __init__(self, owner: object, path: str) -> None:
        self.owner, self.path = owner, path

    @property
    def data(self) -> SimpleNamespace:
        import torch
        from scipy.spatial.transform import Rotation
        attachment = self.owner.physics.attachments
        index = attachment.paths.index(self.path)
        pos, quat = attachment.view.get_world_poses(indices=np.array([index], dtype=np.int32))
        rotation = Rotation.from_quat(np.asarray(quat)[0][[1, 2, 3, 0]])
        local_q = (self.owner.rotation.inv() * rotation).as_quat()[[3, 0, 1, 2]]
        local_p = self.owner.rotation.inv().apply(np.asarray(pos)[0] - self.owner.origin)
        return SimpleNamespace(root_pos_w=torch.tensor(local_p[None]),
                               root_quat_w=torch.tensor(local_q[None]))


class LocalArm:
    """같은 관절/링크 측정을 HCR 로컬 프레임으로 제공한다. 제어값은 변경하지 않는다."""
    def __init__(self, owner: object) -> None:
        self.owner = owner
        self.body_names = ['link6']

    @property
    def data(self) -> SimpleNamespace:
        import torch
        from pxr import UsdGeom, Usd
        from scipy.spatial.transform import Rotation
        world = np.asarray(UsdGeom.Xformable(self.owner.stage.GetPrimAtPath(
            '/World/HCRRobot/link6')).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
        local = self.owner.inverse @ world
        quat = Rotation.from_matrix(local[:3, :3]).as_quat()[[3, 0, 1, 2]]
        return SimpleNamespace(joint_pos=torch.tensor(self.owner.robot.get_joint_positions()[None]),
            body_pos_w=torch.tensor(local[:3, 3][None, None]),
            body_quat_w=torch.tensor(quat[None, None]))


class SorterScene:
    """생성은 reset 전, initialize는 reset 후. 별도 SimulationContext를 만들지 않는다."""
    def __init__(self, stage: object, root: Path, settings: dict, physics: object) -> None:
        from pxr import Gf, UsdGeom, UsdPhysics, PhysxSchema
        from scipy.spatial.transform import Rotation
        self.stage, self.root, self.settings, self.physics = stage, root, settings, physics
        if physics is None:
            raise ValueError('선별 통합에는 농장 기존 과실 물리 프로파일이 필요합니다.')
        source = root / settings['source_workspace']
        sys.path.insert(0, str(source / 'src/sorting_station'))
        self.cfg = json.loads((source / settings['source_config']).read_text())
        self.rois = json.loads((source / settings['source_roi']).read_text())['rois']
        self.output = root / settings['output_dir']
        self.output.mkdir(parents=True, exist_ok=True)
        self.rotation = Rotation.from_euler('z', settings['station_yaw_rad'])
        self.origin = np.array(settings['station_pose_world_m'], dtype=float)
        self.transform = np.eye(4)
        self.transform[:3, :3], self.transform[:3, 3] = self.rotation.as_matrix(), self.origin
        self.inverse = np.linalg.inv(self.transform)
        old = stage.GetPrimAtPath(settings['replace_prim'])
        if old.IsValid():
            old.SetActive(False)  # 세션 layer에서만 교체; 원본 농장 USD는 저장하지 않는다.
        from hcr_sim.scene import create_station
        create_station(self.cfg)
        station = UsdGeom.Xformable(stage.GetPrimAtPath('/World/HCRStation'))
        station.ClearXformOpOrder()
        station.AddTransformOp().Set(Gf.Matrix4d(*map(float, self.transform.T.flat)))
        arm = UsdGeom.Xform.Define(stage, '/World/HCRRobot')
        arm.GetPrim().GetReferences().AddReference(str(root / settings['robot_asset']))
        arm.ClearXformOpOrder()
        pose = self.transform.copy()
        pose[:3, 3] += self.rotation.apply([0, 0, self.cfg['base_z']])
        arm.AddTransformOp().Set(Gf.Matrix4d(*map(float, pose.T.flat)))
        for prim in list(stage.Traverse()):
            if not str(prim.GetPath()).startswith('/World/HCRRobot'):
                continue
            if prim.IsInstance():
                prim.SetInstanceable(False)
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                PhysxSchema.PhysxRigidBodyAPI.Apply(prim).CreateDisableGravityAttr(True)
            if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                PhysxSchema.PhysxArticulationAPI.Apply(prim).CreateEnabledSelfCollisionsAttr(False)
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                collision = PhysxSchema.PhysxCollisionAPI.Apply(prim)
                collision.CreateContactOffsetAttr(.001)
                collision.CreateRestOffsetAttr(0.)
            if prim.IsA(UsdPhysics.Joint) and prim.GetName().startswith('joint'):
                drive = UsdPhysics.DriveAPI.Apply(prim, 'angular')
                drive.CreateStiffnessAttr(1200.)
                drive.CreateDampingAttr(80.)
                drive.CreateMaxForceAttr(150.)
            elif prim.IsA(UsdPhysics.PrismaticJoint):
                drive = UsdPhysics.DriveAPI.Apply(prim, 'linear')
                drive.CreateStiffnessAttr(400.)
                drive.CreateDampingAttr(20.)
                drive.CreateMaxForceAttr(20.)
                PhysxSchema.PhysxJointAPI.Apply(prim).CreateMaxJointVelocityAttr(.06)
        self.fruits = []
        self.arm = LocalArm(self)
        self.camera = None

    def register(self, world: object) -> None:
        from isaacsim.core.prims import SingleArticulation
        self.robot = world.scene.add(SingleArticulation('/World/HCRRobot', name='hcr_sorting_arm'))

    def initialize(self) -> None:
        from hcr_sim.control import Sorter
        from isaacsim.core.utils.types import ArticulationAction
        from isaacsim.sensors.camera import Camera
        from scipy.spatial.transform import Rotation
        self.robot.initialize()
        self.arm_ids = [self.robot.get_dof_index('joint' + str(i)) for i in range(1, 7)]
        self.jaw_ids = [self.robot.get_dof_index(n) for n in ('left_jaw', 'right_jaw')]
        self.ctl = Sorter(self.cfg, self.arm, self.fruits)
        self.ctl.arm_ids = self.arm_ids
        self.ctl.lane_map = self.settings['lane_map']
        q = self.robot.get_joint_positions()
        q[self.arm_ids], q[self.jaw_ids] = self.ctl.q, self.ctl.open_jaw
        self.robot.set_joint_positions(q)
        self.robot.set_joint_velocities(np.zeros_like(q))
        self.robot.apply_action(ArticulationAction(joint_positions=q))
        c = self.cfg['camera']
        eye = self.origin + self.rotation.apply(c['eye'])
        target = self.origin + self.rotation.apply(c['target'])
        forward = (target-eye) / np.linalg.norm(target-eye)
        right = np.cross(forward, self.rotation.apply([0, 0, 1.]))
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        quaternion = Rotation.from_matrix(np.column_stack((right, up, -forward))).as_quat()[[3, 0, 1, 2]]
        self.camera = Camera('/World/SortingCamera', name='hcr_sort_camera',
            frequency=self.settings['camera_fps'], resolution=(c['width'], c['height']))
        self.camera.initialize()
        self.camera.set_world_pose(eye, quaternion, camera_axes='usd')
        self.camera.set_focal_length(24.)
        self.camera.set_horizontal_aperture(48 * math.tan(math.radians(c['horizontal_fov_deg'])/2))
        self.camera.set_clipping_range(.01, 10.)

    def bind(self, paths: list[str]) -> None:
        """이 배치의 실제 과실 prim만 연결. 새 과실 생성/색상 변경을 하지 않는다."""
        from hcr_sim.model import lane_centers
        if len(paths) != len(set(paths)) or not paths:
            raise ValueError('중복 없는 실제 투입 과실 목록 필요')
        records = {x['prim_path']: x for x in self.physics.fruits}
        values = []
        for path in paths:
            if path not in records:
                raise ValueError('농장 과실이 아님: ' + path)
            color = str(self.stage.GetPrimAtPath(path).GetAttribute('crop:color').Get()).upper()
            if color not in ('RED', 'YELLOW'):
                raise ValueError('선별 대상 색상이 아님: ' + color)
            obj = LocalBody(self, path)
            y = obj.data.root_pos_w[0, 1].item()
            lane = min(lane_centers(self.cfg), key=lambda k: abs(lane_centers(self.cfg)[k]-y))
            values.append(dict(object=obj, path=path, color=color, lane=lane, sorted=False))
        self.fruits[:] = values

    def command(self, dt: float, previous_q: np.ndarray) -> None:
        from isaacsim.core.utils.types import ArticulationAction
        q = self.robot.get_joint_positions()
        q[self.arm_ids], q[self.jaw_ids] = self.ctl.q, self.ctl.jaw
        # 원본 run_hcr_sim의 위치/속도 목표를 동일하게 전달한다.
        velocity = np.zeros_like(q)
        velocity[self.arm_ids] = np.clip((self.ctl.q-previous_q)/dt, -2, 2)
        self.robot.apply_action(ArticulationAction(joint_positions=q, joint_velocities=velocity))

    def report(self) -> dict:
        return dict(phase=self.ctl.phase, counts=self.ctl.counts, error=self.ctl.error,
            events=self.ctl.events, station_to_world=self.transform.tolist(),
            fruits=[dict(path=f['path'], color=f['color'], sorted=f['sorted'],
                         local_xyz=f['object'].data.root_pos_w[0].tolist()) for f in self.fruits])
