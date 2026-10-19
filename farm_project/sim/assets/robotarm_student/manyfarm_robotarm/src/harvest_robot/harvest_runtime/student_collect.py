"""Camera-only student observations paired with staged expert actions, before stepping."""
import json
import hashlib
import os,time,faulthandler
from contextlib import closing
import numpy as np
import torch
from harvest_vision.client import Detector
from harvest_vision.geometry import Frame
from harvest_vision.pipeline import process
from harvest_vision.tracking import TrackManager
from harvest_vision.dataset import EpisodeWriter
from harvest_rl.student_v2 import pack_observation, StudentInference


def evaluate(env, wrapped, teacher, args, out, app, kin, world_from_robot):
    trace=os.environ.get('HARVEST_COLLECT_TRACE','1')=='1'
    def phase(name):
        if trace:
            (out/'collect_phase.json').write_text(json.dumps(dict(phase=name,episode=episode,frame=local,wall_time=time.time())))
            faulthandler.dump_traceback_later(45,repeat=True)
    student_path=getattr(args,'student_checkpoint',None)
    if student_path and torch.load(student_path,map_location='cpu',weights_only=True).get('schema_version')==3:
        from harvest_rl.student_v3 import StudentInference as Inference
    else:Inference=StudentInference
    student=Inference(student_path,env.device) if student_path else None
    dagger=bool(getattr(args,'dagger_approach',False))
    oracle=None
    if dagger:
        from .approach_oracle import ApproachOracle
        oracle=ApproachOracle(teacher.grasp_expert,env.max_episode_length)
    rng=np.random.default_rng(args.seed)
    rig=env.student_rig
    from harvest_sensors.deployment import is_deployment, CAPTURE_CONTRACT, RawCaptureWriter
    deployment=is_deployment(rig.config)
    if deployment and (dagger or getattr(args,'entry_checkpoint',None)):
        raise ValueError('Student v3 needs its own DAgger/entry auxiliary contract; v2 auxiliary inputs cannot be mixed')
    base=world_from_robot@kin.fk(np.zeros(6),'arm_2/base_link')
    arm_from_world=np.linalg.inv(base)
    from harvest_vision.workspace import load_workspace
    assignment_roi,assignment_contract=load_workspace()
    manifest=dict(capture_contract=CAPTURE_CONTRACT if deployment else 'synchronised_rgbd_v1',schema_version=3 if deployment else 2,camera_order=['right','rear'],camera_config=rig.config,
        visual_scene=env.visual_scene,
        observation_geometry_schema='arm_tcp_v1',
        initial_target_workspace=assignment_contract,
        frame_id='arm_2/base_link',clock_id='simulation',provisional_centres=True,centre_offset_m=args.student_centre_offset,
        detector=str(args.student_detector),detector_sha256=hashlib.sha256(args.student_detector.read_bytes()).hexdigest(),
        experts=teacher.contract,labels='executed staged teacher action; not privileged student inputs',
        target_assignment='unique detected color matching explicit assigned teacher target; ambiguous assignment rejected',
        history=3,control_dt=env.step_dt,episodes=[],
        joint_names=[env.robot.joint_names[i] for i in env.jids],
        lower_rad=env.lower.cpu().tolist(),upper_rad=env.upper.cpu().tolist(),
        action_contract='six normalized joint target increments; existing Teacher low-level controller applies; not direct torque')
    if deployment:
        manifest['sensor_dt']=rig.config['sensor_dt']
        manifest['timing_contract']=dict(camera_hz=30,policy_hz=20,physics_dt=env.physics_dt,
            capture_stride_physics=rig.clock.stride,history_clock='control',
            frame_clock='episode simulation time',reset_clears_frames=True,
            pose_source='measured capture-time joints/FK; factory depth offset from RGB mount')
    profile_path=os.environ.get('STUDENT_TEACHER_PROFILE')
    if profile_path:
        from pathlib import Path
        raw=Path(profile_path).read_bytes()
        manifest['teacher_profile']=dict(path=profile_path,sha256=hashlib.sha256(raw).hexdigest(),profile=json.loads(raw))
    for key in ('checkpoint','grasp_expert','transport_expert','place_expert'):
        path=getattr(args,key)
        manifest[key]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if student:
        saved=torch.load(student_path,map_location='cpu',weights_only=True)
        if saved.get('smoke_test_only'):manifest['smoke_test_only']=True
        contract=saved['input_contract']
        if contract.get('capture_contract','synchronised_rgbd_v1')!=manifest['capture_contract']:
            raise ValueError('Student capture timing contract mismatch')
        if deployment and contract.get('timing_contract')!=manifest['timing_contract']:
            raise ValueError('Student acquisition timing mismatch')
        if deployment and contract.get('visual_scene_sha256')!=env.visual_scene.get('sha256'):
            raise ValueError('Student background appearance mismatch')
        for key in ('camera_order','camera_config','frame_id','history','control_dt','lower_rad','upper_rad','joint_names','detector_sha256','action_contract'):
            if contract[key]!=manifest[key]: raise ValueError(f'Student input contract mismatch: {key}')
        if contract.get('centre_offset_m',.035)!=args.student_centre_offset: raise ValueError('Student centre offset mismatch; use training calibration')
        if contract.get('initial_target_workspace')!=assignment_contract:raise ValueError('Student initial target workspace mismatch; collect/train the new selection contract')
        from harvest_rl.student_bc import canonical_teacher_runtime
        if canonical_teacher_runtime(contract['teacher_runtime'])!=canonical_teacher_runtime(json.loads(json.dumps(teacher.contract['runtime']))):
            raise ValueError('Student runtime mismatch')
        if dagger:
            for key in ('checkpoint','grasp_expert','transport_expert','place_expert'):
                if contract[key]!=manifest[key]['sha256']:raise ValueError('DAgger oracle differs from frozen BC Teacher; collect a separate dataset revision')
            if contract['action_execution']!=teacher.contract.get('action_execution'):raise ValueError('DAgger Teacher action execution mismatch')
        if contract['robot_asset_sha256']!=json.loads((out/'run.json').read_text())['current_asset']['asset_input_sha256']:
            raise ValueError('Student robot mismatch')
        if deployment and contract.get('sensor_mount_reference_urdf_sha256')!=json.loads((out/'run.json').read_text())['current_asset']['sensor_mount_reference_urdf_sha256']:
            raise ValueError('Student sensor mounting reference mismatch')
        if deployment and contract.get('deployment_arm_appearance_sha256')!=json.loads((out/'run.json').read_text())['current_asset']['deployment_arm_appearance_sha256']:
            raise ValueError('Student arm appearance mismatch')
        manifest['reachable_revision']='coverage_dedup_bounded_integral_v2' if getattr(args,'student_reachable_approach',False) else None
        manifest['student_reachable_approach']=bool(getattr(args,'student_reachable_approach',False))
        manifest['student_align_approach']=bool(getattr(args,'student_align_approach',False))
        manifest['student_open_approach']=bool(getattr(args,'student_open_approach',False))
        manifest.update(evaluation_only=True,labels='student actions; DO NOT use as Teacher demonstrations',
            student_checkpoint=str(student_path),student_sha256=hashlib.sha256(student_path.read_bytes()).hexdigest(),
            control='Student only; no Teacher action/routing/ramp/fixed release. Existing environment low-level grip controller retained; simulation truth used for scoring.')
        (out/'DO_NOT_TRAIN.json').write_text(json.dumps({'reason':'Student evaluation, not expert demonstrations'}))
        if dagger:
            manifest.update(dagger_schema='approach_oracle_v1',labels='NPZ action is read-only entry Teacher label; executed_action is separately annotated',
                dagger_beta=args.dagger_beta,dagger_approach_s=args.dagger_approach_s,
                dagger_contact_evidence='capture_tick_only_v2_reset_excluded',
                control='Student/entry oracle mixed approach then staged Teacher recovery; NOT Student success rate')
            (out/'DO_NOT_TRAIN.json').write_text(json.dumps({'reason':'DAgger recovery collection; dedicated audit required, never standard BC'}))
    if getattr(args,'eval_fruit_mass',None) is not None:
        manifest.update(evaluation_only=True, mass_evaluation_kg=args.eval_fruit_mass)
        (out/'DO_NOT_TRAIN.json').write_text(json.dumps({'reason':'Teacher mass transfer evaluation; review before training use'}))
    def save():
        (out/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2))
        if student:
            from collections import Counter
            (out/'student_eval_summary.json').write_text(json.dumps(dict(
                checkpoint=manifest['student_checkpoint'],episodes=manifest['episodes'],
                outcomes=dict(Counter(x['status'] for x in manifest['episodes'])),
                control=manifest['control']),indent=2))
    save();steps=0
    entry_aux=None
    if getattr(args,'entry_checkpoint',None):
        from harvest_rl.entry_aux import EntryAuxInference
        from train_entry_aux import observation_contract
        entry_aux=EntryAuxInference(args.entry_checkpoint,observation_contract(out),env.device)
    with closing(Detector(args.student_vision_python,args.student_detector)) as detector:
        with torch.inference_mode():
            episode_start=getattr(args,'student_episode_start',0)
            for episode in range(episode_start,episode_start+args.episodes):
                if steps>=args.steps or not app.is_running(): break
                if deployment:rig.reset()
                env.layout_episode=episode;env.reset();obs=env.assign_target(env.assignment_slot);teacher.reset()
                if student:
                    student.reset()
                    for attr in ('expert_stage','entry_grasp_active'):
                        if hasattr(env,attr): delattr(env,attr)
                if oracle:oracle.reset()
                recovering=False;dagger_prefix_count=0;takeover=None;recovery_eligible=True
                if entry_aux:entry_aux.reset()
                from harvest_rl.student_approach import OpenApproach
                approach=OpenApproach(env.step_dt) if getattr(args,'student_open_approach',False) else None
                alignment=None
                if getattr(args,'student_align_approach',False) or getattr(args,'student_reachable_approach',False):
                    from harvest_rl.student_alignment import AlignedApproach
                    def gap_pose(q):
                        t=arm_from_world@world_from_robot@kin.fk(q,'arm_2/gripper_link')
                        gap=.0281*(1-np.cos(q[-1]))+.0616*np.sin(q[-1])
                        t[:3,3]+=t[:3,:3]@np.array([-.0079+gap/2,-.000218121,-.085])
                        return t
                    alignment=AlignedApproach(gap_pose,env.lower.cpu().numpy(),env.upper.cpu().numpy(),env.step_dt,env.settings.action_speed)
                reachable=None;lost_s=0.
                if getattr(args,'student_reachable_approach',False):
                    from harvest_rl.reachable_approach import ReachableApproach
                    reachable=ReachableApproach(gap_pose,env.lower.cpu().numpy(),env.upper.cpu().numpy(),env.settings.diameter,env.step_dt,env.settings.action_speed,env.settings.gripper_speed)
                    alignment=None
                tracker=TrackManager(allow_provisional=True,deduplicate=reachable is not None)
                writer=EpisodeWriter(out/f'episode_{episode:04d}',dict(input_schema_version=3 if deployment else 2,seed=args.seed,episode=episode,layout=env.last_layout))
                if deployment:
                    rig.begin_episode(RawCaptureWriter(writer.root/'raw_captures'))
                valid_count=0;status='CANCELLED';initial_selection=None
                try:
                    local=0
                    while env.assignment_status=='RUNNING' and steps<args.steps and app.is_running():
                        stamp=local*env.step_dt
                        if deployment:
                            if abs(rig.clock.time-stamp)>1e-8:raise RuntimeError('Control/capture clock drift')
                        else:
                            phase('follow_wrist')
                            rig.follow_wrist(env.robot.data.body_link_pos_w[0,env.tcp_body],env.robot.data.body_link_quat_w[0,env.tcp_body])
                            phase('forward');env.sim.forward()
                            phase('render_1');env.sim.render()
                            phase('render_2');env.sim.render()
                            phase('sensor_update');rig.update(env.step_dt)
                        phase('capture');capture=rig.capture();frames={};records=[]
                        for name,data in capture.items():
                            f=Frame(data['rgb'],data['aligned_depth_m'],data['intrinsics']['rgb'],
                                arm_from_world@data['world_from_optical']['rgb'],data['stamp_s'] if deployment else stamp,
                                data['pose_stamp_s'] if deployment else stamp,name)
                            # Assert capture transform agrees with measured joint FK at this timestamp.
                            q=np.asarray(data['capture_joint_rad']) if deployment else env.robot.data.joint_pos[0,env.jids].cpu().numpy()
                            prefix='arm_2/wrist_camera' if name=='right' else 'top_camera'
                            expected=arm_from_world@world_from_robot@kin.fk(q,prefix+'_color_optical_frame')
                            error=float(np.abs(expected-f.arm_from_optical).max())
                            if error>2e-4: raise RuntimeError(f'Camera/joint timestamp mismatch {name}: {error}')
                            frames[name]=f
                            if deployment and name=='right':
                                # Target 3D comes exclusively from overhead RGB-D.
                                continue
                            phase('detector_'+name)
                            if deployment:
                                from harvest_sensors.native_vision import process_native
                                detections,overlay=process_native(f,data,detector,stamp,args.student_centre_offset,
                                    arm_roi=assignment_roi if tracker.selected is None else None)
                            else:
                                detections,overlay=process(f,detector,stamp,args.student_centre_offset,
                                    arm_roi=assignment_roi if tracker.selected is None else None)
                            if tracker.selected is None:
                                from PIL import Image
                                Image.fromarray(overlay).save(writer.root/f'initial_{name}_detections.png')
                            records.extend(detections)
                        phase('tracking')
                        tracker.update(records,stamp)
                        if tracker.selected is None:
                            label=env.last_layout['target_color']
                            candidates=[k for k,t in tracker.snapshot(stamp).items() if t['valid'] and t['label']==label]
                            initial_selection=dict(label=label,candidate_ids=candidates,tracks=tracker.snapshot(stamp),
                                records=records,workspace=assignment_contract)
                            if len(candidates)!=1:
                                status='TARGET_UNAVAILABLE';break
                            tracker.assign(stamp,candidates[0])
                        target=tracker.observation(stamp)
                        # Dataset-only label alignment check; never feed this truth into the student.
                        if local==0:
                            truth=env._target_fruit().data.root_link_pos_w[0].cpu().numpy()
                            truth_arm=(arm_from_world@np.r_[truth,1])[:3]
                            association_error=float(np.linalg.norm(truth_arm-np.asarray(target['position_m'])))
                            if association_error>.08:
                                status='TARGET_ASSOCIATION_REJECTED';break
                        valid_count+=target['valid']
                        tcp=env._tcp()[0][0].cpu().numpy()
                        tcp_arm=(arm_from_world@np.r_[tcp,1])[:3]
                        phase('pack_observation')
                        if deployment:
                            from harvest_rl.student_v3 import pack_observation as pack_multimodal
                            sample=pack_multimodal(frames,env.proprio()[0].cpu().numpy(),tcp_arm,target,stamp,capture)
                        else:sample=pack_observation(frames,env.proprio()[0].cpu().numpy(),tcp_arm,target,stamp)
                        entry_prediction=entry_aux.predict(sample,target['target_id']) if entry_aux else None
                        phase('teacher')
                        action=(torch.as_tensor(student.predict(sample,target['target_id']),device=env.device).unsqueeze(0) if student else teacher(obs)).clamp(-1,1)
                        raw_action=action[0].cpu().numpy().copy()
                        dagger_note=None;label_action=None
                        if dagger:
                            if not recovering:
                                from .approach_oracle import recovery_reason,current_contact_evidence
                                evidence=current_contact_evidence(env.last_diagnostics,stamp)
                                takeover=recovery_reason(attached=bool(env._t(env.attached)[0]),confirmed=bool(env.has_grasped[0] and env.grip[0]),
                                    **evidence,elapsed_s=stamp,
                                    limit_s=args.dagger_approach_s,target_valid=bool(target['valid']))
                                if takeover:
                                    recovery_eligible=takeover!='DETACHED_REJECT'
                                    recovering=True;teacher.reset()
                            if recovering:
                                action=teacher(obs).clamp(-1,1)
                            else:
                                label_action=oracle.query(obs)
                                use_teacher=rng.random()<args.dagger_beta
                                if use_teacher:action=label_action.clone()
                                dagger_prefix_count+=1
                                dagger_note=dict(schema='approach_oracle_v1',label_source='readonly_entry_oracle',
                                    executed_source='entry_oracle' if use_teacher else 'student',
                                    label_action=label_action[0].cpu().tolist(),executed_action=action[0].cpu().tolist(),
                                    attached=True,confirmed=False,eligible=bool(target['valid']))
                        approach_prediction=None
                        if approach and reachable is None:
                            from isaaclab.utils.math import quat_apply_inverse
                            delta_world=arm_from_world[:3,:3].T @ np.asarray(sample['state'][18:21])
                            local_est=quat_apply_inverse(env._tcp()[1],torch.as_tensor(delta_world,device=env.device,dtype=torch.float32)[None])[0].cpu().numpy()
                            jaw_measured=env.robot.data.joint_pos[0,env.jids[-1]]
                            measured_gap=float(.0281*(1-torch.cos(jaw_measured))+.0616*torch.sin(jaw_measured))
                            command,approach_prediction=approach.apply(raw_action,sample,local_est,target['target_id'],measured_gap,env.settings.diameter)
                            if alignment and alignment.stage != 'INSERT':
                                approach_prediction['ready']=False
                            if alignment and approach_prediction['observable'] and approach_prediction['opened'] and not approach_prediction['abort'] and not approach_prediction['ready']:
                                command,alignment_diagnostic=alignment.command(env.robot.data.joint_pos[0,env.jids].cpu().numpy(),env.targets[0].cpu().numpy(),np.asarray(target['position_m']))
                                approach_prediction['alignment']=alignment_diagnostic
                                if alignment_diagnostic['abort']:approach_prediction['abort']=alignment_diagnostic['abort']
                            action=torch.as_tensor(command,device=env.device,dtype=torch.float32)[None]
                        if reachable:
                            observed=bool(sample['state'][21] and 0<=sample['state'][22]<=env.step_dt and sample['camera_valid'].any())
                            lost_s=0. if observed else lost_s+env.step_dt
                            if observed:
                                measured=env.robot.data.joint_pos[0,env.jids].cpu().numpy()
                                # Catch FK/frame mismatches before executing planned commands.
                                expected=gap_pose(measured)[:3,3]
                                jaw=measured[-1];gap=.0281*(1-np.cos(jaw))+.0616*np.sin(jaw)
                                from isaaclab.utils.math import quat_apply
                                offset=torch.tensor([[(gap-env.settings.diameter)/2,0.,0.]],device=env.device,dtype=torch.float32)
                                actual_world=env._tcp()[0][0]+quat_apply(env._tcp()[1],offset)[0]
                                actual_arm=(arm_from_world@np.r_[actual_world.cpu().numpy(),1])[:3]
                                if np.linalg.norm(expected-actual_arm)>.002:raise RuntimeError('Approach FK mismatch >2mm')
                                command,approach_prediction=reachable.command(measured,env.targets[0].cpu().numpy(),target['position_m'])
                                action=torch.as_tensor(command,device=env.device,dtype=torch.float32)[None]
                            else:
                                action=torch.zeros_like(action)
                                approach_prediction=dict(ready=False,abort='TARGET_LOST' if lost_s>=.5 else None,stage='WAIT_OBSERVATION')
                        geometry_diagnostic={}
                        if student or getattr(args,"eval_fruit_mass",None) is not None or getattr(args,'deployment_nine_gram',False):
                            from isaaclab.utils.math import quat_apply_inverse, quat_apply, quat_conjugate, quat_mul
                            fruit=env._target_fruit()
                            root=fruit.data.root_link_pos_w[0].cpu().numpy()
                            centre=env._grasp_center(fruit)[0].cpu().numpy()
                            _,tcp_quat=env._tcp()
                            relative=quat_apply_inverse(tcp_quat,env._grasp_center(fruit)-env._tcp()[0])[0].cpu().numpy()
                            jaw=env.robot.data.joint_pos[0,env.jids[-1]]
                            gap=.0281*(1-torch.cos(jaw))+.0616*torch.sin(jaw)
                            shift=torch.zeros((1,3),device=env.device)
                            shift[0,0]=gap/2-env.settings.diameter/2
                            gap_world=tcp+quat_apply(tcp_quat,shift)[0].cpu().numpy()
                            geometry_diagnostic=dict(
                                nominal_pad_gap_m=float(gap),
                                nominal_gap_midpoint_arm_m=(arm_from_world@np.r_[gap_world,1])[:3].tolist(),
                                fruit_root_world_m=root.tolist(),
                                fruit_root_arm_m=(arm_from_world@np.r_[root,1])[:3].tolist(),
                                fruit_center_arm_m=(arm_from_world@np.r_[centre,1])[:3].tolist(),
                                tcp_arm_m=tcp_arm.tolist(),fruit_in_tcp_m=relative.tolist(),
                                # Evaluation-only evidence, never included in Student observations.
                                tcp_quaternion_world_wxyz=tcp_quat[0].cpu().tolist(),
                                fruit_quaternion_world_wxyz=fruit.data.root_link_quat_w[0].cpu().tolist(),
                                fruit_in_tcp_quaternion_wxyz=quat_mul(quat_conjugate(tcp_quat),fruit.data.root_link_quat_w)[0].cpu().tolist(),
                                fruit_com_linear_velocity_world_m_s=fruit.data.root_com_lin_vel_w[0].cpu().tolist(),
                                fruit_com_angular_velocity_world_rad_s=fruit.data.root_com_ang_vel_w[0].cpu().tolist(),
                                joint_position_rad=env.robot.data.joint_pos[0,env.jids].cpu().tolist(),
                                joint_velocity_rad_s=env.robot.data.joint_vel[0,env.jids].cpu().tolist(),
                                joint_target_rad=env.targets[0].cpu().tolist(),
                                attached=bool(env.attached[0,env.assignment_slot]),
                                has_grasped=bool(env.has_grasped[0]),
                                diagnostics={k:float(v[0]) for k,v in env.last_diagnostics.items() if v.ndim==1})
                        # Ground truth supervision only; never part of sample or action.
                        from isaaclab.utils.math import quat_apply_inverse,quat_conjugate,quat_mul
                        from harvest_rl.logic import fruit_bounds
                        from harvest_rl.entry_aux import entry_truth
                        fruit=env._target_fruit();tcp_now,tcp_q=env._tcp()
                        local_center=quat_apply_inverse(tcp_q,env._grasp_center(fruit)-tcp_now)
                        rel_q=quat_mul(quat_conjugate(tcp_q),fruit.data.root_link_quat_w)
                        _,extent=fruit_bounds(torch.zeros_like(local_center),rel_q,env.settings)
                        entered=entry_truth(local_center,extent[:,0],env.robot.data.joint_pos[:,env.jids[-1]],env.settings.diameter)
                        from harvest_rl.entry_grasp import entry_gate
                        clearance,_=entry_gate(local_center,extent[:,0],env.robot.data.joint_pos[:,env.jids[-1]],torch.zeros_like(entered),env.settings.diameter)
                        entry_label=dict(version=2,ready=bool(entered[0]),open_clearance=bool(clearance[0]),
                            usable=bool(env.attached[0,env.assignment_slot]) and bool(target['valid']) and bool(sample['camera_valid'].any()),
                            scope='attached visible target; instantaneous center capture; not open clearance or hold',
                            local_center_m=local_center[0].cpu().tolist(),half_width_m=float(extent[0,0]))
                        phase('save_sample')
                        writer.append(sample,(label_action if label_action is not None else action)[0].cpu().numpy(),dict(
                            observation_geometry=dict(schema='arm_tcp_v1',tcp_arm_m=tcp_arm.tolist(),source='measured robot link/joint FK and fixed grasp-centre calibration; not fruit truth'),
                            dagger=dagger_note,stamp_s=stamp,target=target,raw_student_action=raw_action.tolist() if student else None,approach_prediction=approach_prediction,geometry_diagnostic=geometry_diagnostic,entry_label=entry_label,entry_prediction=entry_prediction,
                            expert_stage=int(env.expert_stage[0]) if hasattr(env,'expert_stage') else -99,initial_association_error_m=association_error,detections=records,
                            cameras={name:dict(raw_rgb_shape=list(f.rgb.shape),k=f.k.tolist(),arm_from_optical=f.arm_from_optical.tolist(),
                                **({key:capture[name][key] for key in ('frame_number','stamp_s','pose_stamp_s','capture_joint_rad','fk_max_error','raw_capture')} if deployment else {})) for name,f in frames.items()}))
                        phase('physics_step')
                        obs,_,_,_=wrapped.step(action)
                        if not torch.equal(env.actions,action):
                            raise RuntimeError('Recorded action differs from executed normalized command')
                        local+=1;steps+=1
                        if approach_prediction and approach_prediction['abort']:
                            status=approach_prediction['abort'];break
                        if approach_prediction and approach_prediction['ready']:
                            status='APPROACH_READY';break
                        if entry_aux and local%20==0:print('ENTRY_SHADOW',episode,local,entry_prediction,flush=True)
                        if trace:faulthandler.cancel_dump_traceback_later()
                        if local%20==0:
                            print('STUDENT_COLLECT',episode,'frames',local,'stage',int(env.expert_stage[0]) if hasattr(env,'expert_stage') else -99,'target_valid',target['valid'],flush=True)
                            if getattr(args,'eval_fruit_mass',None) is not None or getattr(args,'deployment_nine_gram',False):
                                keys=('gripper_q_rad','gripper_target_rad','close_action','fixed_force_N','moving_force_N','attached','fruit_speed_m_s','release_stop_s','valid_release','stop_zone_ok','stop_fruit_speed_ok','stop_tcp_speed_ok','stop_angular_ok','stop_stable_grip_ok','stop_all_ok')
                                print('TEACHER_CONTACT', {k:round(float(env.last_diagnostics[k][0]),5) for k in keys if k in env.last_diagnostics},flush=True)
                    if status not in ('TARGET_UNAVAILABLE','TARGET_ASSOCIATION_REJECTED','APPROACH_READY','TARGET_LOST','APPROACH_MISSED','APPROACH_TIMEOUT','ALIGNMENT_LOST','NO_REACHABLE_APPROACH','TARGET_MOVED','APPROACH_STALLED','TARGET_UNSTABLE'): status=env.assignment_status if env.assignment_status!='RUNNING' else 'CANCELLED'
                    if env.assignment_status=='RUNNING': env.cancel_target()
                    writer.finish(status,dict(target_valid_frames=valid_count,initial_selection=initial_selection,
                        dagger=dict(prefix_frames=dagger_prefix_count,takeover_reason=takeover,recovery_eligible=recovery_eligible,
                            recovery_succeeded=bool(recovering and recovery_eligible and status=='SUCCEEDED')) if dagger else None,
                        terminal_stage=int(env.expert_stage[0]) if hasattr(env,'expert_stage') else -99,
                        terminal_diagnostics={k:float(v[0]) for k,v in env.last_diagnostics.items() if v.ndim==1},
                        failure={k:float(v[0]) for k,v in env.last_diagnostics.items() if k.startswith('failure_')}))
                except BaseException:
                    if not writer.closed: writer.finish('ERROR')
                    raise
                finally:
                    if deployment:rig.reset()
                if trace:faulthandler.cancel_dump_traceback_later()
                manifest['episodes'].append(dict(episode=episode,status=status,samples=writer.count,target_valid_frames=valid_count));save()
                print('STUDENT_EPISODE',manifest['episodes'][-1],flush=True)
