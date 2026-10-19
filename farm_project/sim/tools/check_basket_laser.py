"""저장된 USD 광축과 실제 7cm 과실 중력 낙하를 PhysX로 검사한다(운영 로봇 미구동)."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))


def main() -> None:
    from isaacsim import SimulationApp
    app = SimulationApp({'headless': True})
    try:
        from isaacsim.core.api import World
        from isaacsim.core.api.objects import DynamicCuboid
        from pxr import Gf, Usd, UsdGeom
        from farm_sim_devices.basket_laser import BasketLaserSensor
        from build_basket_laser_assets import URDF, BASES, link_pose
        from scipy.spatial.transform import Rotation
        world = World(physics_dt=1/60, rendering_dt=1/60, stage_units_in_meters=1.)
        world.scene.add_default_ground_plane()
        settings = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/student_policy.json').read_text())['basket_lasers']
        policy = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())
        root = ET.parse(URDF).getroot()
        asset = Usd.Stage.Open(str(BASES[1]))
        reference = str(asset.GetDefaultPrim().GetPath())+'/base_link/BasketLasers'
        cases = [('empty', 0., 0., 0), ('anonymous_cube', 0., 0., 0)]
        cases += [(f'pepper_x_{x}', x, 0., 0) for x in (-.055,-.0475,-.02375,0.,.02375,.0475,.055)]
        cases += [(f'corner_{x}_{y}', x, y, 0) for x in (-.055,.055) for y in (-.055,.055)]
        cases += [('pepper_sideways', .02375, 0., 90)]
        devices = []
        for index, (name, x, y, angle) in enumerate(cases):
            robot = f'/World/Probe_{index}'
            offset = np.eye(4); offset[0,3] = index*.5
            base = UsdGeom.Xform.Define(world.stage, robot+'/base_link')
            base.AddTransformOp().Set(Gf.Matrix4d(offset.T.tolist()))
            world.stage.DefinePrim(robot+'/base_link/BasketLasers').GetReferences().AddReference(str(BASES[1]), reference)
            mount_pose = offset @ link_pose(root, 'arm_2/base_link')
            mount_path = robot+'/mount'
            UsdGeom.Xform.Define(world.stage, mount_path).AddTransformOp().Set(Gf.Matrix4d(mount_pose.T.tolist()))
            config = dict(box_min=policy['runtime']['box_min'], box_max=policy['runtime']['box_max'],
                          policy_arm_position_m=policy['device']['policy_arm_position_m'])
            devices.append(SimpleNamespace(robot_path=robot, _mount_path=mount_path, config=config,
                arm_world_transform=lambda pose=mount_pose: pose))
            position = (offset @ link_pose(root, 'harvest_box') @ [x,y,.55,1])[:3]
            if name == 'anonymous_cube':
                world.scene.add(DynamicCuboid(prim_path=robot+'/object', name=name, position=position, size=.07, mass=.009))
            elif name != 'empty':
                fruit = world.stage.DefinePrim(robot+'/object')
                fruit.GetReferences().AddReference(str(ROOT/'sim/assets/fruit/teacher_9g/pepper_red.usd'))
                xf = UsdGeom.Xformable(fruit)
                xf.AddTranslateOp().Set(Gf.Vec3d(*position))
                quat = Rotation.from_euler('y', angle, degrees=True).as_quat()
                xf.AddOrientOp().Set(Gf.Quatf(float(quat[3]), Gf.Vec3f(*quat[:3])))
        world.reset()
        sensors = [BasketLaserSensor(world, d, settings) for d in devices]
        reports = [dict(name=c[0], events=[], samples=[]) for c in cases]
        for sensor in sensors: sensor.counter.arm()
        for _ in range(90):
            world.step(render=False)
            for sensor, report in zip(sensors, reports):
                event = sensor.sample(float(world.current_time))
                report['samples'].append(dict(sensor.last))
                if event is not None: report['events'].append(event)
        for report in reports:
            report['passed'] = len(report['events']) == (0 if report['name']=='empty' else 1)
        report = dict(passed=all(r['passed'] for r in reports), scope='PhysX gravity/raycast; persisted USD; real fruit collider and anonymous cube', cases=reports)
        output = ROOT/'sim/runs/basket_parallel_lasers_20261019/native_sensor.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2)+'\n')
        print('BASKET_LASER_NATIVE', json.dumps({r['name']:r['passed'] for r in reports}), flush=True)
        if not report['passed']: raise RuntimeError('실제 낙하 레이저 계수 검증 실패')
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush()
        raise
    finally:
        app.close()


if __name__ == '__main__': main()
