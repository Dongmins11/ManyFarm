# 최신 운송 통합 브랜치 검토 및 시뮬레이션 시험 설계

작성일: 2026-10-27 KST. **검토·설계 완료, 구현·병합·Isaac 시험은 미실행.**

## 사용자 확정 범위 조정 — 바구니 정렬 기반 인계 시험

후속 사용자 지시로 과실 실제 배출·낙하 물리·하역 기구 구현은 이번 시험에서 제외한다. **도킹 후 수확 바구니 배출부와 운송 바구니 수용부가 정렬되고, 두 로봇이 정지한 상태로 정렬을 유지하면 시뮬 인계 성공으로 판정한다.** 아래 최초 설계 중 실제 배출/기구 구동/수령량 D~F 검증을 요구하는 부분은 이 조정으로 대체한다.

- 정렬 오차는 두 바구니의 실제 모델 기준점·개구부 형상으로 평가한다. 위치·방향·높이/배출 관계와 연속 유지 시간을 기록한다. 허용 오차와 유지 시간 수치는 형상 확인 후 정하며 현재 임의 확정하지 않는다.
- 마커 기반 도킹·실제 주행·정지·이격·수확로봇 복귀와 관제 이벤트 순서는 계속 검증한다. 기구 완료를 대체하는 sim 어댑터는 정렬 유지 조건에 근거하며 단순 고정 지연 성공으로 만들지 않는다.
- 장면의 실제 바구니 상대 위치는 시험 판정에만 사용하고 도킹 제어에 주입하지 않는다. 실물 판정/기구 코드는 변경하지 않는다.
- A/B/C 수확 지표는 유지. 운송 실제 수령량·낙하손실 D~F는 미측정으로 표시하며, 정렬 성공을 실과실 전달 수량으로 환산하지 않는다.
- 시험 순서: 운송 단독 주행/마커 도킹/마커 없는 복귀 → 두 바구니 정렬 유지 → SEC01 전체 흐름 → 교통 연동/16구간 확대.
- 운송 모델 확인: `sim/assets/robots/transport_robot/urdf/transport_robot.urdf`, `transport_robot.portable.urdf`, 변환된 `transport_robot.portable/transport_robot.portable.usd` 존재. `cargo_box`와 바퀴·틸트·덮개 관절 포함. 업무 runtime 연결은 아직 구현 전이다.

## 1. 결론과 비교 기준

예찰 → 수확 → 운송 인계 → 선별장 이동은 현재 시뮬 구조를 확장하여 재현할 수 있다. 그러나 최신 브랜치를 가져와 설정만 바꾸면 실행되는 상태는 아니다. 운송 실행의 real 전용 제한, 가상 운송 장치·마커, 수확 배출 장치, 인계 제어권, 관제 이벤트 연결을 먼저 구현해야 한다. 실제 열매가 운송함으로 넘어가는 물리 시험까지 성공했다고 볼 근거는 아직 없다.

- 로컬/원격 main: `b5ef6f2fd428b6d4d3d5b7973053ae0026f16ea8`.
- 최신 통합본: `origin/feature_dongmin`, `9686aca909cb52191862ee3500c62fadf7a8ed38` (10/27 17:12:13 KST).
- 통합 커밋 `6fe027d`: 최신 실물 수확 `48d2d1c`를 부모로 운송 업무 통합. 후속 `9686aca`: OpenCR 덮개 구동 시간 갱신.
- 공통 조상: `2a397da842300823cec077210ac7857024a6f66a`.
- 이번 작업 시작 시 fetch 완료. 기존 미커밋 공통 코드 검토 문서와 원본 전달 폴더 보존.

전체 Git 파일 목록을 3방향 비교했다. 서로 다른 최종 파일 2,067개 중 원격만 변경 514개, 로컬만 변경 1,527개, 양쪽 변경 후 내용 상이 26개다. 이는 기능 수나 병합 충돌 수가 아니다. 로컬 시뮬 자산·모델도 포함된 수치다. 최신 수확 `48d2d1c` 이후 운송 통합 변경은 327개 경로다. 전체 경로와 blob SHA는 [비교 JSON](TRANSPORT_SIM_SCOPE_REVIEW_20261027.json)에 보존했다.

