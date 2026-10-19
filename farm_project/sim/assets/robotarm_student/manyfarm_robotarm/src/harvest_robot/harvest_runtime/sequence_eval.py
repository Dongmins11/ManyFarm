"""GPU integration loop for independent scenes, each containing two harvests."""
import json
import time
import torch
from .executor import Request
from .isaac_teacher import make_executor
from .isaac_return import IsaacReturn


def target_order(positions, mode, first_color):
    ids=['red','yellow']
    if mode=='lowest-first':
        return sorted(ids,key=lambda name:(positions[ids.index(name)][2],ids.index(name)))
    return ids if first_color=='red' else ids[::-1]


@torch.inference_mode()
def evaluate(env,wrapped,policy,args,out,app):
    reports=[];ticks=0
    wall_start=time.perf_counter()
    for episode in range(getattr(args,"sequence_start_scene",0),getattr(args,"sequence_start_scene",0)+args.episodes):
        if ticks>=args.steps or not app.is_running():break
        # Reset only between whole two-target scenes, never between targets.
        env.layout_episode=episode;env.reset()
        motion=IsaacReturn(env,path_mode=args.return_path)
        executor,teacher=make_executor(env,wrapped,policy,motion,
            {'red':0,'yellow':1},reset_policy_state=getattr(policy,"reset",lambda:None))
        executor.return_timeout=40.
        target_starts=[]
        old_start=teacher.start_target
        def start(request,target):
            motion.begin_target();old_start(request,target)
            target_starts.append(dict(request_id=request.request_id,target_id=request.target_id,
                slot=int(env.target_index[0]),position_m=list(target.position_m),
                joint_pos=motion.measured().tolist()))
        teacher.start_target=start
        contact_trace=[]
        old_apply=teacher.apply
        def apply(action,now):
            old_apply(action,now);motion.record()
            if getattr(args,'sequence_trace',False):
                contact_trace.append(dict(sim_s=(env._sim_step_counter-start_counter)*env.physics_dt,
                    stage=int(env.expert_stage[0]) if hasattr(env,'expert_stage') else None,
                    target=int(env.target_index[0]),attached=env.attached[0].cpu().tolist(),
                    grip=bool(env.grip[0]),has_grasped=bool(env.has_grasped[0]),valid_detach=bool(env.valid_detach[0]),
                    retained=bool(env.has_retained[0]),
                    pending_detach=bool(env.pending_detach[0]),
                    pending_age_s=float(env.pending_detach_age[0]),
                    pending_hold_s=float(env.pending_detach_time[0]),
                    raw_grip=bool(env.raw_grip[0]),entry_inside=bool(env.entry_inside[0]),
                    center_distance_m=float(env.distance[0]),tcp=env._tcp()[0][0].cpu().tolist(),
                    fruit_positions=[f.data.root_link_pos_w[0].cpu().tolist() for f in env.fruits],
                    fixed_force=env.fixed_contact.data.force_matrix_w[0,0].cpu().tolist(),
                    moving_force=env.moving_contact.data.force_matrix_w[0,0].cpu().tolist(),
                    arm_force=env.arm_contact.data.net_forces_w[0].cpu().tolist(),
                    load=env.load[0].cpu().tolist(),break_timer=env.break_timer[0].cpu().tolist(),
                    joint_pos=env.robot.data.joint_pos[0,env.jids].cpu().tolist(),
                    joint_targets=env.targets[0].cpu().tolist(),
                    slip_m=float(env.slip[0]),
                    action=action[0].cpu().tolist()))
        # Bound methods were captured when backend was constructed.
        executor.backend.apply_action=apply
        order=target_order([f.data.root_link_pos_w[0].cpu().tolist() for f in env.fruits],args.harvest_order,args.target)
        print('SEQUENCE_ORDER',episode,args.harvest_order,order,flush=True)
        layout=dict(env.last_layout)
        initial_positions=[f.data.root_link_pos_w[0].cpu().tolist() for f in env.fruits]
        start_counter=env._sim_step_counter
        def sim_now():return (env._sim_step_counter-start_counter)*env.physics_dt
        executor.start([Request(f'scene-{episode}-{t}',t,env.settings.episode_s+.1) for t in order],0.)
        step=0
        last_state=None
        next_diagnostic_s=0.
        while not executor.done and ticks<args.steps and app.is_running():
            step+=1;ticks+=1
            executor.tick(sim_now())
            if sim_now()>=next_diagnostic_s:
                diagnostic=dict(scene=episode,sim_s=sim_now(),state=executor.state,
                    completed_ids=sorted(executor.completed),target_slot=int(env.target_index[0]),
                    assignment_status=env.assignment_status,
                    expert_stage=int(env.expert_stage[0]) if hasattr(env,'expert_stage') else None,
                    task={k:v[0].cpu().tolist() for k,v in env.last_diagnostics.items()
                          if step>1 and k in ('in_box','placement_hold_s','valid_detach','has_retained','valid_release','fruit_speed_m_s')})
                (out/'sequence_live.json').write_text(json.dumps(diagnostic,indent=2))
                print('SEQUENCE_PROGRESS',json.dumps(diagnostic),flush=True)
                next_diagnostic_s=sim_now()+2.
            if executor.state!=last_state:
                print('SEQUENCE_STATE',episode,step,executor.state,executor.reason,flush=True)
                last_state=executor.state
        if not executor.done:
            executor.cancel(sim_now(),'evaluation_budget_or_app_closed')
            # Stop acknowledgement has a separate bounded budget.
            for _ in range(int(executor.stop_timeout/env.step_dt)+2):
                if executor.done:break
                step+=1;executor.tick(sim_now())
        if getattr(args,'sequence_trace',False):
            (out/f'contact_trace_{episode:03d}.json').write_text(json.dumps(contact_trace,indent=2))
        record=executor.report()
        record.update(scene=episode,harvest_order=args.harvest_order,requested_order=order,target_starts=target_starts,layout=layout,initial_positions=initial_positions,
                      final_positions=[f.data.root_link_pos_w[0].cpu().tolist() for f in env.fruits],
                      collected=env.collected[0].cpu().tolist(),return_records=motion.records,sim_s=sim_now(),
                      task_diagnostics={k:v[0].cpu().tolist() for k,v in env.last_diagnostics.items()},
                      terminal_diagnostics={k:float(v[0]) for k,v in env.last_diagnostics.items() if k.startswith('failure_')})
        reports.append(record)
        (out/'sequence_episodes.json').write_text(json.dumps(reports,indent=2))
        print('SEQUENCE_RESULT',episode,record['state'],record['completed_ids'],record['reason'],flush=True)
    summary=dict(wall_s=time.perf_counter()-wall_start, simulated_s=sum(r['sim_s'] for r in reports), scenes=len(reports),successful_scenes=sum(r['state']=='SUCCEEDED' for r in reports),
                 harvested_targets=sum(len(r['completed_ids']) for r in reports),ticks=ticks,
                 note=f'Physical sequential evaluation; return={args.return_path}, behavior={args.behavior_mode}; sampled clearance/contact monitoring is not an exact collision-free planner')
    summary['realtime_factor']=summary['simulated_s']/max(summary['wall_s'],1e-6)
    (out/'sequence_metrics.json').write_text(json.dumps(summary,indent=2))
    print('SEQUENCE_METRICS',summary,flush=True)
