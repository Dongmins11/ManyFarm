# 로봇팔 인수 자료의 농장 물리·오른팔 좌표 반영

작성일: 2026-10-06 KST. **승인한 기초 물성·오른팔 좌표 적용과 실제 Isaac 기동 검증을 완료했다. Nav2 목표 이동과 학습 정책 수확은 후속 검증 범위다.**

이 문서의 전체288개·고정480Hz 설명은 최초 적용과 기준 검사 기록이다.
현재 운용에는 [동적 주기·수확 주변 과실 활성화](ADAPTIVE_HARVEST_PHYSICS_20261006.md)를 추가했다.
유휴60Hz/수확480Hz 전환과 실제 동시 주행에서 관측한 수치 응답 차이는 새 보고서를 따른다.

## 1. 승인 범위와 현재 동작

사용자가 승인한 1차 적용은 농장 과실 물성, 수확 로봇 오른팔 물성, 예찰에서 생성하는 수확 목표의 오른팔 좌표 기준이다. 과실 외형은 Teacher 기준 **폭 70 mm·높이 75 mm로 통일**하는 것으로 확인받았다. 기존 식물마다 다른 과실 스케일을 유지하는 변경이 아니다.

시뮬 실행 시 기존 농장의 과실 ID·root 위치·회전을 유지하고, 독립 과실 템플릿과 물리 결합을 session layer에 적용한다. 수확 로봇은 기존 주행 자산에 오른팔 drive·그리퍼 접촉 재질·박스 바닥 충돌을 추가하고 초기 HOME를 배치한다. 원본 USD를 저장하거나 수령 번들을 수정하지 않는다.

**Teacher 정책은 아직 실행하지 않는다.** 공통 HarvestTask 서버의 `ARRIVAL_ONLY_NO_HARVEST`, 도착 시 `SUCCESS/harvested_count=0` 계약도 그대로다. 물리 분리 이벤트, 예찰 예상 개수, 작업 상자 정답 개수, 실제 파지·적재 성공은 서로 다른 값이다.

이번 적용은 `sim/` 코드·설정·자산·검사에 한정한다. 공통 `robot/ros_ws/src/` 업무 코드, 실물 설정, 메시지 정의는 변경하지 않았다. 시작 당시 존재하던 미커밋 인수 문서와 다른 작업자 변경은 보존한다.

## 2. 설정과 자산 원본

실행 설정은 [robotarm_physics.json](../ros_ws/src/farm_sim_config/config/robotarm_physics.json) 하나로 묶는다. `scout.json`, `scout_fleet.json`, `harvest.json`의 `runtime.robotarm_physics_config`가 이 파일을 가리킨다. 장치 설정의 기존 렌더 키는 `render_hz`다.

| 구분 | 적용 위치 | 역할 |
|---|---|---|
| 과실 자산 | `sim/assets/fruit/teacher_9g/` | 3색 USD 템플릿, 원본 과실 USD·텍스처, provenance |
| 과실 scene 적용 | `farm_sim_runtime/fruit_asset_setup.py` | 기존 과실 root를 유지하며 크기·질량·접촉·베드별 인장 방향 구성 |
| 줄기 수치 모델 | `farm_sim_devices/stem_physics.py` | attachment4/response5의 외력·토크·분리 누적시간 계산 |
| Isaac 결합 어댑터 | `farm_sim_devices/fruit_attachment.py` | 실제 rigid body pose·COM·관성을 읽고 매 물리 tick에 외력 적용 |
| 오른팔 scene 적용 | `farm_sim_runtime/robotarm_asset_setup.py` | 오른팔 drive, 그리퍼 재질, 바닥 충돌의 session override |
| 박스 바닥 | `sim/assets/robots/harvest_physics/box_floor_v3.usd` | 좌우 바닥 body에 추가할 4개 충돌 타일 |
| 실행 수명·시간 분주 | `farm_sim_runtime/harvest_physics.py` | 프로파일 검사, 초기화, 물리 tick/렌더 분리, 분리 로그 |
| 진입점 | `farm_sim_runtime/run_fleet.py`, `run_sim.py` | 통합·예찰 단독 실행에 물리 환경 연결 |

위 Python 경로의 패키지 루트는 각각 `sim/ros_ws/src/farm_sim_runtime/`와 `sim/ros_ws/src/farm_sim_devices/`다. 자산 내부 참조는 전달용 독립 묶음 안에서 해결하며 실행에 `sim/runs/robotarm/received_*` 경로를 사용하지 않는다. 수령 원본은 [수령 보고서](ROBOTARM_BUNDLE_RECEIPT_20261006.md)에 기록한 상태로 보존한다.

원본 Teacher 작업공간의 `prepare_receiver.py`를 실행하는 것과 이번 농장 적용은 별개다. 원본 캐시의 절대 mesh 경로를 바꾸면 IsaacLab의 URDF hash 검사 때문에 USD가 재생성될 수 있으므로, 수령 원본을 직접 이식·실행하지 않는다. 정책 독립 평가를 할 때 별도 실행 사본과 캐시 보존 절차가 필요하다.

## 3. 과실·줄기·오른팔 물리

### 과실

| 항목 | 설정 |
|---|---|
| 질량 | 0.009 kg |
| 크기 | XY 최대 폭 0.070 m, 전체 높이 0.075 m |
| 정지/운동 마찰 | 1.0 / 1.0 |
| 반발 | 0.02 |
| contact/rest offset | 0.001 / 0 m |
| 선형/각 감쇠 | 0 / 0.02 |
| 선속도/각속도 상한 | 3 m/s / 20 degree/s(약 0.349066 rad/s) |
| 분리 임계력 | 과실마다 seed 713으로 2~3 N 범위에서 고정 추출 |
| 중력 | 활성. 별도 +mg 지지 외력 없음 |

