"""지정 SEC 평행 경로의 두 로봇 교행 물리 검사. ROS/기존 실행에 연결하지 않는다."""
import argparse
import copy
import json
import math
from pathlib import Path
import sys

import numpy as np
import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--harvest-section', default='SEC01')
    parser.add_argument('--scout-section', default='SEC01')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    for package in ('farm_sim_runtime', 'farm_sim_devices'):
        sys.path.insert(0, str(root/'sim/ros_ws/src'/package))
    sys.path.insert(0, str(root/'robot/ros_ws/src/farm_common'))
    config_dir = root/'sim/ros_ws/src/farm_sim_config/config'
    configs = {name: json.loads((config_dir/file).read_text()) for name, file in
               [('scout', 'scout_fleet.json'), ('harvest', 'harvest.json')]}
    sections = yaml.safe_load((config_dir/'task.yaml').read_text())['sections']
    section = sections[args.harvest_section]
    survey = sections[args.scout_section]['survey_geometry']
    lane_x = dict(scout=survey['start_xy_m'][0],
                  harvest=section['harvest_route']['x_m'])
    ranges = [sorted(s[key][1] for key in ('start_xy_m', 'end_xy_m'))
              for s in (survey, section['survey_geometry'])]
    lower, upper = max(r[0] for r in ranges), min(r[1] for r in ranges)
    if upper-lower < 3.6:
        raise ValueError('교행 검사에 필요한 평행 구간 3.6m가 없습니다.')
    center_y = (lower+upper)/2
    harvest_direction = math.copysign(1., math.sin(section['harvest_route']['heading_rad']))
    start_y = dict(scout=center_y+harvest_direction, harvest=center_y-harvest_direction)
    left, right = sorted(lane_x, key=lane_x.get)
    profile = json.loads((root/configs['harvest']['runtime']['robotarm_physics_config']).read_text())
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    app = SimulationApp(dict(headless=True, disable_viewport_updates=True,
                             renderer='RayTracedLighting', fast_shutdown=True))
    try:
        import omni.usd
        from pxr import Gf, Usd, UsdGeom, UsdPhysics, PhysxSchema, PhysicsSchemaTools
        from omni.physx import get_physx_simulation_interface
        from isaacsim.core.api import World
        from isaacsim.core.utils.stage import create_new_stage
        from farm_sim_runtime.robotarm_asset_setup import configure_harvest_arm
        from farm_sim_runtime.harvest_physics import initialize_arm_travel
        from farm_sim_runtime.teacher_arm_alignment import align_teacher_scene
        from farm_sim_runtime.scout_mount import install_scout_mount
        from farm_sim_devices.base_sim import BaseSim
        from farm_sim_devices.control_frame import asset_from_control, station_root_transform

        create_new_stage()
        stage = omni.usd.get_context().get_stage()
        UsdGeom.SetStageUpAxis(stage, 'Z')
        UsdGeom.SetStageMetersPerUnit(stage, 1.)
        stage.SetEditTarget(stage.GetSessionLayer())
        robots = {}
        arm_cfg = copy.deepcopy(profile)
        for key in ('box_floor', 'teacher_alignment'):
            if 'asset_path' in arm_cfg[key]:
                arm_cfg[key]['asset_path'] = str(root/arm_cfg[key]['asset_path'])
        for name, cfg in configs.items():
            binding = cfg['scene_binding']
            path = '/World/'+name
            prim = UsdGeom.Xform.Define(stage, path).GetPrim()
            if name == 'scout':
                # 농장에 저장된 실제 예찰 로봇 subtree를 그대로 참조한다.
                prim.GetReferences().AddReference(str(root/'sim/assets'/cfg['scene']), binding['robot_prim'])
                install_scout_mount(stage, root, path, cfg)
            else:
                prim.GetReferences().AddReference(str(root/'sim/assets'/binding['asset_file']))
                arm_report = configure_harvest_arm(stage, path, arm_cfg)
            body = stage.GetPrimAtPath(path+'/'+binding['articulation_relative'])
            cache = UsdGeom.XformCache()
            matrix = lambda p: np.asarray(cache.GetLocalToWorldTransform(p), float).T
            control = asset_from_control(binding)
            desired = np.eye(4)
            yaw = section['harvest_route']['heading_rad']
            desired[:3, :3] = [[math.cos(yaw), -math.sin(yaw), 0],
                               [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]]
            desired[:3, 3] = [lane_x[name], start_y[name], matrix(body)[2, 3]]
            transform = station_root_transform(desired, matrix(body), matrix(prim), control)
            xf = UsdGeom.Xformable(prim)
            xf.ClearXformOpOrder()
            xf.AddTransformOp().Set(Gf.Matrix4d(*transform.T.flatten()))
            colliders = [p for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies())
                         if p.HasAPI(UsdPhysics.CollisionAPI)
                         and UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get()]
            for p in Usd.PrimRange(prim):
                if p.HasAPI(UsdPhysics.RigidBodyAPI):
                    PhysxSchema.PhysxContactReportAPI.Apply(p).CreateThresholdAttr(0.)
            robots[name] = dict(prim=prim, body=body, control=control,
                                colliders=[str(p.GetPath()) for p in colliders])
        world = World(physics_dt=1/60, rendering_dt=1/30, stage_units_in_meters=1., backend='numpy')
        world.scene.add_default_ground_plane()
        align_teacher_scene(world)
        world.get_physics_context().enable_gpu_dynamics(False)
        world.get_physics_context().set_broadphase_type('MBP')
        for name, robot in robots.items():
            robot['base'] = BaseSim(world, str(robot['body'].GetPath()), configs[name]['base'], name=name)
        state = dict(case='', tick=-1, ground=0, mutual=[])

        def contacts(headers: object, points: object) -> None:
            for header in headers:
                actors = [str(PhysicsSchemaTools.intToSdfPath(getattr(header, key))) for key in ('actor0', 'actor1')]
                if any('GroundPlane' in p or 'groundPlane' in p for p in actors):
                    state['ground'] += 1
                if any(p.startswith('/World/scout/') for p in actors) and any(p.startswith('/World/harvest/') for p in actors):
                    data = points[header.contact_data_offset:header.contact_data_offset+header.num_contact_data]
                    state['mutual'].append(dict(tick=state['tick'], actors=actors,
                        colliders=[str(PhysicsSchemaTools.intToSdfPath(getattr(header, key)))
                                   for key in ('collider0', 'collider1')],
                        points=[dict(position=list(p.position), separation=float(p.separation), impulse=list(p.impulse)) for p in data]))

        subscription = get_physx_simulation_interface().subscribe_contact_report_events(contacts)
        results = []
        for case in ('scout_reverse_harvest_forward', 'both_forward_opposite_heading'):
            world.reset()
            for name, robot in robots.items():
                base = robot['base']
                base.initialize()
                position, _ = base.pose()
                heading = section['harvest_route']['heading_rad']
                if name == 'scout' and case == 'both_forward_opposite_heading':
                    heading += math.pi
                asset_yaw = heading-configs[name]['scene_binding'].get('control_frame_yaw_rad', 0.)
                base.robot.set_world_pose(np.array([lane_x[name], start_y[name], position[2]]),
                                          np.array([math.cos(asset_yaw/2), 0., 0., math.sin(asset_yaw/2)]))
                base.robot.set_linear_velocity(np.zeros(3))
                base.robot.set_angular_velocity(np.zeros(3))
            initialize_arm_travel(robots['harvest']['base'].robot, arm_report)
            state.update(case=case, tick=-1, ground=0, mutual=[])
            rows = []
            for tick in range(1380):
                state['tick'] = tick
                for name, robot in robots.items():
                    speed = .1 if 180 <= tick < 1260 else 0.
                    if name == 'scout' and case == 'scout_reverse_harvest_forward':
                        speed *= -1
                    robot['base'].command(speed, 0.)
                world.step(render=False)
                if tick % 6 == 0:
                    row = dict(time_s=(tick+1)/60, robots={})
                    cache = UsdGeom.XformCache()
                    # 충돌 메시의 visibility=invisible도 형상 간격에는 포함한다.
                    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy', 'guide'],
                                               useExtentsHint=False, ignoreVisibility=True)
                    for name, robot in robots.items():
                        transform = np.asarray(cache.GetLocalToWorldTransform(robot['body']), float).T@robot['control']
                        boxes = [bounds.ComputeWorldBound(stage.GetPrimAtPath(p)).ComputeAlignedRange()
                                 for p in robot['colliders']]
                        if any(box.IsEmpty() for box in boxes):
                            raise RuntimeError('충돌체 경계 누락: '+name)
                        limits = [min(b.GetMin()[0] for b in boxes), max(b.GetMax()[0] for b in boxes)]
                        row['robots'][name] = dict(xyz=transform[:3, 3].tolist(), yaw=math.atan2(transform[1, 0], transform[0, 0]), collision_x=limits)
                    row['collision_x_gap_m'] = row['robots'][right]['collision_x'][0]-row['robots'][left]['collision_x'][1]
                    rows.append(row)
            (args.output/(case+'_trajectory.json')).write_text(json.dumps(rows)+'\n')
            (args.output/(case+'_contacts.json')).write_text(json.dumps(state['mutual'])+'\n')
            first, last = rows[30], rows[-1]
            crossed = (harvest_direction*(first['robots']['scout']['xyz'][1]-first['robots']['harvest']['xyz'][1]) > 0
                       and harvest_direction*(last['robots']['scout']['xyz'][1]-last['robots']['harvest']['xyz'][1]) < -.5)
            results.append(dict(case=case, passed_each_other=bool(crossed), robot_contact_events=len(state['mutual']),
                ground_contact_events=state['ground'], minimum_collision_x_gap_m=min(r['collision_x_gap_m'] for r in rows[30:]),
                collider_count={n:len(r['colliders']) for n,r in robots.items()},
                start=first['robots'], end=last['robots']))
            (args.output/'summary.json').write_text(json.dumps(dict(scope='CPU PhysX 60Hz, folded arms, actual collision assets, empty ground, wheel commands 0.1m/s; no Nav2/AMCL/sensors',
                harvest_section=args.harvest_section, scout_section=args.scout_section,
                lane_x=lane_x, center_separation_m=abs(lane_x['harvest']-lane_x['scout']), cases=results), indent=2)+'\n')
            print('[passing_result] '+json.dumps(results[-1]), flush=True)
        world.stop()
    except Exception:
        import traceback
        (args.output/'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
        raise
    finally:
        app.close()


if __name__ == '__main__':
    main()
