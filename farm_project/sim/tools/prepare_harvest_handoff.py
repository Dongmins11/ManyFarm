"""기존 시뮬 설정에서 선택형 수확 인계 실행 묶음을 생성한다. 원본 설정은 보존한다."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'sim/ros_ws/src/farm_sim_config/config'
SOURCE = 'e135cdef9462276cc25d9fa336f084e2dcac72e4'


def prepare(out: Path) -> dict:
    out = out.resolve()
    if not out.is_relative_to(ROOT/'sim/runs') or out.exists():
        raise ValueError('sim/runs 아래 아직 없는 실행 경로가 필요합니다.')
    out.mkdir(parents=True)
    def relative(path: Path) -> str:return str(path.relative_to(ROOT))
    def write(name: str, data: dict) -> str:
        path = out/name
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        return relative(path)
    source_path = 'farm_project/robot/config/harvest/harvest_handoff_real.json'
    raw = subprocess.check_output(['git','show',SOURCE+':'+source_path],cwd=ROOT)
    source_config = json.loads(raw)
    source_environment = yaml.safe_load(subprocess.check_output(['git', 'show', SOURCE+
        ':farm_project/robot/config/environments/harvest_handoff_real.yaml'], cwd=ROOT))
    transfer = source_config['transfer']
    source_transfer = copy.deepcopy(transfer)
    transfer['device_services'] = {op:'/harvest_01/sim/transfer/'+op for op in ('prepare_arm','stop')}
    transfer['discharge_action']['endpoint'] = '/harvest_01/sim/discharge'
    transfer['journal_path'] = str(out/'journal/transfer.json')
    task = json.loads((CONFIG/'harvest_task.json').read_text())
    task['transfer'] = transfer
    # 인계 선택 시 실물의 주행 재시도 정책도 함께 가져온다. 일반 팔 단독 실행에는 적용하지 않는다.
    task['navigation_collision_retry_count'] = source_config['navigation_collision_retry_count']
    # 관제 워커가 준비/작업/인계 상태를 받도록 원본의 선택형 보고를 연결한다.
    task['status_reporting'] = copy.deepcopy(source_config['status_reporting'])
    task['status_reporting']['map_id'] = task['map_id']
    task_path = write('harvest_task.json',task)
    devices = json.loads((CONFIG/'harvest.json').read_text())
    devices['runtime']['harvest_transfer'] = {'enabled':True}
    devices['runtime']['state_clock_delay_s'] = .1
    device_path = write('harvest.json',devices)
    handoff = json.loads((ROOT/'robot/config/robots/vicpinky/transfer/handoff_fsm.json').read_text())
    sources = {}
    numeric_changes = []
    for key in ('wall_config','monitor_policy'):
        path = ROOT/handoff[key]
        sources[handoff[key]] = hashlib.sha256(path.read_bytes()).hexdigest()
        data = json.loads(path.read_text())
        if key == 'wall_config':
            # 2026-10-28 사용자 승인: 시뮬 잔류 회전 대응용 임시 허용각.
            before = data['controller']['angle_tolerance']
            data['controller']['angle_tolerance'] = math.radians(.8)
            numeric_changes.append(dict(field='wall.controller.angle_tolerance',
                before=before, after=data['controller']['angle_tolerance'], unit='rad',
                scope='sim only, temporary', reason='2026-10-28 user approved 0.8 degree tolerance'))
        handoff[key] = write(path.name,data)
    handoff_path = write('handoff.json',handoff)
    profile = yaml.safe_load((CONFIG/'harvest_runtime.yaml').read_text())
    # map/base frame은 시뮬 좌표계를 유지하고 실제 인계 프로필의 최종 도착 한도를 사용한다.
    profile['navigation']['heading_tolerance_rad'] = source_environment['navigation']['heading_tolerance_rad']
    if profile.get('station_return_components', False):
        # 인계 출력 소유자가 연결된 실행에서만 실물과 같은 복귀 충돌 재시도를 허용한다.
        profile['station_return_navigation']['collision_retry_count'] = task['navigation_collision_retry_count']
    profile['harvest_config'], profile['device_config'] = task_path, device_path
    (out/'harvest_runtime.yaml').write_text(yaml.safe_dump(profile,sort_keys=False))
    fleet = json.loads((CONFIG/'transport_fleet.json').read_text())
    fleet['device_configs'] = [device_path if p.endswith('/harvest.json') else p for p in fleet['device_configs']]
    write('fleet.json',fleet)
    changes = {'source_commit':SOURCE,'transfer_source':source_path,'source_transfer':source_transfer,
               'selected_transfer':transfer,'handoff_input_hashes':sources,
               'numeric_handoff_changes':numeric_changes,
               'real_policy_applied': {
                   'navigation.heading_tolerance_rad': profile['navigation']['heading_tolerance_rad'],
                   'navigation_collision_retry_count': task['navigation_collision_retry_count']},
               'environment_changes':['mode=sim/use_sim_time=true',
                   'global TF; harvest_01/scan', 'sim device endpoints', 'independent journal',
                   'device state_clock_delay_s=0.1 (existing transport sensor timing policy)',
                   'source status_reporting enabled with sim map_id'],
               'traffic_enabled':False,'actual_discharge_count_valid':False}
    write('source_adaptations.json',changes)
    return {'environment_config':relative(out/'harvest_runtime.yaml'),'handoff_config':handoff_path,
            'fleet_config':relative(out/'fleet.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output),indent=2))