시각 메시·색·텍스처와 root ID는 독립 템플릿 참조로 연결한다. 기존 농장 root의 스케일은 제거하고 원래 world 위치·회전만 보존하여 같은 Teacher 크기로 맞춘다. root, 시각 AABB 중심, COM, 파지 중심, 꼭지점은 동일 좌표가 아니다. 파지 중심은 전달 자산에서 local Z 방향으로 root보다 6 mm 아래다.

연결점은 색별 자산 bounds로 계산한 값을 `attachment_local_m_by_color`에 저장한다. 빨강 기준 약 `[0.0175298323,0.0125881526,0.0375]` m이며 노랑·초록도 각 자산의 정확값을 사용한다.

속도 상한은 독립 템플릿과 농장 session override 모두에 반영했다. 각속도 단위는 원본 IsaacLab/USD의 degree/s이므로 20 rad/s로 해석하지 않는다. §7의 최종 USD·GPU 검사는 이 보완 후 실행했다.

`contact_solver_refine=false`에 맞춰 과실의 solver/sleep/depenetration 추가 override를 넣지 않는다. 과실 body의 CCD 플래그는 true다. **실행 시 scene CCD도 true다.** 2026-10-06 GUI 성능 계측에서 Isaac Core `World` 기본 초기화가 CPU PhysX/MBP/TGS와 scene CCD=true를 적용함을 확인했다. 기존의 “scene CCD를 활성화하지 않는다”는 설명은 잘못되어 정정한다. 전달 Teacher의 scene CCD=false와 이 설정은 다르며, 이번 과실/팔 이식이 전체 물리 환경의 완전한 동등 재현을 뜻하지 않는다. 이 플래그 확인을 모든 낙하·접촉의 터널링 방지 검증으로 해석하지 않는다. 실제 설정과 성능은 §11을 참조한다.

### 줄기 결합

고정된 초기 꼭지 앵커와 움직이는 꼭지 사이의 변위·속도에 implicit spring/damping을 적용한다. 인장 강성 60 N/m, 횡방향 강성 15 N/m, 수직 강성 40 N/m, 선형 감쇠 4.2 N·s/m, 회전 복원·감쇠 계수 0.015/0.002를 사용한다. 실제 body COM과 관성을 사용하며, 힘은 월드 COM에 적용하고 꼭지 lever에 따른 토크는 한 번만 더한다.

분리는 다음 OR 조건이 연속 40 ms 충족될 때 발생한다. 조건이 끊기면 누적시간은 0으로 돌아간다.

1. 인장력이 과실별 임계력을 넘고 인장 변위가 12 mm 초과.
2. 전체 변위 40 mm 이상이고 복원 하중이 임계력의 2배 초과.
3. short-hook 인장 변위 25 mm 이상 또는 전체 변위 40 mm 이상.

분리 대기 중 복원력 크기는 과실별 임계력으로 제한한다. 분리된 과실에는 줄기 외력을 다시 적용하지 않는다. Physics native breakable joint 또는 실제 변형 줄기 mesh 해석이 아니며, 과실을 그리퍼에 weld하거나 위치를 따라 움직이게 하지 않는다. 목표·비목표·녹색 과실도 동일한 물리 조건을 적용한다.

인장축은 각 베드의 중심선에서 과실 쪽 통로를 향하는 world 단위벡터다. 양쪽 Section과 `T_map_world`를 사용해 계산하며, 농장 전체에 월드 −X를 고정하지 않는다.

### 오른팔과 박스

팔 관절 순서는 `arm_2_shoulder_pan`, `arm_2_shoulder_lift`, `arm_2_elbow_flex`, `arm_2_wrist_flex`, `arm_2_wrist_roll`, `arm_2_gripper`다.

| 항목 | 팔 5관절 | 그리퍼 |
|---|---|---|
| stiffness | 25 N·m/rad | 8 N·m/rad |
| damping | 1.5 N·m·s/rad | 0.3 N·m·s/rad |
| effort 한도 | 2 N·m | 0.5 N·m |
| 관절 속도 한도 | 1.2 rad/s | 1.5 rad/s |
| HOME | `[0,-1.39,0.77,0.62,0.0487963268]` rad | 1.1 rad |

USD angular drive의 degree 단위에 맞춰 stiffness/damping에는 π/180, target/velocity에는 180/π를 적용한다. effort는 N·m 그대로다. 0.5 N·m는 시뮬 설정이며 실물 STS3215 실측 출력으로 해석하지 않는다.

그리퍼 양쪽 body의 기존 충돌체에 과실과 같은 접촉 재질을 바인딩한다. 박스 바닥은 `box_bottom_left/right` 아래 타일을 추가하여 실제 받침 충돌을 구성한다. 기존 바닥 충돌체가 이미 있으면 중복 적용을 거절한다.

바퀴·캐스터·왼팔 drive·차체 articulation 구조·Nav2 구동 부호는 보존한다. 최초 reset 뒤 오른팔 6축만 HOME에 배치한다. HOME target 설정은 정책 실행이나 파지 성공을 뜻하지 않는다.

