"""Explicit native-pull transfer into the preserved full deposit controller."""
import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))
GRASP=ROOT/'runs/harvest_rl/teacher60_grasp_bridge_20261011_162738.9TsEHh/teacher_final.pt'
PARENT=ROOT/'runs/harvest_rl/teacher60_pull_response_20261011_131601.8TN7Vg/teacher_final.pt'
FINAL=ROOT/'runs/harvest_rl/teacher60_native_alignment_20261012_170952.RKKKIl/teacher_final.pt'
from eval_teacher60_harvest_chain import FILES as UPSTREAM_FILES
FILES=UPSTREAM_FILES+['scripts/eval_teacher60_motion_compare.py',
    'scripts/analyze_teacher60_motion_compare.py',
    'src/harvest_robot/harvest_rl/transport_motion_compare.py',
    'src/harvest_robot/harvest_rl/teacher_bridge_motion_compare_env.py',
    'scripts/eval_teacher60_height_v2.py', 'scripts/analyze_teacher60_height_v2.py',
    'src/harvest_robot/harvest_rl/placement_height_v2.py',
    'src/harvest_robot/harvest_rl/box_wall_contact.py',
    'src/harvest_robot/config/teacher60_placement_height_v2.json',
    'scripts/eval_teacher60_pressure.py','scripts/analyze_teacher60_pressure.py',
    'src/harvest_robot/harvest_rl/pressure_compare.py',
    'src/harvest_robot/harvest_rl/teacher_pressure_compare_env.py']


FILES += ['scripts/eval_teacher60_pull_stability.py', 'scripts/analyze_teacher60_pull_stability.py',
          'src/harvest_robot/harvest_rl/teacher_pull_stability_env.py']

FILES += ['scripts/eval_teacher60_settle_compliance.py', 'scripts/analyze_teacher60_settle_compliance.py']

FILES += ['scripts/analyze_teacher60_settle_compliance_v2.py', 'scripts/eval_teacher60_transport_posture.py',
          'scripts/analyze_teacher60_transport_posture.py',
          'src/harvest_robot/harvest_rl/transport_posture_escape.py',
          'src/harvest_robot/harvest_rl/teacher_transport_posture_env.py']

