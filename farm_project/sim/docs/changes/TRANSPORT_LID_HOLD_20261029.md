# 운송 상부 뚜껑 임시 고정 — 2026-10-29

## 적용 내용

사용자 “일단 뚜껑이 안막히게 조치해” 요청에 따라 시뮬 전용 transport_robot.sim.usda에만 두 상부 뚜껑 관절 override를 추가했다. 직선 관절의 lowerLimit/upperLimit를 모두0으로 맞춰 닫힌 위치에 고정하고 PhysxMimicJointAPI:rotY를 제거했다.

현재 MechanicalRosServer는 정렬·정지 증거 기반 가상 덮개 장치이고 실제 pinion/뚜껑 joint를 구동하지 않는다. 가상 과실 인계·레인 투입 흐름은 그대로다. 이번 조치는 실제 기구 개폐 구현이 아니며, 물리 개폐가 필요해지면 고정을 제거하고 원본 URDF 범위0~0.155m와 pinion 연동을 검증해야 한다.

- 변경 파일: `sim/assets/robots/transport_robot/urdf/transport_robot.portable/transport_robot.sim.usda`.
- 형상·질량·충돌·바퀴·핀리언·기타 관절·공통 코드·실물·성공 판정은 변경하지 않았다.
- 원본 portable_physics.usd/URDF도 보존했다. 시뮬 overlay의 해당21줄만 제거하면 이전 상태로 복원된다.
- 기준 HEAD `18d0e000d4c98e3478e0a8510d84948561fc7d5f`, 기존 미커밋 변경 유지. 이번 commit/push는 요청되지 않아 수행하지 않았다.

## 검증

정적 USD 합성: 두 관절 제한0/0과 mimic API 제거 확인. 바퀴·pinion authored 속성은 전후 동일. Git LFS 원본 로컬 객체와 비교한 diff는 해당21줄뿐이며 `sim/runs/transport_lid_hold_20261029/lid_hold.patch`에 보존했다.

원래 명령 재생과 같은 설정으로 542sim초 비교 시험을 수행했다. Domain13/SUBNET, CPU60Hz/render30Hz, 운송 단독, 센서 일부 비활성, ROS 액션 대신 기록된 속도 명령을 sim시각에 맞춰 재생한다. 따라서 공통 액션 전체 사이클 성공과 구분한다.

- 이전 재생: session c2b9ffe532bd431299ba3a8450c4f9ff. 오른쪽 뚜껑 최대3.296m 이탈, 구조물 접촉 후 회전 정체와 후진 밀림32.3mm.
- 수정 후: `sim/runs/transport_lid_hold_20261029/replay/`. 결과는 아래 최종 결과 참조.
- 첫 시작은 Modbus host/peer 실행 인자 누락으로 초기화 실패. 준비 오류 로그를 preparation_failed_*로 보존했고 127.0.0.1 명시 후 재실행. 이 시도는 물리 검증 결과에 포함하지 않는다.
- 실제 시험 결과는 진단 계측으로 검증하며, 모델 제한값만 보고 해결됐다고 판정하지 않는다.

## 최종 결과

- session `e386499e15bc493b8aad39f53ba2c553`, 542.017sim초 기록, probe 정상 완료.
- 전체 기록에서 두 뚜껑 관절 최대 변위 **0m**. 뚜껑의 0보다 큰 충격량 접촉 기록 **0건**.
- 이탈 회전 sim522.10~535.97초: yaw1.80378→-1.54734rad. 수정 전처럼 회전이 정체하지 않았다.
- 회전 중 실제 차체 최대 이동 **7.25mm**, 종료 시 **7.17mm**. 이전 명령 재생은32.30mm 뒤로 밀리고 yaw -0.039rad에서 정체했다. 원래 액션 실패 로그는52.37mm였다.
- 같은 속도 명령/농장/물리 조건의 재생이다. 물리 변화에 따라 회전 시작 위치는 수정 전 재생과 약5cm 다르며, 공통 제어기로 목표를 닫힌루프 추종한 전체 사이클 시험은 아니다.
- 뚜껑이 주행 중 이탈해 구조물에 걸리는 현상은 이번 재생에서 해소됐다. 도킹·인계·선별·복귀 전체 액션의 성공을 새로 검증한 것으로 간주하지 않는다.
- 증거: `sim/docs/test_results/20261029_transport_lid_hold/`. 변경 파일 패치: `sim/runs/transport_lid_hold_20261029/lid_hold.patch`.
- 임시 고정의 제한: 실제 상부 뚜껑 개폐 동작은 하지 않는다. 현재의 가상 기구 장치와 과실 인계 방식은 유지한다.