오른팔 질량·관성도 수신 USD와 대조했다. 가동 body6개 중5개는 mass/COM/관성/주축 값이 동일하다. 나머지 gripper는 모바일의0.087kg body에 camera0.075kg·mount0.018kg 등이 고정 연결돼 있고 수신 converter는 이를 약0.180kg으로 병합한다. 고정 body를 같은 좌표계에서 합산한 차이는 질량 약6.5e-9kg, COM3.93e-8m, 관성텐서3.71e-10kg·m² 이하로 반올림 수준이다. 질량을 중복 가산하지 않았다.

현재 모바일 로봇 articulation의 solver 32/1·self-collision false와 주행 바닥 설정을 유지한다. 원본 Teacher는 로봇 spawn에서 solver 12/4·self-collision true를 사용한다. 이를 모바일 전체에 복사하면 바퀴·차체까지 달라지므로 적용하지 않았다. 따라서 이번 작업은 전달한 과실·줄기·오른팔 설정의 농장 통합이며 Teacher 전체 환경의 완전 동등 재현은 아니다.

## 4. 오른팔 좌표와 예찰→수확 목표

현재 주행 자산은 논리 `base_footprint`와 자산 축이 yaw π만큼 다르다. 실제 URDF 고정 joint 체인을 이 변환과 합성하면 오른팔 `arm_2/base_link`의 논리 장착점은 `[+0.19,+0.185,0.713]` m, yaw는 +π/2다.

전달한 root 외곽은 팔 기준 X `[0.265,0.365]`, Y `[-0.175,+0.175]`, Z `[-0.10,+0.35]` m다. 이를 논리 주행 좌표로 바꾸면 작업 상자 중심 `[0.19,0.500,0.838]` m, 크기 `[0.35,0.10,0.45]` m가 된다. `task.yaml` 16구역과 생성된 `scout_survey.json`, `harvest_audit.json`이 이 값을 공유한다. `rebuild_route_data.py`는 예찰·평가 상자를 같은 task 원본에서 생성한다.

예찰 영상 크롭 높이도 `[0.613,1.063]` m로 맞췄다. 실제 예찰 입력은 RGB-D 표면 좌표이고 audit은 시각 AABB 중심이므로, 이 설정을 root 또는 파지점 자동 변환으로 설명하지 않는다. 정책 연결 단계에서 실제 목표 중심·자세·TF 계약을 별도로 맞춰야 한다.

기존 왼팔 임시 설정과 같은 Window를 비교하면 새 로봇 base Goal은 주행 방향 −0.38 m, 베드 반대 방향 −0.065 m 이동한다. 예를 들어 SEC01 중간 위치의 합성 관측에서 새 Goal은 약 `(-6.015,6.045)` m다. 목표 yaw, 베드 원본 위치, 경로 원본 노드·엣지는 바꾸지 않는다.

기존 수확 그래프에서 새 Goal까지 실제 수직 거리는 0.060 m다. 수확 전용 `max_goal_distance_m`를 0.09 m로 설정했다. 이는 기하 변경 0.065 m와 기존 0.02 m 연결 여유를 포함한 후보 검색 한계다. 원본 graph를 이동시키거나 Goal을 레일 위로 대체하지 않는다. 공통 RouteGraph는 기존 엣지에서 실제 Goal로 이어지는 짧은 끝 연결을 Path에 포함한다.

| 구분 | 수확 설정 | 의미 |
|---|---|---|
| 그래프 Goal 연결 한계 | 0.09 m | 기존 엣지의 가까운 연결 후보를 찾는 한계 |
| 최종 도착 허용 | 0.02 m / 0.05 rad | 이동 종료 후 정지·TF 측정값으로 판정 |
| Nav2 goal checker | 0.015 m / 0.04 rad | 최종 도착 조건보다 엄격한 제어 종료 gate |

Nav2와 최종 도착 허용값을 같게 하면 기존 공통 사전검사가 거부한다. 예찰 주행 허용값은 변경하지 않았다. RPP 최소 접근속도 0.03 m/s와 제어 20 Hz는 약 1.5 mm/step이며 velocity smoother deadband는 0이다. 이것만으로 실제 정밀 정지 수렴을 보장하지는 않는다.

Teacher 근거리 후보 18개는 이산 평가 후보다. 외곽 직육면체 전부의 IK·경로 안전·수확 성공을 보장하지 않는다. 이 18개 중 초기 간격 0.18 m를 동시에 만족하는 최대 조합은 3개이며, 현재 농장 전체 배치를 18개 후보로 재배치하지 않았다.

## 5. 물리 시간과 실행 순서

물리는 480 Hz(dt=1/480 s), 렌더는 60 Hz다. 정책 기준 주기 20 Hz는 프로파일 명세로만 남으며 현재 정책 추론은 호출하지 않는다. 한 렌더 동안 여러 물리 tick이 외력 갱신 없이 진행되는 것을 막기 위해 `World.step(render=True)`를 사용하지 않는다.

실행 순서는 다음과 같다.

1. 프로파일·scene 단위 확인, 베드 충돌·과실 물성·오른팔 session override 구성.
2. 과실 RigidPrim view 등록, `world.reset()`.
3. 오른팔 HOME 배치, 실제 과실 질량·COM·관성 확인.
4. 매 tick: 줄기 외력 갱신 → `world.step(render=False)` 한 번 → dt 검사.
5. 8 tick마다 `world.render()` 한 번. 렌더 중 물리 시간이 추가로 진행되면 오류로 중단.

