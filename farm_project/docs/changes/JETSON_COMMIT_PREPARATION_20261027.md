# Jetson 연결 현재 코드 커밋 준비 — 2026-10-27

## 기준과 승인

사용자 요청으로 로봇에서 PC로 읽기 전용 수집·비교했다. 실제 커밋은 사용자가 수행한다.
브랜치 `feat/harvest-handoff-real-20261018`, HEAD `48d2d1c812a968058254ddb2355ee5dfc9b96c68`.
기존 미커밋 소스·문서는 보존했다. 원격 조회·staging·commit·push는 수행하지 않았다.

## 이번 확인 및 추가 보존

- 로봇 `/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/src/`의 harvest_robot 및 jetson_harvest_interfaces 소스82파일은 PC와 바이트 일치. 별도 덮어쓰기 불필요.
- 로봇 harvest_robot 설치 Python48파일은 해당 소스와 SHA256 일치. 현재 실행 프로세스의 메모리까지 동일하다는 의미는 아니다.
- Jetson JSON 프로필 및 팔 Zenoh 설정 동일. 환경 YAML 차이는 harvest_config의 배치 절대경로뿐이므로 PC project_root 상대경로 유지.
- `robot/tools/terminal/jetson_release_20261027/`: 실제 run.bash, terminal.py, aliases.bash 원문과 배치 관계 README 추가. 기존 공용 터미널 실행기를 교체하지 않는다.
- `robot/config/robots/vicpinky/communication/zenoh-control-without-arm.json`: 로봇에서 실제 사용하는 관제 deny 전체 설정 추가. 기존 주행/인계 제외 항목과 팔/시험 모드 제외를 함께 보존.
- 로봇의 control-bridge-jetson-exclusions.json은 시험 모드 항목 추가 전 참고 파일이다. PC 최신 목록 유지, 실제 전체 config에 최신 목록 모두 포함됨을 검증.

## 커밋 대상

1. ControlState V3 인터페이스, JetsonConnection/상태 수신 및 팔 요청 직전 준비 확인, 관련 패키지 의존성·시험.
2. 실제 Jetson 프로필·도메인77 두 브리지 설정 및 실행 진입점 보존본.
3. 미니관제 팔 요청/응답·수량/상태 표시·배출 시험 모드·프로세스 조회/정리 기능과 시험.
4. 위 변경의 인수인계·상태·결정·변경 기록 및 기존 미커밋 성공 기준 인계 문서.

빌드/install/log, bag, 실제 저널, PC 더미 실행물, 바이너리, 백업, 감사 로그는 커밋 대상이 아니다.
미니관제와 실행 스크립트에는 현재 PC/로봇 경로 및 주소가 의도적으로 남아 있다.
수정 Zenoh 바이너리·드라이버·기존 프로젝트 설치본·일부 Downloads 별칭 의존성은 외부에 남으므로 clone만으로 전체 재현된다고 보지 않는다.

권장 커밋 제목:

```text
feat(harvest): Jetson V3 상태 연동과 미니관제 수동 통신 시험 지원
```

권장 본문:

```text
ControlState V3 발행과 Jetson RuntimeStatus 수신 및 팔 요청 직전 준비 확인을 연결한다.
미니관제에 수동 수확·배출 요청, 피드백·결과·수량 표시와 배출 시험 상태 전환을 추가한다.
도메인77의 실제 Jetson 연결 설정과 로봇 실행 진입점을 보존한다.
기존 성공 주행·인계 경로와 완료 허용오차는 유지한다.

검증: PC 격리 ROS/단위 검사 37개, JS 상태 표시·문법, Bash 문법 검사 통과.
실제 요청 수락·Feedback·실패 Result 왕복은 관측했으나 실물 전체 수확·배출 성공 검증은 남아 있다.
```

## 검증과 한계

이번 직접 실행: PC 격리 domain231/loopback 검사37개 통과(14.51초), JS 요약 상태 시나리오 및 문법,
Bash 문법, 설정 경로 차이/브리지 제외 목록 포함 관계, git diff --check 통과.
기존 harvest_handoff_real.yaml, handoff_fsm.json, handoff_planning.py, handoff_window.py는 HEAD와 바이트 동일.
로봇/Jetson 동작 시험은 이번에 수행하지 않았다. 기존 통신 시험의 실패 Result와 Feedback 중복은 성공으로 바꾸지 않는다.
전체 실물 연속 주행·팔·운송 연동 안정성은 미검증이며 Feedback 6회 반복 원인도 미확정이다.

## 백업과 되돌리기

PC Git 외부 `/home/eunbi/vmany_artifacts/commit_prepare_20261027/`:
`pc_before.tar.gz`는 이번 수집 전 PC 미커밋 파일, `robot_release.tar.gz`는 로봇 소스·설정·실행 진입점 수집본.
검사 로그는 같은 폴더의 tests.log, 임시 비교 작업은 `/tmp/jetson_commit_prepare_20261027/`.
이번 수집을 되돌리려면 신규 보존 디렉터리/전체 브리지 config/본 문서를 대조해 제거하고,
기존 문서는 PC 백업과 비교해 이번 머리말만 되돌린다. 이전 미커밋 작업을 reset하거나 로봇 저널을 복원하지 않는다.
로봇 파일/프로세스/별칭은 이번 작업에서 변경하지 않았다.
