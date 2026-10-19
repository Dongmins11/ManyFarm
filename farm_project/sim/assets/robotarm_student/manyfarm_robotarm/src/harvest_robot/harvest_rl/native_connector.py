"""Compliant world-to-fruit D6 candidate, solved together with contacts in PhysX.

All six axes are free; drives are damped springs, not a grasp weld. No in-step
pose/velocity rewrite or external support is used. Frames are authored on reset.
"""
from dataclasses import asdict,dataclass
import math
import torch


@dataclass(frozen=True)
class ConnectorSpec:
    axial_release_m: float=.07
    axial_stiffness_N_m: float=35.714285714285715
    lateral_stiffness_N_m: float=15.
    vertical_stiffness_N_m: float=40.
    damping_N_s_m: float=4.2
    angular_stiffness_Nm_rad: float=.015
    angular_damping_Nm_s_rad: float=.008
    force_limit_N: float=2.5
    torque_limit_Nm: float=.02
    opening_hold_s: float=.04
    solver: str='tgs-distributed'

    def validate(self):
        if not all(math.isfinite(v) and v>0 for k,v in asdict(self).items() if k!='solver'):raise ValueError('Finite positive connector parameters')
        if self.solver not in ('tgs-original','tgs-zero','tgs-distributed','pgs'):raise ValueError('Unsupported explicit solver candidate')
        if not .025<=self.axial_release_m<=.08 or self.force_limit_N!=2.5 or self.opening_hold_s!=.04:
            raise ValueError('Only provisional25..80mm opening,2.5N limit and40ms dwell')
        if self.axial_stiffness_N_m>100 or self.damping_N_s_m>5:raise ValueError('Out of bounded spring candidates')
        return self


def directional_open(displacement,attached,timer,dt,spec):
    spec.validate()
    if abs(dt-1/60)>1e-9:raise ValueError('Native connector is an explicit60Hz candidate')
    # World -X is the same outward axis as the frozen Teacher scene.
    axial=-displacement[:,0]
    opening=axial>=spec.axial_release_m
    updated=torch.where(attached & opening,timer+dt,torch.zeros_like(timer))
    remaining=attached & (updated<spec.opening_hold_s)
    return remaining,updated,axial,opening


class NativeConnectors:
    def __init__(self,env,spec):
        self.env=env;self.stage=env.sim.stage;self.spec=spec.validate();self.joints={}

    def reset(self,ids):
        from pxr import UsdPhysics,UsdGeom,Gf
        cache=UsdGeom.XformCache();env=self.env;s=self.spec
        for i in ids.cpu().tolist():
            for slot,fruit in enumerate(env.fruits):
                path=f'/World/envs/env_{i}/NativeConnector_{slot}'
                body=fruit.root_physx_view.prim_paths[i]
                pose=fruit.data.root_state_w[i].cpu().tolist()
                # Reset only: synchronize authored body frame with Fabric state
                # before PhysX parses a new non-articulation constraint.
                prim=self.stage.GetPrimAtPath(body)
                parent_inverse=cache.GetLocalToWorldTransform(prim.GetParent()).GetInverse()
                world=Gf.Matrix4d(1).SetRotate(Gf.Quatd(pose[3],Gf.Vec3d(*pose[4:7])))
                world.SetTranslateOnly(Gf.Vec3d(*pose[:3]))
                UsdGeom.Xformable(prim).MakeMatrixXform().Set(world*parent_inverse)
                if self.stage.GetPrimAtPath(path):self.stage.RemovePrim(path)
                joint=UsdPhysics.Joint.Define(self.stage,path)
                joint.CreateBody1Rel().SetTargets([body])
                joint.CreateLocalPos0Attr().Set(Gf.Vec3f(*env.anchors[i,slot].cpu().tolist()))
                joint.CreateLocalPos1Attr().Set(Gf.Vec3f(*env.fruit_tips[slot].cpu().tolist()))
                q=env.rest_quat[i,slot].cpu().tolist()
                joint.CreateLocalRot0Attr().Set(Gf.Quatf(1.))
                joint.CreateLocalRot1Attr().Set(Gf.Quatf(q[0],Gf.Vec3f(-q[1],-q[2],-q[3])))
                joint.CreateExcludeFromArticulationAttr().Set(True)
                joint.CreateBreakForceAttr().Set(float('inf'));joint.CreateBreakTorqueAttr().Set(float('inf'))
                joint.CreateJointEnabledAttr().Set(bool(env.attached[i,slot]))
                stiffness=[s.axial_stiffness_N_m,s.lateral_stiffness_N_m,s.vertical_stiffness_N_m]
                for axis,k in zip(['transX','transY','transZ'],stiffness):
                    drive=UsdPhysics.DriveAPI.Apply(joint.GetPrim(),axis)
                    drive.CreateTypeAttr().Set('force');drive.CreateStiffnessAttr().Set(k)
                    drive.CreateDampingAttr().Set(s.damping_N_s_m);drive.CreateMaxForceAttr().Set(s.force_limit_N)
                    drive.CreateTargetPositionAttr().Set(0.);drive.CreateTargetVelocityAttr().Set(0.)
                for axis in ['rotX','rotY','rotZ']:
                    drive=UsdPhysics.DriveAPI.Apply(joint.GetPrim(),axis)
                    drive.CreateTypeAttr().Set('force')
                    drive.CreateStiffnessAttr().Set(s.angular_stiffness_Nm_rad*math.pi/180)
                    drive.CreateDampingAttr().Set(s.angular_damping_Nm_s_rad*math.pi/180)
                    drive.CreateMaxForceAttr().Set(s.torque_limit_Nm)
                    drive.CreateTargetPositionAttr().Set(0.);drive.CreateTargetVelocityAttr().Set(0.)
                self.joints[i,slot]=joint

    def disable_detached(self,before):
        broke=(before & ~self.env.attached).nonzero().cpu().tolist()
        for i,slot in broke:self.joints[i,slot].GetJointEnabledAttr().Set(False)

    def audit(self):
        from pxr import UsdPhysics
        rows=[]
        for (i,slot),joint in self.joints.items():
            if joint.GetBody0Rel().GetTargets():raise ValueError('Connector must attach to plant/world, never the gripper')
            if [str(x) for x in joint.GetBody1Rel().GetTargets()]!=[str(self.env.fruits[slot].root_physx_view.prim_paths[i])]:raise ValueError('Wrong connector body')
            enabled=bool(joint.GetJointEnabledAttr().Get())
            if enabled!=bool(self.env.attached[i,slot]):raise ValueError('Physical connector enabled state differs')
            if any(UsdPhysics.LimitAPI(joint.GetPrim(),axis) for axis in ['transX','transY','transZ','rotX','rotY','rotZ']):raise ValueError('Unexpected rigid DOF limit')
            rows.append(dict(env_id=i,slot=slot,path=str(joint.GetPath()),enabled=enabled))
        return dict(spec=asdict(self.spec),joints=rows,all_axes_free=True,
            source_usd_modified=False,drive_type='force',extra_physics_substeps=0,
            fracture='Sustained outward -X displacement only; no side/inward total-distance break',
            force_readout='Drive spring estimate is not a measured solver reaction; isolated fixtures use momentum balance with known external load')
