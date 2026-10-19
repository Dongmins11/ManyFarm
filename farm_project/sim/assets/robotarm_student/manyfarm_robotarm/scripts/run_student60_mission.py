"""Versioned D435/U20 persistent-scene mission; old Student runners unchanged."""
import argparse
from contextlib import closing
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/harvest_robot'))
BASE = ROOT/'outputs/harvest_rl/student60_improvement_20261015'
U20 = ROOT/'outputs/harvest_rl/student60_u20_set_20261015_172817_e60f49a8/u20_bc_after_collection_r3_quality_20261016'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera', choices=['d435', 'u20'], default='d435')
    p.add_argument('--config', type=Path, default=ROOT/'src/harvest_robot/config/student60_mission_v1.json')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path)
    p.add_argument('--detector', type=Path, default=Path('/home/bhc/Downloads/model_yolo11_seg_ver1.2.pt'))
    p.add_argument('--vision-python', type=Path, default=ROOT/'.venvs/harvest_vision/bin/python')
    p.add_argument('--seed', type=int, default=106146)
    p.add_argument('--wall-seconds', type=float, default=1200.)
    p.add_argument('--headless', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--motion-only', action='store_true', help='Physical stow-HOME-stow check, no harvest success claim')
    p.add_argument('--preview-only', action='store_true', help='Static HOME/stow images; no physical motion validation')
    p.add_argument('--smoke-steps', type=int, default=0)
    p.add_argument('--record-video', action='store_true', help='Record overview and sensor inputs at 1x simulation time')
    a = p.parse_args()
    import numpy as np
    import torch
    from harvest_rl.friction_selected import load_selected
    from harvest_rl.kinematics import ArmKinematics
    from harvest_runtime.student60_mission import HarvestTarget, StudentHarvestMission
    from harvest_runtime.student60_mission_session import MissionCameraSession, lifted_return_path
    from harvest_runtime.student60 import encode_command, decode_command
    torch.set_num_threads(4)
    cfg_motion = json.loads(a.config.read_text())
    checkpoint = a.checkpoint or (BASE/'round2_train_lr1e4/student_best.pt' if a.camera == 'd435' else U20/'train/student_best.pt')
    center = BASE/'camera_only_center/center_best.pt' if a.camera == 'd435' else None
    # Packaged releases supply their own paths; no author's datasets required.
    release = ROOT/'handoff/MISSION_RELEASE.json'
    if release.exists():
        manifest = json.loads(release.read_text())
        model = manifest['models'][a.camera]
        checkpoint = a.checkpoint or ROOT/model['path']
        center = ROOT/manifest['models']['center']['path'] if a.camera == 'd435' else None
        if a.detector == Path('/home/bhc/Downloads/model_yolo11_seg_ver1.2.pt'):
            a.detector = ROOT/manifest['models']['detector']['path']
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True); contract = saved['contract']
    if hashlib.sha256(a.detector.read_bytes()).hexdigest()!=contract['detector_sha256']:
        raise ValueError('Detector differs from the selected camera Student contract')
    if a.camera == 'u20':
        from harvest_rl.student60_u20_data import require_contract
        require_contract(contract)
    runtime_profile, _, physical = load_selected()
    if runtime_profile != contract['teacher_runtime']: raise ValueError('Frozen physical contract differs')
    kin = ArmKinematics(ROOT/contract['camera_config'].get('sensor_reference_urdf', 'src/smartfarm_description/urdf/harvest_robot.urdf')) if a.camera == 'u20' else ArmKinematics()
    for key in ('home_rad', 'stow_rad'):
        q = np.asarray(cfg_motion[key]); assert np.all(q >= kin.lower) and np.all(q <= kin.upper)
    a.output.mkdir(parents=True, exist_ok=False)
    sources=[Path(__file__),a.config]+[f for f in (ROOT/'src/harvest_robot').rglob('*.py') if '__pycache__' not in f.parts]
    pins={str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}
    write(a.output/'source_pins.json',pins)
    write(a.output/'run.json', dict(camera=a.camera, config=cfg_motion, checkpoint=str(checkpoint),
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(), seed=a.seed,
        original_policy_preserved=True, task='persistent_scene_assigned_ripe_targets',
        hardware=False, box_evidence_source='simulator_mesh_adjudicator_only',
        camera_policy_no_truth=True, u20_closed_loop_validation='new_candidate'))
    if not a.execute:
        print('CHECK_ONLY_PASSED', a.output, flush=True); return
    from isaaclab.app import AppLauncher
    app = AppLauncher(headless=a.headless, enable_cameras=True, device='cuda:0',
                      kit_args='--/plugins/carb.tasking.plugin/threadCount=4').app
    env = runtime = video = None; report = None; failed = True
    try:
        from scipy.spatial.transform import Rotation
        from harvest_rl.settings import TaskSettings
        from harvest_rl.environment_version import rooted
        from harvest_rl.attachment_60hz_runtime import response6_runtime
        from harvest_rl.friction_followup import FollowupSpec
        from harvest_rl.jaw_surface_compare_v2 import SurfaceSpec
        from harvest_rl.pressure_compare import PressureSpec
        from harvest_rl.bridge_pull_risk import RiskPullSpec
        from harvest_rl.student60_mission_env import StudentMissionEnv
        from harvest_vision.client import Detector
        from harvest_vision.student60_tracking import AssignedFruitTracker
        from harvest_sensors.student60_eval_camera_cache import install
        install()  # Bit-identical constant K/remap grids, never cached frames.
        if a.camera == 'd435':
            from harvest_sensors.deployment_asset import prepare_deployment_robot
        else:
            from harvest_sensors.u20_deployment_asset import prepare_deployment_robot
        source = json.loads((rooted(physical['policies']['grasp']['path']).parent/'run.json').read_text())
        previous = dict(source['current_asset'])
        if release.exists(): previous['usd'] = str(ROOT/manifest['frozen_physics_usd'])
        frame = np.asarray(source['current_base_to_policy_world'])
        rotation = Rotation.from_matrix(frame[:3, :3]).as_quat()[[3, 0, 1, 2]]
        usd, kin, asset = prepare_deployment_robot(previous, contract['camera_config'])
        for field, expected in [('sensor_mount_reference_urdf_sha256',contract['sensor_mount_reference_urdf_sha256']),
            ('deployment_arm_appearance_sha256',contract['deployment_arm_appearance_sha256']),
            ('asset_input_sha256',contract['robot_asset_sha256'])]:
            if asset[field]!=expected:raise ValueError('Changed camera/robot contract: '+field)
        cfg = TaskSettings(**physical['base_task']); cfg.seed = a.seed; cfg.workspace_split = 'eval'
        runtime = response6_runtime(); runtime.__enter__()
        env = StudentMissionEnv(cfg, camera_kin=kin, camera_config=contract['camera_config'], camera_frame=frame,
            camera_kind=a.camera, frozen_urdf=asset.get('frozen_visual_reference_urdf'),
            progress_budget=True, followup_spec=FollowupSpec(.15,6.,'baseline'),
            surface_spec=SurfaceSpec(1.6,'none'),floor_mode='unified',posture_mode='position',
            stability_mode='pause',pressure_spec=PressureSpec(0.),transport_speed_m_s=.035,
            orientation_length_m=.02,opening_rate_rad_s=.3,deposit_timeout_s=6.,
            hold_stiffness_Nm_rad=1.,gain_ramp_s=1.,path_spec=RiskPullSpec(axial=True,hold_after_detach=True),
            domain=source['domain'],domain_stage=3,domain_split='test',num_envs=1,device='cuda:0',cameras=False,
            robot_usd=usd,robot_root_pose=(tuple(frame[:3,3]),tuple(rotation)),
            fruit_color_override=source['domain']['colors'],fruit_asset_cache=a.output/'fruit_assets',visual_scene='greenhouse_v1')
        if abs(env.physics_dt-1/60)>1e-12 or abs(env.step_dt-.05)>1e-12:raise ValueError('Physical clock changed')
        if [env.robot.joint_names[i] for i in env.jids]!=contract['joint_names']:raise ValueError('Joint order changed')
        np.testing.assert_allclose(env.lower.cpu(),contract['lower_rad'],atol=1e-7)
        np.testing.assert_allclose(env.upper.cpu(),contract['upper_rad'],atol=1e-7)
        env.reset(); env.reset(); env.domain_evaluation = True; env.reset()
        layout=env.author_multifruit_scene()
        write(a.output/'scene_layout.json',dict(version='two_simultaneous_ripe_fruits_v1',
            initial_authoring_only=True,minimum_separation_m=.12,fruits=layout))
        rig = env.student_rig; rig.install_physics_hook(env)
        # Initial scene authoring ONLY. No writes to q/fruit after mission begins.
        def place_initial(q):
            full = env.robot.data.joint_pos.clone(); full[0,env.jids] = torch.as_tensor(q, device=env.device)
            env.robot.write_joint_state_to_sim(full, torch.zeros_like(full))
            env.targets[0] = torch.as_tensor(q, device=env.device); env.robot.set_joint_position_target(env.targets, joint_ids=env.jids)
            env.scene.write_data_to_sim(); env.sim.forward(); env.scene.update(env.physics_dt)
        def pictures(label):
            from pxr import UsdGeom, Gf
            from PIL import Image
            import omni.replicator.core as rep
            rig.follow_wrist(env.robot.data.body_link_pos_w[0,env.tcp_body], env.robot.data.body_link_quat_w[0,env.tcp_body])
            robot_base = frame @ kin.fk(np.zeros(6), 'arm_2/base_link')
            target = robot_base[:3,3]+robot_base[:3,:3]@np.array([.04,0,.15])
            for view, offset in [('side', [-.25,.80,.30]), ('oblique', [-.80,-.55,.40])]:
                camera = UsdGeom.Camera.Define(env.sim.stage, '/World/MissionPreview'+view)
                camera.CreateFocalLengthAttr(30.); camera.CreateClippingRangeAttr(Gf.Vec2f(.01,100.))
                eye = target+robot_base[:3,:3]@np.asarray(offset)
                matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0,0,1)).GetInverse()
                camera.ClearXformOpOrder(); camera.AddTransformOp().Set(matrix)
                product = rep.create.render_product(str(camera.GetPath()), (960,720))
                rgb = rep.AnnotatorRegistry.get_annotator('rgb'); rgb.attach(product)
                for _ in range(8): env.sim.render()
                image = np.asarray(rgb.get_data())
                if image.size == 0: raise RuntimeError('Empty preview rendering')
                Image.fromarray(image[:,:,:3]).save(a.output/f'{label}_{view}.png')
                rgb.detach(product); product.destroy()
        place_initial(cfg_motion['home_rad']); pictures('home')
        place_initial(cfg_motion['stow_rad']); pictures('stow')
        if a.preview_only:
            write(a.output/'result.json',dict(preview_complete=True, motion_validated=False, harvest_validated=False)); failed=False; return
        env.mission_active = True; reset_count = env.physical_resets
        deadline = time.monotonic()+a.wall_seconds
        def measured():
            return (env.robot.data.joint_pos[0,env.jids].cpu().numpy().copy(), env.robot.data.joint_vel[0,env.jids].cpu().numpy().copy())
        def apply(command):
            env.pending_student_command = command.copy()
            env.step(torch.zeros((1,6),device=env.device))
            if env.physical_resets != reset_count: raise RuntimeError('Unexpected scene reset')
            return env.last_applied_command.copy()
        if a.motion_only:
            # Real physical command tracking, not synthetic harvest events.
            q, _ = measured(); command_q = q.copy(); poses=[cfg_motion['stow_rad']]+list(reversed(cfg_motion['home_to_stow_via_rad']))+[cfg_motion['home_rad']]+cfg_motion['home_to_stow_via_rad']+[cfg_motion['stow_rad']]
            index=0; stable=0.; since=0.; rows=[]; status='RUNNING';last_q=None
            for step in range(1600):
                q, qd=measured(); goal=np.asarray(poses[index]); now=step*.05
                fault=env.supervisor_fault()
                if fault: status=fault; break
                encoder_speed=float('inf') if last_q is None else float(np.max(abs(q-last_q))/.05)
                last_q=q.copy()
                good=(np.max(abs(q-goal))<cfg_motion['position_tolerance_rad'] and
                      encoder_speed<cfg_motion['stop_speed_rad_s'] and np.max(abs(qd))<cfg_motion['instantaneous_speed_limit_rad_s'])
                stable=stable+.05 if good else 0.
                if stable>=cfg_motion['settle_s']:
                    rows.append(dict(waypoint=index,stamp_s=now,q_rad=q.tolist(),max_error_rad=float(np.max(abs(q-goal)))))
                    index+=1;stable=0.;since=now
                    if index==len(poses):status='SUCCEEDED';break
                    goal=np.asarray(poses[index])
                if now-since>cfg_motion['waypoint_timeout_s'] or time.monotonic()>deadline:status='TIMED_OUT';break
                desired=np.clip(goal,q-.08,q+.08)
                command_q+=np.clip(desired-command_q,-cfg_motion['speed_rad_s']*.05,cfg_motion['speed_rad_s']*.05)
                actual=apply(encode_command(command_q,[1.,.3],contract['lower_rad'],contract['upper_rad']))
                command_q=decode_command(actual,contract['lower_rad'],contract['upper_rad'])[0]
                if step%40==0: print('MOTION',a.camera,now,index,float(np.max(abs(q-goal))),flush=True)
            write(a.output/'result.json',dict(mode='physical_stow_home_stow',status=status,waypoints=rows,
                final_q_rad=measured()[0].tolist(),final_qd_rad_s=measured()[1].tolist(),
                scene_resets_during_motion=env.physical_resets-reset_count, harvest_evaluated=False))
            failed=False; return
        if a.record_video:
            from harvest_sensors.mission_video import MissionVideo
            video = MissionVideo(env, a.output, a.camera)
        rig.begin_episode(None)
        with closing(Detector(a.vision_python,a.detector,device='cuda:0')) as detector, torch.inference_mode():
            session=MissionCameraSession(checkpoint,contract,detector,kin,frame,camera_kind=a.camera,center_checkpoint=center,device='cuda:0')
            _, detections=session.observe(rig.capture(),0.)
            tracker=AssignedFruitTracker(session.roi); tracker.update(detections,0.)
            targets=[HarvestTarget(key,t['label'],tuple(t['position_m'])) for key,t in tracker.snapshot(0.).items() if t['valid'] and t['label'] in ('Red','Yellow')]
            if not targets: raise RuntimeError('No valid camera targets; empty view is not all-harvested success')
            # Evaluation-only identity map: image-derived target list is fixed
            # first. Simulator truth cannot choose/alter controller coordinates.
            truth=[(session.arm_from_world@np.r_[f.data.root_link_pos_w[0].cpu().numpy(),1])[:3] for f in env.fruits]
            mapping={}
            for t in targets:
                eligible=[i for i,label in enumerate(source['domain']['colors']) if label==t.label]
                distances=sorted((float(np.linalg.norm(truth[i]-t.anchor_arm_m)),i) for i in eligible)
                if not distances or distances[0][0]>.06 or (len(distances)>1 and distances[1][0]-distances[0][0]<.02):
                    raise RuntimeError('Ambiguous evaluation identity mapping')
                mapping[t.target_id]=distances[0][1]
            expected={i for i,label in enumerate(source['domain']['colors']) if label in ('Red','Yellow')}
            write(a.output/'inventory_check.json',dict(targets=[asdict(t) for t in targets],
                evaluation_only_slot_mapping=mapping,expected_slots=sorted(expected),
                detections=[{k:d.get(k) for k in ('label','confidence','candidate_valid','candidate_reason','grasp_estimate_arm_m','bbox')} for d in detections]))
            if set(mapping.values())!=expected or len(mapping)!=len(expected):
                raise RuntimeError('Camera inventory incomplete; cannot claim all ripe fruit mission')
            write(a.output/'targets.json',dict(targets=[asdict(t) for t in targets],evaluation_only_slot_mapping=mapping))
            mission=StudentHarvestMission(session,targets,cfg_motion,
                lambda q,h:lifted_return_path(kin,contract,cfg_motion,q,h),task_list_complete=True)
            previous_state=None; evidence=None
            with (a.output/'trace.jsonl').open('w',buffering=1) as trace:
                for step in range(8000):
                    now=step*.05; q,qd=measured(); fault=env.supervisor_fault()
                    command,note=mission.tick(now,q,qd,now,rig.capture(),box_evidence=evidence,fault=fault);evidence=None
                    if mission.state in ('HARVEST','WAIT_BOX') and not env.assessing:
                        env.begin_target_assessment(mapping[mission.target.target_id])
                    if mission.state!=previous_state:
                        print('MISSION',a.camera,now,mission.state,mission.target.target_id,len(mission.harvested),flush=True);previous_state=mission.state
                    actual=apply(command);mission.acknowledge(actual)
                    if env.assessing and bool(env.success[0]):
                        evidence=dict(target_id=mission.target.target_id,settled=True,stamp_s=now+.05,source='simulator_box_outcome_v2')
                        env.commit_box_success()
                    trace.write(json.dumps(dict(step=step,stamp_s=now,q_rad=q.tolist(),qd_rad_s=qd.tolist(),
                        command=command.tolist(),state=mission.state,target_id=mission.target.target_id,harvested=mission.harvested, fault=fault,
                        camera_target=(note.get('policy_note') or {}).get('target'),
                        assessment={k:float(v[0]) for k,v in getattr(env,'chain_snapshot',{}).items()}))+'\n')
                    report=mission.report();report.update(scene_resets_during_mission=env.physical_resets-reset_count,
                        control_checks=env.control_checks,physics_control_checks=env.physics_control_checks,response6_physics_calls=env.response6_physics_calls)
                    write(a.output/'result.json',report)
                    if video is not None: video.append(mission,rig.capture(),now+.05)
                    if step%40==0:print('MISSION_PROGRESS',a.camera,now,mission.state,len(mission.harvested),'/',len(targets),flush=True)
                    if mission.state in ('DONE','FAILED'):break
                    if a.smoke_steps and step+1>=a.smoke_steps:report['intentional_smoke_stop']=True;break
                    if time.monotonic()>deadline:report['wall_budget_interrupted']=True;break
                    if not app.is_running():report['app_closed']=True;break
                write(a.output/'result.json',report)
        failed=False
    except BaseException:
        write(a.output/'error.json',dict(error=traceback.format_exc()));traceback.print_exc();raise
    finally:
        if video is not None: video.close(report)
        if runtime is not None: runtime.__exit__(None,None,None)
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)


if __name__=='__main__': main()
