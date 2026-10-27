"""고정 명령 어댑터. 브라우저에서 쉘/파일 경로를 입력받지 않는다."""
from pathlib import Path
import json
import os
import shlex
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parent


def run(argv: list, *, data: str | None = None, timeout: int = 45) -> dict:
    result = subprocess.run(argv, input=data, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-3000:])
    # ROS 설정 스크립트의 안내 출력과 최종 JSON을 구분한다.
    return json.loads(result.stdout.strip().splitlines()[-1])


class Backend:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.last_permit = None

    def robot(self, action: str, **kwargs: object) -> dict:
        req = dict(action=action, journal=self.config['robot_journal'], **kwargs)
        command = 'python3 - ' + shlex.quote(json.dumps(req))
        return run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                    self.config['robot_ssh'], command], data=(ROOT/'robot_agent.py').read_text())

    def dummy(self, action: str, **kwargs: object) -> dict:
        cfg = self.config; req = dict(action=action, robot_id=cfg['robot_id'], **kwargs)
        backup = None
        if action == 'recover':
            raw = Path(cfg['dummy_journal']).read_bytes()
            json.loads(raw)  # 읽기 실패/손상 시 복구 요청을 보내지 않는다.
            folder = Path(cfg['state_dir'])/'dummy-backups'
            folder.mkdir(parents=True, exist_ok=True)
            backup = folder/(str(time.time_ns())+'.json')
            with backup.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        sources = ['/opt/ros/jazzy/setup.bash', cfg['project_setup'], cfg['dummy_root']+'/install/setup.bash']
        shell = '\n'.join('source '+shlex.quote(p) for p in sources)
        shell += '\nexec python3 '+shlex.quote(str(ROOT/'ros_probe.py'))+' '+shlex.quote(json.dumps(req))
        env = os.environ.copy()
        for name in ('ROS_STATIC_PEERS', 'ROS_DISCOVERY_SERVER', 'ROS_LOCALHOST_ONLY',
                     'FASTRTPS_DEFAULT_PROFILES_FILE', 'FASTDDS_DEFAULT_PROFILES_FILE'):
            env.pop(name, None)
        env.update(ROS_DOMAIN_ID='177', RMW_IMPLEMENTATION='rmw_cyclonedds_cpp', ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST',
            CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="lo"/></Interfaces><AllowMulticast>false</AllowMulticast></General><Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>32</MaxAutoParticipantIndex><Peers><Peer Address="127.0.0.1"/></Peers></Discovery></Domain></CycloneDDS>')
        result = subprocess.run(['bash', '-c', shell], env=env, capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-3000:])
        response = json.loads(result.stdout.strip().splitlines()[-1])
        if action == 'repeat_last_harvest' and response.get('success') is True:
            self.last_permit = dict(expires_at=time.time()+300, message=response.get('message'))
        if action in ('recover', 'stop'):
            self.last_permit = None
        if backup is not None:
            response['journal_backup'] = str(backup)
        return response

    def control(self) -> dict:
        with urllib.request.urlopen(self.config['web_control'], timeout=4) as response:
            data = json.load(response)
        # 관제 토큰/운송 데이터는 브라우저로 전달하지 않는다.
        return {key: data.get(key) for key in ('ready', 'paused', 'robot_paused', 'blocked_reasons')}

    def runtime(self) -> dict:
        command = "source " + shlex.quote(self.config["robot_environment"]) + "; python3 -"
        return run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", self.config["robot_ssh"], command], data=(ROOT/"robot_observe.py").read_text(), timeout=15)

    def status(self) -> dict:
        result = {'observed_at': time.time(), 'permit': self.last_permit}
        for key, call in [('robot', lambda: self.robot('status')), ('runtime', self.runtime), ('dummy', lambda: self.dummy('status')), ('control', self.control)]:
            try:
                result[key] = call()
            except Exception as error:
                result[key] = {'error': str(error)}
        return result

    def perform(self, action: str, body: dict) -> dict:
        if action == 'robot_stop':
            if body.get('confirmed') is not True:
                raise ValueError('수확 시험 전체 종료 확인이 필요합니다.')
            return self.robot('stop')
        if action == 'robot_reconcile':
            if body.get('station_confirmed') is not True:
                raise ValueError('실제 스테이션 위치·방향 재배치 확인이 필요합니다.')
            return self.robot('reconcile', snapshot=body['snapshot'], station_confirmed=True)
        mapping = {'dummy_recover': 'recover', 'dummy_prepare': 'prepare', 'dummy_stop': 'stop', 'dummy_repeat': 'repeat_last_harvest'}
        if action in mapping:
            return self.dummy(mapping[action])
        if action == 'dummy_count':
            return self.dummy('count', count=body.get('count'))
        raise ValueError('허용하지 않은 작업')
