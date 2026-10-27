# 인계 이후 선별장 접근점 이동 연결

2026-10-27 KST. 기준 main `b5ef6f2`, 공통 운송 원본 `9686aca`. 사용자가 선별장 이동 연결·정상 완료 후 커밋/푸시를 요청했다. 실제 모델에 접근점·경로를 맞추는 안을 추가 승인했다(D-066).

## 연결 내용

- 실제 선별장 USD 원점은 map/world `(-7,14)`, 방향+90°이고 기존 접근점8004는 `(5,13.25)`였다. 모델을 이동하지 않고 접근점을 `(-7,13.25)`, 목표방향+90°로 수정했다. 기존 북쪽 통로9001 `(-6.655,11.5)`와 양방향 연결30514/30515를 정합했다. 다른 노드·베드·통로는 변경하지 않았다.
- 원본 `task.yaml` / `scout_harvest.geojson` 수정 후 생성기로 역할별 그래프와station을 갱신했다. 운송143노드324엣지 유지. 강연결·16SEC/80예찰점·371경로 검사 통과. 신규 접근 구간 주변±20cm 지도표본은 free였다.
- `transport_runtime.yaml`, `nav2_transport.yaml`, `transport_destinations.yaml`, `transport_navigation.launch.py`: 공통 TransportNode + 실제 AMCL/map_server/Nav2 controller/velocity_smoother 연결. 주행은 기존 TransportNavigator·Nav2Client·RPP·MotionMonitor를 사용한다.
- 최종 출력은 기존 motion_gate 하나다. Nav2 smoother→motion/nav, 정밀주행→motion/precision로 입력을 분리하고 기존 LeaseClient/ExclusiveNavigator가 소유권을 넘긴다. 실제 DDS 발행자 수1 확인.
- 72% 이상 정렬·정지 조건으로 가상 인계 완료→실제 CLEAR→실제 CheckRoute Action으로 선별장 접근점 도착·정지를 확인한다. 이격 뒤 로봇을 재배치하거나 시뮬을 리셋하지 않는다.
- 도킹/이격 종료 뒤 시험 영상 구독을 해제하여 선별장 이동 중 카메라 비활성 확인.

## 직접 실행 결과

| 실행 | 결과 | 선별장 이동 실시간 | 도킹 시작부터 실시간 | 실제 좌표 오차 |
|---|---|---:|---:|---:|
| 1 | SUCCESS / arrived=true | 141.34초 | 175.70초 | 11.19cm |
| 2 | SUCCESS / arrived=true | 147.37초 | 182.72초 | 9.82cm |

두 실행 모두 작업 중 실패/재시작 없음. 최종 실행의 AMCL 기준 위치 오차는 0.05cm이며 실제 좌표 오차와 구분한다. 두 실행 모두 도착 결과 저장 후 Isaac SDK 정리에서 child exit-11이 재현됐다.

## 원본 보존

실물 Nav2 원본은 `config/transport_sources/waffle_nav2.yaml`에 9686aca 내용 그대로 보존했다. RPP 속도0.1m/s, lookahead0.07m, goal_checker XY0.01m/yaw0.05236rad, progress checker0.1m/10초, footprint, smoother 한계값 등 수치는 변경하지 않았다. 공통 최종 도착 조건0.1m/0.12rad 및 정지0.8초도 원본 운송 설정을 따른다.

차이는 namespace TF, scan 토픽, use_sim_time=true, 알려진 시작 배치에 대한 AMCL initial_pose뿐이다. `odom_frame_id`는 transport_01/odom, 상대 토픽 `odom_topic`은 odom이다. 실제 위치는 로그 평가에만 쓰며 주행/AMCL에 주입하지 않는다. 도킹20cm·이격25.2cm±1cm·바구니/선별장 USD 원본 불변. 이번 턴에는 공통 실행 소스를 수정하지 않았다.

실행 중 파라미터 덤프로 활성 RPP의 원본 지정값 전부 일치를 확인했다. 비활성 DWB의 `FollowPath.stateful`은 원본 YAML에 유지했지만 현재 플러그인이 런타임 파라미터로 선언하지 않았다. 이를 적용 완료로 집계하지 않았다. 상세 `validation.json`.

## 시험 범위와 해석

