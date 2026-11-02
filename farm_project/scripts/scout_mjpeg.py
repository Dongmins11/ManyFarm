"""기존 카메라의 최신 프레임만 읽는 localhost MJPEG 뷰어."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>예찰 D435 · Live</title><style>body{margin:0;background:#101820;color:#e8f1f5;font:16px system-ui;padding:28px}main{max-width:1400px;margin:auto}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:26px}small,p{color:#a4bdca}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{background:#1a2833;padding:18px;border-radius:16px}img{width:100%;aspect-ratio:16/9;object-fit:contain;background:#060c11}button,a{background:#244557;color:white;padding:10px 16px;border:0;border-radius:8px;cursor:pointer}#status{color:#7ce3c2}body.stale img{opacity:.3}@media(max-width:800px){.grid{grid-template-columns:1fr}body{padding:16px}}</style><main><header><div><small>SCOUT_01 / REALSENSE</small><h1>D435 실시간 카메라</h1></div><button id="toggle">일시정지</button></header><p id="status">영상 연결 중…</p><div class="grid"><article><h2>RGB</h2><img id="rgb" src="/rgb.mjpg" alt="D435 RGB 영상"></article><article><h2>Depth</h2><img id="depth" src="/depth.mjpg" alt="D435 깊이 영상"><p>깊이 0–3 m · 미측정 영역은 검정 · RGB에 정렬하지 않은 원본 깊이 영상</p></article></div><p>표시 최대 3 FPS · 기존 카메라 프레임 읽기 전용 · 로봇 제어 없음</p></main><script>let paused=false;document.querySelector('#toggle').onclick=()=>{paused=!paused;for(const k of ['rgb','depth']){const e=document.getElementById(k);if(paused)e.removeAttribute('src');else e.src='/'+k+'.mjpg?t='+Date.now()}document.querySelector('#toggle').textContent=paused?'다시 보기':'일시정지'};async function status(){try{const r=await fetch('/status',{cache:'no-store'});const s=await r.json();document.body.classList.toggle('stale',!s.fresh);document.querySelector('#status').textContent=(paused?'표시 일시정지 · ':'')+(s.fresh?'LIVE · 최근 프레임 '+s.age_s.toFixed(1)+'초 전':'영상 대기 / 끊김 · '+(s.error||'새 프레임 없음'))}catch(e){document.body.classList.add('stale');document.querySelector('#status').textContent='서버 연결 끊김'}setTimeout(status,1000)}status();</script></html>'''

class Viewer:
    def __init__(self, camera, host: str = '127.0.0.1', port: int = 8088) -> None:
        self.camera = camera
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.frames = {}
        self.sequence = 0
        self.received = None
        self.error = None
        self.clients = 0
        viewer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
                pass

            def do_GET(self) -> None:
                path = urlparse(self.path).path
                if path in ('/', '/status'):
                    if path == '/':
                        body, mime = PAGE.encode(), 'text/html; charset=utf-8'
                    else:
                        with viewer.condition:
                            age = None if viewer.received is None else time.monotonic()-viewer.received
                            body = json.dumps(dict(fresh=age is not None and age<3 and not viewer.error,
                                age_s=age, error=viewer.error, sequence=viewer.sequence)).encode()
                        mime = 'application/json'
                    self.send_response(200)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if path not in ('/rgb.mjpg', '/depth.mjpg'):
                    self.send_error(404)
                    return
                with viewer.condition:
                    if viewer.clients >= 8:
                        self.send_error(503, 'Too many streams')
                        return
                    viewer.clients += 1
                try:
                    self.connection.settimeout(5)
                    self.send_response(200)
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    sequence = -1
                    key = path[1:].split('.')[0]
                    while not viewer.stop.is_set():
                        with viewer.condition:
                            viewer.condition.wait_for(lambda: viewer.sequence != sequence or viewer.stop.is_set(), timeout=2)
                            if viewer.stop.is_set(): break
                            sequence = viewer.sequence
                            data = viewer.frames.get(key)
                            fresh = viewer.received is not None and time.monotonic()-viewer.received<3 and not viewer.error
                        if not data or not fresh: continue
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data+b'\r\n')
                        self.wfile.flush()
                except (OSError, TimeoutError):
                    pass
                finally:
                    with viewer.condition: viewer.clients -= 1

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server.daemon_threads = True
        self.encoder = threading.Thread(target=self._encode, daemon=True)
        self.http = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.encoder.start()
        self.http.start()

    def _encode(self) -> None:
        import cv2
        import numpy as np
        last = -1
        while not self.stop.wait(1/3):
            with self.condition:
                if not self.clients: continue
            try:
                with self.camera.condition:
                    latest = self.camera.latest
                    sequence = self.camera.sequence
                    error = self.camera.error
                if error: raise RuntimeError(error)
                if latest is None or sequence == last: continue
                frames, _cn, _dn, received = latest
                # SDK 프레임 참조를 유지하고 잠금 밖에서 축소·JPEG 변환한다.
                rgb = np.asanyarray(frames.get_color_frame().get_data())
                raw = np.asanyarray(frames.get_depth_frame().get_data())
                rgb = cv2.cvtColor(cv2.resize(rgb, (640,360)), cv2.COLOR_RGB2BGR)
                meters = cv2.resize(raw.astype(np.float32)*self.camera.scale, (640,360), interpolation=cv2.INTER_NEAREST)
                depth = cv2.applyColorMap(np.uint8(np.clip(meters/3,0,1)*255), cv2.COLORMAP_TURBO)
                depth[meters<=0] = 0
                encoded = {}
                for key, value in [('rgb',rgb), ('depth',depth)]:
                    ok, jpeg = cv2.imencode('.jpg',value,[cv2.IMWRITE_JPEG_QUALITY,75])
                    if not ok: raise RuntimeError('JPEG encoding failed')
                    encoded[key] = jpeg.tobytes()
                with self.condition:
                    self.frames=encoded; self.sequence=sequence; self.received=received; self.error=None
                    self.condition.notify_all()
                last=sequence
            except Exception as exc:
                with self.condition: self.error=str(exc)

    def close(self) -> None:
        self.stop.set()
        with self.condition: self.condition.notify_all()
        self.server.shutdown()
        self.server.server_close()
        self.encoder.join(timeout=3)
        self.http.join(timeout=3)
