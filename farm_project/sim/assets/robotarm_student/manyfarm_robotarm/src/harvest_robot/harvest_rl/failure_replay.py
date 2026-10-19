"""Read-only replay selection and exact initial domain geometry reconstruction."""
import json
import math
from pathlib import Path

CONDITIONS={'baseline':'baseline','weak':'extra_half_degree','early':'earlier_load'}


def load_trials(folder, trials, segment='loss', successful=False):
    folder=Path(folder)
    run=json.loads((folder/'run.json').read_text())
    evaluation=json.loads((folder/'evaluation.json').read_text())
    if not run.get('completed') or run.get('learning') or run.get('hardware_executed'):
        raise ValueError('Requires a completed simulation-only comparison')
    episodes={e['trial_id']:e for e in evaluation['episodes']}
    if any(i not in episodes or bool(episodes[i]['success']) != successful for i in trials):
        raise ValueError('Select recorded '+('successful' if successful else 'failed')+' trial IDs')
    if successful and segment != 'full':
        raise ValueError('Successful cases require the full recorded segment')
    rows={i:[] for i in trials}
    for line in (folder/'trace.jsonl').open():
        frame=json.loads(line)
        for i,values in zip(frame['env_ids'],frame['rows']):
            if i not in rows:continue
            row=dict(zip(frame['columns'],values));row['recorded_time_s']=frame['time_s']
            if not all(math.isfinite(v) for v in row.values()):raise ValueError('Nonfinite replay frame')
            rows[i].append(row)
    for i,rr in rows.items():
        if not rr:raise ValueError('Missing recorded trial '+str(i))
        if successful:
            # Pull-only success logs have no transport fields. Keep every frame
            # through their recorded success, including any earlier contact loss.
            continue
        transport=next((j for j,x in enumerate(rr) if x['transport_action_active']),None)
        lost=next((j for j,x in enumerate(rr) if x['transport_action_active'] and
            (not x['qualified_grasp'] or x['slip_m']>=.012)),None)
        if segment=='loss':
            if transport is None or lost is None:raise ValueError('No recorded transport loss for trial '+str(i))
            begin=max(0,transport-10);end=min(len(rr),lost+21)
            rows[i]=rr[begin:end]
        elif segment=='full':
            # Retain HOME/approach/pull, omit the stationary timeout tail.
            if lost is not None and not successful:rows[i]=rr[:lost+21]
        else:raise ValueError('Segment must be loss or full')
    return run, episodes, rows


def initial_batch(env, run, expected):
    """Reproduce the three original32-row resets using the original CUDA RNG.

    Reconstruct only data, never run physics. One display environment suffices.
    Tilt azimuth was absent from initial_samples.json; reusing the exact sampler
    reconstructs it instead of inventing a fruit rotation or stem anchor.
    """
    import torch
    from .teacher_domain import sample_pose
    n=run['num_envs'];stage=3
    generator=torch.Generator(device=env.device).manual_seed(run['seed']+100003)
    pool=env.domain_pools[stage]
    # TeacherContactMarginEnv repeats far candidates in train only. The plain
    # display environment deliberately has no reward/recording controller, so
    # reconstruct that exact sampling pool here rather than changing the scene.
    if run['split']=='train':
        from .grasp_contact_margin_60hz import SPEC
        far=pool[env.domain_distances[pool]>SPEC['far_distance_m']]
        pool=torch.cat([pool]+[far]*SPEC['extra_far_pool_repeats'])
    # RslRlVecEnvWrapper construction resets once, then the evaluator explicitly
    # calls wrapped.reset() twice. Preserve that otherwise invisible first reset.
    for _ in range(3):
        chosen=pool[torch.randint(len(pool),(n,),generator=generator,device=env.device)]
        color=torch.randint(2,(n,),generator=generator,device=env.device)
        quat,tilt,yaw=sample_pose(n,env.domain,stage,generator,env.device)
        torch.rand((n,2),generator=generator,device=env.device)  # original thresholds
        torch.rand((n,5),generator=generator,device=env.device)  # original home jitter
    samples=torch.stack((env.domain_bank_ids[chosen].float(),tilt*180/math.pi,
        yaw*180/math.pi,env.domain_distances[chosen],color.float(),
        torch.full_like(tilt,stage)),-1)
    actual=samples.cpu().tolist()
    if len(actual)!=len(expected) or max(abs(a-b) for row,old in zip(actual,expected)
            for a,b in zip(row,old))>1e-5:
        raise ValueError('Original32-scene RNG/geometry differs; do not invent a replay anchor')
    return samples,quat
