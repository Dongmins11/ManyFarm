# 2026-10-27 수확 인계·복귀·다음 window 성공 기준 고정

기준 HEAD `5ff5b50327c2668365c09ee2ae2504ce316df9da` 이후 미커밋 변경을 사용자 요청으로 커밋 준비했다. 이번 작업은 백업·대조·문서화이며 실행 동작을 추가 수정하지 않았다. commit/push/스테이징은 수행하지 않는다.

## 확인한 실기 범위
사용자가 실제 인계·복귀 후 다음 좌표 이동을 확인했다. 관제 GET 결과와 로봇 성공 실행 로그를 대조했다(시간 KST).

- 15:17:48 #59 수확 SUCCESS, PC 더미 수확2개. task `25fabab7b348_SEC01_TASK001`, job `8d19c212896e461394d48a696588b5e3`.
- 15:19:06 DOCK_READY, 15:19:14 TRANSFER_COMPLETE.
- 15:20:06 인계 SUCCESS, transfer_complete/transport_clear/restore_complete 모두 true. task `DOCK_TEST_cfd3d8073d204d17b7229fdaa5e51ac5`, transfer `TRANSFER_TEST_95b51d2999704041a4b7ee548e642089`.
- 15:20:32 다음 #60 수확 SUCCESS, task `TEST_987f94d266c3_SEC01_TASK001`, job `921f41f9c12a495f891ee667133aff4d`, 목표 (2.181,-0.035), PC 더미 수확2개.

관제 completion은 SINGLE_SUCCEEDED다. PC 더미를 사용한 수확 단독 시험이며 실제 팔, 실제 운송 로봇의 도킹·이격 완료까지 검증했다고 확대하지 않는다. 직전 벽 정렬 progress 실패 이력도 보존한다. 이번 성공1회는 반복 안정성 보장이 아니다.

## 확정할 변경
- 실물 인계 환경의 일반 주행 방향 허용치6도. 다른 프로필 공통 기본값은 유지.
- 실물 인계 completion.return_position=0.05, return_endpoint_position=0.05, return_heading=6도.
- 정지 후 원호 끝점/최종 map 완료 판정만 완화. 실행중 motion_heading은 기존 최대3도 유지.
- 원호 경로/controller/goal checker/충돌/취소/실제정지 검사는 변경하지 않음. 미지정 프로필의 기존 완료 조건 유지.

## 실행본·PC 대조
로봇 소스/설정/터미널 도구359파일 대조 중338파일 동일. 나머지는 로봇 현장 .bak6개, 로봇 시험8개, 범위 밖 scout/burger7개 차이. 수확 관련 운영 파일은 PC와 동일하므로 추가 덮어쓰기 불필요. 범위 밖 다른 담당자 변경은 보존한다. 설치본과 원본 Python74모듈 바이트 동일. 성공 실행 startup의 handoff_planning 해시는 `8c18cfa4d3cbbb5dbbe408849b1ba0ca38d1cd35b51918a805be4b32c626d4da`로 적용 후보와 일치.

## 백업·검증
모든 새 시험자료는 Git 밖 `/home/eunbi/vmany_artifacts/success_freeze_20261027_152308/`에 보존했다.
- robot_success.tar.gz: 로봇 robot/ros_ws/src, robot/config, terminal 도구, 수확/주행/원호/벽/bringup 설치본, transfer저널, 성공 launch 로그·trace, 실제별칭. archive SHA256은 sha256.txt.
- running_parameters.json: 실행 프로세스가 전달받은 파라미터 파일 스냅샷.
- control.json, handoff-test_logs.json: 관제 결과(최상위 token 제외), pc_dummy/: 더미 서버/브리지 설정·저널.
- pc_robot_comparison.json, source_install_comparison.json, startup.json: 동일성 근거. pc_before.diff/status: 작업 전 PC 변경 보존.
로그는 실행 중 읽은 시점의 스냅샷이며 이후 출력까지 포함하지 않는다. 로봇 기록을 삭제/이동하거나 프로세스를 기동/종료하지 않았다.
기존 백업 `/home/vic/vmany-runtime-backups/return_completion_20261027_145454/` 및 PC `return_completion_20261027_144650/operating_deploy/` 유지. 기존 운영설치본 오프라인25테스트 통과 기록 보존; 이번에는 코드 변경이 없어 재실행하지 않았다. git diff --check 확인. 실제 시험 자료/후보/백업 파일은 커밋 목록에 추가하지 않았다.

## 남은 범위
현 성공본을 기준으로 유지한다. 반복 시험 안정성 및 실제 팔/운송 로봇 전체 연동은 별도. 기존 벽 정렬 progress 실패와 일반 주행 충돌 실패가 전부 해결됐다는 의미는 아니다. 원복 시 원본 백업에서 필요한 소스/설정/설치본만 복구하며 저널은 자동 덮어쓰지 않는다.
