# 수확 인계 시뮬 연결 및 장치 시험 — 2026-10-28

## 완료 범위

사용자 “다음 작업 해” 승인으로 1단계 통합 코드에 시뮬 시계·TF·센서·가상 배출 장치를 연결했다. 공통 차체 제어·FSM·수치·성공 판정은 유지하고 환경 연결만 확장했다. 새 인계 실행 묶음은 생성 도구로 명시적으로 선택한다. 기존 일반 수확 설정의 transfer.enabled=false는 그대로다.

기준은 main `ea25693650a9a61d8bbcfcf6e02f6ac6889a97a1` + 직전 미커밋 통합, 실물 원본은 `e135cdef9462276cc25d9fa336f084e2dcac72e4`다. 이번 작업도 미커밋·미푸시다. Frontend와 기존 실물 설정·USD 자산은 수정하지 않았다.

**실제 Isaac + DDS로 인계 서버 활성화, 팔 준비 확인, 미준비 요청 거절, 정렬 후 배출 Action 성공을 검증했다. 완료된 윈도우에서 시작하는 차체 인계 전체 동작이나 SEC01 전체 사이클 성공을 뜻하지 않는다.**

## 실제 실행 결과

조건: ROS_DOMAIN_ID=13, ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET, Isaac headless, CPU 물리/MBP/60Hz. 소스 숫자만 확인한 것이 아니라 실행 로그의 gpu_dynamics=false도 확인했다.

| 시험 | 결과 | 확인한 범위 |
|---|---|---|
| 최초 준비 | 실패 | 공통 원호/벽 설정이 이름 `odom`만 허용하여 sim의 `harvest_01/odom` 거절. 주행 전 launch 실패이며 105 아님 |
| 수정 후 일반 정차 배치 | 성공 | 실제 팔 접힘 확인, 4개 인계 노드 use_sim_time=true, cmd_vel_nav 단일 발행자. 완료 윈도우 없는 DockTransfer 거절, 정렬 안 된 Discharge 거절 |
| 정렬 정차 배치 | 성공 | 일반/인계 Nav2 서버 active 확인. 실제 겹침72.6426%, 정지2.90초. 운송 LID_OPEN → 수확 Discharge SUCCEEDED(4), 오류배열 없음 → LID_CLOSE 완료 |

정렬 시험은 과거 실제 도킹 정지 기록의 초기 자세를 사용했다. 이번 실행에서 다시 도킹한 것은 아니다. 초기 배치 뒤에는 로봇을 순간 이동시키지 않았다. 입력 기록과 초기 배치 근거는 aligned/fixture_basis.json, 실제 이번 평가값은 aligned/connection_result.json에 있다. 실제 월드 상대 자세는 인계 평가에만 사용하며 주행/위치 추정에 주입하지 않았다.

수확 배출은 사용자 승인된 정렬·정지 기반 가상 장치다. 배출구 USD나 과실을 움직이지 않았고, 전달 수량은 count_valid=false/미측정으로 남겼다. 기대 수량을 실제 수령량으로 만들지 않는다. 기존 바구니72%/정지0.8초 기준도 바꾸지 않았다.

### 실패·종료 기록

- 최초 실행에는 위 odom 프레임 거절과 함께 sandbox의 Isaac 재질 캐시 쓰기 금지 오류가 있었다. 수정 후 실제 실행에 필요한 캐시 접근을 허용받아 재시도했다.
- 초기 교통 검사 15개 실패는 시험 mock이 zone_01을 고정해서 새 zone_02를 거부한 결과였다. 시험 입력을 현재 등록 버전에서 읽도록 수정했다. 운영 버전 검사를 약화하지 않았다.
- 결과 저장 후 SIGINT 정리에서 일부 ROS child exit-2/예외, Isaac 종료 지연 후 SIGTERM 및 child exit-11이 남았다. launch 상위 프로세스 exit0과 구분해 원시 로그를 보존했다. 이 종료 문제는 이번에 해결하지 않았다. 시험 프로세스 정리는 완료했다.

