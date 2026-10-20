# 차체 단독 Spin 시험

## 실물 인계 차체 회전 시험 준비 — 2026-10-19

- 사용자 승인: behavior_server 최소/최대 회전속도 0.1rad/s, 가속도 1.0rad/s²를 실물 override에 추가. 기존 주행 설정을 참고한 시험 후보이며 실물 Spin 검증 전이다. 같은 behavior_server의 다른 동작에도 영향 가능.
- robot/tools/transfer/spin_trial.py는 공통 farm_navigation.SpinClient를 재사용한다. left +90도와 right -90도는 별도 명령. 팔·배출·전체 인계 미션을 호출하거나 완료를 모의하지 않는다.
- 실제 확인 endpoint /harvest_01/spin 사용. 활성 상태·속도 설정·최근 odom과 1초 정지를 검사한다. 시험 관측용 정지 기준은 0.005m/s, 0.01rad/s, 요청 제한시간 40초다. 운영 인계 허용치로 확정하지 않는다.
- right는 성공한 left 기록과 종료 자세 연속성(5cm,0.1rad)을 검사한다. 실측 회전각/이동량/복원 오차를 기록하며 Action 성공과 정밀도 합격은 구분한다. odom 기반 측정이므로 외부 실측을 대신하지 않는다.
- 도구끼리 중복 실행은 잠금으로 막는다. 공통 미션 소유권을 획득하는 도구는 아니므로 관제·다른 터미널의 이동 요청을 중단한 차체 단독 시험에만 사용한다. 팔은 접힌 상태여야 한다. 오류 시 자기 Spin만 취소하고 정지 확인을 시도한다. Ctrl+C는 물리 비상정지가 아니다.
- 실물 local 0.02m·footprint·지도·태그·통신·수확 프로파일 보존. 시뮬 및 공통 실행 코드 변경 없음.
- 시작 절차 수정: AMCL active 직후 초기 위치를 발행해야 한다. 모든 Nav2 노드 active를 기다린 후 초기 위치를 발행하면 global costmap TF 대기로 시작이 실패할 수 있다. /tmp/init_station_newmap.py 존재 여부를 런치 전에 확인한다.
- 검증: Python 구문/CLI, YAML 차이 확인, 패치 적용 검사. ROS 도구 실행·실물 회전은 아직 미실행. 결과는 후속 기록한다.
- 복원: 추가한 실물 behavior_server override 제거 후 런치 재시작. 공통 기본값으로 되돌아가므로 Spin 시험을 이어서 실행하지 않는다. 사용자 VS Code 커밋 방식 유지.
