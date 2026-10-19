"""Read-only constrained transport with bounded near-stop contact unloading."""
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
FINAL=ROOT/'runs/harvest_rl/teacher60_bridge_pull_20261011_183519.81Q1hV/teacher_final.pt'
FILES=['scripts/eval_teacher60_bridge_transport_unload_v2.py','scripts/analyze_teacher60_bridge_transport_unload_v2.py',
       'src/harvest_robot/harvest_rl/transport_contact_unload_v2.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_transport_unload_v2_env.py','scripts/eval_teacher60_bridge_transport_unload.py','scripts/analyze_teacher60_bridge_transport_unload.py',
       'src/harvest_robot/harvest_rl/transport_contact_unload.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_transport_unload_env.py','scripts/eval_teacher60_bridge_transport_constrained.py',
       'src/harvest_robot/harvest_rl/bridge_transport_constrained.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_transport_constrained_env.py','scripts/eval_teacher60_bridge_transport_path.py',
       'src/harvest_robot/harvest_rl/bridge_transport_path.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_transport_path_env.py','scripts/eval_teacher60_bridge_transport.py','scripts/analyze_teacher60_bridge_transport.py',
       'src/harvest_robot/harvest_rl/bridge_transport_60hz.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_transport_env.py','scripts/eval_teacher60_pull_guarded.py','src/harvest_robot/harvest_rl/bridge_pull_path.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_pull_risk_env.py',
       'src/harvest_robot/harvest_rl/teacher_bridge_pull_guarded_env.py',
       'src/harvest_robot/harvest_rl/bridge_pull_risk.py',
       'src/harvest_robot/harvest_rl/matched_pull_60hz.py']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,default=FINAL)
    parser.add_argument('--split',choices=['validation','test'],default='validation')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--execute',action='store_true')
    a=parser.parse_args()
    import torch
    from harvest_rl.bridge_pull_risk import RiskPullSpec
    from harvest_rl.bridge_pull_training import source_metadata,make_contract,training_settings
    from harvest_rl.teacher_asset_reference import sha
    from harvest_rl.grasp_handoff_60hz import contract_digest
    metadata,grasp_saved=source_metadata(GRASP)
    _,parent_contract=make_contract(metadata,PARENT)
    original_digest=contract_digest(parent_contract)
    saved=torch.load(a.checkpoint,map_location='cpu',weights_only=True)
    if saved.get('infos',{}).get('bridge_pull_contract_sha256')!=original_digest:
        parser.error('Checkpoint must match the frozen continuous bridge-pull training contract')
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
    seed={'validation':6042,'test':7042}[a.split]
    cfg=training_settings(metadata,seed);cfg.workspace_split='eval'
    output=(a.output or ROOT/'outputs/harvest_rl'/
        f'bridge_transport_unload2deg_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}').resolve()
    if output.exists():parser.error('Use a new output folder; omit --output for an automatic unique folder')
    plan=dict(mode='evaluate',learning=False,hardware_executed=False,control='guarded-pull-to-constrained-unload2deg-transport',
        split=a.split,seed=seed,num_envs=32,task=cfg.as_dict(),spec=contract['spec'],
        output=str(output),command=sys.argv,contract_sha256=contract_digest(contract),
        evaluation_checkpoint=str(a.checkpoint.resolve()),evaluation_checkpoint_sha256=sha(a.checkpoint),
        grasp_checkpoint=str(GRASP),pull_checkpoint=str(PARENT),controller=asdict(spec),
        bank_restore=False,production_selection_changed=False,training_gate_eligible=False,
        camera_streams_enabled=False)
    print('BRIDGE_TRANSPORT_PLAN',json.dumps(plan),flush=True)
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
        from harvest_rl.teacher_bridge_transport_unload_v2_env import TeacherBridgeTransportUnloadV2Env
        from harvest_rl.attachment_60hz_runtime import response6_runtime
        from harvest_rl.policy import teacher_config
        from harvest_rl.progress_normalization import install_grasp_progress_normalization
        from harvest_rl.followup_60hz import verify_source
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rsl_rl.runners import OnPolicyRunner
        source=metadata['source_run'];frame=np.asarray(source['current_base_to_policy_world'])
        rotation=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
        runtime=response6_runtime();plan['attachment_runtime']=runtime.__enter__()
        env=TeacherBridgeTransportUnloadV2Env(cfg,grasp_policy=None,transport_policy=None,path_spec=spec,domain=source['domain'],
            domain_stage=3,domain_split=a.split,num_envs=32,device='cuda:0',cameras=False,
            robot_usd=Path(source['current_asset']['usd']),robot_root_pose=(tuple(frame[:3,3]),tuple(rotation)),
            fruit_color_override=source['domain']['colors'],fruit_asset_cache=output/'fruit_assets',
            visual_scene=source['visual_scene_requested'])
        if abs(env.physics_dt-1/60)>1e-12 or abs(env.step_dt-.05)>1e-12:raise ValueError('60/20Hz changed')
        plan.update(actual_physics_dt_s=env.physics_dt,actual_policy_dt_s=env.step_dt,
            arm_contact_body_names=env.arm_contact.body_names,contact_recording_metadata=env.margin_sensor_metadata,
            controller_urdf_sha256=sha(ROOT/'outputs/harvest_rl/assets/harvest_training.urdf'))
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
        done=set();records=[];obs=wrapped.get_observations()
        with torch.inference_mode(),(output/'trace.jsonl').open('x') as trace,(output/'contact_points.jsonl').open('x') as contact:
            for step in range(env.max_episode_length*3+4):
                active=[i for i in range(32) if i not in done]
                obs,_,_,_=wrapped.step(policy(obs))
                snapshot=env.chain_snapshot;columns=sorted(snapshot)
                packed=torch.stack([snapshot[k].float() for k in columns],-1).cpu().tolist()
                trace.write(json.dumps(dict(time_s=(step+1)*env.step_dt,env_ids=active,columns=columns,rows=[packed[i] for i in active]))+'\n')
                contact.write(json.dumps(dict(time_s=(step+1)*env.step_dt,env_ids=active,
                    jaws={k:[v[i] for i in active] for k,v in env.chain_contacts.items()}))+'\n')
                for row in env.chain_episode_records:
                    i=row['env_id']
                    if i not in done:
                        done.add(i);records.append(dict(row,trial_id=i))
                        print('BRIDGE_TRANSPORT_EPISODE',i,row['success'],row['reasons'],flush=True)
                if step%20==0 or len(done)==32:
                    trace.flush();contact.flush()
                    print('BRIDGE_TRANSPORT_PROGRESS',round((step+1)*env.step_dt,2),len(done),'/32',
                          'success',sum(r['success'] for r in records),'learning=False',flush=True)
                if len(done)==32:break
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
        (output/'transport_handoffs.json').write_text(json.dumps(env.transport_events,indent=2)+'\n')
        plan.update(completed=True,source_still_matches=True,grasp_actor_unchanged=True,normalizers_unchanged=True)
        (output/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
        from analyze_teacher60_bridge_transport_unload_v2 import analyze
        report=analyze(output);(output/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
        print('BRIDGE_TRANSPORT_COMPLETE',report['success'],'/32',output,flush=True)
    except BaseException:
        failed=True
        import traceback
        (output/'error.txt').write_text(traceback.format_exc());raise
    finally:
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)
        if runtime is not None:runtime.__exit__(None,None,None)


if __name__=='__main__':main()
