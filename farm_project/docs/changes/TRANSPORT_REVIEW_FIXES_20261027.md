# 운송 통합 리뷰 수정 및 재검토 — 2026-10-27

## 범위와 승인

사용자 요청: 두 차례 리뷰에서 발견한 문제 수정 후 재검토. 후진 기준각은 0° 유지. 통합 폴더에서만 수정하며 로봇 배포·기동·이동은 하지 않는다. 기준 수확 브랜치 feat/harvest-handoff-real-20261018, 5ff5b50327c2668365c09ee2ae2504ce316df9da 위의 로컬 통합 변경이다. Git commit/push/원격 병합 없음.

## 수정 내용과 이유

| 문제 | 수정 | 주요 파일 |
|---|---|---|
| 마커 ID만 보이면 목표 확보 처리되어 실제 방향 조건 불만족 시 실패 | 실측 정지 + 목표 추적기 TRANSIT/ALIGN 또는 안정 HeadingCapture 확보 후 진행. 보이지만 부적합한 마커는 제한 탐색 지속 | initial_marker_recovery.py, precision_server.py |
| 종료 중 라이다 검사 예외로 ending 상태 무한 대기 가능 | 검증 예외는 실패로 기록하고 정지/3초 종료 판정은 수행. 종료 중 취소도 후보 성공 무효화. 카메라 종료 예외에도 done 전달 | precision_server.py |
| 거리 도킹 복구가 생성하지 않는 pose preview를 기다림 | distance_heading_trial 복구는 센서·TF·정지 확인 후 방향 표본과 획득 시계를 새로 시작 | precision_server.py |
| 정밀주행이 상위 Nav2용 map/scan 검사로 조기 취소됨 | 상위는 작업 취소·비상정지, 정밀 서버는 기존 odom/scan/영상·제어권·복구 책임 유지. Nav2 check_motion 유지 | transport_node.py |
| 관측 180초 만료 후 경로 주행은 계속 가능 | 만료 상태를 반복 발행하고 경로 측에서 실패로 전달하여 기존 취소/정지 정리 실행. 관측기는 상위 finally가 종료 | precision_server.py, harvest_approach.py |
| 취소 확인 시간 초과 시 handle을 버림 | 원격 terminal 결과와 stopped 확인까지 handle/result future 유지. 후속 stop에서 재확인 | clients.py |
| terminal stopped=false 뒤 수동 복구도 영구 차단 가능 | 수동 복구의 기존 최신 odom/1초 정지를 확인한 경우에만 과거 stopped=false를 보완. 실행 중/결과 미수신 Goal은 계속 유지 | clients.py, transport_communication.py |
| 환경/프로파일에 재탐색 설정 중복 | waffle_profiles.yaml만 원본으로 사용, 시험도 동일 설정을 로드 | transport_docking_trial.yaml, test_integration.py |
| 관측 단절 이전 방향 표본이 이후 표본과 합쳐짐 | 표본 간격이 max_age_s를 넘으면 누적 표본 초기화 | distance_heading.py |

후진 distance_departure.map_yaw_rad=0.0을 유지했다. 속도/PID/티칭/카메라 보정/footprint 및 하역 계약을 이번 수정에서 변경하지 않았다. 기존 충돌 조건을 추가하거나 일괄 제거하지 않았다.

## 직접 수행한 검증

- scripts/build.sh: 17패키지 빌드 통과. ASCII /tmp/transport_handoff_build_20261027 복사본 사용.
- scripts/test.sh: 88개 통과(기존71 + 새17). 실제 PrecisionServer/PrecisionClient 메서드에 대역 센서·Future를 주입했으며 ROS 노드를 만들지 않았다.
- 회귀: 종료 센서 예외/미정지 제한시간/취소/카메라 종료 예외, 정상 종료, ID와 목표 확보 구분, 부적합 bearing, 관측 공백, 거리 복구, 현재 세션 표본, 취소 시간 초과 후 재확인, 수동 복구, 검사 책임, 관측 만료, 설정 단일화와 yaw0.
- 수확71파일·예찰45·farm_navigation49·지도7·모델3을 기준 브랜치와 SHA256 재비교하여 모두 동일. reports/review_preservation.json.
- sim은 수정·빌드·실행하지 않았다. 이번 회차에는 sim 대형 자산 전체를 재해시하지 않았으며 이전 source_audit.json 보존 결과와 구별한다.
- 로그: 워크스페이스 reports/build_review_fix.log, reports/test_review_fix.log.

## 남은 문제 및 검증 한계

