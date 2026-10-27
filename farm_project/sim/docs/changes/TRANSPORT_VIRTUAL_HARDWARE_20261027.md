# 운송 가상 하드웨어 연결 — 2026-10-27

기준: main `b5ef6f2` + 이전 운송 통합 미커밋 변경. 승인: 사용자 “가상 하드웨어 연결해”. 이번 변경은 sim 장치·자산·실행·검증이며 공통 미션/주행·실물 설정을 추가 변경하지 않았다. 커밋·푸시하지 않았다.

## 결과와 완료 범위

운송 USD의 두 바퀴를 `cmd_vel`에 연결하고 실제 관절 회전으로 odom을 계산한다. PhysX raycast 라이다, USD 렌더 카메라, CameraInfo, joint_states, TF, 공유 clock을 기존 가상 장치 어댑터로 연결했다. 정답 위치는 진단 파일에만 기록한다. `map→odom` 위치 추정/Nav2 및 운송 업무 서버는 이번 장치 launch에 포함하지 않는다.

- 실제 Isaac 농장: 예찰·수확·운송 3대, Domain 13/SUBNET, headless, CPU PhysX(MBP), 60Hz 물리/30Hz 렌더. 60 시뮬레이션 초 완료, 로봇별 상태 패킷 1,800개. 예찰·수확 업무 서버와 Nav2는 이 시험에서 실행하지 않았다.
- 실제 ROS 검사 8/8: 전진, 양의 yaw 회전, cmd_vel 유실 후 정지, 라이다, 바퀴 이름, TF, Image/CameraInfo 동기, 카메라 재개.
- 최종 실제 차체 순변위 0.1906m, yaw 변화 0.4390rad. 관절 odom과 별도로 USD/PhysX 자세를 확인했다. 저속 명령은 0.05m/s·0.2rad/s이며 이 수치는 전체 경로/정밀 도킹 성능 평가가 아니다.
- 카메라는 시작 OFF → 영상 구독 ON → 구독 해제 OFF → 재구독 ON → 해제 OFF. 최종 fleet 렌더 프레임 147개. 구독 종료 시 발행뿐 아니라 Hydra 렌더도 중단한다. 요구 갱신은 0.2초, 어댑터 유실 시 2초 wall lease로 꺼진다. 기존 예찰/수확 카메라 동작은 유지했다.
- 오프라인/ROS 구성 검사 87개, USD 형상 검사 5개 통과. sim 3패키지 빌드 통과.
- 측정 구간의 실제 시간/시뮬 시간은 약 1.18배. 시작·종료 시간은 제외했으며 이번 3대 센서/저속 시험에 한정한다.

## 구동 불량 원인과 변경

첫 시험은 센서/TF/카메라가 정상인데 전진·회전이 실패했다. 0.05m/s 전진 명령에 odom 증가가 약 0.4mm였고 실제 차체도 거의 움직이지 않았다. 이를 성공 처리하지 않았다.

분리 시험 결과:

| 조건 | 관측 |
|---|---|
| 원본 바퀴/캐스터 | 3초 실제 이동 약 0.8mm |
| 접촉/중력 영향 제거 | 바퀴는 목표 1.515rad/s로 정상 회전 |
| 감쇠 변경·solver 반복 변경 | 구동 불량 유지 |
| 고정 캐스터 마찰만 0 | 바퀴는 회전하지만 차체 이동 부족 |
| 원통 유지 + 타이어 마찰 0.8 | 구동 불량 유지 |
| 둥근 접촉 단면 + 캐스터 마찰 0 + 타이어 마찰 0.8 | 3초 실제 이동 약 0.143m |

원본의 넓은 원통 접촉과 고정 박스 캐스터 조합에서 접촉 제약이 주행을 막았다. ROS 명령 전달·RPP·도착 판정 문제로 확인된 것은 아니다. PhysX 내부 접촉 계산의 정확한 결함까지 입증한 것은 아니며, **개별 마찰 변경만으로 해결됐다고 해석하면 안 된다.**

원본 `transport_robot.portable.usd`를 보존하고 같은 폴더의 `transport_robot.sim.usda`가 이를 참조한다. 기존 수확 타이어 생성 함수를 바퀴 이름 인자만 추가해 재사용했다. 반경 33mm/폭 18mm, 질량·관성·joint drive는 유지하고 폭 방향 21개 원통으로 둥근 단면을 만들었다. 캐스터는 지지 형상을 유지하면서 자유 구름을 마찰 0으로 근사한다. 타이어 0.8/캐스터 0은 **실물 마찰 실측값이 아니다.**

카메라 재개 때 중첩 visual instance에서 `cannot find protoPath` 58건도 확인했다. 운송 자산의 시각 인스턴스만 풀어 형상·재질을 유지했고, 최종 통합 실행에는 해당 오류 및 `[Error]` 로그가 없었다.

## 설정·호환성

