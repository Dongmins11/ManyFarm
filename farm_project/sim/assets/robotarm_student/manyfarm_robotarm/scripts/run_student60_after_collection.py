#!/usr/bin/env python3
"""Opt-in queue: wait for Student60 collection, train one BC baseline, summarize.

Does not modify the collector, start simulation evaluation, or use hardware.
"""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import signal
import statistics
import subprocess
import time

from monitor_student60 import ROOT, ProcessProbe, discover, duration, option, planned_colors

KST = timezone(timedelta(hours=9))


def read(path):
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def write(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def qualify(plan, version='student60_executed_targets_servo_v1'):
    if not plan.get('ready_for_initial_bc') or plan.get('student60_version') != version:
        raise ValueError('Data is not an approved Student60 BC plan')
    for split, minimum in (('train', 50), ('validation', 10)):
        episodes = plan.get(split, [])
        if len(episodes) < minimum or {e.get('color') for e in episodes} != {'Red', 'Yellow'}:
            raise ValueError(f'{split}: need >= {minimum} successful demonstrations and both colors')
    return plan.get('summary', {})


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def collection_gate(collection, prepared, *, batches=None, allowed_parents=(), data_path=None):
    """Check every planned batch; the trainer checks all prepared sample hashes."""
    plan = read(collection/'plan.json') or {}
    batches = plan.get('batches') if batches is None else batches
    if not batches:
        raise ValueError('Collection has no planned batches')
    approved_roots = {'train': set(), 'validation': set()}
    source_pins = {}
    outcomes = {}
    checked = []
    indexed_files = prepared.get('files', {})
    parents = {collection, *(Path(p).resolve() for p in allowed_parents)}
    for batch in batches:
        destination = Path(batch['destination']).resolve()
        scratch = Path(batch['scratch']).resolve()
        if destination.parent not in parents or scratch.parent not in parents:
            raise ValueError('Batch paths do not belong to this collection')
        split = option(batch['command'], '--split')
        if split not in approved_roots or destination in approved_roots[split]:
            raise ValueError('Invalid or repeated batch split')
        expected = len(planned_colors(batch['command']))*int(option(batch['command'], '--per-color', '2'))
        for flag in ('error.json', 'DO_NOT_TRAIN.json', 'COLLECTION_IN_PROGRESS.json'):
            if (destination/flag).exists():
                raise ValueError(f'Unapproved batch: {destination.name}/{flag}')
        run = read(destination/'run.json') or {}
        audit = read(destination/'verification.json') or {}
        manifest = read(destination/'dataset_manifest.json') or {}
        if not all(run.get(k) for k in ('completed', 'weights_unchanged', 'source_still_matches')):
            raise ValueError(f'Incomplete collection/source/weight check: {destination.name}')
        if not audit.get('audit_passed') or not audit.get('final_runtime_audit_complete'):
            raise ValueError(f'Native audit did not pass: {destination.name}')
        if manifest.get('split_role') != split or manifest.get('student60_version') != prepared.get('student60_version'):
            raise ValueError(f'Batch split/version mismatch: {destination.name}')
        proof_files = ['run.json', 'verification.json', 'dataset_manifest.json']
        if plan.get('compact_native'):
            if scratch.exists():
                raise ValueError(f'Compact export/cleanup is not finished: {destination.name}')
            cert = read(destination/'compact_certificate.json') or {}
            if cert.get('schema') != 'student60_audited_compact_v1' or not cert.get('native_images_fully_audited_before_export'):
                raise ValueError(f'Compact certification is missing: {destination.name}')
            if Path(cert.get('source', '')).resolve() != scratch:
                raise ValueError(f'Compact source mismatch: {destination.name}')
            proof_files.append('compact_certificate.json')
        if any(str(destination/name) not in indexed_files for name in proof_files):
            raise ValueError(f'Batch evidence is absent from the prepared hash index: {destination.name}')
        results = [read(p/'result.json') for p in sorted(destination.glob('episode_*'))]
        if len(results) != expected or audit.get('count') != expected or run.get('requested_episodes') != expected:
            raise ValueError(f'Planned attempts were not all completed: {destination.name}')
        for result in results:
            if not result or result.get('status') not in ('SUCCEEDED', 'FAILED', 'TIMED_OUT'):
                raise ValueError(f'Interrupted/error episode: {destination.name}')
            key = result['status']
            outcomes[key] = outcomes.get(key, 0)+1
        pins = run.get('source_pins', {})
        if not pins:
            raise ValueError(f'Missing source provenance: {destination.name}')
        for path, expected_sha in pins.items():
            if path in source_pins and source_pins[path] != expected_sha:
                raise ValueError('Source changed between collection batches: '+path)
            source_pins[path] = expected_sha
        approved_roots[split].add(destination)
        checked.append(destination.name)
    for split in approved_roots:
        for episode in prepared[split]:
            folder = Path(episode['path']).resolve()
            if folder.parent not in approved_roots[split] or (read(folder/'result.json') or {}).get('status') != 'SUCCEEDED':
                raise ValueError('Prepared episode is outside the approved successful split: '+str(folder))
    for path, expected_sha in source_pins.items():
        if file_sha(path) != expected_sha:
            raise ValueError('Current collection source differs from its frozen version: '+path)
    return dict(passed=True, checked_kst=datetime.now(KST).isoformat(),
        batches_checked=len(checked), batch_names=checked, episode_outcomes=outcomes,
        source_files_checked=len(source_pins), prepared_data_sha256=file_sha(data_path or collection/'data.json'),
        full_sample_hash_check='performed by trainer before optimizer updates')


def input_hash_gate(prepared):
    files = prepared.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Prepared input hash index is missing')
    for path, expected_sha in files.items():
        if file_sha(path) != expected_sha:
            raise ValueError('Prepared input changed: '+path)
    return dict(passed=True, input_files_checked=len(files))


def training_command(args, data, output):
    python = os.environ.get('HARVEST_PY', '/home/bhc/isaac/env_isaaclab/bin/python')
    return [python, '-u', str(ROOT/'scripts/train_student60.py'), '--data', str(data),
        '--output', str(output), '--epochs', str(args.epochs), '--patience', str(args.patience),
        '--batch-size', str(args.batch_size), '--workers', str(args.workers),
        '--learning-rate', str(args.learning_rate), '--seed', str(args.seed),
        '--verification-report', str(output.parent/'data_validation.json'), '--execute']


def summarize(train, reason, elapsed):
    rows = []
    metrics = train/'metrics.jsonl'
    if metrics.exists():
        for line in metrics.read_text().splitlines():
            try:
                row = json.loads(line)
                if isinstance(row.get('macro_mse'), (int, float)) and math.isfinite(row['macro_mse']):
                    rows.append(row)
            except (ValueError, TypeError):
                pass
    best = min(rows, key=lambda r: r['macro_mse']) if rows else None
    result = read(train/'result.json') or {}
    return dict(reason=reason, training_completed=bool(result.get('completed')),
        training_elapsed_seconds=elapsed, completed_epochs=len(rows),
        median_epoch_seconds=statistics.median([r['elapsed_s'] for r in rows]) if rows else None,
        best_epoch=best['epoch'] if best else None, best_validation=best,
        best_checkpoint=str(train/'student_best.pt') if (train/'student_best.pt').exists() else None,
        resume_checkpoint=str(train/'student_last.pt') if (train/'student_last.pt').exists() else None,
        harvest_success_evaluated=False,
        next_task='Student60-only closed-loop simulation evaluation; old increment-action runner is incompatible')


def stop_owned_process(proc):
    """Only the training process group created by this invocation is stopped."""
    if proc.poll() is not None:
        return
    for sig, wait in ((signal.SIGINT, 20), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            pass


def execute(args, collection, output, command):
    output.mkdir(parents=True, exist_ok=False)
    status_path = output/'status.json'
    status = dict(state='WAITING_COLLECTION', collection=str(collection), command=command, pid=os.getpid(),
        started_kst=datetime.now(KST).isoformat(), training_started=False,
        training_time_limit_hours=args.training_hours, collector_modified=False)
    write(output/'plan.json', status)
    write(status_path, status)
    print('JOB_OUTPUT', output, flush=True)
    proc = None
    started = None
    probe = ProcessProbe()
    absent_polls = 0
    data_path = collection/'data.json'

    def obtain(candidate, cause=None):
        nonlocal data_path
        if candidate is not None:
            try:
                qualify(candidate)
                approval = collection_gate(collection, candidate)
                approval['input_hash_check'] = input_hash_gate(candidate)
                return candidate, approval
            except (OSError, ValueError, KeyError) as exc:
                cause = repr(exc)
        if not args.auto_repair:
            raise RuntimeError('Collection approval failed; automatic repair disabled: '+str(cause))
        status.update(state='RECOVERING_COLLECTION', recovery_reason=str(cause), training_started=False)
        write(status_path, status)
        print('AUTO_RECOVERY', str(cause), flush=True)
        from student60_recovery import Recovery
        recovery = Recovery(collection, output/'recovery', max_batches=args.repair_batches,
            hours=args.repair_hours, qualify=qualify, gate=collection_gate, stop_process=stop_owned_process)
        data_path, prepared, approval = recovery.ensure()
        approval['input_hash_check'] = input_hash_gate(prepared)
        status['recovered_data'] = str(data_path)
        return prepared, approval
    try:
        deadline = time.monotonic()+args.wait_hours*3600
        last_notice = 0.
        while True:
            processes, full_visibility = probe.scan(collection, time.time())
            stopped = read(collection/'stopped.json')
            if stopped:
                if processes:
                    time.sleep(5); continue
                plan, approval = obtain(None, 'Collection stopped: '+str(stopped.get('error')))
                break
            plan = read(collection/'data.json')
            if plan and plan.get('ready_for_initial_bc'):
                if processes:
                    time.sleep(5)
                    continue
                status.update(state='CHECKING_COLLECTION')
                write(status_path, status)
                plan, approval = obtain(plan)
                break
            absent_polls = absent_polls+1 if full_visibility and not processes else 0
            if absent_polls >= 2:
                plan, approval = obtain(None, 'Collector disappeared before approved data.json')
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Collection wait limit exceeded; collector kept running')
            if time.monotonic()-last_notice >= 300:
                print('WAITING_COLLECTION: data.json 승인 완료를 기다립니다. 수집은 그대로 실행됩니다.', flush=True)
                last_notice = time.monotonic()
            time.sleep(30)
        status['data_summary'] = qualify(plan)
        write(output/'collection_validation.json', approval)
        status['collection_validation'] = str(output/'collection_validation.json')
        command = list(command)
        command[command.index('--data')+1] = str(data_path)
        command += ['--expected-data-sha256', approval['prepared_data_sha256']]
        status['command'] = command
        if shutil.disk_usage(output).free < 2*1024**3:
            raise RuntimeError('Need at least 2 GiB free before training')
        # The trainer verifies hashes/contracts once before optimizer updates.
        # Do not re-run native audits or start a second concurrent GPU job.
        status.update(state='VALIDATING_DATA', training_started=False)
        write(status_path, status)
        print('COLLECTION_CHECK_PASSED', json.dumps(approval, ensure_ascii=False), flush=True)
        print('VERIFY_DATA_THEN_BC', shlex.join(command), flush=True)
        started = time.monotonic()
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONUNBUFFERED='1')
        reason = 'COMPLETED'
        def observe(line):
            print(line, end='', flush=True)
            if line.startswith('STUDENT60_TRAINING_STARTED'):
                status.update(state='TRAINING', training_started=True,
                    training_started_kst=datetime.now(KST).isoformat(),
                    data_validation=str(output/'data_validation.json'))
        with (output/'train.log').open('x', buffering=1) as log:
            proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
            with (output/'train.log').open() as reader:
                while proc.poll() is None:
                    for line in reader:
                        observe(line)
                    elapsed = time.monotonic()-started
                    status.update(training_elapsed_seconds=elapsed,
                        training_time_left_seconds=max(0., args.training_hours*3600-elapsed))
                    write(status_path, status)
                    if elapsed >= args.training_hours*3600:
                        reason = 'TIME_LIMIT'
                        print('TRAINING_TIME_LIMIT: 저장된 epoch checkpoint를 보존하고 이번 학습만 종료합니다.', flush=True)
                        stop_owned_process(proc)
                        break
                    time.sleep(2)
                for line in reader:
                    observe(line)
        elapsed = time.monotonic()-started
        if proc.returncode != 0 and reason != 'TIME_LIMIT':
            reason = 'FAILED'
        if reason == 'COMPLETED' and not (read(output/'data_validation.json') or {}).get('verified'):
            reason = 'FAILED'
        summary = summarize(output/'train', reason, elapsed)
        write(output/'summary.json', summary)
        text = [f'학습 종료: {reason}', f'학습 경과: {duration(elapsed)}',
            f"완료 epoch: {summary['completed_epochs']}", f"최선 epoch: {summary['best_epoch']}",
            f"최선 모델: {summary['best_checkpoint']}", f"재개 모델: {summary['resume_checkpoint']}",
            'Student 자율 수확 성공률: 미평가',
            '다음: Student60 전용 폐루프 평가 연결 → 양 색상 smoke → 독립 배치 평가']
        (output/'summary.txt').write_text('\n'.join(text)+'\n')
        status.update(state=reason, finished_kst=datetime.now(KST).isoformat(), summary=str(output/'summary.json'))
        write(status_path, status)
        print('\n'.join(text), flush=True)
        if reason == 'FAILED':
            raise RuntimeError(f'Training exited {proc.returncode}; see {output / "train.log"}')
    except BaseException as exc:
        if proc is not None:
            stop_owned_process(proc)
        status.update(state='INTERRUPTED' if isinstance(exc, KeyboardInterrupt) else 'FAILED',
            error=repr(exc), finished_kst=datetime.now(KST).isoformat())
        write(status_path, status)
        if started is not None:
            write(output/'summary.json', summarize(output/'train', status['state'], time.monotonic()-started))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=Path, help='Student60 set 폴더; 생략하면 현재 최신 작업')
    parser.add_argument('--output', type=Path, help='새 작업 기록 폴더; 기본 runs/harvest_rl/student60_night_시각')
    parser.add_argument('--epochs', type=int, default=300)
    parser.add_argument('--patience', type=int, default=30)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--learning-rate', type=float, default=1e-4)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--training-hours', type=float, default=8, help='학습 시간 상한; 수집 대기 시간 제외')
    parser.add_argument('--wait-hours', type=float, default=24)
    parser.add_argument('--auto-repair', action=argparse.BooleanOptionalAction, default=True,
        help='Recover missing/corrupt batches and supplement insufficient successful data')
    parser.add_argument('--repair-batches', type=int, default=10, help='Maximum recollection attempts, only on approval failure')
    parser.add_argument('--repair-hours', type=float, default=3, help='Recovery wall-time limit, only on approval failure')
    parser.add_argument('--execute', action='store_true', help='사용자가 지정할 때만 대기·학습 실행')
    args = parser.parse_args()
    if min(args.epochs, args.patience, args.batch_size) < 1 or args.workers < 0 or not 0 < args.learning_rate < 1:
        parser.error('Invalid training options')
    if args.repair_batches < 1 or not all(math.isfinite(x) and x > 0 for x in (args.training_hours, args.wait_hours, args.repair_hours)):
        parser.error('Time limits must be positive finite hours')
    collection = (args.collection or discover()).resolve()
    if not read(collection/'plan.json'):
        parser.error('Collection plan.json is missing')
    output = (args.output or ROOT/'runs/harvest_rl'/('student60_night_'+datetime.now(KST).strftime('%Y%m%d_%H%M%S_%f'))).resolve()
    if output.exists() or output.is_relative_to(collection):
        parser.error('Use a new output outside the collection directory')
    command = training_command(args, collection/'data.json', output/'train')
    print('PLAN: 수집·자료 준비 완료 대기 → Student60 BC → 결과 요약', flush=True)
    print('COLLECTION', collection, 'OUTPUT', output, flush=True)
    print(shlex.join(command), flush=True)
    print('TRAINING_LIMIT', args.training_hours, 'hours; collection waiting excluded', flush=True)
    print('AUTO_REPAIR', args.auto_repair, 'limit', args.repair_batches, 'batches /', args.repair_hours, 'hours', flush=True)
    if not args.execute:
        print('CHECK_ONLY: add --execute to start waiting/training. No process started.', flush=True)
        return
    # One queue per dataset, even if the command is accidentally launched twice.
    lock_dir = ROOT/'runs/harvest_rl'
    lock_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(str(collection).encode()).hexdigest()[:16]
    with (lock_dir/f'.student60_queue_{key}.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('This collection already has an active Student60 BC queue')
        try:
            execute(args, collection, output, command)
        except KeyboardInterrupt:
            print('야간 작업 종료. 기존 수집기는 계속 실행됩니다.', flush=True)
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            parser.exit(1, str(exc)+'\n')


if __name__ == '__main__':
    main()
