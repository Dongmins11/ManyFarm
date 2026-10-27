# 운송로봇(transport_01) 바구니 액추에이터 펌웨어 — OpenCR 1.0

작성: 채윤식 · 기준일 2026-10-27 · 상태: **통합 펌웨어 + ROS 2 브리지 노드 실물 시험 통과 / 운송 노드·관제 연동 전**

> 이 압축 파일을 `~/Downloads`에 풀면 `~/Downloads/oc_fw/`가 생긴다. 아래 명령은 이 위치를 기준으로 한다.
> Confluence: **04. 개발 → Firmware** (구현·검증 기록, 빌드·업로드 가이드), **03. 시스템 설계 → Hardware 구성 → 운송로봇 배선도 스펙**

운송로봇(TurtleBot3 Waffle Pi 개조)의 바구니 구동부 3개(윗덮개·앞문·틸트)를 OpenCR 1.0 하나로 제어한다.
별도 MCU는 없다. 주행용 TB3 순정 펌웨어와 합친 **통합 펌웨어**가 로봇에 올라가 있다.

---

## 0. 빠른 사용법 (팀원용)

**지금 로봇 OpenCR에는 통합 펌웨어가 올라가 있다.** 주행(bringup)은 평소처럼 쓰면 되고, 기구는 **ROS 2 서비스**로 부른다.

### 0-1. 기본: ROS 2 브리지 노드 (운송 노드·관제에서 쓰는 방법)

```bash
# 터미널: 로봇 ① — 브리지 노드 실행 (bringup 과 동시에 사용 가능)
source ~/device_ws/install/setup.bash
ros2 launch transport_device_bridge device_bridge.launch.py
```
정상: `UART 열림: /dev/ttyS0 115200` → `서비스 준비: ...` → `OpenCR 연결 확인 (PONG)`

```bash
# 터미널: 로봇 ② (또는 같은 ROS 네트워크의 다른 PC) — 서비스 호출
ros2 service call /transport_01/device/lid_open std_srvs/srv/Trigger
```

| 서비스 (`std_srvs/srv/Trigger`) | 동작 | 응답 (성공 시) |
|---|---|---|
| `/transport_01/device/lid_open` / `lid_close` | 윗덮개 열기 / 닫기 (약 4.0초) | `success=True, message='DONE lid open'` |
| `/transport_01/device/gate_open` / `gate_close` | 앞문 열기 / 닫기 (약 1.2초) | `message='DONE gate open'` |
| `/transport_01/device/unload` | 쏟기 전체: 앞문 열기 → 틸트 쏟기 → 앞문 닫기 (약 23초) | `message='DONE gate open -> tilt dump -> gate close'` |
| `/transport_01/device/stop` | **전체 즉시 정지** | `message='OK stop all'` |

- 동작이 **끝나야** 응답한다. 실패하면 `success=False`와 이유가 `message`에 온다. 자세한 것은 9-1.
- OpenCR 회신 원문은 `ros2 topic echo /transport_01/device/raw`로 볼 수 있다.

### 0-2. 직접 시험: UART 명령 (브리지 노드를 **끈 상태**에서만)

`/dev/ttyS0`는 한 프로그램만 열 수 있다. 브리지 노드가 켜져 있으면 miniterm이 열리지 않는다.

```bash
# 터미널: 로봇
python3 -m serial.tools.miniterm -e --eol LF /dev/ttyS0 115200
```

| 입력 (영문) | 동작 | 회신 |
|---|---|---|
| `ping` | 연결 확인 | `PONG` |
| `lid open` / `lid close` | 윗덮개 열기 / 닫기 (약 4.0초) | `OK ...` → 끝나면 `DONE lid open` |
| `gate open` / `gate close` | 앞문 열기 / 닫기 (약 1.2초) | `OK ...` → `DONE gate open` |
| `tilt dump` | 쏟기: 올림 8초 → 위에서 2초 → 내림 9초 (약 20초) | `OK ...` → `DONE tilt dump` |
| `tilt up` / `tilt down` | 틸트만 올림 / 내림 (9초) | `OK ...` → `DONE tilt up` |
| `stop` | **전체 즉시 정지** | `STOPPED <이름>` + `OK stop all` |
| `status` / `help` | 상태 / 짧은 영문 도움말 | |

- 쏟는 순서: `gate open` → `tilt dump` → `gate close` / 받는 순서: `lid open` → (수확물 받기) → `lid close`
- 덮개·앞문은 위치 센서가 없는 **시간 제어**다. **닫힌 상태에서 시작**한다.
- 종료: 영문 입력 상태에서 `Ctrl + ]`
- 기구 전원은 **배터리 B 스위치**. 이상하면 `stop` → 그래도 안 되면 배터리 B OFF.

---

## 1. 현재 상태

