# 2026-10-25 PC 반복 시험 콘솔 후보

사용자 요청: 터미널 기동은 유지하면서 반복 시험에 필요한 종료·복구·더미 반복 허용·수확 개수를 로컬 웹에서 처리. 기준 HEAD cf870da, 브랜치 feat/harvest-handoff-real-20261018, 기존 미커밋 핫픽스 보존. 별도 관제 서버 코드는 읽기 상태 API 외에 접근/수정하지 않음.

대상은 robot/tools/trial_console 신규 도구. 공통 FSM·Nav2·센서·안전 조건·로봇 실행 설정 변경 없음. 실제 이동/재시작/배포 없음. 프로세스 종료·복구는 화면에서 사용자가 명시적으로 실행하며 기존 저널은 백업 및 previous_record로 보존한다. 실행 중 IDLE 직접 변경은 제공하지 않는다.

더미 수량 후보는 외부 기존 server.py 해시를 검증해 별도 출력 폴더에 patch 적용. 수량 변경은 idle에만 허용하고 실행 기록에 수량 저장. 발견한 Node._services 덮어쓰기 충돌을 후보에서 전용 _trial_services로 분리. 기존 종료·취소·중복 처리 보존. 운영 원본 server.py 변경 없음.

검증: HTTP/복구 테스트 2개 통과. domain191·console_validation에서 실제 ROS Action 완료(3/1/0개), 완료한 ID의 1회 반복, 활성 중복/수량 변경 거절, 취소·복구 및 이전 결과 보존 통과. 초기 검증은 sandbox 소켓/로그 경로 제한 및 기존 _services 충돌 때문에 실패했고 후보 보완 후 재검증했다. 웹 브라우저 렌더링과 요소 로딩 확인. 실장비 버튼·운영 연결 통합 검증 미실시. runs/trial_console_20261025에 후보/실패/성공 로그 보존.

사용·후보 생성·시험·원복 절차는 robot/tools/trial_console/README.md. 기존 기록·백업은 삭제하지 않았으며 commit/push 미실시. 다음 단계는 PC 더미만 후보 적용할 시점 협의 및 이동 없는 운영 서비스 검증이다.

## 2026-10-26 사용자 검증 요청

- 사용자 실행 웹 PID316199 유지. 실제 웹 `/api/refresh`로 SSH·로봇 저널·관제 GET 연결 확인. 수확 대상 프로세스 0, ROS 상태/odom 없음, PC 더미 프로세스 및 status 없음, 관제 harvest Action false. 미연결 상태를 준비 성공으로 판단하지 않음.
- 운영 더미/로봇을 시작·종료·재기동하지 않음. 운영 원본 server.py/executor_lifecycle.py SHA256가 후보 생성 기준과 동일함 재확인. 운영 복구·반복 허용·이동 요청 없음.
- HTTP/저널 테스트 2개 재통과. 별도 domain191/console_validation에서 직접 ROS 시험 및 새 ros_http_integration.py의 HTTP→Console→ros_probe→실제 후보 더미 시험 각각 통과. 수량3/1/0 완료, 중복 거절, 1회 반복, 활성 중 수량 거절, 취소·복구 및 이력 보존 검증. HTTP 시험은 운영 어댑터의 SSH/고정domain177 대신 격리 어댑터를 사용하므로 운영 연결 통합 완료와 구분.
- 결과: runs/trial_console_20261026/checks.log, live_state.json, original_unchanged.json, http_*/audit.jsonl, ros_check_*/server.log/result.json/journal.json. 격리 서버는 시험 후 종료. 기존 사용자 웹 유지.
- 남음: 운영 후보 적용 및 기동 후 domain177/브리지 실제 연결, 실장비 종료·수동복구 버튼 검증. 물리 재배치 없이 복구 기록을 변경하지 않음. Git commit/push 없음.

## 2026-10-26 PC 운영 더미 적용
사용자 백업·후보 적용·웹 연결 승인. 로봇 대상 프로세스0/PC더미·브리지 없음 확인 후 원본 해시 대조. 백업 `/home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/console-backup-1792952564874101122`에 server.py, executor_lifecycle.py, journal, pc-bridge.json, pc.bash 보존. server.py만 검증 후보 ee3eeab0…로 원자 교체. 기존 pc.bash dummy/bridge로 PC 측 기동, 사용자 웹PID316199 유지. 로봇 코드/설정/프로세스 기동/이동 변경 없음.

웹 RuntimeStatus 최신 수신 및 prepare/개수 파라미터 서비스 왕복 확인. 기존 더미 journal recovery_required=true가 보존돼 prepare=DUMMY_NOT_READY, count=DUMMY_NOT_IDLE로 거절됨. 연결 성공과 준비 완료를 구분하며, 유휴 수량 변경 성공은 아직 확인하지 않음. 백업 대비 journal JSON 완전 동일. 로봇 DOCK_TEST_188c3962206a465cab024b8092f108ca active=false/recovery=true 남아 사용자에게 실제 스테이션 재배치 확인 요청. 아직 복구 플래그 변경 없음.

로그/manifest/web 결과: runs/trial_console_apply_20261026. PC 기동 로그 restart_terminal_20261024/20261026_032245_dummy.log 및 032310_bridge.log. 원복은 PC더미 정상종료 후 위 백업의 server.py만 원래 위치에 복원, journal은 현재 이력 유지. 다음: 재배치 확인 후 승인된 복구 처리 및 로봇 사용자 기동/IDLE/vinit/zen/dzen 확인. commit/push 없음.

## 2026-10-26 충전 중 PC 더미만 복구·웹 검증
사용자 로봇 충전 위치 유지 및 PC더미 복구/준비/수량 검증 승인. 웹 API로 dummy_recover → dummy_prepare → dummy_count 3 → 기본값2 순서 모두 SUCCEEDED. 최신 RuntimeStatus IDLE/ready=true/recovery_required=false 확인. GetParameters로 trial_targets=2 직접 재조회. 수확 Action/반복 허용/이동은 요청하지 않음.

복구 전 원본 백업 `/home/eunbi/vmany_artifacts/trial_console/dummy-backups/1792952715556333695.json` 및 runs/trial_console_recover_20261026/journal.before.json. 비교 결과 history 전체 동일, records의 recovery_required 플래그 이외 모든 필드 동일. 로봇 저널 SHA256 전후 동일. 로봇 복구/재시작/초기위치/이동 없음. PC더미/브리지/사용자 웹 계속 실행. 로그 check.log, verified.json, parameter_readback.json 및 각 웹 응답을 같은 runs 폴더에 보존. 실제 팔 준비나 실물 작업 완료 검증과 구분.
