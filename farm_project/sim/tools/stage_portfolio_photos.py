"""원본 자산을 별도 세션에서 연출 촬영한다. ROS·물리·운영 파일은 수정하지 않는다.

Isaac Python으로 실행. output/request.json에 촬영 구도를 지정하면 PNG와
연출 조건 JSON을 저장한다. 입력은 관절/배치/카메라 데이터만 받는다.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--gui', action='store_true', help='촬영용 GUI viewport 표시')
    parser.add_argument('--all-beds', action='store_true', help='전체8베드 유지')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    from isaacsim import SimulationApp
    app = SimulationApp({'headless': not args.gui, 'renderer': 'RayTracedLighting',
                         'width': 1920 if args.gui else 64, 'height': 1080 if args.gui else 64, 'fast_shutdown': True,
                         'disable_viewport_updates': not args.gui,
                         'extra_args': ['--/app/asyncRendering=false']})
    try:
        import omni.usd
        import omni.timeline
        import carb
        from pxr import Gf, Usd, UsdGeom, UsdPhysics, UsdLux
        from scipy.spatial.transform import Rotation
        from isaacsim.core.utils.stage import open_stage
        from isaacsim.sensors.camera import Camera
        from PIL import Image
        sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
        sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
        fleet = json.loads((args.runtime/'fleet.json').read_text())
        configs = [json.loads((ROOT/p).read_text()) for p in fleet['device_configs']]
        open_stage(str(ROOT/'sim/assets'/configs[0]['scene']))
        stage = omni.usd.get_context().get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        # 먼 베드만 끄고, 줄기 등이 참조하는 공용 Looks 재질은 유지한다.
        for prim in list(stage.GetPrimAtPath('/World/Vegetation').GetChildren()):
            if not args.all_beds and prim.GetName().startswith('Bed_') and prim.GetName() not in ('Bed_01', 'Bed_02'):
                prim.SetActive(False)

        def matrix(path: str) -> np.ndarray:
            return np.asarray(UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T

        def set_local(path: str, transform: np.ndarray) -> None:
            x = UsdGeom.Xformable(stage.GetPrimAtPath(path))
            x.ClearXformOpOrder()
            x.AddTransformOp().Set(Gf.Matrix4d(*map(float, transform.T.flat)))

        def set_world(path: str, transform: np.ndarray) -> None:
            parent = stage.GetPrimAtPath(path).GetParent()
            parent_t = np.eye(4) if parent.IsPseudoRoot() else matrix(str(parent.GetPath()))
            set_local(path, np.linalg.inv(parent_t) @ transform)

        def pose(xyz: list, yaw: float = 0.) -> np.ndarray:
            t = np.eye(4)
            t[:3, :3] = Rotation.from_euler('z', yaw).as_matrix()
            t[:3, 3] = xyz
            return t

        roots = {}
        for cfg in configs:
            binding = cfg['scene_binding']
            path = binding['robot_prim']
            if not stage.GetPrimAtPath(path):
                UsdGeom.Xform.Define(stage, path).GetPrim().GetReferences().AddReference(
                    str(ROOT/'sim/assets'/binding['asset_file']))
            from farm_sim_runtime.scout_mount import install_scout_mount
            install_scout_mount(stage, ROOT, path, cfg)
            roots[cfg['robot_id']] = path
            from farm_sim_runtime.robotarm_asset_setup import expand_box_visual_instances
            expand_box_visual_instances(stage, stage.GetPrimAtPath(path))
            # 촬영 장면에 필요한 로봇만 요청에서 표시한다.
            UsdGeom.Imageable(stage.GetPrimAtPath(path)).MakeInvisible()

        sorter_settings = json.loads((args.runtime/'sorter.json').read_text())
        from farm_sim_runtime.sorter_scene import SorterScene
        sorter = SorterScene(stage, ROOT, dict(sorter_settings, output_dir=str(out/'sorter')), object())
        from hcr_sim.model import teach
        sorting_poses = teach(sorter.cfg)
        (out/'sorting_poses.json').write_text(json.dumps(sorting_poses, indent=2)+'\n')
        from farm_sim_runtime.docking_marker_scene import install_docking_markers
        install_docking_markers(stage, ROOT, fleet.get('docking_markers'))
        alignment = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json').read_text())['teacher_alignment']
        for name in alignment['merged_fixed_bodies']:
            UsdGeom.Imageable(stage.GetPrimAtPath(roots['harvest_01']+'/'+name)).MakeInvisible()
        # 운영 시뮬과 같은 전달 U20/검은색 팔 외형 설치 함수만 재사용한다.
        from types import SimpleNamespace
        release = ROOT/'sim/assets/robotarm_student/manyfarm_robotarm'
        sys.path.insert(0, str(release/'src/harvest_robot'))
        from harvest_rl.kinematics import ArmKinematics
        from harvest_sensors.u20_deployment import reference_urdf
        from farm_sim_devices.student_camera import FarmD435Rig
        camera_cfg = json.loads((release/'src/harvest_robot/config/u20_wrist_deployment_v1.json').read_text())
        wrist_visual = SimpleNamespace(world=SimpleNamespace(stage=stage),
            device=SimpleNamespace(robot_path=roots['harvest_01'],
                _fixed_path=roots['harvest_01']+'/arm_2_gripper_link'),
            kin=ArmKinematics(reference_urdf(camera_cfg)), config=camera_cfg)
        FarmD435Rig.install_visuals(wrist_visual)
        # 촬영 중 visibility를 전환해도 원본 검은 팔 외형의 상속 바인딩을 유지한다.
        from pxr import UsdShade
        black_material = UsdShade.Material(stage.GetPrimAtPath('/World/StudentSensors/ArmAppearance'))
        for prim in list(Usd.PrimRange(stage.GetPrimAtPath(roots['harvest_01']))):
            if '/arm_' in str(prim.GetPath()) and prim.IsInstance():
                prim.SetInstanceable(False)
        for prim in Usd.PrimRange(stage.GetPrimAtPath(roots['harvest_01'])):
            if '/arm_' in str(prim.GetPath()) and prim.IsA(UsdGeom.Mesh):
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(black_material, bindingStrength=UsdShade.Tokens.strongerThanDescendants)
        for prim in stage.Traverse():
            if prim.GetName().startswith('arm_2_wrist_camera') and prim.GetChild('visuals'):
                UsdGeom.Imageable(prim.GetChild('visuals')).MakeInvisible()
        for path in ('/World/HarvestCountPreview', '/World/HCRRobot', '/World/HCRStation'):
            if stage.GetPrimAtPath(path):
                UsdGeom.Imageable(stage.GetPrimAtPath(path)).MakeInvisible()

        # 물리 연결을 끈 별도 촬영 stage. 모든 변화는 세션 layer에만 존재한다.
        joints = []
        for prim in list(stage.Traverse()):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
            if prim.IsA(UsdPhysics.Joint):
                j = UsdPhysics.Joint(prim)
                j.CreateJointEnabledAttr(False)
                for schema in prim.GetAppliedSchemas():
                    if schema.startswith('PhysxMimicJointAPI:'):
                        from pxr import PhysxSchema
                        prim.RemoveAPI(PhysxSchema.PhysxMimicJointAPI, schema.split(':', 1)[1])
                a, b = j.GetBody0Rel().GetTargets(), j.GetBody1Rel().GetTargets()
                if not a or not b:
                    continue
                def local_frame(index: int) -> np.ndarray:
                    pos = getattr(j, f'GetLocalPos{index}Attr')().Get()
                    q = getattr(j, f'GetLocalRot{index}Attr')().Get()
                    t = np.eye(4)
                    t[:3, :3] = Rotation.from_quat([*q.GetImaginary(), q.GetReal()]).as_matrix()
                    t[:3, 3] = pos
                    return t
                axis = prim.GetAttribute('physics:axis').Get() or 'X'
                joints.append(dict(name=prim.GetName(), a=str(a[0]), b=str(b[0]),
                    f0=local_frame(0), f1=local_frame(1), axis='XYZ'.index(axis),
                    kind=prim.GetTypeName(), path=str(prim.GetPath())))
        by_child = {j['b']: j for j in joints}

        def fk(path: str, angles: dict) -> np.ndarray:
            j = by_child.get(path)
            if j is None:
                return matrix(path)
            delta = np.eye(4)
            value = angles.get(j['name'], 0.)
            if j['kind'] == 'PhysicsRevoluteJoint':
                axis = np.eye(3)[j['axis']]
                delta[:3, :3] = Rotation.from_rotvec(axis*value).as_matrix()
            elif j['kind'] == 'PhysicsPrismaticJoint':
                delta[j['axis'], 3] = value
            return fk(j['a'], angles) @ j['f0'] @ delta @ np.linalg.inv(j['f1'])

        angles = {}
        def apply_angles(values: dict) -> None:
            angles.update(values)
            # 전체 변환을 먼저 계산하여 USD 계층 갱신에 따른 이중 변환을 피한다.
            frames = {j['b']: fk(j['b'], angles) for j in joints}
            for path, t in sorted(frames.items(), key=lambda x: x[0].count('/')):
                set_world(path, t)
            wrist_visual.visual_transform.Set(Gf.Matrix4d(*map(float,
                matrix(roots['harvest_01']+'/arm_2_gripper_link').T.flat)))

        apply_angles({})
        info = dict(roots=roots, joints=[{k:v for k,v in j.items() if k not in ('f0','f1')} for j in joints],
            fruit_paths=[str(p.GetPath()) for p in stage.Traverse() if p.GetAttribute('crop:color').Get()],
            prims=[dict(path=str(p.GetPath()), type=p.GetTypeName(), xyz=matrix(str(p.GetPath()))[:3,3].tolist())
                   for p in stage.Traverse() if p.IsA(UsdGeom.Xform) and str(p.GetPath()).count('/') <= 3])
        (out/'inventory.json').write_text(json.dumps(info, indent=2)+'\n')

        settings = carb.settings.get_settings()
        settings.set('/rtx/post/histogram/enabled', False)
        settings.set('/rtx/post/tonemap/filmIso', 100.)
        settings.set('/rtx/post/tonemap/cameraShutter', 100.)
        settings.set('/rtx/post/tonemap/fNumber', 4.)
        settings.set('/rtx/post/aa/op', 2)
        settings.set('/rtx/indirectDiffuse/enabled', False)
        # 카메라용 보조 광원. 원본 농장 조명 파일은 저장하지 않는다.
        fill = UsdLux.RectLight.Define(stage, '/World/PortfolioFill')
        fill.CreateWidthAttr(1.3)
        fill.CreateHeightAttr(1.)
        fill.CreateIntensityAttr(200.)
        fill.CreateColorAttr(Gf.Vec3f(1., .98, .95))
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.BasisCurves) and 'beam_' in str(prim.GetPath()):
                UsdGeom.Imageable(prim).MakeInvisible()
        camera = Camera('/World/PortfolioCloseup', resolution=(1920, 1080), frequency=30)
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        camera.initialize()
        if args.gui:
            from omni.kit.viewport.utility import get_active_viewport
            get_active_viewport().camera_path = '/World/PortfolioCloseup'
        camera.set_clipping_range(.01, 100.)
        camera.set_horizontal_aperture(36.)
        def apply_request(request: dict) -> None:
            for path in request.get('hide', []):
                # 센서 외형만 숨긴다. 공유 팔 재질이 있는 상위 Scope는 유지한다.
                if path == '/World/StudentSensors':
                    path += '/WristVisuals'
                UsdGeom.Imageable(stage.GetPrimAtPath(path)).MakeInvisible()
            for path in request.get('show', []):
                if path == '/World/StudentSensors':
                    path += '/WristVisuals'
                UsdGeom.Imageable(stage.GetPrimAtPath(path)).MakeVisible()
            for path, placement in request.get('placements', {}).items():
                t = np.asarray(placement['matrix']) if 'matrix' in placement else pose(placement['xyz'], placement.get('yaw',0.))
                set_world(path, t)
            apply_angles(request.get('joints', {}))
            for path, value in request.get('fruit_positions', {}).items():
                t = matrix(path)
                t[:3, 3] = value
                set_world(path, t)
            # 기존 링크의 관절 범위 안에서 촬영용 IK만 계산한다.
            if request.get('ik'):
                from scipy.optimize import least_squares
                spec = request['ik']
                names = spec['joints']
                seed = np.array([angles.get(n, 0.) for n in names])
                def residual(q: np.ndarray) -> np.ndarray:
                    t = fk(spec['link'], dict(angles, **dict(zip(names, q))))
                    p = t[:3, 3]+t[:3, :3]@np.asarray(spec['offset'])
                    return np.r_[(p-spec['target'])*5, .002*(q-seed)]
                fit = least_squares(residual, seed, bounds=(spec['lower'],spec['upper']), max_nfev=500)
                apply_angles(dict(zip(names, fit.x)))
                request['ik_result'] = dict(q=fit.x.tolist(), residual=residual(fit.x).tolist())
            for item in request.get('attach_fruits', []):
                t = matrix(item['fruit'])
                link = matrix(item['link'])
                if 'matrix' in item:
                    t = link @ np.asarray(item['matrix'])
                else:
                    t[:3, 3] = link[:3, 3]+link[:3, :3]@np.asarray(item['offset'])
                set_world(item['fruit'], t)
            if 'eye' in request:
                eye, target = np.array(request['eye'], dtype=float), np.array(request['target'], dtype=float)
                f = target-eye; f /= np.linalg.norm(f)
                right = np.cross(f,request.get('up',[0.,0.,1.])); right /= np.linalg.norm(right)
                up = np.cross(right, f)
                q = Rotation.from_matrix(np.column_stack((right,up,-f))).as_quat()[[3,0,1,2]]
                camera.set_world_pose(eye,q,camera_axes='usd')
                camera.set_focal_length(request.get('focal_mm',32.))
                light_t = np.eye(4)
                light_t[:3,:3] = np.column_stack((right,up,-f))
                light_t[:3,3] = eye+np.array([0.,0.,.3])
                set_world('/World/PortfolioFill',light_t)
                fill.GetIntensityAttr().Set(request.get('fill_intensity',200.))

        baseline_fruits = {p:matrix(p).copy() for p in info['fruit_paths']}
        baseline_visibility = {str(p.GetPath()):UsdGeom.Imageable(p).GetVisibilityAttr().Get()
                               for p in stage.Traverse() if p.IsA(UsdGeom.Imageable)}
        baseline_roots = {p:matrix(p).copy() for p in [*roots.values(), '/World/HCRRobot', '/World/HCRStation']}
        def reset_clip() -> None:
            for path, value in baseline_visibility.items():
                if value is not None:
                    UsdGeom.Imageable(stage.GetPrimAtPath(path)).GetVisibilityAttr().Set(value)
            for path, transform in baseline_roots.items():set_world(path, transform)
            apply_angles({j['name']:0. for j in joints})
            for path, transform in baseline_fruits.items():set_world(path, transform)

        last = None
        deadline = time.monotonic()+3600
        (out/'ready.json').write_text(json.dumps({'ready':True, 'scope':'staged poses, no ROS or dynamics'})+'\n')
        print('PORTFOLIO_READY', flush=True)
        while app.is_running() and time.monotonic() < deadline:
            request_path = out/'request.json'
            if not request_path.exists() or request_path.stat().st_mtime_ns == last:
                app.update()
                time.sleep(.02)
                continue
            last = request_path.stat().st_mtime_ns
            request = json.loads(request_path.read_text())
            if request.get('quit'):
                break
            name = request['name']
            if Path(name).name != name:
                raise ValueError('단일 출력 파일명 필요')
            try:
                if 'keyframes' in request:
                    if not args.gui:
                        raise ValueError('발표 영상은 --gui가 필요합니다.')
                    import importlib
                    import presentation_video_frames
                    importlib.reload(presentation_video_frames)
                    reset_clip()
                    presentation_video_frames.capture(request, out, app, camera, apply_request,
                            lambda r: {p:matrix(p).tolist() for p in r.get('inspect',[])})
                    continue
                apply_request(request)
                for _ in range(request.get('warmup_frames',48)):
                    app.update()
                rgb = np.asarray(camera.get_rgb())
                if rgb.shape != (1080,1920,3):
                    raise RuntimeError('RGB frame unavailable: '+str(rgb.shape))
                Image.fromarray(rgb.astype(np.uint8)).save(out/(name+'.png'))
                request.update(scope='staged illustration using project USD assets; not an autonomous test result',
                    resolution=[1920,1080], gui=args.gui, all_beds=args.all_beds, joint_positions=angles,
                    inspected={p:matrix(p).tolist() for p in request.get('inspect',[])})
                (out/(name+'.json')).write_text(json.dumps(request,indent=2)+'\n')
                print('SAVED '+name, flush=True)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                (out/(name+'-error.json')).write_text(json.dumps({'error':repr(exc)})+'\n')
        timeline.stop()
    finally:
        app.close()


if __name__ == '__main__':
    main()
