# Codex 시작 및 ChatGPT 프로젝트 인계 절차

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


작성: 2026-10-06. 기준 코드: `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`.
이 문서와 PROJECT_STATE.md는 최신 코드·결정을 전달하기 위한 시작점이다. 기존 상세 인수인계서와 시험 기록을 대체·삭제하지 않는다.

## 1. 작업 위치와 읽는 순서

- 저장소: `Robot3FinalProject/main`, 기준 브랜치 `main`.
- 저장소 안 프로젝트 위치: `farm_project/`.
- 사용자 PC 작업 경로: `~/main/farm_project`.
- 프로젝트 폴더에서 Codex를 시작한다. 다른 경로에서 시작하면 작업 루트와 AGENTS 적용 범위를 먼저 확인한다.

1. 루트 `AGENTS.md`와 수정 대상 디렉터리의 추가 AGENTS.
2. [PROJECT_STATE.md](PROJECT_STATE.md): 현재 구조·통신·설정·검증 상태.
3. [DECISIONS.md](DECISIONS.md): 확정 설계·미확정 과제.
4. 시뮬 작업: `sim/AGENTS.md`, [현행 실행·로그 가이드](../sim/docs/RUN_GUIDE_20261006.md), `sim/docs/CHANGELOG.md`.
5. 관련 변경 문서와 실제 코드·설정. 최신 통신 변경은 `docs/changes/PROTOCOL-20261006-014.md`.
6. 상세 예찰 구조가 필요할 때 `docs/SUMMARY_인수인계서.md`를 읽되 10/2의 시점을 구분한다.

현재 코드의 동작과 사용자에게 확정받은 요구사항을 각각 확인한다. 문서·코드가 충돌하면 차이를 기록하며 임의로 과거 코드에 되돌리지 않는다. AGENTS의 변경 승인 규칙은 요약 문서보다 우선 적용한다.

## 2. 첫 세션에서 확인할 것

```bash
cd ~/main/farm_project
git status --short
git branch --show-current
git rev-parse --show-toplevel
git rev-parse HEAD
git remote -v
```

현재 파일을 덮어쓰거나 pull하기 전에 미커밋 변경과 원격을 확인한다. 원격 조회가 가능하면 `git fetch origin` 후 현재 브랜치와 `origin/main`의 차이를 읽는다. fetch 성공과 실제 코드 반영은 다르다. 이 문서는 reset, clean, stash, 강제 push를 지시하지 않는다.

처음 Codex에 전달할 요청:

```text
AGENTS.md와 docs/CODEX_HANDOFF.md를 먼저 읽어.
docs/PROJECT_STATE.md, docs/DECISIONS.md와 작업에 관련된 하위 AGENTS를 확인해.
Git 상태·현재 브랜치·HEAD를 확인하고 내 미커밋 변경을 보존해.
인수인계 기준 커밋과 현재 코드가 다르면 관련 차이를 확인해.
현재 구현 상태, 실제 검증된 범위, 남은 문제, 바로 이어서 할 작업을 간단히 알려줘.
내가 작업을 지시하면 해당 범위 안에서 수정·검증하고 관련 상태·변경 문서를 갱신해.
공통 코드 변경은 기존 승인 규칙을 따르고, 실행하지 않은 시험을 통과했다고 쓰지 마.
```

## 3. 양쪽 역할과 전달 기준

| 구분 | 역할 | 저장할 내용 |
|---|---|---|
| ChatGPT 프로젝트 | 세부 설계·기획·논의·보고서·도식 | 확정 결정, 요구사항, 완료 조건, 미확정 사항 |
| 로컬 Codex | 현재 코드 확인·구현·디버깅·실행 검증 | 변경 파일, 실제 결과, 미실행 항목, 다음 작업 |
| GitHub | 공통 기준과 변경 이력 | 공유할 문서·코드의 커밋과 브랜치 |

### ChatGPT → Codex

1. 이 프로젝트에서 최신 저장소 문서와 관련 코드를 읽고 설계를 논의한다.
2. 확정된 내용은 DECISIONS.md 또는 해당 상세 설계 문서에 기록한다. 제안/확정 상태를 표시한다.
3. 저장소 반영을 요청받은 경우 연결 권한과 범위 안에서 반영한다. 파일만 전달한 경우 사용자가 로컬에 적용하고 기록해야 한다.
4. Codex에는 결정 ID·파일·완료 조건을 전달한다. 별도 브랜치에 기록했다면 그 브랜치/커밋도 명시한다.

### Codex → ChatGPT

1. 관련 구현·검증 후 PROJECT_STATE.md를 갱신한다.
2. 시뮬 변경은 `sim/docs/CHANGELOG.md`, 공통 계약 등은 `docs/changes/`의 해당 기록을 유지한다. 같은 내용을 별도 WORKLOG에 다시 복제하지 않는다.
3. 사용자 요청·기존 승인 범위에 따라 commit/push한다. 요청되지 않은 원격 게시를 자동으로 수행하는 규칙은 아니다.
4. 이 프로젝트로 돌아오면 저장소·브랜치·최신 문서를 다시 읽는다. 직전 대화 기억보다 현재 파일과 근거 기록을 확인한다.

**최신 공유의 기준은 반영된 파일과 커밋이다.** PC에만 있는 변경, 대화에만 있는 결정, 전송하지 않은 로그는 다른 쪽에서 자동으로 알 수 없다. 파일을 수정하거나 이 ZIP을 해제한 것만으로 GitHub push 또는 ChatGPT 프로젝트 지침 변경이 완료되지는 않는다.