| 항목 | 상태 |
|---|---|
| 배선 (서보 2, 리니어 1, UART) | 완료 |
| 덮개·앞문·틸트 동작값 | **확정** (3장) |
| 라즈베리파이 UART `/dev/ttyS0` | 설정 완료 (2026-10-21) |
| 통합 펌웨어 `oc_tb3_actuator` | **로봇 탑재** (2026-10-23). 주행 + UART 명령 동시 동작 확인 |
| 실물 시험 (주행 동시·전원·순서·반복 5회·비상 정지·적재 쏟기) | **통과** (2026-10-23) |
| 동작 완료 회신 (`DONE` / `STOPPED` / `ERR` / `PONG` / `READY`) | **실물 확인** (2026-10-23). 덮개·틸트 동시 동작 시 각각 `DONE` 회신 확인 |
| ROS 2 브리지 노드 `transport_device_bridge` | **실물 확인** (2026-10-23). 서비스 6개 (덮개·앞문·쏟기·정지) 정상, 쏟기 도중 `stop` 정상 |
| 운송 노드 · 관제 연동 | 미구현 (9장 연동 정보, 10장 남은 작업) |

---

## 2. 하드웨어 구성

| 구동부 | 부품 | OpenCR 핀 | 비고 |
|---|---|---|---|
| 윗덮개 (lid) | MG996R **360° 연속회전형** | D5 (TIM1) | 위치 제어 불가 → 시간 기반 |
| 앞문 (gate) | MG996R **360° 연속회전형** | D6 (TIM2) | 위치 제어 불가 → 시간 기반 |
| 틸트 (tilt) | 12V 리니어 액추에이터 100mm · 100N · 8mm/s | L298N: IN1=D7, IN2=D8, ENA=D9 (PWM 1 kHz) | 내장 끝 리미트 스위치. 끝까지 약 12.5초 |

- 리니어 배선: **빨강 → M1(OUT1), 검정 → M2(OUT2)**. 이 배선 기준 `invert 0`이 정방향.
- MG996R은 라벨로 180°/360°를 구분할 수 없다. 손으로 돌려 계속 돌면 360°형이다.

### 라즈베리파이 ↔ OpenCR UART (통합 펌웨어 명령 채널)

| 선 | 라즈베리파이 4 | OpenCR | 비고 |
|---|---|---|---|
| U1 (흰색) | 8번 핀 TX | D0 (RX, Serial1) | |
| U2 (회색) | 10번 핀 RX | D1 (TX, Serial1) | |
| U3 (검정) | 9번 핀 GND | POWER 헤더 GND | 선택 (기준 접지) |

- 라즈베리파이 4·6번 핀은 원래 있던 OpenCR → 파이 전원선이므로 손대지 않는다.
- 그림: `docs/운송로봇_배선도_v3.png`(전체), `docs/UART_배선_파이_OpenCR.png`, `docs/OpenCR_D5-D9_위치.png`, `docs/L298N_점퍼.png`

---

## 3. 확정 동작값

| 명령 | 실제 동작 | 소요 시간 |
|---|---|---|
| `lid open` | `spin -400 1350` — 끊어치기 (전진 0.1초 / 후진 0.05초 반복) | 약 4.0초 |
| `lid close` | `spin 400 1350` — 끊어치기 | 약 4.0초 |
| `gate open` | `spin -400 1200` — 연속 회전 | 약 1.2초 |
| `gate close` | `spin 400 1200` — 연속 회전 | 약 1.2초 |
| `tilt up` | 100%로 9초 올림 | 약 9.6초 (램프 포함) |
| `tilt down` | 100%로 9초 내림 | 약 9.6초 |
| `tilt dump` | 8초 올림 → **위에서 2초 정지** → 9초 내림 (자동) | 약 20초 |

- `spin <±us> <ms>`: 중립 1500us에 ±us를 더한 펄스를 보낸다. `ms`는 **순수 전진 시간의 합**이다. 끝나면 펄스를 끊어 정지한다.
- 덮개 끊어치기는 슬라이드 덮개가 문틀에 끼는 문제 때문에 넣었다. 앞문과 틸트는 끊어치기 없이 움직인다.
- 틸트 내림(9초)을 올림(8초)보다 길게 잡아 매번 맨 아래(내장 리미트)에 확실히 닿게 한다.
- 위 값은 모두 **펌웨어 기본값**이다. 전원을 켜면 `set` 없이 바로 쓸 수 있다.

---

## 4. 동작 방식

- `loop()`는 `act_poll()`(명령 받기)과 `act_update()`(상태머신)만 반복한다. `delay()`를 쓰지 않는다.
  그래서 통합 펌웨어에서 TB3 주행 처리와 함께 돌아간다 (시험: 기구 동작 중 `/odom` 20 Hz 유지).
