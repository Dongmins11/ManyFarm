"""Finite-length flexible hanger, with compliance ONLY beyond its length.

GPU-compatible D6 distance soft limit; no position/angle restoring drives.
Optional zero-stiffness velocity drives dissipate bending/rotation energy.
The PhysX constraint breaks at actual solver force, not a guessed displacement.
"""
from dataclasses import asdict, dataclass
import math
import torch


@dataclass(frozen=True)
class HookSpec:
    length_m: float = .06
    final_extension_m: float = .01
    break_force_N: float = 2.5
    damping_N_s_m: float = 4.2
    bending_drag_N_s_m: float = .1
    rotation_damping_Nm_s_rad: float = .008
    pivot_offset_direction: tuple = (0., 0., 1.)
    solver: str = 'tgs-distributed'

    @property
    def stiffness_N_m(self):
        return self.break_force_N / self.final_extension_m

    def validate(self):
        if not all(math.isfinite(v) and v > 0 for v in
                   (self.length_m, self.final_extension_m, self.break_force_N)):
            raise ValueError('Finite positive length, extension and force required')
        if (self.length_m != .06 or self.final_extension_m not in (.005, .01, .02)
                or self.break_force_N != 2.5 or not 0 <= self.damping_N_s_m <= 5.):
            raise ValueError('Provisional60mm hanger,5/10/20mm final compliance,2.5N fracture')
        if self.bending_drag_N_s_m not in (0.,.05,.1) or not 0<=self.rotation_damping_Nm_s_rad<=.01:
            raise ValueError('Bounded dissipative drag only; no position/angle restoration')
        direction = torch.as_tensor(self.pivot_offset_direction)
        if direction.shape != (3,) or not torch.isfinite(direction).all() or direction.norm() < 1e-8:
            raise ValueError('Finite pivot offset direction required')
        if self.solver != 'tgs-distributed':
            raise ValueError('Keep the previously checked explicit60Hz solver candidate')
        return self


def hook_geometry(tip_world, original_tip_world, spec):
    """No spring error within the allowed ball. No angular rest orientation."""
    spec.validate()
    direction = tip_world.new_tensor(spec.pivot_offset_direction)
    direction = direction / direction.norm()
    pivot = original_tip_world + spec.length_m * direction
    vector = tip_world - pivot
    distance = vector.norm(dim=-1)
    extension = (distance - spec.length_m).clamp_min(0.)
    radial = vector / distance.clamp_min(1e-9)[..., None]
    return dict(pivot_world=pivot, distance_m=distance, extension_m=extension,
                radial=radial, elastic_force_estimate_N=spec.stiffness_N_m * extension)


