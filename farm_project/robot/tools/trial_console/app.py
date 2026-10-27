#!/usr/bin/env python3
"""PC 로컬 반복 시험 콘솔. 기동/이동/초기위치/관제 버튼 API는 제공하지 않는다."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import secrets
import threading
import time
from backend import Backend

ROOT = Path(__file__).resolve().parent
ACTIONS = {'robot_stop', 'robot_reconcile', 'dummy_recover', 'dummy_prepare', 'dummy_stop', 'dummy_repeat', 'dummy_count', 'process_list', 'process_stop'}


class Console:
    def __init__(self, backend: object, state_dir: Path) -> None:
        self.backend = backend; self.state_dir = state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock(); self.pool = ThreadPoolExecutor(max_workers=1)
        self.active = None; self.jobs = []; self.snapshot = {}; self.refreshing = False
        self.token = secrets.token_urlsafe(32)

    def audit(self, entry: dict) -> None:
        with (self.state_dir/'audit.jsonl').open('a') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False)+'\n'); stream.flush()

    def refresh(self) -> None:
        with self.lock:
            if self.refreshing or self.active:
                return
            self.refreshing = True
        def work() -> None:
            try:
                value = self.backend.status()
                with self.lock:
                    self.snapshot = value
            finally:
                with self.lock:
                    self.refreshing = False
        self.pool.submit(work)

    def submit(self, action: str, body: dict) -> dict:
        if action not in ACTIONS:
            raise ValueError('허용하지 않은 작업')
        with self.lock:
            if self.active or self.refreshing:
                raise ValueError('다른 조회/작업 진행 중입니다. 완료 후 다시 시도하세요.')
            job = dict(id=secrets.token_hex(8), action=action, state='RUNNING', started_at=time.time())
            # 실행 전에 기록이 실패하면 작업을 시작하지 않는다.
            self.audit(dict(job, phase='requested', request=body))
            self.active = job['id']; self.jobs.append(job); self.jobs = self.jobs[-50:]
        def work() -> None:
            try:
                result = self.backend.perform(action, body)
                state = 'FAILED' if result.get('ok') is False or result.get('success') is False else 'SUCCEEDED'
            except Exception as error:
                result = {'error': str(error)}; state = 'FAILED'
            with self.lock:
                job.update(state=state, result=result, finished_at=time.time())
                try:
                    self.audit(dict(job, phase='finished'))
                finally:
                    self.active = None
            self.refresh()
        self.pool.submit(work)
        return dict(job)

    def view(self) -> dict:
        with self.lock:
            return dict(snapshot=self.snapshot, active=self.active, refreshing=self.refreshing, jobs=list(self.jobs), arm=self.backend.arm.view())


def handler(console: Console) -> type:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            pass

        def send(self, code: int, body: bytes, kind: str = 'application/json') -> None:
            self.send_response(code); self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body)

        def trusted(self) -> bool:
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                return False
            origin = self.headers.get('Origin')
            return origin is None or origin == 'http://'+expected

        def do_GET(self) -> None:
            if not self.trusted():
                self.send(403, b'{}'); return
            if self.path == '/api/state':
                self.send(200, json.dumps(console.view(), ensure_ascii=False).encode()); return
            if self.path == '/api/session':
                self.send(200, json.dumps({'token': console.token}).encode()); return
            files={'/': ('index.html','text/html; charset=utf-8'), '/app.js': ('app.js','text/javascript'), '/style.css': ('style.css','text/css')}
            if self.path not in files:
                self.send(404, b'{}'); return
            name, kind=files[self.path];self.send(200,(ROOT/'static'/name).read_bytes(),kind)

        def do_POST(self) -> None:
            if not self.trusted() or not secrets.compare_digest(self.headers.get('X-Trial-Token',''),console.token):
                self.send(403,b'{}');return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 4096 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('JSON 요청 형식 오류')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('JSON object 필요')
                if self.path=='/api/refresh':
                    console.refresh();result={'accepted':True}
                elif self.path=='/api/arm':
                    action=body.get('action')
                    if action=='connect':
                        result=console.backend.arm.connect()
                    elif action=='close_connection':
                        if body.get('confirmed') is not True:
                            raise ValueError('시험 연결 종료 확인이 필요합니다.')
                        console.backend.arm.close()
                        result={'note':'시험 클라이언트 연결 종료 요청. 팔 정지/작업 완료를 뜻하지 않습니다.'}
                    else:
                        result=console.backend.arm.send(action,body)
                elif self.path=='/api/action':
                    result=console.submit(body.get('action'),body)
                else:raise ValueError('지원하지 않는 경로')
                self.send(202,json.dumps(result,ensure_ascii=False).encode())
            except (ValueError,KeyError,TypeError,OSError,RuntimeError) as error:
                self.send(409,json.dumps({'error':str(error)},ensure_ascii=False).encode())
    return Handler


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config.json');parser.add_argument('--port',type=int,default=8091)
    args=parser.parse_args();cfg=json.loads(args.config.read_text())
    console=Console(Backend(cfg),Path(cfg['state_dir']))
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(console))
    print(f'시험 콘솔: http://127.0.0.1:{args.port} (이동 기능 없음)',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();console.backend.arm.close();console.pool.shutdown(wait=True)

if __name__=='__main__':main()