- **서보**: PWM 드라이버(`drv_pwm`)를 직접 50 Hz, 12비트로 제어한다. 부팅 직후 펄스는 0이라 **전원을 켜도 서보가 움직이지 않는다**.
- **360° 서보 시간 제어**: 전진 `sfwd` ms → 후진 `sback` ms를 반복한다(`sback 0`이면 연속). 순수 전진 시간이 목표에 닿으면 펄스를 끊는다.
- **틸트**: L298N 방향 핀 + 1 kHz PWM이다. 시작과 정지에 300 ms 소프트 램프를 둔다. 방향을 바꾸려면 먼저 정지해야 한다.
- **안전장치**
  - 서보 spin: 한 번에 최대 6초(순수 전진), 전체 20초를 넘으면 강제 정지 + `ERR <이름> timeout`
  - 틸트: 한 번에 최대 15초(`maxrun`), 넘으면 즉시 정지 + `ERR tilt timeout`
  - `stop`: 전체 즉시 정지 (틸트 쏟기 자동 내림도 취소)
  - 틸트는 부팅 시 **잠금 해제 상태**다. `tilt disable`로 잠글 수 있다.

### 회신 규칙 (상위 노드가 쓰는 부분)

| 회신 | 언제 | 예 |
|---|---|---|
| `OK ...` | 명령을 **받았을 때** (즉시) | `OK lid open = spin -400 1350 ...` |
| `DONE <이름> <동작>` | 동작이 **정상으로 끝났을 때** | `DONE lid open`, `DONE gate close`, `DONE tilt dump`, `DONE lid spin` |
| `STOPPED <이름>` | `stop`·`release` 또는 **새 명령이 이전 동작을 덮어써서** 중단됐을 때 | `STOPPED tilt` |
| `ERR <이름> timeout` | 안전 시간 초과로 강제 정지했을 때 | `ERR tilt timeout` |
| `ERR ...` | 명령 거절 (예: 틸트 동작 중 다른 틸트 명령) | `ERR busy` |
| `PONG` | `ping` 응답 | |
| `READY` | 통합 펌웨어 부팅 직후 1번 (UART) | |

- 회신은 **마지막으로 명령을 받은 포트**로 나간다 (시험용 = USB, 통합 = UART).
- `<이름>` = `lid` / `gate` / `tilt`, `<동작>` = `open` / `close` / `spin` / `up` / `down` / `dump`
- `tilt dump`은 올림이 끝났을 때가 아니라 **내림까지 끝났을 때** `DONE tilt dump` 1번만 보낸다.
- 상위 노드는 **`DONE`을 받아야 완료**로 판단한다. `OK`는 접수일 뿐이다.

---

## 5. 명령 목록

115200 bps, 줄 끝 LF, 대소문자 무관. 시험용은 USB, 통합 펌웨어는 UART로 받는다. 명령은 같다.

### 기본
```
help                      짧은 영문 도움말 (펌웨어 크기 때문에 요약만. 자세한 설명은 이 README)
ping                      연결 확인 → PONG
status                    현재 상태 (덮개·앞문·틸트)
dump                      현재 설정값 출력 (기본값으로 붙여넣기용)
stop                      전체 즉시 정지
release                   서보 전체 힘 빼기
```

### 윗덮개 / 앞문 (lid · gate 동일)
```
lid open | close          열기 / 닫기 (시간 기반, home 불필요)
lid spin <±us> <ms>       직접 회전 (시험용). 예: lid spin -400 500
lid stop | release        정지 / 힘 빼기
set lid sopen <us>        열기 방향 세기 (닫기는 부호 반대). 0이면 각도 서보 모드
set lid stime <ms>        열기·닫기 시간 (순수 전진 합, 최대 6000)
set lid sfwd <ms>         끊어치기 전진 시간
set lid sback <ms>        끊어치기 후진 시간 (0 = 연속)
```
`lid home`, `lid raw ...`, `lid zero`, `lid <deg>`는 180° 각도 서보용 기능이다. 현재 360° 서보에서는 쓰지 않는다.

### 틸트
```
tilt up | down [duty%] [ms]   숫자 없으면 100% 9000ms. 예: tilt up 100 1000
tilt dump                     쏟기: 올림 → 정지 → 내림 자동
tilt stop                     램프 정지 (자동 내림 취소)
tilt enable | disable         잠금 해제 / 잠금
set tilt dumpup <ms>          쏟기 올림 시간 (기본 8000)
set tilt dumpwait <ms>        쏟기 위 정지 시간 (기본 2000)
set tilt dumpdown <ms>        쏟기 내림 시간 (기본 9000)
set tilt invert 0|1           방향 반전 (기본 0)
set tilt maxduty|ramp|maxrun <val>
```
`set` 값은 전원을 끄면 사라진다. 고정하려면 `actuator.cpp` / `actuator.h` 기본값을 수정하고 다시 업로드한다.

---

## 6. 파일 구조

