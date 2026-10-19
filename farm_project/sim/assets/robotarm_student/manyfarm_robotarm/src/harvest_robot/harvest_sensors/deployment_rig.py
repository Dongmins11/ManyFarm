"""Isaac single-environment 30Hz acquisition, independent of 20Hz policy."""
import numpy as np
from .isaac_rig import StudentD435Rig
from .deployment import validate_deployment, PhysicsCaptureClock, expected_poses


class DeploymentD435Rig(StudentD435Rig):
    def __init__(self, kin, config, world_from_robot=None):
        super().__init__(kin, validate_deployment(config), world_from_robot)
        self.config = config
        self.kin = kin; self.world_from_robot = world_from_robot
        self.active = False; self.recorder = None; self.clock = None

    def install_physics_hook(self, env):
        if env.num_envs != 1:
            raise ValueError('High resolution Student capture requires one environment')
        self.env = env
        self._install_wrist_visuals()
        self.clock = PhysicsCaptureClock(env.physics_dt, env.step_dt, self.config['fps'])
        original = env.scene.update
        def update(dt):
            original(dt)
            if self.active and self.clock.advance(dt):
                self._acquire()
        # Installed only on this camera-evaluation scene; Teacher class untouched.
        env.scene.update = update

    def _install_wrist_visuals(self):
        # Replace only the imported visual group. Old rigid-body mass, inertia,
        # collisions and drives remain in the preserved Teacher USD.
        import sys,xml.etree.ElementTree as ET
        from pxr import UsdGeom,UsdShade,UsdPhysics,Sdf,Gf,Vt
        from harvest_rl.settings import ROOT,URDF
        sys.path.insert(0,str(ROOT/'src/smartfarm_description/scripts'))
        from model_geometry import visuals,fk
        stage=self.env.sim.stage
        def physical_properties():
            result={}
            for prim in stage.Traverse():
                physics=any(str(schema).startswith(('Physics','Physx')) for schema in prim.GetAppliedSchemas()) or prim.IsA(UsdPhysics.Joint)
                if physics:
                    for attr in prim.GetAttributes():
                        if attr.GetName()!='visibility':result[str(attr.GetPath())]=str(attr.Get())
            return result
        preserved=physical_properties()
        # Appearance bindings only: collision/mass geometry stays preserved.
        import json
        appearance=json.loads((ROOT/'src/harvest_robot/config/arm_appearance.json').read_text())
        material=UsdShade.Material.Define(stage,'/World/StudentArmAppearance')
        shader=UsdShade.Shader.Define(stage,'/World/StudentArmAppearance/Shader')
        shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateOutput('surface',Sdf.ValueTypeNames.Token)
        shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*appearance['rgba'][:3]))
        shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.65)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
        self.arm_appearance_groups=0
        for prim in stage.Traverse():
            path=str(prim.GetPath())
            if path.endswith('/visuals') and prim.GetParent().GetName().startswith(('arm_1_','arm_2_')):
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,bindingStrength=UsdShade.Tokens.strongerThanDescendants)
                self.arm_appearance_groups+=1
        groups=[p for p in stage.Traverse() if str(p.GetPath()).endswith('/arm_2_gripper_link/visuals')]
        if len(groups)!=1:raise ValueError('Cannot identify preserved wrist visual group')
        UsdGeom.Imageable(groups[0]).CreateVisibilityAttr().Set('invisible')
        self.visual_group=UsdGeom.Xform.Define(stage,'/World/StudentWristVisuals')
        self.visual_transform=self.visual_group.AddTransformOp()
        root=ET.parse(URDF).getroot();poses=fk(root,{})
        reference=np.linalg.inv(self.kin.fk(np.zeros(6),'arm_2/gripper_link'))
        allowed={'arm_2/gripper_link','arm_2/gripper_frame_link','arm_2/tool0'}
        allowed|={link.get('name') for link in root.findall('link') if link.get('name').startswith('arm_2/wrist_camera')}
        for link in list(root.findall('link')):
            if link.get('name') not in allowed:root.remove(link)
        count=0
        for name,tri,colour in visuals(root,URDF,poses):
            points=tri.reshape(-1,3)@reference[:3,:3].T+reference[:3,3]
            mesh=UsdGeom.Mesh.Define(stage,f'/World/StudentWristVisuals/Mesh_{count}')
            mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points.astype(np.float32)))
            mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(tri),3,np.int32)))
            mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(np.arange(len(points),dtype=np.int32)))
            mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDoubleSidedAttr(True)
            c=tuple(colour[:3]) if 'camera' in name else (.06,.06,.065)
            mesh.CreateDisplayColorAttr([Gf.Vec3f(*c)]);count+=1
        self.visual_mesh_count=count
        if not count:raise ValueError('No current wrist CAD visuals')
        if physical_properties()!=preserved:raise ValueError('Display change modified a physics property')
        self.physics_properties_checked=len(preserved)

    def follow_wrist(self, position_w, quat_wxyz):
        super().follow_wrist(position_w,quat_wxyz)
        if hasattr(self,'visual_transform'):
            from pxr import Gf
            from scipy.spatial.transform import Rotation
            def cpu(x):return x.detach().cpu().numpy() if hasattr(x,'detach') else np.asarray(x)
            wrist=np.eye(4);wrist[:3,3]=cpu(position_w)
            wrist[:3,:3]=Rotation.from_quat(cpu(quat_wxyz)[[1,2,3,0]]).as_matrix()
            self.visual_transform.Set(Gf.Matrix4d(wrist.T))

    def reset(self):
        self.active = False; self._last.clear(); self.recorder = None
        if self.clock is not None: self.clock.reset()

    def begin_episode(self, recorder):
        self.reset(); self.recorder = recorder; self.active = True
        self._acquire()

    def _acquire(self):
        env = self.env
        q = env.robot.data.joint_pos[0, env.jids].cpu().numpy().copy()
        self.follow_wrist(env.robot.data.body_link_pos_w[0, env.tcp_body],
                          env.robot.data.body_link_quat_w[0, env.tcp_body])
        env.sim.forward()
        # Two render passes propagate a changed Fabric/world sensor pose on the
        # installed Isaac build. Neither advances simulation time/physics.
        env.sim.render(); env.sim.render()
        expected = expected_poses(self.kin, q, self.config, self.world_from_robot)
        for name, pair in self.cameras.items():
            for camera in pair.values(): camera.update(0., force_recompute=True)
            data = self._capture_view(name)
            error = max(float(np.abs(t-expected[name][s]).max()) for s,t in data['world_from_optical'].items())
            if error > 2e-4: raise RuntimeError(f'Acquisition FK mismatch {name}: {error}')
            data.update(frame_number=self.clock.sequence, stamp_s=self.clock.stamp,
                pose_stamp_s=self.clock.stamp, capture_joint_rad=q.tolist(), fk_max_error=error)
            self._last[name] = data
        if self.recorder is not None: self.recorder.append(self._last)

    def update(self, dt):
        if self.active:
            raise RuntimeError('Deployment frames are acquired by the physical-step hook')
        # Static preview only, with its own explicit capture clock.
        super().update(dt)

    def capture(self):
        if not self.active: return super().capture()
        if not self._last: raise RuntimeError('No frame in this episode')
        return {name: dict(data, image_age_s=self.clock.time-data['stamp_s'],
            acquisition_time_s=data['stamp_s'], acquisition_sequence=data['frame_number'],
            clock_id='simulation', acquisition_hz=self.config['fps']) for name,data in self._last.items()}
