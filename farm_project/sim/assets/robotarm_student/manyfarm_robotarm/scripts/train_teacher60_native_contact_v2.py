"""Versioned native-pull alignment refinement from the latest continuous final.

Plan by default. prepare/evaluate are inference only. train --execute is the
only learning path; it requires a matching train preflight report.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))
GRASP=ROOT/'runs/harvest_rl/teacher60_grasp_bridge_20261011_162738.9TsEHh/teacher_final.pt'
PULL=ROOT/'runs/harvest_rl/teacher60_pull_response_20261011_131601.8TN7Vg/teacher_final.pt'
WARM=ROOT/'runs/harvest_rl/teacher60_native_alignment_20261012_170952.RKKKIl/teacher_final.pt'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','evaluate','train'])
    p.add_argument('--grasp-checkpoint',type=Path,default=GRASP)
    p.add_argument('--pull-checkpoint',type=Path,default=PULL)
    p.add_argument('--warm-checkpoint',type=Path,default=WARM)
    p.add_argument('--resume-checkpoint',type=Path)
    p.add_argument('--evaluate-checkpoint',type=Path)
    p.add_argument('--preflight',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--num-envs',type=int,default=32)
    p.add_argument('--iterations',type=int,default=300)
    p.add_argument('--split',choices=['train','validation','test'])
    p.add_argument('--seed',type=int)
    p.add_argument('--headless',action='store_true')
    p.add_argument('--execute',action='store_true')
    a=p.parse_args()
    a.split=a.split or ('validation' if a.mode=='evaluate' else 'train')
    if a.mode!='evaluate' and a.split!='train':p.error('prepare/train must use train split; no validation/test training')
    if min(a.num_envs,a.iterations)<1:p.error('Positive environment/iteration counts required')
    if a.resume_checkpoint and a.mode!='train':p.error('Resume is a train option only')
    if a.evaluate_checkpoint and a.mode!='evaluate':p.error('A trained checkpoint is an evaluation option only')
    if a.mode!='train' and a.num_envs>128:p.error('Read-only preparation/evaluation is limited to128 environments')
    from harvest_rl.bridge_pull_training import source_metadata
    from harvest_rl.native_contact_v2_training import make_contract,training_settings,FILES
    from harvest_rl.native_contact_refine_v2 import SPEC
    from dataclasses import asdict
    from harvest_rl.grasp_handoff_60hz import contract_digest
    from harvest_rl.teacher_asset_reference import sha
    import torch
    print('VERIFY_SOURCE latest model, frozen assets and selected floor; no simulator started yet',flush=True)
    metadata,grasp_saved=source_metadata(a.grasp_checkpoint)
    pull_saved,contract=make_contract(metadata,a.pull_checkpoint,a.warm_checkpoint)
    digest=contract_digest(contract)
    seed=a.seed if a.seed is not None else {'train':5042,'validation':6042,'test':7042}[a.split]
    cfg=training_settings(metadata,seed);cfg.workspace_split='train' if a.split=='train' else 'eval'
    out=(a.output or ROOT/('runs/harvest_rl' if a.mode=='train' else 'outputs/harvest_rl')/
         f'native_contact_v2_{a.mode}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}').resolve()
    if out.exists():p.error('Use a new output folder; omit --output for an automatic unique folder')
    resume=None
    evaluated=None
    if a.resume_checkpoint:
        resume=torch.load(a.resume_checkpoint,map_location='cpu',weights_only=True)
        if (resume.get('infos',{}).get('bridge_pull_contract_sha256')!=digest
                or resume['infos']['seed']!=seed):p.error('Resume contract/seed mismatch')
    if a.evaluate_checkpoint:
        evaluated=torch.load(a.evaluate_checkpoint,map_location='cpu',weights_only=True)
        if evaluated.get('infos',{}).get('bridge_pull_contract_sha256')!=digest:
            p.error('Evaluated model does not match the continuous training contract')
    preflight=None
    if a.mode=='train' and a.execute:
        if not a.preflight:p.error('Training requires the matching train preparation.json via --preflight')
        preflight=json.loads(a.preflight.read_text())
        if (not preflight.get('passed') or preflight.get('split')!='train' or preflight.get('learning') is not False
                or preflight.get('optimizer_updates')!=0 or preflight.get('contract_sha256')!=digest
                or not preflight.get('masked_returns_checked') or not preflight.get('normalizers_unchanged')
                or not preflight.get('floor_all_clones_verified') or not preflight.get('reward_audit_passed')
                or not preflight.get('bias_training') or preflight.get('seed')!=seed):
            p.error('Preflight is incomplete or from another source/control contract')
        prior=json.loads((a.preflight.parent/'run.json').read_text())
        if not prior.get('completed') or not prior.get('source_still_matches') or prior['mode']!='prepare':
            p.error('Preflight run did not complete source verification')
        for name,h in preflight['artifacts'].items():
            if sha(a.preflight.parent/name)!=h:p.error('Preflight artifact changed: '+name)
    plan=dict(mode=a.mode,learning=a.mode=='train' and a.execute,hardware_executed=False,
        command=sys.argv,output=str(out),split=a.split,seed=seed,num_envs=a.num_envs,
        planned_iterations=a.iterations,task=cfg.as_dict(),contract_sha256=digest,
        grasp_checkpoint=str(a.grasp_checkpoint.resolve()),pull_checkpoint=str(a.pull_checkpoint.resolve()),
        resume_checkpoint=str(a.resume_checkpoint.resolve()) if a.resume_checkpoint else None,
        evaluation_checkpoint=str(a.evaluate_checkpoint.resolve()) if a.evaluate_checkpoint else None,
        evaluation_checkpoint_sha256=sha(a.evaluate_checkpoint) if a.evaluate_checkpoint else None,
        optimizer_resume=bool(resume),world_resume='HOME reset; physical scene is not resumed',
        preflight=str(a.preflight.resolve()) if a.preflight else None,
        preflight_sha256=sha(a.preflight) if a.preflight else None,
        baseline_reference=contract['baseline_artifacts'],
        floor_collision_override=contract['floor_collision_override'],
        contact_refine=asdict(SPEC),bias_training=a.mode in ('prepare','train'),
        camera_streams_enabled=False,domain_stage=3,bank_restore=False,
        production_selection_changed=False,spec=contract['spec'],alignment=contract['alignment'],
        warm_checkpoint=str(a.warm_checkpoint.resolve()),warm_checkpoint_sha256=sha(a.warm_checkpoint),
        optimizer_transfer=False)
    print('BRIDGE_PULL_PLAN',json.dumps(plan),flush=True)
    if not a.execute:return
    out.mkdir(parents=True)
    (out/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'bridge_pull_contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    for name in contract['files']:
        dst=out/'source_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)
    from isaaclab.app import AppLauncher
    app=AppLauncher(headless=a.headless,device='cuda:0',kit_args='--/plugins/carb.tasking.plugin/threadCount=1').app
    env=runtime=None;failed=False
    try:
        import numpy as np
        from scipy.spatial.transform import Rotation
        from harvest_rl.teacher_native_contact_v2_env import TeacherNativeContactV2Env
        from harvest_rl.bridge_pull_risk import RiskPullSpec
        from harvest_rl.attachment_60hz_runtime import response6_runtime
        from harvest_rl.policy import teacher_config
        from harvest_rl.progress_normalization import install_grasp_progress_normalization
        from harvest_rl.bridge_pull_ppo import BridgePullPPO
        from harvest_rl.followup_60hz import verify_source
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rsl_rl.runners import OnPolicyRunner
        source=metadata['source_run'];frame=np.asarray(source['current_base_to_policy_world'])
        rot=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
        runtime=response6_runtime();plan['attachment_runtime']=runtime.__enter__()
        env=TeacherNativeContactV2Env(cfg,bias_training=a.mode in ('prepare','train'),path_spec=RiskPullSpec(axial=True,hold_after_detach=True),grasp_policy=None,domain=source['domain'],domain_stage=3,
            domain_split=a.split,num_envs=a.num_envs,device='cuda:0',cameras=False,
            robot_usd=Path(source['current_asset']['usd']),robot_root_pose=(tuple(frame[:3,3]),tuple(rot)),
            fruit_color_override=source['domain']['colors'],fruit_asset_cache=out/'fruit_assets',
            visual_scene=source['visual_scene_requested'])
        if abs(env.physics_dt-1/60)>1e-12 or abs(env.step_dt-.05)>1e-12:raise ValueError('Actual60/20Hz mismatch')
        plan.update(actual_physics_dt_s=env.physics_dt,actual_policy_dt_s=env.step_dt,
                    arm_contact_body_names=env.arm_contact.body_names,
                    contact_recording_metadata=env.margin_sensor_metadata)
        from harvest_rl.floor_unified import audit_floor_clones
        floor_audit=audit_floor_clones(env)
        (out/'floor_clone_audit.json').write_text(json.dumps(floor_audit,indent=2)+'\n')
        (out/'floor_override.json').write_text(json.dumps(env.floor_override,indent=2)+'\n')
        plan['priority_bank_ids']=env.priority_bank_ids
        plan['train_bank_end_exclusive']=env.train_bank_end_exclusive
        wrapped=RslRlVecEnvWrapper(env,clip_actions=None)
        frozen=OnPolicyRunner(wrapped,teacher_config(),log_dir=None,device='cuda:0')
        install_grasp_progress_normalization(frozen.alg.policy)
        frozen.alg.policy.load_state_dict(grasp_saved['model_state_dict'])
        env.grasp_policy=frozen.get_inference_policy(device='cuda:0')
        for param in frozen.alg.policy.parameters():param.requires_grad_(False)
        class PullRunner(OnPolicyRunner):
            def _construct_algorithm(self,obs):
                parent=super()._construct_algorithm(obs)
                alg=BridgePullPPO(parent.policy,device=self.device,**self.alg_cfg,multi_gpu_cfg=self.multi_gpu_cfg)
                alg.init_storage('rl',self.env.num_envs,self.num_steps_per_env,obs,[self.env.num_actions])
                alg.bind(env);return alg
            def save(self,path,infos=None):
                super().save(path,dict(bridge_pull_contract_sha256=digest,seed=seed,
                    completed_iteration=self.current_learning_iteration+1,domain_state=env.domain_state(),
                    grasp_actor_frozen=True,normalizers_frozen=True,pull_arms_only=True))
            def log(self,locs,*args,**kwargs):
                super().log(locs,*args,**kwargs)
                recent=env.chain_history;handoffs=sum(x['handoff'] for x in recent);success=sum(x['success'] for x in recent)
                priority=[r for r in recent if int(r['sample'][0]) in env.priority_bank_ids]
                priority_handoffs=sum(r['handoff'] for r in priority)
                priority_success=sum(r['success'] for r in priority)
                print('CHAIN_PROGRESS',json.dumps(dict(iteration=locs['it']+1,
                    recent_episodes=len(recent),recent_handoffs=handoffs,recent_success=success,
                    success_rate=success/max(1,len(recent)),pull_success_rate=success/max(1,handoffs),
                    early_contact_loss_rate=sum(x['early_contact_loss'] for x in recent)/max(1,handoffs),
                    priority_episodes=len(priority),priority_handoffs=priority_handoffs,
                    priority_pull_success_rate=priority_success/max(1,priority_handoffs),
                    active_samples=locs['loss_dict']['active_samples'],learning=True)),flush=True)
        config=teacher_config();config['seed']=seed
        config['algorithm']['learning_rate']=5e-5;config['algorithm']['entropy_coef']=.001
        config['save_interval']=50
        runner=PullRunner(wrapped,config,str(out) if a.mode=='train' else None,device='cuda:0')
        install_grasp_progress_normalization(runner.alg.policy)
        runner.alg.policy.load_state_dict((resume or evaluated or pull_saved)['model_state_dict'])
        if resume:
            runner.alg.optimizer.load_state_dict(resume['optimizer_state_dict'])
            runner.current_learning_iteration=resume['infos']['completed_iteration']
            runner.alg.learning_rate=runner.alg.optimizer.param_groups[0]['lr']
            env.restore_domain_state(resume['infos']['domain_state'])
        elif a.mode in ('prepare','train'):
            with torch.no_grad():runner.alg.policy.std[:5].fill_(SPEC.exploration_std)
        before={k:v.clone() for k,v in runner.alg.policy.state_dict().items()}
        frozen_before={k:v.clone() for k,v in frozen.alg.policy.state_dict().items()}
        wrapped.reset();wrapped.reset();env.domain_evaluation=a.mode!='train'
        (out/'initial_samples.json').write_text(json.dumps(env.domain_samples.cpu().tolist(),indent=2)+'\n')
        (out/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
        if a.mode=='train':
            runner.learn(num_learning_iterations=a.iterations,init_at_random_ep_len=False)
            runner.save(str(out/'teacher_final.pt'))
        else:
            env.diagnostic_contacts=True
            obs=wrapped.get_observations();done=set();records=[];active_samples=0;checked=False
            policy=runner.get_inference_policy(device='cuda:0')
            with torch.inference_mode(),(out/'trace.jsonl').open('x') as trace,(out/'contact_points.jsonl').open('x') as contact:
                for step in range(env.max_episode_length*2+4):
                    active=[i for i in range(a.num_envs) if i not in done]
                    actions=runner.alg.act(obs) if a.mode=='prepare' else policy(obs)
                    obs,reward,ended,extras=wrapped.step(actions)
                    if a.mode=='prepare':
                        runner.alg.process_env_step(obs,reward,ended,extras)
                        active_samples+=int(runner.alg.before.sum())
                        if runner.alg.storage.step==runner.num_steps_per_env:
                            runner.alg.compute_returns(obs)
                            if not torch.isfinite(runner.alg.storage.returns).all():raise ValueError('Nonfinite masked returns')
                            if runner.alg.storage.returns[~runner.alg.active].abs().any():raise ValueError('HOME/bridge leaked into PPO returns')
                            checked=True;runner.alg.storage.clear();runner.alg.active.zero_()
                    d=env.chain_snapshot;columns=sorted(d)
                    packed=torch.stack([d[k].float() for k in columns],-1).cpu().tolist()
                    trace.write(json.dumps(dict(time_s=(step+1)*env.step_dt,env_ids=active,columns=columns,rows=[packed[i] for i in active]))+'\n')
                    contact.write(json.dumps(dict(time_s=(step+1)*env.step_dt,env_ids=active,
                        jaws={k:[v[i] for i in active] for k,v in env.chain_contacts.items()}))+'\n')
                    for row in env.chain_episode_records:
                        i=row['env_id']
                        if i in done:continue
                        done.add(i);records.append(dict(row,trial_id=i))
                        print('CHAIN_EPISODE',i,row['success'],row['reasons'],flush=True)
                    if step%20==0 or len(done)==a.num_envs:
                        trace.flush();contact.flush()
                        print('CHAIN_PROGRESS',round((step+1)*env.step_dt,2),len(done),'/',a.num_envs,
                              'success',sum(x['success'] for x in records),'learning=False',flush=True)
                    if len(done)==a.num_envs:break
            if len(done)!=a.num_envs:raise ValueError('Incomplete inference preparation/evaluation')
            records.sort(key=lambda x:x['trial_id'])
            (out/'evaluation.json').write_text(json.dumps(dict(count=len(records),success=sum(x['success'] for x in records),
                episodes=records,learning=False,split=a.split),indent=2)+'\n')
            torch.save(dict(schema='continuous_bridge_train_audit_v1',split=a.split,restore_supported=False,
                source_grasp_sha256=metadata['source_checkpoint_sha256'],contract_sha256=digest,
                states=env.handoff_records),out/'handoff_audit.pt')
            unchanged=all(torch.equal(v,runner.alg.policy.state_dict()[k]) for k,v in before.items())
            if not unchanged:raise ValueError('Inference preparation mutated learner weights/normalizers')
            from analyze_teacher60_native_contact_v2 import analyze
            plan.update(completed=True,source_still_matches=True,grasp_actor_unchanged=True,normalizers_unchanged=True)
            (out/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
            analysis=analyze(out);(out/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
            if a.mode=='prepare':
                report=dict(passed=bool(env.handoff_records and active_samples and checked),split=a.split,
                    learning=False,optimizer_updates=0,contract_sha256=digest,masked_returns_checked=checked,
                    normalizers_unchanged=unchanged,active_samples=active_samples,
                    floor_all_clones_verified=floor_audit['all_clones_verified'],
                    reward_audit_passed=analysis['contact_reward_verified'],
                    bias_training=True,seed=seed,num_envs=a.num_envs,
                    actual_handoffs_recorded=len(env.handoff_records),
                    artifacts={k:sha(out/k) for k in ['evaluation.json','trace.jsonl','handoff_audit.pt','contact_points.jsonl','initial_samples.json','floor_clone_audit.json','floor_override.json','analysis.json']},
                    scope='Train-only no-update pipeline preflight. Not legacy scripted certification or unseen performance.')
                if not report['passed']:raise ValueError('No real train handoff/active pull samples in preflight')
                (out/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
        if not all(torch.equal(v,frozen.alg.policy.state_dict()[k]) for k,v in frozen_before.items()):
            raise ValueError('Frozen grasp policy changed')
        if not all(torch.equal(v,runner.alg.policy.state_dict()[k]) for k,v in before.items() if 'normalizer' in k):
            raise ValueError('Parent normalization buffers changed')
        verify_source(metadata)
        if any(sha(ROOT/k)!=h for k,h in contract['files'].items()):raise ValueError('Training sources changed during run')
        if sha(a.pull_checkpoint)!=contract['pull_transfer']['checkpoint_sha256']:raise ValueError('Parent pull checkpoint changed')
        for name,h in contract['baseline_artifacts'].items():
            if sha(ROOT/name)!=h:raise ValueError('Baseline evidence changed: '+name)
        if sha(a.warm_checkpoint)!=plan['warm_checkpoint_sha256']:
            raise ValueError('Warm-start checkpoint changed')
        if a.evaluate_checkpoint and sha(a.evaluate_checkpoint)!=plan['evaluation_checkpoint_sha256']:
            raise ValueError('Evaluated checkpoint changed during inference')
        plan.update(completed=True,source_still_matches=True,grasp_actor_unchanged=True,normalizers_unchanged=True)
        (out/'run.json').write_text(json.dumps(plan,indent=2)+'\n')
        if a.mode!='train':
            from analyze_teacher60_native_contact_v2 import analyze
            analysis=analyze(out);(out/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
        print('NATIVE_CONTACT_COMPLETE',a.mode,out,flush=True)
    except BaseException:
        failed=True
        import traceback
        (out/'error.txt').write_text(traceback.format_exc())
        plan.update(completed=False,source_still_matches=False)
        (out/'run.json').write_text(json.dumps(plan,indent=2)+'\n');raise
    finally:
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)
        if runtime is not None:runtime.__exit__(None,None,None)


if __name__=='__main__':main()