```
oc_fw/
├── README.md                        이 문서
├── oc_actuator_test/                시험용 (USB 명령, TB3 주행 펌웨어 없음)
│   ├── oc_actuator_test.ino
│   ├── actuator.h                   핀·설정 구조체·클래스 선언, 틸트 기본값, 회신 함수
│   └── actuator.cpp                 덮개·앞문 기본값, 상태머신, 명령 해석, 회신
├── oc_tb3_actuator/                 통합 펌웨어 (TB3 순정 주행 + UART 명령) ← 로봇에 올라가 있는 것
│   ├── oc_tb3_actuator.ino
│   ├── actuator.h                   ← oc_actuator_test 와 동일 파일
│   └── actuator.cpp                 ← oc_actuator_test 와 동일 파일
├── ros/
│   └── transport_device_bridge/     ROS 2 브리지 노드 패키지 (로봇 ~/device_ws/src 에 넣고 빌드)
│       ├── transport_device_bridge/device_bridge.py   노드 (서비스 6개 + raw 토픽)
│       ├── transport_device_bridge/device_link.py     UART 송수신·회신 판정 (ROS 무관)
│       ├── config/device_bridge.yaml                  포트·제한 시간
│       └── launch/device_bridge.launch.py
├── bashrc_PC.sh                     PC ~/.bashrc 용 함수
├── bashrc_ROBOT.sh                  로봇 ~/.bashrc 용 함수
├── opencr_ld_src.tar.gz             업로더 소스 (로봇은 인터넷이 안 됨)
└── docs/
    ├── 운송로봇_배선도_v3.png        전체 배선도 (리니어 + UART U1~U3)
    ├── UART_배선_파이_OpenCR.png     라즈베리파이 8·9·10번 핀 ↔ OpenCR D0·D1·GND
    ├── OpenCR_D5-D9_위치.png         서보·L298N 신호 핀 위치
    └── L298N_점퍼.png                L298N 점퍼 (5V-EN·ENA 제거, ENB 유지)
```

- `actuator.h` / `actuator.cpp`는 **두 스케치에서 같은 파일**을 쓴다. 고치면 양쪽에 복사한다.
- 덮개·앞문 기본값은 `actuator.cpp` 맨 위 `LID_DEF` / `GATE_DEF` 한 줄이다. 틸트 기본값은 `actuator.h`의 `TiltMotor` 멤버다.

---

## 7. 처음 1번 준비 (펌웨어를 직접 수정·업로드할 사람만)

### PC (터미널: PC)
```bash
# arduino-cli 설치
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=$HOME/.local/bin sh
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://raw.githubusercontent.com/ROBOTIS-GIT/OpenCR/master/arduino/opencr_release/package_opencr_index.json
arduino-cli core update-index
arduino-cli core install OpenCR:OpenCR
arduino-cli lib install Dynamixel2Arduino        # 통합 펌웨어용

# 스케치 복사 + bashrc 함수 등록
mkdir -p ~/oc_fw && cp -r ~/Downloads/oc_fw/oc_actuator_test ~/Downloads/oc_fw/oc_tb3_actuator ~/oc_fw/
cat ~/Downloads/oc_fw/bashrc_PC.sh >> ~/.bashrc && source ~/.bashrc
oc_build                                         # → build/oc_actuator_test.ino.bin
```
`arduino-cli: command not found`이면 새 터미널을 열거나 `export PATH=$HOME/.local/bin:$PATH`를 실행한다.
`bashrc_PC.sh`의 로봇 주소(`OC_PI="wmany@192.168.0.15"`)가 다르면 수정한다.

### 로봇 (업로더 빌드 — 로봇은 인터넷이 안 되므로 PC에서 소스를 보냄)
```bash
# 터미널: PC
scp ~/Downloads/oc_fw/opencr_ld_src.tar.gz ~/Downloads/oc_fw/bashrc_ROBOT.sh wmany@192.168.0.15:~/
```
```bash
# 터미널: 로봇
mkdir -p ~/oc_fw && cd ~/oc_fw && tar xzf ~/opencr_ld_src.tar.gz
cd ~/oc_fw/opencr_ld && make
cat ~/bashrc_ROBOT.sh >> ~/.bashrc && source ~/.bashrc
ls ~/opencr_update                               # 순정 복구 파일이 있어야 함
```
현재 운송로봇(wmany)에는 이미 준비되어 있다.

### 로봇 ROS 2 브리지 노드 설치 (2026-10-23 완료, 기록용)
```bash
# 터미널: PC
scp -r ~/Downloads/oc_fw/ros/transport_device_bridge wmany@192.168.0.15:~/
```
```bash
# 터미널: 로봇
mkdir -p ~/device_ws/src && rm -rf ~/device_ws/src/transport_device_bridge && mv ~/transport_device_bridge ~/device_ws/src/
cd ~/device_ws && colcon build --symlink-install
source ~/device_ws/install/setup.bash
```
정상: `Summary: 1 package finished`. 의존성은 `rclpy`, `std_srvs`, `std_msgs`, `python3-serial`(이미 설치됨)뿐이다.