FILES += ['scripts/eval_teacher60_floor_guarded.py','scripts/analyze_teacher60_floor_guarded.py',
          'src/harvest_robot/harvest_rl/floor_unified.py',
          'src/harvest_robot/harvest_rl/teacher_native_floor_guarded_env.py',
          'scripts/eval_teacher60_settle_v4.py','scripts/analyze_teacher60_settle_v4.py',
          'src/harvest_robot/harvest_rl/floor_collision_v4.py',
          'src/harvest_robot/harvest_rl/floor_collision_buffered.py',
          'src/harvest_robot/harvest_rl/floor_override_audit_v4.py',
          'src/harvest_robot/harvest_rl/floor_override_audit_v3.py',
          'src/harvest_robot/harvest_rl/teacher_native_floor_unified_env.py',
          'scripts/eval_teacher60_settle_v2.py','scripts/analyze_teacher60_settle_v2.py',
          'src/harvest_robot/harvest_rl/settle_gain_v4.py',
          'src/harvest_robot/harvest_rl/teacher_native_settle_v4_env.py',
          'scripts/eval_teacher60_native_chain.py','scripts/analyze_teacher60_native_chain.py',
          'src/harvest_robot/harvest_rl/settle_gate_v2.py',
          'src/harvest_robot/harvest_rl/teacher_native_settle_v2_env.py',
          'src/harvest_robot/harvest_rl/floor_geometry_audit.py',
          'scripts/eval_teacher60_floor_unified.py','scripts/eval_teacher60_native_contact_chain.py','scripts/analyze_teacher60_floor_unified.py',
          'src/harvest_robot/harvest_rl/native_policy_transfer.py']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pressure-goal',type=float,default=0.,help='Per jaw normal feedback trigger N;0 baseline')
    parser.add_argument('--pressure-reference',type=Path,default=None)
    parser.add_argument('--legacy-placement',action='store_true',help='Diagnosis only: preserve original lower height')
    parser.add_argument('--transport-speed',type=float,default=.035,help='TCP command cap in m/s, <=.035')
    parser.add_argument('--orientation-length',type=float,default=.02,help='Rotation weighting in m, .02..04')
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--policy-role',choices=['warm','trained'],default='trained')
    parser.add_argument('--opening-rate',type=float,default=.3,help='Jaw target rad/s after verified stop')
    parser.add_argument('--deposit-timeout',type=float,default=6.)
    parser.add_argument('--baseline',type=Path,help='Verified original stop-only evaluation, same split')
    parser.add_argument('--split',choices=['train','validation','test'],default='validation')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--stability-mode',choices=['baseline','pause','early','axial'],default='pause')
    parser.add_argument('--settle-gain',type=float,default=1.)
    parser.add_argument('--floor-mode',choices=['unified'],default='unified')
    parser.add_argument('--posture-mode',choices=['off','position','null','center'],default='position')
    a=parser.parse_args();a.settle_goal_limit=.01
    if a.legacy_placement:parser.error('Native-alignment chain uses height-v2 explicitly')
    if (a.stability_mode!='pause' or a.settle_gain!=1. or a.posture_mode!='position'
            or a.transport_speed!=.035 or a.orientation_length!=.02
            or a.opening_rate!=.3 or a.deposit_timeout!=6.):
        parser.error('Native-contact evaluation preserves the selected full-chain controls')
    chosen_output=(a.output or ROOT/'outputs/harvest_rl'/f'contact_chain_{a.policy_role}_{a.split}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}').resolve()
    a.pressure_reference=(a.pressure_reference or chosen_output).resolve()
    if not .5 <= a.settle_gain <= 2:parser.error('Settle gain must be .5..2 Nm/rad')
    if a.pressure_goal != 0:parser.error('This comparison preserves original pressure')
    from harvest_rl.transport_motion_compare import validate_motion
    try:validate_motion(a.transport_speed,a.orientation_length)
    except ValueError as exc:parser.error(str(exc))
    if not 0<a.opening_rate<=1.2 or a.deposit_timeout<2:parser.error('Requires opening(0,1.2]rad/s and timeout>=2s')
    from harvest_rl.pressure_compare import PressureSpec
    pressure=PressureSpec(a.pressure_goal).validate()
    a.hold_stiffness=a.settle_gain;a.gain_ramp=1.
    baseline=(a.baseline or ROOT/'outputs/harvest_rl/transport_servo_20261011'/f'{a.split}_settle').resolve()
    from analyze_teacher60_transport_gain import analyze as audit_stop
    original_stop=audit_stop(baseline)
    baseline_run=json.loads((baseline/'run.json').read_text())
    if baseline_run['split']!=a.split:parser.error('Baseline split differs')
    import torch
    from harvest_rl.bridge_pull_risk import RiskPullSpec
    from harvest_rl.bridge_pull_training import source_metadata,make_contract,training_settings
    from harvest_rl.teacher_asset_reference import sha
    from harvest_rl.grasp_handoff_60hz import contract_digest
    metadata,grasp_saved=source_metadata(GRASP)
    _,parent_contract=make_contract(metadata,PARENT)
    original_digest=contract_digest(parent_contract)
    from harvest_rl.native_contact_training import verify_policy
    saved,native_policy=verify_policy(metadata,PARENT,a.checkpoint,a.policy_role)
    profile=json.loads((ROOT/'src/harvest_robot/config/teacher_ramp_20260930.json').read_text())
    binding=profile['checkpoints']['TRANSPORT_CKPT'];transport_path=ROOT/binding['path']
    transport_run=transport_path.parent/'run.json'
    if sha(transport_path)!=binding['sha256'] or sha(transport_run)!=binding['run_sha256']:
        raise ValueError('Frozen transport checkpoint/run hash changed')
    transport_metadata=json.loads(transport_run.read_text())['task']
    if transport_metadata['task']!='transport':raise ValueError('Expected transport actor')
    transport_saved=torch.load(transport_path,map_location='cpu',weights_only=True)
    spec=RiskPullSpec(axial=True,hold_after_detach=True)
    contract=dict(parent_contract,schema='teacher60_guarded_transport_transfer_v1',
        parent_contract_sha256=original_digest,controller=asdict(spec),
        comparison_only=True,training_gate_eligible=False,learning=False,
        transport=dict(checkpoint=str(transport_path),checkpoint_sha256=sha(transport_path),run_sha256=sha(transport_run),
            original_task=transport_metadata,trained_physics_hz=480,trained_mass_kg=.035,
            explicit_transfer=True,normalization='original empirical, not grasp progress identity',
            observation='Teacher82 raw quaternion, one target slot0, stage-local time',
            arm_scale_start=.25,arm_ramp_s=3.,jaw='Near stationary box waypoint only: force>.5N, instantaneous fruit speed>.2m/s, bounded opening<=2deg at.5deg/s; no reclose',
            transport_control='Cartesian clearance30mm -X, box center, predictedTCP<=35mm/s joint<=.3rad/s',
            transport_actor_controls_arm=False,
            joint_target_guard='active-set original joint limits, elbow target upper1.45rad; no URDF/physics override',
            success='original current box stop geometry,0.3s, actual bilateral/center/slip, speed<=.05m/s'),
        detached_arm_hold='Ends when actual0.5s retained pull succeeds; transport acts on next tick',
        files={**parent_contract['files'],**{f:sha(ROOT/f) for f in FILES}})
    contract['native_policy']=native_policy
    contract['files'].update(native_policy['native_training_contract']['files'])
    contract['motion_comparison']=dict(speed_m_s=a.transport_speed,orientation_length_m=a.orientation_length,
        scope='After actual0.5s pull retention, arm targets only; original ramp, bounds and timeout',
        no_autoadoption=True,no_learning=True)
    contract['transport']['transport_control']=f'Cartesian clearance30mm -X, box center, predictedTCP<={a.transport_speed}m/s, rotation weight{a.orientation_length}m, joint<=.3rad/s'
    contract['deposit']=dict(controller='Stored arm targets, jaw bounded opening only after actual0.3s stop',
        opening_rate_rad_s=a.opening_rate,timeout_s=a.deposit_timeout,
        first_open='One authorized removal of closing preload; no later measured-q rebase',
        actuator='Freeze actual jaw gain at stop; original effort/damping/velocity; restore8 before reset',
        success='Actual mesh incl stem inside original box/tolerances, SDK speed<.12m/s, both jaws<.08N, detached/retained and0.6s physical dwell; original failures',
        legacy_place_actor_used=False,stop_baseline=str(baseline),
        stop_contract_sha256=baseline_run['contract_sha256'])
    contract['transport']['loaded_jaw_gain_Nm_rad']=a.hold_stiffness
    contract['transport']['gain_ramp_s']=a.gain_ramp
    contract['transport']['actuator_change']='Only after6 consecutive measured20Hz stationary box plateau ticks: zone, waypoint error<5mm, TCP/poseCOM<=20mm/s, SDKCOM>.2m/s, bilateral force>.5N, center/slip qualified;1s8->2 ramp, restore8 at reset; original effort/damping/velocity unchanged'
    seed={'train':5042,'validation':6042,'test':7042}[a.split]
    cfg=training_settings(metadata,seed);cfg.workspace_split='eval'
    from harvest_rl.placement_height_v2 import height_settings
    cfg,placement=height_settings(cfg,a.legacy_placement)
    from harvest_rl.grasp_handoff_60hz import physical_signature
    contract['placement_height_v2']=placement
    contract['current_evaluation_signature']=physical_signature(cfg.as_dict())
    contract['placement_transfer']='Frozen learned weights/normalizers; explicitly changed reset domain only. Old training/PPO certification not reused.'
    contract['pressure_comparison']=dict(goal_N=pressure.goal_N,extra_close_deg=pressure.extra_close_deg,rate_deg_s=pressure.rate_deg_s,scope='Original4deg first; attached qualified bridge/pull only adds reserve; retain target through0.5s retention; unchanged transport/stop/release',reference=str(a.pressure_reference.resolve()),effort_Nm=.5,no_learning=True)
    contract['box_contact_recording']='Read-only target fruit -> fixed base contacts, loaded points labelled by actual four wall Cube bounds. Original control sensors unchanged.'
    contract['pull_stability']=dict(mode=a.stability_mode,early_lateral_m=.002,early_rotation_rad=.10,
        contact_loss='Pause previous arm targets while qualification absent; original timeout remains',
        reference=str(a.pressure_reference.resolve()),no_learning=True)
    contract['settle_compliance']=dict(final_gain_Nm_rad=a.settle_gain,trigger='Six consecutive qualified stationary box plateau ticks',goal_limit_m=a.settle_goal_limit,original_stop_success_gates=True)
    contract['floor_collision_override']=dict(mode=a.floor_mode,added_shapes=1,disabled_shapes=8,added_rigid_bodies=0,original_usd_modified=False,visible_top_z_m=.501,depth_m=.05,contact_offset_m=.04,rest_offset_m=0.,explicit_physics_transfer=True)
    if a.floor_mode=='buffered':contract['floor_collision_override'].update(contact_offset_m=.04,rest_offset_m=0.)
    contract['settle_compliance']['ramp_guard']='Decrease<=7Nm/rad/s only if qualified center/slip<8mm, min jaw force>.5N only if center/slip<6mm, else>1N, actual TCP/pose<=20mm/s, SDK>.18m/s and goal<10mm; freeze otherwise, never increase'
    contract['transport']['actuator_change']=contract['transport']['actuator_change'].replace('waypoint error<5mm',f'waypoint error<{a.settle_goal_limit*1000:g}mm')
    contract['transport']['actuator_change']=contract['transport']['actuator_change'].replace('8->2',f'8->{a.settle_gain}')
    contract['posture_comparison']=dict(mode=a.posture_mode,stall_s=.5,angle_limit_rad=.6,angular_speed_limit_rad_s=.08,center_request_path_m=.002,no_learning=True)
    output=chosen_output
    if output.exists():parser.error('Use a new output folder; omit --output for an automatic unique folder')
    plan=dict(mode='evaluate',learning=False,hardware_executed=False,control='pressure-comparison-height-v2-deposit',pressure_comparison=contract['pressure_comparison'],placement_height_v2=placement,transport_speed_m_s=a.transport_speed,orientation_length_m=a.orientation_length,opening_rate_rad_s=a.opening_rate,deposit_timeout_s=a.deposit_timeout,stop_baseline=str(baseline),loaded_jaw_gain_Nm_rad=a.hold_stiffness,gain_ramp_s=a.gain_ramp,
        split=a.split,seed=seed,num_envs=32,task=cfg.as_dict(),spec=contract['spec'],
        output=str(output),command=sys.argv,contract_sha256=contract_digest(contract),
        evaluation_checkpoint=str(a.checkpoint.resolve()),evaluation_checkpoint_sha256=sha(a.checkpoint),
        grasp_checkpoint=str(GRASP),pull_checkpoint=str(PARENT),controller=asdict(spec),
        bank_restore=False,production_selection_changed=False,training_gate_eligible=False,
        camera_streams_enabled=False)
    plan['floor_collision_override']=contract['floor_collision_override']
    plan['native_policy']=native_policy
    plan['posture_comparison']=contract['posture_comparison']
    plan['settle_compliance']=contract['settle_compliance']
    plan['pull_stability']=contract['pull_stability']
    print('TEACHER60_STABILITY_PLAN',json.dumps(plan),flush=True)
    if not a.execute:return
    output.mkdir(parents=True)
    (output/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
    (output/'bridge_pull_contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    for f in contract['files']:
        target=output/'source_snapshot'/f;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/f,target)
    from isaaclab.app import AppLauncher
    app=AppLauncher(headless=a.headless,device='cuda:0',kit_args='--/plugins/carb.tasking.plugin/threadCount=1').app
    env=runtime=None;failed=False
    try:
        import numpy as np
        from scipy.spatial.transform import Rotation
        from harvest_rl.teacher_native_floor_unified_env import TeacherNativeFloorUnifiedEnv
        from harvest_rl.attachment_60hz_runtime import response6_runtime
        from harvest_rl.policy import teacher_config
        from harvest_rl.progress_normalization import install_grasp_progress_normalization
        from harvest_rl.followup_60hz import verify_source
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rsl_rl.runners import OnPolicyRunner
        source=metadata['source_run'];frame=np.asarray(source['current_base_to_policy_world'])
        rotation=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
        runtime=response6_runtime();plan['attachment_runtime']=runtime.__enter__()
        env=TeacherNativeFloorUnifiedEnv(cfg,floor_mode=a.floor_mode,posture_mode=a.posture_mode,stability_mode=a.stability_mode,pressure_spec=pressure,transport_speed_m_s=a.transport_speed,orientation_length_m=a.orientation_length,opening_rate_rad_s=a.opening_rate,deposit_timeout_s=a.deposit_timeout,hold_stiffness_Nm_rad=a.hold_stiffness,gain_ramp_s=a.gain_ramp,grasp_policy=None,transport_policy=None,path_spec=spec,domain=source['domain'],
            domain_stage=3,domain_split=a.split,num_envs=32,device='cuda:0',cameras=False,
            robot_usd=Path(source['current_asset']['usd']),robot_root_pose=(tuple(frame[:3,3]),tuple(rotation)),
            fruit_color_override=source['domain']['colors'],fruit_asset_cache=output/'fruit_assets',
            visual_scene=source['visual_scene_requested'])
        if abs(env.physics_dt-1/60)>1e-12 or abs(env.step_dt-.05)>1e-12:raise ValueError('60/20Hz changed')
        plan.update(actual_physics_dt_s=env.physics_dt,actual_policy_dt_s=env.step_dt,
            arm_contact_body_names=env.arm_contact.body_names,contact_recording_metadata=env.margin_sensor_metadata,
            controller_urdf_sha256=sha(ROOT/'outputs/harvest_rl/assets/harvest_training.urdf'))
        from harvest_rl.floor_unified import audit_floor_clones
        (output/'floor_clone_audit.json').write_text(json.dumps(audit_floor_clones(env),indent=2)+'\n')
        (output/'floor_override.json').write_text(json.dumps(env.floor_override,indent=2)+'\n')
        from harvest_rl.floor_geometry_audit import floor_geometry
        (output/'floor_geometry.json').write_text(json.dumps(floor_geometry(env.sim.stage,env.scene.env_origins[0].cpu().tolist()),indent=2)+'\n')
        wrapped=RslRlVecEnvWrapper(env,clip_actions=None)
        def runner_for(state,progress_identity=True):
            runner=OnPolicyRunner(wrapped,teacher_config(),log_dir=None,device='cuda:0')
            if progress_identity:install_grasp_progress_normalization(runner.alg.policy)
            runner.alg.policy.load_state_dict(state['model_state_dict'])
            for parameter in runner.alg.policy.parameters():parameter.requires_grad_(False)
            return runner
        grasp=runner_for(grasp_saved);pull=runner_for(saved);transport=runner_for(transport_saved,False)
        env.grasp_policy=grasp.get_inference_policy(device='cuda:0')
        policy=pull.get_inference_policy(device='cuda:0')
        env.transport_policy=transport.get_inference_policy(device='cuda:0')
        before=[{k:v.clone() for k,v in r.alg.policy.state_dict().items()} for r in [grasp,pull,transport]]
        wrapped.reset();wrapped.reset();env.domain_evaluation=True;env.diagnostic_contacts=True
        (output/'initial_samples.json').write_text(json.dumps(env.domain_samples.cpu().tolist(),indent=2)+'\n')
        (output/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
        from harvest_rl.transport_substeps import SubstepRecorder
        recorder=SubstepRecorder(env)
        from harvest_rl.box_wall_contact import BoxWallRecorder
        box_recorder=BoxWallRecorder(env)
        (output/'box_wall_geometry.json').write_text(json.dumps(box_recorder.walls,indent=2)+'\n')
        done=set();records=[];obs=wrapped.get_observations()
        with torch.inference_mode(),(output/'trace.jsonl').open('x') as trace,(output/'contact_points.jsonl').open('x') as contact,(output/'substeps.jsonl').open('x') as substeps,(output/'box_contacts.jsonl').open('x') as boxtrace:
            for step in range(env.max_episode_length*3+4):
                active=[i for i in range(32) if i not in done]
                obs,_,_,_=wrapped.step(policy(obs))
                for frame_record in recorder.drain(active):substeps.write(json.dumps(frame_record)+'\n')
                for box_record in box_recorder.drain(active):boxtrace.write(json.dumps(box_record)+'\n')
                snapshot=env.chain_snapshot;columns=sorted(snapshot)
                packed=torch.stack([snapshot[k].float() for k in columns],-1).cpu().tolist()
                trace.write(json.dumps(dict(time_s=(step+1)*env.step_dt,env_ids=active,columns=columns,rows=[packed[i] for i in active]))+'\n')
                contact.write(json.dumps(dict(time_s=(step+1)*env.step_dt,env_ids=active,
                    jaws={k:[v[i] for i in active] for k,v in env.chain_contacts.items()}))+'\n')
                for row in env.chain_episode_records:
                    i=row['env_id']
                    if i not in done:
                        done.add(i);records.append(dict(row,trial_id=i))
                        print('TEACHER60_PRESSURE_EPISODE',i,row['success'],row['reasons'],flush=True)
                if step%20==0 or len(done)==32:
                    trace.flush();contact.flush();substeps.flush();boxtrace.flush()
                    print('TEACHER60_PRESSURE_PROGRESS',round((step+1)*env.step_dt,2),len(done),'/32',
                          'success',sum(r['success'] for r in records),'learning=False',flush=True)
                if len(done)==32:break
        box_recorder.close();recorder.close()
        if len(done)!=32:raise ValueError('Incomplete assigned evaluation')
        records.sort(key=lambda row:row['trial_id'])
        (output/'evaluation.json').write_text(json.dumps(dict(count=32,success=sum(r['success'] for r in records),
            episodes=records,learning=False,split=a.split),indent=2)+'\n')
        if any(not torch.equal(v,r.alg.policy.state_dict()[k]) for old,r in zip(before,[grasp,pull,transport]) for k,v in old.items()):
            raise ValueError('Inference mutated actor/normalizer weights')
        verify_source(metadata)
        for f,h in contract['files'].items():
            if sha(ROOT/f)!=h:raise ValueError('Comparison source changed: '+f)
        if sha(a.checkpoint)!=plan['evaluation_checkpoint_sha256']:raise ValueError('Checkpoint changed')
        if sha(ROOT/'outputs/harvest_rl/assets/harvest_training.urdf')!=plan['controller_urdf_sha256']:
            raise ValueError('Controller FK asset changed')
        if sha(transport_path)!=binding['sha256'] or sha(transport_run)!=binding['run_sha256']:
            raise ValueError('Transport weights or metadata changed')
        (output/'deposit_handoffs.json').write_text(json.dumps(env.deposit_events,indent=2)+'\n')
        (output/'transport_handoffs.json').write_text(json.dumps(env.transport_events,indent=2)+'\n')
        plan.update(completed=True,source_still_matches=True,grasp_actor_unchanged=True,normalizers_unchanged=True)
        (output/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
        from analyze_teacher60_native_contact_chain import analyze
        report=analyze(output);(output/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
        print('TEACHER60_PRESSURE_COMPLETE',report['success'],'/32',output,flush=True)
        print('TEACHER60_PHASE_RESULTS',json.dumps(report['classification_counts']),flush=True)
    except BaseException:
        failed=True
        import traceback
        (output/'error.txt').write_text(traceback.format_exc());raise
    finally:
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)
        if runtime is not None:runtime.__exit__(None,None,None)


if __name__=='__main__':main()
