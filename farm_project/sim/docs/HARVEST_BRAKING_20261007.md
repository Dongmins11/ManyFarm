# 수확 로봇 회전·제동 보정

기준 main/1666a23 이후 미커밋. 사용자 진입 정렬 실패 보고와 “해결해” 요청으로 sim 범위만 변경했다.

## 확인한 현상

사용자 실제 Nav2 시험: 진입 위치 오차10.08mm는 충족했으나 방향 오차0.2486rad로 실패했다. 구동 로그에서 정지 명령 이후 차체 실제 월드 방향도 계속 회전했다. 단순 AMCL 오차라고 판단하지 않는다.

별도 fleet 시험에서 기존0.5rad/s 명령을 끊은 뒤 encoder 추가회전0.2534rad 재현.0.06rad/s로 속도만 줄이면 양방향 거의 회전하지 않았다. drive gain20배, velocity solver16, position solver64도 저속 조건을 만족하지 못했다. 이 비교 설정은 최종 운영 코드에서 제거했다.

## 최종 변경

- `base_sim.py` 및 `wheel_servo.py`: 연속된 실제 바퀴 관절 각도의 변화량/실제 시뮬 시간으로 속도 측정. PI 목표 보정 kp1/ki4, 적분 및 보정2rad/s 제한, 측정 필터0.25. 정지 요청 때 적분을 지우고 잔류 회전의 반대 방향으로 제동한다. 위치정답/차체 pose/teleport를 제어 입력으로 쓰지 않는다.
- `harvest.json`의 바퀴2개에만 `wheel_velocity_servo` 활성화. 예찰/실물/팔 정책·USD 원본과 물리주기는 변경하지 않는다. 현재60Hz 명령 프레임에 맞춰 dt_s=1/60을 설정한다.
- 수확 Nav2: 정렬회전0.5→0.06rad/s, 각가속도10→0.10rad/s², Nav2 yaw gate0.04→0.01rad. 공통 최종도착 방향 허용0.05rad는 그대로다. 앞선 stateful=false 유지. 저속 회전에 맞춰 progress120초/이동600초. 이로 인해 실패 판정도 이전보다 늦어질 수 있다.
- `drive_diagnostics.py`: 원래 요청 wheel target과 실제 보정 후 joint target을 별도 기록한다.
- `check_harvest_braking.py`: 포트·카메라 공유메모리·평가 스냅샷까지 분리한32sim초 물리 시험. 실제 ROS/Nav2 E2E와 구분한다.

## 검증

- 신규 servo4개 및 평행접근7개 검사 PASS. 기존371경로 검사 PASS. sim3패키지 build PASS. 원본농장USD SHA256 1d9887539611d65ec9c284a810bcd0b8015493db0158147c7188b414f95395e7 유지.
- 실제 Isaac 최종 encoder PI 고정시간 회전: 양방향0.06rad/s에서5초간 +0.2471/-0.3115rad 회전, 명령 종료 후 추가회전 -0.00319/-0.01317rad, 프로세스code0. high0.5rad/s 조건은 여전히 추가회전0.1871rad이므로 고속정렬을 유지하지 않는다.
- 마지막 목표각도 도달→정지 시험 결과는 `sim/runs/harvest_braking_20261007_servo1_heading1/result.json` 및 버전관리 요약을 따른다.
- 실제 Nav2 진입 경로 전체와 카메라/수확을 포함한 관제 E2E,480Hz 활동 중 차체 주행은 이번 보정 후 미검증. 부하/접촉 조건이 달라지면 추가 조정이 필요할 수 있다.
- 중간 저속휴면 비교는 평가 snapshot 공유경로 충돌로 실패했다. 시험 도구의 snapshot 경로를 분리했다. 해당 실행과 중지한 비교의 비정상종료는 최종PASS에 포함하지 않는다. 운영 snapshot은 다음 정상 운영 캡처로 갱신되며 시험 중 snapshot 기반 평가 기록은 섞였을 수 있다.

## 사용

all launch 종료 후 재시작해야 적용된다. 저장된 첫 HarvestTask Goal을 다시 보낼 수 있으므로 예찰부터 재실행할 필요는 없다. 기동 후 다음 값 확인:

```bash
ros2 param get /harvest_01/controller_server RPP.rotate_to_heading_angular_vel
ros2 param get /harvest_01/controller_server RPP.max_angular_accel
ros2 param get /harvest_01/controller_server goal_checker.yaw_goal_tolerance
```

기대값0.06/0.10/0.01. 직접 물리 회전 재현은 다음과 같다(별도 Isaac 인스턴스를 띄운다).

```bash
cd ~/main/farm_project
/usr/bin/python3 sim/tools/check_harvest_braking.py --servo --heading
```

되돌림은 harvest.json의 wheel_velocity_servo 제거와 이번 수확 Nav2 속도/시간 설정 복원이다. 앞선 평행경로 수정과 다른 미커밋 작업은 보존한다. 커밋·푸시는 하지 않았다.

최종 목표각도 시험 PASS: +0.3/-0.3rad 회전 요청 후3초 정지 확인, encoder 최종 오차0.00510/0.00932rad(0.29°/0.53°), 허용0.05rad.960개 상태 수신, 정상 종료code0. 고정시간 phase용 cases는 이 목표각도 시험에서 판정에 사용하지 않으며 heading_runs/checks를 확인한다. [버전관리 결과](changes/HARVEST_BRAKING_VALIDATION_20261007.json).


## 실제 Nav2 코너 정지 보정 — 2026-10-07 18시 사용자 재현

controller_server_680852 로그에서 Failed to make progress 확인. 실제 구동 session539072af6d254ae4ad8e9618628ccc0b: 첫 코너 이전 (-1.998,11.838) 부근에서 선속도0, 각속도 명령 약±0.005rad/s를 반복하며 정지. 앞선 목표각도 시험은 일정0.06rad/s를 입력했으므로 Nav2의 현재 속도 피드백/가속 제한 결합을 검증한 것이 아니었다.

이번 수정은 RPP.max_angular_accel=0.10→1.2rad/s².20Hz 한 제어 주기의 변화 허용량을0.005→0.06rad/s로 늘려 정지 상태에서 검증된 저속 정렬 명령에 도달할 여유를 준다. rotate_to_heading_angular_vel=0.06, 최종 정지 허용값 및 충돌 검사/바퀴 PI는 유지한다. 전체 Nav2 재시험은 아직 미실행이며 해결 완료로 간주하지 않는다.

실행 중 반영:
```bash
ros2 param set /harvest_01/controller_server RPP.max_angular_accel 1.2
```
재시작 시에도 새 설정을 읽는다. 과거 위0.10 표는 최초 적용 기록이며 현재 기준은1.2다.