1. **접수 응답 지연 경로: 후속 수정 완료.** PrecisionClient가 접수 Future를 먼저 보관한다. 5초 응답 제한 이후 accepted가 오면 즉시 취소하고 결과를 비동기 추적한다. terminal(4/5/6) + stopped 확인 전에는 pending을 유지한다. 늦은 거절은 해제한다. 결과 구독 오류가 취소 전송을 막지 않도록 분리했고, 취소 전송 오류·미정지 결과는 참조를 유지하여 stop/기존 수동 복구에서 재확인한다. 접수 응답 자체가 끝내 오지 않으면 접수 여부를 알 수 없으므로 완료로 간주하지 않는다. 아직 서버 Goal ID가 없는 동안에는 취소를 보낼 수 없으며 응답 즉시 취소한다. 범위는 정밀주행 클라이언트이며 기구 클라이언트의 공통 accepted_goal 도우미는 변경하지 않았다.
2. **티칭 유지 확정.** 사용자가 기존 마커 상대 티칭으로 정밀주행 가능함을 확인했다. 그래프 노드 변경 때문에 상대 티칭을 수정하지 않는다. 새 그래프 좌표와 이전 init 별칭의 일치 여부는 별개의 항목이다.
3. **초기 탐색의 실물 수렴 미검증.** 목표 부적합 시 이제 제한된 후진·좌우 탐색을 수행한다. 이 정책의 카메라 시야/정렬 성공 및 30초 안 수렴은 PC 단위시험으로 보증하지 않는다. 새 과도한 회전이나 반복 정지가 없는지 실제 기록이 필요하다.
4. **센서·통신 통합 미검증.** 실제 TF/영상 지연, 관제·OpenCR 응답, 늦은 취소 결과의 DDS 전달은 이번 대역 시험 범위 밖이다. 하드웨어 underlay, 카메라 가상환경/보정 파일은 별도 준비가 필요하다.

이번 시험 범위에서 기존 리뷰 결함을 재현하던 경로는 통과했으나 전체 실물 시퀀스 성공으로 표현하지 않는다. 후속 실기에서는 접수/취소/terminal 시각, 관측 ID와 목표 확보 사유, recovery 전후, odom/scan age, lease 소유권을 함께 기록한다.

## 되돌리기와 적용

원본 운송 snapshot 및 Desktop 수확 브랜치는 수정하지 않았다. 통합 폴더의 이번 파일들을 리뷰 전 상태로 되돌린 뒤 scripts/build.sh를 다시 실행하면 된다. 원본 운송 파일을 덮어쓰는 방식의 원복은 통합 어댑터 변경도 잃으므로 사용하지 않는다. 로봇 배포는 이번 작업 범위가 아니며 실행 명령은 최상위 README에 있다.

## 지연 Goal 후속 검증

사용자 요청으로 보관·즉시 취소·종료 추적 적용. 17패키지 빌드 및 총94개 시험 통과(기존88 + 지연 경로6). 추가 시험: 응답 대기 중 중복 접수 차단/늦은 수락 즉시 취소/종료까지 pending 유지, 늦은 거절, 미정지 terminal, 취소 전송 오류, 결과 구독 오류, 제한시간 경계에 이미 완료된 Future. 대역 Future 시험이며 DDS 지연 실기 재현은 아니다. 최신 로그 reports/build_late_goal_fix.log, reports/test_late_goal_fix.log. 로봇 배포·주행·티칭·후진각 변경 없음.


## 2026-10-27 사용자 승인 로봇 별도 배포 완료

로봇 wmany@192.168.0.15의 `/home/wmany/transport_handoff_integration_20261027`에 배포했다. 기존 운영 폴더·별칭 불변, 시뮬레이션 자산 제외. `/home/wmany/transport_handoff_integration_20261027/robot_build`에서 ARM 17패키지 빌드 성공(13분34초). PC/로봇 소스501개 및 빌드소스376개 해시 일치. 정밀주행·운송·기구 브릿지·인터페이스의 import/prefix가 새 통합 경로임을 확인했다. 기존 turtlebot3_ws/device_ws를 하드웨어 underlay로만 사용한다.

로봇 회귀시험90개 통과, launch --show-args 및 real 설정 로드 통과. 전체 시험을 처음 시도했을 때 제외한 sim fixture를 찾는 시험2개가 FileNotFoundError로 실패하여 로그를 보존했다. 해당 PC 전용 묶음4개는 로봇 시험에서 제외했으며 PC94개 통과와 구별한다. scripts/test_robot.sh에 범위를 명시했다. reports/robot_build.log, robot_test.log, robot_test_full_missing_sim.log, robot_verify.log, robot_launch_args.log 참고.

브링업·노드·모터 명령은 실행하지 않았다. 최종 점검에서 운송 브링업/precision_server/transport_node/motion_gate 실행 없음. 사용자 실행: `bash ~/transport_handoff_integration_20261027/scripts/bringup_robot.sh`. 기존 bringup/init/zen 별칭은 바꾸지 않았다. 티칭 및 후진0° 유지. 실물 주행 성공은 아직 확인하지 않았다. Git commit/push 없음.


### 2026-10-27 수확 최신 업데이트와 운송 통합본 게시
사용자 승인으로 48d2d1c의 수확 설정2개·코드2개 및 관련 문서를 별도 운송 통합본에 반영했다. 운송 티칭/속도/후진0° 및 기존 관제 계약 유지. PC98시험·17패키지, 운송로봇 변경패키지 재빌드·94시험, 소스501/빌드376 해시 일치. 로봇 백업: transport_handoff_integration_20261027/backups/before_48d2d1c.tar.gz. 실기기동/이동 없음. 후속 사용자 요청으로 기존 커밋 금지 지시를 변경하여 feature_dongmin 브랜치 게시를 승인받았다. 업로드 worktree는 원본과 분리하고 최신48d2d1c를 부모로 사용한다. main/기존 수확 브랜치는 변경하지 않는다. sim 프로그램·설정 수정 없음(상위 커밋의 sim 문서는 게시 기준에 그대로 보존). 상세 TRANSPORT_REVIEW_FIXES_20261027.md 후속 항목 참고.
