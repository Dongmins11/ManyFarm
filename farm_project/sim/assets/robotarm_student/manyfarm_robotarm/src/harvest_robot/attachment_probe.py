"""Isaac physical v4 connector smoke test, isolated fruit with no policy.

Relocates the existing fruit assets away from the robot to test connector response
without incidental robot/box collisions. This is not a grasp or policy evaluation.
"""
import argparse
import json
from pathlib import Path
from isaaclab.app import AppLauncher
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stem-response-version', type=int, choices=[1,2,3], default=3)
parser.add_argument('--mass', type=float, default=.035)
parser.add_argument('--rebound-test', action='store_true')
parser.add_argument('--output', type=Path, default=Path('outputs/harvest_rl/attachment_v4_probe.json'))
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.kit_args = (args.kit_args or '') + ' --/plugins/carb.tasking.plugin/threadCount=1'
app = AppLauncher(args).app
env = None
failed = False
try:
    import torch
    from isaaclab.utils.math import quat_apply
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    labels = ['rest', 'lateral_pulse', 'axial_pulse', 'sustained_pull', 'compression', 'lateral_hold']
    class Probe(HarvestEnv):
        def _get_dones(self):
            self._update_task()
            return torch.zeros_like(self.success), torch.zeros_like(self.success)
        def _apply_action(self):
            super()._apply_action()
            if not hasattr(self, 'probe_step'):
                return
            force = torch.zeros(6, 1, 3, device=self.device)
            if self.probe_step < 6:  # 25 ms at 240 Hz
                force[1, 0, 1] = .6
                force[2, 0, 0] = -6.
            force[3, 0, 0] = -4.
            force[4, 0, 0] = 4.
            force[5, 0, 1] = 1.
            self.fruits[0].instantaneous_wrench_composer.set_forces_and_torques(
                forces=force, torques=torch.zeros_like(force), is_global=True)
            self.probe_step += 1
    cfg = TaskSettings(task='pull', attachment_version=4, stem_response_version=args.stem_response_version, mass=args.mass)
    env = Probe(cfg, num_envs=6, device=args.device)
    env.reset()
    fruit = env.fruits[0]
    state = fruit.data.default_root_state.clone()
    state[:, :3] = env.scene.env_origins + torch.tensor([1.4, 0., 2.], device=env.device)
    state[:, 3:7] = torch.tensor([1., 0., 0., 0.], device=env.device)
    state[:, 7:] = 0.
    fruit.write_root_state_to_sim(state)
    env.rest_quat[:, 0] = state[:, 3:7]
    tip = torch.as_tensor(env.tips_np[0], device=env.device, dtype=torch.float32).expand(6, -1)
    env.anchors[:, 0] = state[:, :3] + quat_apply(state[:, 3:7], tip)
    env.threshold.fill_(2.5)  # deterministic diagnostic; training randomization unchanged
    if args.rebound_test:
        # Displace an attached fruit downward by 30 mm, then release it at rest.
        # Keep the connector anchor at its original position.
        state[0, 2] -= .03
        fruit.write_root_state_to_sim(state)
    env.probe_step = 0
    action = torch.zeros(6, 6, device=env.device)
    traces = []
    for step in range(20):
        env.step(action)
        pos = fruit.data.root_link_pos_w + quat_apply(fruit.data.root_link_quat_w, tip)
        traces.append({'time_s': (step+1)*env.step_dt,
                       'attached': env.attached[:, 0].tolist(),
                       'extension_m': (env.anchors[:, 0, 0]-pos[:, 0]).tolist(),
                       'tension_N': env.load[:, 0].tolist(),
                       'speed_m_s': fruit.data.root_com_lin_vel_w.norm(dim=-1).tolist(),
                       'z_m': (fruit.data.root_link_pos_w-env.scene.env_origins)[:,2].tolist(),
                       'stem_length_m': (pos-env.anchors[:,0]).norm(dim=-1).tolist()})
    report = {'settings': cfg.as_dict(), 'cases': labels, 'traces': traces,
              'final_attached': env.attached[:, 0].tolist(),
              'break_load_N': env.break_load[:, 0].tolist(),
              'break_dwell_s': env.break_duration[:, 0].tolist(),
              'expected_attached': [True, True, True, False, True, True]}
    report['passed'] = report['final_attached'] == report['expected_attached']
    if args.rebound_test:
        report['rebound_max_speed_m_s'] = max(t['speed_m_s'][0] for t in traces)
        report['rebound_max_stem_length_m'] = max(t['stem_length_m'][0] for t in traces)
        report['rebound_final_speed_m_s'] = traces[-1]['speed_m_s'][0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print('ATTACHMENT_V4_PROBE', json.dumps({k:v for k,v in report.items() if k not in ('settings','traces')}), flush=True)
    assert report['passed'], report['final_attached']
except Exception:
    import traceback
    traceback.print_exc()
    failed = True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app, env, failed)