실행 흐름에 해당하는 공통 주행·수확 인계·운송 FSM·정밀 도킹·기구·인터페이스·launch/config를 중점 검토했다. 하드웨어 vendor 전체의 모든 줄을 검증한 것은 아니다. 이전 수확/공통 주행의 상세 차이는 [공통 코드 사전 검토](COMMON_CODE_MERGE_REVIEW_20261027.md)를 함께 참조한다.

## 2. 현재 브랜치 대비 기능 목록

| 영역 | 현재 main | 최신 통합본 / 반영 판단 |
|---|---|---|
| 예찰·윈도우 | 정렬, 깊이 ±2cm, 위치 보정 등 로컬 개선 있음 | 이번 운송 커밋에서 새 예찰 기능 없음. 로컬 개선 보존 |
| 일반 수확 | 실제 팔·바구니 카운트 및 누락 성능 기록. sim 인계 비활성 | 최신 실물 수확 인계 구성 포함. 일반 수확을 원격 파일로 일괄 교체하지 않음 |
| 수확 인계 자세 | DockTransfer/Discharge 계약과 기존 회전 경계 있음 | 후진 곡선·벽 정렬·배출 자세·원래 윈도우 복귀, 일시 센서 단절 정지/재관측, 정지 후 복귀 5cm/6도, 이동 중 방향 최대 3도 |
| 운송 업무 | transport_robot는 README 수준, sim 모델·그래프는 존재 | TransportPickup, BucketUnload, ReturnToStation, internal/check_route의 실제 서버/FSM 추가 |
| 수확로봇 접근 | 운송 실행 없음 | 주행 중 마커42 관측 → Nav2 종료·실측 정지 → 42 상대 자세 접근 → DOCK_READY 대기 → 41/라이다 최종 접근 |
| 인계 수령 | 미연결 | 도킹 후 덮개 열기 → TRANSFER_COMPLETE 대기 → 덮개 닫기 → 0.252m 상대 후진 이격 → TRANSPORT_CLEAR |
| 선별장 | 모델·목적지 후보만 있음 | 관측 구간 주행 → 마커40/라이다 도킹 → UNLOAD_READY 대기 → 기구 완료 → 이격·정렬 |
| 스테이션 복귀 | 예찰/수확은 지정 경로 복귀, 별도 도킹 마커 없음 | 운송은 마커32 도킹·주차 방향 회전 필수. sim에서는 이 마커 단계를 생략하도록 별도 정책 필요 |
| 도킹 실패 복구 | 미연결 | 초기 목표 미확보 시 정지 재관측3초, 0.02m/s·5cm 후진, 좌우15도 탐색, 전체30초 제한. 성공 보장은 아님 |
| 제어권 | 현재 교통 클라이언트/주행 정지 경계 있음 | 운송 MotionLease와 motion_gate 추가. Nav2와 정밀주행 중 한 소유자만 최종 cmd_vel 출력 |
| 취소/재시작 | 기존 Action/교통 계약 | 늦은 정밀 Goal 수락도 추적·취소, terminal+stopped 전 다음 동작 금지. 접촉 중 재시작은 복구 필요, 동일 task_id 재실행 금지 |
| 기구 장치 | 수확 팔 가상 장치 존재, 운송 기구 서비스 없음 | OpenCR UART Trigger 서비스: 덮개, 앞문, 틸트, 정지. DONE 응답 대기 |
| 펌웨어 | 운송 펌웨어 없음 | 덮개 stime 1500→1350ms, 전체 개폐 약4.4→4.0초. 브리지 덮개 제한10초 유지. sim 바퀴 설정 변경 아님 |
| 배포 도구 | 현재 sim 도구 | hardware_ws, 실물 빌드/실행 도구 및 옛 명령 보관 추가. sim 실행에 실물 환경 스크립트를 사용하지 않음 |

