"""Continue a live camera regression into audited, frozen fresh-scene evaluation."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
from run_student60_after_collection import stop_owned_process

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    try:return json.loads(Path(path).read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None


def is_native_command(args):
    # Only the invoked Python script identifies a job. An evaluator supplied
    # as a watcher's --evaluator value is not another Isaac process.
    script=next((v for v in args[1:] if v not in ('-u','-B','-s','-E','-I','-O','-OO')),None)
    return bool(script and (Path(script).name.startswith(('eval_student60','collect_student60'))
        or Path(script).name in ('view_student60_camera.py','preview_u20_wrist.py',
            'benchmark_student60_latency.py')) and Path(script).suffix=='.py')


def active_native_outputs():
    if Path('/proc/1/comm').read_text().strip() not in ('systemd','init'):raise RuntimeError('Host visibility required')
    live=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            args=[v.decode() for v in (p/'cmdline').read_bytes().split(b'\0') if v]
            if not is_native_command(args):continue
            if '--output' in args:
                target=Path(args[args.index('--output')+1])
            else:
                # The live U20 preview can choose its output internally. Use
                # its actual script path as an identity for the overlap guard.
                target=Path(next(v for v in args[1:] if v.endswith('.py')))
            target=target if target.is_absolute() else (p/'cwd').resolve()/target
            live.append((int(p.name),target.resolve()))
        except (OSError,UnicodeError,ValueError,IndexError):pass
    return live


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['regression','data','checkpoint','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--evaluator',choices=['eval_student60_active_view.py','eval_student60_lifted.py','eval_student60_reobserved.py','eval_student60_box_outcome.py','eval_student60_bounded_box.py','eval_student60_standoff_box.py','eval_student60_side_scan_box.py','eval_student60_finite_load_box.py','eval_student60_flexible_box.py','eval_student60_faster_capture_box.py'],default='eval_student60_active_view.py')
    p.add_argument('--minimum-regression-successes',type=int,choices=[3,4],default=3)
    p.add_argument('--center-correction',type=Path)
    p.add_argument('--fresh-seed',type=int,default=106143);a=p.parse_args()
    a.regression=a.regression.resolve();a.output=a.output.resolve();a.data=a.data.resolve();a.checkpoint=a.checkpoint.resolve()
    a.output.mkdir(exist_ok=False);py='/home/bhc/isaac/env_isaaclab/bin/python';child=None
    status=dict(state='WAITING_REGRESSION',pid=os.getpid(),regression=str(a.regression),fresh_seed=a.fresh_seed)
    def write(**changes):
        status.update(changes,checked_unix_s=time.time())
        tmp=a.output/'status.json.tmp';tmp.write_text(json.dumps(status,indent=2)+'\n');tmp.replace(a.output/'status.json')
    def run(command,log_name,timeout):
        nonlocal child
        with (a.output/log_name).open('x') as log:
            child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
            write(child_pid=child.pid,command=command)
            deadline=time.monotonic()+timeout
            while child.poll() is None:
                if time.monotonic()>deadline:stop_owned_process(child);raise TimeoutError(log_name)
                result=read(a.output/'fresh_test/result.json')
                if result:write(fresh_progress={k:result.get(k) for k in ['executed_attempts','planned_attempts','successes','placement_quality_successes']})
                time.sleep(5)
            if child.returncode:raise RuntimeError(log_name+' exit '+str(child.returncode))
    try:
        deadline=time.monotonic()+2400
        while True:
            regression=read(a.regression/'result.json') or {};live=active_native_outputs()
            write(regression_progress={k:regression.get(k) for k in ['completed','executed_attempts','planned_attempts','successes']},native_pids=[x[0] for x in live])
            if not any(path==a.regression for _,path in live):
                if regression.get('completed'):break
                if (a.regression/'diagnostic_stop.json').exists():
                    raise RuntimeError('Regression intentionally stopped for diagnosis; no fresh test')
                if (a.regression/'error.json').exists() or regression.get('finished_utc'):
                    raise RuntimeError('Regression incomplete; preserve evidence and do not launch a test')
            if time.monotonic()>deadline:raise TimeoutError('Regression wait')
            time.sleep(5)
        write(state='AUDITING_REGRESSION')
        run([py,'scripts/verify_student60_evaluation_artifacts.py','--evaluation',str(a.regression),
            '--contract',str(a.data),'--output',str(a.output/'regression_audit.json')],'regression_audit.log',120)
        audit=read(a.output/'regression_audit.json')
        if (regression.get('success_criterion') not in ['harvest_outcome_v1','box_outcome_v2'] or regression['planned_attempts']!=4
                or audit['outcome_successes']<a.minimum_regression_successes):
            write(state='NEEDS_FURTHER_CORRECTION',reason=f'Require at least{a.minimum_regression_successes}/4 actual audited regression harvests before fresh test',regression_audit=audit)
            return
        if active_native_outputs():raise RuntimeError('Another native job appeared; do not overlap')
        pins=read(a.regression/'evaluation_source_pins.json')
        if str(ROOT/'scripts'/a.evaluator) not in pins:raise RuntimeError('Fresh evaluator differs from regression')
        center_path=str(a.center_correction.resolve()) if a.center_correction else None
        if regression.get('center_correction_checkpoint')!=center_path:raise RuntimeError('Fresh camera correction differs from regression')
        for name,expected in pins.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Candidate source changed after regression: '+name)
        if a.fresh_seed==regression['seed']:raise RuntimeError('Fresh seed overlaps regression')
        write(state='FROZEN_FRESH_TEST',frozen_source_pins=pins,regression_outcome_successes=audit['outcome_successes'])
        test=a.output/'fresh_test'
        command=[py,'scripts/'+a.evaluator,'--checkpoint',str(a.checkpoint),'--data',str(a.data),
            '--output',str(test),'--seed',str(a.fresh_seed),'--per-color','2','--split','test',
            '--wall-seconds','2400','--episode-wall-seconds','600','--cache-camera-maps','--fast-native-depth',
            '--detector-device','cuda:0','--visual-servo','--entry-jaw-gate','--headless','--execute']
        if a.center_correction:command+=['--center-correction',center_path]
        run(command,'fresh_test.log',2550)
        write(state='AUDITING_FRESH_TEST')
        run([py,'scripts/verify_student60_evaluation_artifacts.py','--evaluation',str(test),'--contract',str(a.data),
            '--output',str(a.output/'fresh_test_audit.json')],'fresh_test_audit.log',120)
        result=read(test/'result.json')
        if not result.get('completed'):raise RuntimeError('Fresh evaluation incomplete')
        (test/'evaluation_role.json').write_text(json.dumps(dict(role='fresh_test_frozen_after_regression',independent=True,
            selection_regression=str(a.regression),seed=a.fresh_seed),indent=2)+'\n')
        write(state='COMPLETED',result=result,fresh_audit=read(a.output/'fresh_test_audit.json'))
        print('CAMERA_FOLLOWTHROUGH_COMPLETED',result['successes'],'/',result['planned_attempts'],flush=True)
    except BaseException as exc:
        if child is not None and child.poll() is None:stop_owned_process(child)
        write(state='FAILED',error=repr(exc));raise


if __name__=='__main__':main()
