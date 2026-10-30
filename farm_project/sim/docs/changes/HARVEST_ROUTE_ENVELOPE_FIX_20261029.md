# 운송 접근→도킹 전환 거리 정합 — 2026-10-29

- 승인: 조기 도킹 전환 원인 설명 후 사용자 “붙어서 도킹으로 넘기도록 수정해그럼”. 공통 전환 조건 수정 승인으로 적용. 기준 main `18d0e00` 및 기존 미커밋 작업 보존.
- 실패 근거: `sim/runs/transport_resume_20261029_attempt02/precision.log`. 19:41:12 마커42 인식으로 Nav2 종료, 19:41:46 `Initial marker reacquisition exhausted`. 정차 후 `distance target outside approach envelope` 반복. 주행측은 ID/최신성만 검사했으나 도킹측은 접근 목표까지 1.2m 제한을 검사했다.
- 변경 파일: `robot/ros_ws/src/farm_docking/farm_docking/precision_server.py`의 `update_harvest_route`만 변경. 먼 마커를 인식해도 기존 Nav2 경로를 계속 주행하며, 현재 도킹 컨트롤러 설정으로 일회용 추적기의 첫 관측이 수락될 때만 ready를 발행한다. 같은 관측시각의 odom→base TF 및 같은 `StagedDockTracker.update` 거리/기울기 판정을 사용한다. 거절 이유는 기존 ready 메시지의 reason으로 전달한다.
- 1.2m는 차체 외벽 간격이나 마커까지의 거리가 아니라 **도킹 접근 목표까지의 평면거리**다. 현 프로필의 marker stand-off 0.54m도 기존 계산에서 그대로 반영된다. 직진·횡오차0인 경우 마커거리 약1.74m부터 전환 가능하다.
- 주행 중 검사기의 목표·샘플은 실제 추적기에 저장하지 않는다. Nav2 취소/정지 후 새 관측으로 8샘플 목표 취득하는 기존 과정 유지. TF 미확보/잘못된 관측은 ready=false. 관측900초 만료 및 Nav2 자체 실패는 기존대로 상위에 전달한다.
- 공통 적용 영향: 실물과 시뮬 모두 이 route_handoff 경로의 조기 전환이 제한된다. 실물/시뮬 설정 파일, 속도, 도킹 거리·성공 판정, 회복30초 등 수치 변경 없음. 선별장 도킹의 별도 전환 경로는 변경 없음.
- 검증: `sim/tests/test_harvest_route_envelope.py` 11개 PASS. 실제 공통 ready 발행→HarvestApproach 소비 경로로 원거리/경계 안팎/횡오차/오래된·미래·이전 세션 영상/다른 ID/TF 누락 및 복구/현재 컨트롤러 제한값/ready 해제/관측 만료 검사. ROS 노드나 모터 출력 없이 실행한 오프라인 검사다. `farm_docking` colcon 빌드, diff 검사 PASS.
- 미검증: 실제 Isaac 재주행·정차 후 지속 가시성·전체 도킹/인계 완주. 경계 통과 뒤 관측 오차나 정차 중 목표 변화 가능성까지 제거했다고 주장하지 않는다. 다음 검증은 기존 수확 완료 상태로 운송 재개, 전환 직전 거리/정차 후 목표 취득 로그 확인.
- 복원: 위 함수의 일회용 검사 부분을 제거하고 ID/최신성만으로 ready 발행하던 방식으로 복원(조기 전환 재발 가능). 다른 미커밋 수정은 건드리지 않는다. 커밋/푸시 없음.

검증 명령(프로젝트 루트):
```bash
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/setup.bash
python3 -m pytest -q sim/tests/test_harvest_route_envelope.py
```

변경 파일 묶음 복원/적용:
```bash
unzip -o sim/runs/harvest_route_envelope_20261029_changes.zip -d /home/ysy/main/farm_project
```
묶음의 누적 상태 문서는 현재 다른 미커밋 작업 기록도 포함하므로 다른 PC에서는 문서 병합 여부를 먼저 확인한다.