### 로봇 UART 설정 (2026-10-21 완료, 기록용)
```bash
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
sudo sed -i 's/console=serial0,115200 //' /boot/firmware/cmdline.txt
sudo systemctl disable --now serial-getty@ttyS0.service
sudo systemctl mask serial-getty@ttyS0.service
sudo reboot
```
- 확인: `cat /proc/cmdline | grep -c serial0` → `0`, `systemctl is-active serial-getty@ttyS0.service` → `inactive`
- 되돌리기: `sudo cp /boot/firmware/cmdline.txt.bak /boot/firmware/cmdline.txt && sudo systemctl unmask serial-getty@ttyS0.service && sudo reboot`

---

## 8. 업로드 순서

| 함수 | 실행 위치 | 하는 일 |
|---|---|---|
| `oc_build` | PC | 컴파일 |
| `oc_send` | PC | bin을 로봇 `~/oc_fw/fw.bin`으로 복사 |
| `oc_flash` | PC | 컴파일 + 전송 + 업로드 한 번에 |
| `oc_mon` | PC | 로봇에서 **USB** 시리얼 모니터 열기 (시험용 펌웨어용) |
| `oc_stock` | PC | 순정 TB3 펌웨어 복구 |

### 통합 펌웨어 업로드 (평소)
1. 로봇 bringup·miniterm 종료 (USB 포트 해제)
2. 업로드

```bash
# 터미널: PC
OC_SKETCH=oc_tb3_actuator oc_flash
```
정상: `CRC OK` → `[OK] Download` → `jump_to_fw`. 이후 bringup 주행과 UART 명령을 함께 쓸 수 있다.

### 시험용 펌웨어 (USB로만 시험할 때)
```bash
oc_flash      # 업로드 (주행 기능 없음!)
oc_mon        # USB 모니터
```
⚠ 시험용 펌웨어에는 TB3 주행 기능이 없다. **시험 후 반드시 통합 펌웨어를 다시 올리거나 `oc_stock`**.

---

## 9. 팀원 요청 대응 — 연동 정보 (Slack 요청 기준, 2026-10-23)

### 9-1. 운송 주행·도킹 (신동민) — 운송 노드에서 기구를 부르는 방법

운송 미션 노드(FSM)가 기구를 부르는 쪽이다. 펌웨어 쪽 준비는 끝났고, **ROS 2에서 어떻게 부를지**만 정하면 된다.

**호출 시점 (제안)**

| 미션 | 단계 | 기구 명령 | 완료 조건 |
|---|---|---|---|
| `transport_pickup` | 수확로봇과 도킹 안정 직후 (`DOCK_STABLE` 보고 **전**) | `lid open` | `DONE lid open` |
| `transport_pickup` | `TRANSFER_COMPLETE` 수신 후, 출발 **전** | `lid close` | `DONE lid close` |
| `bucket_unload` | 선별장 도킹 후 BUCKET_PROCESS | `gate open` → `tilt dump` → `gate close` | 각 `DONE` 순서대로 |
| 공통 | 비상 / 미션 취소 | `stop` | `OK stop all` |

**연동 방식 — (가)로 결정 (2026-10-23), 브리지 노드 실물 확인 완료**

| | (가) 브리지 노드를 따로 둠 | (나) 운송 노드가 UART를 직접 엶 |
|---|---|---|
| 구조 | 운송 노드 → ROS 2 서비스 호출 → **브리지 노드**(채윤식) → UART → OpenCR | 운송 노드 → (노드 안에서 pyserial로) UART → OpenCR |
| 운송 노드가 할 일 | 서비스 호출 한 줄 (`/transport_01/device/lid_open` 등, `std_srvs/Trigger`) | 시리얼 열기, 명령 쓰기, `DONE`/`STOPPED`/`ERR` 줄 읽기·타임아웃 처리 |
| 장점 | 역할이 깔끔히 나뉨. 시리얼 문제는 펌웨어 담당이 책임. 관제·시험에서 `ros2 service call`로 바로 시험 가능 | 노드가 하나 줄어듦. 지연이 약간 적음 |
| 단점 | 노드 1개 추가 (실행 런치에 포함 필요) | 운송 노드 코드에 시리얼 처리가 섞임. `/dev/ttyS0`는 **한 프로세스만** 열 수 있음 |
| 결정 | **✅ (가) 채택** | |

(가)의 서비스 목록 (구현·실물 확인 완료):

