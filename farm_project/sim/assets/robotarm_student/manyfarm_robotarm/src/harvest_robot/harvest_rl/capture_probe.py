"""No-learning fixture test of real closing/contact; not a HOME success estimate."""
import json
import math
import numpy as np
import torch
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .kinematics import ArmKinematics
from .settings import CACHE


def check_capture(env, wrapped, out):
    wrapped.reset()
    k = ArmKinematics(CACHE/'harvest_training.urdf')
    fruit = env._target_fruit()
    positions = (env._grasp_center(fruit)-env.scene.env_origins).cpu().numpy()
    quat = fruit.data.root_link_quat_w.cpu().numpy()
    bank_ids = env.domain_samples[:, 0].long().cpu().numpy()
    targets = []
    for i, bank_id in enumerate(bank_ids):
        long_axis = Rotation.from_quat(quat[i, [1,2,3,0]]).as_matrix()[:, 2]
        def residual(a):
            t = k.grasp_fk(np.r_[a, 1.35], env.settings.diameter)
            return np.r_[100*(t[:3, 3]-positions[i]),
                         2*t[2, 0], 2*np.dot(t[:3, 0], long_axis)]
        fit = least_squares(residual, env.bank_np['q'][bank_id, :5],
            bounds=(k.lower[:5]+.005,k.upper[:5]-.005),max_nfev=80)
        t = k.grasp_fk(np.r_[fit.x, 1.35], env.settings.diameter)
        if np.linalg.norm(t[:3, 3]-positions[i]) > .005 or max(
                abs(t[2, 0]), abs(np.dot(t[:3, 0], long_axis))) > math.sin(math.radians(20)):
            raise RuntimeError(f'Fixture {i} has no verified horizontal IK pose')
        targets.append(np.r_[fit.x, 1.35])
    target = torch.tensor(np.array(targets),device=env.device,dtype=torch.float32)
    q = env.robot.data.default_joint_pos.clone()
    q[:, env.jids] = target
    env.robot.write_joint_state_to_sim(q,torch.zeros_like(q))
    env.targets[:] = target
    env.robot.set_joint_position_target(target,joint_ids=env.jids)
    env.domain_evaluation = True
    env.capture_probe_active = True
    completed = set(); outcomes=[]; traces=[]
    with torch.inference_mode():
        for step in range(100):
            actions = torch.zeros((env.num_envs,6),device=env.device)
            if step >= 10:actions[:, -1] = -.5
            _, reward, _, _ = wrapped.step(actions)
            row = dict(step=step,sim_time_s=(step+1)*env.step_dt,
                       **env.capture_probe_snapshot)
            traces.append(row)
            for result in env.last_domain_episodes:
                if result['env_id'] not in completed:
                    completed.add(result['env_id']);outcomes.append(result)
            if step%20==0:print('CAPTURE_CHECK',dict(step=step,completed=len(completed),
                successes=sum(r['success'] for r in outcomes),learning=False),flush=True)
            if len(completed)==env.num_envs:break
    passed = any(r['success'] for r in outcomes)
    result = dict(passed=passed, learning=False, model_created=False,
        fixture='IK-aligned open-jaw initial poses; no contact/grasp flags injected',
        meaning='mechanical capture and reward reachability check, not HOME policy performance',
        outcomes=outcomes, incomplete_envs=[i for i in range(env.num_envs) if i not in completed],
        trace=traces)
    (out/'capture_check.json').write_text(json.dumps(result,indent=2))
    if not passed:raise RuntimeError('No real fixture capture; inspect capture_check.json before training')