메시지 추가는 `TransportPickup`, `BucketUnload`, `CheckRoute`, `MechanicalOperation`, `PrecisionMotion`, `TransportDeviceState`, `MotionLease`, `UnloadEvent`다. `NavigateToNode`는 양쪽 동일하며 로컬에서 이미 추가했다. `DockTransfer`, `TransferEvent`도 현재 main과 동일하다. RobotStatus 필드는 같고 boot_id 주석만 다르다. 새 메시지 추가만으로 서버·교통 기능이 연결되는 것은 아니다.

## 3. 실행을 막는 차이와 회귀 위험

### P1 — 먼저 해결해야 하는 실행 장애

1. **운송과 최신 수확 인계의 real 전용 제한.**
   - `transport_robot/configuration.py:load_profile()`은 mode=sim 즉시 거절. `farm_bringup/launch/transport.launch.py`도 choices=['real'].
   - `harvest_robot/handoff_runtime.py`는 mode!=real을 거절. 수확 launch의 전용 인계 컨트롤러 시간 설정도 실물 기준이다.
   - 실제 원격 load_profile 함수를 호출해 sim 거절 확인. 제한문만 삭제하면 센서·시간·출력 계약이 해결되는 것이 아니다.

2. **시뮬 장치는 모델까지만 있고 업무 연결이 빠져 있다.**
   - `sim/.../config/harvest_fleet.json`에는 scout/harvest 둘뿐이며 all.launch.py에도 운송 인자가 없다.
   - 운송 URDF/USD와 바퀴·상부 덮개·옆문·틸트 관절은 존재한다. 운송 카메라/ROS 어댑터/기구 서비스/운송 Nav2 환경은 추가해야 한다.
   - 수확 바구니 바닥 개폐 관절도 존재하지만 이번 검색 범위의 sim runtime/devices에는 Discharge 서버가 없다. `harvest_task.json`의 transfer.enabled=false.
   - 물리 모델 파일 존재를 관절 구동·과실 이동 검증 완료로 해석하지 않는다.

3. **교통 허가와 단일 속도 출력의 충돌.**
   - 최신 운송 TransportNode/TransportNavigator는 현재 로컬 TrafficClient를 조립하지 않는다. 주행 중 교통 허가·점유 보고 연결도 아직 없다.
   - 원격에는 로컬 AcquirePassage 등 교통 8타입이 없다. 삭제 변경이 아니라 분기 후 로컬에만 추가된 기능이다. 전체 덮어쓰기 금지.
   - 운송 motion_gate는 cmd_vel publisher가 둘 이상이면 lease 거부/정지. 수확 HandoffRuntime도 cmd_vel_nav 단일 publisher를 검사한다. 로컬 교통 정지 publisher를 그대로 추가하면 구성 충돌한다.
   - 최종 출력 소유자는 로봇별 하나로 두고, 교통 정지/재시도 정지는 해당 소유자의 정지 경계로 전달한다. 도킹·이격 궤적의 공간 예약은 일반 그래프 허가와 별도 검증해야 한다.

4. **운송 스테이션 마커 생략은 현재 설정만으로 지원되지 않는다.**
   - transport_communication의 return 접수, Controller.start, arrived 모두 정밀 도킹을 전제한다. precision_enabled=false만 지정하면 복귀도 거절된다.
   - 사용자 요구대로 **sim의 return만 경로 주행→도착 오차/정지 확인→완료**로 선택할 최소 정책을 추가한다. pickup/unload 마커는 유지. 실물 기본 경로는 그대로 둔다.
   - 예찰/수확의 기존 sim StationReturn은 유지. 현재 sim 성공의 docked=true는 마커 검출이 아니라 가상 주차 완료 의미다. 운송도 이 기존 의미를 따르되 로그에 marker_stage=SKIPPED_SIM_POLICY를 남겨 물리 마커 도킹 성공과 구분한다.
   - 접촉/미확인 이격 상태에서는 마커 생략으로 복구 금지를 우회하지 않는다.