| 서비스 (`std_srvs/srv/Trigger`) | 펌웨어 명령 | 응답 |
|---|---|---|
| `/transport_01/device/lid_open` | `lid open` | `DONE` 수신 시 `success=true`, `STOPPED`/`ERR`/시간 초과 시 `false` + `message` |
| `/transport_01/device/lid_close` | `lid close` | 〃 |
| `/transport_01/device/gate_open` | `gate open` | 〃 |
| `/transport_01/device/gate_close` | `gate close` | 〃 |
| `/transport_01/device/unload` | `gate open` → `tilt dump` → `gate close` (한 번에) | 약 23초 후 응답 |
| `/transport_01/device/stop` | `stop` | 즉시 응답 |

- 서비스는 동작이 **끝날 때까지** 응답하지 않는다 (덮개 약 4.0초, 쏟기 약 23초). 운송 노드에서는 **비동기 호출**(`call_async`)로 부른다.

**실패 응답 (`success=False`)**

| 상황 | `message` 예 | 브리지 노드가 하는 일 |
|---|---|---|
| 다른 기구 동작 중 | `busy: unload 동작 중` | 즉시 거절 (기구는 그대로) |
| `stop` 서비스로 중단 | `tilt dump 실패: STOPPED tilt (완료: gate open)` | — (이미 정지) |
| 펌웨어 안전 시간 초과 | `lid open 실패: ERR lid timeout` | `stop` 전송 |
| 브리지 제한 시간 초과 | `gate close 실패: 시간 초과 (5.0초)` | `stop` 전송 |
| OpenCR 재부팅 | `gate open 실패: OpenCR 재부팅됨 (READY)` | `stop` 전송 |
| UART 끊김 | `lid open 실패: 전송 실패: UART 미연결` | 2초마다 다시 연결 시도 |

- `unload` 도중 실패하면 그 자리에서 멈춘다. `message`의 `(완료: ...)`로 어디까지 했는지 알 수 있다. **앞문이 열린 채일 수 있으므로** 복구 시 `gate_close`를 부른다.
- 덮개·앞문은 시간 제어라 위치를 모른다. 중간에 멈춘 뒤에는 **사람이 닫힌 상태로 맞춘 뒤** 다시 시작한다.

**운송 노드 호출 예 (Python, rclpy)**

```python
from std_srvs.srv import Trigger

# __init__
self.lid_open_cli = self.create_client(Trigger, '/transport_01/device/lid_open')
self.lid_close_cli = self.create_client(Trigger, '/transport_01/device/lid_close')
self.unload_cli = self.create_client(Trigger, '/transport_01/device/unload')
self.dev_stop_cli = self.create_client(Trigger, '/transport_01/device/stop')

# 도킹 안정 직후
def open_lid(self):
    if not self.lid_open_cli.service_is_ready():
        self.get_logger().error('device_bridge 가 실행 중이 아님')
        return
    fut = self.lid_open_cli.call_async(Trigger.Request())
    fut.add_done_callback(self._on_lid_open)        # 약 4.0초 뒤 호출됨 (FSM 을 막지 않음)

def _on_lid_open(self, fut):
    res = fut.result()
    if res.success:
        pass        # → DOCK_STABLE 보고 단계로
    else:
        self.get_logger().error(f'lid_open 실패: {res.message}')   # → 오류 상태로
```

- 액션 콜백 안에서 결과를 기다려야 하면 **콜백 그룹을 Reentrant 로 두고 MultiThreadedExecutor** 를 쓴다 (같은 스레드에서 기다리면 응답을 못 받고 멈춤).
- 미션 취소·비상 시에는 `self.dev_stop_cli.call_async(Trigger.Request())`.

**실행 방법**
- 현재: 브리지 노드를 **따로 실행**한다 (0-1).
- 나중에: 운송 bringup 런치에 포함할 수 있다. 런치 파일에 아래만 추가하면 된다 (`~/device_ws/install/setup.bash`를 먼저 source).

```python
import os
from ament_index_python.packages import get_package_share_directory
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

device_bridge = IncludeLaunchDescription(PythonLaunchDescriptionSource(os.path.join(
    get_package_share_directory('transport_device_bridge'), 'launch', 'device_bridge.launch.py')))
# LaunchDescription([... , device_bridge])
```

### 9-2. 시뮬레이션 (양시영 · 조병현) — "운송로봇 파트 애셋 및 코드 전달", "박스 관절 이름·구동 주체"

**기구 구성 (실물 기준)**

| 구동부 | 움직임 | 구동 주체 | 실물 소요 시간 | 시뮬레이션 관절 (제안) |
|---|---|---|---|---|
| 윗덮개 (lid) | 슬라이드 개폐 | MG996R 360° 서보 (OpenCR D5) | 열기·닫기 각 약 4.0초 | `lid_joint` (prismatic) — 팀 URDF에 이미 있음 |
| 앞문 (gate) | 앞쪽 문 회전 개폐 | MG996R 360° 서보 (OpenCR D6) | 열기·닫기 각 약 1.2초 | `gate_joint` (revolute) — **팀 URDF에 없음, 추가 필요** |
| 틸트 (tilt) | 바구니 뒤쪽을 들어 앞으로 기울임 | 12V 리니어 액추에이터 (L298N, OpenCR D7~D9) | 올림 8초 → 정지 2초 → 내림 9초 | `tilt_joint` (revolute) — **팀 URDF에 없음, 추가 필요** |

