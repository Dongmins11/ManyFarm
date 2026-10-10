# Vic Pinky 모터 FTDI latency_timer 영구 설정

<!-- MOTOR_INSTALLED_20261010_1751 -->
> **모터 영구 설정 설치 확인 — 2026-10-10 17:51 KST**
> 사용자 로봇 출력: udev 규칙 검사 Success 1 / Fail 0,
> serial=BG02QM7Y, latency_timer=1, rule_installed=True,
> CHECK_OK 및 INSTALL_OK 확인.
> 아래의 설치 미실행 표기는 설치 전 기록이며 이 확인으로 갱신한다.
> 재부팅·USB 재연결 후 지속성 확인은 아직 미실행이다.


사용자 요청: 임시 16→1 쓰기를 재부팅·USB 재연결 후에도 유지한다. 준비 완료이며 로봇 설치/재부팅 검증은 아직 하지 않았다.

## 확인 근거

- 사용자 로봇 수집: /dev/motor → /dev/ttyUSB0, ftdi_sio, USB 0403:6001, 시리얼 BG02QM7Y, 현재 latency_timer=1.
- 기존 /etc/udev/rules.d/99-vic-pinky.rules는 모터 별칭과 권한을 지정한다. 이 파일은 변경하지 않는다.
- latency_timer는 tty 자식이 아니라 usb-serial 포트에 존재한다. 새 규칙은 해당 포트의 add/change 이벤트에서 속성을 쓴다. USB 부모의 vendor/product/serial은 모두 같은 부모에서 일치해야 한다.
- 다른 FTDI 시리얼은 제외한다. 로봇/장치 교체 시 식별자를 재확인해야 한다.
- udev는 장치 생성 시 재적용하는 방식이다. 실행 중 다른 프로그램이 값을 덮어쓰는 것까지 지속 감시하지 않는다.
- 근거: https://github.com/systemd/systemd/blob/main/man/udev.xml (SUBSYSTEM, DRIVER, ATTR, ATTRS, ACTION).

## 설치

PC에서 이번 전달물을 적용한 후 새 규칙과 도구 두 파일만 로봇으로 복사한다. 기존 로봇 파일이 있으면 아래 전송 절차가 같은 내용만 허용한다. 주행을 종료한 상태에서 설치한다. 빌드나 새 Goal은 필요 없다.

```bash
sudo python3 /home/vic/vmany/main/farm_project/robot/tools/vicpinky_motor_latency.py install
python3 /home/vic/vmany/main/farm_project/robot/tools/vicpinky_motor_latency.py check
```

install은 장치 신원→기존 동명 규칙 비교→udevadm verify→새 /etc 규칙 생성→reload→해당 포트 change 이벤트→현재값 확인 순서다. 다른 동명 파일이나 심볼릭 링크가 있으면 덮어쓰지 않는다. 기존 규칙을 바꾸지 않으므로 로봇 백업을 만들지 않는다. 새 설치 도중 오류가 나면 출력과 /etc 규칙 존재 여부를 확인한다. INSTALL_OK를 보기 전 완료로 기록하지 않는다.

예상 결과: serial=BG02QM7Y latency_timer=1 rule_installed=True, CHECK_OK, INSTALL_OK.
재부팅/USB 재연결 후 check 결과를 추가로 기록해야 지속성의 실물 검증 완료다. 이번 기능 확인 때문에 추가 주행은 요구하지 않는다. 다음 정상 재부팅 때 확인해도 된다.

## 복원

```bash
sudo python3 /home/vic/vmany/main/farm_project/robot/tools/vicpinky_motor_latency.py remove
```

현재 원본과 일치하는 새 규칙만 삭제하고 reload 후 해당 모터 현재값을 16으로 돌린다. 기존 /dev/motor 규칙·권한·드라이버는 유지한다. 현재 장치가 없거나 신원이 다르면 복원도 자동 수행하지 않는다.

## 검증 구분

오프라인: 수집된 sysfs 계층과 규칙 조건 대조, 설치 도구 Python 구문 및 파일 충돌/잘못된 신원 거절/재적용/복원 테스트. 실제 udev 이벤트·하드웨어 시험과 다르다.
로봇: 설치 시 udevadm verify 및 실제 target change 이벤트로 값 확인. 전달 시점 미실행.