5. **관제가 두 로봇의 이벤트를 중계해야 한다.**
   - 로봇은 feedback을 내고 TransferEvent를 받는다. 로봇끼리 자동 중계하지 않는다.
   - 송신 task_id를 그대로 전달하면 안 된다. 수신 로봇의 task_id, 동일 transfer_id, 실제 상대 source_robot_id로 매핑해야 한다.
   - 이 저장소 control 경로에는 전체 관제 오케스트레이터가 없고, 전달된 traffic 시험 묶음만으로는 인계/하역 중계 검증이 안 된다. 별도 관제 실행본과 계약 시험 필요.

### P2 — 시험 전 동등성 확인 항목

- **시간 기준:** TransferSession/UnloadSession 제한과 정밀주행 여러 단계는 time.monotonic(실시간)을 사용한다. 메시지 stamp/TF는 ROS 시간이다. 4배 느린 sim에서 실시간60초는 sim15초에 해당하므로 false timeout 가능성이 있다. 정밀 서버뿐 아니라 motion_gate·Nav2·수확 인계 전부 use_sim_time을 일관되게 설정해야 한다. 센서 헤더 나이는 ROS 시간, 통신 단절/정지 watchdog은 실시간으로 구분하고, 물리 동작 제한의 기준은 비교표를 만들어 선택한다. 처음부터 모든 제한을 일괄 늘리지 않는다.
- **티칭/프레임/거리:** 실물 카메라 외부 보정과 마커 상대 티칭을 sim에 그대로 복사하지 않는다. 로봇 프레임·마커 장착·라이다 대상 면이 같을 때만 재사용 가능하다. 수확 최종 거리0.20m, 선별장0.17m는 라이다 대상 면 기준으로 검증하며 로봇 중심 간 거리와 혼동하지 않는다.
- **맵 종속 방향:** 실물 노드3/15/17/20, 차단5↔12, 선별장 이탈 map yaw=0은 sim에 자동 적용하지 않는다. 기존 sim 그래프와 실제 모델 배치를 기준으로 목적지/진입·이격 방향을 만든다.
- **수량:** 최신 Trigger 백엔드는 수령량을 측정하지 않는다. TransportPickup 성공 후에도 loaded_count=None, RobotStatus=-1이다. TRANSFER_COMPLETE 또는 기구 DONE만으로 C개가 모두 운송함에 담겼다고 계산하면 안 된다.
- **보존:** 로컬 경로 길이별 timeout, D059 짧은 전방 이동 판정, Nav2 시간 패치, 교통 계약, 위치 보정·예찰·과실 배치·카메라 활동 정책을 유지한다. 예: 원격 harvest_task의 팔 제한660초를 로컬7260초에 덮어쓰지 않는다.
- **문서 불일치:** 원격 transport README의 '도킹 미연결' 및 루트 README 초기의 '배포하지 않음'은 후속 코드/후속 기록보다 오래됐다. 현재 코드에서는 PrecisionClient와 도킹 서버 연결이 존재한다. 실물 브링업·전체 E2E 성공은 이 업로드의 배포/단위시험 기록만으로 입증되지 않는다.

## 4. 권장 시험 환경

공통 FSM·주행·도킹 알고리즘은 최신 코드를 선별 병합하고, 가상 장치/센서/모델/환경 설정만 sim에 둔다. 업무 로직을 sim에 복사하는 방식은 선택하지 않는다. 최신 브랜치 전체 교체는 로컬 개선을 잃으며, 장치를 모두 더미 성공으로 처리하면 실제 실패 원인을 확인할 수 없다.

### 구성

