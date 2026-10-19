"""Bounded environment application check: 4 clones, 3 inference steps, no learning."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))


def main():
    from isaaclab.app import AppLauncher
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path)
    p.add_argument('--kind',choices=['eval','train'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--execute',action='store_true')
    AppLauncher.add_app_launcher_args(p)
    a=p.parse_args()
    from harvest_rl.environment_version import load_profile,rooted,sha,runtime_audit
    profile,path=load_profile(a.profile)
    if a.output.exists():p.error('Use a new output folder')
    if not a.execute:
        print('CHECK_PLAN',profile['version'],a.kind,'4 clones,3 inference steps;learning=False',flush=True)
        return
    a.output.mkdir(parents=True)
    app=AppLauncher(a).app;env=None;runtime=None;failed=True
    try:
        import numpy as np
        import torch
        from scipy.spatial.transform import Rotation
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rsl_rl.runners import OnPolicyRunner
        from harvest_rl.settings import TaskSettings
        from harvest_rl.policy import teacher_config
        from harvest_rl.progress_normalization import install_grasp_progress_normalization
        from harvest_rl.attachment_60hz_runtime import response6_runtime
        from harvest_rl.bridge_pull_training import source_metadata
        from harvest_rl.native_contact_control_training import verify_policy
        from harvest_rl.bridge_pull_risk import RiskPullSpec
        from harvest_rl.pressure_compare import PressureSpec
        from harvest_rl.floor_unified import audit_floor_clones
        from harvest_rl.teacher_finger_friction_v1_env import TeacherFingerFrictionV1EvalEnv,TeacherFingerFrictionV1TrainEnv
        metadata,grasp_saved=source_metadata(rooted(profile['policies']['grasp']['path']))
        saved,_=verify_policy(metadata,rooted(profile['policies']['parent_pull']['path']),rooted(profile['policies']['native']['path']))
        source=metadata['source_run'];frame=np.asarray(source['current_base_to_policy_world'])
        rotation=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
        cfg=TaskSettings(**profile['base_task'])
        cfg.seed=profile['evaluation_seeds']['train' if a.kind=='train' else 'validation']
        cfg.workspace_split='train' if a.kind=='train' else 'eval'
        runtime=response6_runtime();attachment=runtime.__enter__()
        common=dict(environment_profile=path,path_spec=RiskPullSpec(axial=True,hold_after_detach=True),
            grasp_policy=None,domain=source['domain'],domain_stage=3,
            domain_split='train' if a.kind=='train' else 'validation',num_envs=4,device=a.device,
            cameras=False,robot_usd=Path(source['current_asset']['usd']),
            robot_root_pose=(tuple(frame[:3,3]),tuple(rotation)),fruit_color_override=source['domain']['colors'],
            fruit_asset_cache=a.output/'fruit_assets',visual_scene=source['visual_scene_requested'])
        if a.kind=='eval':
            env=TeacherFingerFrictionV1EvalEnv(cfg,floor_mode='unified',posture_mode='position',stability_mode='pause',
                pressure_spec=PressureSpec(0.),transport_speed_m_s=.035,orientation_length_m=.02,
                opening_rate_rad_s=.3,deposit_timeout_s=6.,hold_stiffness_Nm_rad=1.,gain_ramp_s=1.,
                transport_policy=None,**common)
        else:
            env=TeacherFingerFrictionV1TrainEnv(cfg,bias_training=True,**common)
        wrapped=RslRlVecEnvWrapper(env,clip_actions=None)
        def runner_for(state):
            r=OnPolicyRunner(wrapped,teacher_config(),log_dir=None,device=a.device)
            install_grasp_progress_normalization(r.alg.policy)
            r.alg.policy.load_state_dict(state['model_state_dict'])
            for param in r.alg.policy.parameters():param.requires_grad_(False)
            return r
        grasp=runner_for(grasp_saved);native=runner_for(saved)
        env.grasp_policy=grasp.get_inference_policy(device=a.device)
        policy=native.get_inference_policy(device=a.device)
        before=[{k:v.clone() for k,v in r.alg.policy.state_dict().items()} for r in [grasp,native]]
        wrapped.reset();wrapped.reset();env.domain_evaluation=True
        start=runtime_audit(env);obs=wrapped.get_observations()
        with torch.inference_mode():
            for _ in range(3):obs,_,_,_=wrapped.step(policy(obs))
        unchanged=all(torch.equal(v,r.alg.policy.state_dict()[k]) for r,state in zip([grasp,native],before) for k,v in state.items())
        if not unchanged:raise ValueError('Inference altered frozen model/normalizer')
        end=runtime_audit(env);floor=audit_floor_clones(env)
        load_profile(path)
        result=dict(schema='teacher60_environment_smoke_v1',version=profile['version'],profile_sha256=sha(path),
            kind=a.kind,environment_class=type(env).__name__,clones=4,policy_steps=3,
            simulated_duration_s=.15,learning=False,optimizer_updates=0,hardware_executed=False,
            models_and_normalizers_unchanged=unchanged,attachment_runtime=attachment,
            source_robot_usd_sha256=sha(source['current_asset']['usd']),
            start=start,end=end,floor=floor,completed=True,
            limitation='Material/clone/frequency/inference check only; not a harvest success evaluation')
        (a.output/'check.json').write_text(json.dumps(result,indent=2)+'\n')
        print('ENVIRONMENT_CHECK_PASSED',a.kind,profile['version'],'60Hz/20Hz;4clones;no learning',flush=True)
        failed=False
    finally:
        if runtime is not None:runtime.__exit__(None,None,None)
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)


if __name__=='__main__':main()
