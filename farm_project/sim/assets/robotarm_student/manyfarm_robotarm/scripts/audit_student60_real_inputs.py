"""Offline audit of the preserved camera Student and STS feedback contract.

No USB, serial, actuator writes, Isaac runtime, GPU inference, or training.
Static guards are bounded evidence, not a proof of all possible information flow.
Historical calibration is evaluated as recorded and never authorized for motion.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/harvest_robot'),str(ROOT/'scripts/so101_bench')]


def speed_rad_s(signed_raw,phase,direction):
    """Nominal STS manual units. Not measured feedback accuracy/resolution."""
    if direction not in (-1,1) or type(phase) is not int or not 0<=phase<=255:
        raise ValueError('Explicit phase and calibrated joint direction required')
    if not -32767<=signed_raw<=32767:raise ValueError('Signed-magnitude speed outside register range')
    return direction*signed_raw*(.0146 if phase&4 else .732)*2*math.pi/60


def source_evidence(relative,needle):
    path=ROOT/relative
    return [dict(path=str(path),line=i,text=line.strip()) for i,line in enumerate(path.read_text().splitlines(),1)
            if needle in line]


def controller_guard():
    from harvest_runtime.student60_timing.controller import TimingAssistedController,TimingCore
    from harvest_runtime.student60_timing.runtime import TimingRuntime
    classes=[cls for cls in TimingAssistedController.__mro__ if cls is not object]+[TimingCore,TimingRuntime]
    forbidden={'env','_target_fruit','_grasp_center','root_link_pos_w','root_link_quat_w','chain_snapshot',
        'net_forces_w','contact_forces','applied_torque','incoming_joint_wrench','teacher_actor'}
    forbidden_modules=('isaaclab','omni','pxr','harvest_rl.env')
    violations=[];sources={};task_keys=set()
    for cls in classes:
        path=Path(inspect.getsourcefile(cls));tree=ast.parse(path.read_text());sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        definition=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls.__name__)
        for node in ast.walk(definition):
            name=node.attr if isinstance(node,ast.Attribute) else None
            if name in forbidden:violations.append(dict(path=str(path),line=node.lineno,attribute=name))
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='getattr' and len(node.args)>1:
                key=node.args[1]
                if isinstance(key,ast.Constant) and key.value in forbidden:violations.append(dict(path=str(path),line=node.lineno,attribute=key.value))
            if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant):
                if ast.unparse(node.value)=="self.contract['task']":task_keys.add(node.slice.value)
        for node in tree.body:
            modules=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            for module in modules:
                if module.startswith(forbidden_modules):violations.append(dict(path=str(path),line=node.lineno,module=module))
    if violations:raise AssertionError(violations)
    return dict(passed=True,scope='MRO helper classes + TimingCore/TimingRuntime, bounded AST attribute/import check',
        classes_checked=len(classes),source_sha256=sources,forbidden_accesses=violations,
        consumed_nominal_task_keys=sorted(task_keys),
        note='Manually traced camera/vision/TCP producers in the evaluator separately; this is not a whole-program taint proof')


def input_contract_check():
    import torch
    from harvest_rl.student_v2 import measured_proprio
    from harvest_rl.target_contract import student_state
    from harvest_runtime.student60 import encode_command,decode_command
    from harvest_vision.student60_camera_center import features
    saved=torch.load(ROOT/'outputs/harvest_rl/student60_improvement_20261015/round2_train_lr1e4/student_best.pt',map_location='cpu',weights_only=True)
    c=saved['contract'];lo=np.asarray(c['lower_rad']);hi=np.asarray(c['upper_rad']);q=(lo+hi)/2
    qd=np.array([.1,-.1,.2,-.2,0.,.03]);command=encode_command(q,[8.,.15],lo,hi)
    recovered,servo=decode_command(command,lo,hi);np.testing.assert_allclose(recovered,q,atol=2e-7)
    proprio=measured_proprio(q,qd,command[:6],lo,hi)
    tcp=np.array([.2,0.,.1]);target=tcp+np.array([.01,.02,.03])
    state=student_state(torch.tensor(proprio)[None],torch.tensor(target,dtype=torch.float32)[None],
        torch.tensor(tcp,dtype=torch.float32)[None],torch.tensor([True]),torch.tensor([.02]))[0].numpy()
    assert state.shape==(23,) and np.isfinite(state).all()
    np.testing.assert_allclose(state[6:12],qd/1.5,atol=1e-7)
    np.testing.assert_allclose(state[18:21],[.01,.02,.03],atol=1e-7)
    class Poison:
        def __array__(self,*args,**kwargs):raise AssertionError('Privileged state must not be read')
    record=dict(bbox=[10,20,30,40],confidence=.9,valid_depth_fraction=.8,depth_mad_m=.002,depth_pixels=100)
    np.testing.assert_array_equal(features(Poison(),target,record),features(None,target,record))
    return dict(passed=True,joint_order=c['joint_names'],joint_position_unit='rad',joint_velocity_unit='rad/s',
        normalized_state=dict(q=[0,6],qd_divided_by_1_5=[6,12],previous_sent_goal=[12,18],
            estimated_target_minus_tcp=[18,21],valid=[21,22],age_seconds=[22,23]),
        camera_center_inputs=11,camera_center_ignores_privileged_state=True,
        command_outputs='6 joint goals + simulator jaw stiffness + jaw speed limit',
        jaw_servo_physical_mapping_verified=False),c


def historical_feedback_check(folder,contract):
    from bench import angles,tick_delta
    from response_core import decode_feedback
    summary=json.loads((folder/'summary.json').read_text());limits=json.loads((folder/'motor_limits.json').read_text())
    cal_path=Path(summary['calibration_path']);cal=json.loads(cal_path.read_text());motors=limits['motors']
    assert [m['id'] for m in motors]==list(range(1,7))
    for m in motors:
        assert m['mode']==0 and m['resolution']==1 and m['end']==0
        np.testing.assert_allclose(speed_rad_s(1,m['phase'],1),m['nominal_speed_rad_s_per_raw'],rtol=1e-12)
    # Exercise the actual feedback decoder with synthetic signed-magnitude bytes.
    packet=[0]*31
    def word(index,value):packet[index]=value&255;packet[index+1]=value>>8
    packet[0]=1;word(16,2048);word(18,0x800A);word(20,0x400|123);word(29,20)
    packet[22]=120;packet[23]=32
    decoded=decode_feedback(packet)
    assert decoded['speed_raw']==-10 and decoded['load_raw']==-123 and decoded['current_raw']==20
    assert decoded['voltage_V']==12.
    assert tick_delta(2,4094)==4 and tick_delta(4094,2)==-4
    sample_count=0;velocity_count=0;spreads=[];periods=[];old_q=old_t=None;outside=0;voltage=[]
    lo=np.asarray(contract['lower_rad']);hi=np.asarray(contract['upper_rad'])
    with (folder/'hardware.jsonl').open() as stream:
        for line in stream:
            row=json.loads(line)
            if row.get('event')=='health_sample':
                voltage.extend(v['voltage'] for v in row['health']);continue
            if row.get('event')!='tracking_sample':continue
            snap=dict(cal['reference'],ticks=row['ticks'])
            q=np.asarray(angles(snap,cal,display=True));sample_count+=1
            outside+=int(np.any(q<lo-1e-6) or np.any(q>hi+1e-6))
            times=row.get('position_read_times_s')
            if times is None:continue
            times=np.asarray(times);spreads.append(float(times.max()-times.min()))
            if old_q is not None:
                dt=times-old_t
                if np.all((dt>0)&(dt<=.1)):
                    qd=(q-old_q)/dt
                    assert np.isfinite(qd).all();velocity_count+=1;periods.extend(dt.tolist())
            old_q,old_t=q,times
    assert sample_count>0 and velocity_count>0
    def stats(v):return None if not v else dict(minimum=float(min(v)),median=float(np.median(v)),p95=float(np.percentile(v,95)),maximum=float(max(v)))
    return dict(passed=True,scope='Historical records and offline/synthetic conversions only, no live sensor accuracy test',
        folder=str(folder),calibration=str(cal_path),calibration_purpose=cal.get('purpose'),calibration_note=cal.get('note'),
        motors=[{k:m[k] for k in ('id','model','firmware_major','firmware_minor','phase','mode','resolution','speed_unit_coefficient')} for m in motors],
        nominal_speed_rad_s_per_raw=[speed_rad_s(1,m['phase'],1) for m in motors],
        position_rad_per_tick=2*math.pi/4096,position_deg_per_tick=360/4096,
        one_tick_difference_at20hz_rad_s=2*math.pi/4096/.05,
        captured_position_samples=sample_count,causal_velocity_windows_checked=velocity_count,
        historical_samples_outside_student_joint_bounds=outside,per_joint_read_spread_s=stats(spreads),per_joint_sample_interval_s=stats(periods),
        historical_supply_voltage_V=stats(voltage),live_registers_verified=False,
        register_speed_vs_encoder_derivative_validated=False,
        load_semantics='PWM drive duty, not torque Nm or contact force N',
        current_semantics='motor phase-current feedback, model/firmware capability must be checked; not fingertip force',
        no_load_or_current_in_student_observation=True)


def simulated_tcp_fk_check(contract):
    from harvest_rl.kinematics import ArmKinematics
    kin=ArmKinematics();arm_from_robot=np.linalg.inv(kin.fk(np.zeros(6),'arm_2/base_link'))
    folder=ROOT/'outputs/harvest_rl/student60_improvement_20261015/faster_capture_followthrough_v20/fresh_test'
    errors=[]
    for path in sorted(folder.glob('episode_*/trace.jsonl')):
        with path.open() as stream:
            for line in stream:
                row=json.loads(line)
                tcp=(arm_from_robot@kin.grasp_fk(np.asarray(row['measured_q_rad']),contract['task']['diameter']))[:3,3]
                errors.append(float(np.linalg.norm(tcp-np.asarray(row['tcp_arm_m']))))
    if not errors:raise AssertionError('No preserved q/TCP trace')
    assert max(errors)<.0005
    return dict(passed=True,samples=len(errors),maximum_error_m=max(errors),p95_error_m=float(np.percentile(errors,95)),
        scope='Same public FK reproduces recorded simulator TCP from q; real FK accuracy/backlash/flexibility remain unverified')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--motor-label-confirmed',action='store_true',help='Record user confirmation of STS3215 12V label; no live device identity verification')
    p.add_argument('--hardware-run',type=Path,default=ROOT/'outputs/so101_bench/ppo_motor_dynamics_20261013_114827_909368935/run')
    a=p.parse_args()
    if a.output.exists():p.error('Preserve previous audits; choose a new output')
    guard=controller_guard();observations,contract=input_contract_check();hardware=historical_feedback_check(a.hardware_run.resolve(),contract)
    fk=simulated_tcp_fk_check(contract)
    baseline=json.loads((ROOT/'outputs/harvest_rl/student60_timing_20261015_212202/preservation.json').read_text())
    unchanged=all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in baseline['original_paths_sha256'].items())
    assert unchanged
    report=dict(schema='student60_real_input_compatibility_audit_v1',created_utc=datetime.now(timezone.utc).isoformat(),
        hardware_commands_sent=0,baseline_64_files_unchanged=unchanged,controller_static_guard=guard,
        student_input_check=observations,historical_feedback_check=hardware,simulator_tcp_reconstructed_from_q=fk,
        motor_identity=dict(repository_model='STS3215',user_confirmed_label='STS3215 12V' if a.motor_label_confirmed else None,
            live_model_firmware_phase_verified=False),
        current_hardware_scope='No ttyACM/ttyUSB or serial/by-id found in read-only host inventory this turn',
        findings=[
          dict(id='NO_FRUIT_ORACLE_AT_CONTROL_INPUT',severity='passed_bounded_audit',detail='Camera detections/tracker/11-feature camera center; helper receives q,qd,TCP,task geometry and own state'),
          dict(id='SIM_TCP_REQUIRES_HARDWARE_ESTIMATOR',severity='porting_required',detail='Evaluator passes env._tcp derived from exact simulated body pose. Hardware must use calibrated FK/visual estimate; FK self-consistency is not independent accuracy proof'),
          dict(id='CAMERA_EXTRINSICS_REQUIRE_CALIBRATION',severity='porting_required',detail='Renderer exact camera poses must become calibrated mount+capture-time encoder FK. Real IR/depth have additional noise, occlusion and sensor failure'),
          dict(id='JOINT_SPEED_AND_TIME_DOMAIN',severity='conversion_required',detail='Sign-magnitude speed and phase-dependent RPM units -> calibrated direction * rad/s; or causal position differentiation. Preserve per-joint sample times, quantization, delay'),
          dict(id='SIX_MOTORS_ARE_NOT_SAMPLED_SIMULTANEOUSLY',severity='measurement_alignment_required',detail='Historical six-angle read spans median11ms, p95about12ms. Preserve per-joint times and align a common past pose; do not mark all samples at receive time or assume simulation60Hz feedback'),
          dict(id='CALIBRATION_PROVISIONAL_MODE_IS_SIMULATION_ONLY',severity='hardware_gate_required',detail='AssignedFruitTracker permits provisional detections; real execution must require independently verified camera/mount/center calibration, robot/clock identities and reject unverified geometry'),
          dict(id='SENT_GOAL_NOT_PHYSICAL_POSITION',severity='hardware_ack_contract_required',detail='Previous action is sent/accepted goal, not encoder q. SyncWrite packet transmission alone does not prove each servo accepted it; define readback/ack evidence separately from target reached'),
          dict(id='OFFLINE_SMOOTHING_IS_NONCAUSAL',severity='do_not_reuse_live',detail='motor_dynamics.derivatives smooth fit uses two future samples. Only raw backward difference is causal; timing runtime currently does not use the offline smoother'),
          dict(id='SIM_STIFFNESS_NOT_STS_GAIN_OR_TORQUE',severity='blocking_for_direct_hardware_output',detail='NN outputs6 joint goals + jaw stiffness Nm/rad and velocity limit. STS P/Torque_Limit have different units; no calibrated direct mapping exists'),
          dict(id='CONTACT_PROXY_NOT_FORCE_SENSOR',severity='physical_validation_required',detail='Grip inference uses measured jaw position, estimated speed and goal tracking error; does not prove contact, load, actual retention or stem separation'),
          dict(id='NOMINAL_GEOMETRY_NOT_OBSERVED_PER_FRUIT',severity='calibration_or_estimation_required',detail='Diameter70mm,length75mm,pull axis/tray/mount transform are configured assumptions, not online fruit truth. grasp_fk TCP offset depends on nominal diameter'),
          dict(id='SIM_GRADING_AND_SAFETY_USE_TRUTH',severity='separate_hardware_evidence_required',detail='Actual detach/contact/forces/whole mesh box settlement grade simulation and can terminate it. They are outside neural/helper inputs. Hardware needs separate completion and safety evidence'),
          dict(id='HISTORICAL_CALIBRATION_PROVISIONAL',severity='physical_validation_required',detail=hardware['calibration_note'])],
        evidence=dict(tcp_provider=source_evidence('scripts/eval_student60_timing.py','tcp=(arm_from_world'),
            neural_state=source_evidence('src/harvest_robot/harvest_rl/target_contract.py','return torch.cat'),
            simulator_output=source_evidence('src/harvest_robot/harvest_runtime/student60.py','write_joint_stiffness_to_sim'),
            grip_proxy=source_evidence('src/harvest_robot/harvest_runtime/student60_observed_closure.py','stalled='),
            camera_pose=source_evidence('src/harvest_robot/harvest_sensors/isaac_rig.py',"data.pos_w")),
        references=['https://ftservo.github.io/ftservo-wiki/reference/parameter/memory-sts/',
            'https://ftservo.github.io/ftservo-wiki/en/products/models/st-3215-c018/main/',
            'https://gitee.com/ftservo/FTServo_Python/blob/main/scservo_sdk/sms_sts.py'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(report=str(a.output.resolve()),classes_checked=guard['classes_checked'],
        historical_samples=hardware['captured_position_samples'],causal_velocity_windows=hardware['causal_velocity_windows_checked'],
        baseline_unchanged=unchanged,hardware_io=False)))


if __name__=='__main__':main()
