
## 2026-10-22 수확 인계 컴포넌트 연결 (별도 수정본)

사용자의 컴포넌트 조합 설계 및 진행 요청을 근거로 구현했다. 상태별 공통값 변경 대신 시작 시 전용 controller/저속 Spin 객체를 구성한다. 관제 window 좌표를 사용하고 기존 TransferMission의 TRANSPORT_CLEAR 이후 복귀한다. 다음 window는 다음 관제 목표로 받는다.

기준 커밋: 4b5c5b13605216d1b8b163ea988805572a6a908a. 대상: harvest_robot 연결/런타임/시험, farm_bringup의 선택적 출력 라우팅, vicpinky 전용 설정, 점검 도구. handoff_config 기본값은 빈 값으로 기존 실행을 유지한다. 시뮬에서는 새 기능 선택을 거부한다. 공통 Navigator/StationReverse 알고리즘은 변경하지 않았다.

직접 검증: 오프라인 64+58개 통과 및 정적 컴파일. 로그: 전달 패키지 component_checks.log, regression_checks.log. 실제 ROS/실물 주행은 미실행이다. 사용자 PC 적용 및 commit/push는 미실행. 실제 장치 서비스와 TF/odom/명령 라우팅 확인이 남았다. 변경 전 파일은 패키지 baseline에 보관하며 적용 도구는 기존 파일 비교 및 백업 후 변경한다. 상세 및 되돌리기: docs/changes/HARVEST_HANDOFF_COMPONENT_INTEGRATION_20261022.md.

# 시뮬레이션 통합 변경 이력

## 2026-10-21 복귀 단독 시험 보존 및 커밋 준비

기준 PC HEAD: `8df5f8eab87d450c675587b0be38ed85e3866a2e`. 사용자 제공 PC 소스와 로봇 `harvest_align_resume_tgm2zr8q/candidate`를 대조하여 누락된 실행 코드를 보존했다. 이번 변경은 검증 후보를 저장소로 옮기는 작업이며 제어 수치·완료 허용오차를 추가 변경하지 않는다. 커밋은 사용자가 VS Code에서 수행한다.

- 실물 후진 이탈 성공: 위치 오차 4.17mm, 정지 확인 완료. 기록 `1792558359276249505/1792558365404338213_arc.json`.
- 실물 방향 조정 성공: 위치 오차 5.56mm, 방향 오차 0.248도, 입력 시각 오류 없음. 기록 `1792560526521819101/1792560533286982755_arc.json`.
- 충돌 계산을 별도 프로세스로 분리하고 현재 입력과 유효한 기하 조건으로 결과를 검증한다. 계산 시간은 진단값이며 50ms 초과만으로 주행을 차단하지 않는다. 충돌·unknown·센서 단절·속도·정지 검사는 유지한다.
- 전진 복귀는 Nav2 성공 후 정지했으나 최종 방향 오차 1.91도가 기존 1도 기준을 넘어 실패 판정됐다. 위치 오차 1.77mm. 기록 `1792560666951148110/1792560672778478081_arc.json`. 성공으로 바꾸지 않는다.
- 같은 사이클의 벽 정렬은 관측 만료로 실패했다. 이전 벽 정렬 성공과 구분한다. 전체 연속 실물 주행 및 관제 연동 완료가 아니다.
- 다음 작업: 과한 완료 조건 검토와 초기 위치→12번→후진 곡선→벽 정렬→후진 이탈→방향 조정→전진 복귀→14번 연속 실행 연결.
- 이번 패키지 적용은 PC 소스만 변경하며 로봇 설치·이동·Git stage/commit/push는 하지 않는다. 백업은 Downloads에 저장한다.


## 최신 확인 상태 — 2026-10-21 KST

이 절은 아래 과거 기록의 “미반영/미검증/미커밋” 이후 확인된 결과다. 과거 기록은 당시 검증 범위를 남기기 위해 유지한다.

- 코드 커밋: `5d47a230699fa80551aad35cd5875a2fc87318a7`, 브랜치 `feat/harvest-handoff-real-20261018`. GitHub 반영 확인. 코드·설정·테스트·문서 79개이며 로그/빌드/설치 산출물은 해당 커밋에 포함되지 않았다.
- PC: 관련 회귀 26개, 실제 ROS 타입 16개, 독립 설치 및 실제 ROS 모의 FollowPath/파라미터/정지 odom 계약 검사 통과. 기록: `/home/eunbi/Downloads/harvest_preflight_check_zVeZWN`.
- 로봇: 16개 변경 항목 적용, 회귀 26개·ROS 타입 16개 및 독립 ROS 계약 검사 통과. 운영 `install/farm_navigation` 빌드 후 실제 import 파일과 소스 해시 일치 확인. 당시 검사에서는 실제 이동하지 않았다.
- 로봇 배포 기록: `/home/vic/Downloads/harvest_common_robot_TJWw1P`. 배포 전 PC 백업: `/home/eunbi/Downloads/harvest_common_robot_5Tg82O/robot_before.tar.gz` (체크섬 확인).
- 이후 공통 Navigator를 사용하는 벽 접근 실물 실행 성공: `SUCCEEDED`, `navigation.status=ARRIVED`, `accepted=true`, `cleanup_stopped=true`, `ros_cleanup_complete=true`, `baseline_unchanged=true`.
- 실물 기록: `/home/vic/vmany/main/farm_project/runs/wall_alignment/1792515109507469094/result.json`. 계획: `1792515066706348113/result.json` (동일 wall_alignment 폴더).
- 최종 관측 거리 0.4357192517535471m, 목표 0.4325m 대비 +3.219mm (허용 ±5mm). 보정 기준 각도 오차 -0.004926108427052628rad, 약 -0.282° (허용 ±0.5°).
- 최대 전진 명령 0.02m/s, odom 최대 전진속도 0.020808379895475848m/s. 속도 감시 이벤트 없음. 시작 시 TF 과거 시각 조회 실패 1건이 기록됐으며 이후 관측 및 완료 판정은 통과했다. TF 오류가 완전히 제거됐다고 기록하지 않는다.
- 성공 기준 유지: 연속 P·순차 정렬, target_angle=0.04276056667386108rad, 각도 허용오차 0.5°, 최대 전진 0.02m/s. 펄스 미사용. 곡선 충돌 검사·footprint 축소 없음.
- 최신 보존: `/home/eunbi/Downloads/harvest_common_success_dbLWxY`. `pc_source.tar.gz`, `robot_success.tar.gz` 모두 체크섬 확인. PC 소스/미추적 파일/Git diff 및 로봇 소스/설정/대상 설치본/이번 벽 계획·실행 기록 포함.
- 검증 범위: 이번 출력으로 공통 구조 적용 후 벽 접근의 실제 실행을 확인했다. 같은 재시험의 후진 곡선 상세 결과는 이 기록에 제공되지 않았으므로 별도의 신규 성공 수치를 만들지 않는다. 이전 곡선 성공 보존 기록은 유지한다. 물리 외부 측정 각도와 라이다 판정 각도는 구분한다.
- 전체 인계 FSM·팔/배출 연동·윈도우 복귀의 실물 통합 완료를 뜻하지 않는다. 본 갱신은 문서만 변경하며 커밋은 사용자가 VS Code에서 수행한다.


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

## 실물 성공 보존 — 2026-10-18 18:56 KST

- 사용자 보존 승인. 실물 local costmap resolution=0.02m를 이번 성공 기준으로 보존한다. 공통 코드·시뮬 설정은 추가 변경하지 않는다.
- 기록: runs/tag_bias_trial/20261018_185412_684309_on, 전달 원본 harvest_resolution002_trial.tar.gz.
- 목표 14번 (3.576, -0.035, yaw=0), graph_test_c7a18b04f61f4de6ababec0a4d547375. 18:55:17 수락 후 18:56:57 SUCCESS / SUCCEEDED / NONE. 코너 통과 후 목표 도착.
- 실제 bag costmap 해상도 0.02m 확인. costmap 419개, published_footprint 1068개 기록. 태그 관측 70회, 보정 요청/적용 각 7회.
- 이전 실패 기록 20261018_183455_478769_on과 비교 가능한 저장 입력은 real nav2.yaml local resolution 0.025→0.02만 다르다. footprint/padding·지도·태그·주행 설정 보존.
- 이번 검증은 공통 코드 기반 실물 주행·태그 보정 1회 성공이다. 반복 안정성·팔 수확·인계 물리 동작 완료로 확대 해석하지 않는다. 이전 코너 실패의 단일 원인이 해상도라고 확정하지 않는다.
- 복구 기준은 이번 백업의 코드와 설정을 대조하여 선택 적용한다. 과거 0.025m 성공본과 통합 전 로봇 전체 백업도 삭제하지 않는다.
- 문서 패치 제공 상태이며 사용자 PC 적용/백업 완료는 출력으로 확인한다. 자동 commit/push 없음. 커밋은 사용자 VS Code에서 진행한다.

## REAL-LOCAL-RESOLUTION-TRIAL-20261018 — 실물 코너 정지 비교 시험

- 사용자 승인: local costmap 0.025→0.02m 시험. 기존 성공값 0.025m를 새 성공값으로 대체 확정한 것은 아니다.
- 대상: robot/config/robots/vicpinky/nav2.yaml의 local resolution만 변경. 공통 정책, global costmap, 지도, footprint/padding, 속도, 태그, CycloneDDS/Zenoh 설정은 유지한다. 시뮬 동작 변경 없음.
- trial.py에는 local costmap/costmap 및 published_footprint 기록만 추가한다. 목표 생성·주행 순서는 유지한다.
- 사용자 제공 결과: 공통 코드 로봇 빌드 10개 패키지 성공, 관제 연결 및 PoseProgressChecker/scan 구독 확인. 18:37 주행은 코너에서 Nav2 106으로 실패했다. launch.log에 collision ahead 기록. 실행 local resolution은 0.025m였으므로 기존 해상도 누락은 아니다.
- 실패 기록: runs/tag_bias_trial/20261018_183455_478769_on. 정지 후 costmap은 실패 순간 자료가 아니므로 원인을 확정하지 않는다.
- 오프라인 검증: 설정 로더 병합·기존 보존 수치·목표 생성 검사, 기록 토픽 추가/파이썬 구문 검사, 패치 적용 검사. 0.02m 실제 주행 결과는 대기.
- 다음: 런치 재시작 후 resolution=0.02 확인, 실제 원래 출발 위치로 복귀한 뒤 올바른 초기 위치 설정, 기존 성공 순서로 Zenoh 연결, 동일 경로 1회 비교. 설정 변경만으로 해결을 보장하지 않는다.
- 복원: local resolution을 0.025로 복구 후 런치 재시작. 기록 토픽은 유지 가능. 커밋은 사용자 VS Code에서 수행하며 원격 반영하지 않았다.

## REAL-FIELD-PRESERVATION-20261018

- 사용자 승인: 성공 보존본 대조 후 시험 목표 방향과 실물 costmap 센서 연결 수정.
- trial.py 방향 기준 13→12: 10/14 그래프의 실제 12→14 엣지를 사용한다.
- vicpinky Nav2 override의 local voxel/global obstacle scan.topic을 기존 /scan_filtered로 복원한다. 실물 launch가 /harvest_01/scan_filtered로 remap한다.
- 공통 PoseProgressChecker는 유지한다. 지도·태그·속도·footprint·허용치와 시뮬 설정은 변경하지 않는다.
- 정적 검증과 실물 구동은 구분한다. 상세 및 복원: docs/changes/HARVEST_FIELD_PRESERVATION_20261018.md (프로젝트 루트 기준).

시뮬 전용 변경과 시뮬 통합에 필요한 공통 변경을 기록한다. 공통 변경은 사용자 승인 전 적용하지 않는다.

## SHARED-REAL-INTEGRATION-20261018 — 실물 설정·인계의 공통 연결

- 사용자 승인으로 공통 HarvestNode/설정 로더/ActionHandoff/launch 및 인계 인터페이스를 확장했다. sim 프로파일은 기존 기본값과 인계 OFF를 유지한다.
- 실물 지도·bias·Nav2 수치는 실물 설정에 보존한다. 공통 관측 모델과 주행 정책을 복제하지 않는다. sim 전용 소스/자산 변경 없음.
- 오프라인 완료 묶음 133개 통과. ROS/Isaac 실행 미검증 및 태그 의존성 제한은 docs/changes/HARVEST_COMMON_REAL_INTEGRATION_20261018.md 참고. 별도 통합 브랜치로 제공, 기존 운용 배포 없음.

## HARVEST-COMPLETION-PROFILE-20261016 — 이동 전용 실행 경로의 팔 생략 수정

- 요청/범위: 팔 작업 없이 완료되는 현상 확인 요청. 실제 런치·서버 파라미터·로그로 ARRIVAL_ONLY_NO_HARVEST 선택 확인.
- 대상/전후: 실제 사용 중인 `runs/navigation_smoke_20261014/harvest_runtime.yaml`의 harvest_config 참조를 이동 전용 시험 JSON→현행 canonical harvest_task.json으로 변경. 다음 시작부터 ARRIVAL_THEN_ARM을 선택한다. 이전 이동 전용 JSON은 증거로 보존했다. 공통/실물 변경 없음.
- 검증: 공통 환경 로더로 수정 경로를 읽어 팔 작업 정책/팔 활성화/60Hz 확인. 기존 실행 중 서버는 재시작하지 않았으며 사용자 작업 중단·Goal 전송 없음. 재시작 후 시작 로그와 실제 수확 완료는 아직 이번 실행에서 미확인.
- 복원/반영: `runs/harvest_completion_20261016/harvest_runtime_before.yaml` 또는 참조 한 줄 복구. PROJECT_STATE §67과 실행 가이드에 재시작 필요 명시. 미커밋/원격 미반영.

## WHEEL-TIRE-FIX-20261016 — 저속 회전 접촉 단면 수정과 정지 유지 보완

- 승인: 사용자 “진행해 … 원인을 … 설명해” 실행 요청. 기존60Hz 통합과 사용자 변경 보존, 공통/실물 수정 없음.
- 대상: `assets/robots/harvest_count_test/harvest_robot.usd`, `farm_sim_devices/wheel_servo.py`, `tests/test_wheel_servo.py`, `tools/rebuild_harvest_tire_collisions.py`, 진단 결과와 PROJECT_STATE §66/DECISIONS D-039/이 기록.
- 전후: 평평한50mm 원통 충돌선에서 같은 +0.05rad/s 4초 입력0.970° 정체→같은 외경/폭의 둥근 native 원통 묶음10.425° 회전. 평평한 단면 분할 대조군0.953°로 개수 증가 효과를 배제했다. 정지 유지 때 매 tick 적분 초기화→정지 전환에서만 초기화/유지 중 외란 오차 적분. 원래 kp1/ki4/상한2 유지(kp8 후보 탈락·복구).
- 검증: 바퀴 단위5개/자산 범위 검사 통과.46sim초 전후진·회전·정지 특성 기록, 실제 Nav2 양방향 정렬/0.5m 이동3개 정상 완료, 실제 Teacher 팔 Action2/2 적재·복귀·safe_stopped. 중속 급정지 피크2° 목표는 약3.4°로 미달한 계측 한계를 명시했다. 전체 농장 연속 미션·실물·밀집3개 복귀·접촉 취소는 이번 인증 범위 아님.
- 복원: `runs/wheel_contact_20261016/before_apply`의 자산과wheel_servo.py만 원위치 복사. 기존60Hz 통합을 되돌리지 않는다. 미커밋/원격 미반영. SHA와 결과/시행착오는 같은 runs의applied.json/verification_final.json을 따른다.

## WHEEL-CONTACT-DIAG-20261016 — 무부하/접지 분리 및 후보 탈락 기록

- 승인: 사용자 sim 전용 구동·접지 개선 방향 승인. 대상은 `sim/runs/wheel_drive_20261016/` 진단 실행 사본/집계와 PROJECT_STATE §64 정정·§65, DECISIONS D-038, 이 문서다.
- 전후: 속도 보정 상한 부족을 근본 원인으로 단정했던 설명을 철회했다. 무부하 정상 추종/접지 정체, 접촉 폭 영향, 질량 증대·유한 force drive·직접 토크 PI 후보 미통과를 확인했다.
- 운영/실물 영향: 이번 진단은 운영 소스·USD·설정 및 공통/실물 변경 없음. 사용자 확인 결과 공식 공개 자료에 필요한 질량/감속비/출력축 토크 사양 없음. PI 상한 확대, 타이어 폭 축소, 임의 질량/토크 변경은 운영에 반영하지 않았다.
- 검증/복원: 실제 Isaac CPU60Hz 격리 시험의 관절 위치 차분·차체 회전·정지 구간 집계. 전체 Nav2/실물 회귀는 미실행. 시험 출력과 문서만 있어 운영 복원 대상 없음. 미커밋/원격 미반영.

## HARVEST-105-20261016 — 실제 정체 원인 분리

- 요청/범위: 사용자105 발생 당시 움직이지 못한 원인 확인 요청. 운영 소스·설정·공통 코드·자산 수정 없음. 기존 프로세스 종료 이후 별도 포트·scene으로 접촉/구동 비교 시험만 실행했다.
- 결과: 실제 명령 수신 정상, 바퀴 PI 보정±2rad/s 포화와 차체 정체 확인. 실패 자세에서 동일 +0.05rad/s 10초 입력에 기본0.919°/보정 상한20 시험26.448° 회전. 내부 충돌 제거·GPU·drive gain/type 변경만으로는 미해결. 마찰 감소/solver 반복 증가로 개선돼 현행 접지·구동 보정 조합의 한계로 확인. 운영 상한20 적용은 하지 않았다.
- 검증/제약: 유효8개 격리 시험의14sim초 trace/contact와 실제 수신/휠/차체 로그 집계. 최초 마찰 시험은 instance 편집 오류로 제외하고v2로 재시험. 종료 지연으로 소유한 시험 프로세스만SIGTERM 정리. 전체 Nav2 재주행/실물 미실행. 수치와 다음 검증은 PROJECT_STATE §64.
- 파일/복원: `sim/runs/harvest_105_20261016/`의 진단 산출물, PROJECT_STATE §64 및 이 기록만 추가. 운영 복원 대상 없음. 문서·결과 미커밋, 원격 미반영.


## TEACHER60-ACTION-20261016 — 수확 Action과 팔 실행/국소 물리 연결 확인