## 코드 변경

| 대상 | 변경과 보존 |
|---|---|
| farm_bringup/launch/harvest.launch.py | 명시 handoff_config의 sim 실행 허용. 해당 환경 경로 검사. sim은 /clock와 전역 TF 사용, 기존 scan을 인계 scan 입력에 remap. real은 기존 namespace TF·wall clock 유지 |
| harvest_robot/handoff_runtime.py | sim/real 모드 선택과 bundle의 odom 프레임 사용. 센서·costmap·경로·복귀 좌표계를 같은 이름으로 연결. TF 복구 비활성/단일 출력 조건 유지 |
| handoff_server_config.py, transfer_retreat.py | AMCL odom_frame_id와 costmap 프레임 일치 요구. Spin도 같은 odom 사용. 기본값 odom 유지 |
| farm_navigation/arc_isolation.py, wall_trial_support.py | 명시 odom_frame 인자 추가. 기본 odom 및 프레임 불일치 거절 유지 |
| handoff_input_trace.py | 진단 TF도 선택한 odom 프레임 사용 |
| sim_devices/harvest_transfer_ros.py | 실제 팔 접힘·정지·최신성 확인 Trigger와 Discharge Action. 중복·취소·중단·세션 변경·정렬 만료를 처리 |
| sim_devices/arm_session.py, ros_adapter.py | 기존 팔 telemetry에 측정된 접힘/동작 상태 추가. 명시 harvest_transfer.enabled 선택 시에만 새 장치 연결. 팔 미연결이면 시작 거절 |
| sim_runtime/run_fleet.py | 기존 바구니 평가를 수확 측 장치에도 전달. 평가 방법 불변 |
| sim/tools/prepare_harvest_handoff.py | 원본 실물 transfer 수치와 기존 sim 데이터를 읽어 sim/runs에 실행 묶음 생성. 주소/시계/프레임/기록 경로만 환경에 연결 |
| sim/tools/*handoff_connection.py | 움직임 없는 실제 장치/런타임 연결 시험과 결과·프로세스 정리 기록 |

prepare_arm은 기존 수확 동작이 실제로 팔을 접은 상태를 확인한다. 이 서비스가 별도 접기 동작을 가짜로 완료시키지는 않는다. 측정 기반 travel_ready가 없거나 팔이 움직이는 중이면 실패한다. stop 역시 관측된 실제 팔 정지 없이 성공을 반환하지 않는다.

원본 인계 거리·속도·각도·시간·재시도 정책은 변경하지 않았다. 실물 원본 환경 입력으로 생성한 최종 인계 파라미터 JSON은 1단계 원본 결과와 바이트 동일하다. sim 환경 차이는 생성된 source_adaptations.json에 기록했다. 센서 시계 전달 대기는 기존 운송 어댑터와 같은0.1초를 선택했고 측정 stamp는 바꾸지 않는다.

## 교통 등록 자료 정합

기존 선별장 변경 뒤 source snapshot에는 8004=(5,13.25), 연결9019가 남아 있었다. 실행 그래프의 8004=(-7,13.25), 연결9001에 맞춰 다음을 함께 갱신했다.

- graph.geojson/harvest_graph.geojson 등록용 snapshot.
- 해당 node 구역과 edge 구역의 graph_refs·bounds·edge_to_zone.
- 각 graph_revision을 graph_02, zone_revision을 zone_02로 증가.
- source_manifest의 현행 SHA256과 버전. original_sources는 원래 인수 자료의 이력으로 보존.

그 외 구역/차체 여유/정책은 유지했다. sync_traffic_graphs.py는 기존 노드·엣지 ID의 좌표/연결 변경만 처리하며 추가·삭제는 거절한다. 재실행 시 변경0을 확인했다. 단순히 그래프 파일만 복사해 해시 검사를 우회한 것이 아니다.

**Frontend에 받은 등록 자료는 여전히 zone_01이므로 아직 같은 버전이 아니다.** Frontend 파일을 수정하거나 운영 관제에 등록하지 않았다. 전체 교통 연동 전 같은 zone_02/graph_02 자료를 관제에도 반영하고 재초기화·재등록해야 한다. 현재 인계 실행 묶음은 교통 기능을 켜지 않는다. components 인계와 교통 동시 출력 연결 거절 조건도 유지한다. 원호가 기존 그래프 외부로 나가는 경우의 예약 계약은 별도 검토 대상이다.

## 검증

- 공통 주행215 통과(기존 실패했던 교통21개 포함, 실제 로컬 운영 자료 사용).
- 수확196 통과, 별도 Jetson ROS5개 건너뜀.
- 시뮬 회귀58 통과: 증거 누락/만료/미접힘/취소/세션 변경/중복배출/정지 실패/프레임 불일치/교통자료 정합 포함.
- 합계469 통과,5 건너뜀. 위의 실제 Isaac 정차 시험2회는 별도.
- farm_navigation, harvest_robot, farm_bringup, farm_sim_devices, farm_sim_runtime, farm_sim_config 빌드 성공.
- 실물 생성 파라미터 동일, git diff --check 통과.

공유 근거: [validation.json](../test_results/20261028_harvest_handoff_connection/validation.json), [이번 단계 파일별 해시](../test_results/20261028_harvest_handoff_connection/changed_files.json). 원시 실행은 sim/runs/handoff_sim_connection_20261028/, 공유 로그는 sim/docs/test_results/20261028_harvest_handoff_connection/다.

## 실행 및 다음 단계

기존 설정을 덮어쓰지 않고 새 실행 폴더를 만든다. 1단계 통합 패키지를 먼저 빌드해야 한다.

```bash
cd /home/ysy/main/farm_project
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/local_setup.bash
source sim/ros_ws/install/local_setup.bash
export ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
python3 sim/tools/prepare_harvest_handoff.py sim/runs/handoff_next/runtime
python3 sim/tools/run_harvest_handoff_connection.py sim/runs/handoff_next
```

새 일반 정차 연결 시험은 수확 작업/예찰을 보내지 않는다. 실제 업무 실행에는 생성된 harvest_runtime.yaml 및 handoff.json을 공통 harvest.launch.py에 전달하고 생성된 fleet.json으로 Isaac을 실행한다. 승인된 원본 수치 그대로 준비된다.

다음은 SEC01에서 실제 완료 윈도우를 확보한 뒤 공통 DockTransfer의 차체 원호·벽 정렬·복귀 동작과 관제 TransferEvent를 연결하는 단계다. 실물 벽 관측 거리/각도가 sim 베드 형상에도 성립하는지는 아직 이동 시험으로 확인하지 않았다. 시험 편의를 위해 완료 윈도우를 조작하거나 실물 수치를 완화하지 않았다. 선별장 정밀 도킹·하역·양 로봇 복귀 전체 사이클은 미검증이다.

## 전달·복원

이번 단계 수정 파일만 담은 패치: sim/runs/handoff_sim_connection_20261028_patch.zip. **직전 1단계가 적용된 작업공간용**이며 전체 배포 패키지가 아니다. 현재 PC에는 이미 반영되어 있다.

```bash
unzip -o /home/ysy/main/farm_project/sim/runs/handoff_sim_connection_20261028_patch.zip -d /home/ysy/main/farm_project
```

복원은 이번 changed_files의 파일만 작업 시작 전 내용으로 되돌리고 신규 도구/어댑터를 제거한다. 교통 자료는 snapshot·zones·manifest를 같은 버전 묶음으로 복구해야 한다. 기존 1단계 통합과 사용자 Frontend는 유지한다. 기본 일반 수확 프로필은 이번에 변경하지 않아 신규 생성 묶음을 선택하지 않으면 인계가 활성화되지 않는다.