`run_fleet.py`는 예찰·수확 로봇을 함께 초기화하고, `run_sim.py`는 기존 예찰 단독 역할을 유지한다. 단독 실행에 수확 로봇이 이미 있는 scene을 주면 해당 팔의 물성·HOME 유지도 구성한다. 현재 원본 농장 scene에는 수확 로봇이 없어 이 분기를 생략하고, fleet은 수확 로봇을 추가한 뒤 적용한다. 두 진입점 모두 명시적 project root를 사용하여 별도 `assets_root`에서도 프로파일 경로를 정확히 찾는다. `SimulationApp.fast_shutdown=False`로 실행하여 종료 과정이 Python 오류·결과 저장을 가리지 않게 한다.

정상 앱 정리 후에도 Kit의 내부 스레드가 남는 현상이 있어 CLI 진입점은 `app.close()`·로그 정리·출력 flush를 마친 뒤 실제 성공/실패 종료코드를 보존해 프로세스를 끝낸다. 물리 시험 도구는 종료 전에 JSON을 fsync하여 실패 원인을 보존한다. 초기 시험에서 이미 정리가 끝났지만 남아 있던 이번 시험 프로세스들은 별도로 종료했다.

실행별 물리 로그는 `sim/runs/robotarm/physics/<session>/setup.json`, `detach_events.jsonl`, `summary.json`에 저장한다. `PHYSICAL_DETACH`는 분리 사실만 기록하며 수확 성공으로 집계하지 않는다. 기존 scene truth는 평가에만 사용하고 공통 비전·제어 입력으로 보내지 않는다.

## 6. 재현 명령

아래 명령은 Isaac 물리 검사만 수행한다. 정책 학습·추론, ROS 수확 Goal, 실물 서보를 시작하지 않는다. 다른 Isaac 실행과 GPU를 중복 사용하지 않도록 기존 실행을 확인한다.

```bash
cd /home/ysy/main/farm_project
PYTHONDONTWRITEBYTECODE=1 /home/ysy/isaac/env_isaaclab/bin/python \
  sim/tools/check_harvest_physics.py \
  --expected-fruits 288 --pull --fall-seconds 0.6 \
  --output sim/runs/robotarm/physics_smoke_review/result.json
```

기본 정지 검사는 2초다. `--pull`은 지정 과실 COM에 외력을 주어 실제 분리·분리 후 중력 궤적을 확인한다. 그리퍼의 정상 파지·운반·박스 적재 시험이 아니다. 실패 시 결과 JSON의 `status`, `checks`, 오류와 로그를 함께 읽는다. shell exit code만으로 성공을 판정하지 않는다.

실제 fleet 진입점의 2초 정지 기동 검사는 다음과 같다. ROS/Nav2 이동 Goal을 보내는 명령은 아니다.

```bash
/home/ysy/isaac/env_isaaclab/bin/python \
  sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py \
  --project-root /home/ysy/main/farm_project \
  --fleet-config sim/ros_ws/src/farm_sim_config/config/harvest_fleet.json \
  --module-path /home/ysy/main/farm_project/sim/ros_ws/src/farm_sim_runtime \
  --module-path /home/ysy/main/farm_project/sim/ros_ws/src/farm_sim_devices \
  --module-path /home/ysy/main/farm_project/robot/ros_ws/src/farm_common \
  --headless --duration-s 2
```