- `transport.json`: wheel_left/right_joint, 반경 0.033m, 간격 0.288m, namespace `transport_01`, UDP 17620/17621. `model=waffle`.
- 속도 상한은 최종 설정에서 실물 `feature_dongmin 9686aca`의 velocity_smoother 기준 0.15m/s·1.0rad/s. 실제 시험은 이보다 작은 0.05m/s·0.2rad/s만 사용했다. 시험 당시 angular clamp는 0.6이었으며 최종 1.0 상한 영역의 고속 주행은 미검증이다.
- station 8003 `(2,13.25)`, yaw −π/2: 기존 그래프 30513(8003→9014)의 출발 방향. `task.yaml` 원본과 생성된 `station_spawn.json`을 같이 반영했다. 선별장 yaw를 임의 확정하지 않았다.
- 카메라 1280×720/10Hz, 실물 waffle의 `T_base_camera` 장착값 사용. 실물 IMX219 내부 보정 파일은 저장소에 없어 **임시 수평 90° FOV, fx=fy=640, 왜곡 0**을 사용한다. 정밀 도킹 시험 전 실제 보정값 확인이 필요하다.
- `transport_hardware_fleet.json`: 운송 단독, 수확 평가/팔 물리 없음. `transport_fleet.json`: 기존 예찰/수확 + 운송.
- 수확 팔이 없으면 fleet 평가 설정을 생략할 수 있다. 팔이 있으면 평가 설정을 계속 요구한다. 팔 없는 운송 장치는 별도 과실 물리 프로파일 없이 같은 월드의 물리 주기를 따른다. 서로 다른 명시적 물리 프로파일은 계속 거부한다.
- `all.launch.py`의 `transport` 기본값 false. 기존 실행을 자동으로 3대로 바꾸지 않는다. transport=true는 현재 **가상 장치만** 시작한다.

## 실행

운송 단독 가상 하드웨어:

```bash
cd /home/ysy/main/farm_project
source scripts/env.sh sim
export ROS_DOMAIN_ID=13
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
ros2 launch farm_sim_runtime all.launch.py \
  project_root:="$PWD" scout:=false harvest:=false transport:=true \
  rviz:=false headless:=true physics_device:=cpu \
  isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python
```

3대 하드웨어만 시험하려면 위 명령에 `fleet_config:=sim/ros_ws/src/farm_sim_config/config/transport_fleet.json`을 추가한다. 기존 예찰/수확 업무 bringup도 함께 시작하려면 scout/harvest를 true로 선택한다. 아직 운송 업무/도킹은 실행하지 않는다. 같은 포트/namespace의 기존 시뮬과 중복 실행하지 않는다.

실제 ROS 검사(별도 터미널, 같은 ROS 환경):

```bash
python3 sim/tools/transport_hardware_smoke.py \
  --output sim/runs/transport_hardware_manual/result.json
```

이 검사는 transport_01에 짧은 전진·회전 명령을 실제로 보낸다. 제어 없이 센서만 보는 도구가 아니다. 시작까지 최대 360초 대기한다. `all.launch`의 `duration_s:=60`을 사용하면 fleet를 제한 시간 후 종료할 수 있다.

토픽: `/transport_01/cmd_vel`, `odom`, `scan`, `joint_states`, `camera/image_raw`, `camera/camera_info`; 공용 `/tf`, `/tf_static`, `/clock`. 카메라는 image 구독이 있을 때만 켜진다.

## 검증 자료·남은 항목

공유 자료: `sim/docs/test_results/20261027_transport_hardware/validation.json`, `failure_original_contact.json`, `contact_diagnostics.txt`, `transport_drive.jsonl`, `runtime_events.txt`, 테스트/빌드 결과와 SHA256. 원본 로그·격리 시험 스크립트는 `sim/runs/transport_hardware_20261027/`, 실제 자세 로그는 `sim/runs/drive_diagnostics/41457741536d404986fb5d37100b00b1/`.

첫 구동 실패, 중간 자산 생성 실패 후 중단한 실행, 구동 통과/렌더 오류 실행을 별도 보존했다. SDK 종료 때 GUI 메뉴 callback의 `get_stage_state` AttributeError 2건이 있었으나 60초 완료 뒤 발생했고 모든 프로세스는 정상 종료했다. SDK 종료 메시지까지 무오류라고 보고하지 않는다. 원본 자산의 비어 있는 base/caster visual 참조 경고도 남아 있다.

기존 `test_harvest_motion.py::HarvestLaunchTests` 4개는 구식 공통 launch mock이 GroupAction을 지원하지 않아 최종 묶음에서 제외했다. 수정 전 HEAD에서도 같은 ImportError를 재현해 자료에 남겼다. 이번 transport/기존 DDS·태그 launch 구성 검사는 실제 launch 패키지로 통과했고, 실제 Isaac 단독/3대 실행으로 별도 검증했다.

**미완료:** ArUco 42/41/40 배치·검출·정밀 도킹, 운송 Nav2/위치 추정·업무 조립, 바구니 정렬 유지 판정, 관제 운송 요청/인계/교통, 선별장 이동 E2E. 과실 배출·낙하 물리/기구 구현 제외(D-063), station 마커 생략 정책은 유지한다.

복원: 이번 sim 코드 변경과 transport 설정/launch/파생 자산만 되돌린다. 원본 USD와 기존 scout/harvest 설정은 보존되어 있다. 이전 운송 공통 통합/사용자 변경을 함께 삭제하지 않는다.

## 전달 패치

이번 단계 파일만 담은 로컬 전달본: `sim/runs/transport_hardware_20261027_patch.zip`. 앞 단계 운송 공통 패키지는 포함하지 않으므로 해당 통합이 적용된 작업 트리에 사용한다. 이 작업 공간에는 이미 적용되어 있어 다시 풀 필요가 없다. 다운로드한 다른 작업 공간에서의 적용 예:

```bash
unzip -o "$HOME/Downloads/transport_hardware_20261027_patch.zip" -d "$HOME/main/farm_project"
```
