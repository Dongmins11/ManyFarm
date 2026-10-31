"""실제 영상 워커 RPC. 대기 작업은 Controller의 I/O 스레드에서만 호출합니다."""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from .mission_types import JsonObject


class SurveyObserver:
    def __init__(self, command: list[str], log: Path, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._rpc_timeout = 30.0
        self._responses: queue.Queue[JsonObject] = queue.Queue()
        self._serial: int = 0
        self._log: TextIO = log.open('w')
        try:
            self._process: subprocess.Popen[str] = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
        except Exception:
            self._log.close()
            raise
        self._reader: threading.Thread = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    @property
    def is_alive(self) -> bool:
        return self._process.poll() is None

    def _read(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._log.write(line)
                self._log.flush()
                if line.startswith('FARM_RPC '):
                    try:
                        self._responses.put(json.loads(line[9:]))
                    except ValueError:
                        continue
        finally:
            self._responses.put({'dead': True})

    def receive(self, check: Callable[[], None], timeout: float) -> JsonObject:
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            check()
            try:
                response = self._responses.get(timeout=0.05)
            except queue.Empty:
                continue
            if response.get('dead'):
                raise RuntimeError('Vision worker exited; see vision_worker.log')
            return response
        raise RuntimeError('Vision worker timeout; see vision_worker.log')

    def call(self, op: str, check: Callable[[], None], **values: object) -> JsonObject:
        """RPC는 단일 I/O 스레드가 직렬 호출하므로 프레임·응답 순서가 섞이지 않습니다."""
        check()  # 취소 이후 새로운 영상 요청을 보내지 않습니다.
        assert self._process.stdin is not None
        self._serial += 1
        self._process.stdin.write(json.dumps(dict(id=self._serial, op=op, **values), allow_nan=False) + '\n')
        self._process.stdin.flush()
        response = self.receive(check, self._rpc_timeout)
        if response.get('id') != self._serial:
            raise RuntimeError('Vision response sequence mismatch')
        if not response.get('ok'):
            raise RuntimeError(response.get('error', 'Vision failed'))
        return response['result']

    def close(self) -> None:
        """진행 중 RPC가 끝난 뒤 호출합니다. 상태 exit마다 프로세스를 종료하지 않습니다."""
        if self._process.poll() is None:
            try:
                assert self._process.stdin is not None
                self._process.stdin.write('{"op":"stop"}\n')
                self._process.stdin.flush()
                self._process.wait(timeout=2)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=2)
        self._reader.join(timeout=2)
        if self._reader.is_alive():
            raise RuntimeError('Vision log reader termination not confirmed')
        self._log.close()