- Isaac 한 프로세스: scout_01, harvest_01, transport_01 및 기존 선별장 모델. CPU physics, headless, Domain13/SUBNET 유지. 단일 /clock.
- 기존 farm_map_v1와 sim 역할별 그래프 사용. 운송 그래프는 현재143노드/324엣지다. 8003(2.0,13.25)↔8004(5.0,13.25)는 양방향6.5m 경로 계산 확인. 이는 실제 충돌 없는 주행 보증이 아니다.
- transport_01 및 sorting_station의 station yaw가 현재 null/DESIGN_PROPOSAL이므로 모델 기준 장착/접근 방향을 확정해야 한다. run_fleet가 yaw를 float로 읽으므로 설정 없이 추가하면 시작부터 실패한다.
- 기존 BaseSim/ROS 어댑터의 바퀴 odom·Lidar·TF 경계를 재사용. 위치 추정은 odom/AMCL 및 관측 센서로 수행. GT 위치/과실ID는 평가 로그에만 사용.
- transport 카메라를 실제 모델 장착 위치에 추가하고 ROS Image/CameraInfo로 연결. PrecisionServer는 이미 ros/picamera2 입력 선택을 지원한다. sim은 ros 선택, 실물 PiCamera 경로/Serial/OpenCR 프로세스 실행 안 함.
- ArUco DICT_4X4_50, 물리 마커 변 길이0.05m: 수확로봇의 접근용42/최종41, 선별장40. 모델 표면·높이·방향·TF와 카메라 시야를 함께 검증. 스테이션32는 배치/검출을 필수로 하지 않음. 기존 위치 보정용 AprilTag와 구분.
- 카메라는 접근 중 관측부터 정밀 도킹까지 켠다. 정밀 서버의 cam_off는 ROS 구독만 해제하므로 Isaac 렌더링도 멈추도록 가상 카메라 활동을 연결한다. 기존 팔 카메라는 수확 때만 켜는 정책 유지.
- 수확 Discharge와 운송 lid_open/lid_close/unload/stop 가상 어댑터는 해당 USD 관절을 움직이고 실제 관절 상태/정지·과실 관측으로 결과를 반환한다. 이동 물체 순간이동·카운트 복사·고정 지연 뒤 성공 응답은 물리 합격 증거로 사용하지 않는다.
- 로그/티칭/저널은 sim/runs 아래로 분리. real 운영 티칭·저널 경로를 사용하지 않는다. 재시작 때 접촉 중단 상태와 task_id 이력도 보존한다.

### 관제 순서

1. 예찰 결과의 정렬된 window 목록으로 수확 수행. A/B/C 카운트·누락 분류 유지.
2. 수확 작업 완료 후 관제는 수확 DockTransfer와 운송 TransportPickup을 동일 transfer_id로 묶는다. 두 task_id는 별개로 기록한다. staging_pose는 운송 그래프 위의 접근 가능 지점으로 계산한다.
3. 운송이 42 접근을 마치고 WAITING_FOR_TRANSFER를 내면 수확 측 DOCK_READY를 운송 TransferEvent로 전달한다. 수확 준비가 먼저 끝났으면 보관했다가 수신 단계가 준비된 뒤 전달한다.
4. 운송 최종41 도킹·덮개 열기 후 DOCK_STABLE → 수확에 전달. 수확 배출 완료 TRANSFER_COMPLETE → 운송에 전달.
5. 운송 덮개 닫기·이격 완료 TRANSPORT_CLEAR → 수확에 전달. 수확 원래 작업 자세 복귀까지 확인한다. DockTransfer의 transfer_complete/transport_clear/restore_complete 모두 true 확인.
6. 운송을 선별장 접근 지점까지 이동시키고 도착/정지 확인. **사용자가 지정한 기본 범위의 끝은 여기**다.

선별장 정밀 도킹·하역·이격은 추가 시험으로 분리한다. 기존 BucketUnload는 이동만 하는 Action이 아니라 도킹→UNLOAD_READY→하역→이격까지 포함한다. 이를 발행하고 접근점 도착만으로 SUCCESS라고 기록하지 않는다. 이동만 검증하는 초기 단계에는 기존 internal/check_route를 사용하고, 최종 관제 흐름에서 BucketUnload를 사용하는 경우 단계별 도착과 전체 Action 결과를 따로 남긴다. 신규 외부 Action을 임의로 추가하지 않는다.