- 리니어 액추에이터 속도 8mm/s × 올림 8초 → **약 60mm 신장**에서 멈춘다 (전체 스트로크 100mm).
- 앞문 열림 각도·바구니 최대 기울기 각도는 **실측값 기입 예정** (현재 시간 기반 제어라 펌웨어에는 각도 값이 없음).
- 덮개·앞문 서보는 위치 센서가 없어 **시간으로만** 움직인다. 시뮬레이션에서는 위 시간 동안 목표 위치까지 등속 이동으로 모델링하면 실물과 같다.

**동작 순서 (시뮬레이션 시나리오에 그대로 사용)**

```
[수확물 받기]  수확로봇 도킹 → lid open (4.0초) → 과실 이송 → lid close (4.0초) → 출발
[선별장 쏟기]  선별장 도킹 → gate open (1.2초) → tilt 올림 8초 → 위에서 2초 → tilt 내림 9초 → gate close (1.2초) → 복귀
```

- 쏟기 전체 약 23초. 과실은 틸트가 올라가는 동안 열린 앞문으로 미끄러져 나간다.
- 펌웨어 코드 전체는 이 압축 파일의 `oc_tb3_actuator/`. 시간 값은 `actuator.cpp`의 `LID_DEF` / `GATE_DEF`, `actuator.h`의 `TiltMotor` 멤버.

### 9-3. 관제 (전민석) — "운송/인계 테스트, 통신 방식 검증"

- 기구 동작은 **운송 노드 안에서** 처리된다 (9-1). 관제가 `transport_pickup` / `bucket_unload`를 보내면 그 안에서 덮개·쏟기가 자동으로 실행되므로 **관제 쪽 메시지·인터페이스 변경은 없다**.
- 관제 웹 인계 테스트(`transport_pickup`)에는 덮개 개폐 시간(열기·닫기 각 약 4.0초)만큼 단계가 길어진다.
- `bucket_unload`(쏟기)는 관제 웹 테스트 화면에 아직 없다. 쏟기를 관제에서 시연하려면 버튼 추가 협의가 필요하다.
- 기구만 따로 시험할 때 (브리지 노드 실행 중): `ros2 service call /transport_01/device/lid_open std_srvs/srv/Trigger`

---

## 10. 남은 작업

| 순서 | 할 일 | 상태 |
|---|---|---|
| 1 | 연동 방식 결정 → **(가) 브리지 노드** | ✅ 완료 (2026-10-23) |
| 1-1 | ROS 2 브리지 노드 `transport_device_bridge` (서비스 6개, `DONE` 수신 후에만 `success=True`) | ✅ 실물 확인 (2026-10-23) |
| 1-2 | 브리지 노드를 운송 bringup 런치에 포함 (9-1 실행 방법) | 통합 시험 때 운송 주행 담당과 협의 |
| 2 | 관제 연동: Zenoh 브리지(관제 PC `tcp/192.168.0.20:7447`, Domain 77, CycloneDDS). 서비스 직접 호출 또는 `bucket_unload` Action 중 결정 | 관제 담당과 협의 |
| 3 | 운송 미션 노드에 연결: `transport_pickup` 도킹 안정 후 `lid open`, TRANSFER_COMPLETE 후 `lid close`. `bucket_unload`의 BUCKET_PROCESS에서 `gate open → tilt dump → gate close` | 설계 제안 |
| 4 | 5V 레일 전압·전류 계측 | 예정 |
| 5 | 덮개·앞문 서보 180°형 교체 검토 (360°형은 위치를 모름 → 장시간 반복 시 누적 오차 가능) | 검토 |

---