class HookConnectors:
    """Own ONLY world-to-fruit distance constraints and their break events.

    Original harvest bookkeeping consumes events through hook_connector_runtime.
    Reset authors poses/frames only at explicit scene reset. Never while moving.
    """
    def __init__(self, env, specs):
        from omni.physx import get_physx_interface
        self.env = env
        self.stage = env.sim.stage
        self.specs = ([specs] * env.num_envs if isinstance(specs, HookSpec) else list(specs))
        if len(self.specs) != env.num_envs:
            raise ValueError('One spec per environment required')
        for spec in self.specs:spec.validate()
        self.joints = {}
        self.paths = {}
        self.pending = []
        self.stream = get_physx_interface().get_simulation_event_stream_v2()
        self.subscription = self.stream.create_subscription_to_pop(self._event)

    def _event(self, event):
        from omni.physx.bindings._physx import SimulationEvent
        from pxr import PhysicsSchemaTools
        if event.type == int(SimulationEvent.JOINT_BREAK):
            path = str(PhysicsSchemaTools.decodeSdfPath(*event.payload['jointPath']))
            if path in self.paths:self.pending.append(self.paths[path])

    def consume(self):
        self.stream.pump()
        events, self.pending = self.pending, []
        for index in events:self.joints[index].CreateJointEnabledAttr().Set(False)
        return events

    def reset(self, ids):
        from pxr import UsdPhysics, UsdGeom, PhysxSchema, Gf
        ids = ids.cpu().tolist()
        self.stream.pump()
        self.pending = [pair for pair in self.pending if pair[0] not in ids]
        cache = UsdGeom.XformCache()
        env = self.env
        for i in ids:
            spec = self.specs[i]
            direction = torch.tensor(spec.pivot_offset_direction)
            direction = (direction / direction.norm()).tolist()
            for slot, fruit in enumerate(env.fruits):
                path = f'/World/envs/env_{i}/HookConnector_{slot}'
                body = fruit.root_physx_view.prim_paths[i]
                pose = fruit.data.root_state_w[i].cpu().tolist()
                prim = self.stage.GetPrimAtPath(body)
                parent_inverse = cache.GetLocalToWorldTransform(prim.GetParent()).GetInverse()
                world = Gf.Matrix4d(1).SetRotate(Gf.Quatd(pose[3], Gf.Vec3d(*pose[4:7])))
                world.SetTranslateOnly(Gf.Vec3d(*pose[:3]))
                # Fabric pose synchronization ONLY at reset, as in the old fixture.
                UsdGeom.Xformable(prim).MakeMatrixXform().Set(world * parent_inverse)
                self.paths.pop(path, None)
                if self.stage.GetPrimAtPath(path):self.stage.RemovePrim(path)
                joint = UsdPhysics.Joint.Define(self.stage, path)
                joint.CreateBody1Rel().SetTargets([body])
                anchor = env.anchors[i, slot].cpu().tolist()
                pivot = [anchor[j] + spec.length_m * direction[j] for j in range(3)]
                joint.CreateLocalPos0Attr().Set(Gf.Vec3f(*pivot))
                joint.CreateLocalPos1Attr().Set(Gf.Vec3f(*env.fruit_tips[slot].cpu().tolist()))
                joint.CreateExcludeFromArticulationAttr().Set(True)
                joint.CreateBreakForceAttr().Set(spec.break_force_N)
                joint.CreateBreakTorqueAttr().Set(float('inf'))
                joint.CreateJointEnabledAttr().Set(bool(env.attached[i, slot]))
                limit = UsdPhysics.LimitAPI.Apply(joint.GetPrim(), UsdPhysics.Tokens.distance)
                limit.CreateHighAttr().Set(spec.length_m)
                soft = PhysxSchema.PhysxLimitAPI.Apply(joint.GetPrim(), UsdPhysics.Tokens.distance)
                soft.CreateStiffnessAttr().Set(spec.stiffness_N_m)
                soft.CreateDampingAttr().Set(spec.damping_N_s_m)
                soft.CreateRestitutionAttr().Set(0.)
                # Material dissipation, not a spring to the initial position.
                # All targets are zero VELOCITY; position/angle stiffness is0.
                for axis in ('transX','transY','transZ'):
                    if spec.bending_drag_N_s_m:
                        drag=UsdPhysics.DriveAPI.Apply(joint.GetPrim(),axis)
                        drag.CreateTypeAttr().Set('force');drag.CreateStiffnessAttr().Set(0.)
                        drag.CreateDampingAttr().Set(spec.bending_drag_N_s_m)
                        drag.CreateMaxForceAttr().Set(.2);drag.CreateTargetVelocityAttr().Set(0.)
                for axis in ('rotX','rotY','rotZ'):
                    if spec.rotation_damping_Nm_s_rad:
                        drag=UsdPhysics.DriveAPI.Apply(joint.GetPrim(),axis)
                        drag.CreateTypeAttr().Set('force');drag.CreateStiffnessAttr().Set(0.)
                        drag.CreateDampingAttr().Set(spec.rotation_damping_Nm_s_rad*math.pi/180)
                        drag.CreateMaxForceAttr().Set(.02);drag.CreateTargetVelocityAttr().Set(0.)
                self.joints[i, slot] = joint
                if bool(env.attached[i, slot]):self.paths[path] = (i, slot)

    def pending_mask(self):
        mask = torch.zeros_like(self.env.attached)
        for i, slot in self.consume():mask[i, slot] = True
        return mask

    def audit(self):
        from pxr import UsdPhysics, PhysxSchema
        rows = []
        for (i, slot), joint in self.joints.items():
            prim = joint.GetPrim()
            spec = self.specs[i]
            if joint.GetBody0Rel().GetTargets():raise ValueError('Hanger must not connect to gripper')
            if [str(p) for p in joint.GetBody1Rel().GetTargets()] != [str(self.env.fruits[slot].root_physx_view.prim_paths[i])]:
                raise ValueError('Wrong hanger body')
            limit = UsdPhysics.LimitAPI(prim, UsdPhysics.Tokens.distance)
            soft = PhysxSchema.PhysxLimitAPI(prim, UsdPhysics.Tokens.distance)
            if (abs(limit.GetHighAttr().Get() - spec.length_m) > 1e-7
                    or abs(soft.GetStiffnessAttr().Get() - spec.stiffness_N_m) > 1e-5
                    or abs(joint.GetBreakForceAttr().Get() - spec.break_force_N) > 1e-7
                    or abs(soft.GetDampingAttr().Get() - spec.damping_N_s_m) > 1e-6
                    or soft.GetRestitutionAttr().Get() != 0
                    or not joint.GetExcludeFromArticulationAttr().Get()):
                raise ValueError('Actual hanger properties differ')
            for axis in ('transX','transY','transZ','rotX','rotY','rotZ'):
                if UsdPhysics.LimitAPI(prim, axis):raise ValueError('Unexpected individual-axis limit')
                drag=UsdPhysics.DriveAPI(prim,axis)
                linear=axis.startswith('trans')
                damping=(spec.bending_drag_N_s_m if linear
                         else spec.rotation_damping_Nm_s_rad*math.pi/180)
                if bool(drag) != bool(damping):raise ValueError('Dissipative drive presence differs')
                if drag and (drag.GetStiffnessAttr().Get()!=0 or drag.GetTargetVelocityAttr().Get()!=0
                        or abs(drag.GetDampingAttr().Get()-damping)>1e-7
                        or abs(drag.GetMaxForceAttr().Get()-(.2 if linear else .02))>1e-7
                        or drag.GetTypeAttr().Get()!='force'):
                    raise ValueError('Dissipative drive properties differ')
            if bool(joint.GetJointEnabledAttr().Get()) != bool(self.env.attached[i, slot]):
                raise ValueError('Physical break and environment attachment differ')
            rows.append(dict(env_id=i, slot=slot, path=str(joint.GetPath()), spec=asdict(spec)))
        return dict(model='finite_length_hook_v2', rows=rows, distance_limit_only=True,
                    added_rigid_bodies=0, angular_restoring_drive=False, break_force_is_actual_constraint=True,
                    source_assets_modified=False, new_physics_substeps=0,
                    velocity_damping_has_zero_restoring_stiffness=True)

    def close(self):
        self.subscription = None