### 교통 시험 분리

먼저 격리된 시험에서 로봇별/두 로봇 인계 기능을 검증하고 다른 로봇은 정지시킨다. 이는 교통 E2E 합격으로 표시하지 않는다. 최종 공동 시험에는 운송의 등록/Status/Progress/허가와 도킹 공간의 예약·이격 후 해제가 필요하다. 기존 scout/harvest 교통 시험 프로필을 훼손하지 않고 별도 통합 프로필로 검증한다. 교통 활성 시 허가 실패를 무허가 주행으로 대체하지 않는다.

## 5. 구현 대상과 검증 순서

| 순서 | 최소 작업 범위 | 통과 조건 |
|---|---|---|
| 1 | farm_interfaces 추가 정의, 공통 주행/수확 인계 선별 병합 | 기존117회귀 및 새 인터페이스 빌드, 로컬 교통/거리timeout/전방판정 보존 |
| 2 | transport configuration/launch와 harvest handoff의 환경 조립 경계 | real 기본 동작 유지, sim 센서·시간·로그 경로 선택, 단일 속도 출력 보장 |
| 3 | sim 운송 장치 config·fleet·카메라·마커·기구 어댑터 | 정지/이동/취소, 관절 도달, 실제 이미지에서42/41/40검출, 잘못된ID 거부 |
| 4 | transport return의 마커 없는 sim 정책 | 경로 주행/정지 검증 후 완료, 마커 관측0이어도 복귀 가능, pickup 마커 필요 조건은 유지 |
| 5 | 수확 배출·인계와 관제 이벤트 연결 | 양쪽 상태/ID 일치, 배출 전 DOCK_STABLE 필수, 이격 전 복귀 금지, 물리 이동량 측정 |
| 6 | 운송 선별장 주행 및 선택적 하역 | 접근점 실제 도착/정지, 하역 시험은 준비 이벤트 전 기구 작동 없음 |
| 7 | 교통 통합과 SEC01 반복→SEC01~16 확대 | 예약 충돌/차량 접촉/미확인 취소 없음, 단계·수량·실시간/sim시간 로그 완비 |

공통 변경의 정확한 제안 경계는 transport_robot/configuration.py, transport_communication.py, transport_state_controller.py, farm_bringup의 transport/harvest launch, harvest_robot/handoff_runtime.py 및 기존 주행·교통 정지 연결부다. 센서/기구/마커 구현은 farm_sim_devices/runtime/config/assets 안에 둔다. 실물 PID·footprint·RPP·마커 티칭을 단순히 sim 성공을 위해 완화하지 않는다.

시험은 다음 순서로 진행하도록 제안한다.

- 정적/빌드: IDL 호환, config 참조, 지도/프레임, 모든 최종 출력 publisher, clock, 관절명·단위 검증.
- 무과실 Isaac: 운송 8003→접근점→선별장→복귀, 마커42→41 전환, 마커32 없는 복귀. 정지·취소·카메라 끄기 확인.
- 소수 과실: 실제 수확 과실을 배출/수령. 누락·바닥 낙하·잔류·운송 중 유실 기록. 관절 완료와 수량 판정 분리.
- SEC01 예찰부터 전체 순서 반복 3회. 오류가 나면 원인 수정 및 해당 회귀 후 재개. 성공/실패 모두 동일 로그 수집.
- 이후16구간 확대. 동일 현상3회는 원본 로그 보존 후 해당구간 생략 정책을 적용하되, 접촉 중 오류는 월드 재초기화/정지 확인 없이 저널만 지워 재개하지 않는다.
- 오류 주입: 마커 가림/오ID, TF·scan·영상 단절, 늦은 Goal수락/취소, 순서가 이른 이벤트/중복/다른transfer_id, 기구 미도달, controller단절, CPU부하 및 시뮬 일시정지. 성공 응답의 실제 정지 여부까지 확인.

