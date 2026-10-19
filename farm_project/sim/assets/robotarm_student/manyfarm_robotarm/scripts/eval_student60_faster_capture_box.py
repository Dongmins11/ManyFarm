"""Active camera harvest with lift-before-transfer and independent physical outcome evaluation.

Check-only by default. Use a new output directory, a held-out validation seed,
and an explicit wall budget. Original data/checkpoints/calibration are read-only.
"""
import argparse
from contextlib import closing
import faulthandler
import json
from pathlib import Path
import sys
import time
import traceback
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))


def save(path,data):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)


def preflight(checkpoint,data,seed,camera_path,detector):
    import torch
    from harvest_rl.student60_data import read,digest,contract_for
    from harvest_rl.student60_model import Student60Inference
    from harvest_rl.student60_recurrent import RecurrentCameraInference,FAMILY
    from harvest_rl.student60_crop import from_record,EXTENSION
    from harvest_rl.friction_selected import load_selected
    from harvest_rl.settings import URDF
    from harvest_runtime.student60 import VERSION,OBSERVATION
    plan=read(data);saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    c=saved['contract']
    if saved['student60_version']!=VERSION or c!=plan['contract'] or saved['data_sha256']!=digest(data):
        raise ValueError('Actual checkpoint/data/observation/action contract mismatch')
    if c['observation_contract']!=OBSERVATION:raise ValueError('Old observations')
    seeds={e['seed'] for s in ['train','validation'] for e in plan[s]}
    if seed in seeds:raise ValueError('Evaluation seed overlaps input data')
    if read(camera_path)!=c['camera_config'] or digest(detector)!=c['detector_sha256']:
        raise ValueError('Camera calibration or detector changed')
    if digest(URDF)!=c['sensor_mount_reference_urdf_sha256']:
        raise ValueError('Sensor FK reference changed')
    profile,path,physical=load_selected()
    if profile!=c['teacher_runtime']:raise ValueError('Teacher physical runtime changed')
    reference=Path(plan['train'][0]['path']).parent
    if contract_for(reference)!=c:raise ValueError('Source dataset contract differs')
    pins=read(reference/'run.json')['source_pins']
    for name,expected in pins.items():
        if digest(name)!=expected:raise ValueError('Frozen collection source changed: '+name)
    from harvest_rl.student60_data import Student60Dataset
    import numpy as np
    torch.set_num_threads(4)
    recurrent=saved.get('model_family')==FAMILY
    if recurrent and (plan.get('observation_extension')!=EXTENSION or saved.get('observation_extension')!=EXTENSION):
        raise ValueError('Recurrent camera observation extension mismatch')
    policy=RecurrentCameraInference(checkpoint,c,'cpu') if recurrent else Student60Inference(checkpoint,c,'cpu')
    ds=Student60Dataset(plan['validation'],c)
    recorded=[];predictions=[]
    for i in [0,1,2]:
        obs,_,_=ds[i]
        observation={k:v[-1] for k,v in obs.items()}
        if recurrent:
            folder,step,_=ds.rows[i]
            observation.update(from_record(observation,read(folder/f'{step:06d}.json'),c))
            recorded.append(observation)
        # Offline command history provides the actually executed Teacher labels.
        if i:policy.acknowledge(np.r_[observation['state'][12:18],[-1.,1.]].astype('float32'))
        cmd=policy.predict(observation,'cpu-contract-target')
        predictions.append(cmd)
        if not recurrent:
            with torch.inference_mode():expected=policy.model(**{k:torch.as_tensor(v[None]) for k,v in obs.items()})[0].numpy()
            np.testing.assert_allclose(cmd,expected,atol=1e-6)
    if recurrent:
        with torch.inference_mode():expected=policy.model(**{k:torch.as_tensor(np.stack([o[k] for o in recorded])[None]) for k in recorded[0]})[0].numpy()
        np.testing.assert_allclose(np.asarray(predictions),expected,atol=1e-6)
    result=dict(passed=True,checkpoint_path=str(checkpoint.resolve()),checkpoint_sha256=digest(checkpoint),
        checkpoint_epoch=saved['epoch'],data_path=str(data.resolve()),data_sha256=digest(data),
        student60_version=VERSION,contract_matches=True,input_sources_checked=len(pins),
        history_forward_matches_offline=True,input_seeds=sorted(seeds),seed=seed,
        native_hz=30,policy_hz=20,physics_hz=60,teacher_actors_loaded=False,
        runtime_profile_path=str(path),camera_config_path=str(camera_path),
        model_family=saved.get('model_family','student60_absolute_v1'),
        observation_extension=saved.get('observation_extension'),
        note='CPU/check-only is not a completed harvest evaluation')
    return result,c,physical


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--per-color',type=int,default=5)
    p.add_argument('--colors',nargs='+',choices=['Red','Yellow'],default=['Red','Yellow'])
    p.add_argument('--camera-config',type=Path,default=ROOT/'src/harvest_robot/config/d435_deployment_20261013_overhead30.json')
    p.add_argument('--detector',type=Path,default=Path('/home/bhc/Downloads/model_yolo11_seg_ver1.2.pt'))
    p.add_argument('--vision-python',type=Path,default=ROOT/'.venvs/harvest_vision/bin/python')
    p.add_argument('--detector-device',choices=['cpu','cuda:0'],default='cpu')
    p.add_argument('--fast-native-depth',action='store_true')
    p.add_argument('--success-criterion',choices=['box_outcome','harvest_outcome','legacy_stop'],default='box_outcome')
    p.add_argument('--wall-seconds',type=float,default=900.)
    p.add_argument('--episode-wall-seconds',type=float,default=240.)
    p.add_argument('--headless',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--cache-camera-maps',action='store_true',help='Bit-identical memoization; preserves all native acquisitions')
    p.add_argument('--command-rate-guard',action='store_true',help='Bound desired goal changes by recorded Teacher command speeds')
    p.add_argument('--tracking-mode',choices=['legacy','scoped'],default='scoped')
    p.add_argument('--split',choices=['validation','test'],default='validation')
    p.add_argument('--jaw-intent',choices=['measured','goal_delta'],default='measured')
    p.add_argument('--center-estimator',choices=['ray','sphere'],default='ray')
    p.add_argument('--visual-servo',action='store_true')
    p.add_argument('--center-correction',type=Path)
    p.add_argument('--entry-jaw-gate',action='store_true')
    p.add_argument('--smoke-steps',type=int,default=0,help='Short execution check only; does NOT adjudicate harvest completion')
    a=p.parse_args()
    if not 1<=a.per_color<=20 or not 30<=a.wall_seconds<=3600 or not 10<=a.episode_wall_seconds<=600:
        p.error('Invalid attempt/time budget')
    if a.jaw_intent!='measured':p.error('Response6 evaluation requires measured jaw intent')
    if a.fast_native_depth and a.center_estimator!='ray':p.error('Shared projection currently requires ray centre estimator')
    if a.smoke_steps and not 20<=a.smoke_steps<=100:p.error('Smoke requires20..100 policy steps')
    out=a.output.resolve()
    if out.exists():p.error('Preserve original evaluations: use a new output path')
    check,c,physical=preflight(a.checkpoint,a.data,a.seed,a.camera_config,a.detector)
    print('STUDENT60_CHECK_ONLY',json.dumps(check),flush=True)
    out.mkdir(parents=True);save(out/'check_only.json',check)
    if not a.execute:return
    start=time.monotonic();deadline=start+a.wall_seconds
    result=dict(completed=False,planned_attempts=len(a.colors)*a.per_color,executed_attempts=0,successes=0,
        failures=0,timeouts=0,success_rate_or_null=None,checkpoint_path=check['checkpoint_path'],
        checkpoint_sha256=check['checkpoint_sha256'],seed=a.seed,split=a.split,
        student_only_control_verified=False,attempts=[],unexecuted_attempts=len(a.colors)*a.per_color)
    result['colors']=a.colors
    result['initial_detection_deadline_s']=3.0
    result['success_criterion']={'box_outcome':'box_outcome_v2','harvest_outcome':'harvest_outcome_v1','legacy_stop':'legacy_stopped_release_v1'}[a.success_criterion]
    result['box_task_budget_s']=60. if a.success_criterion=='box_outcome' else None
    result['prescribed_grasp_history_required']=a.success_criterion!='box_outcome'
    result['detector_device']=a.detector_device;result['shared_native_depth_projection']=a.fast_native_depth
    result['placement_quality_successes']=0
    result['started_utc']=datetime.now(timezone.utc).isoformat()
    result['wall_budget_s']=a.wall_seconds;result['episode_wall_budget_s']=a.episode_wall_seconds
    result['camera_map_cache']=a.cache_camera_maps
    result['command_rate_guard']=a.command_rate_guard
    result['tracking_mode']=a.tracking_mode
    result['model_family']=check['model_family']
    result['jaw_intent_semantics']=a.jaw_intent
    result['center_estimator']=a.center_estimator
    result['physical_plant_dispatch']='dynamic_active_response6_checked_each_physics_tick'
    result['visual_servo']=a.visual_servo
    result['control_source']='camera_student_with_side_scan_finite_preload_flexible_transfer_and_faster_capture' if a.visual_servo else 'camera_student_neural_policy'
    from harvest_rl.student60_data import digest as center_digest
    result['center_correction_inputs']='camera_estimate_bbox_depth_quality_only'
    result['entry_jaw_gate']=a.entry_jaw_gate
    result['center_correction_checkpoint']=str(a.center_correction.resolve()) if a.center_correction else None
    result['center_correction_sha256']=center_digest(a.center_correction) if a.center_correction else None
    result['smoke_steps']=a.smoke_steps;result['execution_check_completed']=False
    save(out/'result.json',result)
    from harvest_rl.student60_data import digest
    source_paths=[Path(__file__),ROOT/'src/harvest_robot/harvest_rl/student60_eval_adapter.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_eval_env.py',
        ROOT/'src/harvest_robot/harvest_sensors/student60_eval_camera_cache.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_rate_guard.py',
        ROOT/'src/harvest_robot/harvest_vision/student60_tracking.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_recurrent.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_crop.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_camera_controller.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_command_intent.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_camera_eval_env.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_response6_eval_env.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_response6_boundary.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_outcome_eval_env.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_box_outcome.py',
        ROOT/'src/harvest_robot/harvest_rl/student60_box_outcome_env.py',
        ROOT/'src/harvest_robot/harvest_sensors/student60_native_fast.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_controller.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_visual_servo.py',
        ROOT/'src/harvest_robot/harvest_sensors/native_fruit_center.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_stable_grip.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_entry_hold.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_retention_guard.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_approach_anchor.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_camera_pull.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_pregrasp.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_observed_closure.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_camera_harvest.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_clear_view.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_active_view.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_lifted_harvest.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_reobserved_harvest.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_bounded_occlusion.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_side_scan.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_finite_load.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_flexible_transfer.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_faster_capture.py',
        ROOT/'src/harvest_robot/harvest_runtime/student60_entry_servo.py',
        ROOT/'src/harvest_robot/harvest_vision/student60_center_correction.py',
        ROOT/'src/harvest_robot/harvest_vision/student60_camera_center.py']
    if a.center_correction:source_paths.append(a.center_correction.resolve())
    source_pins={str(p):digest(p) for p in source_paths}
    save(out/'evaluation_source_pins.json',source_pins)
    for path in source_paths:
        destination=out/'evaluation_source_snapshot'/path.relative_to(ROOT)
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(path.read_bytes())
    faulthandler.enable();faulthandler.dump_traceback_later(int(a.wall_seconds)+90,exit=True)
    from isaaclab.app import AppLauncher
    app=AppLauncher(headless=a.headless,enable_cameras=True,device='cuda:0',kit_args='--/plugins/carb.tasking.plugin/threadCount=4').app
    env=runtime=None;failed=True
    try:
        import numpy as np
        import torch
        from scipy.spatial.transform import Rotation
        from PIL import Image
        from harvest_rl.settings import TaskSettings
        from harvest_rl.environment_version import rooted,sha
        from harvest_rl.attachment_60hz_runtime import response6_runtime
        from harvest_rl.friction_followup import FollowupSpec
        from harvest_rl.jaw_surface_compare_v2 import SurfaceSpec,audit as audit_surface
        from harvest_rl.pressure_compare import PressureSpec
        from harvest_rl.bridge_pull_risk import RiskPullSpec
        from harvest_rl.floor_unified import audit_floor_clones
        from harvest_rl.rgbd_geometry import project
        from harvest_rl.student60_eval_env import Student60EvalEnv
        if a.jaw_intent=='measured':
            from harvest_rl.student60_response6_eval_env import Response6CameraStudentEnv
            Student60EvalEnv=Response6CameraStudentEnv
        if a.success_criterion=='harvest_outcome':
            from harvest_rl.student60_outcome_eval_env import OutcomeCameraStudentEnv
            Student60EvalEnv=OutcomeCameraStudentEnv
        if a.success_criterion=='box_outcome':
            from harvest_rl.student60_box_outcome_env import BoxOutcomeCameraStudentEnv
            Student60EvalEnv=BoxOutcomeCameraStudentEnv
        if a.cache_camera_maps:
            from harvest_sensors.student60_eval_camera_cache import install
            install()
        from harvest_sensors.deployment_asset import prepare_deployment_robot
        from harvest_sensors.native_vision import process_native
        if a.center_estimator=='sphere':from harvest_sensors.native_fruit_center import process_native
        if a.fast_native_depth:from harvest_sensors.student60_native_fast import process_native
        from harvest_vision.geometry import Frame
        from harvest_vision.tracking import TrackManager
        from harvest_vision.student60_tracking import AssignedFruitTracker
        from harvest_vision.client import Detector
        from harvest_vision.workspace import load_workspace
        from harvest_runtime.student60_controller import Student60Controller
        from harvest_runtime.student60_camera_controller import make_controller
        if a.command_rate_guard:
            from harvest_runtime.student60_rate_guard import RateGuardedStudent60Controller
            Student60Controller=RateGuardedStudent60Controller
        grasp_path=rooted(physical['policies']['grasp']['path'])
        source=json.loads((grasp_path.parent/'run.json').read_text())
        frame=np.asarray(source['current_base_to_policy_world'])
        rotation=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
        usd,kin,asset=prepare_deployment_robot(source['current_asset'],c['camera_config'])
        for key,expected in [('sensor_mount_reference_urdf_sha256',c['sensor_mount_reference_urdf_sha256']),
            ('deployment_arm_appearance_sha256',c['deployment_arm_appearance_sha256']),('asset_input_sha256',c['robot_asset_sha256'])]:
            if asset[key]!=expected:raise ValueError('Deployment asset contract changed: '+key)
        cfg=TaskSettings(**physical['base_task']);cfg.seed=a.seed;cfg.workspace_split='eval'
        actual_task=cfg.as_dict();actual_task.pop('seed')
        if actual_task!=c['task']:raise ValueError('Physical TaskSettings changed')
        runtime=response6_runtime();provenance=runtime.__enter__()
        env=Student60EvalEnv(cfg,camera_kin=kin,camera_config=c['camera_config'],camera_frame=frame,
            progress_budget=True,followup_spec=FollowupSpec(.15,6.,'baseline'),
            surface_spec=SurfaceSpec(1.6,'none'),floor_mode='unified',posture_mode='position',
            stability_mode='pause',pressure_spec=PressureSpec(0.),transport_speed_m_s=.035,
            orientation_length_m=.02,opening_rate_rad_s=.3,deposit_timeout_s=6.,
            hold_stiffness_Nm_rad=1.,gain_ramp_s=1.,path_spec=RiskPullSpec(axial=True,hold_after_detach=True),
            domain=source['domain'],domain_stage=3,domain_split=a.split,num_envs=1,device='cuda:0',cameras=False,
            robot_usd=usd,robot_root_pose=(tuple(frame[:3,3]),tuple(rotation)),
            fruit_color_override=source['domain']['colors'],fruit_asset_cache=out/'fruit_assets',visual_scene='greenhouse_v1')
        if abs(env.physics_dt-1/60)>1e-12 or abs(env.step_dt-.05)>1e-12:raise ValueError('Clock changed')
        if env.visual_scene['sha256']!=c['visual_scene_sha256']:raise ValueError('Scene changed')
        np.testing.assert_allclose(env.lower.cpu(),c['lower_rad'],atol=1e-7)
        np.testing.assert_allclose(env.upper.cpu(),c['upper_rad'],atol=1e-7)
        if [env.robot.joint_names[i] for i in env.jids]!=c['joint_names']:raise ValueError('Joint order changed')
        rig=env.student_rig;rig.install_physics_hook(env)
        env.reset();env.reset();env.domain_evaluation=True
        arm_from_world=np.linalg.inv(frame@kin.fk(np.zeros(6),'arm_2/base_link'))
        np.testing.assert_allclose(np.linalg.inv(arm_from_world),c['box_from_arm'],atol=1e-10)
        roi,workspace=load_workspace()
        if a.command_rate_guard and check['model_family']!='student60_absolute_v1':raise ValueError('Residual family already bounds command changes')
        controller=Student60Controller(a.checkpoint,c,device='cuda:0') if a.command_rate_guard else make_controller(a.checkpoint,c,device='cuda:0')
        core_controller=controller
        from harvest_vision.student60_camera_center import CenterCorrector,selected_record,features as center_features
        from harvest_rl.student_v2 import measured_proprio
        from harvest_rl.target_contract import student_state
        if a.center_correction:
            center_saved=torch.load(a.center_correction,map_location='cpu',weights_only=True)
            if center_saved['data_sha256']!=check['data_sha256']:raise ValueError('Centre calibration data fingerprint differs')
        center_corrector=CenterCorrector(a.center_correction) if a.center_correction else None
        if a.visual_servo:
            from harvest_runtime.student60_faster_capture import FasterCaptureCameraHarvestController as CameraHarvestController
            controller=CameraHarvestController(controller,kin,c,body_center=a.center_estimator=='sphere',entry_jaw_gate=a.entry_jaw_gate)
        save(out/'plant_audit.json',dict(attachment_runtime=provenance,
            jaw_surface=audit_surface(env),floor=audit_floor_clones(env),current_asset=asset,
            visual_scene=env.visual_scene,domain_bank_range=[int(env.domain_bank_ids.min()),int(env.domain_bank_ids.max())],
            teacher_actor_loads=0,teacher_controllers_called=0,
            command_boundary='Student60CommandBoundary -> HarvestEnv._apply_action only',
            adjudication='original legacy diagnostics + independent actual mesh settlement; safety terminal retained; fixed60s for box_outcome_v2',
            physical_properties_checked=rig.physics_properties_checked))
        with closing(Detector(a.vision_python,a.detector,device=a.detector_device)) as detector,torch.inference_mode():
            for episode,label in enumerate(a.colors*a.per_color):
                if time.monotonic()>=deadline:break
                rig.reset()
                for skip in range(100):
                    env.reset()
                    if source['domain']['colors'][int(env.target_index[0])]==label:break
                else:raise ValueError('Color sampling failed')
                folder=out/f'episode_{episode:04d}';folder.mkdir()
                row=dict(episode=episode,color=label,seed=a.seed,split=a.split,status='RUNNING',
                    domain_sample=env.domain_samples[0].cpu().tolist(),color_reset_skips=skip,
                    initial_fruit_world_m=env._target_fruit().data.root_link_pos_w[0].cpu().tolist(),
                    initial_q_rad=env.robot.data.joint_pos[0,env.jids].cpu().tolist(),
                    initial_targets_rad=env.targets[0].cpu().tolist(),completed=False,steps=0,
                    initial_servo=[float(env.robot.data.joint_stiffness[0,env.jids[-1]]),float(env.robot.data.joint_vel_limits[0,env.jids[-1]])],
                    snapshots=[],phase_events=[],initial_detection_valid=False,initial_truth_error_m=None)
                save(folder/'result.json',row)
                tracker=AssignedFruitTracker(roi) if a.tracking_mode=='scoped' else TrackManager(allow_provisional=True)
                assigned=f'evaluation-{episode:04d}'
                controller.start(assigned,env.targets[0].cpu().numpy())
                rig.begin_episode(None)
                episode_start=time.monotonic();last_phase=None
                print('STUDENT60_START',episode,label,row['domain_sample'],flush=True)
                with (folder/'trace.jsonl').open('w',buffering=1) as trace:
                    for step in range(1200):
                        wall_tick=time.monotonic();timing={}
                        now=step*.05
                        if abs(rig.clock.time-now)>1e-8:raise ValueError('Camera/control drift')
                        capture=rig.capture();frames={}
                        for name,d in capture.items():
                            frames[name]=Frame(d['rgb'],d['aligned_depth_m'],d['intrinsics']['rgb'],
                                arm_from_world@d['world_from_optical']['rgb'],d['stamp_s'],d['pose_stamp_s'],name)
                        timing['capture_view_s']=time.monotonic()-wall_tick;wall_phase=time.monotonic()
                        detections,_=process_native(frames['rear'],capture['rear'],detector,now,c['centre_offset_m'],
                            arm_roi=roi if tracker.selected is None else None)
                        timing['native_detection_s']=time.monotonic()-wall_phase;wall_phase=time.monotonic()
                        tracker.update(detections,now)
                        if tracker.selected is None:
                            candidates=[k for k,t in tracker.snapshot(now).items() if t['valid'] and t['label']==label]
                            if len(candidates)==1:tracker.assign(now,candidates[0])
                        target=tracker.observation(now);target['target_id']=assigned
                        q=env.robot.data.joint_pos[0,env.jids].cpu().numpy().copy()
                        qd=env.robot.data.joint_vel[0,env.jids].cpu().numpy().copy()
                        tcp=(arm_from_world@np.r_[env._tcp()[0][0].cpu().numpy(),1])[:3]
                        center_diagnostic=None
                        uncorrected=core_controller.target_filter.filter(target)
                        observed=selected_record(uncorrected['position_m'],detections) if uncorrected['valid'] else None
                        assigned_detection=(observed if observed is not None
                            and np.linalg.norm(np.asarray(observed['grasp_estimate_arm_m'])-uncorrected['position_m'])<1e-7
                            and abs(now-uncorrected['age_s']-observed['stamp_s'])<1e-7 else None)
                        if uncorrected['valid'] and center_corrector is not None:
                            if observed is not None:
                                corrected,offset=center_corrector.predict(None,uncorrected['position_m'],observed)
                                center_diagnostic=dict(raw_position_m=target['position_m'],offset_m=offset.tolist(),
                                    observed_features=center_features(None,uncorrected['position_m'],observed).tolist())
                                target=dict(target,position_m=corrected.tolist())
                        controller_capture=dict(capture,student_target_detections=detections,
                            student_assigned_detection=assigned_detection)
                        command,note=controller.step(frames,q,qd,tcp,target,now,controller_capture)
                        timing['student_observation_inference_s']=time.monotonic()-wall_phase;wall_phase=time.monotonic()
                        # Truth is used only below this observation/control boundary.
                        fruit_data=env._target_fruit().data
                        fruit_world=fruit_data.root_link_pos_w[0].cpu().numpy()
                        truth=(arm_from_world@np.r_[fruit_world,1])[:3]
                        fruit_rotation=Rotation.from_quat(fruit_data.root_link_quat_w[0].cpu().numpy()[[1,2,3,0]]).as_matrix()
                        hull=env.fruit_collision_hulls[int(env.target_index[0])].cpu().numpy()@fruit_rotation.T+fruit_world
                        visibility={}
                        for view,streams in [('right',['rgb','ir_right']),('rear',['rgb'])]:
                            for stream in streams:
                                d=capture[view];spec=c['camera_config']['views'][view]['streams'][stream]
                                uv,z,visible=project(np.vstack((fruit_world,hull)),d['world_from_optical'][stream],
                                    d['intrinsics'][stream],(spec['height'],spec['width']))
                                visibility[view+'_'+stream]=dict(center_visible=bool(visible[0]),
                                    hull_visible_fraction=float(visible[1:].mean()),hull_clipped=bool(not visible[1:].all()),
                                    center_pixel_uv=uv[0].tolist(),pose_stamp_s=d['pose_stamp_s'],truth_stamp_s=now,
                                    note='FOV projection only; does not detect occlusion')
                        error=float(np.linalg.norm(truth-np.asarray(note['target']['position_m']))) if note['target']['valid'] else None
                        if note['target']['valid'] and not row['initial_detection_valid']:
                            row['initial_detection_valid']=True;row['initial_truth_error_m']=error
                            row['first_detection_s']=now
                        env.pending_student_command=command.copy()
                        _,_,terminated,timeout,_=env.step(torch.zeros((1,6),device=env.device))
                        applied=env.last_applied_command.copy();controller.acknowledge(applied)
                        timing['physics_native_capture_s']=time.monotonic()-wall_phase
                        diagnostic={k:float(v[0]) for k,v in env.chain_snapshot.items()}
                        phase=('place' if diagnostic.get('deposit_active') else 'transport' if diagnostic.get('transport_active')
                            else 'pull' if diagnostic.get('chain_pull_active') else 'bridge' if diagnostic.get('chain_bridge_confirmed') else 'approach')
                        if phase!=last_phase:row['phase_events'].append(dict(step=step,sim_s=now,phase=phase));last_phase=phase
                        record=dict(step=step,sim_s=now,phase=phase,measured_q_rad=q.tolist(),measured_qd_rad_s=qd.tolist(),
                            tcp_arm_m=tcp.tolist(),predicted_command=command.tolist(),applied_command=applied.tolist(),
                            target=note['target'],release_latched=note['release_latched'],truth_error_m=error,
                            detection_summary=[{k:d.get(k) for k in ['label','confidence','bbox','candidate_valid','candidate_reason','reason','control_valid','depth_coverage','grasp_estimate_arm_m','surface_arm_m','camera_id','stamp_s','body_center_fit','centre_method','ray_prior_estimate_arm_m']} for d in detections],
                            cameras={name:{k:d[k] for k in ['frame_number','stamp_s','pose_stamp_s','fk_max_error']} for name,d in capture.items()},
                            wrist_ir_valid=bool('ir_right' in capture['right']['ir'] and 0<=now-capture['right']['stamp_s']<=.3),diagnostic=diagnostic)
                        record['wall_timing']=timing
                        arm_forces=env.arm_contact.data.net_forces_w[0].norm(dim=-1).cpu().tolist()
                        arm_names=getattr(env.arm_contact,'body_names',[str(i) for i in range(len(arm_forces))])
                        record['diagnostic_arm_contacts_N']={name:force for name,force in zip(arm_names,arm_forces) if force>1.}
                        record['tracking_diagnostic']=getattr(tracker,'last_update',{})
                        record['target_crop_valid']=note.get('target_crop_valid')
                        record['center_correction']=center_diagnostic
                        record['assigned_detection']=assigned_detection
                        if center_diagnostic is not None:
                            center_diagnostic['diagnostic_raw_root_error_m']=float(np.linalg.norm(truth-np.asarray(center_diagnostic['raw_position_m'])))
                        if 'visual_servo' in note:record['visual_servo']=note['visual_servo']
                        if 'command_guard' in note:record['command_guard']=note['command_guard']
                        record['diagnostic_truth_visibility']=visibility
                        trace.write(json.dumps(record)+'\n');row['steps']=step+1
                        done=bool(terminated[0] or timeout[0])
                        if step==0 or (episode<2 and step in [40,160]) or done:
                            for name,array in [('wrist_rgb',capture['right']['rgb']),('wrist_right_ir',capture['right']['ir']['ir_right']),('rear_rgb',capture['rear']['rgb'])]:
                                path=folder/f'{step:04d}_{name}.jpg';Image.fromarray(array).save(path);row['snapshots'].append(str(path))
                        if done:
                            row['status']='SUCCEEDED' if diagnostic['success'] else 'FAILED' if diagnostic['failure'] else 'TIMED_OUT'
                            row['terminal']=diagnostic;row['completed']=True;break
                        if now>=3.0 and not row['initial_detection_valid']:
                            row.update(status='FAILED',reason='initial_detection_missing_within_3s',terminal=diagnostic,completed=True);break
                        if a.smoke_steps and step+1>=a.smoke_steps:
                            row.update(status='SMOKE_CHECK_FINISHED',reason='intentional_short_execution_check',
                                terminal=diagnostic,execution_check_completed=True);break
                        if time.monotonic()>=deadline or time.monotonic()-episode_start>=a.episode_wall_seconds:
                            row.update(status='WALL_BUDGET_INTERRUPTED',reason='rollout_incomplete_wall_budget',terminal=diagnostic);break
                        if not app.is_running():row.update(status='INTERRUPTED',reason='app_stopped');break
                    else:row.update(status='INTERRUPTED',reason='unexpected_step_ceiling')
                rig.reset();row['elapsed_wall_s']=time.monotonic()-episode_start
                save(folder/'result.json',row);result['attempts'].append(row)
                result['executed_attempts']=len(result['attempts'])
                result['successes']=sum(r['status']=='SUCCEEDED' for r in result['attempts'])
                result['placement_quality_successes']=sum(r['status']=='SUCCEEDED'
                    and bool(r.get('terminal',{}).get('valid_release'))
                    and not bool(r.get('terminal',{}).get('release_quality_violation',True)) for r in result['attempts'])
                result['failures']=sum(r['status']=='FAILED' for r in result['attempts'])
                result['timeouts']=sum(r['status']=='TIMED_OUT' for r in result['attempts'])
                result['unexecuted_attempts']=result['planned_attempts']-result['executed_attempts']
                result['student_only_control_verified']=env.control_checks>0 and env.physics_control_checks==3*env.control_checks
                result['control_checks']=env.control_checks;result['physics_control_checks']=env.physics_control_checks
                result['response6_physics_calls']=getattr(env,'response6_physics_calls',0)
                if result['response6_physics_calls']!=env.physics_control_checks:raise RuntimeError('Not every Student physics tick ran response6')
                save(out/'result.json',result)
                print('STUDENT60_EPISODE',episode,label,row['status'],row['steps'],row['elapsed_wall_s'],flush=True)
                if not row['completed'] and row['status']!='SMOKE_CHECK_FINISHED':break
        from harvest_rl.friction_selected import load_selected
        load_selected()
        for name,digest in asset['preserved_usd_layers'].items():
            if sha(name)!=digest:raise ValueError('Preserved physical asset changed')
        result['completed']=(result['executed_attempts']==result['planned_attempts'] and
            all(r['completed'] for r in result['attempts']) and result['student_only_control_verified'])
        result['execution_check_completed']=(bool(a.smoke_steps) and result['executed_attempts']==result['planned_attempts']
            and all(r['completed'] or r.get('execution_check_completed') for r in result['attempts'])
            and result['student_only_control_verified'])
        if a.smoke_steps:result['completed']=False
        if result['completed']:result['success_rate_or_null']=result['successes']/result['planned_attempts']
        result['elapsed_wall_s']=time.monotonic()-start
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        for name,digest in source_pins.items():
            if sha(name)!=digest:raise ValueError('Evaluation source changed during rollout: '+name)
        save(out/'result.json',result);failed=False
        print('STUDENT60_RESULT',result['completed'],result['successes'],'/',result['executed_attempts'],flush=True)
    except BaseException:
        result.update(error=traceback.format_exc(),completed=False)
        result['elapsed_wall_s']=time.monotonic()-start
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        save(out/'result.json',result);save(out/'error.json',dict(traceback=traceback.format_exc()));raise
    finally:
        faulthandler.cancel_dump_traceback_later()
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)
        if runtime is not None:runtime.__exit__(None,None,None)


if __name__=='__main__':main()
