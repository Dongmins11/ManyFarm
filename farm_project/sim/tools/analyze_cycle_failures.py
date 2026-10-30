"""완료된 반복 시험의 실패 근거를 추출한다. ROS/시뮬 명령은 보내지 않는다."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[2]


def save(path: Path, data: dict) -> None:
    """분석 산출물만 원자적으로 교체한다."""
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def arc_point(origin: list, radius: float, angle: float) -> tuple:
    """평가용 원호 좌표. 실제 제어 입력에는 사용하지 않는다."""
    x, y = -radius * math.sin(angle), -radius * (1 - math.cos(angle))
    c, s = math.cos(origin[2]), math.sin(origin[2])
    return origin[0] + c*x - s*y, origin[1] + s*x + c*y


def analyze(trial: Path, entry: dict, destination: Path) -> dict:
    """로그 판정과 추정 재구성을 구분해 시도별 증거를 보존한다."""
    result_path = trial / 'result.json'
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    error = result.get('error', entry.get('error', ''))
    reasons = []
    for key in ('dock_final', 'pickup_final'):
        reply = result.get(key, {})
        if reply.get('result', {}).get('result_code') not in (None, 'SUCCESS'):
            reasons.append(reply.get('reason') or reply['result'].get('error_message', ''))
    # DOCK_READY 이전 실패는 최종 reply 대신 예외에 원문 JSON이 남는다.
    if ': {' in error:
        try:
            reply = json.loads(error[error.index('{'):])
            reasons.append(reply.get('reason') or reply.get('result', {}).get('error_message', ''))
        except ValueError:
            pass
    lines = (trial / 'harvest.log').read_text(errors='replace').splitlines() if (trial / 'harvest.log').exists() else []
    evidence = [dict(line=i+1, text=line) for i, line in enumerate(lines)
                if any(s in line for s in ('arc deviation exceeded', '곡선 경로 위치 오차',
                    'HANDOFF_WAIT', 'HANDOFF_RESUMED', 'Running spin', 'Turning ',
                    'spin completed successfully'))]
    text = '\n'.join(reasons) + '\n' + '\n'.join(x['text'] for x in evidence)
    category = ('arc_deviation' if any(x in text for x in ('arc deviation exceeded', '곡선 경로 위치 오차'))
                else 'reentry_heading' if '복귀 원호 재진입' in text else 'unclassified')
    stages = []
    for path in (trial / 'input_trace').glob('*.jsonl'):
        with path.open('rb') as stream:
            for line in stream:
                if b'"event": "stage_' not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get('stage', '').startswith('HandoffPlanner'):
                    stages.append(row)
    session = None
    events = trial / 'events.jsonl'
    if events.exists():
        with events.open('rb') as stream:
            for line in stream:
                if b'"kind": "basket_alignment"' not in line:
                    continue
                try:
                    session = json.loads(line).get('data', {}).get('session')
                except ValueError:
                    continue
                if session:
                    break
    captures = [s for s in stages if s['stage'] == 'HandoffPlanner.capture' and s['event'] == 'stage_end']
    reconstruction = []
    origin_age = None
    drive = ROOT / 'sim/runs/drive_diagnostics' / str(session) / 'harvest_01.jsonl'
    if captures and drive.exists():
        capture_time = captures[0]['mono_ns'] / 1e9
        origin = None
        with drive.open() as stream, (destination / 'drive_handoff.jsonl').open('w') as output:
            for line in stream:
                row = json.loads(line)
                if row['monotonic_s'] <= capture_time:
                    origin = row
                    continue
                if origin is None:
                    continue
                output.write(line)
                od = origin['wheel_odom'][:3]
                a = origin['T_world_base']
                wp = [a[0][3], a[1][3], math.atan2(a[1][0], a[0][0])]
                q = row['wheel_odom']
                b = row['T_world_base']
                w = [b[0][3], b[1][3], math.atan2(b[1][0], b[0][0])]
                angle = math.atan2(math.sin(q[2]-od[2]), math.cos(q[2]-od[2]))
                wa = math.atan2(math.sin(w[2]-wp[2]), math.cos(w[2]-wp[2]))
                spec = json.loads((trial / 'runtime/handoff.json').read_text())['arc'] if not reconstruction else spec
                extent, radius = spec['angle'], spec['radius']
                expected = arc_point(od, radius, min(extent, max(0, angle)))
                world_expected = arc_point(wp, radius, min(extent, max(0, wa)))
                origin_age = capture_time - origin['monotonic_s']
                reconstruction.append(dict(sim_s=row['sim_time_s'], mono_s=row['monotonic_s'],
                    odom_deviation_mm=1000*math.dist(q[:2], expected),
                    world_deviation_mm=1000*math.dist(w[:2], world_expected),
                    yaw_from_origin_deg=math.degrees(angle),
                    command=row['applied_cmd_mps_rps'], measured=q[3:]))
    report = dict(attempt=entry['attempt'], success=entry['success'], category=category,
        error=error, reasons=reasons, session=session, log_evidence=evidence, stages=stages,
        drive_source=str(drive), origin_sample_age_s=origin_age,
        reconstruction_scope='capture 직전 1초 주기 진단표본 기준 근사 재구성. 제어기의 정확한 TF 표본 아님. departure/return 외 wall/retreat 구간 원호 오차는 실패 판정에 사용하지 말 것.',
        samples=reconstruction)
    save(destination / 'diagnosis.json', report)
    (destination / 'evidence.md').write_text(
        f"# 시도 {entry['attempt']} 실패 분석\n\n분류: `{category}`\n\n" +
        '\n'.join('- ' + reason for reason in reasons) + '\n\n' +
        f"원본: `{trial}`\n\n" + report['reconstruction_scope'] + '\n\n```text\n' +
        '\n'.join(f"harvest.log:{r['line']} {r['text']}" for r in evidence) + '\n```\n')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    base = args.run.resolve()
    if not base.is_relative_to(ROOT / 'sim/runs'):
        raise ValueError('sim/runs 내부 시험만 분석합니다.')
    output = base / 'failure_analysis'
    output.mkdir(exist_ok=True)
    while True:
        state = json.loads((base / 'status.json').read_text())
        for entry in state['attempts']:
            if entry.get('success') is not False:
                continue
            dest = output / f"attempt_{entry['attempt']:03d}"
            if (dest / 'diagnosis.json').exists():
                continue
            dest.mkdir(exist_ok=True)
            try:
                report = analyze(Path(entry['path']), entry, dest)
                print(f"분석 저장: {dest} ({report['category']})", flush=True)
            except (OSError, ValueError, KeyError) as error:
                save(dest / 'analysis_error.json', dict(error=str(error)))
                print(f'분석 재시도 예정: {dest}: {error}', flush=True)
        save(output / 'watch_status.json', dict(updated_at=datetime.now(timezone.utc).isoformat(),
            experiment_state=state['state'], current=state.get('current'),
            analyzed=[p.parent.name for p in sorted(output.glob('attempt_*/diagnosis.json'))]))
        if not args.watch or state['state'] in ('SUCCEEDED', 'STOPPED'):
            return
        time.sleep(10)


if __name__ == '__main__':
    main()