- 승인: 사용자 수확 액션에60Hz Teacher 팔 움직임 연결, 향후 카메라 정책 교체, 근처 과실만 물리 적용 요청.
- 대상: `farm_sim_runtime/{fleet_config.py,launch/harvest.launch.py}`, `sim/tools/check_teacher_action.py`, `check_teacher_harvest.py`, sim 액션 설정/통신 시험과 실행 문서. 기존 공통 `HarvestMission`/`ArmActionClient` 및 sim 팔 실행 연결을 재사용하며 공통·실물 소스 변경 없음.
- 전후: 기존 ARRIVAL_THEN_ARM/내부 팔 Action 기본값은 유지하고 팔 OFF·endpoint 불일치·국소 물리 OFF를 시작 전에 거부한다. 미래 카메라 모델 교체는 관측/정책/대상 선정 어댑터 경계로 명시하며 새 추상화나 Student 대역을 넣지 않는다.
- 검증: 실제 ROS→UDP→Isaac로2개 적재·물리 복귀·접힘·정지 및 ROS SUCCESS/2개 수량 확인. 활성 과실0→4→2/전체288. 취소 시험 상세와 로그는 [PROJECT_STATE §63](../../docs/PROJECT_STATE.md#63-수확-action의60hz-teacher-팔-실행과-주변-과실-물리--2026-10-16). 관련 최종62개, sim3패키지 build PASS. 전개 중 취소는 실제 정지/CANCELED 확인, 접촉 중 취소는 CANCEL_UNCONFIRMED로 미해결. 외부 주행→팔 호출은 단위시험, 이번 실제 Nav2 미실행.3개 밀집 복귀 문제는 미해결.
- 복원/영향: 이번 사전검사와 검증 도구/문서 변경만 역적용하면 §62 상태다. 이전60Hz 모델/정책 통합을 되돌리지 않는다. 공통·실물 영향 없음. 새 launch는 재시작 필요. 미커밋·원격 미반영.

## TEACHER60-R2-20261016 — 60Hz Teacher 통합,480Hz 폐기

- 승인: 사용자 “그렇게 적용하고480hz는 폐기하자”. 기준 `7b0e1a4` 위 미커밋 작업. sim 전용 변경이며 공통·실물 파일 변경 없음.
- 대상: `assets/robotarm_teacher/`, `assets/robots/harvest_physics/teacher_arm_reference.*`, sim config5개, `farm_sim_devices`의 Teacher/줄기/장치/세션과 `_teacher_vendor`, runtime 물리 스케줄/자산/UI/진단, 해당 시험·fixture·import/replay 도구 및 실행 문서. 이전4개 체크포인트·staged_teacher/kernel 제거.
- 전후: 기존480Hz/response5·분리 정책 실행을 전달60Hz r2의 JIT+원본 단계 제어/response6/마찰2.2/단일 바닥/실제 속도 제한으로 교체. 유휴·수확60Hz/정책20Hz/렌더30Hz. 낮은순·물리 복귀 후 다음 목표, 적재 보존. SDK qd 잔류에 대한 정지 판정은 실측 q 변화·hold 오차·bounded qd를 함께 검사한다.
- 검증: 전달 SHA/내부1438개 일치, 독립 GPU26/32 재현,239tick 원본 명령 비교 최종목표 최대4.06e-6rad. 농장 단일1/1·연속2/2 적재/복귀/접힘/정지 PASS.3개 배치는 첫 적재 후 복귀 중 비목표 분리로 안전 정지(1개 적재/뒤2개 미시도),3개 순차 성공은 미완료. 상세와 최초 fixture 불일치 기록은 [PROJECT_STATE §62](../../docs/PROJECT_STATE.md#62-60hz-teacher-r2-적용과480hz-폐기--2026-10-16) 참조. 관련108개+84subtests, 추가 과실/배치17개+9subtests, USD 팔11개·과실19개 PASS. sim3패키지 빌드 PASS. 로그 `sim/runs/teacher60/`.
- 실물 영향/한계: 직접 영향 없음. 공유 Isaac scene 시간은60Hz로 고정되므로 기존 주행 사용자 확인과 이번 주기 변경 후 전체 연계 재검증을 구분한다. Student·실물·전체 Nav2 연계·실측 분리력 대응은 미검증. 기존 실행 세션은 유지했고 재시작이 필요하다.
- 복원/전달: sim 소스·자산·설정을 기준 커밋 버전으로 함께 복원 후3패키지 재빌드. 새 모델과480Hz를 혼용하지 않는다. 변경 파일과 삭제 목록만 담은 `sim/runs/teacher60/teacher60_changes.tar.gz` 및 패치 적용 방법은 같은 디렉터리 `PATCH_README.txt`. 현재 workspace에는 이미 적용했으므로 재적용 불필요. commit/push 없음.

## HARVEST-PROGRESS-AUDIT-20261014 — 최근 수확 주행 두 건 실패 진단 (미해결)

- 요청: 최근 수확 주행 중 제자리회전 후 ABORTED 원인 확인 및 현재 작업 커밋·푸시. 운영 코드·설정 변경이나 추가 주행 없이 기존 로그를 대조했다.
- 대상: `smoke_33b0484b8905`(16:41:21 KST), `smoke_48ad6a58d594`(16:50:29 KST). 두 건 모두 목표 (-6.015, 3.5278)로 WINDOW_MOVE 중 Nav2 `105: Failed to make progress`. 장치 세션은 각각 `4f43c6d8925a4201b06a6051bb44d861`, `c4518e851e42419897b6c52d236b6312`; 원본은 로컬 `sim/runs/drive_diagnostics/<session>/harvest_01.jsonl` 및 `sim/runs/harvest_motion/`에 있다(실행 로그는 Git 제외).
- 확인: 목적지 약 3.7m 앞, 실제 위치 x≈-6.02/y≈7.21에서 두 번 모두 정체했다. 두 번째 주행 sim 185.388초에 전진 0.1m/s·회전 -0.00372rad/s 명령, 좌우 바퀴 목표 약 -1.2rad/s였으나 측정 오른쪽 +0.468/왼쪽 -1.876rad/s. 제자리 보정 명령보다 실제 차체 방향 이탈이 먼저이며, 이후 진행 검사(10cm/20 ROS초) 실패로 중단됐다. 도착 판정/다음 주행 시작 조건의 실패가 아니다.
- 태그: 첫 실패 Goal 중 보정 요청 없음. 두 번째 마지막 태그 보정은 sim≈181.02초, 물리 방향 이탈은 ≈184.9초 이후. 태그 보정이 직접 회전을 유발했다는 근거는 없다.
- 미확정: 반복 위치의 물리적 접촉·걸림 또는 구동/물리 응답 이상을 의심하나, 접촉 대상·힘이 기록되지 않아 특정 충돌이나 시뮬 전용 결함으로 확정하지 않는다. 다음 검증은 해당 위치의 접촉 쌍/힘·바퀴 구동 힘을 동시 기록하는 재현 시험이다. 기존 0.313/0.35 성공 시험은 이 위치를 지나지 않아 이번 문제를 검증하지 못했다.
- 실물 영향/복원: 이번 추가는 진단 기록뿐이며 주행 동작 변경 없음. 이 항목 삭제로 문서만 복원 가능. 본 커밋은 누적 통합 작업의 체크포인트이며 수확 실패 해결 완료를 뜻하지 않는다.

## SHARED-NAVIGATION-CODE-20261014 — 공통 구현 한 벌과 변경 가능한 설정

- 승인: 사용자 “똑바로 통합해”와 후속 “같은 코드를 … 동일한 파일”, “설정값은 … 바꿀 수 있어야”, “sim … 전용 파일만” 지시. 초기 편집의 설정 override 금지를 제거했다. 공통/실물/시뮬 연결 변경 범위이며 기존 미커밋 작업을 보존했다.
- 공통 실행: `farm_navigation/configuration.py`의 설정 병합/공통 Nav2 로딩, `harvest_robot/configuration.py`의 수확 기본값 로딩, `farm_tag_localization/{launch_support,ros_capture,detection}.py`의 태그 연결/기록/검출 변환을 양쪽에서 호출한다. sim 태그 구현은 공통 import wrapper만 남긴다. 실물 USB 도구도 공통 태그 ID/크기/검출 override 경로를 사용한다. 수확 태그 구역 신호는 공통 단계 callback으로 전달한다.
- 데이터: `robot/config/navigation/`과 `robot/config/localization/common_observation_model.json`을 한 원본으로 참조한다. 기존 sim/real Nav2 파일은 해당 참조와 환경 데이터, 필요한 `overrides`만 관리한다. 공통 기본값 변경은 양쪽에 반영되며 환경별 수치 변경도 허용한다. BT/기존 모델 경로는 링크로 호환한다. 지도 생성기는 로컬 튜닝값을 삭제하지 않고, 실물 시험 manifest는 참조한 공통 파일까지 기록한다.
- 기본값 영향: 수확 RPP/SimpleGoalChecker 및 끝점 선분연장을 전달 `bf10fcd` 기준으로 정렬했다. 4cm/2.5°·0.10m/s·CLOSED_LOOP·진행20ROS초·Goal300wall초가 공통 기본값이다. 이전 실험 Settling/Stopped 소스는 보존하지만 기본 선택에서 제외했다. 종료 잔차 비차단(D-029)과 예찰 RPP.stateful=false는 유지한다. CPU 물리·휠 PI·센서 교정은 이번에 바꾸지 않았다.
- 검증: 공통4/sim3 패키지 빌드, 주행20·수확90·태그80·sim 통합32·launch9 검사 PASS. 추가 관련 fixture41개 및 경로371개 PASS(일부 시험은 앞 검사와 중복). 별도 real/sim 셸에서 주요9개 모듈의 실제 원본 파일 경로가 동일함을 확인했다. CPU/GUI/RViz/카메라3개/태그ON 전체 실행 결과는 PROJECT_STATE §52와 [검증 JSON](changes/SHARED_NAVIGATION_CODE_20261014.json)에 기록한다.
- 한계/적용: 실물 PiCam 자료 미확보를 configured:false로 명시했고 실제 모터 펌웨어/응답 동등성은 미검증이다. 실물 주행/배포는 하지 않았다. 사용 중인 팔OFF smoke 프로파일도 공통 참조로 갱신했다. 소스/설정 적용에는 launch 재시작이 필요하다. 이번 참조·로더·호출 변경을 함께 역적용해 복원하며 다른 누적 변경은 유지한다. commit/push 없음.


## SIM-REAL-NAVIGATION-AUDIT-20261014 — 추가 수정 전 동등성 감사

- 사용자 실물/시뮬 차이 검증 요청. 운영 코드·설정 수정/재주행 없이 실제 선택 프로파일·공통 호출·전달 이력·최신 실패 로그를 대조했다. [감사 JSON](changes/NAVIGATION_SIM_REAL_AUDIT_20261014.json), PROJECT_STATE §51에 근거·값·한계를 기록했다.
- 공통 구현 사용과 동작 일치를 혼동한 설명을 정정한다. 수확 도착/새 출발/진도/timeout/끝점 추종/속도/smoother 차이, 전달본의 진입·작업 끝점 정책 미반영, 실물 예찰 기본 태그 연결 미완료를 확인했다. 하위 바퀴PI도 공유 구현이 아니며 실물 응답 정합 미검증이다. 필요한 지도·장치 차이로 이 정책 차이를 정당화하지 않는다.
- 최신 실행은 첫 진입Goal에서 회전 지속 후 취소, 태그보정0회. 직전 작업점 도착 수정과 다른 단계이며 이번에 원인 확정/수정 완료로 기록하지 않는다. 기존 각 성공 기록은 유지하되 반복 신뢰성/실물 검증의 증거로 확대하지 않는다.
- 이번 대상은 감사 JSON/현행 문서뿐이며 문서 추가만 역적용 가능하다. 기존 미커밋 작업 보존, commit/push 없음.

## SIM-HARVEST-ARRIVAL-STATE-20261014 — 작업 도착 판정을 실물과 일치

- 사용자 수확0.313 도착 회전 반복 보고 및 기존 원인 확인·조치·CPU 검증 지시에 따른 시뮬 설정 수정. 원본은 SECTION_APPROACH 성공 뒤 WINDOW_MOVE에서 전진0/±0.06rad/s 회전을 지속하다 사용자 취소됐다. 태그 요청 직전 map XY11.34mm→보정 후26.47mm로15mm 도착 범위를 벗어났다.
- 대상: `sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml`의 기본 SimpleGoalChecker.stateful=false→true. RPP의 위치 도착 기억과 완료 판정을 맞춘다. 실물 vicpinky 설정은 이미true이므로 수정하지 않았다. 위치 도착 확인 후 방향 정렬을 마치며 새 Goal은 이력을 초기화한다. 진입 전용 Stopped checker·허용 수치·공통 코드/PID·물성·센서·timeout은 유지한다. 작업·이탈의 기본 checker에 적용되며 출발 차단/자동 뒤돌기 추가 없음.
- 직접 CPU/태그ON/카메라3개/GUI/RViz 시험:0.313→0.35 두 Goal 모두SUCCESS, 두 번째는 재진입 없이SECTION_RESUME→WINDOW_MOVE, 태그 보정11회. 정지 후 map 거리16.20/15.48mm, 방향0.411/1.192°. 예찰 서버는 정차했으며 예찰 미션 재실행·실물·16구역·장시간 반복은 미검증이다.
- 검사: 관련 Python20개 PASS, 설치 SimpleGoalChecker 직접 재생7 assertions PASS, config 빌드/소스·설치 일치. 전후 YAML mapping 차이는 stateful 한 항목뿐이다. [검증 JSON](changes/HARVEST_ARRIVAL_STATE_FIX_20261014.json), PROJECT_STATE §50/D-031 및 `sim/runs/harvest_arrival_fix_20261014/` 참고.
- 실행/복원: 기존 및 시험 런치 종료, CPU 런치 재시작 필요. 종료 중 Isaac SIGTERM/예찰 detector -11은 미션 성공과 별도로 기록했다. 이번 stateful 한 항목/주석만 역적용해 복원하며 다른 미커밋 작업은 보존한다. 문서 갱신, commit/push 없음.

## SIM-SCOUT-PROGRESS-FIX-20261014 — 예찰 도착 상태 고정 수정

- 승인: 사용자 “원인 확인 - 조치 - 보고”. CPU에서105를 재현하고 실물·시뮬 공통 RPP 동작을 최소 수정했다. 대상은 `sim/ros_ws/src/farm_sim_config/config/nav2_scout.yaml`, `robot/config/robots/burger/nav2.yaml`의 RPP.stateful=false 및 공통 `farm_nav2_controller/test/test_settling_controller.cpp`의 대조시험2개다.
- 전후: 한번 XY 범위에 들어가면 밖으로 나가도 회전/전진0 유지 → 현재 위치가 밖이면 경로 추종 재개. CPU 재현은 태그 적용 전에도 발생했다. 따라서 태그만의 오류라는 설명은 하지 않는다. 도착/진행 허용치·물리·PI·태그·수확 프로파일·종료 잔차 비차단 정책은 변경하지 않았다.
- 직접 Isaac 검증: CPU/태그ON/카메라3개/RViz/GUI 동일 조건, 원래 station 배치. 수정 전 첫 관측에서105/ABORTED, 수정 후SEC01 5개 관측 전체SUCCESS/SUCCEEDED 및 태그 보정129회. 전후 각1회이며 실물 배포/주행·전체16구역·장시간 반복은 미실행이다. 수정 후 정지 잔여 위치25.13~40.32mm는 그대로 기록하며 정밀도 인증으로 확대하지 않는다.
- 오프라인: 설치 RPP 직접 회귀 포함 C++12개+관련 Python14개=26개 PASS. 공통 controller/시뮬config 빌드 PASS, 소스/설치config 일치, 수정 전 YAML 대비 RPP 한 항목만 변경 확인. [검증 JSON](changes/SCOUT_PROGRESS_FIX_20261014.json), PROJECT_STATE §49/D-030 및 `sim/runs/scout_progress_fix_20261014/` 참고.
- 적용/복원: 기존 실패 런치와 시험은 종료했다. CPU 런치를 재시작해야 새 설정을 읽는다. 실물 설정 로컬 반영, 실제 장치 검증은 별도다. 두 RPP 설정 추가·신규 시험만 역적용하며 기존 미커밋 변경은 보존한다. commit/push 없음.

## SIM-SCOUT-PROGRESS-20261014 — 예찰 Nav2 105 로그 조사

- 사용자 로그 확인 요청. CPU/태그ON/RVizON 실행의 SEC01 세 번째 목표에서 Nav2 FAILED_TO_MAKE_PROGRESS(105)를 확인했다. 종료 오차 추가 검사 이전의 실패다.
- 약7.4sim초 동안 전진 명령0·실제 위치 변화0.0183mm, map 추정은 목표에서36.64~54.36mm로 도착3cm 밖이었다. 실행 중 RPP.stateful=true와 progress10cm/10초를 읽기 전용 확인했다. 위치 보정 후 RPP의 XY 도착 상태 고정이 추종 재개를 막는 조건이 가장 유력하지만 내부 latch는 직접 기록되지 않았다.
- 예찰은 기존 RPP이며 수확 진입 plugin을 사용하지 않는다. CPU만의 문제/태그 오차/저속 물리 기여는 아직 미분리다. 운영 코드·파라미터 변경, 새 주행/재현 시험은 하지 않았다. 대상은 분석 JSON과 PROJECT_STATE §48뿐이며 [증거](changes/SCOUT_PROGRESS_FAILURE_20261014.json)에 세부값을 남겼다. 문서 변경만 역적용 가능, commit/push 없음.

## SIM-ARRIVAL-GATE-REMOVAL-20261014 — 종료 잔여 오차로 다음 이동을 차단하지 않음

- 요청/승인: 사용자 “어제 작업종료 오차로인해 다음주행 시작조건 막는거 빼라고했잖아”. 이전 추가 오차 검사 유지 판단을 정정한다(D-029, PROJECT_STATE §47).
- 대상/전후: 공통 `farm_navigation/navigator.py`의 정지 후 도착·재측정·진입·이탈 오차 초과 4개 예외를 경고로 바꾼다. 측정값/`accepted=false`는 그대로 기록하고 다음 이동 잠금을 남기지 않는다. Nav2 실패·정지 미확인·TF 오류는 기존대로 실패다. 현재 예찰·수확, 실물·시뮬 공통 경로에 반영한다. 제동 개선·물성·허용 수치와 새 경로 검사는 변경하지 않았다.
- 검사: `sim/tests/test_recorded_arrival_overshoot.py`와 `test_parallel_approach.py`에서 오차 기록·후속 요청·중간 단계 진행 및 실제 실패 대조를 검증한다. CPU 26.82mm 기록에서 실제 수확 단계기/작업 경로 생성기로 다음 전방 30cm Window가 재진입 없이 실행됐다. 같은 이전 목표 재시도와 다음 목표 이동을 구분하며 별도 종단 제어가 필수라는 이전 설명은 철회한다.
- 결과: 기록 재생/평행 접근 11개 + 공통14개 + 수확 단계18개 =43개 PASS, farm_navigation 빌드 및 수정 소스 런타임 import 확인. Isaac/실물 재주행은 미실행이며 과거 실제 실패 결과는 그대로 보존한다. 로그는 `sim/runs/arrival_gate_removal_20261014/`.
- 적용/복원: ROS 런치 재시작 필요. 해당 Navigator 수정 전 백업/이번 diff만 복원하고 다른 미커밋 변경은 유지한다. commit/push 없음.

## SIM-STOPPED-ARRIVAL-20261014 — 공통 진입 정지 제어와 도착 판정 수정

- 요청/승인: 사용자 “아니그래서 어떻게 조치할거야 일단 해결은 해야될거아니야”에 따라 D-027 개선 실행. 시뮬·실물의 같은 공통 주행 제어를 수정하며 물성/PI/최종 허용치는 유지한다. 실제 실물 배포·주행은 미실행이다.
- 변경: 공통 farm_nav2_controller RPP subclass는 기존 경로·충돌 검사 후 최종 XY/yaw 안에서0속도 명령을 내린다. farm_navigation은 Stopped checker 사전검사와 속도 masking 검증을 지원한다. harvest_robot/node.py의 optional approach_goal_checker_id로 진입에만 새 controller/checker를 선택하고 작업·이탈은 기존 설정을 보존한다. sim nav2_harvest.yaml/harvest_task.json, real vicpinky/nav2.yaml/harvest_real.json, farm_bringup 의존성 및 check_runtime.py를 연결했다.
- 호환/검사: 복수 checker의 일반 NavigateToPose/ThroughPoses 호환을 위해 기본 BT의 기존 일반 checker ID만 명시한 환경별 XML4개와 상대경로 해석을 추가했다. sim/tests 및 기존 진입/작업 테스트, 공통 C++ 단위검사를 갱신했다. 기존 default설정 생략 동작은 유지한다.
- 전후: 회전 중 목표각 통과 성공 → 목표 자세 안에서 제동 명령 → 속도까지 검사 → 기존0.8초 정지·최종 pose 검사. 설정만 바꾼 후보는 진입 또는 작업 회전 반복이 재발하여 폐기했다. 좁은 작업 구간에 새로운 XY 재접근/복구 회전을 추가하지 않았다.
- Isaac 직접 검증: 최종 구성 CPU/GPU 각1회 진입 정렬 완료; 전체 HarvestTask 결과는 다음과 같다. cpu_brake_01 전체결과 FAILED: 진입 6.85mm/0.279°, 작업 도착 26.82mm/0.426°; gpu_brake_01 전체결과 SUCCESS: 진입 6.87mm/0.221°, 작업 도착 11.31mm/0.778°. 팔OFF/expected_count0, 원래 카메라·태그·GUI 조건 유지. 후보의 성공·취소·무효 배치 기록도 모두 JSON에 구분 보존한다. [검증 JSON](changes/STOPPED_ARRIVAL_FIX_20261014.json), PROJECT_STATE §46 참고.
- 남은 문제: CPU 작업 지점은 Nav2 종료 뒤26.82mm map 오차로 최종검사가 거절했다. 그 사이 태그 보정도 적용됐으나 요청 변화는진행축각0.3mm수준이어서 전체 원인으로 단정하지 않는다. 안전한 기존 직선 재접근 검사도 목표방향9.777°로 거절하므로 자동 재시도하지 않는다. 진입 과회전과 별도인 작업 종단제어 문제이며 전체 미션 완전 해결로 기록하지 않는다.
- 검증: 관련86개 PASS, 정적 runtime5그룹 PASS, 공통/시뮬5패키지 빌드 PASS. 전체 geometry의 기존 연결선48 subcase 실패는 HEAD 시험에서도 동일하다. 실물 동작·모든 구간·장시간 반복·팔 수확은 미검증이며 목표 범위 밖의 원본 RPP/시뮬 저속 물리 응답 원인을 해결했다고 주장하지 않는다.
- 실물 영향/복원: 로컬 실물 프로파일도 새 공통 package가 필요하므로 실물 아키텍처에서 소스 빌드해야 한다. sim/runs/rotation_fix_20261014/*before 및 before_* 백업/이번 diff로만 복원하고 기존 미커밋 작업은 보존한다. commit/push 없음.

## SIM-ARRIVAL-REGRESSION-20261014 — 공통 주행 검증 방향과 실패 조건 보존

- 요청/범위: 사용자 “그래 그 방향성으로 가야지”. 시뮬 모델 오류와 실물에서도 가능한 공통 제어 실패를 분리하고, 성공을 위한 시뮬 튜닝으로 실패를 가리지 않는 D-027을 기록했다. 운영 코드/설정 변경 없음.
- 변경: `sim/tests/test_recorded_arrival_overshoot.py`가 기존CPU/GPU 성공3·실패3의 실제 도착 좌표를 공통 Navigator 종료 경계에 재생한다. 정지 확인 뒤 같은 시각 pose 사용, 과회전 거절/성공 대조군 유지, 실패 후 새 이동 우회 차단을 확인한다. 기존 증거와 허용치는 그대로다.
- 검증: ROS Jazzy 환경에서 `python3 -m unittest sim.tests.test_recorded_arrival_overshoot -v` 1검사/6기록조건 PASS. I/O를 대체한 오프라인 회귀이며 물리/Nav2 재실행·과회전 수정·실물 검증이 아니다. 회전 공간 검증 없는 공통 자동 재정렬은 도입하지 않았다.
- 실물 영향/복원: 실물·공통 실행 코드 및 USD/PI 변경 없음. 시험 제거만으로 되돌릴 수 있으며 기존 실패 증거·다른 미커밋 변경은 보존한다. 상세 PROJECT_STATE §45. commit/push 없음.

## SIM-ROTATION-ROOT-CAUSE-20261014 — 진입 정렬 과회전 분석

- 구분/요청: 사용자 “6도 이상의 오차 … 원인 분석”. 분석 문서·격리 시험 산출물만 추가. 운영 코드/설정·USD·허용치 변경 없음. 기존 main/62a80ed 미커밋 변경 보존, commit/push 없음.
- 결과: 6~7°는 실제 차체 과회전이며 최종2.865° 허용치 초과를 상위 도착 검사가 정상 차단한다. 저속 구동 응답 저하→시뮬 PI 누적→회전 속도 상승→측정 속도를 따르는 RPP 감속 제한→회전 중 Nav2 순간 도착 판정→제동 중 추가 회전의 흐름을 기존 실패3회에서 확인했다. GPU 실패는 첫 기록된0명령 뒤에도 최대4.77° 더 회전했다. 정확한 물성/접촉 원인은 미확정이며 정지 후 PI 적분 잔류는 아니다.
- 격리 검증: ROS/Nav2 없이−0.06rad/s를8sim초 명령했다. 기본 스테이션−90°에서 CPU23.57°/GPU26.41°, 실패 방향−71.03°에서는 진입 위치CPU0.80°/스테이션CPU0.69° 회전, 두 후자는 PI 적분 상한2.0 도달. 방향에 따른 시뮬 구동 응답 차이를 확인했다. 각1회이며 전체 Nav2 실패 재현 시험은 아니다. PI 제거 시 정상 방향에서도 CPU1.61°/GPU0.09°에 그쳐 단순 제거는 해결책이 아니다. 모든6조건14sim초 계산 완료, app.close 대기로 종료−15, 시험 프로세스 잔류 없음.
- 원인 범위: 명백한 cmd 월드축/로봇축 혼동 없음. 기존6회 정지 map/world yaw 차이≤0.184°, 실패 태그 적용0회. CPU/GPU 선택이나 태그 변경만으로 해결할 근거 없음. 다음은 방향별 바퀴 구동력·접촉력 계측, 시뮬 PI 포화/제동 수정 검증 후 동일 Nav2 반복 시험이다. 허용치를 풀지 않는다.
- 근거/복원: [분석 요약](changes/ROTATION_OVERSHOOT_ANALYSIS_20261014.json), [추적 그래프](changes/ROTATION_OVERSHOOT_20261014.png), `sim/runs/rotation_root_cause_20261014/`. 상세는 `docs/PROJECT_STATE.md` §44. 문서/JSON 검증 완료; 실행 코드 변경이 없어 복원할 운영 변경 없음.

## SIM-DOC-20261002-001 — 인수 검토 및 작업 규칙 기록

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 문서·작업 규칙. 실행 코드·설정 변경 없음 |
| 기준 자료 | 사용자 첨부 `farm_project.zip`, `SUMMARY_인수인계서.md`, 프로젝트 기획·시뮬레이션 파트 문서 |
| 승인 근거 | 이번 사용자 요청: 변경사항 검토, 시뮬 전용 변경의 폴더 분리, 공통 코드 사전 확인 및 변경 기록 |
| 대상 파일 | `AGENTS.md`에 규칙 추가, `sim/AGENTS.md`, 이 문서, `sim/docs/INTEGRATION_REVIEW_20261002.md` 추가 |
| 이유 | 실물 담당자 소스를 기준으로 시뮬 통합을 시작하면서 실물·공통 코드에 대한 영향과 승인 범위를 명확히 하기 위함 |
| 변경 전후 | 기존 구현 합의를 보존하고 시뮬 수정 위치, 공통 변경 승인, 변경 기록 기준을 추가 |
| 실물 영향 | 실행 소스·설정·모델·메시지·실물 자산 변경 없음 |
| 직접 검증 | 기존 오프라인 시험 44개 통과. 두 환경 설정 로드 성공. 시뮬 그래프 128노드/112엣지/16개 약연결 성분, 실물 18노드/40엣지/1개 약연결 성분 확인 |
| 미실행 | ROS 2 빌드·통신, 새 State 흐름 전체 시험, VisionRuntime 시험, YOLO 실행, Isaac Sim 통합, 실물 주행 |
| 복원 | `AGENTS.md`의 이번 추가 절만 제거하고 이번에 추가한 `sim/AGENTS.md`와 문서 2개를 제거. 다른 변경이 누적된 뒤에는 해당 기록의 변경분만 되돌릴 것 |

원본 ZIP SHA-256:

`ca092228082a9e47b6fa79de8878408923f82d9ca9dbfa328811811a65728b24`

공통 실행 코드 수정 승인을 받은 항목: 없음.

## SIM-CONFIG-20261002-002 — 시뮬 설정 실제 분리

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 시뮬 설정·진입점·출력 경로. 공통 ROS 실행 소스 및 실물 설정 변경 없음 |
| 승인 근거 | 사용자 후속 요청: “시뮬레이션 설정은 sim 폴더안에 있어야돼. 명확히 분리해” |
| 승인 범위 해석 | 시뮬 전용 설정 이동, 필요한 기존 경로 참조 갱신. 공통 업무 로직 변경 승인으로 확대하지 않음 |
| 설정 이동 | `robot/config/vision/scout.json` → `sim/ros_ws/src/farm_sim_config/config/scout_vision.json`. 이전 경로의 설정 파일·링크는 제거 |
| 환경 선택 | `scout_survey.json`이 새 영상 설정을 참조. `scout_runtime.yaml`에 시뮬 `rviz_config` 추가 |
| RViz 분리 | `sim/.../farm_sim_config/config/scout.rviz` 추가. `sim/.../farm_sim_runtime/launch/scout.launch.py`에서 공통 bringup과 별도로 선택하여 한 번 실행 |
| 비전 진입점 | `sim/tools/run_scout_vision.py`에서 기본 설정 선택. 기존 루트 스크립트는 인자를 그대로 전달하는 호환 진입점으로 변경 |
| 외부 참조 갱신 | `scripts/run_scout_vision.py`, `tests/test_scout_survey.py`만 시뮬 외부 실행/시험 파일로 변경. 기존 시험은 survey의 `vision_config`를 읽도록 수정 |
| 출력 분리 | 예찰·단독 비전·합성 데이터 기본 출력을 각각 `sim/runs/scout_survey`, `sim/runs/scout_vision`, `sim/runs/scout_dataset`으로 변경 |
| 평가 도구 | `--survey latest`는 시뮬 결과 폴더만 검색. 기존 결과는 명시 경로로 읽을 수 있음 |
| 패키징 | 새 설정·launch는 기존 glob으로 설치. 시뮬 runtime의 실행 의존성만 추가 |
| 실물 영향 | `robot/ros_ws/src/`, 실물 설정·모델·센서 값·메시지·공통 알고리즘은 유지. 기존 실물 launch와 기존 결과 데이터도 유지 |
| 검증 | 기존 오프라인 44개 통과. sim/real 환경 로드 성공. 수치·ID·모델 선택·그래프 참조 보존. 공통 ROS/실물 설정/모델 124개 파일 원본 동일. 실행 객체를 대체한 launch 구성 4조건·외부 설정 거절 4조건, 비전 함수만 대체한 신·구 CLI 인자 전달 6조건 통과. 변경 Python 문법 및 패키지 XML 확인 |
| 미실행 | ROS 2 빌드 및 실제 launch, Isaac·YOLO·실물 실행 |
| 복원 | 적용 전 설정·진입점·시험·sim 패키지 파일로 되돌리고 이번 추가 파일만 제거. 기존 비전 설정은 `sim/runs/config_backups/`에서 복원 가능. 새 결과 폴더는 삭제하지 않음 |

추가/수정 파일의 상세 위치와 실행 명령은 `sim/README.md`를 참고한다. 기존 `INTEGRATION_REVIEW_20261002.md`는 변경 전 인수 검토 기록이며 현재 설정 위치는 이 변경 항목이 우선한다.

## 다음 변경 기록 양식

```text
변경 ID / 일자:
구분: 시뮬 전용 / 공통 / 실물 / 문서
상태: 제안 / 승인 대기 / 승인 완료 / 적용 완료 / 검증 완료
기준 버전: Git commit 또는 전달 파일 식별값
대상 파일:
변경 이유와 재현 조건:
구체적인 변경안 / 변경 전후 동작:
실물 영향:
시뮬 영향:
사용자 승인 일자·요청 내용·승인 범위:
적용 결과:
검증 명령·결과·미실행 범위:
시험 로그 / 보고서 경로:
되돌리는 방법:
```


## SIM-DATA-20261002-003 — 연결 경로·로봇 station 복원

- 승인 근거: 사용자 요청 “어제 업데이트한 경로 데이터 yaml … 경로끼리 연결, 각 로봇 station … sim 파트 데이터 다시”.
- 이유: 인수본에는 과거의 분리 그래프와 FOV 자동 관측 설정이 남아 있어 이후 업데이트한 연결·station·고정 촬영점 데이터가 누락돼 있었다.
- 대상: sim의 task.yaml, 연결 원본/역할별 GeoJSON, 원본 점유 지도, scout_survey/scout_patrol/scout_runtime/scout.json, 재생성·검증 도구, 문서와 작업 규칙. 상세 목록은 패치 ZIP에 포함된 파일 목록 기준.
- 출처: farm_scout_harvest_count_v0.8.5.zip의 최신 연결 데이터. 운송/선별장 용도는 기존 sim_route_design_v1 설계. 보관본 자체와 실제 git 커밋 비교는 구분한다.
- 변경 전후: 16개 분리 성분 → 연결 원본 227노드/516방향 엣지. BED_01~16/FOV 자동 관측 → SEC01~16/고정 관측점 80개. 예찰·수확 station 좌표·방향 복원, 운송/선별장 설계 좌표 복원(방향 미정).
- 호환: 공통 로더가 role 메타데이터를 읽지 않아 역할별 파생 그래프를 생성. 원본 베드 경계는 scout 파생 그래프의 기존 엣지를 분할해 보존. 공통 코드 복제나 변경 없음.
- 실물 영향: 이번 변경은 전부 sim/ 내부. 공통 코드·실물 설정·모델·USD 자산 변경 없음.
- 검증: 현재 공통 로더와 기하 계산/순찰 로더에서 16구역·80관측점 유효, 371개 역할별 경로 계산 통과. 원본 그래프/지도 동일, 원본 구역·베드·예찰/수확 station 동일, 227개 원본 노드의 지도 free 픽셀 확인.
- 미실행/유지: ROS/Isaac/colcon 미실행. station 자동 배치, AMCL station 초기화, FollowPath 전환, 수확/운송 실행부 연결은 미적용. 기존 navigate_to_pose 유지. 자동 station 복귀 없음.
- 복원: 패치 적용 전 백업 사용. 이번에 추가된 파일은 제거하고 기존 파일만 백업본으로 돌린다. sim/runs 결과는 보존한다.
- 보고: sim/docs/ROUTE_RESTORE_20261002.md 및 ROUTE_RESTORE_VALIDATION_20261002.json.


## SIM-RUNTIME-20261002-004 — Isaac 실행 대상 station 자동 배치

- 승인 근거: 사용자 “robot의 station 자동 배치는 isaacsim 실행용 코드에 포함”. FollowPath 설명 요청은 모드 전환 지시로 해석하지 않았다.
- 대상: sim runtime의 station_spawn.py/run_sim.py/scout.launch.py, scout.json, task.yaml, station_spawn.json, nav2_scout.yaml, 재생성·검증 도구, sim/tests/test_station_spawn.py 및 sim 문서.
- 변경 전후: USD 저장 위치에서 시작 → task 기반 station JSON의 예찰 station XY/yaw로 물리 시작 전 배치. 기존 body 높이·센서 상대 위치 유지. USD session layer만 사용하며 원본 저장 없음.
- 위치추정: AMCL 초기 pose를 같은 station 원본에서 생성. launch에서 서로 다르면 오류. 물리 reset 후 배치 검증. 주행 중 정답 pose 주입 없음.
- 범위: 현재 단일 예찰 런타임에 적용. 수확/운송 실행부 생성·구동 및 FollowPath 전환은 미적용. 공통 코드·실물 설정·USD 자산 변경 없음.
- 검증: 좌표/설정 시험 6개, launch 구성 4개 및 AMCL 불일치 거절 검사 통과. 경로 371개 검사 통과. nav2는 초기 pose 외 설정 값 유지.
- 한계: ROS/Isaac/USD API 실실행, 물리 구동, colcon 빌드 미검증.
- 복원: 이전 sim 파일 백업을 복원하고 새 station_spawn.py/json 및 시험 파일을 제거한다. sim/runs 결과는 보존. 배치만 끄려면 station_spawn.enabled=false와 실제 시작 위치의 AMCL 초기 pose를 함께 맞춘다.
- 상세: sim/docs/STATION_SPAWN_20261002.md.


## SIM-NAV-20261002-005 — 실물과 동일한 FollowPath/RPP 설정

- 승인 근거: 사용자 “시뮬설정도 실제랑 동일하게 세팅해”.
- 대상: sim의 scout_runtime.yaml, nav2_scout.yaml, task.yaml, 재생성된 scout_survey.json, 문서·작업 규칙. 공통 코드/실물 파일 변경 없음.
- 전후: navigate_to_pose → follow_path, controller_id FollowPath → RPP, goal checker general_goal_checker → goal_checker. 실물과 navigation 파라미터 동일(base_frame 제외).
- 제어 설정: 인수본 실물의 controller_server·velocity_smoother 값을 적용(use_sim_time/odom_topic 제외). controller 10Hz, RPP 0.15m/s·lookahead 0.15m, goal 0.03m/0.05236rad, progress 0.1m/10s. local/global inflation도 RPP 비용 모델에 맞게 실물과 동일하게 설정.
- 유지: 시뮬 지도·graph·관측점·station, TF·센서·장치·시간, AMCL station 초기 pose, 로봇 반경/센서 costmap 레이어. 모든 Nav2 값을 무조건 복사한 것은 아님.
- 실행 동작: 공통 RouteGraph가 연결 그래프 경로를 계산하고 Nav2 FollowPath 액션에 controller_id=RPP로 전달한다. 교통 제어·자동 복귀·도킹 추가 없음.
- 검증: 양 환경 설정 로드, 주행값/선택 controller/goal/progress ID 일치, 공통 goal checker 검사 통과. 371개 경로 계산 및 station 시험 6개 통과. 이번 수정이 sim 내부로 한정됨을 파일 해시로 확인.
- 한계: ROS/Isaac 실주행·colcon 빌드 미실행. 인수본 설정과 동일하다는 의미이며 담당자의 현장 실행값은 별도 확인 대상.
- 원복: 적용 전 시뮬 설정 백업 복원. 주행 모드 한 줄만 바꾸면 제어 튜닝까지 원복되지는 않는다.
- 상세: FOLLOWPATH_ALIGNMENT_20261002.md, FOLLOWPATH_VALIDATION_20261002.json.


## LAUNCH-SPLIT-20261002-006 — 로봇/Isaac/RViz 독립 실행 및 시뮬 전체 실행

- 승인: 사용자 “그럼 그렇게 수정해 … 시뮬레이션용 전체실행 런치 … 만들어줘 … 실행 절차 … 작성”. 공통 launch 변경을 포함한 실행 구조 분리 승인으로 적용.
- 공통 대상: farm_bringup의 scout.launch.py, scout_navigation.launch.py, 새 rviz.launch.py, tests/test_launch_composition.py, 공통 실행 안내/루트 README/AGENTS.
- 시뮬 대상: sim 런타임의 scout/scout_devices launch, 새 isaac/all launch, setup.py의 launch 파일 설치 패턴, 안내 문서.
- 변경 전후: 로봇 launch에서 Isaac/RViz를 함께 시작 → 로봇 단독 기본은 장치+Nav2+예찰 서버, Isaac과 RViz는 독립 실행. 시뮬 all은 독립 launch 세 개를 조합.
- 실물 영향: 기존 survey=true 실행은 장치·Nav2·서버 구성 유지. RViz는 별도 실행. survey/navigation 기본값이 true로 변경됨. start_isaac/rviz=true는 명시적으로 이관 안내 오류. navigation 전용 sim 실행도 환경 프로파일을 선택하도록 보완.
- 유지: 실물 설정·공통 미션/FSM/주행 계산/메시지·USD 및 station 배치 구현 변경 없음. 수확/운송/관제 구현을 임의 추가하지 않음.
- 검증: launch 기록 객체 기반 9개 시험 통과. 시뮬 전체의 Isaac/어댑터/예찰서버/RViz 각 1개, 독립 실행 경계, 실물 장치 포함 및 Nav2/서버, 모드별 RViz 시간/TF, 옵션 및 잘못된 구형 옵션 거절 확인. 직접 ROS/Isaac 구동·실물·colcon 빌드는 미실행.
- 실행 안내: docs/RUN_GUIDE_20261002.md. 실물 담당자 변경표, 각 장비 실행, 시뮬 전체/세 터미널 실행, 시험 관제, 종료·재시작 범위, 다중 로봇 미구현 항목을 명시.
- 복원: 적용 전 공통/시뮬 launch와 setup.py 백업 복원. 새 launch·구성 시험·안내 파일 제거. 실행 결과는 삭제하지 않음.


## SIM-LAUNCH-20261002-007 — 활성 robot_venv의 비전 Python 자동 선택

- 사용자 확인: 비전 의존성이 robot_venv에 설치되어 있어 별도 vision_python 인자가 불필요해야 함.
- 대상: sim 런타임의 launch_environment.py, all/scout launch. 공통/실물 코드 변경 없음.
- 전후: 인자/환경변수 미지정 시 빈 경로 → FARM_VISION_PYTHON 우선, 없으면 VIRTUAL_ENV/bin/python, 활성 venv도 없으면 launch Python 사용. 명시적인 vision_python 인자는 계속 우선함.
- venv 심볼릭 링크는 resolve하지 않아 가상환경을 유지. 잘못된 활성 venv 경로는 명시적 오류.
- 검증: 우선순위 및 경로 선택 검사, 기존 launch 구성 시험 9개 통과. 실제 ROS/Isaac/추론 실행은 미검증.
- 원복: 이전 all/scout launch 복원 후 새 launch_environment.py 제거.

## HARVEST-SIM-20261002-008 — 수확 이동 Action 및 시뮬 bringup

- 상태: 사용자 승인 후 적용, 오프라인 검증 완료. ROS/Isaac 실실행 미검증.
- 승인 근거: 수확 코드/bringup·sim/real 구분·sim 내부 작성 요청과 후속 “action 추가해. 진행해도 돼”, “그렇게 result 보내면 됨”. 사전 제안한 공통 인터페이스 추가와 이동 완료/수확량 0 계약을 적용했다.
- 공통 대상: farm_interfaces/action/HarvestTask.action 신규, CMakeLists.txt 등록만. 기존 HarvestTask.msg 및 주행/예찰/실물 설정 유지.
- 시뮬 대상: farm_sim_harvest 신규 서버/미션/통신/상태/평가; runtime harvest launch/fleet 실행/all 조합/clock relay; harvest 자산/설정/지도 선택/RViz; 데이터 생성·검증·시험·안내.
- 전후: 수확 실행부 없음 → 같은 공통 Navigator와 harvest 역할 graph로 window XY/yaw 도착 후 SUCCESS/harvested_count=0. 팔 작업 없음. expected와 실제 USD pose의 과실 박스 판정은 별도 로그. real 장치 연결은 미구현 오류, 실물 가상 구동 대체 없음.
- 출처: 제공된 v0.8.5 수확 물리 자산/주행좌표 변환/시뮬 센서 및 GT 수집 부분만 이식. 예전 서버·관제·공통 로직은 복원하지 않음. 실제 팔 도달성 대신 기존 임시 박스이며 인수 후 보정 필요.
- 실행 영향: harvest=true일 때 두 로봇 포트·TF 분리 및 독립 clock 하나. scout 단독 기본 동작 유지. fleet scout profile이 중복 clock을 막음. 새 Action 사용자는 robot workspace 재빌드 필요.
- 검증: sim 단위/구성 20개, 기존 launch 9개, 기존 경로 371개, 수확 엣지 내부 목표 경로 48개 통과. 공통 변경 2개 외 모든 변경 sim 내부 확인. ROS/colcon/Isaac/실물 미실행.
- 수정 안내·실물 인수 경계·로그·원복: HARVEST_RUN_GUIDE_20261002.md. 적용 전 파일 백업 복원 및 신규 파일 제거 후 재빌드, sim/runs 결과 보존.

## HARVEST-COMMON-20261002-009 — 수확 서버의 공통 위치 정정

- 승인: 수확 서버와 bringup을 공통 위치로 옮기고 평가만 sim에 남기자는 구체적 제안에 대한 사용자 “그래임마 정신차려”.
- 이유: 008에서 수확 서버 전체를 sim 전용 패키지에 배치한 것은 동일 서버를 sim/real에서 공유하는 기존 합의에 맞지 않았다. 008의 서버 위치 설명은 이 항목으로 대체한다.
- 공통 변경: robot/ros_ws/src/harvest_robot 신규(Node/Communication/Mission/StateController/계약), farm_bringup/launch/harvest.launch.py 실제 조합 및 package.xml 의존성. 기존 farm_navigation과 HarvestTask 계약 유지.
- sim 변경: farm_sim_harvest는 audit_node/evaluation만 유지. 작업 설정과 평가 설정 분리, fleet 평가 경로 갱신, sim harvest launch가 공통 launch+평가를 조합. 이전 sim 서버 소스 5개 제거용 백업 이관 도구 추가.
- 전후: sim 서버가 평가 함수를 호출 → 공통 서버는 Action/주행 처리와 환경 독립 task_events 진단 발행만 담당, sim 평가 노드는 비동기 구독하여 비교 로그 생성. 서버에서 sim import/Isaac snapshot 접근/평가 대기 제거.
- 실물 영향: real 설정과 외부 드라이버가 있으면 devices=false로 같은 서버 실행 가능. 미구현 실물 장치 기본 분기는 오류. 실물 맵/드라이버/팔 작업을 가짜 구현하지 않음. 공통 workspace 재빌드 필요.
- 검증: 오프라인 31개, 기존 경로 371개, 수확 내부 좌표 경로 48개 통과. sim/real 동일 서버, 시간 선택, 평가 분리, 중복 launch 없음 확인. 실제 ROS/Isaac/colcon/실물 미실행.
- 전달/원복: HARVEST_COMMON_MIGRATION_20261002.md. 이전 수확 패치를 대체하는 합본 패치, 이관 도구로 옛 서버만 백업 후 제거. 결과 로그는 보존.

## SIM-FLEET-20261002-010 — Isaac fleet 진입점 누락 수정

- 증상: 17:09 실행 로그에서 Isaac Python이 시작 직후 exit 0으로 종료, OnProcessExit에 의해 모든 ROS 노드가 SIGINT로 종료됨.
- 원인: run_fleet.py에 main 함수는 있으나 직접 실행 시 호출하는 __main__ 진입점 누락. 기존 문법/launch 구성 검사는 함수 호출 여부를 검증하지 못했음.
- 대상: sim runtime/run_fleet.py, sim/tests/test_fleet_entrypoint.py, 이 변경 기록. 공통/실물 파일 변경 없음.
- 변경: 직접 실행 시 main() 호출 추가. 종료 연동은 그대로 유지.
- 검증: 수정 전 --help가 출력 없이 exit 0인 현상 재현. 수정 후 실제 subprocess --help에서 옵션 출력, 필수 인자 누락 시 exit 2 확인(2개 통과). Isaac 물리 구동은 해당 환경이 없어 미검증.
- 적용: 패치 압축 해제 후 sim workspace의 farm_sim_runtime 재빌드, 환경 다시 로드 후 기존 전체 실행 명령 사용.
- 원복: run_fleet.py 마지막 __main__ 블록과 새 시험 파일을 되돌림. 결과 데이터는 변경하지 않음.

## SIM-TF-20261002-011 — 카메라 없는 수확 로봇 상태 패킷 수락

- 증상: HarvestTask는 수락됐으나 harvest_01/base_footprint TF가 없어 NAVIGATION_FAILED.
- 원인: ros_adapter.valid가 고정 TF 3개를 강제. fleet 런타임은 카메라 없는 harvest에 base/link·lidar TF 2개를 전송하여 모든 패킷이 거절됐음. odom·scan·TF 발행에 도달하지 못함.
- 변경: camera.enabled에 따라 2/3개를 선택하고 설정의 부모/자식 프레임 쌍과 일치하는지 검사. 공통 서버·실물·Nav2 변경 없음.
- 검증: 실제 valid 메서드를 ROS 없이 실행, harvest 2개/scout 3개 수락 및 누락/다른 로봇 프레임 거절 4개 통과. ROS/Isaac 직접 실행 미검증.
- 적용: farm_sim_devices 재빌드 및 전체 launch 재시작. 확인: harvest_01/odom → harvest_01/base_footprint TF 출력.
- 복원: 이전 ros_adapter.py 복원 후 시뮬 패키지 재빌드. 시험 로그 데이터 유지.

## DRIVE-DIAG-20261006-012 — 수확 무응답 구동 진단

- 근거: cmd_vel 0.12m/s, wheel odom 약 0, 로봇 정지 및 Failed to make progress. 전달 경로/물리 구동 중 원인 미확정.
- 범위: sim runtime/run_fleet.py와 신규 drive_diagnostics.py. 공통/실물/게인/구동 제한 변경 없음. 앞선 main 호출 수정 포함.
- 변경: ROS→Isaac 수신 패킷과 gate 수락/거절 누적, 실제 적용 cmd, 공통 kinematics로 계산한 관절 목표, 관절 실측 속도/인덱스, 실제 pose를 1Hz로 기록. 적용된 USD 바퀴 drive 설정 기록.
- 산출: sim/runs/drive_diagnostics/<세션>/<robot_id>.jsonl 및 <robot_id>_setup.json. 목표 속도는 apply_action에 전달한 입력으로 계산한 값이며 PhysX 내부 target readback은 아님.
- 정적 검사: 제공 자산의 바퀴 stiffness=0, damping=625. 별도 자산의 검사이며 사용자 실행 중인 scene 적용 상태의 증명은 아님.
- 검증: 실제 common wheel_targets를 사용한 목표 rad/s, 수락/거절 카운터, JSON 출력/1Hz 제한, USD 관절 추출 검사 통과. Isaac 물리 실행 미검증. 근본 원인 수정 완료가 아닌 진단 계측 패치.
- 원복: 적용 전 run_fleet.py 복원, drive_diagnostics.py 제거 후 runtime 재빌드. 기록은 보존.



## DOC-HANDOFF-20261006-015 — Codex·ChatGPT 최신 인수인계 문서 패키지

- 일자: 2026-10-06 (Asia/Seoul).
- 구분: 문서·작업 지침. 실행 코드·환경 설정·ROS 정의·USD·모델 변경 없음.
- 승인 근거: 사용자 요청 “필요한 인수인계용 파일 최신버전으로 작성해서 전달해줘”. 문서 작성·전달 범위이며 공통 실행 코드 변경 승인으로 확대하지 않음.
- 기준 코드: `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`, Robot3FinalProject/main의 main 브랜치.
- 상태: 다운로드 적용용 문서 패키지 작성. 사용자 PC 적용·GitHub 반영은 별도 확인 필요.
- 대상: `AGENTS.md`, `README.md`, `docs/CODEX_HANDOFF.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF_SOURCES_20261006.json`, `sim/docs/RUN_GUIDE_20261006.md`, 이 변경 이력.
- 변경 이유: 초기 토마토 기획과 10/2 예찰 인수 기록만으로는 10/6 수확·통신·다중 로봇 실행 상태를 전달하기 어려움. 코드·문서·사용자 확인의 시점을 구분하기 위함.
- 변경 내용: 최신 구조·메시지·로그·실행 인자·미구현 영역 정리. 루트 AGENTS의 복원 전 그래프 설명과 README의 수확 미구현 포괄 설명을 정정. 인수인계 읽기·갱신 규칙과 ChatGPT 프로젝트에 추가할 지침을 문서화.
- 현재 규칙 유지: 시뮬 전용 작업은 sim 내부, 공통 코드 변경 승인, sim 정답 평가와 실제 제어 분리, 코드 및 사용자 미커밋 변경 보존.
- 직접 검증: 기준 커밋의 관련 소스·설정 정적 대조; 8베드/16Section/80관측점, 원본/예찰/수확 그래프의 노드·엣지·약연결성 계산; 최종 패키지의 링크·경로·필드·Bash 구문·ZIP 내용 검사. 상세 결과는 전달 시 검증 기록 기준.
- 미실행: 사용자 PC의 git 상태, colcon 빌드, ROS 네트워크·관제 연동, Isaac 물리 실행, 실물 실행. 과거 시험 횟수를 이번 재실행 결과로 쓰지 않음.
- 실물 영향: 실행 동작 변경 없음. 새 세션에서 갱신된 문서 확인 절차가 적용됨.
- 되돌리기: 적용 전 문서 백업과 비교하여 이번 문서 변경만 복원. 이번에 새로 추가된 문서의 제거 여부는 이후 편집 유무를 확인한 뒤 결정. 실행 코드·데이터를 되돌릴 이유는 없음.
- 관련 과거 기록: 캐스터 보정은 `sim/docs/changes/CASTER-FIX-20261006-013.md`, 통신규약은 `docs/changes/PROTOCOL-20261006-014.md`에 별도로 존재한다. 여기에서 해당 변경을 새로 적용한 것으로 기록하지 않는다.


## DOC-STATE-20261006-016 — 로컬 코드·문서·기존 로그 대조

- 일자/구분: 2026-10-06 KST / 문서. 적용 완료, 정적 검토 완료.
- 승인 근거: 사용자 요청 “인수인계서, 변경 이력, docs/changes와 현재 코드를 대조해서 docs/PROJECT_STATE.md를 작성해 … 이번에는 문서만 작업해”.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e 및 시작 시 미커밋 인계 문서. fetch 후 origin/main과 0/0. 기존 AGENTS/README/이력 수정, 미추적 인계 파일과 백업 보존.
- 대상: docs/PROJECT_STATE.md, 이 변경 이력. 코드·설정·시험·모델·USD 변경 없음.
- 전후: 인계 패키지의 원격 기준 요약 → 실제 로컬 Git 상태, 실행 요약, 구형 설명과 코드의 차이, 저장된 수확 성공 2건/실패 6건의 증거·한계 보강. 로컬 장면 USD는 포인터가 아닌 바이너리 객체임을 정정.
- 실물/시뮬 영향: 실행 동작 변경 없음. 최신 프로토콜 E2E 검증 완료로 확대하지 않음.
- 직접 검증: Git fetch·차이 조회, 관련 문서/launch/메시지/미션 정적 대조, GeoJSON 규모·약연결성 및 16Section/80관측점/8베드 계산, 기존 survey/audit JSON 열람, USD 헤더·크기·캐스터 패치 체크섬 비교, 문서 링크·기존 파일 보존 검사.
- 미실행: 기존 단위/경로 검사의 재실행, colcon/ROS/CDR/Isaac/실물/최신 프로토콜 E2E.
- 로그: 새 런타임 로그 없음. 기존 증거 위치와 다음 통합 시험 조건은 PROJECT_STATE §11·§13.
- 복원: 문서의 이번 보강과 이 항목만 이전 내용과 비교해 복원. 시작 시 미커밋 변경은 유지. commit/push 미실행, 원격 미반영.

## ROBOTARM-REVIEW-20261006-017 — 로봇팔 인수 자료 검토 및 반영 승인 대기

- 일자/구분: 2026-10-06 KST / 문서 검토. 실행 코드·설정·USD 반영은 승인 대기.
- 승인 근거: 사용자 “main에 robotarm 폴더에 … 확인해보고 sim에 반영할 내용 정리해서 나한테 확인받고 적용해”. 이번에는 검토서 작성만 수행하고 적용 전 확인 절차를 따른다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e. 이번 fetch 후 origin/main과 0/0. 기존 미커밋 문서·백업 및 robotarm 원본 4개 보존.
- 대상: 신규 `sim/docs/ROBOTARM_INTEGRATION_REVIEW_20261006.md`, 이 변경 이력. 실행 파일·공통/실물 코드·기존 설정·자산 변경 없음.
- 전후: 인수 명세 4개만 존재 → 현재 sim과의 차이, 필수 추가 인수, 단계별 대상 파일·영향·검증·승인 경계를 문서화.
- 주요 발견: 정책 4개/run.json/profile/runtime/RL 소스/전용 자산/검증 원본 미수신. 오른팔 Teacher와 기존 왼팔 Window/audit 불일치. 현재 60Hz와 Teacher 실효 480Hz/정책20Hz 차이. 활성 농장 과실 288개 하위에 rigid body/mass/collision API 없음. 현재 과실 크기와 root 의미 대조 및 박스 바닥 물리 준비 필요.
- 직접 검증: 문서/JSON/현행 코드 정적 대조, 후보18개 범위·HOME 거리·18cm 간격 조합 계산(최대3개), 파일 목록/SHA256, Git 상태·fetch·커밋 차이, 설치 pxr를 사용한 USD 정적 TF/기하/물리 API 검사.
- 미실행: 정책 추론, Isaac SimulationApp/PhysX, ROS/colcon, 실제 수확 및 실물 시험. 문서의 적재3/6은 담당자 과거 기록이며 이번 검증 결과가 아님.
- 제안: A sim 인수 설정·검사 도구 → 원본 수령 후 B 독립9g 평가 → C 농장/오른팔 기하 정합 → 별도 공통 승인 후 D 실제 팔 작업 연결. 이번 승인 요청은 A이며 B~D 동작을 자동 승인받은 것으로 취급하지 않음.
- 실물/시뮬 영향: 문서만 추가되어 실행 영향 없음. Teacher 내부 상태 입력은 독립 평가 범위로 한정하며 기존 공통 제어 정답 주입 금지를 유지.
- 결과/다음 작업: 상세 검토서의 A 범위를 사용자에게 제시. 승인 후 설정·검사 도구를 구현하고 누락 원본 확보 후 물리 재현 진행. 새 런타임 로그 없음. commit/push 미실행.
- 복원: 이번 검토서와 이 항목만 되돌린다. 기존 이력과 시작 시 미커밋 변경을 보존한다.

## ROBOTARM-RECEIPT-20261006-018 — 전체 전달 묶음 수령 및 이식 문제 검토

- 일자/구분: 2026-10-06 KST / 수령 검사·문서. 사용자 요청 “파일 받아서 robotarm 폴더안에 넣어놨어 파악해봐”. 앞선 전체 자료 수신 후 일괄 작업 요청에 따라 017의 A 단독 반영은 보류.
- 기준: 농장 main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e, 이번 fetch 후 origin/main과0/0. 전달 소스 base abe9e13357e1be549500712b62c5582649d444ab + 현재 수정본.
- 대상: 신규 `sim/docs/ROBOTARM_BUNDLE_RECEIPT_20261006.md`, 기존 검토서의 최신 문서 연결, `docs/PROJECT_STATE.md` §14, 이 이력. `sim/runs/robotarm/received_20261006_143434/`에 검토용 원본 추출 및 검사 JSON2개. 실행 소스·정책·기존 자산·프로파일은 수정하지 않음.
- 전후: 문서4개만 수령 → 소스·정책·자산·환경·YOLO·평가 원본 확보 및 무결성 확인. 새 평가/농장 통합 완료는 아님.
- 직접 검증: archive SHA256, 안전한 상대경로/일반파일 검사, manifest2148 및 정책4/run.json 해시 일치, 기존4개 파일 동일, 미수신LFS 포인터0. USD/URDF 참조·박스 바닥·팔/차체/캐스터 정적 대조, 환경metadata 비교, 과거episode JSON 집계, 동작코드 분석.
- 발견: prepare 경로 치환 뒤 converter asset hash가 달라져 USD 재생성 경로 발생. 복귀는12×1/480s이나 제어·dwell은50ms 사용. 전달 current USD는 고정차체 평가용, 농장 주행 USD 통째 교체 불가. 비전 환경 일부 버전 차이. 상세는 수령 검토서.
- 미실행: prepare/캐시변환/설치/정책로딩/Isaac·ROS·실물·학습. 원본3/6 성공은 과거 기록이며 수신PC 결과가 아님.
- 실물/시뮬 영향: 문서·검토용 추출만 수행, 현재 운영 동작 영향 없음. source 원본/기존 미커밋 문서·백업 보존. commit/push 없음.
- 후속: 이식·비전환경·복귀시간 보완을 포함해 독립9g 재현 및 농장 통합 범위를 확정. 공통 업무 변경은 기존 구체안 승인 절차 유지.
- 복원: 이번 문서 항목만 비교 복원. 원본 archive/기존 자료를 삭제하지 않으며 검토용 추출본은 운영에서 참조하지 않음.

## ROBOTARM-PHYSICS-20261006-019 — 농장 과실·오른팔 물리 및 수확 목표 좌표 적용

- 일자/구분: 2026-10-06 KST / sim 코드·설정·독립 자산·시험·문서. 구현 및 GPU 기초 물리/진입점 시험 완료, 정책 파지·적재와 실제 Nav2 주행은 미실행.
- 승인 근거: 사용자 “전달받은 파일들 기반으로 아이작심에 적용 … 농장 맵 … 물성치 … 오른쪽 팔 … 예찰로봇 좌표 … 오른쪽 암 기준 … 그것부터 작업”. 추가 선택 “Teacher 규격으로 통일”. 017/018의 검토 대기는 이 sim 1단계에 한해 구현 요청으로 대체했다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e와 기존 미커밋 변경. fetch 후 origin/main과 동일. 받은 전체 묶음 및 공통/실물 실행 파일은 보존했다.
- 과실: `sim/assets/fruit/teacher_9g/`, `fruit_asset_setup.py`, `fruit_attachment.py`, `stem_physics.py`, 생성 도구. 농장288개를70mm폭/75mm높이·9g로 통일하고 마찰/감쇠/접촉·줄기 response5·40ms 지속 분리를 적용했다. 기존 ID·색·위치·회전 보존. 선속도3m/s·각속도20deg/s를 source runtime까지 대조해 적용. 받은 runs 폴더에 대한 운영 의존 없음.
- 오른팔: `robotarm_asset_setup.py`, `sim/assets/robots/harvest_physics/`.6축 힘 drive·그리퍼 접촉·HOME·박스 바닥4타일. 주행용 USD를 교체하지 않고 기존 바퀴/캐스터/왼팔/rigidbody/전체 articulation 물성은 보존했다. 고정차체 Teacher와 전체 solver/self-collision이 같은 환경이라고 주장하지 않는다.
- 좌표: `task.yaml`, 생성 `scout_survey.json`/`harvest_audit.json`, `rebuild_route_data.py`, `scout_vision.json`.16구역 오른팔 mount `[.19,.185,.713]`, 작업중심 `[.19,.5,.838]` 및 크롭 높이를 동기화. `harvest_runtime.yaml` 연결한계.09m/도착.02m·.05rad, `nav2_harvest.yaml` 내부허용.015m·.04rad. 원본 graph·베드 좌표 변경 없음.
- 실행: `robotarm_physics.json`, scout/scout_fleet/harvest.json, `harvest_physics.py`, run_sim/run_fleet, isaac.launch.480Hz 물리 한 tick마다 외력을 갱신하며60Hz 렌더를 별도 호출. 원본 USD 저장 없이 session layer에서 적용. 단독 runner도 실제 project_root를 받는다. 실행별 setup/물리 분리 로그를 저장하고 정책·수확 성공으로 사용하지 않는다.
- 직접 검증: 관련 단위54개+USD 정적7개=61개 통과(skip0), 원본 줄기 Torch와256개 상태 수치 대조,371개 경로,48개 오른팔 Goal과 정적 map 연결선, sim3패키지 colcon 빌드. GPU RTX4070SUPER/Isaac5.1에서288과실2초 자연이탈0, 선택 과실3N 외력으로40ms 이상 지속 후 분리·0.6초 낙하를 확인. 실제 fleet 진입점2초에서288결합 유지, RGB-D29프레임, 로봇별 상태60개. 상세값과 명령은 `ROBOTARM_PHYSICS_20261006.md`.
- 중간 문제: sandbox CUDA 접근 실패는 GPU 권한 환경에서 재시험. fast_shutdown 기본값이 결과 기록 전 프로세스를 끝내는 문제는 정상 종료/종료 전 보고서 기록으로 수정. 최초 낙하0.2초 검사는 분리 직후 상승속도 때문에 실패하여 초기속도/궤적을 기록하고0.6초 관측으로 보완했다. 최종시험은 누락된 과실 속도 제한까지 적용한 후 다시 통과. 중간 JSON 보존.
- 남은 차이/미실행: 실제 Nav2 정밀 정지·동적 장애물/footprint 검사, 전체 예찰→수확 E2E, 정책4개 독립 재현/20Hz 추론·파지·박스 적재, 실물 시험. 원본 농장 빈 visual 참조와 종료 UI extension 경고는 보고서에 구분했다. 공통 수확 Action은 현재 이동+수확0 계약 유지.
- 문서: 신규 `sim/docs/ROBOTARM_PHYSICS_20261006.md`, RUN_GUIDE 최신 절, PROJECT_STATE §15, DECISIONS D-013/D-014 및 이력 갱신. 실물 소스·설정·모델·공통 업무/메시지 변경 없음.
- 로그: `sim/runs/robotarm/physics_smoke_gpu_20261006/result.json`, 같은 이름 `.log`, `fleet_physics_smoke_20261006.log`, `asset_setup_static_final_20261006.log`, `physics/98d899878bda4638a1aa82bbaa51f46b/`.
- 종료 보완: 정상 app.close 후에도 Kit 스레드가 남는 현상을 확인해 CLI에서 파일·앱 정리와 출력 flush 후 검사 결과의 종료코드로 종료한다. 이전 시험 중 결과 기록을 마치고 남은 프로세스4개만 종료했다. 보완 후 물리 검사와 fleet 진입점을 재실행해 각각 종료코드0을 확인했다. 물리/장치 검증 성공과 종료 문제가 있었던 중간 실행을 구분한다.
- 복원: 신규 물리 프로파일 enabled=false로 물리 override를 임시 비활성화할 수 있다(480Hz와 좌표 변경은 별도). 전체 복원은 이번 sim 실행/설정 변경만 비교해 되돌리고 task 원본 기준으로 생성 설정을 함께 재생성한다. 기존 캐스터 패치·인계 문서·사용자 변경을 전체 reset하지 않는다. 소스 농장 USD는 변경하지 않았으므로 복구 저장이 필요 없다. commit/push 미실행, 원격 미반영.

## ROBOTARM-VERIFY-20261006-020 — 인장력 비교 검사 및 커밋·푸시 요청

- 승인: 사용자 “테스트하고 커밋푸쉬 … 정상적용 확인 … 어느정도 인장력 … 강화학습 환경을 적용한거야?”.019 구현과 관련 문서를 테스트 후 게시한다. 별도 AGENTS/README 등 기존 수정, 수신 archive·백업은 작업 트리에 보존한다.
- 대상: `check_harvest_physics.py`에0.1N 유지1초/무외력 회복0.5초 비교·GUI 카메라·실제COM/관성 및 초기tick 기록 추가. `stem_physics.py`/`fruit_attachment.py`에 힘 clamp 전후 및 분리 조건 진단 추가, 줄기 회귀1개 추가. 물리 수식·계수·판정·공통 코드는 변경하지 않는다.
- 검증:62개 테스트(skip0),371개 경로,sim3패키지 빌드 통과. GPU15항목/종료코드0,288과실 유지→0.1N 유지→3N 실제 분리·0.6초간0.90448m 하강 확인. 원본 USD와 주행 구성 보존.
- 중요한 중간 관측:0.5N·1초 유지 예상은 실패했다.116.7ms 뒤 인장축32.32mm, 원시0.51955N, 후크조건41.667ms로 분리됐다. 전달 수식의 거리 분리 조건이며 단순 힘 임계값 실패가 아니다. 별도1kg 무중력 GPU 시험에서 두 외력 호출은 합산됨을 확인했다. 실패 JSON을 보존하고, 물성을 바꾸지 않고 유지 확인 하중을0.1N으로 명시했다.
- 문서/증거: `ROBOTARM_PHYSICS_20261006.md` §10, PROJECT_STATE §16, `sim/docs/changes/ROBOTARM_PHYSICS_VALIDATION_20261006.json`. 원본 로그 `sim/runs/robotarm/precommit_20261006/`. 최초 격리 빌드의 underlay 의존경로 누락은 기존 install을 지정한 최종3패키지 빌드로 해결했으며 실패/성공 로그 모두 보존.
- 경계: 받은9g 평가 환경을 적용했으며 원 체크포인트의35g 학습조건 전체 재현·학습정책 적용·실물 파괴력 측정으로 해석하지 않는다. 정밀Nav2 이동·정책 파지·적재는 미실행.
- 복원:019 물성은 유지하고 이번 진단/검사 도구 추가만 별도로 되돌릴 수 있다. 기존 사용자 파일과 받은 원본은 삭제하지 않는다. commit/push는 이번 사용자 요청으로 승인됐으며 실행 결과는 최종Git 원격 일치로 확인한다.


## ROBOTARM-PERFORMANCE-20261006-021 — GUI 검사 종료와 CPU 물리 병목 분석

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 성능 계측·문서 정정. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd.
- 대상:`ROBOTARM_PHYSICS_20261006.md` §11 및 CCD 설명, `docs/PROJECT_STATE.md` §17, 이 이력. 임시 계측 도구/JSON/로그는 ignored `sim/runs/robotarm/perf_20261006/`와 `cpu_microbenchmark_20261006/`에 저장했다.
- 전후:GUI 검사 종료와12FPS 원인 미확인 →사용자 JSON15 checks 통과/유한 검사 후 의도된 종료 확인. 현재 물리/진단 생략/과실 고정480Hz/과실 고정60Hz의 GUI 비교를 각각 실행해8.30/8.27/22.22/89.52FPS 측정. 마지막60Hz 대조군은 초기 reset 영향으로 카메라Z 약8.05mm 차이가 있고 이전 운영 버전 성능이 아니다.
- 결론:현재 조건 frame120.44ms 중 CPU 물리 실행/결과 동기화100.63ms(83.5%). runtimeCPU/GPUDynamicsfalse, GPU평균11.9%.288개 동적 과실과 전역480Hz가 부하를 늘렸으며 추가 상태 진단만 제거해서 해결되지 않는다.
- 정정:실행 시sceneCCD=true를 확인했다. 기존 “scene CCD false 유지” 설명은 잘못됐다. 설정 자체를 변경하지 않고 Teacher와의 차이를 기록했다.
- 검증:4개 GUI 비교 정상 종료, 물리1tick/렌더 시간 불변 검사 및 대조군288kinematic/변위0 확인. 준비30/측정120프레임씩. 순수 NumPy 수식288개0.495ms/tick. 초기 SDK getter 계측 실패 기록 보존 후 임시 도구만 수정했다. 전체fleet/정책 수확/장기 성능·최적화 적용은 미실행.
- 실물/시뮬 영향:운영 코드·자산·물성·공통/실물 실행 변경 없음. 분석용 고정/60Hz는 별도 프로세스 메모리/session 안에서만 적용하고 종료했다. 이번 문서는 미커밋·원격 미반영.
- 복원:이번 문서 항목만 비교 복원한다. 기존 사용자 변경 및 원본 JSON/전달 묶음은 보존한다.

## ROBOTARM-ADAPTIVE-20261006-022 — 수확 활동에 따른 물리 주기·주변 과실 선택

- 일자/구분:2026-10-06 KST / 사용자 승인 sim 구현·실제GPU/ROS 검증. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 이후 미커밋. 승인 문구 “물리주기도 동적으로 … 수확중 수확로봇 인근 …”. 공통 업무 코드 변경 없음.
- 대상: runtime `physics_schedule.py`, `harvest_regions.py`, `harvest_physics.py`, `run_fleet.py`, `run_sim.py`; devices `fruit_attachment.py`, `harvest_activity.py`, `ros_adapter.py`, `package.xml`; config `robotarm_physics.json`, `harvest.json`; 새 검사도구 `check_adaptive_harvest.py`와 단위시험4개. 상세문서 `ADAPTIVE_HARVEST_PHYSICS_20261006.md`, 기존 물리/실행문서 연결, PROJECT_STATE §18, DECISIONS D-015, 검증JSON 갱신.
- 전후: 전체288개 항상동적/480Hz → 유휴60Hz·부착과실 고정, 수확중480Hz·오른팔 실제장착점0.8m/유지1.0m 영역합집합만 활성. 분리과실은 고정하지 않고0.6초 정지 후60Hz/움직이면480Hz. 부착과실의 움직임/분리타이머 동안 freeze 유예. 현재pose·앵커·기준자세·분리상태 보존. kinematic중CCDoff, 활성화시 원복·PhysX flush로 전환 순서 보장.
- 시간/동시성:60Hz 프레임당1~8물리tick과 렌더1회. 매tick 힘갱신, reset없이dt변경, 실제누적시각으로odom/clock/센서. 활동은 로봇별세션/seq/유효기간 검사, 다른 활동이 남으면 고주기 유지. 미래복수수확기 영역합산은 단위시험이며 현재 실제GPU는 예찰+수확각1대.
- 연결 경계:공통이동완료를 팔작업으로 추정하지 않는다. 내부set_activity와 sim전용Bool heartbeat를 추가했으며 실제팔정책/공통FSM 연결은 후속이다. 과실정답은 물리영역선택에만 사용하고 목표/수확성공으로 전달하지 않는다.
- 직접검증:단위/USD107개(skip0),sim3패키지빌드,실제ROS bridge13항목. GPU선택물리19항목/종료0,기존전체288개기준15항목/종료0. 근거리3개활성,3N분리41.667ms,0.20714m하강,60Hz복귀. 원본USD SHA256불변. fleet6초2개조건에서clock360/상태각180/RGB-D89/라이다10Hz/카메라pose시각검사 통과.
- 관측된 한계:동일0.08m/s 개방루프명령에서 고정60Hz와60→480→60Hz의 최종world위치 약2.6cm차이. 시계정상과 궤적동일성은 별개다. 바퀴drive/명령을 보정해 차이를 감추지 않았다. 짧은headless측정 실시간배율0.725대0.483. 이전GUI성능과 직접비교 불가.
- 중간문제:시험초기mount가 과실반경밖이어서 최초검사실패, 실제장착점기준 초기배치로 시험만 수정한뒤 통과. 초기kinematic+CCD경고는 batchflag전환순서로 해결. 실패로그 보존. 기존visual참조/Kit종료UI경고와 검사실패를 구분한다.
- 실물영향/미실행:실물·공통·원본자산 수정없음. 정책파지/적재·Nav2폐루프주행정밀도·다수수확기/운송·전체E2E·실물 미검증. 같은Scene고주기는 여전히 전역CPU비용이다. 독립세트주기는 별도인스턴스가 필요하다.
- 로그:`sim/runs/robotarm/adaptive_20261006/`, 각 결과의physics_log_directory. 검증요약:`sim/docs/changes/ADAPTIVE_PHYSICS_VALIDATION_20261006.json`. 문서/코드 로컬적용·sim패키지빌드 완료, 커밋/푸시 미실행.
- 복원:`adaptive.enabled=false`로 전체과실/기준480Hz모드 복귀. 영역처리유지/주기고정시험은idle_hz와harvest_hz를 동일값으로 설정. 전체코드복원은 이번파일만 비교복원하며 기존사용자문서/인수자료/백업을 보존한다. USD는 저장하지 않았다.

## TEACHER-INTEGRATION-20261006-023 — 도착 후 순차 수확 실현성·공통 변경 검토

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 구현 검토·승인 제안. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 및022 미커밋 구현. 요청은 도착 후Teacher에과실좌표제공→시도별물리성공/실패Feedback→대상처리후Result. 사용자선택으로빨강·노랑각1회/일반실패다음진행/녹색및차체추가이동제외 확정.
- 대상: `TEACHER_HARVEST_INTEGRATION_REVIEW_20261006.md`, `proposals/HARVEST_ARM_COMMON_CONTRACT_20261006.md`와 `.proposal` 스키마3개, `changes/TEACHER_INTEGRATION_REVIEW_20261006.json`, PROJECT_STATE §19, DECISIONS D-016/O-008, 이 이력. 검사스크립트/원본JSON은ignored sim/runs/robotarm/policy_integration_review_20261006 아래다.
- 직접검증: 정책4개/각run.json SHA256, 현재설치공식ActorCritic strict load·정규화·합성82D입력5개→6D유한/결정적출력. 전달/농장팔·박스 FK9자세/9link 강체변환 최대오차2.22e-16,실제USD정적8link 최대5.96e-7. 농장288root간격/자세/현재planner기하 정적비교. ROS Jazzy rosidl parser로 제안3종문법통과. 물리수확성공/타입생성·통신을시험한것은아니다.
- 주요발견: 좌표만이아닌82D+접촉/진행상태 필요. 원본환경은scene/physics소유하므로farmWorld어댑터 필요. 첫실패batch종료/실패후assign거절/미수집분리과실복귀거절과복귀25ms/계산50ms불일치를보완해야한다.0.8m물리영역과Teacher도달범위는별개,주변장애물은정책관측에서제외됨. 농장root최소132.77mm,18cm미만34쌍/66개.
- 제안: 공통harvest_robot가후보순서/누적결과/취소/Window종료를소유, sim이후보발견/단일과실Teacher/실제결과·정지·다음시도준비ACK를제공. 외부HarvestTask필드유지,내부HarvestCandidate/GetHarvestCandidates/PickFruit추가. 대상파일/실물영향/검증안을제시하고사전확인질문을보냈으며아직미승인이다. 부분실패를수량으로반환하면서대상처리완료SUCCESS로보는안도확인대기.
- 승인/실물영향: sim Teacher 정답입력은이번사용자의명시지시로허용,예찰/실물입력으로확대하지않는다. 공통/실물실행소스·기존모델·자산·물성·운영설정 수정없음. 새ROS타입등록/빌드/팔GPU실행/전체수확E2E미실행. 추가정책파일은필수누락아니며담당자에게검증된연속도달범위·실패복구·독립추론접점이있으면요청하는문구만작성했다. 실제외부메시지는전송하지않았다.
- 다음: 공통범위/부분성과종결의미 확인 후 독립9g재현→농장단일과실→실패후순차진행→Action·취소→동시Nav2검증. 기존022의주행응답차이를해결완료로취급하지않는다.
- 복원:이번검토문서/제안/상태기록만비교복원한다. 기존미커밋022/사용자AGENTS·README/받은원본은보존한다. 이번검토는미커밋·원격미반영이다.


## SIM-COMMON-20261006-024 — 최소 공통 연결과 sim Teacher 실행

| 항목 | 내용 |
|---|---|
| 기준 | main/1666a23 이후 미커밋. 앞선 동적 물리·검토 및 사용자 변경 보존 |
| 승인 | 사용자 “대부분 로봇팔 구동 코드는 sim 전용 … 공통에서 도착하자마자 result를 날리면 그 부분을 sim 코드에 연결”. 앞선 빨강/노랑 각1회·Teacher규격·좌표정답사용 승인 유지 |
| 공통 대상 | harvest_robot의 node/mission/communication/contract 및 새 arm_client. 상세는 docs/changes/HARVEST_ARM_HOOK_20261006.md |
| sim 대상 | teacher_policy/state/device/_teacher_vendor, arm_session/arm_ros, ros_adapter/package/setup, run_fleet/physics_schedule, harvest/harvest_task/teacher_policy 설정, 정책4개+run자산, 시험/도구/문서 |
| 변경 전후 | 도착 후 수확0 즉시반환→시뮬 내부Action 실제완료·정지대기. 지역활성→후보확정→20Hz정책→물리복귀/안착→누적결과. 메시지신규타입/공통Window실행기 제안은 미채택 |
| 성과 의미 | 정상 후보전체처리SUCCESS, 실제안착·실패수량 별도. 취소는정지확인, 미확인은차단. 과실/관절teleport·재부착·가짜성공없음 |
| 실물 영향 | 실물설정/모델/장치·공통주행/비전·외부메시지 불변. legacy도착전용설정 유지. 현재새팔장치는sim만 선택 |
| 직접 검증 | 178단위/USD 중176PASS/ROS2skip, 별도실ROS/UDP2PASS,4패키지build. 최종Isaac fixture 실제정책/복귀/실패수량/정지/정상종료 PASS. 원본FK·CPU재생 대조. 자세한 숫자와 취소 결과는 실행보고서 |
| 성능 한계 | 실제농장3과실 적재0. ENTRYtimeout/bad_detach 후복귀. 적재성능PASS와구분. 다중과실/기존적재실물보존/Nav2전체E2E/실물/카메라/다수로봇 미검증 |
| 중간 실패 | SDK sensor/filter길이오류 수정, testerSIGINT/짧은Kit종료대기-11 수정. 최종프레임종료+60초대기 code0확인, 중간실패로그보존 |
| 결과 | sim/runs/robotarm/teacher_integration_20261006, teacher/<session>/<job>; 요약 sim/docs/changes/TEACHER_RUNTIME_VALIDATION_20261006.json |
| 되돌림 | 실행중지후 harvest_task completion_policy=ARRIVAL_ONLY_NO_HARVEST, harvest runtime.harvest_arm.enabled=false. 소스복원은 이번변경만, 다른미커밋변경초기화금지. 동적물리별도설정유지 |

[실행·검증 보고서](TEACHER_HARVEST_RUNTIME_20261006.md). 커밋·푸시는 수행하지 않았다.

## SIM-TEMP-CONTROL-20261007-025 — 임시 예찰→수확 관제 CLI

- 사용자 요청: 나중에 삭제할 사이클 확인용 관제를 sim 안에 추가. 공통/실물 소스 변경 없음.
- 추가: `sim/tools/temporary_control.py`, `sim/tests/test_temporary_control.py`. 실행 가이드 §7 및 PROJECT_STATE §21 갱신.
- Section 입력→ScoutArea 성공 최종 목록→원본 HarvestTask 순차 요청→수량 출력. 실패/취소 부분 예찰 목록 제외, 중복 ID 사전 거절, 수확 작업 실패 시 큐 중단. Ctrl+C 자기 Goal 취소/종료 대기, 정지 미확인 차단. JSONL은 sim/runs/temporary_control.
- 직접 검사: ROS 설치 메시지를 이용한 단위검사 6개, --help 로딩, diff 공백 검사. 실제 네트워크 Action/Isaac/Nav2 전체 사이클은 이번에 실행하지 않음.
- 기준 main/1666a23 이후 미커밋. 기존 미커밋 변경 보존. 커밋·푸시 없음.
- 되돌림: 위 임시 도구/시험과 가이드 §7 제거. launch와 로봇 실행은 변경하지 않았음.

## SIM-RVIZ-20261007-026 — FollowPath 추종 경로 표시

- 사용자 요청에 따라 sim의 scout_harvest/scout/harvest.rviz에 로봇별 `/received_global_plan` Path를 추가했다. 예찰 초록, 수확 주황, 선폭0.045m·높이0.12m. 기존 planner `/plan` 표시는 비활성화하고 이름으로 구분했다.
- 현재 GeoJSON 경로는 FollowPath로 직접 전달되므로 planner `/plan`만 구독하면 추종 경로가 표시되지 않을 수 있다. RPP가 발행하는 변환/가지치기 구간을 표시하며 전체 원본 Goal Path나 전체 그래프와 동일하다고 설명하지 않는다. 기존 route_markers 표시는 유지한다.
- 공통/실물/주행 코드·주기·도착 허용오차 변경 없음. 설치된 RPP 라이브러리의 토픽 이름과 YAML3개 설정을 확인했다. 실제 RViz 화면·이동 중 수신 검증은 미실행.
- RViz만 설정 재로드하면 적용. 되돌림은 이번 Path 항목 제거와 기존 plan Enabled 복원. 기준1666a23 이후 미커밋, 커밋·푸시 없음.

## SIM-NAV-20261007-027 — 베드 평행 접근 분석·공통 변경 승인 대기

- 사용자 베드 앞 정렬/평행 주행 요청.16개Section 모두 정차선과 기존 수확 graph가60mm 불일치함을 정적 확인. 실제6개 수확로그 최종60mm 구간이 목표 yaw와90도 차이. geometry.json에 저장.
- sim/docs/proposals/HARVEST_PARALLEL_APPROACH_20261007.md에 sim 수확 graph 정렬과 공통 선택적 진입/최종방향 검사·이미 도착 처리의 파일/영향/검증안을 작성. 실행 코드/설정/graph 미변경, 공통 승인 대기.
- 실제 새 주행 미실행. 기존 변경 보존, 커밋·푸시 없음. 되돌림은 이번 제안/분석 기록만 제거.

## SIM-COMMON-20261007-028 — 수확 평행 접근 적용

- 사용자 “수정해”로027 제안 승인. common farm_navigation3파일+parallel_approach.py, sim 생성기/task/survey/harvest graph/runtime/Nav2 설정 변경. 상세 docs/changes/HARVEST_PARALLEL_APPROACH_20261007.md.
- 주행선60mm 정렬, 넓은 기존 진입부 도착/정렬 후 평행 주행, 다른 구간 이동 전 정방향 이탈. 이미 도착 시 정지 재검사. 좁은 구간 복구 조건 불충족은 실패. 실물 옵션기본false/설정 불변.
- 신규7검사/371경로/build PASS. 기존도착검사9PASS/1구형메시지fixtureERROR. 실제 신규 Isaac 주행/회전충돌 여유 미검증. 사용자 실행 중인 프로세스는 재시작하지 않았음.
- 재시작 후 station에서 첫 Goal 재전송 필요. 기준1666a23 이후 미커밋·원격 미반영. 복원은 이번변경만 대상으로 한다.

## SIM-DRIVE-20261007-029 — 수확 회전·제동 보정

- 사용자 진입 정렬0.2486rad 실패 및 “해결해” 요청. sim base_sim/wheel_servo, harvest.json, nav2_harvest.yaml, harvest_runtime.yaml, drive_diagnostics, 물리 시험도구/단위시험/보고서 수정. 공통·실물 소스 및 원본USD 불변.
- 엔코더 각도차 속도 PI 보정과 정지시 적분 초기화·반대방향 제동. 수확만 활성화, 저속정렬0.06rad/s/각가속0.1/yaw gate0.01; 최종0.05rad 도착 기준 유지. 느린회전 대응 progress120/goal600초.
- 실제 Isaac 기존추가회전0.2534rad 재현. 최종 양방향 저속제동 추가회전0.00319/0.01317rad, 목표각도 후정지 오차0.00510/0.00932rad PASS/code0. 신규servo4+평행7검사/371경로/3패키지build PASS. Nav2 전체 경로·관제E2E·480Hz 동시주행 미실행.
- 비교시험 gain/solver/휴면 설정은 최종코드에서 제거. 중간시험 snapshot 공유 충돌 발견 후 별도 출력으로 수정. 해당 실패 및 중지한 비정상종료는 PASS 제외. 운영 snapshot 기반 평가가 시험 중 섞였을 가능성은 상세보고서에 기록.
- 상세 sim/docs/HARVEST_BRAKING_20261007.md, 결과 changes/HARVEST_BRAKING_VALIDATION_20261007.json. 사용자 운영프로세스 재시작은 하지 않았다. 적용은 all launch 재시작. 원복은 servo설정 제거 및 이번 속도/대기설정 복원. 미커밋·푸시 없음.

## SIM-NAV-20261007-030 — 실제 Nav2 코너 회전 시작 실패 보정

- 사용자18:06실패로그 직접 확인: controller_server Failed to make progress. 구동로그539072...에서첫코너전제자리 각명령약±.005rad/s. 이전 일정.06rad/s시험은 Nav2피드백결합 검증이 아니었다.
- sim nav2_harvest.yaml의 RPP.max_angular_accel만.10→1.2. 정렬속도.06/도착기준/PI/충돌검사 유지. 실제 전체Nav2 재검증 미실행. 설정생성일치/371경로검사 PASS.
- 실행중은 ros2 param set으로 적용가능. 사용자프로세스에는 자동 명령을 보내지 않았다. 원복은각가속도.10이나 기존정지문제재현가능. 미커밋·원격미반영.

## SIM-HARVEST-UI-20261008-031 — 배치·480Hz 수확 시험 패널

- 일자/기준: 2026-10-08 KST, main/7d9ae40ec8e0d0bebf0e0552f8a6ee85ddfc9bc3 이후 미커밋. 시작 Git 상태 clean. 원격 재조회·커밋·푸시 없음.
- 승인 근거: 사용자 “로봇팔 480hz 물리 연산 기준 … UI … 배치 버튼(수확가능한 열매가 있는 무작위 적정 위치) … 수확 버튼(480hz 전환, 인근 파프리카 물리)”. 시뮬 전용 시험 범위다.
- 파일: tools/harvest_test_ui.py; runtime harvest_test_placement.py/harvest_test_ui.py/run_fleet.py; devices arm_session.py/teacher_device.py의 읽기 전용 상태·장착점 조회; tests/test_harvest_test_{placement,ui,ui_launcher}.py; HARVEST_TEST_UI_20261008.md, RUN_GUIDE, PROJECT_STATE, 이 이력.
- 전후: 고정 fixture/CLI 위주 → 실제 Isaac GUI의 Place robot/Harvest/Stop 버튼으로 반복 관찰 가능. 기존 정차선/측정 팔 장착/Teacher 범위/원본 바닥지도 footprint 검사 후 미시도 부착 빨강·노랑 후보가 있는 배치를 선택한다. 차체 전체의 시험용 순간 배치이며 Nav2 성공으로 기록하지 않는다.
- 실행: python3 sim/tools/harvest_test_ui.py. 단독 수확 장치·사용 가능한 별도 UDP 포트·snapshot/로그 생성. ROS/빌드 불필요, 외부 UDP 제어 무시. 원본 fleet/지도/USD/Teacher/물성 보존. 공통·실물 코드 변경 없음.
- 물리/제어: 기존 ArmSession/Teacher/HarvestPhysics/AdaptivePhysicsTicks 재사용. 실제 정지/HOME/후보 재확인, 60→480→안정후60Hz, 주변 활성·20Hz 정책·실제 성공수량 유지. 활동 중 배치/중복 수확 차단. 적재 후 차체만 순간이동하거나 취소 후 비HOME 상태로 재배치하지 않는다.
- 직접 검증: 관련75검사 PASS(skip0); 새 배치10/UI13/실행기8 포함. Isaac5.1 GUI/RTX4070SUPER seed713 SEC10 Bed01/Pepper0017 yellow: 정책400회, 주변5/288 활성, 실제복귀/정지확인 및480→60Hz·활성0, 종료0. 처리SUCCESS지만 실제 적재0/실패1(target_timeout). 수확성능 개선 PASS가 아니다.
- 화면 검증: 최초 ReviewCamera 선택/한글 글리프 문제를 발견했다. Perspective를 명시 선택해 작업 팔과 과실/바구니를 보여주고 패널은 영문으로 제공한다. 최종 GUI 재실행·창 캡처에서 카메라/버튼/단계/480Hz/활성5개 표시 확인. UI 창 닫기 버튼을 제거하고 전체 Isaac 종료로 정리, timeline reset은 프레임 시작에서 감지한다.
- 로그/보고: sim/runs/harvest_test_ui/validation_20261008/{result.json,unittest.log,isaac.log,final_gui.png,final_gui_run.json}; 연결된 physics/teacher 경로는 result.json. 최종 GUI는 직접 조작하도록 실행 상태로 남겼다.
- 미검증/다음: 사용자 수동 클릭·다양한 seed의 실제 성공률·동시 운영 시뮬·Nav2 포함 E2E는 미검증. 적정 배치의 근거리/바닥 검사는 팔 IK/모든 동적 장애물 회피 인증이 아니다. 다음은 사용자가 버튼으로 반복 관찰하고 기존 Teacher 농장 성능을 별도 개선하는 일이다.
- 되돌림: 독립 도구/패널/기하/시험 추가 파일, run_fleet 선택 연결과 devices 읽기 API 및 문서 항목만 비교 복원한다. 전체 reset 금지. 배포 패치는 변경 파일만 sim/runs/harvest_test_ui/harvest_test_ui_20261008.tar.gz, 적용 명령은 실행 가이드에 기록했다.

## SIM-PHYSICS-INSPECT-20261008-032 — 충돌 메뉴·과실 물리 관찰

- 사용자 요청: Show By Type에 없는 Physics collision 표시 추가, 중력/connector 연결과 랜덤 회전 유지 여부 확인. 031 미커밋 변경을 보존하고 추가. 기준main/7d9ae40, 이번 원격 조회·커밋·푸시 없음.
- 대상: runtime 신규 harvest_physics_inspector.py 및 run_fleet/run_sim/harvest_test_ui; devices fruit_attachment 진단 snapshot/teacher_device 읽기 접촉 API; inspector 신규4검사/UI 추가2검사/접촉 추가1검사; 물리 진단 가이드·기존 UI가이드·PROJECT_STATE·이력.
- 전후: PhysX GUI 확장 미활성/수확 때만 확인 → GUI 실행에서 공식 omni.physx.ui 활성화, Show By Type > Physics > Colliders 메뉴와 패널 Hide/Selected/All 제공. Physics only 관찰은 팔정책 없이 기존 주변영역480Hz를 사용한다. 전역물성/원본USD/정책/실물·공통 코드는 변경하지 않았다.
- 계측: 선택 과실의 active/kinematic/gravity/collider flag, 초기 PhysX질량, 실제 pose/속도·root dz·tip 변위·회전각, 이전 tick 적용 줄기 힘, SDK 선택과실별 손가락 접촉력. mg는 Scene중력×질량 계산값임을 명시. 앵커/꼭지/COM/중력 표시만 추가하며 물리 joint를 생성하지 않는다.
- 발견: 현재 connector와 과실의 자유회전 native joint가 아닌 world 고정 앵커 spring + 초기 랜덤 quaternion 복원 토크다. 유휴부착과실은 kinematic. 중력이 작동해도 수직으로 완전히 정렬되지 않는 이유이며 성공0의 단일 원인을 확정하지 않는다.
- 직접검증: 99개 실행98PASS/1USD미설치skip/실패0. 실제GUI seed713 Bed01/Pepper0017 yellow, 팔정책 없이8초480Hz/주변5개: root하강10.788mm, 회전8.360°, 남은COM-꼭지기울기35.099°, mgZ -0.088290N/적용줄기Fz +0.088290N. collider1/1 convexDecomposition, 안정후60Hz/활성0, 종료0. 새GUI 재실행에서 와이어/표시와 선택과실별접촉0/0 확인. 이번 직접 수확접촉/파지 성공 검증은 아니다.
- 로그: sim/runs/harvest_test_ui/physics_inspection_20261008/{result.json,unittest.log,gui.png,final_gui.png}; 실행별 physics_inspection.jsonl. 최종 진단창은 열어두고 기존 사용자시험창/로그는 건드리지 않았다.
- 다음/한계: Harvest 중 실제집게 접촉력과 충돌형상 대조; 자유진자 connector 모델이 필요하면 별도 물리 모델 설계/Teacher 영향검증. 이번에 angular_k 완화/자세 초기화/가짜 성공은 하지 않았다.
- 복원: 032의 inspector/관찰 토글/읽기 API/GUI 확장 활성화와 해당 문서 항목만 비교 복원한다. 031 및 사용자 변경은 유지한다. 패치는 변경 파일만 포함, 적용 명령은 UI 가이드와 동일하다.

## SIM-TEACHER-DIAGNOSTIC-20261008-033 — 로봇암팀 요청 재현·회신 로그

- 승인/기준: 사용자 “robotarm/SIM_TEAM_TEACHER_DIAGNOSTIC_REQUEST 확인 … 자료 보고 회신 로그 확보”. main/7d9ae40 이후031/032 및 사용자 미커밋 변경을 보존했다. 공통·실물 코드/운영 설정·정책·물성·원본 robotarm 자료 변경 없음.
- 대상: sim teacher_policy.py에 기본off forward hook 계측; 신규 runtime teacher_diagnostics.py; run_fleet/check_teacher_harvest 선택적 --teacher-diagnostic-trace 연결; 신규 test_teacher_diagnostic_trace.py; 회신 문서·PROJECT_STATE·이 이력. 산출물은 sim/runs/robotarm/receiver_diagnostic_20261008.
- 전후: 기존 sample/최종action 위주 로그 → 실제 원본/시간보정/정규화82D와 전문가 raw action, 후처리/clip/최종6D, 상태 플래그, 실제 관절 target buffer·시뮬/벽시계·물리step·dt·초기/복귀/정지 연속 기록 및 USD/PhysX 설정. 추가추론/정규화 재학습 없음. USD 자동계산·무제한 Infinity는 최종계측에서 문자열로 저장하며 초기 노랑 원본은 보존하고 portable사본 추가.
- 전달본 직접 확인: 최초143434 TAR hash7b33...일치; 새해제본2148개검사 후 cache경로보정. 정책4개+run.json·전달평가소스불변. prepare/cache차이12파일은diff로보존.
- 실제 GPU 독립진단: 받은 무카메라 어댑터·전달실행기로 red182/yellow183각5회. 성공3+4/실패2+1, 두프로세스0종료. 송신10개trace1069tick가 SHA256까지일치. 카메라/YOLO포함원본스크립트E2E는미실행.
- 실제 GPU 농장: 기존headless fixture 노랑400POLICY timeout, 빨강42POLICY bad_detach, 실제적재0/2; 두job복귀/정지확인·종료0. 정책dt=.050000002608s, 각24physics step=480Hz. 원본관측/명령/PhysX전달 각19검사통과. taskSUCCESS/검증passed와수확성공을분리.
- 발견: 빨강양손접촉3.754/3.982N 있으나 파지확인0.05s<0.25s, 총변위46.790mm·지속41.667ms 이탈(인장0N), 정상파지전분리. 노랑최소거리74.99mm/양측접촉없음. farmUSD자기충돌false·solver32/1 vs전달소스true·12/4, 초기과실랜덤회전/고정차체차이. 단일원인으로확정하거나이번에수정하지않음.
- 검증: 실제가중치등Teacher/ArmSession60개+fleet entrypoint2개PASS, skip0; 새로운계측11개포함. 추가추론없이action/target·normalizer불변검사. diff --check/구문검사 및 회신manifest검증.
- 오류/한계: GUI2회는Teacher/recorder생성전World.__init__.render nativeOmniGraph SIGSEGV(-11). startup_error 로그별도보존, 성공/수확실패분모제외. 이번viewport영상미확보. 동일초기조건farm대조·Nav2·실물미실행.
- 회신: sim/docs/TEACHER_DIAGNOSTIC_REPLY_20261008.md, TAR+SHA256+MANIFEST. 원본stdout/trace/결과·설정·모델계약·관련source포함,checkpoint/RGB-D/전체해제본제외. 발송·커밋·푸시·원격재조회없음.
- 복원: 진단 플래그를 생략하면 기존제어경로다. 추가계측/CLI연결/시험·문서만비교복원하며031/032·사용자변경은유지한다. 다음은 담당자와같은q/목표pose/TF/threshold조건으로최초관측/action차이와solver·접촉영향을분리하는비교다.

## 2026-10-08 — AprilTag 태그 배치와 수확 PCWEB400 가상 카메라

- 구분/승인: 사용자 직접 요청의 sim bed 배치·수확 카메라/bringup 연결·공용 코드 인수 확인. 후속 답변으로 각 면100~114 반복/구간ID와 함께 식별 확정. 기준main/450bf5f, 기존 미커밋 수확 작업 보존.
- 대상: `assets/apriltag/`, 수확URDF, `farm_sim_config/config/{apriltag_layout,apriltag_map,harvest,scout,scout_fleet}.json`, 런타임`apriltag_scene.py` 및`run_sim/run_fleet`, 장치`camera_sim/camera_ros/ros_adapter`, generator·USD/렌더검증도구, 관련시험·상태/결정/실행문서.
- 전후: 태그없음/수확camera.disabled → session layer16벽240개(15원본반복), 수확측면optical센서 및RGB/CameraInfo발행. 기존공통bringup의sim장치선택으로연결해공통소스변경불필요. 실제웹캠depth없음. 예찰센서장착·경로·원본USD·실물설정은유지.
- 검증:19PASS,USD벽범위/크기/TF검사PASS,실제IsaacID104렌더검출/공유메모리전달PASS,3패키지build/371경로PASS. 첫Kit종료지연으로해당시험만정리, 최종렌더결과저장후종료timeout124. 최종반복IDUSD검사재실행. 전체DDS·이동검출/보정·실물미시험. [상세](APRILTAG_INTEGRATION_20261008.md),로그`sim/runs/apriltag_20261008/`.
- 코드인수: 로컬공용코드에AprilTag검출/보정없음. [요청서](APRILTAG_NAVIGATION_REQUEST_20261008.md)작성,발송없음. 공통수정승인대상diff는이번작업에없으며후속소스인수후검토한다.
- 실물영향: 없음. 실물harvest장치bringup은여전히미구현. 카메라장착은실측기반추정이며정밀실물검증완료가아님.
- 복원: 장치JSON의apriltag_map제거/harvest.camera.enabled=false후재시작,URDF추가광학링크/조인트제거. 기존미커밋수확변경을통째로되돌리지않는다. 미커밋·원격미반영.

## SIM-PEPPER-ROTATION-20261008-035 — 수확 비교용 랜덤 기울기 0도

- 사용자 요청: 기존 seed/최대각도 회전 스크립트를 찾아0도로Isaac적용. 기준 main/450bf5f 및 기존 미커밋·AprilTag 변경 보존.
- 도구: sim/tools/randomize_pepper_rotation.py → scout_dataset.stage.randomize_current_stage_and_save. 기존 구현 그대로 사용; sim/config/scout_dataset.json fruit_rotation.max_degrees만30→0, seed734유지.
- 실제 Isaac headless stage에서 기존 runpy 스크립트를 실행해 farm_with_plants_v5.usd 저장·정상종료0. 288개 jitter XYZ=0, world local-Z 기울기 전0.964~41.171°→후모두0°. 위치/원래xform op/ID 유지. 원래 yaw는보존하며모든quaternion이identity라는뜻은아님.
- 백업: sim/assets/envs/output/farm_with_plants_v5.usd.before_rotation_20261008_142400_041527. 설정백업/실행스크립트/stdout/전후288개검증은 sim/runs/pepper_rotation_zero_20261008.
- 실물·공통·물성·정책변경없음. 기존실행창의메모리상태는유지. 별도UI는초기화SIGSEGV(-11)로종료해ready미확인(gui.log/gui_result.json). 맵저장프로세스종료0과구분. 기존Isaac재시작으로새맵로드필요. 이번수확성공률재시험은아직수행하지않음.
- 복원: 위USD백업을원래파일로복사하고설정max_degrees=30(seed734)복원한뒤Isaac재시작. 커밋·푸시없음.

## SIM-HARVEST-UI-STARTUP-20261008-036 — 시험 GUI 시작 종료 수정

- 사용자 오류 수정 요청, 기준 main/450bf5f 및 기존 미커밋 보존. 대상: 런타임 `run_fleet.py`, `run_sim.py`, `harvest_physics_inspector.py`, `physics_schedule.py`, inspector 회귀 검사 및 상태 문서.
- 조기 PhysX UI 확장 활성화 상태에서 World 초기 render가 native SIGSEGV로 종료됐다. 확장 등록을 World/장치 초기화 뒤로 이동했다. 이후 드러난 dt 오류는 layers 확장이 USD 편집 대상을 session→root로 변경해, 더 강한 session의480Hz가 root에 쓴60Hz를 덮은 문제였다. 확장 활성화 성공/실패 모두 기존 edit target을 복원하며 dt 불일치 메시지에 실제/기대값을 추가했다. 충돌 메뉴와 엄격한 주기 검사는 유지한다.
- 실제 Isaac5.1 GUI: 일반3초/180tick 종료0, 물리 관찰14초/840render/4200tick 종료0. 1.520833초에480Hz·주변5과실 활성,9.520834초에60Hz·0과실 복귀. 일반 무기한 시험창 재실행 및 패널/60Hz 화면 확인 후 열어둠. 로그·화면 `sim/runs/harvest_ui_startup_fix_20261008/`.
- 관련 검사39개 PASS(레이어 복원 성공/실패, 주기, UI, launcher, fleet entrypoint). 넓은 harvest 패턴 검사112개에서는 별도 geometry 단일 테스트의48개 subtest 실패 및 sandbox UDP 차단3오류가 있었다. UDP 관련 launcher8개는 허용 환경에서 전부PASS. 경로 기하 실패는 이번 시작 수정 범위에서 수정하지 않았다. run_sim 실제 GUI 및 수확 성공률은 이번 미검증.
- 실물/공통/Teacher/물성/0도맵 변경 없음. 복원은 이번 확장 호출 이동·edit target 보존·오류 메시지만 역적용하며 기존 사용자 변경을 통째로 되돌리지 않는다. 수정 파일 묶음 `sim/runs/harvest_ui_startup_fix_20261008/changed_files.tar.gz`는 현재 미커밋 파일 전체를 포함한다. 커밋·푸시 없음.


## SIM-TEACHER-ARM-ALIGNMENT-20261008-037 — 학습 오른팔 물리 정렬

- 승인: 사용자 “로봇팔 물성치, 충돌 판정 … 다 학습환경에 맞춰서 수정”. main/450bf5f 및 기존 미커밋 보존. sim 전용, 실물/공통/전달 정책 소스 변경 없음.
- 대상: `teacher_arm_alignment.py`, `robotarm_asset_setup.py`, `harvest_physics.py`, `teacher_device.py`, `teacher_diagnostics.py`, `run_fleet.py`(종료 전 최초 예외 보존), `robotarm_physics.json`, 기준 팔usdc/manifest, 추출/대조 도구2개, 회귀 검사, 물리 확인/진단 회신·상태·결정 문서.
- 변경: convexHull→전달 convexDecomposition 메시15개; 여섯몸체 질량/COM/관성·집게카메라 합성; 자기충돌true/solver12·4, 학습GPU/TGS/접촉설정, material, 팔 collider1mm override제거, 학습4링크 접촉센서. 이동 차체·왼팔/바퀴 구동 구조 유지. 원본USD 미저장/세션적용. [상세 비교와 환경 차이](HARVEST_PHYSICS_INSPECTION_20261008.md).
- 검증: 독립 전달1회 종료0, 농장GUI3초 종료0, USD/PhysX115항목 일치(최종GUI 반복확인), 회귀56PASS. 수확480Hz/주변5과실 및60Hz복귀/정상종료0. 수확 적재0/1: arm_collision→return_contact_2.779N→safe_stopped=true. 수확성공률 개선/전체학습환경 동일성 검증 아님. 최종 GUI 열어둠.
- 최초 통합2회는 SDK 확장속성 API 부재로 초기예외, 종료native오류가 원인을 가림. typed USD attribute fallback 및 종료전 예외기록 후 해결, 세 번째부터 정상. 실패로그도 보존.
- 결과 `sim/runs/arm_physics_alignment_20261008/`, 설정/초기 코드 백업 포함. 복원: teacher_alignment.enabled=false 후 새실행(기존 팔 물리 경로). 전체 파일 reset 금지. 변경파일묶음/적용명령은 상세문서에 기록. 커밋·푸시/외부발송 없음.


## SIM-FRUIT-RENDER-SYNC-20261008-038 — 과실 물리/화면 위치 동기화

- 승인: 사용자 내부 적재 로그와 초기 위치 화면의 차이 조사 요청. main/450bf5f 및 기존 미커밋 보존.
- 대상: devices 신규 fruit_pose.py 및 fruit_attachment.py, runtime fruit_asset_setup.py, pose 신규검사/asset 설정검사, 물리진단·회신·PROJECT_STATE·이력 문서.
- 원인/수정: 사용자 정의 matrix op로 고정된 과실은 동적 PhysX만 이동하고 표시 root/mesh는 정지했다. 초기 배치/재고정 모두 pose를 보존한 표준 translate/orient/scale로 작성한다. 내부 SUCCESS만으로 화면 운반을 확인했다고 한 판단을 정정했다.
- 검증: 실제GUI 통제 이동·낙하23sample 최대 물리/표시 오차0.550647m→0.000590m(root0m). 최종5초/300render/1763physics/종료0. 초기3probe는 완료 후 잔류종료를 수동 정리했으며 최종 정상종료와 구분. 단위·USD43PASS. 새 일반GUI480→60Hz 및 화면 확인. 전체수확 성공 재검증은 미실행.
- 실물영향 없음. 정책·마찰·질량·성공기준·원본맵 불변. 결과/백업/변경파일묶음 sim/runs/fruit_render_sync_20261008. 복원은 before.py와 이번함수/검사 차이만 비교하며 기존변경 유지. 적용명령은 물리진단문서 마지막 절.
- 다음: 새GUI에서 실제 파지→운반→적재 관찰. 문서갱신, 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-OPT-20261008-039 — 단독 시험 UI의480Hz 비용 축소 (정적화는040에서 철회)

- 승인: 사용자의 PhysX step 최적화 요청. sim 런타임3개 파일(physics_schedule, harvest_test_ui, run_fleet)과 관련 검사만 변경. 실물·공통·원본USD·학습 팔 물성/충돌/주기 불변.
- 변경: 미사용 선별기/정찰 로봇43강체를 표시·충돌 형상 보존한 정적 배경으로 전환. USD 위치/속도 쓰기를 렌더 프레임의 마지막 tick에 수행. 힘/물리/접촉은480Hz 유지. 두 변경 모두 시험 UI에만 활성화.
- 실측: 동일seed713의480Hz GUI 수확에서 물리 step195.84→102.43ms, FPS4.28→7.01. 실제 적재0/1, 복귀 접촉 실패는 남음. GPU backend 유지; CPU/MBP10.51FPS 비교는 미적용.
- 검증: 관련37검사PASS, 운영GUI 종료0·표시 위치136표본/배경형상불변·PhysX오류0. 독립 sleep/재활성/480→60→480 시험 종료0(최대 위치오차1.92e-8m). Stop→재배치→240Hz 재수확 확인. [상세 수치·재현·범위](HARVEST_TEST_UI_20261008.md), 로그 sim/runs/physx_optimization_20261008.
- 복원: run_fleet의 configure_test_background 호출과 batch_usd_writeback 활성화만 역적용. 기존 사용자 변경/물성정렬/과실표시수정 보존. 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-RESTORE-20261008-040 — 네 로봇 동시 운용 요구에 따른 정적화 철회

- 사용자 정정: 예찰·수확·운송·선별팔은 최종적으로 모두 동시에 움직여야 하므로 다른 로봇 정적화는 부적절함.
- 변경: harvest_test_ui의 configure_test_background, run_fleet의 해당 호출, 전용 test_harvest_test_background.py 제거. USD 쓰기 프레임 단위 처리만 유지. 이전 GUI 세션 종료 후 새 stage로 실행. 원본USD/실물/공통코드 불변.
- 수치 정정: 7.01FPS/PhysX102.43ms는 두 로봇을 정적화한 폐기 조건이다. 로봇 물리 유지 시 기존 비교4.28→4.67FPS이며 네 로봇 동시 운용 실측은 미실행. fetch_results는 계산 완료 대기/결과 반영을 포함하므로 readback 주병목 단정도 철회.
- 검증: 스케줄러15·UI17·진입점2개PASS. 실제 물리 복원 로그는 sim/runs/physx_optimization_20261008/restored_scene.json 및 restored_ui.log. [현재 범위와 기록](HARVEST_TEST_UI_20261008.md).
- 사용자 변경 보존, 커밋·푸시·외부발송 없음. 정적화는 다시 적용하지 않는다.

## SIM-HARVEST-PHYSX-PROFILE-20261008-041 — GPU 커널과 대기 FPS 간극 실측

- 승인/기준: 사용자 “병목을 더 확실하게 파악 … 기존 Nav2 약70FPS와 현재대기22FPS 간극 확인”. main/450bf5f 및 기존 미커밋 보존. 운영 소스·설정·정책·원본USD·실물·공통 코드 변경 없음.
- 대상: `sim/runs/physx_bottleneck_20261008/`의 격리 계측 wrapper/결과와 `HARVEST_TEST_UI_20261008.md`, `HARVEST_PHYSICS_INSPECTION_20261008.md`, `docs/PROJECT_STATE.md`, 이 이력. CPU/MBP 전환·좌표기록 생략/캐시는 임시 대조 실행만 적용.
- 전후: fetch_results 경과시간만으로 CPU/GPU원인을 분리하지 못함 → Nsight CUDA/NVTX/OSRT와 PhysX profile zone으로428tick분리. USD쓰기없는fetch17.843ms 중GPU커널15.924ms, GPU→CPU복사0.0619ms/tick. 상위관절커널각15408회=428×36,1block×32thread. GPU solver최대반복32/4의 장면전체영향을 공식107.3소스/실제커널로 확인. 기존팔115항목속성검사한계를명시.
- 대기 비교: 동일ReviewCamera1280×720/센서OFF/각새프로세스. 모든기존로봇97동적/3관절계·과실형상4829유지, GPU29.80FPS→CPU50.23FPS. 좌표기록생략진단GPU31.95/CPU59.53FPS. 원본맵대조는43동적/2관절계/29convex/CPU,실제59.56FPS(60cap)·물리1.81ms. sleep제외처리용량138.49를실제FPS로사용하지않음. 원본맵SHA전후동일.
- 수확 비교: CPU480Hz작업13.01FPS,seed713적재0/1,RETURN_FAILED/2.839N·실제정지확인·정상종료0. 성공률개선/물리backend동등성으로해석하지않음. 상세현재GPU대조와좌표캐시결과는연결보고서참고.
- 검증/한계: 실제Isaac5.1 GUI격리대조와Nsight원본보존. 최초Nsight실행은optional SDK cooking API선택오류로capture전종료1,수정후최종종료0; 실패로그보존. CPU IP sampling권한제한은우회하지않음. 실제Nav2경로주행·과거사용자70FPS정확조건·최종4로봇동시미션·다지점수확회귀는미실행.
- 복원: 이번에는운영변경없음. 진단wrapper를사용하지않으면기존기본GPU/수확480/대기60Hz. 추가문서만해당절비교복원하고원본로그는보존한다. 다음은환경조건완화보다CPU480Hz접촉/관측/성공률회귀우선. 문서갱신,커밋·푸시·외부발송없음.

## SIM-HARVEST-REPORT-20261008-042 — 최적화 종합 자료와 Git 반영

- 승인: 사용자 “최근커밋 이후 수정사항 커밋메세지에 간략하게 … 480hz 물리 연산 적용 후 … 보고서 작성용 md”, 후속으로 commit+pull+push까지 명시. 기준 main/450bf5f 이후 미커밋 변경 전체를 보존·반영한다.
- 대상: `HARVEST_OPTIMIZATION_REPORT_MATERIAL_20261008.md`, `changes/HARVEST_OPTIMIZATION_EVIDENCE_20261008.json`, PROJECT_STATE 링크, 이 이력, sim/.gitignore의 회전 전 로컬백업 제외 규칙.
- 변경: 초기 CPU480Hz→지역 활성화/주기전환→UI/정확성 수정→Hz비교→USD쓰기→정적화 철회→Nsight/CPU/원본맵 대조를 종합했다. 핵심 JSON8개를 출처SHA256과 함께 버전관리 경로에 복사해 원격 보고서 작성에 사용할 수 있게 했다. raw runs/회전 전 백업은 로컬 보존한다.
- 범위: 이번 종합 과정에서 운영 로직·물성·backend를 추가 변경하지 않았다. 최근 미커밋에는 별도 승인된 AprilTag 작업도 포함하며 보고서에서 물리 최적화와 구분한다. 맵과 팔자산은 기존 LFS로 저장한다.
- 검증: 원본 JSON8개 hash/내용 및 Markdown 내부링크 대조 PASS, Python43개 구문 PASS, 기존 전달 CSV의 CRLF를 보존한 변경공백 검사 PASS. Isaac Python에서 수확/물리/진단58개, ROS Jazzy 환경에서 AprilTag4개 PASS(skip0). 최초 검사는 테스트 import 경로 누락, 이전 진단 대역의 PhysX view 누락, Isaac 환경 OpenCV API 차이로 실패했다. import 경로/실행 환경을 맞추고 `test_teacher_diagnostic_trace.py`의 대역 view만 보완해 통과했다. 운영 소스 변경은 없다. 성능/수확 숫자는 앞선 실제 시험 기록이며 보고서 작성 중 재측정값으로 표현하지 않는다. 최종 커밋·원격 반영 상태는 Git 결과를 따른다.
- 복원: 이 종합자료/링크/백업 제외 규칙만 필요에 따라 역적용한다. 이전 변경을 통째로 reset하거나 raw 로그·복원용 USD를 삭제하지 않는다.



## SIM-SCOUT-URDF-20261013 — PDF 장착 모델 반영

- 기준 main/a393f1a, 사용자 URDF 수정 요청 및 첨부 PDF 기준. sim scout 원본/portable URDF에 기둥·상판/홀더 근사 외형·봉·D435/파이캠 TF 추가. 기존 기본 링크/물성 불변, 공통·실물 소스 변경 없음.
- 변경 전 센서/장착 없음 → D435(-49,55,595)mm/하향1도, 파이캠(-32,63,117)mm, 기둥 상단620mm. PDF A/B/C 구분 유지; 추가 질량/관성은 미정.
- 직접 검증: XML/트리/기존 노드 보존/좌표·방향 계산. ROS·Isaac·실물 미실행. 기존 USD/실행 설정은 자동 변경되지 않으며 PC 적용/원격 반영 없음.
- [상세·한계·복원](SCOUT_URDF_MOUNT_20261013.md). 패치 역적용으로 복원하며 사용자 변경이 있으면 먼저 병합.


## SIM-SCOUT-USD-20261013 — 장착 USD 및 단독/fleet 연결

- 승인: 사용자 “usd까지 반영한다음 커밋푸쉬해”. 기준 main/a393f1a. 앞선 URDF 수정본까지 함께 반영.
- 대상: scout_mount_20261013.usda/하위 .gitattributes, build_scout_mount_usd.py, scout_mount.py, run_sim.py/run_fleet.py, scout.json/scout_fleet.json, test_scout_mount_usd.py 및 관련 상태·결정/보고서.
- 전후: URDF만 수정 → 실제 sim 진입점에서 기존 base_link에 장착 USD 참조·D435 transform 적용·파이캠/PDF TF 발행. 기존 Camera 광학/구동 joint/본체 질량 유지. 공통·실물 변경 없음.
- 직접 검사: OpenUSD26.8 합성 stage4PASS(비활성 prim 검증 결함 수정 후 통과), Python 구문PASS. 원본 농장 LFS binary 미확보로 실제 농장 합성/Isaac/PhysX/ROS/주행은 미검증.
- 복원: scout_mount_asset 설정 제거 및 재시작. 원본 USD는 세션 방식으로 보존. [상세·한계](SCOUT_URDF_MOUNT_20261013.md) 최상단 절을 따른다. 원격 게시 승인은 받았으며 최종 Git ref 결과로 게시 여부 확인.

## SIM-APRILTAG-HANDOFF-20261013 — 인수 주행 병합과 시뮬 영상 보정 연결

- 기준: `main/a393f1a` + 기존 사용자 미커밋 변경. 전달 `bf10fcd`, SHA-256 120개 일치. 승인 근거는 이번 사용자의 “새로 받은 주행 기준으로 업데이트하고 변경내용 적용하고 시뮬레이션 추가 조치” 요청이다. 공통 통합도 이 요청 범위로 적용했다.
- 대상: 공통 `farm_navigation`, `farm_bringup`, `harvest_robot`, 신규 `farm_tag_localization`/`farm_tag_amcl`; 전달 실물 config/tools/문서; sim 설정·영상 어댑터·launch·생성기·관련 시험. 상세는 [통합 변경 기록](../../docs/changes/APRILTAG_HANDOFF_INTEGRATION_20261013.md), [실행 안내](APRILTAG_INTEGRATION_20261013.md).
- 전후: graph_only 수확→graph 기반 진입/직선 작업/이탈 및 정방향 중간 출발; 태그 배치/가상 영상만 존재→정류·실제 검출·구간별 등록·공통 관측기·scan-sync AMCL 연결. 기존 RPP/오른팔 정차선/Teacher 및 ARRIVAL_THEN_ARM 보존. wire Section 추가 없이 sim 목표 좌표·방향으로 유일한 구간을 선택한다.
- 반복 ID는 `(section_id, family, tag_id)`로 등록하고 진입/이탈 중에는 적용하지 않는다. 실제 ROS 영상 검사로 발견한 detector QoS 불일치와 태그 x/z축 반전을 수정했다. 검출 신뢰도나 보정 pose를 정답으로 대체하지 않았다.
- 실물 영향: 담당자 전달 주행/설정 반영, 실물은 도착 전용·TF 복구 OFF 유지. 반복 구간 기능은 기존 고유 ID와 호환하고 USB 자동 실행은 real에 한정한다. 시스템 udev/sysctl/드라이버 설치·로봇 재배포 없음.
- 검증: 공통5+sim3 패키지 빌드, 공통123/태그65/시뮬23 회귀검사(평행 접근7개 중복), 경로371개, 실제 ROS AMCL22개 PASS. 실제 launch 기동 READY·기동 오류 없음·종료0. 실제 Isaac 새 정차 렌더240태그/1280×720·공유메모리 확인 후 Kit 종료 대기 timeout124. 해당 영상의 genuine ROS 검출/Journal/공통 관측기 연결10/10프레임 확인(ID104 기준 약1.44mm/0.171°); 한 장면 결과다. 영상 재생 후 upstream 정류/검출기 SIGINT 종료 -11 미해결(전달본 기존 이슈), 모든 시험 프로세스 정리. 전체 주행/팔 E2E 미실행.
- 환경: detector/image_proc 시스템 설치는 관리자 암호로 미완료; 임시 ROS 바이너리를 `sim/runs/apriltag_integration_20261013/deps/`에 풀어 실제 시험했다. 설치 명령과 재빌드/보정 ON 방법은 실행 안내 참조. 기본 보정 OFF.
- 로그·초기 실패·수정 후 결과: `sim/runs/apriltag_integration_20261013/`. 버전관리용 [검증 요약](changes/APRILTAG_VALIDATION_20261013.json), 변경 파일 패치 및 적용 명령은 [실행 안내](APRILTAG_INTEGRATION_20261013.md)에 연결했다. 기존 사용자 URDF/문서·다른 경로 삭제 상태 보존. 세 공용 문서에는 담당자 과거 이력을 요약/연결했고 전면 덮어쓰지 않았다.
- 복원: 이번 파일만 적용 전 사본/시작 커밋과 비교해 복원 후 재빌드한다. 기존 수정 문서/실물 설정 사본은 위 로그 폴더 `before/`. 보정만 OFF할 경우 tag_correction:=false이며 단계별 주행은 유지된다. 미커밋·원격 미반영, commit/push 미수행.

## SIM-SCOUT-MERGE-20261013 — 62a80ed 로컬 병합 및 장착 TF 수신 수정

- 승인: 사용자 `62a80ed`의 예찰 URDF/USD 반영 요청, 후속 “아니요, main에 예찰 변경만 반영”. 원격 heads 직접 조회로62a80ed=main 확인. 로컬 main a393f1a→62a80ed fast-forward; 어떤 브랜치도 삭제하지 않았다.
- 반영: 기존 URDF 두 개는 이미 같았고, 누락된 USD 장착 자산/단독·fleet 실행/카메라/TF 설정과 검사를 병합했다. 공용 문서3개 충돌은 양쪽 이력을 보존했다. 미커밋 AprilTag 소스·설정은 해시로 보존을 확인했고 기존 삭제55개 상태도 유지했다.
- 추가 수정: `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py`, `sim/tests/test_adapter_tf_contract.py`. 장착이 켜진 예찰의 정적 TF 기대값3→7개. 정확한 부모/자식/namespace를 검증하며 누락·중복·미등록 프레임은 거절한다. 이 수정 없이는 새 예찰 상태 패킷 전체가 무시된다. 공통·실물·수확 설정 영향 없음.
- 검증: 수신 계약11/진입점2/OpenUSD4 PASS, sim3패키지 재빌드 PASS. 실제 농장 binary USD에서 세션 장착·D435 렌즈 위치/방향·추가 TF4개·원본 보존 확인. 실제 Kit/PhysX/주행·ROS 전체 E2E는 이번 미실행.
- 로그·적용 전 사본: `sim/runs/scout_merge_20261013/`. 실행 중인 sim에는 소급되지 않으므로 새 overlay source 및 재시작 필요. 원격 main에 이미 있던 커밋만 가져왔고 새 commit/push 없음; 추가 호환 수정은 기존 AprilTag 작업과 함께 미커밋.
- 복원: 추가 수신 수정은 두 파일만 역적용한다. 장착 비활성화는 두 scout 프로파일의 `scout_mount_asset` 선택 해제 후 재시작한다. 이번 Git 병합을 되돌리려고 기존 미커밋 작업을 reset/clean하지 않는다.

- 원본 정리(2026-10-13): 전달 폴더 120개 파일의 반영 대상 존재, SHA-256 및 Git `bf10fcd` 원본 일치, 실행 symlink 의존성 없음을 확인하고 사용자 요청으로 전달 폴더를 삭제했다. `sim/runs/apriltag_integration_20261013/SOURCE_HANDOFF.md`와 `source_cleanup.json` 보존.
- 주행 시험: `sim/runs/navigation_smoke_20261013/harvest_runtime.yaml`과 관련 파일을 준비했다. 기존 수확 설정에서 완료 정책만 `ARRIVAL_ONLY_NO_HARVEST`로 변경하여 팔 동작 없이 시험한다. 운영 기본 `ARRIVAL_THEN_ARM` 유지. 환경 로딩·수확 launch 조립(태그 OFF)·SEC01 Goal 생성 확인, 실제 주행은 실행하지 않았다. 태그 ON 실행 전 시스템 `apriltag_ros`/`image_proc` 설치가 필요하다.


### 수확 진입 경계 오류 — 2026-10-13 (공통 변경 승인 대기)

- 사용자 시험 `smoke_7616aba8822b` 로그에서 SEC01 진입 `(-6.015,10.7)`에 실제 `(-6.01767356,10.71018813)`로 도착했다. 오차 0.010533m는 허용 0.02m 이내라 ARRIVED지만, `CorridorNavigator._plan_current()`의 시작점 앞 무오차 경계 검사에서 WINDOW_MOVE가 즉시 실패했다. 태그 보정의 원인 여부를 추측하지 않으며 확인된 직접 원인은 두 판정 기준의 불일치다.
- 최소 제안: `robot/ros_ws/src/harvest_robot/harvest_robot/corridor_navigation.py`의 작업 경로 시작 검사에서 기존 구간 내부 또는 진입점 반경 `arrival_tolerance_m` 이내를 허용한다. 목표 구간, 종료 경계, 전방·횡오차·방향 검사, 진입 생략 조건은 유지한다. 양 환경 공통 영향 때문에 AGENTS의 명시 확인 전 실제 소스에는 적용하지 않았다.
- 산출물: `sim/runs/corridor_entry_review_20261013/proposal.patch`, `corridor_navigation.py.proposed`, `verification.json`. 원래 실패를 실제 기록 좌표로 재현했고 수정안의 정상 연결 및 2cm 초과/횡오차/끝점 초과/후방 목표/방향 오류 거절·진입 생략 조건 유지 8개 오프라인 확인을 통과했다. 실제 ROS/Isaac 재주행은 하지 않았다.
- 승인 후 적용·관련 회귀검사·빌드·재시작 후 동일 목표 재시험이 다음 단계다. 실행 코드/설정 변경 없음, commit/push 없음. 제안 취소 시 산출물만 폐기하면 된다.


## SIM-SHARED-TAG-20261013 — 예찰 PiCam과 공통 주행 보정

- 승인: 사용자가 “예찰도 apriltag 기준으로 주행보정 … 동일 개념의 주행 시스템을 공유”하도록 요청했다. 공통 코드 변경을 포함한 직접 승인 범위에서 적용했다. 기준 `main/62a80ed`, 기존 미커밋 변경 보존, 이번 commit/push 없음.
- 공통 연결: `farm_navigation/tag_control.py`에 보정 권한 신호를 두고 두 로봇이 재사용한다. 수확 import 호환 경로 유지. ScoutNode의 `tag_correction`과 관측 이동 상태를 연결해 진입 완료 후 해당 구역 이동에서만 활성화하고 접근/이탈/정지 관측·완료/실패/취소 때 해제한다. 기존 공통 Navigator/Nav2, 업무 FSM과 관제 메시지는 유지한다.
- 시뮬 센서: 예찰 USD PiCam optical 프레임에 실제 Camera를 생성해 별도 RGB/CameraInfo/공유메모리로 연결했다. D435 과실 영상은 유지한다. 단독/fleet 모두 동작하며 장착 TF를 중복 생성하지 않는다. USD 원본 대신 세션 레이어를 사용한다.
- 시뮬 연결: `farm_sim_runtime/tag_localization.py`가 두 로봇의 정류·검출·기록을 공통 조립한다. `all.launch.py tag_correction:=true`는 선택한 예찰·수확 모두에 적용되고 두 로봇이 같은 `farm_tag_localization`/`farm_tag_amcl`을 사용한다. namespace·보정 권한·캡처 폴더는 각각 분리한다. 실행 중인 Isaac/ROS는 재시작해야 한다.
- 자산: 동일 240개 구역 태그 지도와 계산 코드를 사용한다. PiCam URDF 외부변환, 명시적인 시뮬 pinhole 광학, 약1.1m 관측 거리와 약48px 태그 조건은 예찰 프로파일로 분리했다. 실물 PiCam 교정값이 아니며 수확 자산은 기존 SHA와 일치한다.
- 확인: 공통4·시뮬3패키지 빌드, 수확82·현행 예찰 통신6·예찰 보정수명5·시뮬 태그/카메라26·공통 launch9 검사 PASS. OpenUSD 장착7검사 PASS. 구형 `tests/test_scout_state_flow.py`는 30개 중20오류: 기존 HEAD의 `section_id` 계약에 옛 fixture가 `section_ids`를 보내는 불일치이며 이번 범위에서 변경하지 않았다.
- 실제 Isaac PiCam 1280×720 렌더·공유메모리 전달과 ROS 정류→검출→Journal→공통 관측기 5/5프레임 수신/채택을 확인했다. 초기 배치가 아니라 RGB와 함께 받은 CameraParams로 촬영 시점 좌표를 비교했다. 해당 정차 장면은 횡방향 약3.72cm·진행방향7.16cm·yaw3.41° 오차로, 시험의 축별5cm 정확도 조건을 **실패**했다. 검출 해상도 축소 해제(decimate1)로 개선되지 않았다. 작은 정면 태그의 자세 추정 민감도가 확인됐으나 이동 중 성능·전체 원인은 추가 검증 대상이다. 정밀 주행 성공으로 기록하지 않는다.
- 종료 제한: Isaac은 영상/메타데이터 저장 후 종료 대기로 timeout124. ROS 검출기도 SIGINT 시 -11 또는 종료 대기로 시험 소유 프로세스만 강제 종료한 기록이 있다. 정상 종료 시험으로 기록하지 않는다. 실물·폐루프 실제 주행은 실행하지 않았다.
- 기록: `sim/runs/shared_tag_navigation_20261013/`의 빌드/회귀 로그, 초기·촬영시점 렌더, ROS replay 결과 및 [검증 요약](changes/SHARED_TAG_NAVIGATION_20261013.json). 실행 안내는 [시뮬 통합 안내](APRILTAG_INTEGRATION_20261013.md).
- 남은 작업: 예찰 실제 카메라 교정 및 관측 모델/정면 소형 태그 정확도 개선, 이동 중 보정 평가. 기존 수확 진입 허용오차 수정은 여전히 별도 제안 상태이며 이번 변경에 적용하지 않았다.

- 복원: 이번 변경 파일에서 공통 신호 이동·예찰 연결·추가 센서/프로파일만 되돌린 후 빌드/재시작한다. 단순 보정 OFF 비교는 `tag_correction:=false`로 가능하며 이전 인수/예찰 장착 변경 전체를 reset하지 않는


## 2026-10-18 — 공통 수확량 집계 연결

- 구분: 공통 구현 + 환경별 선택 설정. 사용자 “1단계 부터 진행하자” 승인. 기준 8466ac1.
- 변경 전: 작업별 실적 전달과 외부 적재 Topic만 연결. 변경 후: 공통 HarvestLoad에 성공 증가분 누적, 기존 호출 상태와 인계 완료 초기화 연결.
- 대상: harvest_robot의 harvest_load/node/communication/configuration/transfer_communication, 실물 harvest_real.json, sim harvest_task.json, 관련 시험 및 상태·결정 문서.
- sim 설정은 arm_feedback을 선택하되 transfer OFF와 미확정 호출값 유지. 기존 Teacher/팔 Action/주행 변경 없음. 실물은 이동 전용 정책과 장치 미설정 유지.
- 오프라인 관련 29개 PASS. ROS/Isaac/실물 미실행. 원격 미반영·사용자 PC 적용 전 패치.
- 되돌림: 패치 역적용 검사 후 해당 변경만 복원. 상세 farm_project/docs/changes/HARVEST_LOAD_COMMON_20261018.md 참고.


## 2026-10-18 — 공통 팔 Action 선택과 Status 연결 2단계

- 구분/승인: 공통 변경. 사용자 “알겠어 진행해줘”, PC 코드와 모의 시험 범위.
- 대상: harvest_robot의 arm_client/node/mission/communication/status, 공통 시험2개 및 sim 기존 팔 연결 시험, PROJECT_STATE/DECISIONS/상세 변경 문서.
- 전후: sim에만 허용하던 팔 Action을 명시 설정 시 양 환경에서 연결. 팔 작업 중 HARVESTING 보고 및 서버 연결 기반 준비 상태. 팔 비정상 종료 후 다음 이동 차단 보완.
- 실물 영향: 운영 설정/장치 주소/주행/지도/태그/통신 환경 변경 없음. sim 정상 수확 흐름 유지; sim도 비정상 팔 종료 후 자동 다음 이동은 차단한다.
- 검증: 오프라인43개 PASS, ROS/Isaac/실물 미실행. 패치 적용 검사 및 결과 파일 일치 검사 수행. 원격 미반영.
- 복원: 2단계 패치만 역적용 검사 후 복원. 1단계 누적량 패치는 유지. 상세 HARVEST_ARM_COMMON_STAGE2_20261018.md.


## 2026-10-18 — 공통 인계 Spin 회전 연결 3단계

- 구분/승인: 공통 변경. 사용자 파일별 제안 및 제자리 반대각 복원 승인, PC 모의 검증 범위.
- 대상: farm_navigation/spin_client, harvest_robot의 transfer_rotation/transfer_devices/transfer_communication/configuration/node, 신규 시험2개 및 공통 상태·결정·상세 문서.
- 전후: 기존5개 서비스 방식 보존, 명시 선택한 환경은 차체 Spin과4개 비차체 장치 동작으로 분리. 정/역각 회전 및 실제 관측 기반 정지·위치·방향 확인. 실패 시 자동 보정 없음.
- 영향: 실물/시뮬 운영 프로파일·속도·footprint·지도·태그·통신 환경은 변경하지 않는다. 새 연결은 운영에서 비활성. 예찰/운송 기존 주행 코드 변경 없음.
- 검증: 관련 오프라인62개 PASS, 패치 적용 검사와 구문 검사 통과. ROS/Isaac/실물 미실행. 기준8466ac1 + 1·2단계, 원격 미반영.
- 복원:3단계 패치만 역적용 검사 후 복원. 상세 HARVEST_ROTATION_COMMON_STAGE3_20261018.md.


## 2026-10-18 — 배출 Action 단일 요청 4단계 설계

- 구분: 공통 설계 문서. 사용자 확정 및 설계 요청 승인.
- 대상: PROJECT_STATE §74/75, DECISIONS D-044, 상세 HARVEST_DISCHARGE_ACTION_STAGE4_DESIGN_20261018.md, 이 기록.
- 내용: Jetson 한 번 요청으로 열기·배출·닫기, 전체 완료 후 인계 완료 보고. 새 어댑터 복원에서 닫기 중복 요청 금지. 공통 미션 순서 유지.
- 영향: 런타임/환경 설정 변경 없음.3단계까지의 코드는 유지. 실제 Action 규격 미정으로4단계 구현 완료 아님.
- 검증: 문서 증분 패치 적용 검사 및 diff 검사. 코드 변경이 없어 기존62개 시험 반복 없음. ROS/Isaac/실물 미실행.
- 복원: 이 문서 패치만 역적용 검사 후 복원. 원격 미반영.


## 2026-10-18 — 공통 배출 결과 모의 검증 (승인 후 적용)

- 승인: 사용자가 Result 필드 유지/제외와 감지 방식 보류를 결정하고 PC 모의 검증 승인.
- 대상: harvest_robot/discharge_result.py, test/test_discharge_result.py, 공통 PROJECT_STATE/DECISIONS/4단계 상세 문서.
- 전후: 설계만 존재하던 전체 완료 판정을 독립 공통 모듈로 추가. 운영 런치/Trigger 어댑터/FSM/환경 설정은 그대로이며 시험에서만 새 판정을 조합.
- 이유: 배출 완료와 닫기 실패를 구분하고 미완료·이전 응답이 완료 보고/역회전을 허용하지 않음을 검증.
- 실물/시뮬: 동일 공통 판정 사용 가능. 실제 연결 활성화 없음, 지도·주행·태그·Zenoh 변경 없음.
- 직접 검증: 새13개, 기존 회전12개 PASS(총25). 실제 ROS/Isaac/Jetson/실물 미실행. 전체 기존 묶음 재실행 없음.
- 복원: 이번 증분 패치만 역적용 검사 후 역적용. 기존 단계 변경 보존. 원격 commit/push 없음.


## 2026-10-18 — 공통 배출 Result 복수 오류 배열 (승인 후 적용)

- 승인: 사용자가 discharge_complete 제거 및 error_codes 배열 전환 승인.
- 대상: discharge_result.py, test_discharge_result.py, PROJECT_STATE/DECISIONS/4단계 상세 문서.
- 전후: 별도 완료 bool/단일 오류/외부 error_free 대신 현재 ID·Action 성공·빈 오류 배열로 전체 성공 판정. 복수 실패 원인 보존.
- 직접 검증: 관련15개 PASS. 배출·닫기 동시 실패 시 완료 보고/역회전 차단. 이전 회전 전체 묶음 반복 없음.
- 실물·시뮬 설정/운영 연결/주행/지도/태그 변경 없음. 실제 ROS/Isaac/Jetson/실물 미검증. 원격 미반영.
- 되돌림: 직전 mock 패치를 유지하고 이번 errors 증분 패치만 역적용 검사 후 역적용.


## 2026-10-18 — 공통 Discharge Action 연결 (승인 후 적용)

- 사용자 승인: 합의한 오류 배열 규격으로 실제 Action 정의·클라이언트·장치 어댑터 및 PC 시험 서버 구현.
- 대상: farm_interfaces Discharge.action/CMakeLists, harvest_robot discharge_client/discharge_devices/configuration/transfer_communication, test_discharge_client, robot/tools/discharge의 공통 PC 시험 도구, 상태·결정·상세 문서.
- 전후: 결과 판정만 존재하던 구조에서 명시 설정 시 실제 ROS Action 전송과 기존 인계 흐름 조합 지원. TransferMission/차체 회전 정책은 동일, 기존 서비스 방식 기본값 유지.
- 실물·시뮬 동일 연결 사용. 실물/시뮬 운영 프로파일·지도·태그·Nav2·Zenoh 변경 없음. Action 방식은 운영 활성화하지 않음.
- 직접57개 오프라인 PASS(client12/result15/rotation12/load18). Python/Bash 구문 PASS. ROS 빌드/실제 DDS/Zenoh/Isaac/Jetson·실물 미실행. PC 실제 ROS 시험 스크립트 제공.
- 되돌림: 이번5단계 증분 패치만 역적용 검사 후 역적용하고 인터페이스 사용 환경을 해당 버전으로 재빌드.4단계 결과 판정은 보존. commit/push/배포 없음.


## 2026-10-18 — PC 배출 Action 검증 결과 및 Jetson 인계 문서

- 사용자 승인: PC 검증 결과 반영과 담당자 전달 규격/남은 합의 정리.
- 대상: docs/PROJECT_STATE.md, changes/HARVEST_DISCHARGE_ACTION_STAGE5_20261018.md, 신규 docs/JETSON_ARM_COMMUNICATION_HANDOFF_20261018.md, 본 이력.
- 사용자 제공 로그로 PC 오프라인57개·farm_interfaces 빌드·ROS 송수신4개 PASS 확인. Jetson·Zenoh 기기간·Isaac·실물 검증과 구분.
- 배출 Action 현재 규격과 미정인 수확 Action/Status Topic/감지/취소 물리 동작을 구분해 전달 문서화. 새 운영 계약이나 설정을 추가하지 않음.
- 실행 코드/실물·시뮬 설정 영향 없음. 문서 증분 패치 적용·형식 검사만 실행. 코드 재검증 반복 없음. 담당자 직접 메시지 전송 및 commit/push/배포 미수행.
- 되돌림: 이번 문서 증분 패치만 역적용 검사 후 역적용.


## 2026-10-18 — 시뮬 공통 수확 통신 인계 자료

- 사용자 승인: 시뮬 전달 문서/코드 묶음/PC 커밋 준비.
- 대상: docs/SIM_HARVEST_COMMUNICATION_HANDOFF_20261018.md, PROJECT_STATE, 본 이력. 실행 코드/환경 설정 변경 없음.
- 공통 구현을 복사하지 않고 시뮬 장치 및 환경 설정으로 연결하는 기준, 미확정 수량/수확 Action/Status와 검증 한계 명시.
- 전체 변경 패치/파일 해시와 PC 커밋·bundle 생성 도구 제공. 실제 사용자 PC 커밋·원격 반영은 별도 결과 확인 필요.
- 문서 증분 및 전체 패치 적용·내용 검증 수행. 코드 시험 반복 없음. 되돌림은 문서 증분만 역적용 검사 후 역적용; 기존 코드 단계 보존.

## ARC-ISOLATED-TRIAL-20261019 — 기존 주행 유지 곡선 시험

- 사용자 승인: 기존 주행 서버를 변경하지 않고 공통 곡선 플러그인을 별도 서버로 시험한다. 반경 0.10m 후진 왼쪽 90도. 운영 미션에는 연결하지 않는다.
- 기존 nav2.yaml·BT·지도·태그·드라이버 불변. 독립 서버는 기존 costmap 실행 수치를 복사하고 별도 토픽에 출력한다. execute에서만 검사 후 기존 smoother로 전달한다. 시뮬 기본 동작 변경 없음.
- 오프라인 36개 시험 통과. 독립 ROS 서버/물리 곡선은 아직 미검증. 이번 격리를 기존 106 실패 원인 해결로 기록하지 않는다.
- 상세/파일/검증/복원: docs/changes/HARVEST_ARC_ISOLATED_TRIAL_20261019.md (farm_project 기준). 미커밋 전달본, 자동 commit/push 없음.

## ARC-SUCCESS-PRESERVED-20261019 — 후진 곡선 실물 성공 보존

- 기존 주행 유지 + 독립 controller로 반경0.10m 후진 왼쪽90도 성공. 첫 실행 로그/정지/기존 파라미터 불변 확인, 재시험 동일 동작은 사용자 확인. 두 번째 수치는 백업 결과에서 별도 확인.
- 근거·실행·수치·설계·미검증·복원: docs/changes/HARVEST_ARC_SUCCESS_20261019.md (farm_project 기준).
- PC/로봇 소스·설치본·완료 시험·주행 입력 백업: /home/eunbi/harvest_arc_success_20261019_vtUw5K; BACKUP_RESULT.json과 파일별 SHA256 기록.
- 복귀 곡선·실제 도킹/인계·후속 주행 검증은 아직 미완료. 다음 단계는 보존 확인 이후. 자동 commit/push 없음.


## WALL_REFERENCE_CAPTURE_20261020 — 2026-10-20

- 사용자 승인: 이동 없는 라이다 기준 수집·공통 벽 추정 준비. 신규 파일만 추가.
- 기존 설치 PoseProvider/MotionMonitor 재사용. 기존 후진 곡선·Nav2·지도·태그·FSM·Jetson 설정 변경 없음.
- 원격 작업 기준 6f21119, main e735dc9, 통합 fb5c61a. PC 미커밋 파일 보존.
- 오프라인 14개 및 정적 검사 통과. ROS 실수집·Isaac·실물 전진은 미검증.
- 벽 후보는 자동 주행 목표로 승인하지 않음. 실제 기준 자세/벽 선택은 수집 후 확인.
- 상세: docs/changes/HARVEST_WALL_REFERENCE_20261020.md. 자동 커밋·배포 없음.


### WALL_CAPTURE_OPTIONAL_CONTEXT_20261020

- 초기 위치 없는 정지 측정을 위해 map TF/footprint를 선택 입력으로 수정. 필수 scan/센서 TF/odom/정지 확인 유지.
- map/footprint 조회 대기는 각각20ms 설정. 미수집 이유를 기록하며 가짜 외곽 간격을 만들지 않는다.
- 실제 배포 수집기 main을 모의 ROS로 실행한16개 시나리오 통과(5개 test method). 기존 벽 분석14개 통과.
- 실제 ROS/DDS/실물 수집은 미검증. Nav2 활성화나 주행 준비 완료를 의미하지 않는다.
- 기존 곡선/주행/설정/런치 변경 없음. 상세 HARVEST_WALL_CAPTURE_FIX_20261020.md.


### HARVEST_ARC_MONITOR_FIX_20261020

- 사용자 승인: 곡선 시험 측정속도 순간/지속 초과 구분 및 공통 MotionMonitor 연결.
- 기존 곡선/명령gate/Nav2/주행/지도/태그 불변. 공통 새 감시 모듈과 시험별 정책 추가.
- 오프라인21개 및 정적 비교 통과. 실제 ROS·실물 재시험 미실행.
- 정책·근거·한계·파일 범위: docs/changes/HARVEST_ARC_MONITOR_FIX_20261020.md.


## 공통 벽 정렬 제어기 추가 — 2026-10-20

- 사용자 별도 제어기 구현 승인. wall_reference/TF/MotionMonitor/Nav2Client/측정 감시 공통 모듈 재사용.
- 목표 중심–벽0.4325m/정면0rad, 실물 시험값은 별도 JSON. 기존 주행·지도·태그·후진곡선 코드/설정 수정 없음.
- 새 Nav2 벽 제어기/완료 판정기 및 독립 시험 어댑터. 운영 FSM·복원 연결은 미구현.
- 직접 검증: Python14개, C++33개 assertion, 실제 라이다164프레임 재생. ROS/실물 실행 성공을 의미하지 않음.
- PC 새 패키지 빌드·configure 검사부터 진행. 로봇 배포/이동/자동 커밋 없음.
- 상세 파일/후보값/남은 검증/복원: docs/changes/HARVEST_WALL_ALIGNMENT_COMMON_20261020.md (farm_project 기준).
- 복원 방향은 곡선 시작 전 방향벡터, 위치 목표는 윈도우 좌표. 실제 출발 자세도 저장하며 현재 위치추정값을 덮어쓰지 않는다.


## 벽 정렬 PC ROS 빌드·로딩 확인 — 2026-10-20

- 사용자 실행 출력 확인: farm_wall_controller colcon build 성공, CTest 1개 실패0, WallController/WallGoalChecker configure 후 inactive 확인.
- PC 빌드: /home/eunbi/harvest_wall_pc_9xD536, 로딩 로그: /home/eunbi/harvest_wall_load_9quz5wa6/controller.log.
- Python14개·C++33 assertion 통과. Action Goal·차체 이동은 없었다.
- 아직 ROS 접근 완료/취소/충돌 차단 및 실물 벽 접근은 미검증. 로봇 배포 결과는 다음 출력으로 구분한다.


## 벽 관측 시각 진단 보완 — 2026-10-20

- 새 벽 시험 관측기/실행기만 보완. 구독 큐 최신 1개, 단계별 시각 기록, plan 지속 관측, 중복 종료 처리.
- 0.3초 기준 및 기존 주행·곡선·지도·태그·제어 설정 유지. Python 단위 9개 통과; ROS/실물 보완 효과 미검증.
- docs/changes/HARVEST_WALL_TIMING_20261020.md 참고.


## 벽 계산·종료 순서 개선 — 2026-10-20

- 새 벽 시험 관측기/실행기만 보완. 벽 후보 일괄 계산 및 후보 재사용, 콜백 종료 확인 후 연결 객체 제거.
- 0.3초 기준 및 기존 주행·곡선·지도·태그·제어 설정 유지. 벽 결과 369개 비교 및 종료 4개 검사 통과; ROS/실물 보완 효과 미검증.
- docs/changes/HARVEST_WALL_PERFORMANCE_20261020.md 참고.


## 벽 종료 API 호환 수정 — 2026-10-20

- 새 벽 시험 관측기/실행기만 보완. 실제 shutdown 함수 서명에 맞는 인자 선택.
- 0.3초 기준 및 기존 주행·곡선·지도·태그·제어 설정 유지. 종료 API 호환 6개 검사 통과; ROS/실물 보완 효과 미검증.
- docs/changes/HARVEST_WALL_SHUTDOWN_COMPAT_20261020.md 참고.


## 벽 실제 속도 전달 기록 — 2026-10-20

- 새 벽 시험 관측기/실행기만 보완. 실제 속도 전달 단계와 모터 입력 토픽 및 odom 동시 기록.
- 0.3초 기준 및 기존 주행·곡선·지도·태그·제어 설정 유지. 실제 전달 콜백 4개 검사 통과; ROS/실물 보완 효과 미검증.
- docs/changes/HARVEST_WALL_COMMAND_TRACE_20261020.md 참고.


## 벽 제어 최소 속도 보완 — 2026-10-20

- 공통 벽 제어 최소 속도 선택형 파라미터 추가. 기본 0으로 기존 동작 유지; Vic Pinky 벽 시험에만 설정.
- 기존 주행·곡선·지도·태그·드라이버 보존. C++ 44 assertion 및 정수 RPM 모형 648조건 통과. ROS/실물 보완 효과 미검증.
- docs/changes/HARVEST_WALL_MINIMUM_20261020.md 참고.


## 벽 정렬 후 접근 선택 옵션 — 2026-10-20

- 공통 벽 제어 sequential_alignment 옵션 추가. 기본 false로 기존 동작 유지; Vic Pinky 벽 시험에서만 true.
- 기존 주행·곡선·지도·태그·드라이버 보존. C++ 108 assertion 통과. 정렬 후 정지 상태 0.5초 유지 후 접근, 접근 중 각도 이탈 시 정지 후 재정렬. ROS/실물 효과 미검증.
- docs/changes/HARVEST_WALL_SEQUENTIAL_20261020.md 참고.


## 곡선 사전 검사 정확한 셀 비교 — 2026-10-20

- 공통 arc_clearance의 사각형 셀 직접 비교 및 연속 구간 적응 검사. footprint·패딩·경로·실행 중 Nav2 충돌 검사 유지.
- 실측 실패 재현/새 검사 통과, 3mm 접근 변형 차단, 단위 검사 12개 통과. ROS·실물 효과 미검증.
- docs/changes/HARVEST_ARC_CLEARANCE_EXACT_20261020.md 참고.


## 벽 시험 콜백 종료 순서 보완 — 2026-10-20

- 벽 시험 및 관측기만 단일 콜백 실행기로 전환. spin 중단·스레드 join 후 실행기와 객체 제거. 콜백 예외는 실패로 보고.
- 주행/곡선/벽 제어값 변경 없음. 단위 검사 8개 통과. ROS 종료 반복 검사는 패키지 실행 로그로 별도 판정하며 실물 정렬 성공은 미검증.
- docs/changes/HARVEST_WALL_LIFECYCLE_20261020.md 참고.


## 벽 정렬 전용 각도 보정 — 2026-10-20

- target_angle 기본 0rad, Vic Pinky 벽 시험 +2.45도. C++ 제어/완료 판정과 Python 시작/최종 판정에 동일 적용.
- 실측 폭 50cm, 왼쪽 16cm/오른쪽 13.3cm와 라이다 -0.636도에 근거한 시험값. TF/주행/곡선/속도/허용오차 유지. 실물 효과 미검증.
- docs/changes/HARVEST_WALL_ANGLE_OFFSET_20261020.md 참고.


## 벽 정렬 미세 회전 — 2026-10-20

- 사용자 승인: 선택형 짧은 회전→정지 확인→새 관측 재판단. Vic 시험만 활성화, 각도 허용오차 0.3도, 보정 2.45도 유지.
- 오프라인 공통 C++ 및 구동 지연 모형 검증. 실물 성공 미확인. docs/changes/HARVEST_WALL_FINE_20261020.md 참고.


## 벽 정렬 연속 P 복원 — 2026-10-20

- 사용자 승인: 펄스 제거, 보정 2.45도 유지. 연속 P/순차 정렬/허용오차 0.5도로 복원. 정확한 곡선 충돌검사 수정본 보존.
- 오프라인 공통 C++ 회귀검증. 실물 성공 미확인. docs/changes/HARVEST_WALL_CONTINUOUS_RESTORE_20261020.md 참고.


## 벽 정렬 성공 보존 및 접근 속도 시험 — 2026-10-20

- 성공: 연속 P·보정 +2.45도·허용각도 ±0.5도, 거리오차 +3.39mm/보정각도오차 -0.0094도. 사용자 자연스러운 동작 확인. 물리 각도 정밀도와 라이다 판정은 구분.
- 원본 보존: /home/eunbi/harvest_wall_success_20261020_KVfEUy
- 사용자 승인: 벽 시험 max_linear만 0.01→0.02m/s. 회전/곡선/공통 로직 불변. 속도감시 0.025m/s 유지. 새 속도 실물 성공 미확인.


## 2026-10-20 공통 실행 정리

[공통/사용자 구현 승인] 명시적 경로/완료 판정을 기존 공통 코드에 추가. 기본 그래프 주행과 sim/real 설정 회귀 검사 통과. 시뮬 런치·Isaac 실행은 하지 않았다. 새 실물 설정을 시뮬에 자동 적용하지 않는다.
상세 파일·검증 한계·복원 방법: `../../docs/changes/HARVEST_COMMON_EXECUTION_20261020.md`. commit/push 없음.


## 2026-10-21 PC ROS preflight 수정

사용자 PC의 독립 설치·실제 ROS 타입 검사까지 통과했으나, WallGoalChecker에 일반 checker의 미선언 xy_goal_tolerance 등을 함께 요청하여 실제 ROS 계약 검사가 실패했다. 오프라인 대역이 누락 항목을 None으로 돌려주는 방식이어서 이를 놓쳤다. plugin 종류를 먼저 읽고 Simple/Stopped의 기존 키 또는 wall_alignment.*만 조회하도록 수정했다. 필수 벽 키가 없는 경우의 실패는 유지한다. 테스트 대역에 미선언 항목 전체 실패를 반영하여 수정 전 오류를 재현하고 수정 후 공통 주행/명시적 경로 26개를 통과했다. 일반 Simple/Stopped 검사와 허용오차 초과 거절도 확인했다. PC 실제 ROS 재검사는 전달 스크립트에서 수행하며 이 수정본의 실물 검증은 미완료다. 제어기·주행 수치·FSM 변경 없음. 원본/로그/독립 빌드 경로는 Downloads 하위다.


## 2026-10-21 윈도우 복귀 기반 구현(로컬, 미배포)

사용자 승인으로 기존 곡선 플러그인에 전진 우회전 역경로를 추가하고 harvest_robot.transfer_restore에 기준 저장/역원호/재진입 검사/공통 Navigator 완료 판정 연결부를 구현했다. 윈도우 2cm·저장 방향 1°는 초기 기준이다. 기존 벽/후진 설정·FSM은 유지한다. Python 172개, 양방향 C++ 이상 궤적 60개, 기존 후진 명령 동등성 4,545조건 및 벽 861 assertion 통과. ROS 빌드/실물 복귀 미검증. 벽 이탈·재진입 보정·운영 호출은 미연결이며 전체 복귀 완료로 취급하지 않는다. 원본/빌드/로그는 Downloads 하위. commit/push 없음. 상세: docs/changes/HARVEST_WINDOW_RESTORE_BASE_20261021.md.


## 복귀 플러그인 격리 ROS 검사 준비 — 2026-10-21

사용자 PC에서 복귀 기반 farm_arc_controller 빌드 및 CTest 2개가 통과했다. 실제 동적 로딩과 FollowPath 실행은 아직 검증 전이다.
기존 CommandGate에 direction 인자를 추가한다. 기본 reverse_left의 범위와 호출은 유지하며, 명시적인 forward_right에서만 속도 부호를 대칭으로 검사한다. 속도 상한, 시간 초과, 충돌 시 차단, 종료 차단은 유지한다.
검사 도구는 PC 전용 domain 95 / localhost / 고유 namespace에서 실제 controller_server와 공통 gate를 사용한다. TF와 odom은 이상 평면 모델이며 모터 속도 발행은 없다. 기존 후진 좌회전, 역경로 전진 우회전, Goal 취소 후 0 출력, 잘못된 경로 거절과 종료를 검사한다. 장애물 충돌 실험 및 하드웨어 성능을 입증하는 검사는 아니다.
벽 정렬 설정과 제어기, 곡선 충돌검사 및 주행 설치본은 변경하지 않는다. 복귀 기준 저장, 벽 이탈/재진입 실행, 전체 미션 연결은 후속 작업이다. 커밋은 사용자가 VS Code에서 진행한다.


## 전진 우회전 단독 실물 시험 준비 — 2026-10-21

사용자 PC에서 실제 Nav2 플러그인의 후진 좌회전/전진 우회전, 취소·정지, 변형 경로 차단과 정상 종료가 확인되었다. odom은 이상 모델이며 실물 시험은 아직 아니다.
기존 arc_isolated/arc_trial에 --return-from을 추가한다. 새 후진 성공 기록의 원호를 역순으로 사용하며, 부팅 ID 및 odom publisher GID, 설정 해시, 곡선 설정과 경로를 확인한다. 오래된 기록과 재시작한 odom 기록은 거절한다.
복귀 시작 자세는 기존 endpoint 8mm 및 방향 1도 이내여야 한다. 복귀만 임시 goal checker를 0.5도로 설정하고 정지 후 출발점 8mm/1도를 판정한다. 기본 후진 profile과 벽 정렬은 유지한다. 공통 Navigator/Nav2Client/MotionMonitor/CommandGate 및 check_grid/check_motion을 재사용한다.
실측 속도 감시는 부호만 반전해 동일 한도를 사용한다. 역경로와 현재 시작 자세를 기존 footprint·costmap으로 검사하며 Nav2 실시간 충돌 검사도 유지한다. 판정 실패 시 자동 자세 복원이나 충돌 임계 완화는 없다.
단독 시험은 후진 곡선 직후 벽 접근을 하지 않은 상태에서 복귀한다. 벽 이탈/재진입과 전체 미션 연결은 후속 단계다. 백업·빌드·기록은 Downloads에 저장하며, 준비 스크립트는 실제 이동을 실행하지 않는다.


## 복귀 전체 순서 검증 후보 — 2026-10-21 패키지명

사용자 승인: 코드와 검증 준비 후 실물 실행. 기존 보존 스냅샷에서 후보를 작성했으며 최신 원격 Git 대조·커밋·로봇 적용은 하지 않았다.
출발 기준 저장 → 기존 후진 좌회전 → 기존 벽 정렬 → StationReverse 기반 RPP 후진 → 기존 SpinClient를 통한 재진입 방향 맞춤 → 기존 ArcController 전진 우회전 순서다.
공통 Navigator/Nav2Client/MotionMonitor와 정지 확인을 재사용한다. 새로운 모터 제어기와 펄스는 추가하지 않는다. 벽 성공 설정과 곡선 충돌 검사 원본은 유지한다.
동일 cycle/odom 세션·직전 성공 결과 해시·정지 이후 자세·단계 순서를 확인한다. 재시작/실패/진행 중 기록은 자동 재시도하지 않는다. 출발 시점 map/odom 자세를 저장하며 마지막 위치는 저장한 map 자세 기준 2cm/1도다. 그래프 윈도우 도착 판정과는 별개인 시험 기준이다.
RPP 후진의 중간 방향 허용은 15도이며 뒤따르는 Spin 재진입 기준은 1도다. 벽 정렬 0.5도 기준은 유지된다.
직접 수행: Python 단위/회귀 및 구문 검사. 실제 ROS, 실제 장치, 전체 실행 도구 E2E는 미실행. 격리 ROS 검사도 실제 벽 제어 단계 대신 이상 모델 위치를 설정하므로 전체 미션 E2E로 표현하지 않는다.
이번 배포물은 Downloads 안에서 후보를 빌드·검사하는 용도다. 기존 소스/설치본을 적용하지 않으며 실물 실행 래퍼는 차단한다. 되돌리기는 후보 폴더 삭제만으로 충분하다. 다음 단계는 PC ROS 검사 결과 확인 후 전체 실행 경로 검증이다.

수정 기록 — 2026-10-21: PC에서 ROS Python 경로 덮어쓰기와 실제 StationReverse 플러그인 계약 불일치가 발견되어 ROS 동작 검사는 시작되지 않았다. ROS 환경 경로를 보존하며, 기존 farm_nav2_controller::ReverseRegulatedPurePursuitController를 선택한다. 기존 C++ 구현은 수정하지 않는다. 회전 속도는 격리 후진 gate 범위에 맞춰 0.03rad/s로 설정한다. 두 플러그인 패키지를 독립 빌드하고 로딩 prefix를 검사한다. 전달하는 station_reference.json을 직접 사용하는 설정 생성/오류 플러그인 차단 회귀 3개를 추가했다. ROS 결과는 여전히 미확인이다.

2026-10-21 v3: 사용자 PC의 v2 결과는 후진/회전/복귀/취소/잘못된 경로/후진 충돌까지 통과했으나 기본 Spin에서 비영 명령 후 충돌 중단으로 전체 실패했다. 기본 Spin 자체를 수정하거나 무출력 통과로 간주하지 않는다. 기존 check_grid를 alignment_clearance로 재사용해 회전 요청 전과 전달 전 남은 회전 footprint를 검사한다. 기존 SpinClient를 실제 ROS 정상 회전 검사에 사용한다. 장애물 사전 거절과 사전 검사 우회 고장 주입에서 실제 모델에 전달되는 비영 명령 0회를 별도로 요구한다. 원본 Spin 비영 명령 수를 숨기지 않고 기록한다. 9개 PC ROS 검사는 아직 미실행이며 전체 실행 도구 E2E/실물 배포는 보류다. 데이터 갱신 사이의 장애물 변화까지 무조건 방지한다고 주장하지 않는다.


## v4 footprint 좌표 입력 수정 — 2026-10-21 패키지
사용자 PC의 v3는 기존 후진 좌회전과 RPP 후진 뒤 ‘중심 대칭 사각 footprint 확인 실패’로 중단했다. 전체 성공으로 취급하지 않는다.
원인 후보를 코드로 재현했다: world footprint의 발행 시각과 현재 자세가 다른 상태로 역변환하면, 2mm 이동 또는 0.004rad 회전만으로 같은 오류가 발생한다. 사용자 로그에는 두 입력의 원시 시각/좌표가 없어 현장 실패의 시차를 확정한 것은 아니다.
회전 검사에서 costmap의 차체 좌표 footprint 및 padding으로 현재 자세의 형상을 구성한다. 발행 polygon은 시각·frame·크기 일치 검사에 계속 사용한다. 점간 거리 비교만으로 과거의 위치·방향과 현재 자세를 섞지 않고 동일 형상인지 확인한다. 설정/발행 형상 크기 불일치는 차단한다. arc_clearance/check_grid와 사각형 허용 오차, 장애물/unknown 차단은 변경하지 않았다.
실행 후보와 PC ROS checker 모두 같은 alignment_footprint/alignment_clearance를 호출한다. 실제 costmap 파라미터를 조회하여 검사 설정과 대조한다. 실행 후보는 odom/footprint 기준 frame이 다르면 공통 PoseProvider로 평면 원점/축 일치를 확인하며 다른 회전 중심을 추정해 통과시키지 않는다.
직접 검증: 기존 오류 재현 3조건, 발행 자세 지연 조합 200조건의 정상/장애물/unknown 검사, padding 영역 접촉 차단, 형상 변경 차단, 실제 checker 콜백을 추출한 실행 검사, 기존 회귀·구문 검사. ROS Jazzy가 이 작업 환경에 없어서 v4 실제 ROS 9항목은 미실행이다. 사용자 PC에서 그 검사를 수행하도록 패키지를 제공한다. 전체 도구 E2E 및 실물 복귀는 미검증이며 실물 실행 래퍼는 계속 차단한다. 기존 프로젝트/설치본 수정, 로봇 접속, commit/push는 하지 않았다.


## 실제 실행 도구 연결 검사 준비 — 2026-10-21
사용자 PC에서 v4의 실제 ROS 9개 검사가 통과했다. 후진/재진입 Spin/전진 복귀와 충돌 전달 차단 및 정상 종료가 확인되었다. 모델 odom이며 실물·전체 실행 도구 E2E는 아니다.
실제 arc_trial.py의 릴레이·watchdog와 restore_sequence.main 호출 경계를 추가 검사한다. 벽 이후 retreat 선택, 단계별 plan/execute 명령, 기록 변경·잘못된 cycle·실패·정지 미확인 시 다음 요청 차단을 확인한다. 하위 프로세스 응답을 대역으로 주입하는 순서 검사와 실제 ROS를 구분한다.
arc_trial.py의 기존 속도 전달 검사에 6축 유한성 검사를 추가한다. 사용하지 않는 축의 NaN도 0 출력 후 차단한다. 기존 공통 Navigator/Nav2Client/PoseProvider/MotionMonitor/SpinClient와 충돌/속도/정지 기준은 유지한다.
새 PC 검사에서는 복사한 모듈 함수 대신 후보 arc_trial.py를 별도 프로세스로 실행한다. 새 departure plan/execute로 세션·map/odom 기준을 기록한 후 벽 종료 자세 fixture, retreat plan/execute, align plan/execute, return plan/execute 및 장애물 plan 거절의 9항목을 요청한다. 기존 v4 C++ 소스가 동일할 때만 통과한 독립 설치본을 재사용한다.
범위 제한: 검사 노드가 모의 odom/TF와 이상 명령 적분을 제공한다. velocity_smoother 노드는 timeout 파라미터 계약 대역이며 실제 smoother/드라이버 시험이 아니다. wall 단계와 arc_isolated 감독 프로세스는 이번 ROS 검사에서 실행하지 않는다. 순서 관리 도구의 프로세스 경계는 오프라인으로 검사한다. 따라서 전체 복귀 E2E/실물 검증 완료로 표시하지 않는다.
직접 수행한 검증은 패키지 OFFLINE_VERIFICATION.json 참조. 새 실제 runtime ROS 검사는 사용자 PC에서 수행해야 하며 이 환경에는 ROS가 없다. 설치본/사용자 Git 소스 적용·로봇 접속·커밋 없음. 모든 산출물은 Downloads 하위. 실물 실행 래퍼의 차단은 유지한다.


## 전체 실행 연결 검사 후보 — 2026-10-21 패키지

사용자 PC의 실제 arc_trial.py 별도 프로세스 9항목이 통과했다. 성공 기록은 /home/eunbi/Downloads/harvest_restore_runtime_check_xHZnQV이며 runtime SHA256은 ae9a8c0b98ece07e4ee0a0f1104dbb9de705d259b87b2ccf6bb719d57a0de97f다. 벽 종료 fixture와 smoother 파라미터 대역을 사용한 결과이므로 전체 연결/실물 결과로 확대하지 않는다.

사용자 ‘준비해’ 승인으로 Downloads 후보에서 실제 restore_sequence.py → arc_isolated 감독/벽 실행 → 기존 Navigator/Controller → 실제 velocity_smoother 연결 검사를 준비했다. 기본 실물 Bash의 domain 77 및 설치 경로는 그대로 유지한다. 명시 HARVEST_PC_CHECK=1에서는 domain 95/localhost/FastDDS, Downloads 후보·독립 플러그인 설치 경로와 Python 모듈 위치를 확인하고 사전 로딩 환경을 사용한다. PC에서 실물 domain으로 빠지는 것을 막는다. 실물 restore_sequence.bash 차단은 유지한다.

검사 순서: departure/wall/retreat/align/return 각 plan/execute 10항목 및 footprint 장애물 departure plan 거절 1항목. 기존 상태/증명 파일을 실제 순서 도구가 생성한다. 벽 종료 위치를 강제 설정하지 않고 이상 평면 환경의 LaserScan을 기존 WallTracker/WallController가 처리한다. 실제 CLOSED_LOOP velocity_smoother 출력을 이상 모델에 적분한다. 지도·TF는 PC 검사 전용이며 실물 지도/모터 성능을 검증하는 것이 아니다.

기존 성공 후보/상세 결과를 새 검사 폴더의 preserved_success에 복사하고 파일 해시를 기록한다. 이전 v4와 두 C++ 패키지 소스 일치 시 독립 설치본을 재사용하며 벽 플러그인만 새 Downloads 설치본으로 빌드한다. 기존 제어기, arc_trial, 공통 주행 코드, 충돌/속도/정지 기준과 성공 벽 설정은 변경하지 않았다.

직접 수행: 오프라인 회귀 238개 PASS, Bash/Python 구문 검사, 성공 핵심 5파일 해시 보존, 실제 wrapper의 잘못된 domain 진입 차단. 실제 ROS 전체 연결은 이 환경에 Jazzy가 없어 미실행이다. 사용자 PC 실행 결과 전에는 완료로 간주하지 않는다. 프로젝트 적용/로봇 접속/실물 이동/커밋/원격 Git 검증 없음. 후보 삭제로 되돌릴 수 있다.


## 출발 기준 TF 시각 수정 — 2026-10-21

사용자 “확인하고 확실하게 고쳐와서 말해” 승인. 독립 Downloads 후보만 변경한다. 정지 확인 시각이 TF 버퍼보다 45.223ms 이른 실물 plan 실패를 확인했다. PoseProvider.lookup_available_pair는 기존 lookup을 재사용하여 진행하는 odom 표본 중 map/odom을 같은 시각에 조회할 수 있는 표본을 선택한다. TF가 지연될 때 최신 표본만 추격하지 않도록 유효 기간 내 표본을 보관한다. 시각 역행, 오래된 표본, 정지 상실, 다른 Action, TF 누락은 실패한다. 출발 경로 원점도 저장한 odom 자세와 일치시킨다. 기존 lookup/current 및 도착 판정 호출, 컨트롤러, 충돌/정지/속도 기준은 불변이다. 최신 TF 두 개를 독립 조회하는 대체 동작은 없다.

로컬 검증은 대역 TF 버퍼 및 기존 회귀이며 실제 ROS/실물 결과가 아니다. 배포 전 PC Jazzy tf2 Buffer 검사, 로봇 적용 후 설치 위치 및 무이동 departure plan 검사를 요구한다. 해당 결과가 나오기 전 실물 해결 완료로 표시하지 않는다. Git 커밋/푸시 없음. 원본 및 진입 도구 해시는 Downloads 백업으로 보존한다.


## 2026-10-23 실물 인계 지연 증거 수집 (시뮬 변경 없음)

- 구분/승인: 사용자 인계 지연 조사 및 계측 요청. 운영 공통 변경은 적용하지 않음.
- 대상: robot/tools/transfer/handoff_diagnostics 신규 도구와 docs 인계 기록. 기존 기록 보존.
- 전후: 수신/header age 구분 자료 없음 → 읽기 전용 수집기, 외부 관측기, 내부 계측 제안 생성기 준비. 로봇 SSH 인증 실패로 현장 적용 대기.
- 영향: 실물 제어·시뮬 소스/설정/허용치 변경 없음. 도구 실행 비용 검증은 현장에 남음.
- 검증: 오프라인 6개 통과, ROS 메시지 import 및 PC 수집 확인. 실기·Isaac 미실행.
- 복원: 새 진단 도구를 호출하지 않으면 운영 영향 없음. 이번 추가 파일/문서 절만 선택 제거.
- 상세: ../../docs/changes/HANDOFF_DELAY_AUDIT_20261023.md. commit/push 미수행.


## 2026-10-23 실물 직접 조사 후속 (시뮬 변경 없음)

사용자 직접 작업 승인 및 초기 스테이션 시험 준비 확인에 따라 로봇 수확 전용 계측/선택형 TF 실행 문맥을 적용·빌드. 변경 전 소스/설치본 백업과 manifest 원복 관리. 공통 navigation·실물 설정·시뮬은 미변경. 동시성20/계측3/인계64 오프라인 검사, 별도 무동작 ROS TF 검사 통과. 실기 window 요청1회는 일반 Nav2 전방 충돌 판정으로 실패, 사용자 정지 확인, body 미호출. TF age 개선을 전체 인계 성공으로 간주하지 않음. 상세/원복: ../../docs/changes/HANDOFF_DELAY_AUDIT_20261023.md. commit/push 없음.

## 2026-10-23 실물 코너 비교 기록

구분: 실물 진단 도구/문서. 사용자 진행 승인으로 record_corner.bash를 추가하고 실제 window 1회 성공 기록을 남겼다. 공통 제어·실물 설정·시뮬 소스 변경 없음. bash 구문 검사 및 실물 bag 순차 읽기 확인. body 인계 및 시뮬 시험 미실행. 원복은 수집 도구만 선택 제거 가능. 상세: docs/changes/HANDOFF_DELAY_AUDIT_20261023.md.

## 2026-10-23 인계 실기 기록 추가

실물 body enter 시험은 곡선 출력 시간 초과로 중단. 실제 이동/취소/정지 확인과 남은 한계를 인계 문서에 기록. 수집기 raw 속도/인계 토픽 추가(bash -n 통과), 운영·공통·시뮬 설정 변경 없음. 수집기 추가 행 선택 제거로 원복 가능. 실기 자동 재시험 없음.

## 2026-10-23 출력 승인 공백 오프라인 조사

실물 진단용 재현 테스트/계측 후보 생성기만 추가. 사용자 필요한 확인 진행 승인. 현장 운영본 변경 없이 후보 AST 동일성과 회귀6개 검증. 공통/시뮬 코드 변경·실기 재시험 없음. 도구/미적용 후보 선택 제거로 원복 가능. 상세는 HANDOFF_DELAY_AUDIT_20261023.


### 2026-10-23 — 실물 인계 구조 비교 기록(시뮬 동작 변경 없음)
- 사용자 “그거 먼저 추적해서 대조해줘” 요청으로 과거 독립 성공/통합/fixed 출력 구조 및 실행 파라미터 비교. 대상: docs/changes/HANDOFF_DELAY_AUDIT_20261023.md, docs/PROJECT_STATE.md, docs/CODEX_HANDOFF.md.
- 전후: 원인 미확정은 유지하되 공통 Navigator 독립 성공 증거, 같은 주요 제어 설정, fixed의 센서 객체 갱신 거절 추가를 구분해 기록. 실물/시뮬 운영 소스 변경·빌드·이동 없음.
- 검증: 로봇 과거 성공 JSON과 YAML, 현재 param dump, pre-fixed 백업 및 fixed 캡처 읽기 대조. 실기 원인 확정/인계 완료 아님. 되돌리기: 이번 추가 문서 절만 제거. commit/push 없음.


### 2026-10-23 — 실물 인계 센서 갱신 commit 수정 후보
- 승인: 사용자 정상 센서 갱신 차단 수정·오프라인 검증 요청. 대상: 별도 현장 패키지 복사본의 handoff_runtime.py, robot/tools/transfer/handoff_diagnostics/prepare_sensor_commit_fix.py 및 test_sensor_commit_fix.py, 인계 문서.
- 변경 전후: departure/return/retreat 객체 교체 무조건 거절 → 최신 입력 freshness/frame/형상 commit 재검사. 취소/정지 보호 유지. 공통 모듈·시뮬 소스·실물 운영 설치본 변경 없음.
- 검증: PC/로봇20개, 격리 빌드 성공, 경로 구성 수정 후 기존 인계64개 통과. 실제 ROS 부하/실기 미검증. 원복: 운영 미적용으로 필요 없음, 후보/백업 별도 보존. 상세 HANDOFF_DELAY_AUDIT_20261023.md. commit/push 없음.


### 2026-10-23 18:39 — 실물 수확 센서 commit 수정 운영 적용
- 사용자 운영 적용/재시작 전 상태 확인 승인. 로봇 handoff_runtime.py 한 메서드 후보 적용, harvest_robot 운영 빌드 및 노드 단독 재시작. 기존 핫픽스/상태 파일/설치본 백업 보존. 시뮬 소스·설정 변경 없음.
- 검증: 후보/소스/install 해시 동일, 기존10개 파일 불변, 프로세스1개, body IDLE/odom0, 위치 추정 유지. window 기준 소실로 인계 준비 완료 아님. 이동 없음.
- 원복: 새 노드 정상 종료 후 deployment 원본 복원/재빌드. 상세 HANDOFF_DELAY_AUDIT_20261023.md. Git commit/push 없음.


### 2026-10-23 — 실물 window 재확보 요청 기록
사용자 현재 위치 이동 승인으로1회 요청. 접근 사전 방향 검사에서 실패, 위치 유지/odom0. 성공 기준 미확보. 코드·시뮬 설정 수정 없음; 로봇 bag/PC 결과·인계 문서 보존. 상세 HANDOFF_DELAY_AUDIT_20261023.md. commit/push 없음.


### 2026-10-23 — 실물 부분 복구 경로 읽기 검토
사용자 복구 계획 준비 요청으로 prepare_recovery_path.py 추가 및 실제 센서 snapshot 기반 후보 계산. 회전/후진 정적 footprint 검사·후진 목표의 기존 window 접근 조건 통과. 운영/시뮬 코드·설정·실기 이동 변경 없음. 복구 실행 입구는 아직 없어 실행 준비 완료 아님. 증거/미검증/후속 조건은 HANDOFF_DELAY_AUDIT_20261023.md와 recovery_plan_v1/RECOVERY_PLAN.md. 원복은 별도 분석 산출물/도구만 제거, 기존 핫픽스 영향 없음. commit/push 없음.


### 2026-10-23 — 부분 복구 실행 연결 후보
- 사용자 복구 실행 연결/오프라인 검증 승인. 최신 로봇 패키지 별도 복사본의 node.py/runtime.py 및 신규 handoff_recovery.py에 opt-in 복구 서비스/토큰 보호 구현. 신규 test_handoff_recovery.py와 출력 주입 시험 추가.
- 변경 전 없음 → 약12°×3회전/후진을 기존 안전 모듈과 단일 소유권으로 실행하는 연결. window 도착은 별도 정상 Action 완료만 인정.
- 검증:87개+출력22개, 보존 snapshot 사전검사 및 격리 빌드 통과. 운영·시뮬 소스/설정·프로세스/실기 이동 변경 없음. 원복/승인/검증 한계는 HANDOFF_DELAY_AUDIT_20261023.md 마지막 절. 기존 핫픽스 백업 유지, commit/push 없음.


### 2026-10-23 — 스테이션 초기 정합/일반 재주행 실기 기록
사용자 스테이션 배치 및 이동 승인. 초기위치 설정 후 정지 scan/map 정합 확인. 일반 controller가 출발 직후 회전 중 전방 충돌 예상으로 중단해 window 미도착. check_station_alignment.py 읽기 도구와 기록 추가, 운영/시뮬 코드·안전 설정 변경 없음. 복구 후보 미적용, 인계 미실행. 실기 원인 미확정, 실패 순간 bag 보존. 상세 HANDOFF_DELAY_AUDIT_20261023.md. commit/push 없음.


### 2026-10-23 — 실물 local costmap 잔존 정보 분리
사용자 제안에 따라 원본 저장 후 IDLE/odom0에서 일반 local costmap1회 초기화 및6초 재관측. 같은 회전 footprint가 전에는 충돌, 후에는 통과. 실제 이동/초기위치/안전 설정/시뮬 변경 없음. 동적 센서 지도 재생성 비교이며 운영 코드 변경 아님. before/after 근거 및 인과 한계는 HANDOFF_DELAY_AUDIT_20261023.md. commit/push 없음.


### 2026-10-23 19:29 window 재주행 성공
일반 local costmap 초기화 후 사용자 승인1회 이동 최종 SUCCESS. 현재 window 위치(1.15805,-.03114), yaw.01863rad, 목표 오차2.82cm/1.07°, IDLE/odom0 확인. Zenoh ON/요청은 로봇 로컬. 초기위치 재발행·복구 후보 적용·안전 설정 변경 없음. 인계 enter/restore 미실행, 팔 미시험. 근거/한계/로그는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. 문서·수집 자료만 갱신, commit/push 없음.


### 2026-10-23 19:33 차체 인계 후 정지 유지
사용자 승인 enter/restore 각1회. departure·wall 완료/ENTERED 및 정지 확인 후 restore. retreat와 Spin 제어기는 성공했으나 align 정지 후 재진입 검사 실패: RECOVERY_REQUIRED. 전진 복귀 미시작. odom 재구성 위치오차 약8.77mm(한계8mm), 방향약.70도(한계1도); 정확한 runtime reference 미노출로 재구성 근거임을 구분. map=(1.059564,-.124540),yaw1.648618, odom0 및 사용자 현장 정지 확인. 재진입/초기위치/추가 이동 없음. Zenoh ON, 팔 미시험, 전체 인계 미완료. 안전조건/운영 코드 변경 없음. 상세·로그·잔여 범위: docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 복귀 재진입 정책 후보 검증 완료(운영 미적용)
사용자 승인으로 현장 최신본 백업 후 reentry_policy_v1 별도 후보4파일 수정. 재진입 위치는 선택형 설정으로 분리하여 body_trial만10mm, 기존 사용처/출발·최종 곡선8mm/방향·정지·충돌·출력 보호 유지. 현재 자세→원호 시작점 충돌 검사 추가, controller 원형 경로는 불변. PC/로봇 신규18+기존64=82개 및 출력20개 PASS, 로봇 격리 빌드/설치 해시 확인. 보존 costmap/실제 C++ 제어식 이상 모델로 다음 복귀·window 보정 계약 통과했으나 최대 이탈9.55mm로10mm 대비 여유가 작아 실기 성공은 미확정. 운영152파일 및 기존 핫픽스 상태 보존. 재시작/이동 없음, RECOVERY_REQUIRED 정지 상태 유지. 상세·초기 시험 실패·원복 경계는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 19:55 재진입 정책 적용/재배치 대기
사용자 승인으로 reentry_policy_v1 원본4파일·운영 설치본 백업 후 PID85474 정상 종료,4파일 적용 및 harvest 빌드/설치 해시 일치 확인. 기존 핫픽스 상태/백업 유지. 수확 노드는 아직 미기동, 기존 launch·Zenoh·AMCL/Nav2/드라이버 유지. odom0/cmd_vel_nav publisher0/사용한 Action terminal 확인 후 사용자에게 비상정지 유지하여 스테이션 재배치 안내. 재기동 검사 도구 CHECK_ONLY_OK, 실제 기동/초기위치/이동 없음. 다음은 재배치 확인 후 재기동·정합·costmap 확인·window 재확보. 상세 백업/원복은 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:05 수정본 재기동·스테이션 정합 확인
사용자 스테이션 재배치 확인 후 수확 PID129702 재기동, 기존 초기좌표 설정. scan/map 중앙오차6mm/p90 2.17cm, odom300개0, 중첩 그림 확인. 일반/인계 local costmap의 현재 차체 및 +.1rad 회전 검사 통과하여 이번 clear 미실행. cmd_vel_nav/odom publisher각1개, IDLE/ready·body IDLE, 전용TF 유지. 전체 경로/비상정지 해제/실기 이동 안전 보장은 아님. 주행·enter/restore 미요청, window 기준 재확보 필요. 상세 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:11 수정본 일반 window 재주행 성공
사용자 승인 단발 window 이동 status4/SUCCESS. 현재(1.156699,-.037115),yaw-.007667rad, 목표 오차2.94cm/.44도, IDLE 및 odom31표본0. PID129702/Zenoh 유지, 요청은 로봇 로컬. bag·외부/내부 계측 마감 보존. body IDLE, enter/restore 미요청. 재진입10mm 수정의 실기 검증은 아직 아님. 초기위치 재발행 금지, 인계 전 안내. 상세 HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:15 전체 차체 인계 실기1회 완료
사용자 승인 enter/restore 각1회. 적용10mm 재진입 정책·Zenoh ON 상태에서 후진 곡선/벽 정렬/후진 이탈/Spin/전진 복귀/최종 window 도착 검증 COMPLETED. 추가 window 보정 이동은 없었음. 최종(1.184048,-.028186),yaw-.002234, 관제 goal오차7.09mm/.128도; IDLE·최근odom30표본0 별도 확인. bag 재구성 재진입오차6.08mm로 기존8mm 이내여서8~10mm 실기 통과·완화의 인과 효과는 아직 미확인. 팔 NOT_TESTED, 반복신뢰성/PC관제왕복/타로봇 실기 미검증. 현재 body COMPLETED이므로 자동 enter 반복 금지. 로봇 body-reentry-policy-nVLFxOy9 및 PC body_reentry_policy에 로그/분석 저장. 상세 HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:31 인계 후 그래프14 일반 주행 연속 시험 성공
사용자 요청으로 관제 웹을 직접 조회: #59/25fabab7b348_SEC01_TASK001(표시 목표1.601,-.035)은21:25:15 대기열 등록 후 Action 전송 전. 수확 Action 서버 대기, 인계 수확Status는18:38:38의 이전boot ERROR/CANCEL_UNCONFIRMED에 정체되어 최신 로봇IDLE/ready와 불일치. 지도 위치 수신은 최신이었다. 근본 통신 원인 미확정. 이후 화면에서 해당 작업의 전송 전 취소 및 수확 대기열 일시정지 확인(에이전트가 취소 버튼을 누르지 않음).
사용자 “일단14번 노드로” 승인으로 실제 graph.geojson 노드14=(3.576,-.035) 읽고 yaw0, expected_count0 시험 HarvestTask NODE14_79189ba30dfe_TASK001을 로봇 로컬에서1회 요청. 현재 위치·정지 확인 및 경로 안내 후21:30:03 수락→21:30:43 status4/SUCCESS. 실제 SECTION_RESUME→WINDOW_MOVE→ARRIVED, 현 위치에서 목표까지2.392278m 직선 FollowPath(reverse=false, graph edge_ids=[]); 그래프 전체 경로 추종 시험으로 확대 해석하지 않는다. 도착 판정오차28.060mm/.5154도, 최종Status(3.550325,-.023535),yaw-.009290;21:31 IDLE/ready 및 최근odom30표본 전부0. PID129702/Zenoh 유지, 재시작·초기위치·코드/안전설정 변경·추가 인계 없음.
새 시험 goal의 arrival와SUCCESS 이벤트를 확인. 현재 communication.py의 remember_window→handle.succeed 순서에 근거하여 새 기준 저장 경로 완료를 판단했으며 메모리를 직접 조회한 것은 아니다. body-only 팔 NOT_TESTED. 인계 완료→일반 주행 전환1회는 실기 확인했으나 관제 웹 다음 실제window 전달은 미완료이며 후속 인계 반복 검증도 별도다.
로그: 로봇 runs/handoff_diagnostics/web-next-window-AiZhUerb (bag 정상 마감, 외부 계측), 하위node14/goal.json,action.log,final.json; PC runs/handoff_diagnostics/20261023_review/web_next_window에 웹 관측과 단발 결과 보존. 기존 핫픽스/백업 보존, 문서만 추가, commit/push 없음. 원복할 운영 변경 없음.


### 2026-10-23 실기 성공본 PC 커밋 준비
사용자 승인으로 로봇 실행/설치 출처 대조 후 최신 핫픽스25파일을 PC에 반영. 기존 dirty 원본 및 시험/로그/백업은 /home/eunbi/vmany_artifacts/handoff-success-20261023-commit-prep에 보존. 관련 없는 예찰/Burger 차이 및 기존 추적 시험 보존. 성공 실행의 dedicated TF 환경 선택과 body-only 프로필을 문서화. 이번 PC 오프라인64+18+20검사,4패키지 격리 빌드 통과. 인계→일반주행 실기1회 성공이며 웹 관제 전달/반복/팔 검증은 미완료. 운영 로봇 변경/이동/commit/push/staging 없음. 상세 docs/changes/HANDOFF_SUCCESS_COMMIT_PREP_20261023.md.


### 2026-10-24 공통 launch 후보 검토 — 미적용
사용자 승인한 실물 인계 전용 padding62×52 후보 준비. 공통 farm_bringup harvest.launch.py는 기존 인계 JSON의 선택형 padding을 구성함수에 전달하는 제안diff만 Git밖에 작성. 시뮬/일반주행/운영소스 변경없음. launch와 runtime 동일전달 및 기존기본값보존 등 오프라인15PASS; 실제launch/실기미검증. 외부 handoff_padding_candidate_20261024에 원본백업/manifest/후보/검증/원복보존. 적용은 사용자안내후별도진행,현재원복불필요. 상세 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신절.


### 2026-10-24 인계62×52 로봇실행본적용·미기동
사용자승인으로원본/설치본백업후3소스+FSM JSON적용,2패키지빌드/설치해시·형상검증완료. 일반64×54/안전보호유지. 기존런치종료(수확SIGINT60초지연→SIGTERM종료경고보존),사용자스테이션복귀확인. 실패1건은FAILED기록보존+수동복구근거를남기고recovery_required해제. 새window기준/더미수확필요. 로봇/PC브리지·PC더미유지,사용자laun→vinit→웹확인대기. 실제기동/이동없음. 상세audit최신절/외부배포검증자료참조. PC운영소스는미반영,commit/push없음.


### 2026-10-24 TBB 잔존 arena 추적·v2 후보 오프라인 검증
OpenCV 전역 task_arena가 노드 소멸 뒤 남는 구조 확인. 설치 ARM disassembly와 카메라 없는 remap 대조로 PC/ARM 각각 보존5회 finalize실패, 해제5회 정상종료 재현. v2 후보는 node/executor 정리 후 cv::setNumThreads(0)→TBB finalize→loader 해제, 실패 보호 유지. 양측 합성 OpenCV 노드 SIGINT/SIGTERM/생성실패·순서·링크 검사 통과. 운영원본/설정 SHA·백업 바이트 일치, harvest270128 유지. 카메라 재실행/운영 적용/이동/commit/push 없음. 실제 영상 재검증 전 해결 확정 금지. 근거 runs/tbb_shutdown_candidate_v2_20261024/README.md 및 상세 인계감사문서. 이전 v1과 백업 보존.


### 2026-10-24 TBB v2 실제 영상 종료 시험 통과 (1회)
사용자 카메라 전용 v2 실행 승인. 원본 카메라/monitor 및 영상 설정 그대로, rectify/apriltag 실행 파일만 runs/tbb_shutdown_candidate_v2_20261024/build 후보 선택. 운영 launch/바이너리 교체와 보정 adapter·이동 요청 없음. 기준 cf870da 및 기존 미커밋 변경 보존.
120.035초 실행, raw/rect/detections 각각939표본, tag100 검출. camera/검출기/rectify/monitor 모두SIGINT 종료0. 검출기0.264714초, rectify0.267155초(신호 전송~프로세스 wait 관측의 monotonic 경과). camera0.465257초,monitor1.867278초,전체3.865244초(카메라 후1초 대기 포함). 기존 검출기/rectify4초 제한 내 종료,TERM/KILL없음. 두 로그 모두 OPENCV_ARENA_RELEASED→TBB_FINALIZE_BEGIN→TBB_FINALIZED→COMPONENT_LIBRARY_RELEASED 확인. 이전 원본-11/v1 exit3과 달리 이번 v2 실제 영상 종료 정상.
운영 카메라3스크립트/설정SHA 전후동일, /opt/ros 실행파일2개 원본 백업과 동일, harvest270128/launch270080 유지. 시험 자식모두종료. 영상 중 별도15초 읽기 odom453개 비영0/IDLE 확인(전체120초 연속 odom계측은 아님). 카메라 설정 복원 기록 보존. PC·로봇 runs/tag_tbb_v2_trial_20261024에 commands/settings/후보SHA/영상표본/로그/receipt.json/보존검사 저장,31파일복사SHA일치검증. Git commit/push없음.
이번 한 차례 카메라 종료 시험 통과이며 장시간/반복 종료·주행과 태그보정 통합·control_readback_stale 원인 해결은 별도. 운영 설정은 여전히 원본 실행 파일 사용. 다음 운영 적용은 사전 안내 필요.


### 2026-10-24 v2 종료 처리 운영 경로 반영 — 재기동 대기
사용자 운영 적용·백업·원복 준비 승인. Git cf870da+기존 미커밋 변경 유지. PC/로봇 robot/ros_ws/src/farm_tag_camera_runtime에 실제 시험한 v2 C++/헤더 바이트 그대로 추가, ament 설치용 CMake/package.xml과 설치 선택 검사 추가. 양측 colcon에서 새 패키지만 빌드. 기존 harvest/Nav2/AMCL 패키지는 빌드·재시작하지 않음.
robot/tools/tag_camera/pinky_tag_capture_compare.py가 기존 /opt/ros 실행 파일 대신 ament index의 farm_tag_camera_runtime/{apriltag_safe,rectify_safe}를 선택. 기존 명령 인자/검출·카메라 설정/종료 제한은 불변. 누락·권한 오류 시 시작 전 실패, 자동 원본 fallback 없음. settings.json에 실행 파일 경로·SHA 기록 추가. /opt/ros 바이너리와 기존 v1/v2 후보·백업 보존. 시뮬 ROS 영상 launch 불변.
PC 오프라인 캡처/설정/세션/실행 선택21건 통과. 최초2건은 시험명령 PYTHONPATH에서 ROS 경로를 제외한 ModuleNotFoundError; 환경 수정 후21건 통과. 임시 복사본 원복3건(정상복원/원본상태/추가변경거부) 통과. 로봇 새 env source에서 설치된 두 바이너리 경로 확인, v2 소스동일, 나머지 카메라2파일+trial_io 및 설정SHA 동일, harvest270128유지. 캡처 적용 SHA 2f21f848041b5e2307233387ec33a0ccd74d3c82c961d48abcd88fc0d1450451. 카메라 재기동/이동/commit/push 없음. 운영 경로 실제 재기동 검증은 아직 미수행.
PC/로봇 runs/tag_tbb_v2_deploy_20261024에 capture.before.py/after.py, 빌드·적용 receipt 및 rollback.py 보존. 카메라 종료 상태에서 로봇 터미널 `python3 /home/vic/vmany/main/farm_project/runs/tag_tbb_v2_deploy_20261024/rollback.py`로 실행 선택 원복. PC는 같은 경로의 /home/eunbi 사용. 실행 중 카메라 또는 적용 후 추가변경이 있으면 거부. 새 패키지는 남아도 원본 스크립트가 참조하지 않으며 삭제/기존노드 재기동 불필요. 새 설치만 복사할 때 farm_tag_camera_runtime을 빌드 목록에 명시한다. 원복 도구는 프로세스 시작/종료하지 않는다.


### 2026-10-24 운영 캡처 경로 v2 실영상·종료 검증 통과
사용자 카메라만 재기동/정상종료 검증 승인. 운영 pinky_tag_capture_compare.py를 변경 없이 subprocess 실행, 기존 캘리브레이션·manual_2ms·검출 파라미터 그대로 사용하고 출력 폴더만 별도 지정. 실제 ament 설치 경로 farm_tag_camera_runtime의 apriltag_safe/rectify_safe 선택을 settings.component_runtime 및 commands.json으로 확인. fleet 주행 노드·보정 adapter 재기동/주행 명령 없음.
약2분 시험, raw/rect/detections 각950표본,tag100검출. 운영 부모+camera/detector/rectify/monitor 모두exit0,process_exits.clean_shutdown=true,예기치않은종료없음,SIGINT만 사용. 검출기·rectify 각각 OpenCV arena 해제→TBB_FINALIZED→COMPONENT_LIBRARY_RELEASED 확인. -11/TERM/KILL없음. 운영 스크립트는 수정하지 않고 외부 수집기가 STOPPING/EXIT 출력 수신시각(monotonic)을 기록: 검출기0.264560초,rectify0.265867초,camera0.414579초,monitor0.565077초. 이는 정확한 OS 신호~exit 시각이 아닌 로그 관측 구간이다. 부모 SIGINT 요청~수집 종료2.736272초.
기존 운영 코드3파일/카메라설정 SHA 전후동일, 기존 성공 주행 PID270128/launch270080유지,시험자식 모두 종료. 별도15초 odom455개 비영0/IDLE. 카메라 controls_restored=true. 검출파라미터 이전v2시험과동일. 로그·종료시간·실행해시·표본은 PC/로봇 runs/tag_operational_v2_trial_20261024, 실제 세션 capture/20261024_060235_la99uakv. PC복사32파일SHA일치 확인. 원복백업/도구 유지,commit/push없음.
검증 범위는 운영 캡처 스크립트와 설치 실행파일의 카메라 전용 시작·영상처리·정상종료 1회. 전체launch 재기동·태그보정/주행 통합·장시간 반복·설정조회 stale 원인 해결은 이번 검증에 포함하지 않는다. 현재 카메라는 종료 상태,주행노드는 유지.


### 2026-10-24 카메라→태그 보정 정지 연결 확인
사용자 정지 연결 확인 요청 후 카메라·어댑터가 모두 종료 상태임을 확인하고 재기동 범위를 사전 고지. 운영 tag_capture_session만 기존 environment에 지정된 capture config와 runs/tag_bias_trial/20261023_165950_381707_on/localization.yaml로 잠시 실행. 주행/AMCL 유지, 작업 활성화·보정·initialpose·이동 명령 미발행. 설정/코드 변경 없음.
새세션 runs/harvest_tag/20261024_060658_l_wtlwis,하위20261024_060659_8h_4ce7t:raw/rect/detections418개,tag100검출. 실제어댑터FD17이새detections.jsonl을열었고5초간읽기위치89623→114588로각시점파일끝까지전진. 이전세션재사용아님.
DDSgraph: harvest_motion_server control publisher→adapter/AMCL subscriber, adapter correction publisher→AMCL subscriber, AMCL events publisher→adapter subscriber 확인. AMCL read-only parameters tf_broadcast=true,protocol=scan_sync_v1,robot=harvest_01,map=many_farm_v1 일치. 이는 연결·계약 확인이며 실제 보정 적용 왕복 성공을 의미하지 않음.
35초읽기관측control/correction/events각0,odom1052표본비영0. 어댑터 start/closed 기록 correction_requests=0. 유효작업lease없으면출력을차단하는기존보호를유지했으므로정지대기는정상이며보정성공으로표기하지않음. 영상→관측계산→AMCL 실제적용은유효작업구간에서별도확인필요,이번에는작업신호를인위적으로발행하지않음.
시험후adapter/capture부모및camera/detector/rectify/monitor전부exit0,clean_shutdown=true,-11/강제종료없음. 세션SIGINT→부모종료3.834초. 시험자식종료,기존launch270080/AMCL270098/harvest270128유지. 설정·설치/소스모듈전후SHA동일. 현재카메라·어댑터는시험종료상태. 로그는PC/로봇runs/tag_stationary_link_20261024,로봇원세션도보존;PC에원세션전체추가복사. commit/push없음.


### 2026-10-24 사용자 요청: 벽 시간 임계값 조정 후보
사용자 반복 차단 조건 제거 또는 임계값 확대 요청에 따라 실제 로봇 wall/handoff 설정 원본을 runs/wall_timing_candidate_20261024에 보존. 운영소스/설정/프로세스 불변,PC 후보만 작성. 변경2개: controller.observation_age .3→.45초, observation.max_gap_s .3→.45초. dwell .5초와충돌/취소/정지/속도/미래시각거절유지,일반주행변경없음. .45는원인확정후도출한해결값이아닌제한된실험후보이며이번오류가future분기면해결못함. 최대설정속도.02m/s·.05rad/s에서추가150ms는3mm/.0075rad 이동분에해당하나실물안전증명아님.
실제C++헤더와후보설정생성검사: .35/.44초수락/.451초만료/미래1ms거절/기존.3초거절/실측비영속도정지우선/같은stamp반복성공금지확인. 기존C++회귀도실행,로그test.log. ROS부하·실기검증아님. 이전성공코드및핫픽스보존,이번에는적용/재기동/이동없음. 운영적용은Python과controller가같은설정을기동때읽어야하며수확노드만값변경으로불일치시키지않는다. 현재recovery_required유지. 원복은미적용후보불사용,추후배포시원본설정복원필요. commit/push없음.


### 2026-10-24 0.45초 후보 운영 설정 적용·종료 확인
사용자백업유지/실행본적용/종료·재기동절차승인. 종료전ERROR·odom91표본0,실패transfer기록백업. 카메라311318→launch311278→로봇브리지311773/311836 정상종료,자식포함remaining[];PCdummy196592/bridge196652도기록백업후종료remaining[].최종로봇관련프로세스검색없음. 런치종료중harvest Destroyable 경고1회후finished cleanly;정상종료경고문제까지해결됐다고표시하지않음.
공용wall_alignment_trial.json불변. /home/vic/Downloads/pc_dummy_dock_fsm_20261024/wall_alignment_045.json 신규전용후보배치,동폴더handoff_fsm.json의wall_config참조만변경. observation_age/max_gap_s=.45,dwell=.5,padding=.01 유지. 실제설치구성생성기로controller/observer설정오프라인일치검증,노드기동없음/빌드불필요(JSON선택변경). runs/wall_timing_deploy_20261024에로봇·PC원본/배포receipt/검증/종료PID/rollback.py보존. 원복은프로세스부재·afterSHA검증후원래handoff참조복원,신규설정파일미참조로보존.
현재실패journalrecovery_required유지(물리복구전해제하지않음). 사용자에게드라이버종료확인후스테이션재배치가능시점안내. 스테이션위치·방향이동확인받은뒤이번실패원문보존+수동복구기록을추가하고재기동하도록할것. 아직재배치확인/복구해제/재기동/초기위치/이동없음. PC더미도기동후복구상태조회필요. 사용자기동순서PCdummy→PCbridge→로봇laun→vinit→zen→dzen→vstat,웹연결확인후파라미터·정합·costmap·더미·새window기준점검. commit/push없음.


### 2026-10-24 인계 중단 조건 전체 검토·정지 대기 후보
사용자가 벽 관측 외의 불필요한 중단 조건도 제거/조정 요청. 로봇 최신 소스를 runs/handoff_guard_audit_20261024/source에 확보하고 후보 디렉터리만 수정했다. PC runtime은 로봇과 달라 덮어쓰기 금지 유지. 공통 wall_controller/WallTracker 및 harvest runtime 후보5개 파일, 전용JSON과 patch 작성. 벽header만료·수신없음·표본gap·tracker재획득·준비단계 stale pair를 통합 처리하며 default는 기존정책, 후보만 observation_wait=.8초/stable재획득 선택. 충돌/취소/소유권/미래시각/odom/costmap 유효성 유지. 상세 중단조건 표·남은문제는 runs/handoff_guard_audit_20261024/REVIEW.md.
PC Jazzy 공유라이브러리 별도빌드 성공, 기존861assertions/ctest1통과, 새정지대기C++/tracker/runtime분류오프라인검사통과. ROS통합·전체인계·실기미검증; wall/align snapshot 및 상위watchdog 경로가 남아 모든 지연해결로 표시하지않음. 운영소스/설치/실행설정 불변,재기동/이동/commit/push없음. 후보 적용 전 안내 필요.


### 2026-10-24 watchdog·wall/align 후보 v2 통합검사
사용자 후보 보완·통합검증 승인, 운영 적용/재기동/이동 전 안내 유지. 후보 runtime에서 wall 최신 입력 재검증, align 최신 costmap 키·최신 자세 clearance 재검증을 연결했다. 증명 재계산은 실제 controller 입력을 받은 경우 0 출력으로 최대3초 대기하며 기존 .3초 watchdog은 유지한다. Navigator live guard도 취소 가능한 bounded wait로 연결하여 callback 외 경로의 즉시 실패를 보완했다. epoch/취소/정지/소유권/세션·충돌·freshness보호 유지.
실제 메서드/gate/clearance 통합16, guard 경로4, 실제스레드경쟁4 검사 통과. 실패bag→후보C++ Control 199개 재생(max age .502972초) 통과. PC격리loopback domain191 시험토픽 DDS→실제후보메서드/gate 199개 일치, 입력단절시watchdog정지 확인. 기존861assertions/ctest 및기타후보검사통과. 주변Node/센서/시각은harness이며전체Nav2 Action/실물부하 통합검증과구분한다. 모든조건/지연해결이나실기성공으로보고하지않음.
로봇현재원본5파일hash가보관source와일치. 운영소스/설치/설정/프로세스불변,실물이동/재기동/commit/push없음. runs/handoff_guard_audit_20261024/REVIEW.md의v2표·검증한계와candidate.patch/manifest/검사로그참고. 적용전로봇아키텍처빌드·배포·재기동절차준비필요.


### 2026-10-24 정지 대기 v2 로봇 빌드·설치 적용
사용자 기존핫픽스백업/로봇빌드/실행본적용/종료·재기동절차 승인. 적용전odom91개비영0 확인. camera324570,launch324533 및자식,로봇브리지325032/325095 SIGINT종료,선택28개remaining[] 및최종프로세스부재확인. 드라이버종료후사용자에게스테이션재배치가능안내. 아직물리재배치확인없어실패DOCK_TEST_5793582207d24bc4a9beabdafcae85b8의recovery_required=true는유지했다. 실패원문/결과FAILED 보존.
로봇원본5파일hash와후보manifest대조후 source5개+install3패키지 original.tar.gz 백업. PC/로봇SHA256 6cd5f3ff8f408cc4a7a5ef80d5973ce47afd4115c4c6efed46b12f5f8628c509일치. 로봇colcon farm_navigation/farm_wall_controller/harvest_robot 순차빌드27초성공. underlay재선택경고있음;빌드실패아님. 로봇ctest1/1 및새C++정지대기검사통과. 설치Python2개hash후보와일치,설정생성기로 .45/.8/.5 및재획득선택검증.
/home/vic/Downloads/pc_dummy_dock_fsm_20261024/wall_alignment_wait_v2.json신규,기존handoff_fsm.json의wall_config참조만변경. age=.45/observation_wait=.8/dwell=.5/footprint_padding=.01,충돌·취소·정지·소유권보호유지. 실제노드기동없음. PC운영소스덮어쓰기없음. runs/handoff_wait_deploy_20261024에원본/배포receipt/빌드·검증/종료/rollback.py 보존. rollback은프로세스부재·afterhash일치후원본tar/설정복원,후보C++빌드캐시보존이동으로재설치혼입방지;문법검사만수행,실제원복미실행.
PCdummy204039/bridge204098은계속실행중으로중복기동금지. 재배치확인→실패기록보존수동복구→사용자로봇laun→vinit→zen→dzen→vstat 순서. 웹확인후실제파라미터·정합·costmap·더미복구상태확인필요. laun카메라포함. 종료중harvest Destroyable경고후finishedcleanly확인,기존종료경고까지해결했다고표시하지않음. 실기성공미검증/초기위치발행/재기동/이동/commit/push없음.


### 2026-10-24 코너 종료 대신 전진 곡선 대안 후보
사용자 방향 승인 후 운영파일을보존한별도runs/corner_alternative_candidate_20261024에Corner RPP 후보구현/PC빌드. 정상RPP유지,경로방향맞춤NoValidControl시에만속도규제/각속도·가속제한을따르는전진곡선3개기존충돌검사,전부불가시0출력후재평가/기존progresschecker유지. 취소/TF/최종자세/후진보호유지의도. 실패저장입력에서제자리v0,w-.1은.89초충돌,전진v.02이상+w-.1의1초표본검사통과. PC기존회귀CTest1/1통과는새fallback전체검증아님. 새메서드전체취소/실패/재개통합,실제제동·smoother궤적,진행성,로봇1.3.11호환미검증이므로운영적용준비완료아님. 운영코드/설정/설치본/기동/이동/commit/push없음. 원본hash와한계/후속검증REVIEW.md보존.


### 2026-10-24 일시적 실패 대기 1차 후보·운영 미적용
사용자승인으로현재로봇설치코드/선택설정백업,조사기준74개hash일치확인. 별도runs/transient_wait_candidate_20261024/candidate에수확모듈6개변경:명령공백watchdog0출력대기/최신연속정지증거후재개,전송전DeviceNotStarted만FSM재대기,비동기어댑터분류전달,운송이벤트대기기한을장치실행기한과분리. 취소/epoch/owner/실제충돌/센서만료/전송불명보호유지. 일반normal출력AST불변.
실제후보gate/FSM경계23개+실제runtime메서드통합harness18개=41오프라인검사통과. 전체ROS/DDS/실기검증아님. 센서/TF만료래치·odom샘플간격·align5mm/3초등은이번미변경,전체12개개선완료아님. 상세REVIEW.md/patch/hash/tests로그보존. 운영소스/설정/설치본변경·재기동·이동·commit/push없음.


### 2026-10-24 센서·TF 재관측 및 align 보완 후보 — 운영 미적용
사용자 승인으로 1차 후보 위에 2차 후보를 별도 `runs/transient_sensor_candidate_20261024`에 작성했다. 운영 설치 Python 74개를 SSH로 다시 읽어 기존 백업 해시 일치를 확인했다. 입력 과거 만료/TF 부재를 0출력 재관측으로 분리, worker 대기 중 raw 명령 재개 차단, 최신 연속 정지 확인 후 재개, odom 간격만 인계 선택형 대기로 분리했다. 실제 과속·미래/역행·형상·취소·epoch·소유권·충돌 보호는 유지한다. align의 5mm 즉시 실패는 현재 자세 증명 재계산으로 대체하되 고정 원호 끝점 재진입 한계와 16도 한계를 출력 직전에도 검사한다. 전체 장애물 마스크 키에서 갱신 시각을 제외했다.
후보 재관측/벽 관측 대기는 5초로 맞췄으며 센서 유효기간(odom 등 .5초, wall .45초)은 불변. 상위 전체 Action/FSM/Spin/progress 기한은 계속 진행하므로 잔여 기한을 넘는 대기는 여전히 실패할 수 있다. 자동 Goal 재전송 없음. 1차 후보의 장치 생성자에 잘못 전달된 event_timeout_s도 제거하고 실제 signature 검사를 추가했다(운영 미적용 후보 오류).
실제 runtime/FSM/비동기 어댑터와 대역 입력을 연결한 검사 포함 Python 137개, 로봇 동일 헤더 C++ 7개 시나리오 통과. 실제 spawn 충돌 프로세스의 입력 공백/3.15초 계산 후 복구·종료 포함. 전체 ROS/DDS/Nav2 서버·실기·다른 로봇 E2E 검증은 아님. 공통 모듈 2개는 후보에서만 수정했다. 운영 소스/설치/설정·기동·이동·commit/push 변경 없음. 상세 변경·검증 로그·잔여 기한 한계·원복은 후보 REVIEW.md와 verification.json에 보존. 기존 백업·미커밋 변경·1차 후보 보존.


### 2026-10-24 실제 ROS 서버 격리 검증 — 상위 기한 경합 확인
사용자 요청으로 PC domain191/loopback/validation_no_hardware namespace에서 실제 Nav2 ControllerServer·BehaviorServer와 로봇 현재 WallController 소스의 격리 빌드, 후보 runtime/Navigator/SpinClient/TransferMission을 검증했다. 구동기 연결 없음, 고정 자세·시험 관측·빈 costmap 사용. odom/wall/costmap 지연 중 0출력 및 복구 후 동일 Goal 재개, TF 재조회 중0/복구 후 worker 반환, 취소 후 terminal/출력 차단, 실제 spawn 충돌계산 포함 align 지연·재개·취소 확인. 관측 지속 중단은 약5.494초 후106, 고정 자세에서7초 후 관측 중단하면 총10초/대기3초에 progress105 발생. 후보만으로 상위 기한 소진에 따른 종료를 방지하지 못함을 확인했다.
검증용2초 Navigator/FSM/Spin 기한은 각각 timeout/DEVICE_TIMEOUT/Spin701로 종료하고 자기 Goal 정리 및0출력을 확인했다. 운영120초 등을 그대로 경과시킨 시험은 아님. 시험 settle_s=.3/tf_timeout_s=.5 사용, PC Nav2 1.3.13과 로봇1.3.11 차이 명시. 실기/Zenoh/팔/운영 FSM 전체 성공 아님. 후보 추가수정·운영 적용/재기동/이동 없음. 운영 설치 Python74개 백업 해시 및 후보 해시 불변, 검증 프로세스 모두 종료. 상위 기한 정책 보완 또는 한계 수용 전 운영 준비 완료로 표시하지 않는다. 로그/소스/YAML/버전/상세결과는 runs/transient_ros_validation_20261024/REPORT.md 및 run1~3에 보존. commit/push 없음.


## 2026-10-24 인계 정지 대기 실행시간 후보 및 실제 ROS 무구동 검증

사용자 승인 범위: 일시 정지로 progress·상위 FSM이 먼저 만료되지 않도록 후보 보완, 실제 ROS 무구동 검증. 운영 적용·재기동은 승인 범위 밖이며 하지 않았다. 기준 HEAD `cf870da`; 기존 미커밋 변경과 성공 실행본·백업 보존.

`runs/pause_budget_candidate_20261024/REPORT.md`에 변경표·검증·한계를 기록했다. 인계 전용 0 출력 대기 누계로 progress/Spin/wall/차체 상위 기한을 연결하고 실행별 제외 상한 30초, 연속 입력 대기 5초와 취소·정지·충돌 보호를 유지한다. 후보 Python 9개 및 전용 C++ 패키지만 별도 경로에서 변경했다. 일반 주행 설정과 운영 실행본은 변경하지 않았다.

직접 검증: 격리 PC ROS domain191의 실제 Nav2 서버에서 progress 10초를 넘는 관측 대기 후 같은 Goal 완료(10.548초), 상위 FSM 2초를 넘는 관측 대기 후 완료(3.562초), odom 지연 중 Spin 0 출력·복구·취소 확인. 대기가 없으면 progress/FSM/Spin의 원래 제한이 작동했고 지속 벽 관측 단절 5.499초에 중단했다. 초기 시계 계산 결함과 실패 로그도 보존하고 수정 후 재검증했다. Python 143개·C++ 7개 통과. PC Nav2 1.3.13, 로봇 1.3.11 차이가 있어 로봇용 빌드와 전체 실기/FSM 시험은 남았다. 전체 운영 완료·실기 성공으로 해석하지 않는다.

다음 작업: 운영 적용 전에 버전별 빌드·기존 설치본 대조와 사용자 사전 안내. 원복: 후보 overlay 미사용 시 기존 실행본 유지. 시험 프로세스 종료 확인, 로봇 이동/재기동 및 Git commit/push 미수행.


### 2026-10-24 로봇용 pause budget 후보 빌드·플러그인 로드 확인 (운영 미적용)
사용자 승인으로 로봇 Downloads/pause_budget_robot_20261024에서 ARM64/Nav2 1.3.11용 farm_wall_controller 및 farm_navigation/harvest_robot 별도 빌드. ROS init/노드/Goal 없는 pluginlib 생성·해제로 4종 플러그인 로드, 기존 underlay 위 후보 library 경로, 설치 Python import·전용 설정 선택 확인. 사용 API 헤더3종은 PC1.3.13과 동일하나 전체 동작 동등성 검증 아님. 운영 소스/설치/설정250개 전후 불변, 기존 성공 Python74개 해시 일치, 주요 운영 PID 유지. 기존 백업 유지 및 PC 추가 스냅샷 보존.
실제 laun의 run.bash→terminal.py 경로를 확인하여 launch 분기만 후보 overlay 및 handoff JSON을 선택하는 적용 제안 diff를 준비했다. 운영 파일 수정/재기동/이동/commit/push 없음. 적용 전 사용자 안내·승인 및 현재 상태 확인 필요. 원복은 적용 직전 별칭 wrapper 백업 복원+새 터미널 재기동. 상세 빌드·버전·로드·증거·한계·적용 순서: runs/pause_budget_robot_20261024/REPORT.md. 로봇 lifecycle/전체 FSM 실기 검증은 남았다.


### 인계 pause budget 후보 실행 선택 적용 — 2026-10-24
사용자 승인으로 실제 laun wrapper 두 파일만 백업 후 적용. 기존 운영 소스/install/설정250개 불변, 로봇 후보 overlay와 새 handoff JSON 선택. --check 통과/충돌PID없음. 이번 확인 시 양측 실행은 이미 종료되어 종료신호 미전송. 영구 인계 journal 4건 모두 active/recovery false이며 원본 보존. 사용자 스테이션 재배치 확인 대기, 실제 재기동/초기위치/이동 없음. 원복 백업 activation-backup-20261024_183013; 상세 runs/pause_budget_apply_20261024/REPORT.md. commit/push 없음.


### 2026-10-24 pause budget 운영 기동 후 정지 확인
사용자 스테이션재배치·기동·웹표시 확인 후 실제 PID 후보경로/libmaps·파라미터·lifecycle active 확인. progress4종/Spin후보 및wall .45초/대기5초 반영. IDLE/ready,최근정지odom30개,출력·odom단일publisher. 일반/인계2cm grid와64×54/62×52형상유지,현재정지충돌검사통과. 레이저지도689점 중앙1.44cm/p903.16cm. PC더미ready/recoveryfalse 및로봇prepare왕복success(DUMMY_ONLY). 이번이동/재설정/Action실행없음. 상세 runs/pause_budget_restart_check_20261024/REPORT.md. 반복허용·window/인계실기는아직미수행,commit/push없음.


### 2026-10-24 후보 #59 반복 준비
사용자 승인으로 PC 더미 기록 백업 후 ready/prepare 확인, 25fabab7b348 작업 1회 반복 허용(300초). 로봇 구독 전용 bag PID525077/startticks10184311,15분상한,모든토픽 구독·파일증가 확인. runs/pause_budget_window_20261024에 근거 보존. 사용자 웹 전송 대기이며 이동/수확/인계 요청 미전송,도착·더미완료·새기준저장은아직미확인.


### 2026-10-24 18:39 후보 window+PC더미 성공
사용자 #59 웹 요청, task25fabab7b348 SEC01_TASK001. 이번 accepted 도착 위치오차34.83mm/방향1.345도, request cb7e3a995a2e4b6bb26915ee55fbbaaa. PC더미 새attempt7a064d19… SUCCESS수확2,전체SUCCESS,최종IDLE/ready적재2. SUCCESS전 remember_window 저장 호출·실패시invalidate 계약과 이번이벤트로 새기준저장경로확인(메모리직접조회아님). 인계 동일시각map/odom기준은아직미확보. 수집기만종료,인계요청없음. runs/pause_budget_window_20261024/RESULT.md/이벤트/저널보존. 실제팔·전체인계성공아님,commit/push없음.


### 2026-10-24 후보 인계 웹 시험 준비
사용자window위치유지·이동가능확인. 동일PID/IDLEready적재2/정지/현재형상검사통과/더미prepare성공/인계endpoint확인. wall관측은tracker생성전미발행하는구조,진입후검증필요. 수집PID527824 startticks10210120,15분상한/모든토픽구독. runs/pause_budget_handoff_20261024/READY.md에근거. 사용자버튼대기,인계요청·이동·재기동·설정변경없음.


### 2026-10-24 18:45 인계 후보 DOCK_READY 실기 확인
사용자dock_transfer task7974ad4f…/transfer41fffa2d… 진입goal완료→벽정렬goal완료→DOCK_READY feedback18:45:42 수신. TF/벽준비일시대기후재개확인. WAIT_DOCK_STABLE/최근odom30개0/적재2. 다음사용자DOCK_STABLE만안내,배출·복귀아직미수행. bagPID527824 계속수집(15분상한). 상세runs/pause_budget_handoff_20261024/DOCK_READY.md. 에이전트추가명령·설정변경·재기동·commit/push없음.


### 2026-10-24 운송 대기 중 로그 수집 종료 확인
사용자 STABLE 전까지 수집중지요청. PID527824는이미15분상한으로18:56:45정상기록종료,이번조회에서부재확인하여추가종료신호없음. bag_20261024_184145 metadata/mcap완결,로봇원본유지/PC사본보존진행. 운영PID522218/522199/522200유지,이벤트·정지서비스·취소요청없음. WAIT_DOCK_STABLE의새상태조회는이번미실행이므로직전확인상태로만기록. 사용자STABLE전알림후새상태/준비검사와수집재개필요.


### 2026-10-24 운송연동 재시험 전체종료
사용자 스테이션→#59수확→새관제운송인계 재시험 승인. 기존DOCK_TEST7974…의 정확한ActionUUID만취소,return_code0/terminal5(CANCELED)/최근odom30개0 확인. 이동/복귀/배출요청없음. 취소뒤ERROR/recovery_required=true이며성공으로덮어쓰지않음. PC더미도stop에따라전역recovery_required=true. 기존기록전후백업보존.
수확launch522163와자식·드라이버,로봇hubbridge522657/dummybridge522712,PC더미252660/bridge252718를검증한PID/startticks기반SIGINT로종료. 양측remaining0. 수확노드종료시Destroyable경고있으나cleanexit/잔존없음,원인해결주장없음. 관제서버·운송로봇미접근/미변경.
스테이션수동재배치가능안내. 아직사용자재배치확인전이므로복구journal해제/새기동/초기위치발행없음. 사용자재배치확인뒤취소기록보존한수동복구처리와PC더미복구,기동순서안내필요. 기존성공코드/후보선택/백업유지,commit/push없음.


### 2026-10-24 스테이션 재배치 후 복구 표시만 해제
사용자 명시승인/실제스테이션재배치확인/양측종료확인. 로봇 DOCK_TEST7974…의 recovery_required만false 및manual_recovery근거추가,기존CANCELED결과/ID/시각/다른records불변 검증. PC더미는종료중exclusive journal.lock확보후전역recovery_required만false,records/history완전동일. 전후백업runs/transport_restart_20261024/manual_recovery 및manual_recovery_pc. 기존운영소스/install/설정250개해시불변. 후보재빌드/교체/초기위치/기동/이동없음. 다음사용자PC더미→PCbridge→로봇laun까지실행,에이전트IDLE/정지확인후vinit,그뒤zen/dzen. 아직IDLE실행확인전. commit/push없음.


### 2026-10-24 20:18 운송 연동 재시험 #59 준비
사용자 웹 연결 확인 및 동일 작업 1회 반복 승인. 기존 코드·설정·기동 상태 변경 없이 최신 IDLE/ready, 최근 odom30개 정지, 출력/odom 각 단일 publisher 확인. 일반64×54/인계62×52cm 및2cm costmap 유지, 현재 정지 형상 검사 통과(전체 경로 통과 보장 아님). PC더미 이력 백업/records·history 불변 확인 후 prepare 성공 및 #59 task25fabab7b348 1회 반복 허용(20:18:32부터300초). 구독 전용 수집 PID555201/startticks10790370,15분상한,전체14토픽 구독 및mcap생성 확인. 증거 runs/transport_window_retest_20261024. 사용자 웹 전송 대기; 이동·인계 요청/재기동/commit/push 없음. 다음 window 도착·새 더미attempt 완료·새 도착기준 저장 확인 후 인계 사전 안내.


### 2026-10-24 20:22 운송 연동 재시험 window 완료
사용자 #59 웹 요청으로 SECTION_APPROACH/WINDOW_MOVE accepted, 도착오차26.97mm/1.22도. 새 arrival bfe32fc5… 및 PC더미 새attempt c04c6969… SUCCESS수확2/실패0, 최종IDLE/ready/적재2/최근odom30개0. 실행본 SUCCESS전 remember_window 호출과 이번성공 이벤트로 저장경로확인(메모리직접조회 아님). 별도카메라 control_readback_stale 종료1, detector/rectify종료0; 이번태그보정성공아님. 코드·설정·재기동·인계명령변경없음. 수집기만종료하고 로봇원본/PC사본보존. 상세 runs/transport_window_retest_20261024/RESULT.md. 다음인계전안내필요,commit/push없음.


### 2026-10-24 20:51 실제 운송 연동 인계 준비 결과
사용자dock_transfer a64d… 진입·벽정렬 완료, DOCK_READY20:51:03.538 직접수신/관제수신확인. 수확WAIT_DOCK_STABLE/최근odom30개0/적재2. 운송은20:50:07부터대기해20:51:07 DOCK_READY시간초과FAILED,수확보고후약3.87초뿐. 웹실물snapshot에서다음이벤트allowedfalse,DOCK_READY전달기록없음. 운송내부원인은직접미확인. 다음버튼보류안내,강제이벤트/배출/복귀/재기동/코드설정변경없음. 수집563856은15분상한으로계속,초반진입은수집전이라launch로그보완. 상세runs/transport_handoff_retest_20261024/RESULT.md. 전체인계미완료,commit/push없음.


### 2026-10-24 20:55 운송 연동 재시험 종료
사용자 전체종료/재배치후재시험 요청. 현재 수확 인계 a64d… UUID만 CancelGoal, ack0/terminal5(CANCELED)/최근odom31개0 확인. 종료직전ERROR(CANCELED·복구필요),IDLE확인아님. 로봇launch552969와자식·driver,bridge553658/553713,recorder563856 및PCdummy264119/bridge264177 SIGINT 종료,양측selected remaining0/로봇별도ps잔존없음. 수확노드는종료시Destroyable경고후cleanexit. 기존코드/설정/저널취소결과/로그보존,복구표시해제미수행. 관제서버·타팀운송로봇미변경. 근거runs/transport_shutdown_20261024. 사용자스테이션재배치가능,재배치확인후복구처리/재기동/IDLE확인→vinit 순서 필요. commit/push없음.


### 2026-10-24 인계 a64d 재배치 후 복구 표시 해제
사용자 스테이션 위치·방향 재배치 확인 및 명시 승인. 로봇 수확/드라이버 부재 재확인 후 해당 CANCELED 레코드만 recovery_required=false/manual_recovery근거추가,기존결과/ID/시각/다른레코드불변 검증. PC더미 종료확인+exclusive journal.lock으로 전역 recovery_required만false,records/history완전동일 검증. 전후백업runs/transport_shutdown_20261024/manual_recovery 및manual_recovery_pc(로봇백업도PC복사). 코드·설정·초기위치·재기동·이동 변경 없음. 다음 PCdummy→PCbridge→로봇laun 사용자기동,IDLE/정지확인후vinit,이후zen/dzen/vstat. 현재종료상태여서IDLE미확인. commit/push없음.


### 2026-10-24 21:00 재배치 후 #59 재시험 준비
사용자기동·웹표시·vinit성공확인후 read-only검사: 새boot ee021a052ae6421ab32371238464fb66,IDLE/ready/적재0,최근odom29개0,일반64×54/인계62×52 및2cm costmap 유지/현재형상검사통과. scan693점 지도거리중앙2.07cm/p904.46cm. 더미prepare성공/recoveryfalse/기록백업후동일#59 1회반복허용21:00:05부터300초. 구독수집PID568140/startticks11041844,15분상한,전체14토픽구독/mcap생성확인. runs/transport_retry2_window_20261024에보존. 코드·설정·이동요청·인계요청·commit/push없음. 사용자웹전송대기.


### 2026-10-24 21:02 #59/태그/더미 완료
이번웹#59 accepted 도착오차27.89mm/0.659도,새arrival9a8add9f…/event7f1e3b8f…,더미새attemptbb70efb4…SUCCESS수확2/실패0. 동일실행본저장계약+이번이벤트로새window기준저장경로확인(메모리직접조회아님). AMCL21:01:50 TAG_CORRECTION_APPLIED:1 확인. 최종IDLE/ready/적재2/odom30개0. 수집기만종료,로봇원본/PC사본보존. 코드설정·재기동·인계/운송요청없음. 상세runs/transport_retry2_window_20261024/RESULT.md. 인계전양측이벤트순서및수집준비필요,commit/push없음.


### 2026-10-24 21:04 인계 재시험 벽 관측 대기초과
사용자dock_transfer6b4c… 진입완료후wall21:04:20.509시작→28.135 Wall observation wait exceeded.23.479runtime costmap headerage.5319>.5로대기로그,연쇄원인미확정. ERROR/DEVICE_FAILED/DOCK_READY미확인/배출복귀없음. odom31개0+사용자정지확인. bag은실행후수집시작해초반누락,launch/저널보완. 수집기만종료,코드설정/재기동/추가명령없음. runs/transport_retry2_handoff_20261024/RESULT.md 및로그보존. commit/push없음.


### 2026-10-24 센서 정지대기 작업 유지 후보·통합 검증(운영 미적용)
사용자 센서지연 중 정지/작업유지/회복재개 및벽·watchdog·상위FSM 통합검증 승인. runs/sensor_hold_candidate_20261024에 별도후보. 로봇실행선택본백업/설치Python바이트대조일치,기존성공본·백업·미커밋변경보존. 인계전용 명시선택으로센서재관측5초·벽관측5초 실패와정지누계30초제외상한해제;취소/소유권/epoch/충돌/공간/속도/시각보호유지. 상위FSM/body/Nav2/Spin은기존주입시계를통해동일정책사용,일반주행미변경.
Python147/C++wall10/CTest1 통과. 실제PC ROS domain191무구동:wall38초정지중1488개출력0/동일Goal완료,상위FSM2초제한에서도38초대기후완료,wall+costmap/odom각8초동시지연후복구성공,6초대기취소후출력차단. 정상입력무진행FSM2초/progress10초제한유지. 로봇1.3.11빌드/실기/전체FSM미검증,PC1.3.13결과와구분. runtime자체heartbeat단절·프로세스장애까지무조건유지하는수정아님. 운영적용/재기동/이동/commit/push없음. 상세변경표/검증/남은범위/원복은runs/sensor_hold_candidate_20261024/REPORT.md,시험프로세스정리확인.


### 2026-10-24 센서 정지대기 후보 로봇 빌드·플러그인 로드 완료(운영 미적용)
사용자 로봇용 빌드·로드·적용 준비 승인에 따라 /home/vic/Downloads/sensor_hold_robot_20261024 별도 후보에서 3개 패키지 빌드 완료. ARM64/Nav2 1.3.11에서 플러그인 4종 생성·해제 및 실제 로드 경로, Python 설치 경로·정책 선택 확인. ROS 노드/Goal 없이 검사. C++ assertions 10개/CTest 통과, ldd -r 누락·미해결 없음. 운영 관련 비교 파일 468개 해시 및 주요 PID 5개/명령 동일. 기존 성공본·백업·실패 기록 보존, 운영 적용/재기동/이동/복구 해제/commit/push 없음. 운영 wrapper 두 파일 변경 제안과 적용 직전 백업·원복 절차 준비. 실제 lifecycle/인계 실기 미검증. 상세 runs/sensor_hold_robot_20261024/REPORT.md 및 ACTIVATION_PLAN.md. 이전 PC ROS 검증과 이번 로봇 빌드·로드 범위를 구분한다.


### 2026-10-24 21:25 센서 대기 후보 운영 경로 적용·재기동 전
사용자 후보 운영 적용/종료/재기동 안내 승인. 종료 직전 ERROR/DEVICE_FAILED, task 없음, 최근 odom30개 속도0. 실패 인계 DOCK_TEST_6b4c… active=false/recovery_required=true 기록 보존. 런치566901과 자식 총18개 SIGINT 종료 확인(추가 SIGINT로 수확 노드 종료), 잔존 없음. 종료 중 기존 드라이버 context invalid(exit1), sllidar exit-6 기록 보존하며 이번 변경 원인으로 단정하지 않음. PC 더미/브리지 및 로봇 브리지 실행 없음, PC 더미 recovery_required=true.
실행 선택 run.bash/terminal.py 두 파일만 sensor_hold_robot_20261024로 전환. 로봇 원본 백업 /home/vic/Downloads/sensor_hold_robot_20261024/activation-backup-20261024_212510. 이전 비교대상468개 중 해당2개만 변경, 기존 성공 설치본/설정 유지. launch --check 후보 경로/충돌PID없음 확인(실제 기동 아님). 사용자가 스테이션 재배치 후 알려주도록 안내했으며 현재 확인 대기: 복구 표시 미해제, 초기위치 발행/재기동/이동 없음. 상세 runs/sensor_hold_robot_20261024/activation 및 ACTIVATION_PLAN.md. Git stage/commit/push 없음.

스테이션 재배치 사용자 확인 수신 후, 종료 상태를 재확인하여 실패 인계 한 건의 recovery_required만 false로 변경하고 manual_recovery 근거 추가. FAILED 결과/시간/다른 기록 동일 검증. PC 더미는 활성 작업 없음·모든 기록 terminal 확인 후 최상위 recovery_required만 false 변경; history/records 바이트 의미 동일 검증. 양측 원본 백업 보존. 로봇·PC 프로세스 재기동/초기위치/이동 없음. 다음: PC dummy→PC bridge→로봇 laun, 에이전트 IDLE/정지 확인 후 vinit→zen→dzen→vstat. 같은 #59 반복 허용은 기동 후 별도 서비스 준비 필요하며 아직 수행하지 않음.


### 2026-10-24 21:30 후보 실행 후 웹 #59 관찰
사용자가 직접 기동/초기위치/웹 명령. 에이전트는 읽기·경량 구독만 수행. 후보 sensor_hold 설치 경로 및 handoff controller 로드 maps, wall_alignment.wait_until_fresh=true 확인. 초기위치 발행 기록 및 IDLE/ready/odom30개0 확인 뒤 웹 주행 시작.

SECTION_APPROACH와 WINDOW_MOVE 완료. 21:29:59 window accepted, 오차29.086mm/0.005274rad. arrival request29251f4b8db44783b2d5f32663a7b596 및 새 stamp1792844999178232191 이벤트 기록. 이후 ARM_REJECTED: PC 더미21:29:59.208 duplicate ID 실제 로그 확인. 재기동 후 반복 허용권 미설정 상태였으며 새 더미 수확 완료 아님. 최종 ERROR/ARM_TRAVEL_NOT_READY/loaded0, 최근 odom30개0. 같은 작업 반복 허용 서비스 호출/복구/재전송/인계/이동/재기동/설정 변경은 수행하지 않음.

태그 캡처도 code1로 종료 기록. 상세 원인은 아직 미확정이며 이번 더미 duplicate 거절과 구분. 현재 도착 이벤트를 메모리 내부 저장/복구 후 재사용 가능성까지 검증한 것으로 간주하지 않음. 기록: console.log, live.jsonl, latest.json, dummy.log. 인계 진행 전 더미 반복 준비 및 수확 노드 복구 필요.

### 2026-10-24 21:35 중복 ID 실패 후 수확·더미 복구
사용자 다시 시험 가능하도록 복구 승인. 이후 운송측 개입 금지 명시: 관제 읽기 확인 이후 운송 명령/변경 없음. 수확 노드578985만 SIGINT종료 후 동일 인자/환경/후보로582108 재기동, Nav2/AMCL/드라이버 기존PID 유지. 실패 저널/명령/로그 백업, 코드·설정·초기위치/이동 명령 변경없음. PC 더미 공식 recover/prepare 성공, records/history 동일 검증, IDLE/ready/복구false 확인. repeat_last_harvest21:34:53 성공으로 #59 1회300초(21:39:53까지) 허용. 수확 IDLE/ready,odom30개0 확인. 다만 pose 약(1.455,-1.319),yaw1.527로 이전window와 달라 사용자 실제 재배치 여부 질문 대기; 이동 준비완료로 단정하지 않음. 카메라 control_readback_stale 종료 확인, detector/rectify는code0/TBB_FINALIZED. 카메라 복구는 미완료. 수확 재기동으로 이전 메모리 도착기준은 소실, 새 작업 도착기준 필요. 상세 runs/sensor_hold_recovery_20261024.

21:36 사용자 초기스테이션 수동재배치 확인. 기존 vinit IDLE/정지보호 통과후(21:36:21) x.104/y-1.105/yaw87.79 초기추정 발행. 이후IDLE/ready,odom30개0,pose(.09487,-1.11590),yaw1.52543. 레이저-map 끝점687개 median34.06mm/p90 80.78mm/5cm이내75.55%, 전체주행 안전증명 아님. 두 costmap2cm,일반64x54/인계62x52 현재자세검사통과. 일반제자리+.1rad 가상경로는충돌검사실패(실제주행경로아님),안전조건 유지/clear서비스 미호출. 출력publisher/odom 각1. 기존코드설정으로카메라만583295재기동,raw/rect/detect약8Hz/TAG_ADAPTER_RUNNING 확인. 과거control_readback_stale근본원인 수정없어재발가능성남음. #59허용21:39:53까지1회,실제이동명령없음.

### 2026-10-24 21:41 브리지 복구 후 #59 실패
사용자 더미반복허용→브리지복구→대기작업관찰 승인. PC더미recover/prepare/repeat 성공21:41:04(300초). 로봇 관제브리지만579435→585474 동일 인자/환경/바이너리/설정 재시작. 관제ready.harvest=true 복구 및 대기#59 자동시작21:41:19.559. 일반controller Goal21:41:19.651→20.353 detected collision ahead/106, 작업FAILED21.351. SECTION_APPROACH 단계,window도착/더미수확/새도착기준 없음. 더미repeat는소비되지않음(21:46:04만료). 최종IDLE/ready/loaded0/odom31개0. 기존정적검사에서 일반costmap제자리+.1rad 접촉이 있었으나 이번controller 실제검사점과 동일원인인지 미검증. 충돌조건변경/재전송/인계/운송명령 없음. 카메라약8Hz 유지. 실패이벤트5b87baca…및launch.log/web.after.json/robot/live.jsonl 보존. 관찰프로세스585472만종료,운영프로세스유지.

### 2026-10-24 21:44 전체 종료·costmap 메모리 정리
사용자 이전대조 분석을 중단하고 초기위치 재배치/내부정리/costmap정리 요청. 조회 시 기존 메인launch/Nav2/드라이버/PC더미·PC브리지는 이미없음. 남은 별도수확582108/카메라583295/관제브리지585474와 자식10개 SIGINT 종료,잔존없음. 전체controller/behavior/driver/AMCL/velocitysmoother/카메라/bridge 프로세스없음 확인. costmap 프로세스 종료로 이전 휘발성 격자/voxel 상태 소멸,다음기동에서 재생성;지도/설정/충돌보호 변경·로그삭제 없음. PC더미 journal recoveryfalse/미완료없음/row복구없음 확인,원본백업만. 사용자에게 스테이션 재배치 가능 안내. 다음 재기동후 초기위치/새관측costmap 확인 및 같은#59반복허용을 주행 직전에 수행해야함. 이동/초기위치발행/재기동/운송명령없음. 자료 runs/station_clean_restart_20261024.

### 2026-10-24 21:47 완전종료 후 스테이션 재기동 준비 확인
사용자 재배치/수동기동 확인 후 읽기검증 및 더미반복허용 승인. 후보수확587544/런치587515,새boot2381… IDLE/ready/odom29개0. 사용자vinit21:46:11발행기록 확인. 레이저끝점690개 median21.87mm/p90 70.20mm/5cm82.61%. 새일반/인계costmap해상도2cm,형상64x54/62x52,stationary 및+.1rad가상회전 모두통과. 일반최소거리약.210m(이전유지시.018m),lethal454(이전1305);rolling창/좌표다르므로 단순cellcount로잔존원인확정불가. cmd_vel_nav/odom 각단일publisher. 카메라raw/rect/detect약8Hz/adapter기동. 웹ready.harvest=true,paused.harvest=true(사용자웹해제필요),#59과거FAILED/재시도가능. 더미recover/prepare/IDLE검증/이력동일/반복1회성공21:47:30→21:52:30까지. 이동/웹버튼/재시작/설정변경없음. 자료 runs/clean_station_ready_20261024.

### 2026-10-24 21:49 완전재기동 후 #59 성공
사용자웹전송,관찰만수행. SECTION_APPROACH/WINDOW_MOVE 완료,이벤트SUCCESS21:49:15.886/더미새attempt1976d76be6484a11806139c449cadf0a SUCCESS 수확2/실패0(expected1과더미2기존동작구분). 새arrivalrequest79b17b064b5e4934a4b78aa73597a159,plan13ed447738e54c08bf843121d8657d5a,stamp1792846154151270408,accepted true,오차29.106mm/0.02727rad. 실행설치communication 성공콜백remember_window 계약과이번이벤트로새기준저장경로확인(메모리직접조회아님). 최종IDLE/ready/loaded2. AMCL TAG_CORRECTION_APPLIED:1 21:49:04 확인. 인계경량관찰590109 10분제한으로기동,clean_handoff/live.jsonl;인계명령없음,사용자버튼대기. 기존코드설정/안전조건변경/운송개입없음. 자료 runs/clean_station_window_20261024.

2026-10-25 20:52 사용자 스테이션 위치·방향 재배치 확인. 종료 재확인 및 원본SHA동일 확인 후 인계009b… 한건 active/recoveryfalse, resultFAILED 및 manual_recovery 추가. 실제 종료시각/ROS취소응답은 미확인이므로 생성하지 않음. previous_record에 원래 필드 전체 보존,다른행 동일 검증. 로봇백업 /home/vic/Downloads/sensor_hold_robot_20261024/manual-recovery-20261025_205244. 코드설정/PC더미이력/운송측변경없음. 재기동은 사용자 수행,더미반복허용은기동후별도.

### 2026-10-25 20:55 재기동 준비 검사
사용자 정합/costmap/더미/웹확인 및#59반복허용 승인. 새boot e1ddee… IDLE/ready/최근odom23개0. 실행sensor_hold후보3954,초기위치발행20:53:35확인. 레이저694끝점 median29.82mm/p90 58.55mm/5cm86.46%. 일반64x54/인계62x52,2cm costmap현재자세 및+.1rad검사 모두통과(일반여유약16cm);전체경로보장아님. 출력/odom publisher각1. TAG_ADAPTER_STARTED. 웹 Action ready.harvest=true지만 paused.harvest=true 및 수동인계미확정 차단. 어제DOCK_TEST_009b… 관제UNKNOWN 남음,로봇저널복구와관제정리별개. 사용자웹조작원칙에따라관제수정/명령없음. 더미recover/prepare/IDLE/이력보존 검증 및repeat1회성공;유효기간은repeat_last_harvest.json wall_s+300초. 관제미확정정리 전 주행보내지않도록안내. 자료 runs/station_ready_20261025.

### 2026-10-25 21:04 #59 window/더미 성공
관제재개후 사용자#59전송,에이전트구독만. SECTION_APPROACH/WINDOW_MOVE 완료,이번SUCCESS21:04:27.031/수확2실패0(expected1과더미출력2 구분). 더미새attemptdf64c252ca714e7eb38318fe0472fa4c,완료21:04:26.910. 새arrivalf326a7f14bf8496bb10b45cd0f6a1867/plan904683bced3b47aba66aed8a6c6ff50d/stamp1792929864965796828 accepted true,오차28.613mm/0.015325rad. 기존실행설치본의SUCCESS후remember_window계약 및새이벤트로저장경로확인;내부메모리직접조회와구분. 최종IDLE/ready/loaded2,별도인계명령없음. 인계관찰8792 600초제한구독/handoff_20261025,사용자버튼대기. 코드설정/재기동/운송개입없음. runs/window_retry_20261025 기록.

## 2026-10-25 — 실물 반복 시험 웹 도구 후보
- 사용자 승인: PC 미니 관제 요청. 대상: robot/tools/trial_console, 인계 문서.
- 변경: 종료/복구/더미 반복·수량 후보 및 격리 검증. 시뮬 공통 로직/설정 변경 없음. 실제 운영 적용 없음.
- 검증: HTTP·저널 테스트 2개 및 domain191 실제 ROS 완료·반복·취소·수량 검증 통과. 실기 미실시.
- 원복: 신규 도구 서버 종료. 운영 더미 원본 미변경. 상세 TRIAL_CONSOLE_20261025.md.

## 2026-10-26 — 반복 시험 콘솔 추가검증
- 사용자 검증 요청에 따라 tests/ros_http_integration.py 추가. HTTP→ROS 실제 격리 더미 완료·취소·반복·수량 검사 통과. 시뮬/실물 운영 로직·설정 변경 없음, 운영 적용 없음. 자료 runs/trial_console_20261026. 원복은 추가 시험 파일 제거로 충분하며 기존 실행본은 변경하지 않음.

## 2026-10-26 — 벽 시간 보정 별도 후보
- 승인: 사용자 시간계산 분리 후보 및 오프라인검증 요청. 운영공통소스 수정 없음, 별도 runs/wall_clock_candidate_20261026 후보2파일.
- 고정시작시각/유효실행누계분리 및 수치진단. 기존안전/설정 유지. 신규19·기존대기10·CTest1/1 및 PC ROS빌드통과. ARM/실기미검증.
- 영향: 아직 실물/시뮬 실행경로 미적용. 원복: 후보미사용. 운영적용전별도안내. 상세 WALL_CLOCK_REPRO_20261026.md.

## 2026-10-26 — wall clock ARM 검증
- 사용자 별도빌드/로드검증 승인. 로봇 별도후보 ARM빌드·신규19/기존10/CTest1·4종pluginlib 생성소멸 통과. 운영/시뮬 소스·설정 적용 없음, 기존운영프로세스 유지. 실기미검증. 운영백업/해시/교체원복절차 준비, 상세 WALL_CLOCK_REPRO_20261026.md.

## 2026-10-26 — wall clock 실물 실행 overlay 적용
- 사용자 종료·적용 승인 후 로봇 sensor_hold 실행overlay4파일만 교체, 원본코드/설정/저널 추가백업. PC공통소스/시뮬선택경로미변경.
- 운영경로plugin4종생성/소멸검증통과,설정/기록불변,재기동/실기미실시. 원복은before/after해시검증 및4파일복원,기록미복원. 상세 WALL_CLOCK_REPRO_20261026.md.


## 2026-10-26 회전 검사 대기·재개 후보 (운영 미적용)

사용자 승인으로 로봇 현장 원본을 백업하고 PC runs/align_recovery_candidate_20261026에 별도 후보 작성. align 영역 밖 costmap 변경의 재검사 무효화 방지, 장애물·정지 자세 변화의 정지 대기, 취소·정지 보호 유지. 공통 arc_clearance 예외 하위형 추가는 후보에만 존재하며 실물·시뮬 원본 미수정. 오프라인 91개 통과, 로봇 빌드·ROS/실기 미검증. 설정·운영 프로세스·이동·commit/push 없음. 상세/백업/원복/로그: docs/changes/ALIGN_RECOVERY_CANDIDATE_20261026.md.


- 2026-10-26 사용자 승인 후 align 후보 ARM64 별도 빌드2패키지·설치모듈9개/entrypoint 로드·오프라인91개 통과. 운영 소스/설치본/설정10파일 추가 백업 및 PC전송SHA확인. 운영 교체·재기동·이동 없음. PC 기존 테스트의 상대경로 직접로드 한계를 정정하고 로봇 후보 설치본으로 재검증. 적용·원복계획 및 초기실패 포함 로그: docs/changes/ALIGN_RECOVERY_CANDIDATE_20261026.md. 실기미검증/commit·push없음.

- 2026-10-26 사용자 종료 확인·적용 승인 후 align 후보 운영 소스4/설치본4 적용 완료. 원본·설정·캐시·런치로그 추가백업/PC전송SHA확인. 운영 모듈9+진입점 로드, 오프라인44개 통과. 설정·복구기록 불변, 재기동·이동 없음/실기미검증. 상세 ALIGN_RECOVERY_CANDIDATE_20261026.md. commit/push 없음.

- 2026-10-26 사용자 일반 주행 다회 재시도 요청: 별도 collision retry 후보 작성, PC17개 통과. 기본off/선택5회·정지2초, 충돌검사·취소유지. 운영미적용/실제Action문구·상위시간제한통합검증남음. 상세 docs/changes/NAVIGATION_COLLISION_RETRY_20261026.md.

- 2026-10-26 일반주행 재시도 후보 통합검증: 실제 PC Nav2는106/error_msg빈값 반환, 분류보완. 충돌대기를 전체주행시계에서 제외. 운영 TF복구off/단일출력 계약 유지하도록 수확전용선택·기존runtime zero콜백 분리. 단위18+소유권2, 격리ROS/FSM5시나리오 및 실제Nav2오류1건 확인. 로봇Nav2버전차/ARM빌드/전체노드조립·실기미검증, 운영미적용. 상세 NAVIGATION_COLLISION_RETRY_20261026.md.

- 2026-10-26 재시도 후보 ARM2패키지빌드·모듈11/진입점로드·단위20·격리ROS/FSM5 통과. 로봇Nav2 1.3.11 실제격리controller에서106/빈문구 재현. 운영원본/설정백업·PC전송SHA검증·시험프로세스종료. harvest 전용retry5 설정은제안파일만준비. 운영미적용/재기동·이동없음,전체노드조립·실기미검증. 상세 NAVIGATION_COLLISION_RETRY_20261026.md.

- 2026-10-26 14:47 사용자 승인·잔존프로세스 없음 확인 후 일반주행 retry 후보 소스6/설치6 및 수확전용5회 설정 운영적용. 기존핫픽스/기록 추가백업·PC전송SHA확인. 운영11모듈/진입점로드·수확retry5/공통retry0/TF복구off 확인. 인계설정·복구저널불변. 재기동·이동없음/실기미검증. 상세 NAVIGATION_COLLISION_RETRY_20261026.md.


### 2026-10-26 전진 곡선 대체·지속 대기 후보 (운영 미적용)
사용자 “다시 안멈추게 고쳐와” 요청. 로봇 운영 소스 읽기 백업 후 runs/forward_recovery_candidate_20261026에 별도 후보 작성. 기본 RPP 경로 방향 회전이 막혔을 때 동일 충돌 검사를 통과한 전진 곡선만 선택하는 새 플러그인, 수확 전용 선택형 지속 대기 연결. 횟수 소진/30초 준비 지연으로 종료하지 않되 취소·소유권·기타 오류/실행 제한 유지. 합성 Nav2 costmap 복합1+기존C++12, Python18+4, 격리 Action/실제 Harvest FSM6 시나리오 통과. 지속 대기에서 6회 abort 후7번째 성공, 사용자 취소 전달 확인. PC 빌드 성공; ARM/운영 로드·실물 통과는 미검증. 원본 설정·운영 프로세스·이동·commit/push 변경 없음. 상세 docs/changes/FORWARD_RECOVERY_CANDIDATE_20261026.md. 실제로 막힌 모든 경우에도 계속 움직이는 변경은 아니다.


- 2026-10-26 전진/지속대기 후보 ARM3패키지 빌드 및 로봇 Nav2 1.3.11 검증 완료. 후보 pluginlib3종/설치Python10모듈, C++1+12/Python18+4/격리FSM6 통과. 운영292파일 추가백업·PC전송SHA/내용 검증 및 불변 확인, 운영미적용·재기동/이동없음. 사용자 과도한 변경 지적으로 A(기존 controller 유지·종료 방지 Python4+설정)와 B(새 전진 플러그인 추가)를 명시 분리. 실제 코너 통과·전체노드 기동 미검증. 상세 FORWARD_RECOVERY_CANDIDATE_20261026.md.

- 2026-10-26 사용자 기존 성공 전진·회전 복원/최소 수정 요청으로 새 플러그인 적용 보류. 성공 보존 일반Nav2 설정↔현재 실행값 전체 동일, 성공 runtime baseline↔현재 normal 출력분기 AST 동일 확인. 되돌릴 전진 제거 변경은 미발견. 입력 위치/셀 차이는 있으나 최신실패 controller 내부 기하 기록이 부족해 직접원인·수정완료 미확정. 추가추측수정/운영적용/이동없음. 상세 FORWARD_RECOVERY_CANDIDATE_20261026.md 및 runs/success_motion_compare_20261026.

- 2026-10-26 전진 전환 판단 수집 도구 준비/별도 로봇 Downloads 배치. 기존 코드·설정·프로세스 유지, 수집 미기동. 실제 RPP경로점/회전선택/raw출력·TF/odom/scan/costmap full/update 및 실행params/launch로그 보존. foreground/Ctrl+C/5분·용량한도, CAPTURE_READY 후 사용자웹전송. PC 더미7183/브리지7242/웹7267 실행중, 로봇잔존없음, 위치답변대기. 상세 FORWARD_TRANSITION_CAPTURE_20261026.md.

- 2026-10-26 사용자 재시작 정리 승인 및 스테이션 재배치 확인. 로봇 수확 관련 잔존0/미완료 복구표시0, 저널 전후SHA불변. PC 더미7183/브리지7242 정확한argv확인후SIGINT정상종료·잔존0. 더미저널전후PC백업, records/history동일/recoveryfalse 확인. 미니웹7267 유지. 코드·설정·초기위치·이동·프로세스기동 없음. 근거 runs/restart_cleanup_20261026. 사용자 PC더미→PC브리지→로봇laun 후 IDLE/정지 확인, 이후vinit/zen/dzen. 수집 도구는 아직 미기동.


### 2026-10-27 공통 운영 소스 PC 반영
사용자가 로봇 성공 코드 PC 반영을 명시 승인. farm_navigation/harvest_robot/farm_wall_controller/farm_bringup에 로봇 운영 핫픽스를 반영했다. 모든 로봇 재시도 기본값0 및 명시 실물 프로필 선택 유지, sim 데이터/설정 변경 없음. 실물 인계/복귀 성공 저널은 확인했지만 이번 시뮬 실기 검증은 미수행. PC 별도4패키지빌드/재시도18/벽시각19/CTest1 통과. 백업/파일/원복은 docs/changes/ROBOT_PC_SYNC_20261027.md. Git commit/push 없음.


### 2026-10-27 로봇 프로젝트 실행 경로 전환 완료
사용자 승인으로 성공 overlay 운영 코드를 로봇 프로젝트에 반영·ARM4패키지빌드하고 laun을 project install/상대경로프로필로 전환. 기존70모듈SHA·모든 생성서버설정 동일, 플러그인4로드/소멸·CTest1 통과. 기존 Downloads 성공본과 변경전src/install/별칭 백업 보존. 다른별칭/브리지/저널 불변. 신규 PC 도우미도 저장소에 포함. 실기기동/이동/commit/push 없음. 디스크여유2.7GiB로 기존카메라3GiB시작검사보다부족, 기록임의삭제없음. 상세 docs/changes/PROJECT_RUNTIME_MIGRATION_20261027.md.
