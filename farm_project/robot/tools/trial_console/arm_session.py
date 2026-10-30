"""PC 웹의 지속 SSH 시험 연결. 장치 요청의 수락/결과는 원격 이벤트로만 표시한다."""
from collections import deque
from pathlib import Path
import base64
import json
import os
import shlex
import subprocess
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent
COMMANDS = {'harvest', 'discharge', 'prepare', 'stop', 'cancel', 'get_operation', 'recover', 'disconnect', 'transfer_test', 'station_return', 'station_cancel', 'move_trial', 'move_trial_cancel'}
MUTATING = {'harvest', 'discharge', 'prepare', 'stop', 'cancel', 'recover', 'transfer_test', 'station_return', 'station_cancel', 'move_trial', 'move_trial_cancel'}


class ArmSession:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._lock = threading.RLock()
        self._process = None
        self._events: deque = deque(maxlen=600)
        self._snapshot = {}
        self._snapshot_at = 0.
        self._connected = False
        self._generation = 0
        self._audit = Path(config['state_dir'])/'arm-audit.jsonl'

    def _record(self, event: dict) -> None:
        with self._lock:
            self._audit.parent.mkdir(parents=True, exist_ok=True)
            with self._audit.open('a') as stream:
                stream.write(json.dumps(event, ensure_ascii=False)+'\n')
                stream.flush()
            if event.get('kind') != 'snapshot':
                self._events.append(event)

    def connect(self) -> dict:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return {'connected': self._connected, 'note': '기존 시험 연결 사용'}
            cfg = self._config
            profile = json.loads(Path(cfg['arm_profile']).read_text())
            arm = profile['arm_action']
            request = dict(robot_id=profile['robot_id'], map_id=profile['map_id'], control_aliases=profile.get('control_aliases',{}),
                readiness_timeout_s=arm['readiness_timeout_s'], response_timeout_s=arm['response_timeout_s'],
                execution_timeout_s=arm['execution_timeout_s'], cancel_timeout_s=arm['cancel_timeout_s'])
            script = base64.b64encode((ROOT/'arm_agent.py').read_bytes()).decode()
            code = 'import base64;exec(compile(base64.b64decode('+repr(script)+'),"trial_console_arm_agent","exec"))'
            command = 'set -e\nsource '+shlex.quote(cfg['robot_environment'])
            command += '\nsource '+shlex.quote(cfg['robot_arm_setup'])
            command += '\nexec python3 -u -c '+shlex.quote(code)+' '+shlex.quote(json.dumps(request))
            self._record({'kind':'connect_requested','at':time.time(),'host':cfg['robot_ssh']})
            process = subprocess.Popen(['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=5',
                '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',cfg['robot_ssh'],'bash -c '+shlex.quote(command)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            self._process = process
            self._connected = False
            self._snapshot, self._snapshot_at = {}, 0.
            self._generation += 1
            generation = self._generation
            threading.Thread(target=self._read, args=(process,generation), daemon=True).start()
            threading.Thread(target=self._stderr, args=(process,), daemon=True).start()
            return {'connecting':True}

    def _stderr(self, process: subprocess.Popen) -> None:
        for line in process.stderr:
            self._record({'kind':'connection_log','at':time.time(),'message':line.rstrip()[:3000]})

    def _read(self, process: subprocess.Popen, generation: int) -> None:
        try:
            for line in process.stdout:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict) or 'kind' not in event:
                        raise ValueError('이벤트 형식 아님')
                except (ValueError, TypeError):
                    self._record({'kind':'connection_log','at':time.time(),'message':line.rstrip()[:3000]})
                    continue
                with self._lock:
                    if generation != self._generation:
                        continue
                    if event['kind'] == 'connected':
                        self._connected = True
                    if event['kind'] == 'snapshot':
                        self._snapshot, self._snapshot_at = event, time.time()
                self._record(event)
        finally:
            code = process.wait()
            with self._lock:
                if generation == self._generation:
                    self._connected = False
            self._record({'kind':'disconnected','at':time.time(),'exit_code':code,
                          'note':'연결 종료는 팔 작업 종료 확인이 아닙니다. 미확정 작업은 GetOperation으로 대조하세요.'})

    def station_target(self) -> dict:
        """서버 설정의 복귀 목적지를 읽는다. 좌표나 노드 번호를 브라우저에서 받지 않는다."""
        if not self._config.get('station_return_config'):
            return {}
        import yaml
        data = yaml.safe_load(Path(self._config['station_return_config']).read_text())
        target = data['stations'][self._config['robot_id']]
        return dict(station_id=target['station_id'], node_id=target['node_id'],
                    map_id=self._config.get('station_return_map_id', data['map_id']))

    def navigation_target(self) -> dict:
        """기존 dinit 설정과 실물 그래프에서 시험 주행 자세를 읽는다. 초기위치는 발행하지 않는다."""
        import math
        filename = self._config.get('navigation_trial_config')
        if not filename:
            return {}
        data = json.loads(Path(filename).read_text())
        root = Path(self._config['project_root'])
        graph = json.loads((root/data['route_graph']).read_text())
        nodes = {f['properties']['id']: f['geometry']['coordinates'] for f in graph['features']
                 if f['geometry']['type'] == 'Point'}
        xy, other = nodes[data['node_id']], nodes[data['face_away_from_node_id']]
        yaw = math.atan2(xy[1]-other[1], xy[0]-other[0])
        return dict(node_id=data['node_id'], pose=dict(header=dict(frame_id=data['frame_id']),
            pose=dict(position=dict(x=xy[0], y=xy[1], z=0.), orientation=dict(
                x=0., y=0., z=math.sin(yaw/2), w=math.cos(yaw/2)))))

    def send(self, action: str, body: dict) -> dict:
        if action not in COMMANDS:
            raise ValueError('지원하지 않는 팔 시험 명령')
        if action in MUTATING and body.get('confirmed') is not True:
            raise ValueError('실제 장치 명령 전송 확인이 필요합니다.')
        if action == 'transfer_test' and type(body.get('enabled')) is not bool:
            raise ValueError('배출 시험 enabled는 bool이어야 합니다.')
        if action == 'recover' and body.get('reconciled') is not True:
            raise ValueError('실제 장치·적재량 대조 확인이 필요합니다.')
        if action == 'station_return':
            from datetime import datetime, timezone
            target = self.station_target()
            robot_id = self._config['robot_id']
            # 브라우저가 좌표·목표·업무 ID를 덮어쓰지 못하게 서버 설정에서 구성한다.
            body = dict(confirmed=True, goal=dict(robot_id=robot_id,
                task_id='station-return-'+uuid.uuid4().hex, station_id=target['station_id'],
                map_id=target['map_id'],
                timestamp=datetime.now(timezone.utc).isoformat()))
        if action == 'move_trial':
            body = dict(confirmed=True, goal=dict(pose=self.navigation_target()['pose']))
        with self._lock:
            if self._process is None or self._process.poll() is not None or not self._connected:
                raise ValueError('팔 시험 연결부터 시작하세요.')
            request = {'id':uuid.uuid4().hex, 'action':action, 'body':body}
            self._record({'kind':'requested','at':time.time(),**request})
            self._process.stdin.write(json.dumps(request, ensure_ascii=False)+'\n')
            self._process.stdin.flush()
            return {'id':request['id'], 'queued':True, 'note':'웹 요청 접수. 로봇 수락/최종 결과는 이벤트에서 확인'}

    def view(self) -> dict:
        with self._lock:
            age = None if not self._snapshot_at else max(0.,time.time()-self._snapshot_at)
            return {'navigation':self.navigation_target(), 'station':self.station_target(), 'connected':self._connected, 'snapshot':self._snapshot, 'age_s':age,
                    'stale':age is None or age>2.5, 'events':list(self._events)}

    def close(self) -> None:
        """웹 종료 시 stdin을 닫아 자신이 만든 관찰 클라이언트만 정리한다."""
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                process.stdin.close()
