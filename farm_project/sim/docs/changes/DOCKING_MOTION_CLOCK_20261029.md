# 도킹 접근 제한시간의 시계 수정 — 2026-10-29

사용자 “시간을 시뮬시간으로해야지 절대시간이아니고 … 프레임이 떨어지는데” 지시에 따른 공통 수정. main18d0e00 및 기존 미커밋 작업을 보존했다.

- 원인: attempt02 마지막 라이다 접근은 설정65초를 거리 기반 약25.5초로 계산한 뒤 time.monotonic 실제시간으로 검사했다. 실제25.72초/시뮬14.03초에서0.203m까지 도달하고도 정지 확인 중 실패했다.
- 변경: precision_server.py에 동작 시계 선택 추가. use_sim_time=true이면 노드 ROS시계(/clock), false이면 기존 time.monotonic. 라이다 접근 시작/경과/초기 표면 확보 대기와 전체 정밀주행 예산, execute의120초 상위 제한을 같은 동작 시계로 계산한다. 노드의 기존 use_sim_time 설정을 사용하며 새 설정/의존성 없음.
- 라이다 센서 복구 대기는 실제시간과 동작시간 시작점을 따로 기록한다. 기존 센서 단절 대기 제한은 실제시간으로 유지하고, 복구 후 실제시간을 시뮬 예산에 더하지 않는다. 시계 역행은 액션 재시작이 필요한 오류로 처리한다.
- 실물은 기존 단조 증가 실제시간 유지. 거리 기반25.5초 계산·설정65초·속도·20cm/±0.5cm·정지 완료 조건은 변경하지 않는다. 센서 수신 단절·lease·통신 응답·로그 주기는 기존 실제시간 기준이다.
- 범위: 이번 실패의 라이다 접근과 이를 감싸는 전체 액션 예산. 다른 주행 모듈·마커 검색/회복 등 모든 단계의 시간 처리를 전면 교체한 것은 아니다. 시뮬 pause가 센서 단절 감시까지 무효화한다는 의미도 아니다.
- 검증: 새 시계 회귀9검사 + 기존 도킹 전환11검사 =20 PASS. 실제25.72/sim14.03 상황에서 완료 경로 허용, 시뮬pause 시 동작예산 미소진, 선택시계 예산 초과 실패, 실물monotonic 유지, 시계역행 실패, 복구시 두 시계 분리, 센서단절 실제시간 감시, 시작시계/거리계산 보존 확인. farm_docking colcon 빌드 및 git diff --check PASS.
- 실제 Isaac 재시험은 이번 수정 후 미실행. DOCK_STABLE/최종 도킹 성공을 아직 주장하지 않는다. 다음은 도착 전용 검증을 포함한 운송 출발→도킹 재시험.
- 복원: 이번 motion_time/motion_elapsed와 motion_started/lidar_input_wait_motion 변경만 제거하고 기존 실제시간 계산으로 복원. 이전 승인된 route_handoff 거리 검사와 다른 미커밋 작업은 보존한다. 미커밋·미푸시.

```bash
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/local_setup.bash
python3 -m pytest -q sim/tests/test_docking_motion_clock.py sim/tests/test_harvest_route_envelope.py
```

변경 파일 묶음(공통 파일에는 앞서 승인된 도킹 전환 수정도 포함, 누적 문서는 기존 다른 작업 기록 포함):
```bash
unzip -o sim/runs/docking_motion_clock_20261029_changes.zip -d /home/ysy/main/farm_project
```

후속 실제 재시험: attempt03은 초기 마커 취득 실패로 마지막 라이다 접근 미도달. 상세 DOCKING_MOTION_CLOCK_RETEST_20261029.md 참조. 시계 수정 E2E 검증 완료가 아님.
