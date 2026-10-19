"""Explicit assignment evaluation, simulator only. No automatic terminal stepping."""
import json
import torch
from .target_contract import TargetSession, TargetObservation, student_state


@torch.inference_mode()
def evaluate(env, wrapped, policy, args, output, app):
    results = []
    steps = 0
    session = TargetSession('simulation_world')
    for episode in range(args.episodes):
        if steps >= args.steps or not app.is_running():
            break
        env.reset()  # Deliberate scene reset between independent evaluation trials.
        session.reset()
        session.assign(f'eval-{episode}', f'fruit-{episode}')
        obs = env.assign_target(0)
        while env.assignment_status == 'RUNNING' and steps < args.steps and app.is_running():
            with torch.inference_mode():
                now = float(env.episode_length_buf[0])*env.step_dt
                position = env.fruits[0].data.root_link_pos_w
                session.update(TargetObservation(session.target_id, 'simulation_world', now,
                               tuple(position[0].tolist()), True), now)
                # Contract smoke only: perfect simulation position is NOT vision validation.
                xyz, valid, age = session.sample(now)
                state = student_state(env.proprio(), torch.tensor([xyz],device=env.device),
                                      env._tcp()[0], torch.tensor([valid],device=env.device),
                                      torch.tensor([age],device=env.device))
                assert state.shape == (1,23)
                obs, _, _, _ = wrapped.step(policy(obs))
            steps += 1
        status = env.assignment_status
        if status == 'RUNNING':
            env.cancel_target()
            status = 'CANCELLED'
        session.finish(status, 'simulation_task_result' if status != 'CANCELLED' else 'evaluation_step_budget_or_app_closed')
        results.append(session.result())
        (output/'assignments.json').write_text(json.dumps(results,indent=2))
        print('ASSIGNMENT_RESULT', results[-1], flush=True)
    summary = {status:sum(r['status']==status for r in results)
               for status in ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')}
    summary.update(episodes=len(results), steps=steps,
                   note='Simulator assignment integration; ideal target adapter; no real vision or ROS validation')
    (output/'assignment_metrics.json').write_text(json.dumps(summary,indent=2))
    print('ASSIGNMENT_METRICS',summary,flush=True)
