"""Isaac Python: 임시 마커를 실제 모델에 붙여 정차 RGB를 저장한다.

주행/도킹 성공 시험이 아니다. 광학 배치만 확인하도록 물리는 정지한다.
"""
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'sim/runs/docking_markers_20261027'
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))


def main() -> None:
    from isaacsim import SimulationApp
    app = SimulationApp({'headless': True, 'renderer': 'RayTracedLighting', 'fast_shutdown': False})
    try:
        import omni.usd
        import omni.timeline
        from pxr import Gf, Usd, UsdGeom, UsdPhysics, PhysxSchema
        from isaacsim.core.utils.stage import open_stage
        from isaacsim.sensors.camera import Camera
        from farm_sim_runtime.docking_marker_scene import install_docking_markers
        from PIL import Image
        selected = 'sim/assets/docking_markers/layout.provisional.json'
        layout = json.loads((ROOT/selected).read_text())
        cfg = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json').read_text())
        open_stage(str(ROOT/'sim/assets'/cfg['scene']))
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        harvest = UsdGeom.Xform.Define(stage, '/World/harvest_robot')
        harvest.GetPrim().GetReferences().AddReference(str(ROOT/'sim/assets/robots/harvest_count_test/harvest_robot.usd'))
        records = install_docking_markers(stage, ROOT, selected)
        for prim in stage.Traverse():
            if prim.IsA(UsdPhysics.Scene):
                physics = PhysxSchema.PhysxSceneAPI.Apply(prim)
                physics.CreateEnableGPUDynamicsAttr(False)
                physics.CreateBroadphaseTypeAttr('MBP')
        # 움직임이 영상 확인을 오염시키지 않도록 이 시험에서만 강체를 고정한다.
        for prim in stage.Traverse():
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
            if prim.IsA(UsdPhysics.Joint):
                UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
                for schema in prim.GetAppliedSchemas():
                    if schema.startswith('PhysxMimicJointAPI:'):
                        prim.RemoveAPI(PhysxSchema.PhysxMimicJointAPI, schema.split(':', 1)[1])
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        camera = Camera('/World/DockingMarkerCheckCamera', resolution=(1280,720), frequency=10)
        camera.initialize()
        # 운영 mount_camera와 동일한 근거리 clipping. 기본 1m는 마커를 잘라낸다.
        camera.set_clipping_range(.01, 100.)
        k = cfg['camera']['camera_info']['k']
        camera.set_opencv_pinhole_properties(cx=k[2], cy=k[5], fx=k[0], fy=k[4], pinhole=[0.]*5)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        observations = []
        for item, record in zip(layout['markers'], records):
            cache = UsdGeom.XformCache()
            marker_world = np.asarray(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(record['path']))).T
            normal = marker_world[:3,2]
            yaw = math.atan2(-normal[1], -normal[0])
            base = np.eye(4)
            base[:3,:3] = [[math.cos(yaw),-math.sin(yaw),0], [math.sin(yaw),math.cos(yaw),0], [0,0,1]]
            # 42/40의 저장 관측 거리, 41은 임시 정면 관측 위치. 제어 목표로 쓰지 않는다.
            distance = {42:.5372845021811206,41:.54,40:.3511251946730866}[item['id']]
            lateral = {42:.05043821807923123,41:0.,40:.03180462896244958}[item['id']]
            base[:3,3] = marker_world[:3,3] - base[:3,:3] @ [distance,lateral,item['center_m'][2]]
            optical = base @ np.asarray(cfg['camera']['T_base_optical'])
            usd = optical @ np.diag([1.,-1.,-1.,1.])
            xform = UsdGeom.Xformable(stage.GetPrimAtPath('/World/DockingMarkerCheckCamera'))
            xform.ClearXformOpOrder()
            xform.AddTransformOp().Set(Gf.Matrix4d(*map(float,usd.T.flat)))
            for _ in range(80):
                app.update()
            rgb = np.asarray(camera.get_rgba())
            if rgb.shape[:2] != (720,1280):
                raise RuntimeError(f'마커 {item["id"]} RGB 없음: {rgb.shape}')
            image = OUTPUT/f"marker_{item['id']}.png"
            Image.fromarray(rgb[:,:,:3].astype(np.uint8)).save(image)
            observations.append(dict(id=item['id'], image=str(image.relative_to(ROOT)),
                                     T_world_camera_optical=optical.tolist(), T_world_base=base.tolist()))
        (OUTPUT/'render.json').write_text(json.dumps(dict(scope='static RGB only; no motion/action',
            mounting_status=layout['status'], observations=observations), indent=2)+'\n')
        camera.pause()
        timeline.stop()
        print('DOCKING_MARKER_RENDER_COMPLETE', flush=True)
    except Exception:
        import traceback
        traceback.print_exc()
        raise
    finally:
        app.close()


if __name__ == '__main__':
    main()