기능 시험의 합격과 물리 수확률을 분리한다. 열매 누락·낙하는 성능 지표이며 자동 Action 실패 사유로 추가하지 않는다. 주행 실패, 장치 동작 미완료, 제어/통신 오류, 안전한 종료 확인 실패는 액션 오류로 기록한다. 수량 불일치만으로 전체 구간을 중단하지 않는 기존 사용자 정책을 유지한다.

## 6. 기록할 데이터

- manifest: 두 commit SHA/빌드버전, map/graph/model/config SHA, Domain/범위, CPU physics, 센서 주기·해상도·프레임/티칭, timeout별 시계 기준.
- events.jsonl: KST/UTC·ROS ns·monotonic, robot/task/transfer/window, Goal UUID, accept/feedback/result/cancel, 원래 오류 문자열, 마지막 성공 단계.
- motion: Nav2 error105/106, 경로·잔여거리·제한, TF시각·도착 거리/각도·정지속도, cmd_vel source/lease/permit, 장애물/센서 나이, 재시작 이유.
- docking: marker ID/검출시간/상대좌표/목표 확보 사유, 이미지·CameraInfo·TF, 라이다 대상 면과 최소거리, 탐색·복구/이격 이벤트. 실패 전후 영상/scan 확보.
- mechanism: 명령·응답·관절 위치/속도/목표 도달, 뚜껑·배출구 상태, 미정지/타임아웃.
- A 실제 수확 대상, B 예찰 expected, C 수확 바구니 통과는 기존 정의 유지. 추가 D 운송함 실제 수령, E 선별장 접근 시 잔존 적재량, 선택 시험 F 선별장 하역 수. C-D 인계손실, D-E 운송손실을 별도 산출.
- 로봇 보고 loaded_count=-1은 그대로 보존. 평가기 GT-ID 대응 카운트와 익명 센서 카운트를 분리하고 중복·불확실성도 표시. D/C 및 E/D는 동일 과실집합에 대응될 때만 계산, 분모0은 N/A.
- 단계별 wall/sim 소요시간, RTF, CPU/GPU/메모리·카메라 처리/발행간격. 실패가 sim부하인지 공통 논리인지 비교할 근거 확보.

## 7. 이번 직접 확인 결과와 한계

- fetch 및 전체3방향 Git inventory 완료. 변경 파일/기준SHA는 동반 JSON.
- 원격 실제 load_profile(sim) 거절 재현. ROS 카메라 backend 선택 함수는 ros 설정 반환 확인.
- 로컬 실제 RouteGraph로 운송 station↔sorter 양방향6.5m 계획 성공. 각 SEC 인계 staging 경로와 충돌/도킹 공간은 아직 미검증.
- 원격 tests/protocol/test_protocol_flow.py **12개 PASS**: 이동/도킹/하역 순서, 준비 이벤트, 조기/중복/잘못된 이벤트, 취소, 이격 실패, 재시작 복구 등. **대역 센서·기구·주행을 사용한 FSM 단위시험**이며 최신 실물 프로필 전체 물리 검증이 아니다.
- 로그: `sim/runs/transport_scope_review_20261027/protocol_tests.log`, `inventory_summary.json`, `review.py`. 원격 소스 확인본은 `/tmp/transport_review_20261027`에 추출했으며 실행 소스를 덮어쓰지 않았다.
- 이번에는 Isaac/ROS 노드/기구/실물 주행을 시작하지 않았고, 새 코드 빌드·98개 전체 원격 회귀도 실행하지 않았다. 원격 문서의 PC98개/로봇94개 결과는 담당자의 기존 기록이다.

변경은 이 보고서/JSON과 PROJECT_STATE·sim CHANGELOG 기록뿐이다. 공통 코드·실물 설정·sim 실행 동작은 변경하지 않았다. 커밋·푸시 미실행. 다음 작업은 위 순서1~4의 최소 통합으로 운송 단독 주행·마커 도킹·마커 없는 복귀부터 검증하는 것이다.