## 4. ChatGPT 프로젝트 지침에 추가할 문구

프로젝트 설정의 지침에 사용자가 아래 내용을 추가한다. 이 파일 생성만으로 해당 설정이 변경되지는 않는다.

```text
이 프로젝트의 공통 자료 원본은 GitHub Robot3FinalProject/main의 farm_project/다.
현재 코드·상태가 필요한 요청은 사용할 브랜치와 커밋을 확인하고
docs/PROJECT_STATE.md, docs/DECISIONS.md 및 관련 변경 문서를 읽고 답한다.
기본 기준은 main이며, 사용자가 작업 브랜치를 지정하면 그 브랜치를 사용한다.
코딩·실행 검증은 로컬 Codex, 세부 설계·기획·논의·자료 작성은 이 프로젝트에서 진행한다.
확정 설계는 결정 기록으로, 구현·시험 결과는 상태와 변경 기록으로 인계한다.
GitHub에서 읽지 못한 내용이나 PC에만 있는 변경은 확인했다고 말하지 않는다.
구현 완료, 사용자 확인, 과거 시험 기록, 이번 직접 검증, 미검증을 구분한다.
공통 코드 변경 승인 규칙과 sim 전용 파일을 sim 안에 두는 규칙을 유지한다.
파일 전달 시 다운로드 후 프로젝트 경로에 압축을 푸는 Bash 명령을 함께 제공한다.
```

공식 참고: [Projects and chats](https://learn.chatgpt.com/docs/projects), [Memories](https://learn.chatgpt.com/docs/customization/memories), [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md). 2026-10-06 확인 기준으로 ChatGPT Work와 Codex 대화 기록은 분리되어 있고, 로컬 Codex 메모리도 별도다. 문서 공유 절차를 대화 전체의 실시간 자동 동기화로 설명하지 않는다.

## 5. 작업 종료 시 남길 최소 기록

```text
일자(KST) / 담당 작업:
작업 시작 코드 커밋 / 종료 커밋(없으면 미커밋):
관련 결정 ID / 승인 범위:
변경 파일과 변경 이유:
실물·시뮬 영향:
실제로 실행한 검증 명령과 결과:
미실행 항목 / 실패 / 남은 문제:
로그·보고서·재현 조건:
다음 작업:
원격 반영 상태: 미반영 / push 완료 / PR 검토 중
```

PROJECT_STATE.md의 코드 기준에는 검토한 코드 커밋을 적는다. 문서 자신이 속할 미래 커밋 해시를 미리 쓰지 않는다. SHA가 없는 로컬 변경은 경로·내용·미커밋 상태로 표시한다. UTC 로그와 KST 보고 시각을 구분하고 ROS_DOMAIN_ID 등 실행 환경값은 각 세션에서 확인한다.

## 6. 이 문서 패키지 적용

ZIP 파일명: `farm_codex_handoff_20261006.zip`. ZIP 루트가 `farm_project/` 내부에 해당한다. 기존 AGENTS.md·README.md·시뮬 변경 이력을 갱신하고 인수인계 문서를 추가한다. 실행 코드·ROS 형식·USD·모델은 변경하지 않으므로 이 ZIP 자체를 적용하기 위한 colcon 재빌드는 필요 없다.

먼저 Codex가 같은 문서를 수정 중이라면 작업을 정리한다. 아래는 기존 파일을 백업한 뒤 적용하는 명령이다. 로컬에 별도로 편집한 문서가 있으면 백업본과 차이를 확인해 필요한 내용을 병합한다.

```bash
cd ~/main/farm_project &&
mkdir -p backups &&
tar -czf "backups/codex_handoff_before_$(date +%Y%m%d_%H%M%S).tar.gz" \
  AGENTS.md README.md docs sim/docs &&
unzip -o "$HOME/Downloads/farm_codex_handoff_20261006.zip" -d "$PWD"
```

적용 후 Codex 새 세션을 열어 갱신된 AGENTS를 읽게 한다. 파일 적용 결과는 `git diff`와 `git status --short`로 확인한다. 원격 반영은 별도 작업이다.


## 2026-10-20 공통 실행 정리

공통 실행 정리 패치 작성. PC ROS 검사 후 로봇 설치/무이동 검증이 남아 있다. 운영 설치본은 아직 변경하지 않는다.
상세 파일·검증 한계·복원 방법: `changes/HARVEST_COMMON_EXECUTION_20261020.md`. commit/push 없음.


## 2026-10-21 PC ROS preflight 수정

사용자 PC의 독립 설치·실제 ROS 타입 검사까지 통과했으나, WallGoalChecker에 일반 checker의 미선언 xy_goal_tolerance 등을 함께 요청하여 실제 ROS 계약 검사가 실패했다. 오프라인 대역이 누락 항목을 None으로 돌려주는 방식이어서 이를 놓쳤다. plugin 종류를 먼저 읽고 Simple/Stopped의 기존 키 또는 wall_alignment.*만 조회하도록 수정했다. 필수 벽 키가 없는 경우의 실패는 유지한다. 테스트 대역에 미선언 항목 전체 실패를 반영하여 수정 전 오류를 재현하고 수정 후 공통 주행/명시적 경로 26개를 통과했다. 일반 Simple/Stopped 검사와 허용오차 초과 거절도 확인했다. PC 실제 ROS 재검사는 전달 스크립트에서 수행하며 이 수정본의 실물 검증은 미완료다. 제어기·주행 수치·FSM 변경 없음. 원본/로그/독립 빌드 경로는 Downloads 하위다.