- Domain13/SUBNET, headless CPU PhysX MBP60Hz. 시작 배치는 북쪽 통로9014 근처의 수확 후 시험 상태다. 예찰/수확을 이번에 다시 실행한 것은 아니다.
- 도킹/기구/이격은 실제 DDS Action과 공통 State를 사용한다. 인계 TRANSFER_COMPLETE는 시험기가 기존 공통 TransferSession으로 전달한다. 관제 TransferEvent DDS 중계·전체 TransportPickup 접수는 미검증 상태를 유지한다.
- 선별장 단계는 **CheckRoute의 실제 도착·정지 SUCCESS**다. BucketUnload 전체 완료, 선별장 정밀 도킹·배출·선별 성공으로 해석하지 않는다. 과실 수량은 count_valid=false/loaded_count=null 유지.
- AMCL 기준 도착 성공과 실제 USD 좌표 오차는 별도 기록한다. 첫 실행의 정답 위치 오차는 약11.2cm였다. 기존 위치 추정 정밀도 개선 과제이며 이를 숨기거나 허용오차를 늘리지 않았다.
- 종료 정리 중 예외는 업무 중 실패와 구분한다. 첫 실행에서는 SIGINT 후 gate exit1, precision exit-2, Isaac 내부 Python child exit-11이 남았다(ROS launch 상위 프로세스 exit0). 도착 결과 이후 SDK 종료 오류이며 원시 로그/summary에 포함한다. 이전부터 있던 종료 문제를 이번 이동 성공으로 해결됐다고 선언하지 않는다.

## 검증 자료

결과표와 이동 궤적은 아래 시험별 summary를 따른다.

- [첫 실행](../test_results/20261027_sorter_route/attempt1/summary.json)
- [최종 설정 실행](../test_results/20261027_sorter_route/attempt2/summary.json)
- [첫 실행 실제 궤적](../test_results/20261027_sorter_route/attempt1/route.png)
- [최종 설정 실제/추정 궤적](../test_results/20261027_sorter_route/attempt2/route.png)

각 폴더에 Action 결과·단계 이벤트·실제 trajectory·Nav2 실행 파라미터·cmd_vel 발행자·시험 배치·종료 로그를 저장한다. 전체 raw는 `sim/runs/sorter_route_20261027/attempt{1,2}/41/`, 실제USD/odom은 해당summary.session의 `sim/runs/drive_diagnostics/`에 있다.

오프라인/ROS 환경 단위검사75개 통과, 경로 검증371건 통과, sim_config/runtime 빌드 통과. 테스트 도구의 ROS_LOG_DIR를/tmp로 지정하고 USD 검사는 Isaac Python 환경에서 수행했다. 숫자/판정 보존 검사와 기존 카메라/시각/가상기구/물리/launch/운송 회귀를 포함한다.

## 재실행

```bash
cd ~/main/farm_project
source /opt/ros/jazzy/setup.bash
source scripts/env.sh sim
export ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export ROS_LOG_DIR=/tmp/farm_sorter_route
python3 sim/tools/prepare_sorter_route_trial.py sim/runs/sorter_route_next
python3 sim/tools/run_docking_alignment_trial.py 41 sim/runs/sorter_route_next --sorter
python3 sim/tools/analyze_sorter_route_trial.py \
  sim/runs/sorter_route_next/41 sim/runs/sorter_route_next/report
```

새 결과 폴더가 필요하다. 기존 결과를 덮어쓰지 않는다. 운송 navigation launch는 기존 adapter·clock·motion_gate가 실행된 상태에서 사용한다. 전체 관제 자동 업무 연결 완료를 뜻하지 않는다.

복원: 이번 station8004/연결30514·30515 원본 변경을 되돌리고 rebuild_route_data.py 실행, 새 transport navigation launch 연결 해제. 기존 인계·도킹 코드와 모델을 원복할 필요는 없다.

변경 파일 전달본은 `sim/runs/transport_sorter_connection_20261027_patch.zip`이다. Git 반영과 같은 파일 묶음이며 적용 명령은 다음과 같다.

```bash
cd ~/main/farm_project
unzip -o ~/Downloads/transport_sorter_connection_20261027_patch.zip -d "$PWD"
```
