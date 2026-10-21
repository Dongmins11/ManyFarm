# Codex 시작 및 ChatGPT 프로젝트 인계 절차

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
