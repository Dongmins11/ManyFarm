# 벽 정렬 전용 목표 각도 — 2026-10-20

## 근거
정지 상태 실측: 로봇 앞면의 좌우 측정 지점 사이 50cm, 왼쪽 벽 간격 16cm, 오른쪽 13.3cm. 실측 기울기 크기는 atan(0.027/0.50) 약 3.09도이다. 같은 자세의 라이다 82프레임 중앙값은 -0.636도였다. 현재 부호 정의에서 실물 벽 법선 상대각은 약 -3.09도이므로 라이다가 약 +2.45도 크게 읽는 것으로 해석해 시험 목표를 +2.45도로 설정한다.
단일 자세 실측에 근거한 시험 보정이며 장착 TF 오차로 확정하지 않는다.

## 변경
- 공통 Config.target_angle 기본 0rad. 유한값이며 abs(target_angle)+허용오차가 기존 max_yaw보다 작아야 한다.
- 공통 각도 오차는 wrap(관측 벽 법선각 - 차체 yaw - target_angle). WallController와 WallGoalChecker는 동일 errors/Control을 사용한다.
- wall_input은 wall_alignment.target_angle을 두 플러그인에 공통으로 읽는다.
- Python 시험 감독기의 시작 오차 검사·Goal 방향·최종 정지 후 판정도 같은 목표를 사용한다. 기존 raw wall_angle/final_angle은 보존하고 wall_angle_error/final_angle_error를 별도 기록한다.
- Vic Pinky 시험 JSON에만 +2.45도(0.04276056667386108rad)를 지정한다.
- 거리 계산은 원래 벽 법선 기준을 유지한다. 라이다 TF, 관측 벽 선택, 주행/Nav2 설정, 곡선, 지도/태그, 속도 상하한과 ±1도/5mm 허용오차는 변경하지 않는다.

## 검증
로컬 실제 C++ 코드의 기존 검사와 신규 보정 부호·0기본값·양음 목표·완료·잘못된 설정 검사 통과. Python 감독기의 목표 각도 적용 연결을 정적으로 검사한다. ROS 미설치 작성 환경이므로 빌드/configure/실물 통과는 주장하지 않는다.
run_pc.bash는 PC 빌드/CTest/configure 파라미터 조회가 통과해야 로봇 원본을 PC에 백업하고 승인 파일을 적용한다. 로봇에서도 wall 패키지 빌드/CTest/configure 및 무이동 plan을 수행한다. 실제 이동과 커밋은 실행하지 않는다.
