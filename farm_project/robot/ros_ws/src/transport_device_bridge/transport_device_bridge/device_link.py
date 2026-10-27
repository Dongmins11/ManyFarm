"""OpenCR 액추에이터 펌웨어와 UART 로 주고받는 부분 (ROS 와 무관, 단독 시험 가능).

펌웨어 회신 규칙 (oc_fw README 4장)
  OK ...                 명령 접수 (즉시)
  DONE <name> <act>      정상 완료
  STOPPED <name>         stop / release / 새 명령에 덮어써져 중단
  ERR <name> timeout     안전 시간 초과
  ERR ...                명령 거절 (busy, unknown ...)
  PONG                   ping 응답
  READY                  OpenCR 부팅 직후 1번
"""
import threading
import time

import serial


class _Waiter:
    """명령 1개의 회신을 기다리는 객체."""

    def __init__(self, name=None, act=None, prefix=None):
        self.name = name        # 동작 명령: 'lid' / 'gate' / 'tilt'
        self.act = act          # 동작 명령: 'open' / 'close' / 'dump' ...
        self.prefix = prefix    # 단순 명령: 이 글자로 시작하는 줄이 오면 성공 (예: 'PONG', 'OK stop')
        self.accepted = False   # OK 를 받았는지
        self.ok = False
        self.msg = ''
        self.event = threading.Event()

    def finish(self, ok, msg):
        if not self.event.is_set():
            self.ok, self.msg = ok, msg
            self.event.set()

    def feed(self, line):
        if line.startswith('READY'):
            self.finish(False, 'OpenCR 재부팅됨 (READY)')
            return
        if self.prefix is not None:
            if line.startswith(self.prefix):
                self.finish(True, line)
            return   # 다른 줄은 무시 (동시에 진행 중인 동작의 회신일 수 있음)
        tok = line.split()
        if not tok:
            return
        if not self.accepted:
            # 접수 전: OK 면 접수, ERR 면 거절. 접수 전 STOPPED 는 이전 동작 것이라 무시
            if tok[0] == 'OK':
                self.accepted = True
            elif tok[0] == 'ERR':
                self.finish(False, line)
            return
        if tok[:3] == ['DONE', self.name, self.act]:
            self.finish(True, line)
        elif tok[:2] == ['STOPPED', self.name] or tok[:2] == ['ERR', self.name]:
            self.finish(False, line)


class DeviceLink:
    """UART 열기 + 수신 스레드 + 명령 보내고 회신 기다리기."""

    def __init__(self, port, baud=115200, on_line=None, on_ready=None, log=print):
        self.port = port
        self.baud = baud
        self.on_line = on_line      # 받은 줄마다 호출 (raw 토픽 발행용)
        self.on_ready = on_ready    # READY 받으면 호출
        self.log = log
        self._ser = None
        self._wlock = threading.Lock()
        self._lock = threading.Lock()
        self._waiters = []
        self._run = False
        self._th = None

    # ---------- 연결 ----------
    @property
    def connected(self):
        return self._ser is not None and self._ser.is_open

    def start(self):
        self._run = True
        self._th = threading.Thread(target=self._reader, daemon=True)
        self._th.start()

    def shutdown(self):
        self._run = False
        if self._th:
            self._th.join(timeout=1.0)
        self._close()

    def _open(self):
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
            self._ser.reset_input_buffer()
            self.log(f'UART 열림: {self.port} {self.baud}')
            return True
        except (serial.SerialException, OSError) as e:
            self._ser = None
            self.log(f'UART 열기 실패: {self.port} ({e}) → 2초 후 재시도')
            return False

    def _close(self):
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        self._ser = None

    def _fail_all(self, msg):
        with self._lock:
            for w in self._waiters:
                w.finish(False, msg)

    # ---------- 수신 ----------
    def _reader(self):
        buf = b''
        while self._run:
            if not self.connected:
                if not self._open():
                    time.sleep(2.0)
                    continue
                buf = b''
            try:
                data = self._ser.read(self._ser.in_waiting or 1)
            except (serial.SerialException, OSError) as e:
                self.log(f'UART 오류: {e} → 다시 연결')
                self._close()
                self._fail_all('UART 끊김')
                continue
            if not data:
                continue
            buf += data
            while b'\n' in buf:
                raw, buf = buf.split(b'\n', 1)
                line = raw.decode('utf-8', 'replace').strip()
                if line:
                    self._dispatch(line)

    def _dispatch(self, line):
        if self.on_line:
            try:
                self.on_line(line)
            except Exception:
                pass
        if line.startswith('READY') and self.on_ready:
            self.on_ready()
        with self._lock:
            waiters = list(self._waiters)
        for w in waiters:
            w.feed(line)

    # ---------- 송신 ----------
    def _write(self, cmd):
        with self._wlock:
            if not self.connected:
                raise serial.SerialException('UART 미연결')
            self._ser.write((cmd + '\n').encode())
            self._ser.flush()

    def request(self, cmd, name=None, act=None, prefix=None, timeout=5.0):
        """명령을 보내고 결과를 기다린다. → (성공 여부, 메시지)

        동작 명령: name/act 지정 → DONE <name> <act> 가 와야 성공
        단순 명령: prefix 지정  → 그 글자로 시작하는 줄이 오면 성공
        """
        w = _Waiter(name=name, act=act, prefix=prefix)
        with self._lock:
            self._waiters.append(w)
        try:
            try:
                self._write(cmd)
            except (serial.SerialException, OSError) as e:
                w.finish(False, f'전송 실패: {e}')
            if not w.event.wait(timeout):
                w.finish(False, f'시간 초과 ({timeout:.1f}초)')
            return w.ok, w.msg
        finally:
            with self._lock:
                self._waiters.remove(w)
