"""Native PhysX breakable spherical joints; legacy spring code is independent.

USD lifecycle operations are CPU-side, so benchmark before large vector runs.
Break events certify the native constraint threshold; they do not report a force sample.
"""
from pxr import UsdPhysics, UsdGeom, Gf, PhysicsSchemaTools
from omni.physx import get_physx_interface
from omni.physx.bindings._physx import SimulationEvent


class JointAttachments:
    def __init__(self, stage):
        self.stage = stage
        self.paths = {}
        self.pending = []
        self.stream = get_physx_interface().get_simulation_event_stream_v2()
        self.subscription = self.stream.create_subscription_to_pop(self._event)

    def _event(self, event):
        if event.type == int(SimulationEvent.JOINT_BREAK):
            path = str(PhysicsSchemaTools.decodeSdfPath(*event.payload["jointPath"]))
            if path in self.paths:
                self.pending.append(self.paths[path])

    def reset(self, env_ids, anchors, tips, thresholds, root_states=None, attached=None):
        self.stream.pump()
        ids = set(env_ids)
        self.pending = [pair for pair in self.pending if pair[0] not in ids]
        # Tensor reset does not update USD when Fabric owns body transforms.
        # Author matching reset poses before PhysX parses the new constraints.
        cache = UsdGeom.XformCache()
        for row, env_id in enumerate(env_ids):
            parent = self.stage.GetPrimAtPath(f"/World/envs/env_{env_id}")
            parent_inverse = cache.GetLocalToWorldTransform(parent).GetInverse()
            for fruit_id in range(len(anchors[row])):
                path = f"/World/envs/env_{env_id}/StemJoint_{fruit_id}"
                if self.stage.GetPrimAtPath(path):
                    self.stage.RemovePrim(path)
                fruit_path = f"/World/envs/env_{env_id}/Fruit_{fruit_id}"
                # Reset contract: fruit orientation is identity, root scale is one.
                world_position = Gf.Vec3d(*anchors[row][fruit_id]) - Gf.Vec3d(*tips[fruit_id])
                world = Gf.Matrix4d(1).SetTranslate(world_position)
                if root_states is not None:
                    pose=root_states[row][fruit_id]
                    world=Gf.Matrix4d(1).SetRotate(Gf.Quatd(pose[3],Gf.Vec3d(*pose[4:7])))
                    world.SetTranslateOnly(Gf.Vec3d(*pose[:3]))
                fruit = UsdGeom.Xformable(self.stage.GetPrimAtPath(fruit_path))
                fruit.MakeMatrixXform().Set(world * parent_inverse)
                joint = UsdPhysics.SphericalJoint.Define(self.stage, path)
                enabled = attached is None or attached[row][fruit_id]
                # Explicitly override inherited env_0 joints in cloned environments.
                joint.CreateJointEnabledAttr().Set(bool(enabled))
                joint.CreateBody1Rel().SetTargets([fruit_path])
                anchor = Gf.Vec3f(*anchors[row][fruit_id]) if enabled else Gf.Vec3f(world.Transform(Gf.Vec3d(*tips[fruit_id])))
                joint.CreateLocalPos0Attr().Set(anchor)
                joint.CreateLocalPos1Attr().Set(Gf.Vec3f(*tips[fruit_id]))
                joint.CreateAxisAttr().Set("Z")
                joint.CreateBreakForceAttr().Set(float(thresholds[row][fruit_id]))
                joint.CreateBreakTorqueAttr().Set(float("inf"))
                joint.CreateExcludeFromArticulationAttr().Set(True)
                if enabled:
                    self.paths[path] = (env_id, fruit_id)
                else:
                    self.paths.pop(path, None)

    def consume(self):
        self.stream.pump()
        events, self.pending = self.pending, []
        return events

    def close(self):
        self.subscription = None