오프라인 검사 예시는 다음과 같다. 실행 환경에 맞는 Python을 사용하며 USD 검사는 별도 Isaac USD/PhysX schema 환경이 필요하다.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s sim/tests -p test_harvest_arm_geometry.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s sim/tests -p test_harvest_physics_runtime.py -v
PYTHONDONTWRITEBYTECODE=1 python3 sim/tools/validate_route_data.py
```

## 7. 1차 적용 당시 검증 기록

과실 속도 상한 보완 후 **정적·단위 검사 61개**, 기존 경로 371개, Isaac GPU 물리 검사와 실제 fleet 정지 기동을 통과했다. IsaacSim 5.1.0.0·IsaacLab 0.54.2·Python 3.11 환경에서 검사했다. 정책은 로딩하지 않았으며 실제 Nav2 이동·그리퍼 파지·적재 성공은 검증하지 않았다.

| 검증 | 최종 확인 | 검증 범위 |
|---|---|---|
| 좌표·설정 회귀 | 7개 통과. 실제 URDF chain, 16구역 Goal/평가 상자, 48개 대표 Goal의 끝 연결·정적 지도 centerline 검사 포함 | 동적 장애물·로봇 footprint·실제 Nav2 주행 인증 아님 |
| PhysicsTicks·프로파일 회귀 | 11개 통과. 2초=960 physics/960 외력 갱신/120 render, 60 Hz 호환·dt 오류·프로파일 불일치 거부 | 실제 Isaac 동작은 아래 GPU 검사와 구분 |
| 기존 수확 계약·실행 조합 | action 1개·motion 15개 통과 | mock/정적 검사이며 전체 ROS E2E 아님 |
| 줄기·진입점·TF·station | 각각 8·2·4·6개 통과 | 위 34개와 합계 54개 |
| 과실·팔 USD 정적 검사 | 7개 통과, skip 0. 속도 상한·source 참조·크기·물성·session만 수정·기존 robot 속성 보존 확인 | [최종 로그](../runs/robotarm/asset_setup_static_final_20261006.log). 총 61개 |
| 기존 경로 데이터 검사 | 16구역·80관측·371경로 통과 | 기존 graph 경로 검사이며 정밀 도착 성공률 아님 |
| sim 빌드 | `farm_sim_config`, `farm_sim_devices`, `farm_sim_runtime` 3개 패키지 통과 | 공통 업무 코드 변경 없음 |
| GPU 정지 물리 검사 | 288개 2초 유지, 자발 분리 0. 최대 root 변위 0.02053016 m, base 변위 0.00009645 m, 바퀴 변위 0.00137619 rad | 9g·HOME·시간 tick·유한 상태·원본 보존 포함 13개 check 모두 true |
| 외력 분리·낙하 검사 | 선택 과실에 3 N 외력. 40 ms 조건을 20 tick=0.041667 s 유지 후 물리 분리, 이후 0.6초에 Z가 0.902256 m 하강. 최종 attached 287·detached 1 | 줄기 외력 종료와 중력·바닥 접촉 확인. 정책 또는 그리퍼 시험 아님 |
| fleet 실제 진입점 | 2.0000001043초 정지 실행 완료. 예찰 카메라 29 frame, 두 로봇 telemetry 각 60 packet, station pose 검사 통과, 과실 288개 유지·분리 0 | 실제 카메라·두 로봇·물리 환경 기동 확인. 목표 주행 미실행 |

최종 GPU 결과는 [result.json](../runs/robotarm/physics_smoke_gpu_20261006/result.json)이다. 최종 종료 보완 재검사 시작은 2026-10-06T07:12:51.474942+00:00이며 `status=PASSED`, `policy_loaded=false`, 프로세스 종료코드0을 확인했다. 원본 scene의 실행 전후 SHA-256은 `1d9887539611d65ec9c284a810bcd0b8015493db0158147c7188b414f95395e7`로 같다. 속도 상한 보완 전의 짧은 낙하 관측은 최종 결과에 합산하지 않았다.

fleet [실행 로그](../runs/robotarm/fleet_physics_smoke_20261006.log)와 session `98d899878bda4638a1aa82bbaa51f46b`의 [setup](../runs/robotarm/physics/98d899878bda4638a1aa82bbaa51f46b/setup.json)·[summary](../runs/robotarm/physics/98d899878bda4638a1aa82bbaa51f46b/summary.json)에 실제 적용값과 종료 상태가 있다. `detach_events.jsonl`은 비어 있다. 종료 보완 재검사도 정상 종료코드0을 확인했다. 실행 완료 후 Isaac GUI menu extension 종료 시 `NoneType.get_stage_state` 예외와 기존 USD visual reference 경고가 로그에 남았다. 이는 정상 기동·결과 저장 기록과 구분하며 경고 없는 전체 시뮬 검증으로 보고하지 않는다.

원본 줄기 수식과 256개 seeded state를 대조했을 때 최대 힘 오차 약 4.44e-16 N·토크 오차 약 1.39e-17 N·m였다. 초기 과실 collision mesh의 world AABB에 2 mm 여유를 둔 정적 검사에서는 과실 288개 상호 중첩과 기존 환경 28개 collider 중첩이 없었다. 실제 접근 중 접촉 안전이나 주변 과실 충돌 회피를 보장하는 검사는 아니다.

## 8. 다음 단계와 공통 변경 경계

1. **실제 수확 주행:** 현재 오른팔 Goal로 fleet+Nav2 이동을 실행하고 위치 0.02 m·yaw 0.05 rad·정지를 확인한다. 기존 레일에서 멈춰 성공하는지, 짧은 옆 방향 연결에서 RPP가 수렴하는지, 주변 footprint·장애물·AMCL 오차를 로그로 확인한다.
2. **원본 Teacher 독립 9g 평가:** 수령 번들의 정책 4개와 run/profile 해시, 실행 환경·카메라·탐지기 경로를 맞춘 별도 실행 사본에서 색별 지정 목표 평가를 재현한다. 포장 시점 코드와 과거 평가 당시 코드의 완전 동일성을 보장하지 못한다는 수령 한계를 유지한다.
3. **관절 명령 연결:** 출력 6축은 정규화된 관절 목표 증가량이다. 관절 순서·20 Hz 주기·관측 정규화·관절 한도·그리퍼 하위 제어를 원본대로 연결한다. 480 Hz/60 Hz 분리 조건에서 원본 복귀 실행기의 시간 진행과 외력 갱신도 재검증·보완한다. 고정 놓기와 운반 ramp를 중복 적용하지 않는다.
4. **현장 목표 관측:** 도착 후 실제 RGB-D 재탐지, map→base→`arm_2/base_link`의 촬영 시각 TF, root/표면/중심/파지점 변환, stale 관측 거부, 색·ID 연계를 검증한다. 예찰 Goal은 모바일 base 이동 목표이며 팔의 목표 pose 그 자체가 아니다.
5. **카메라·모델 정합:** 농장 예찰 모델과 전달 YOLO 모델, D435 2대 장착·해상도·RGB-depth 정렬·카메라 좌표·비전 Python 차이를 확인한다. Teacher truth 입력을 공통 배포 제어에 주입하지 않는다.
6. **완전 수확 판정:** 다른 과실·나무·박스·차체와의 접근/당김/운반/복귀 간섭을 평가한다. 중심 파지·분리 후 보유·박스 위 연속 정지 0.3초·놓기 의도·낙하·안착 유지 0.6초·기존 적재물 유지 판정을 연결한다. 현재 물리 분리 이벤트만으로 수확 성공 처리하지 않는다.
7. **공통 FSM/API 승인:** 현재 도착 전용 계약을 실제 수확으로 바꾸기 전 최소 변경안을 다시 확정한다. 후보 파일은 공통 `harvest_robot/{mission.py,state_controller.py,node.py,communication.py,contract.py}`, 필요할 경우 `farm_interfaces/action/HarvestTask.action`·관련 메시지다. 정확한 수정 파일·내부 어댑터 API·성공/실패/취소·수량 의미·실물 영향·검증 방법을 제시하여 승인받은 뒤 적용한다. 이 문서는 해당 공통 변경을 승인하거나 구현한 기록이 아니다.

## 9. 되돌리기와 전달

실행 중 override는 session layer이므로 종료하면 원본 USD에는 남지 않는다. 다만 다음 실행도 새 설정을 읽으므로 프로파일·장치 주기·좌표·Nav2 허용값을 이전 버전으로 되돌려야 전체 동작이 복원된다. `enabled=false`는 신규 물리 연결만 끄며, 자동으로 이전 크기·목표 좌표·480 Hz 설정을 모두 복원하는 스위치가 아니다.

복원 시 이번 변경 파일만 비교하여 되돌리고 기존 미커밋 문서·수령 원본·사용자 실행 로그를 reset/삭제하지 않는다. 배포 패치를 만들면 `sim/` 내부 변경 파일·자산과 문서만 포함하고 적용 명령을 함께 제공한다. 최종 commit/push·패치 전달 상태는 root의 종료 보고에서 확정한다.

## 10. 인장력 확인 방법과 커밋 전 재검증

2026-10-06 사용자 요청 “테스트하고 커밋푸쉬 … 정상적용 확인 … 어느정도 인장력 … 강화학습 환경을 적용한거야?”에 따른 추가 기록이다.

### 어떤 환경의 물성을 적용했는가

받은 소스의 `attachment_version=4`, `stem_response_version=5`와 **9g 평가 설정**을 적용했다. 정책이 물성을 새로 추정한 것이 아니라 환경의 스프링·감쇠·분리 규칙을 이식한 것이다. 받은 체크포인트의 과거 원 학습 질량은35g이고 전달 평가에서9g로 바꿨다. 따라서9g로 새로 학습했다고 설명하지 않는다. 현재 정책 추론은 실행하지 않는다.

| 항목 | 현재 설정 |
|---|---|
| 인장축 스프링 강성 | 60 N/m |
| 수평 횡축 / 수직 강성 | 15 / 40 N/m |
| 점 감쇠 | 4.2 N·s/m |
| 과실별 힘 한도 | 2~3N, seed713으로 생성; 기본 검사 과실은2.39009994N |
| force 분리 조건 | 상한 적용 전 인장력 > 개별 한도 **그리고** 인장축 꼭지 변위 >12mm |
| 후크 개방 조건 | 인장축 꼭지 변위 ≥25mm |
| 최대 이탈 조건 | 초기 꼭지 앵커로부터 전체 변위 ≥40mm |
| 지속시간 | 위 세 조건 중 하나 이상이 연속40ms; 끊기면 누적0.480Hz에서는20tick=41.667ms |

고정력은 일정한 상수가 아니라 현재 변위·속도·질량·관성과 꼭지 레버를 사용해 매 tick 계산한다. 힘 한도는 계산된 복원력의 크기도 제한한다. 원본 Torch 난수열과 같은 개별 과실 값을 재현한 것은 아니며, 같은2~3N 분포와 농장 내 재현 가능한 seed를 사용한다.

**2N 미만이면 항상 유지된다는 뜻은 아니다.** 힘 조건 외에25/40mm 거리 조건이 있기 때문이다. 또한 implicit 수식이 COM 관성과 회전 반응을 함께 계산하므로 단순 `외력/60`으로 실제 변위를 예측할 수 없다. 실제0.5N 시험에서는 힘 한도2.3901N을 넘지 않고도 인장축 변위32.32mm·연속41.667ms의 후크 조건으로 분리됐다. 그때 계산 인장력은0.51955N이었다. 이를 힘 임계값 초과 성공으로 보고하지 않는다.

외력 API의 합산 여부도 별도 GPU 검사로 확인했다. 무중력·무접촉·질량1kg 물체에서 한 tick의1N,1N+1N 두 호출,2N 한 호출은 각각 속도변화1/480,2/480,2/480m/s로 일치했다. 두 외력이 덮어써진 현상은 아니었다. 0.5N 유지 예상이 틀렸던 중간 검사 결과는 삭제하지 않고 보존했다.

### 직접 실행하기

**원본 USD만 열어서는 줄기 물리가 실행되지 않는다.** 아래 도구 또는 farm_sim_runtime 실행기를 사용해야 session 물성·과실 크기와480Hz 줄기 외력이 함께 적용된다.

```bash
cd ~/main/farm_project
~/isaac/env_isaaclab/bin/python sim/tools/check_harvest_physics.py \
  --gui --expected-fruits 288 --pull \
  --output sim/runs/robotarm/manual_physics_check.json
