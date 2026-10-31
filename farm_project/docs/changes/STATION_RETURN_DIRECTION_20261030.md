# 예찰·수확 공통 스테이션 복귀 방향 선택

2026-10-30 / 기준 main399379087374f9982b177e70d68e11721d5fdaaf 및 기존 미커밋 변경 보존.

## 승인·목적

사용자 명시 승인: 예찰/수확은 실물에서도 스테이션 마커 도킹을 하지 않음. 전진 경로가 가까우면 전진 복귀 후 스테이션에서180도 회전, 후진 경로가 가까우면 후진 복귀하도록 공통 코드 변경. 운송의 마커 도킹은 별개로 유지.

## 변경

- robot/ros_ws/src/farm_common/farm_common/station_return.py: 현재→스테이션 방향 그래프의 전진 경로, 기존 스테이션→현재 경로를 뒤집은 후진 경로를 비교. 거리 우선,1마이크로미터 이하 부동소수점 동률은 출발 방향 정렬량으로 선택. 단절 경로는 제외하고 기존 StationReverse의 초기 방향 제한(pi/2+0.1rad)을 위반하는 후진 후보도 제외한다. 모두 불가능하면 오류; 직선 이동으로 대체하지 않는다. 초기 방향 검사는 그래프 투영 오차를 넘는 경로점 기준의 사전 검사이며 실제 제어기의 carrot/충돌 검사와 동일 입력 재현은 아니다.
- 선택 결과/후보 거리/방향/경로/최종yaw를 STATION_RETURN_PLAN 로그로 기록. 전진은 기존 RPP, 후진은 기존 StationReverse. 선택한 Navigator만 실행·취소한다. 클라이언트2개는 종료 시 모두 닫는다.
- 전진도 goal orientation은 기존 스테이션 yaw다. 기존 RPP가 위치 도착 후 제자리 방향 정렬(현재 맵 북향 진입→남향 주차 약180도)을 수행하고 Navigator가 기존 정지 확인을 마쳐야 성공한다. 시간 기반 개방루프180도 명령이나 도착 즉시 성공을 추가하지 않는다. 이미 스테이션인 경우 불필요하게 무조건180도 돌지 않고 지정 방향을 맞춘다.
- 속도·충돌 검사·XY/yaw 허용값·진행 검사·시간 기준·취소/정지미확인 처리·Action 필드 유지. real의 기존 SUCCESS/docked=false 및 sim의 SUCCESS/docked=true 계약도 유지; 마커가 없다는 사용자 확인만으로 메시지 계약을 함께 변경하지 않았다.
- 운송 transport_robot/farm_docking과 실물/시뮬 YAML/지도는 이번 변경 대상 아님. 기존 작업 파일 변경은 보존.

## 검증

`source /opt/ros/jazzy/setup.bash && source robot/ros_ws/install/setup.bash && python3 -m pytest -q robot/ros_ws/src/farm_common/test/test_station_return.py robot/ros_ws/src/farm_navigation/test/test_navigation.py robot/ros_ws/src/farm_navigation/test/test_nav2_execution_clock.py robot/ros_ws/src/farm_navigation/test/test_nav2_route_timeout.py sim/tests/test_transport_sim_integration.py`

57PASS. 새 공통 시험14개: 거리/동률방향, 단절·잘못된후진거절, 이미도착방향정렬, 전진Path의 최종180도 목표, real/sim결과, 실행중취소, 충돌실패, 정지미확인, 두제어기설정/정리. ROS입출력은 대역이며 물리/실기 시험이 아님.

시뮬 실제 지도 SEC01~16 예찰/수확 명목 종점32개 계획 모두 성공. 홀수SEC후진/짝수SEC전진. 실패한 예찰SEC02 명목종점은 전진4.905m 선택. 수확SEC01 마지막시험좌표(-6.015,3.24)는 후진14.025m/전진20.505m, 명목종점y=2에서는 후진15.265m. 좌표가 다른 수치를 혼동하지 않는다.

자료: sim/runs/fresh_full_cycle_20261030_114723_after_push/failure_analysis/attempt_002/station_return_fix/nominal_routes.json. py_compile 및 git diff --check 통과. 설치된 farm_common의 build 경로가 수정한 src 파일을 가리키는 것을 확인했으므로 새 프로세스에서 적용된다.

## 실행 상태·한계

진행 중3차 노드는 수정 전 모듈을 이미 로드했다. 이번 변경으로 중단/재시작/실시간 교체하지 않았다. 다음 프로세스 시작부터 적용. 수정 후 Isaac 전진복귀/180도회전 및 실물 시험은 아직 미실행, 실제 회전 공간/장애물은 기존 Nav2가 검사하며 막히면 실패한다. 공통코드 수정완료와 실제한사이클성공을 구분한다.

복원: station_return.py의 이번 방향선택·전진클라이언트 추가만 이전 구현으로 되돌리고 새 시험 파일 제거. 기존 다른 미커밋 변경을 되돌리지 않는다. 커밋·푸시 없음.