## 11. 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| `[X] /dev/ttyACM0 사용 중` | bringup(turtlebot3_ros)이 포트를 잡고 있음 → bringup 종료 후 다시 |
| `Platform OpenCR:OpenCR not found` | 7장 PC 준비의 `core update-index`, `core install` 실행 |
| `Fail to jump to boot` / 업로드 실패 | OpenCR **PUSH SW2를 누른 채 RESET** → 부트로더 진입 후 다시 업로드 |
| `CRC Fail : 0xF020` (검증 응답 시간 초과) 반복 | 직접 빌드한 `opencr_ld`가 약 160KB(160,696 바이트)에서 실패한 사례 있음. 펌웨어 크기를 줄이면 해결(도움말 축소로 해결). 실패 상태에서는 주행 불가이므로 먼저 `oc_stock`으로 순정 복구 |
| `ERR unknown command: ㅣㅑㅇ` 등 | 한글 입력 상태. **영문 입력**으로 바꿔서 입력 |
| `Ctrl+]`로 miniterm이 안 닫힘 | 영문 입력 상태에서 다시. 안 되면 PC에서 `ssh wmany@192.168.0.15 'pkill -f miniterm'` |
| miniterm이 `could not open port /dev/ttyS0` / 브리지 노드가 `UART 열기 실패` | 다른 프로그램(브리지 노드 또는 miniterm)이 포트를 잡고 있음 → 하나만 실행 |
| 브리지 노드가 `OpenCR ping 실패`를 반복 | 통합 펌웨어가 아님 → `OC_SKETCH=oc_tb3_actuator oc_flash`. UART 배선 확인 |
| `ros2 service call`이 `waiting for service to become available...`에서 멈춤 | 브리지 노드가 꺼져 있음 → 0-1로 실행. 다른 PC에서 부를 때는 `ROS_DOMAIN_ID`·Zenoh 브리지 확인 |
| 서비스가 `busy: ...`로 바로 실패 | 이전 기구 동작이 아직 진행 중 → 끝난 뒤 다시, 또는 `stop` |
| `/dev/ttyS0`에서 아무 회신이 없음 | 통합 펌웨어가 아님(시험용·순정) → 통합 펌웨어 업로드. U1·U2 선 교차(파이 TX→OpenCR D0) 확인 |
| `oc_stock` 입력 시 `ERR unknown command` | miniterm **안**에 입력한 것. 모니터를 닫고 PC 터미널에서 입력 |
| 고친 펌웨어가 반영 안 됨 | `~/oc_fw`에 새 파일이 복사되지 않음 → `cp` 후 다시 업로드 |
| `ssh: No route to host` / `Broken pipe` | 로봇 전원 꺼짐 (배터리 A 방전) 또는 네트워크 끊김 |
| 서보가 멈추지 않고 계속 돎 | 360° 서보에 각도 명령(`raw` 등)을 준 경우 → `stop` / `release` / 배터리 B OFF |
| 앞문·덮개 열기/닫기가 반대 | **닫힌 상태에서 출발**해 다시 확인. 정말 반대면 `set gate sopen <부호 반대>`로 확인 후 기본값 수정 |
| 틸트 방향이 반대 | `set tilt invert 1`로 확인 후 기본값 수정 |
| 서보 떨림 / OpenCR 리셋 | 5V(DC-DC 출력) 전압 처짐 의심 → 하나씩 움직여 보며 DC-DC 표시값 확인 |

---

## 12. 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-10-19 | 배선 완료. 시험용 펌웨어 1차 (각도 서보·JOG 끊어치기·5840 틸트 가정) |
| 2026-10-20 | 덮개 서보가 360° 연속회전형임을 확인 → 시간 기반 `spin` 추가. 5840 대신 12V 리니어 액추에이터로 변경 |
| 2026-10-21 | 덮개 `∓400/1500` 끊어치기, 앞문 `400/1200` 연속 확정. `tilt dump` (8초 → 2초 정지 → 9초) 추가. 틸트 부팅 시 잠금 해제, `tilt up/down` 기본 9초. 라즈베리파이 UART(`/dev/ttyS0`) 설정 |
| 2026-10-23 | 통합 펌웨어 로봇 탑재, UART 명령·주행 동시 동작 확인. 앞문 방향을 닫힘 출발 기준으로 재확인 → `gate open` = `spin -400 1200`. 실물 시험(전원·순서·반복 5회·비상 정지·적재 쏟기) 통과. **회신 기능 추가**: `DONE`/`STOPPED`/`ERR timeout`/`ping→PONG`/부팅 `READY`. 시험용 펌웨어 자동 도움말 제거. 회신 기능 추가 후 업로드가 `CRC Fail 0xF020`로 반복 실패 → `help` 도움말을 짧은 영문으로 줄여 크기를 낮춰 해결, 실물에서 회신 확인 |
| 2026-10-23 (오후) | 연동 방식 **(가) 브리지 노드**로 결정. ROS 2 패키지 `transport_device_bridge` 작성 (`std_srvs/Trigger` 서비스 6개 + `/transport_01/device/raw` 토픽). 가짜 OpenCR 시험 16항목 통과 후 로봇 실물에서 덮개·쏟기·정지 확인. 0장을 서비스 호출 기준으로 변경, 9-1에 실패 응답·호출 예·런치 포함 방법 추가 |
| 2026-10-27 | 덮개가 닫힐 때 기구에 부딪혀 덜 닫히던 문제 → 하드웨어 수정 후 `set lid stime`으로 실측해 덮개 시간 **1500 → 1350 ms**로 변경 (`lid open` = `spin -400 1350`, `lid close` = `spin 400 1350`, 각 약 4.0초). 통합·시험용 펌웨어 기본값과 브리지 주석 갱신 |