```

`--gui`는 선택한 과실 쪽으로 카메라를 배치한다. 기본 순서는 **2초 자연 유지 →0.1N으로1초 당기기 →0.5초 힘을 빼고 회복 →3N으로 분리 →0.6초 낙하**다. 검사가 끝나면 창이 닫힌다. 화면 없이 검사할 때는 `--gui`를 생략한다. 다른 과실은 `--fruit-index`로 선택한다.

결과JSON의 `status=PASSED`, `checks.masses_9g`, `no_spontaneous_detach`, `low_force_stays_attached`, `low_force_recovery_stays_attached`, `selected_physically_detached`, `detached_gravity_drop`을 확인한다. `selected_fruit`에서 실제 질량·힘 한도·꼭지·COM·관성·인장축을 확인할 수 있다. `hold_probe`는 부착 중 최대값과 초기0.2초 매 tick 기록, `detach_events`는 실제 분리 이유와 지속시간을 남긴다.

`raw_tension_N`은 힘 한도를 적용하기 전 계산값이고 `tension_N`은 제한 후 값이다. `criteria`의 `force_and_min_pull`, `hook_opening`, `max_extension`으로 분리 시 충족된 조건을 구분한다. 분리 후 적용되지 않는 가상의 스프링 힘은 유지 시험의 최대값 집계에서 제외했다.

현재 검사 기본 하중0.1N은 해당 과실·방향의 유지 확인용이며 전체 과실의 최소 분리 하중을 의미하지 않는다. `--hold-force-n 0.5`로 앞의 후크 개방을 재현하면 “유지되어야 한다”는 검사 기대 때문에 FAILED가 정상적인 관측 결과다. 물성값·힘 한도·후크 거리·지속시간을 시험 통과 목적으로 바꾸지 않았다.

### 이번 재검증 결과

| 검사 | 결과 |
|---|---|
| 단위·자산 / 경로 / 빌드 | 62개 통과(skip0) /371개 경로 통과 /sim3패키지 빌드 통과 |
| 무외력2초 | 과실288개 유지, 자연 분리0 |
| 0.1N·1초 | 선택 과실 유지. 최대 인장축 변위6.754mm, 최대 계산 인장력0.10944N, 전체 분리0 |
| 이후0.5초 무외력 | 전체288개 유지 |
| 3N | 원시 인장력4.31294N, 인장축 변위134.20mm, 연속41.667ms에 분리. 힘·후크·최대변위 조건 모두 충족 |
| 분리 후0.6초 | Z방향0.90448m 하강 및 바닥 접촉. 최종 결합287·분리1 |
| 최종 실행 상태 | GPU 검사15개 check 모두 true, `status=PASSED`, 프로세스 종료코드0 |

기본 대상은 `/World/Vegetation/Bed_01/Fruits/Pepper_0001_yellow`, world −X 방향으로 COM에 외력을 가한 시험이다. 이 한 과실의 하중 시험을288개 전부의 최소 파괴력 측정으로 확대하지 않는다.

버전 관리되는 요약은 [검증 JSON](changes/ROBOTARM_PHYSICS_VALIDATION_20261006.json)에 보관한다. 전체 원본은 `sim/runs/robotarm/precommit_20261006/`의 `summary.json`, `physics_result.json`, `physics_gpu.log`, `hold_0p5N_hook_result.json`, `force_api_probe.json`에 있다. 실행 로그·백업·413MiB 수신 archive는 소스 커밋에 포함하지 않는다. 공통/실물 실행 코드 변경은 없다.


## 11. GUI 자동 종료와 프레임 저하 실측 — 2026-10-06

사용자가 생성한 `sim/runs/robotarm/manual_physics_check.json`과 기준 커밋 `1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd`의 검사기를 확인했다. **자동 종료는 정상 동작이며, 프레임 저하는 현재 CPU 물리 실행 경로가 주 병목이다.** 이번에는 성능 분석과 문서 정정만 수행했다. 운영 코드·물성·정책·공통/실물 코드는 변경하지 않았다.

### 자동 종료와 물리 검사 결과

`check_harvest_physics.py --gui --pull`은 지속 관찰용 실행기가 아니다. 정지2초 →0.1N 유지1초 →복원0.5초 →3N 당김(분리되면 종료) →낙하0.6초를 진행한 뒤 JSON을 저장하고 `app.close()`로 창을 닫는다. 마지막 `os._exit()`는 정상 cleanup 뒤 잔여 Kit thread 때문에 프로세스가 남는 것을 방지한다. `--gui`는 화면 표시 옵션이며 계속 켜두는 옵션이 아니다. `--seconds`는 최초 정지 검사 시간만 늘린다. 계속 실행하는 일반 fleet은 `--duration-s`를 생략한다.

사용자 JSON은 `status=PASSED`,15개 check 모두 true,288개9g 과실을 확인했다.0.1N 유지/복원 동안 모두 부착,3N 당김으로 선택 과실 분리 후 약0.90448m 낙하, 최종287개 부착/1개 분리다. 총1994tick=4.154167시뮬초였다. 시작/종료 UTC 차이74.023초에는 앱 초기화·장면 로딩·종료가 포함되므로 순수 FPS나 물리 처리시간으로 환산하지 않는다.

### 비교 조건과 결과

- 이번 PC: i7-13700K, RTX4070SUPER, Isaac5.1,1280×720 GUI. 같은 농장·과실 자산·로봇·근접 시점에서 정지 구간을 비교했다. 정책/ROS/카메라 센서 송신/당김 외력은 실행하지 않았다.
- 각 경우는 독립 프로세스에서30렌더 프레임 준비 후120프레임을 측정했다. 로딩·종료·실시간 sleep은 제외했다. 측정 FPS는 렌더 호출 수/벽시계 시간이며 UI의 특정 순간 FPS와 동일한 측정값은 아니다.
- `full`은288개 줄기+PhysX와 원본 정지 검사의 상태/변위 조회를 유지한다. `no_diagnostics`는 추가 조회만 생략한다. `static`은 과실을 kinematic으로 고정하고 줄기 힘을 생략하되 과실 모양·충돌과 로봇을 유지한 **원인 분리용 대조군**이다. 실제 수확 물리와 동등하지 않다.

| 비교 | 전역 물리 주기 | 측정 평균 FPS | CPU 물리 호출 시간/프레임 |
|---|---:|---:|---:|
| 현재288개 동적 과실+줄기+진단 |480Hz|8.30|100.63ms|
| 같은 물리, 추가 상태 진단만 생략 |480Hz|8.27|102.67ms|
|288개 과실 고정, 줄기 생략 |480Hz|22.22|36.25ms|
|같은 고정 대조군의 물리 주기만60Hz |60Hz|89.52|4.27ms|

첫 세 경우는 mesh/fruit 경로 해시·카메라 위치·해상도가 일치한다.60Hz 대조군은 초기 reset의 시간 간격 차이로 고정 전 과실 높이와 이를 바라보는 카메라 Z가 약8.05mm 낮다. 따라서 마지막 행은 이전 운영 버전의 실제 FPS나 완전히 같은 초기 상태의 비교로 해석하지 않는다.120프레임의 짧은 정지 구간 시험이며 반복 분산·전체 fleet·실제 수확 성능은 미측정이다.

현재 조건의 프레임당 평균120.44ms 중 물리 실행100.63ms(83.5%), 줄기 갱신7.06ms(5.9%), 화면/앱 갱신9.90ms(8.2%), 추가 상태 검사2.38ms(2.0%)였다. SDK의 `world.step(render=False)`는 `simulate`와 `fetch_results`를 함께 포함하므로100.63ms를 순수 충돌 solver 시간으로 단정하지 않는다. NumPy 수식만 별도 측정하면288개 전체0.495ms/tick(8tick당3.96ms)이었고, 엔진 상태 조회/외력 전달 비용은 그 수치에서 제외된다.

실제 실행값은 `world_device=cpu`, `backend=numpy`, `enableGPUDynamics=false`, `broadphase=MBP`, `solver=TGS`, `suppressReadback=false`, Fabric 확장 비활성이다. 현재 조건의 측정 구간에서 GPU 사용률은 평균11.9%(29개 샘플)였다. 이 문서의 과거 “GPU 검사”는 RTX를 사용하는 Isaac 실행을 뜻했으며 GPU PhysX 사용을 입증한 기록이 아니었다. 전체CPU시간54.61초/벽14.46초는 여러 스레드 합산 값이다.

**동적 과실288개와 전역 물리60→480Hz 증가가 함께 비용을 늘렸다.** 과실만8배 자주 계산하는 것이 아니라 로봇·농장 접촉을 포함한 전체 PhysicsScene을 렌더1회당8tick 진행한다. 추가 검사 생략만으로 FPS가 개선되지 않았고 과실 고정에서는 크게 개선되었다. CPU 물리 경로가 주 병목이라는 결론은 GPU 사용률 하나가 아니라 구간 계측·대조군·실제 엔진 설정을 함께 근거로 한다. 설정의 렌더60Hz는 시뮬 시간 기준이며 현실에서60FPS를 보장하지 않는다. 물리dt는1/480초로 유지되고 벽시계 대비 시뮬 진행이 느려진다.

### 후속 개선과 실행 설정 정정

1. 우선480Hz와 현재 물성을 유지하면서 PhysX 계산/결과 동기화 구간을 더 나누어 계측하고 CPU worker 수·상태 전달 경로를 비교한다. 이번에는 최적화를 적용하지 않았다.
2. USD 상태 쓰기와 Fabric 경로를 검토할 수 있지만, Fabric 활성화는 USD pose 갱신을 끄므로 현재 USD 기반 SceneTruth/평가가 오래된 위치를 읽지 않도록 함께 검증해야 한다. 단순 스위치 변경으로 처리하지 않는다.
3. 멀리 있는 과실을 고정하고 작업 영역만 동적으로 만드는 방식은 이번 대조군에서 가능성을 보였지만, 비목표 과실의 움직임·접촉·분리를 생략하는 물리 단순화다.60Hz로 낮추기, solver/충돌 축소, GPU dynamics 전환도 기존 물리 조건과 분리 시험을 다시 검증할 별도 변경이다.
4. runtime에서 **scene CCD=true**를 확인해 §2의 기존 false 설명을 정정했다. Isaac Core World의 CPU 기본값에서 발생하며 전달 Teacher의 scene CCD=false와 차이가 있다. 성능 원인에서 CCD만의 기여도는 분리 측정하지 않았다. 이번 분석에서 실제 CCD 설정은 바꾸지 않았다.

원본 결과: [수동 물리 검사](../runs/robotarm/manual_physics_check.json), [성능 집계](../runs/robotarm/perf_20261006/summary.json), [현재 조건 세부](../runs/robotarm/perf_20261006/full.json). 재현용 임시 프로파일러·GPU 샘플·각 실행 로그는 `sim/runs/robotarm/perf_20261006/`, 순수 수식 벤치는 `sim/runs/robotarm/cpu_microbenchmark_20261006/`에 있다. 초기 계측기 실행은 설치 SDK의 `use_fabric` getter 오류로 측정 전에 실패했고 `initial_instrumentation_failure_*`로 보존했다. 임시 계측만 수정한 뒤4개 경우 모두 정상 종료코드0을 확인했다. runs 산출물은 Git에서 제외되며 이번 분석 문서 갱신은 미커밋·원격 미반영이다.
