"""Real Student disturbance followed by Teacher recovery, without pose injection.

The prefix has no Teacher labels and is quarantined. Only subsequent audited
Teacher commands may become demonstrations. Original episode time is retained.
"""
import json
from pathlib import Path
from types import MethodType
from unittest.mock import patch
import numpy as np
import torch


def prefix_reward(env):
    # Teacher reward potentials require Teacher pre-step bookkeeping. During
    # this inference-only prefix only the original _get_dones judges outcomes.
    env.extras['log']={}
    return torch.zeros(env.num_envs,device=env.device)


def run_prelude(env,rig,wrapper,controller,detector,arm_from_world,roi,color,steps,output):
    from harvest_rl.env import HarvestEnv
    from harvest_rl.student60_eval_adapter import Student60CommandBoundary,reset_student_servo
    from harvest_sensors.native_vision import process_native
    from harvest_vision.geometry import Frame
    from harvest_vision.tracking import TrackManager
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'DO_NOT_TRAIN.json').write_text(json.dumps(dict(reason='Student prefix commands are not expert labels')))
    tracker=TrackManager(allow_provisional=True)
    assigned='recovery-prefix';controller.start(assigned,env.targets[0].cpu().numpy())
    env.original_plant_action=MethodType(HarvestEnv._apply_action,env)
    rig.begin_episode(None)
    records=[]
    try:
        with patch.object(type(env),'_pre_physics_step',Student60CommandBoundary._pre_physics_step), \
             patch.object(type(env),'_apply_action',Student60CommandBoundary._apply_action), \
             patch.object(type(env),'_get_rewards',prefix_reward), \
             patch.object(type(env),'_verify_student_command',Student60CommandBoundary._verify_student_command,create=True):
            for step in range(steps):
                now=step*.05
                if abs(rig.clock.time-now)>1e-8:raise ValueError('Prefix camera/control drift')
                capture=rig.capture()
                frames={name:Frame(d['rgb'],d['aligned_depth_m'],d['intrinsics']['rgb'],
                    arm_from_world@d['world_from_optical']['rgb'],d['stamp_s'],d['pose_stamp_s'],name)
                    for name,d in capture.items()}
                detections,_=process_native(frames['rear'],capture['rear'],detector,now,controller.contract['centre_offset_m'],
                    arm_roi=roi if tracker.selected is None else None)
                tracker.update(detections,now)
                if tracker.selected is None:
                    choices=[k for k,t in tracker.snapshot(now).items() if t['valid'] and t['label']==color]
                    if len(choices)==1:tracker.assign(now,choices[0])
                target=tracker.observation(now);target['target_id']=assigned
                q=env.robot.data.joint_pos[0,env.jids].cpu().numpy().copy()
                qd=env.robot.data.joint_vel[0,env.jids].cpu().numpy().copy()
                tcp=(arm_from_world@np.r_[env._tcp()[0][0].cpu().numpy(),1])[:3]
                command,note=controller.step(frames,q,qd,tcp,target,now,capture)
                observation={k:v[-1] for k,v in controller.policy.history.data.items()}
                np.savez_compressed(output/f'{step:06d}.npz',**observation,student_command=command)
                env.pending_student_command=command.copy()
                _,_,done,_=wrapper.step(torch.zeros((1,6),device=env.device))
                controller.acknowledge(env.last_applied_command)
                record=dict(step=step,measured_q_rad=q.tolist(),actual_command=env.last_applied_command.tolist(),
                    target=note['target'],command_guard=note.get('command_guard'),terminated=bool(done[0]))
                records.append(record)
                (output/'trace.json').write_text(json.dumps(records,indent=2))
                if bool(done[0]):raise ValueError('Student prefix physically terminated; do not relabel it as recovery success')
        # Restore the Teacher's known initial servo before querying its labels.
        ids=torch.tensor([0],device=env.device)
        reset_student_servo(env,ids,env.original_jaw_stiffness,env.followup_default_limit)
        result=dict(completed=True,steps=len(records),student_only_control=True,physical_pose_injection=False,
            episode_budget_reset=False,post_prefix_q_rad=env.robot.data.joint_pos[0,env.jids].cpu().tolist(),
            post_prefix_targets_rad=env.targets[0].cpu().tolist(),original_episode_steps=int(env.episode_length_buf[0]))
        (output/'result.json').write_text(json.dumps(result,indent=2))
        return result
    finally:
        # Rebase only the recording camera clock; no scene/joint/fruit reset.
        rig.reset()
