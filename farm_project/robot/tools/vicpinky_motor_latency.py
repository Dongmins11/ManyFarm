#!/usr/bin/env python3
"""확인된 모터만 udev 영구 설정. 기존 규칙/별칭/권한/주행은 변경하지 않는다."""
import argparse
import os
from pathlib import Path
import subprocess

IDENTITY = {'idVendor': '0403', 'idProduct': '6001', 'serial': 'BG02QM7Y'}
RULE_NAME = '99-vicpinky-motor-latency.rules'
PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / 'robot/config/robots/vicpinky/udev' / RULE_NAME
TARGET = Path('/etc/udev/rules.d') / RULE_NAME


def motor_port() -> Path:
    """/dev/motor의 실제 sysfs 포트와 USB 부모 식별자를 확인한다."""
    device = Path('/dev/motor').resolve(strict=True)
    port = (Path('/sys/bus/usb-serial/devices') / device.name).resolve(strict=True)
    if (port / 'driver').resolve(strict=True).name != 'ftdi_sio':
        raise RuntimeError('모터 드라이버 불일치')
    # ATTRS 세 항목은 같은 USB 부모에서 비교해야 한다.
    usb = next((p for p in port.parents if (p / 'idVendor').is_file()), None)
    if usb is None or any((usb / k).read_text().strip() != v for k, v in IDENTITY.items()):
        raise RuntimeError('모터 USB 식별자 불일치: 아무 설정도 변경하지 않음')
    if not (port / 'latency_timer').is_file():
        raise RuntimeError('latency_timer 속성 없음')
    return port


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def apply(action: str) -> None:
    port = motor_port()
    data = SOURCE.read_bytes()
    if TARGET.is_symlink():
        raise RuntimeError('설치 경로가 심볼릭 링크: 중단')
    exists = TARGET.exists()
    if exists and TARGET.read_bytes() != data:
        raise RuntimeError('같은 이름의 다른 규칙이 존재: 덮어쓰지 않음')
    if action == 'check':
        value = (port / 'latency_timer').read_text().strip()
        print(f'serial=BG02QM7Y latency_timer={value} rule_installed={exists}')
        if not exists or value != '1':
            raise RuntimeError('영구 규칙 또는 현재 값 확인 실패')
        print('CHECK_OK (재부팅/재연결 지속성은 해당 동작 후 다시 확인)')
        return
    if os.geteuid() != 0:
        raise RuntimeError('install/remove는 sudo로 실행')
    if action == 'install':
        # Ubuntu 24.04의 udevadm verify로 설치 전에 규칙 문법을 검사한다.
        run('udevadm', 'verify', str(SOURCE))
        if not exists:
            fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(TARGET, 0o644)
        run('udevadm', 'control', '--reload-rules')
        # 전체 USB가 아닌 확인한 usb-serial 포트의 change 이벤트만 발생시킨다.
        run('udevadm', 'trigger', '--action=change', str(port))
        run('udevadm', 'settle', '--timeout=10')
        apply('check')
        print('INSTALL_OK (재부팅/USB 재연결 시험은 아직 별도)')
    else:
        if exists:
            TARGET.unlink()
        run('udevadm', 'control', '--reload-rules')
        (port / 'latency_timer').write_text('16\n')
        value = (port / 'latency_timer').read_text().strip()
        if value != '16':
            raise RuntimeError('복원 값 확인 실패')
        print('REMOVE_OK latency_timer=16; 기존 /dev/motor 규칙 유지')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'install', 'remove'])
    args = parser.parse_args()
    try:
        apply(args.action)
    except (OSError, RuntimeError, StopIteration, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
