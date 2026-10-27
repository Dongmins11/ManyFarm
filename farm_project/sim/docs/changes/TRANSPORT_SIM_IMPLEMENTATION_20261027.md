# 예찰~선별장 시뮬 구현 현황

기준 main b5ef6f2, 운송 원본 feature_dongmin 9686aca. 2026-10-27 KST.
사용자 “구현해야되는 파트 확인하고 하나씩 작업시작해”에 따라 선행 검토의 구현을 시작했다.
기구·과실 낙하 재현 제외, 바구니 정렬 유지 판정은 D-063을 따른다.

## 작업 순서와 현재 상태

| 단계 | 필요한 작업 | 현재 상태 |
|---|---|---|
| 1 예찰 | 기존 예찰/정렬된 window 및 A/B 유지 | 기존 구현 보존. 이번 회귀로 전체 예찰 E2E를 재검증한 것은 아님 |
| 2 수확 | 기존 팔 실행/C 집계, 완료 후 인계 가능 상태 전달 | 기존 수확 보존. 최신 수확 인계 자세/복귀 모듈 선별 병합은 남음 |
| 3 운송요청 | TransportPickup 계약/운송 FSM, task·transfer ID 연계 | 계약·운송 FSM 통합 완료. 관제 요청/이벤트 중계의 sim 연결은 남음 |
| 4 도킹 | 운송 차체/센서/AMCL, 마커42/41, 정밀 접근·실측 정지 | 공통 farm_docking 통합·빌드 완료. 가상 센서/마커/launch 및 실제 도킹 미연결 |
| 5 인계 | 바구니 상대 정렬·연속 정지 유지 판정, 이벤트, 이격·수확 복귀 | 모델 확인 시작. 정렬 판정/가상 어댑터 미구현. 실제 과실 전달량을 만들지 않음 |
| 6 선별장 이동 | sim 그래프의 접근점 이동·정지 및 관제 완료 보고 | CheckRoute 계약/운송 주행 어댑터 통합. sim 운송 프로필·실주행 미검증 |
| 공통 복귀 | sim 스테이션 마커 단계 생략 | navigation_only 선택/접수/FSM/결과 구현·단위/DDS 검증 완료. Isaac 복귀 미검증 |
| 교통 | 운송 등록/허가/점유 및 도킹 영역 예약·정지 출력 | 미연결. 활성화 요청 시 시작을 거절하여 무허가 fallback 방지 |

## 이번 구현 묶음

- 신규 공통 `transport_robot`, `farm_docking` 코드를 9686aca에서 가져왔다. real 장치 드라이버/firmware/real 설정/옛 실행 스크립트는 가져오지 않았다. 업무 FSM을 sim에 복사하지 않았다.
- farm_interfaces에 TransportPickup/BucketUnload/CheckRoute/PrecisionMotion/MechanicalOperation, TransportDeviceState, MotionLease/UnloadEvent를 추가했다. 기존 교통8타입·NavigateToNode·DockTransfer 등은 유지했다.
- transport load_profile은 sim 환경을 허용하되 설정 위치·지도/장치ID·use_sim_time을 검사한다. real은 기존 hardware_configured 확인을 유지한다.
- `station_return_mode: navigation_only`는 sim에서만 허용한다. return Goal은 도킹 연결을 요구하지 않으며 Navigator의 도착/정지 성공 뒤 `STATION_PARKED`, `marker_stage=SKIPPED_SIM_POLICY`를 기록한다. 기본값 marker_docking과 pickup/unload의 마커 조건은 유지한다.
- 정렬/주행 오류 또는 취소를 성공으로 바꾸지 않는다. ReturnToStation의 docked=true는 기존 sim StationReturn과 같은 가상 주차 완료 의미다. 접촉 중 중단/재시작 복구 차단도 그대로 유지한다.
- 아직 연결하지 않은 traffic.enabled는 거절한다. precision_enabled와 별도 Nav2 정지 publisher를 생성하는 TF/106복구 설정의 동시 사용도 거절한다. 단일 출력 소유권 연결을 완료한 후 이 경계를 개선해야 한다.
- 도킹 비활성 상태의 close(None lease)와 recovery 조회(pending)를 보완했다. 실제 Goal을 만들지 않는 UnavailableDocking의 pending만 false다.
- transport_route CLI에 sim 선택 추가. 새 실행 프로필은 아직 제공하지 않았으며 기존 all.launch.py/fleet 기본 실행은 바뀌지 않았다.

공통 farm_navigation/harvest_robot/scout_robot/farm_common 및 기존 실물 설정은 이번 단계에서 변경하지 않았다. 따라서 기존 거리 기반 timeout·교통·D059 이동 조건·수확 실행은 보존된다. 신규 운송의 실제 런타임/하드웨어 동등성은 아직 검증 전이다.

## 직접 실행한 검증

- colcon: farm_interfaces, farm_docking, transport_robot **3패키지 빌드 PASS**.
- pytest: 기존 주행/교통/수확 관련117 + 운송 원본 FSM12 + sim 경계/복귀12 = **141 PASS**.
- 실제 생성된 메시지와 TransportNode/PrecisionServer/MotionGate import PASS.
- Domain13/SUBNET, 고유 `transport_contract_probe_<pid>` namespace에서 실제 DDS Action 검사 PASS. 성공(4/SUCCESS), 실패(6/FAILED), 취소(5/CANCELED), docked 의미, 같은UUID 결과 재조회, 같은task_id 중복 거절 확인.
- DDS 시험의 Navigator는 대역이며 cmd_vel을 생성하지 않는다. 실제 로봇·관제에 작업을 보내지 않았고 시험 프로세스는 종료했다. 실행 도구: `sim/tools/transport_action_smoke.py`.
- 실제 USD를 읽어 운송 base_footprint articulation과 cargo_box, 현재 운영 수확 USD의 harvest_box 존재/변환 확인. 모델 변경/Isaac 물리 시작은 하지 않았다. 일부 빈 visual 참조 경고가 있어 원본 로그를 보존했다. 이 경고를 차체 물리 실패로 단정하지 않는다.
- 전체 예찰→선별장 E2E, Isaac 주행, 바구니 정렬 유지 시험, 실물 시험은 **NOT_RUN**.

검증/원본 SHA: `sim/docs/test_results/20261027_transport_integration/validation.json` 및 동봉 로그.
로컬 실행 로그: `sim/runs/transport_integration_20261027/`.

재실행(물리 주행 없는 DDS 계약 시험):

```bash
cd /home/ysy/main/farm_project
source /opt/ros/jazzy/setup.bash
source scripts/env.sh sim
export ROS_DOMAIN_ID=13
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export ROS_LOG_DIR=/tmp/farm_transport_dds_20261027
/usr/bin/python3 sim/tools/transport_action_smoke.py
```

## 다음 구현 경계

운송 가상 장치/환경 프로필과 fleet 조립부터 연결한다. station yaw·카메라 장착·차체 충돌/바퀴 축·바구니 개구부의 실제 USD 형상을 확인하고 map/odom/scan/Image/CameraInfo를 기존 어댑터로 공급해야 한다. 그다음 마커42/41 관측과 도킹을 검증하고 바구니 정렬 판정을 연결한다. 바구니 GT 상대 위치는 평가 전용이며 도킹 제어에 주입하지 않는다.

커밋·푸시는 수행하지 않았다. 되돌릴 때는 이번 추가 패키지/메시지 및 CMake 등록, sim 시험·문서만 제거하고 farm_interfaces를 다시 빌드한다. 기존 미커밋 검토 문서·사용자 전달 폴더는 보존한다. 통합 원본 대비 변경 파일과 SHA는 validation.json으로 확인한다.
