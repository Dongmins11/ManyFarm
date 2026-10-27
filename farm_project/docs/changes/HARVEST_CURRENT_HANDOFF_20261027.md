# 수확 인계 현재 기준·실행·후속 작업 — 2026-10-27

## 1. 다음 대화가 먼저 읽을 내용

성공 기준 커밋은 `48d2d1c812a968058254ddb2355ee5dfc9b96c68` (`fix(harvest): 복귀 완료 판정 완화 및 다음 window 연속 주행 검증`)이다. 사용자가 직접 커밋했고 이번 문서 작업 시작 시 Git 작업 트리는 깨끗했다. 원격 push 상태는 확인하지 않았다. 아래 과거 이력의 “미적용·미커밋·전체 인계 미확인”은 작성 당시 상태이며 현재 성공 범위는 이 문서와 [성공 증거](HARVEST_SUCCESS_FREEZE_20261027.md)를 우선한다.

이번 작업은 문서만 갱신했다. 코드·설정·저널 변경, 프로세스 기동/종료, 초기위치 발행, 이동, Git stage/commit/push는 하지 않았다. 현재 로봇 위치·실행 상태는 새 작업 시작 시 다시 확인해야 한다. 성공 당시 상태를 현재 상태로 간주하지 않는다.

- PC 프로젝트 `/home/eunbi/vmany/main/farm_project`, 실제 Git 루트 `/home/eunbi/vmany/main`.
- 로봇 `vic@192.168.0.12:/home/vic/vmany/main/farm_project`. Git 인식 실패 시 init/clone하거나 PC 파일로 일괄 덮어쓰지 않는다.
- 시작 시 AGENTS 및 이 문서, PROJECT_STATE, DECISIONS를 읽고 HEAD/status, 로봇 접근, 관련 소스·설치본·실행 경로를 대조한다.
- 사용자가 터미널을 직접 켜고 끈다. 에이전트는 임의 백그라운드 실행·재기동하지 않는다. 웹 주행/인계 버튼도 사용자가 누른다.
- 성공 동작·충돌·취소·정지·출력 소유권 보호를 유지한다. 변경·운영 적용·재기동·실기 이동은 해당 요청 범위를 구분한다. 관제 코드와 다른 팀 운송 코드는 수정하지 않는다.

## 2. 어디까지 성공했는가

2026-10-27 KST 사용자 실물 확인과 관제/로봇 로그 대조 결과다. 이번 문서 작성 중 재시험한 결과는 아니다.

| 시각 | 확인 결과 |
| --- | --- |
| 15:17:48 | #59 window 수확 SUCCESS, PC 더미 수확 2개 |
| 15:19:06 | 인계 진입·벽 정렬 후 DOCK_READY |
| 15:19:14 | TRANSFER_COMPLETE |
| 15:20:06 | DockTransfer SUCCESS, transfer_complete/transport_clear/restore_complete 모두 true |
| 15:20:32 | 다음 #60 window 수확 SUCCESS, 목표 (2.181, -0.035), PC 더미 2개 |

로봇 로그 `/home/vic/vmany-terminal-logs/20261027_151531_launch_95558`. 작업/인계 ID는 성공 증거 문서에 기록했다. 관제 결과는 SINGLE_SUCCEEDED이며 수확 차체+PC 더미 범위다. 실제 팔 수확·배출 및 운송 로봇의 물리 도킹·이격까지 성공했다고 확대하지 않는다. 같은 날 앞선 실패 기록을 삭제하거나 성공으로 바꾸지 않는다.

## 3. 고정한 코드와 설정

| 대상 | 현재 의미 |
| --- | --- |
| `robot/config/environments/harvest_handoff_real.yaml` | 해당 실물 프로필 일반 주행 방향 허용치 6도 |
| `robot/config/robots/vicpinky/transfer/handoff_fsm.json` | 복귀 정지 후 원호 끝점·최종 위치 완료 5cm, 방향 완료 6도 |
| `handoff_planning.py`, `handoff_window.py` | 완료 방향과 실행 중 감시 방향을 분리. 실행 중 motion_heading 최대 3도 유지 |
| 기존 controller/goal checker/경로/출력 보호 | 최근 완료 판정 수정에서 변경하지 않음 |

복귀 방향은 저장한 실제 출발 방향을 기준으로 한다. 5cm·6도는 모든 주행 중 오차를 허용한다는 뜻이 아니다. 재진입·경로·센서·충돌·정지·상위 작업 계약은 별도로 남아 있다. 이전 일반 주행 성공을 보존하려고 공통 기본값과 다른 로봇 프로필은 변경하지 않았다.

성공 보존 시 수확 운영 파일 PC/로봇 동일, 소스/설치 Python 74모듈 동일을 확인했다. 359개 비교 중 나머지 차이에는 현장 .bak, 시험 파일, 다른 담당 scout/burger가 포함되어 전체 트리를 강제 일치시키지 않았다. 성공에 사용한 수확 운영 코드를 제외한 것이 아니다.

## 4. 실행 경로와 Git 밖 의존성

`laun`은 프로젝트 `robot/tools/terminal/run.bash launch`를 거쳐 프로젝트 ROS 설치본을 사용한다. ROS Jazzy, Python 3.12, CycloneDDS, 로봇 domain 77/LOCALHOST. 환경은 `/opt/ros/jazzy`, `/home/vic/vicpinky_ws/install`, 프로젝트 install 순서로 구성한다. PC 더미는 domain 177로 분리하며 더미 브리지 endpoint는 PC `192.168.0.19:18449`, 관제 허브는 `192.168.0.20:7447`이다.

운영 launch는 `mode:=real`, `harvest_handoff_real.yaml`, `handoff_fsm.json`, 장치·navigation·tag_correction·tag_camera를 사용한다. 카메라는 정상 launch에 포함되므로 별도 카메라를 중복 실행하지 않는다.

다음 외부 파일은 여전히 실행에 필요하다. Git clone만으로 모든 현장 실행이 재현되는 상태는 아니다.

- 로봇 별칭: `/home/vic/Downloads/manyfarm_terminal_20261024/aliases.bash` (`.bashrc`에서 로드).
- `zen`: `/usr/bin/zenoh-bridge-ros2dds`, 설정 `/home/vic/Downloads/handoff_completion_fix/zenoh_harvest_handoff_v2.json5`.
- `dzen`: `/home/vic/Downloads/zenoh_callback_candidate_20261023/candidate/zenoh-bridge-ros2dds`, 설정 `/home/vic/Downloads/pc_dummy_fsm_candidate_20261023/robot-bridge.json`.
- PC 더미/브리지 실행 스크립트: 아래 PC 명령 경로. 실제 팔 대신 동작하는 시험 전용 서버다.
- 초기위치 스크립트: `/home/vic/Downloads/init_station_newmap.py`. 성공 당시 별칭·외부 설정은 백업에 보존했다.

## 5. 사용자 터미널 실행 순서

기존 프로세스가 종료됐고 실제 로봇이 기존 스테이션 위치·방향에 있다는 확인 후 진행한다. 이미 켜진 항목은 다시 실행하지 않는다. 복구 필요 표시가 있으면 먼저 6절을 따른다. 아래 명령은 사용자 실행용이며 문서 작성 중 실행하지 않았다.

### PC 터미널 1 — 더미

```bash
bash /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/restart_terminal_20261024/pc.bash dummy
```

### PC 터미널 2 — 더미 브리지

```bash
bash /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/restart_terminal_20261024/pc.bash bridge
```

두 스크립트가 ROS 환경을 구성하고 실행 로그를 남긴다. 각 터미널에서 Ctrl+C로 종료한다.

### PC 터미널 3 — 미니 관제

```bash
cd /home/eunbi/vmany/main/farm_project
python3 robot/tools/trial_console/app.py
```

`http://127.0.0.1:8091` 접속. 상태 조회, 더미 준비/복구, 유휴 중 수확 개수 변경, 같은 작업 1회 반복 허용을 제공한다. 이동·초기위치·운송 명령은 보내지 않는다. 상세는 `robot/tools/trial_console/README.md`.

### 로봇 터미널 1 — 런치

```bash
source ~/.bashrc
laun
```

최신 로봇 상태 IDLE, odom 정지, 실제 스테이션 배치를 확인한 다음에만 로봇 터미널 2에서:

```bash
source ~/.bashrc
vinit
```

초기값은 map의 (0.104, -1.105), yaw 87.79도다. 실제 같은 스테이션 배치일 때만 사용한다. window/충전 위치에서는 실행하지 않는다. vinit이 IDLE 미확인으로 거절하면 보호를 우회하지 않는다. 발행 성공 후 AMCL 정합·새 costmap·센서/TF를 별도 확인한다. `vstat`은 프로세스 목록이며 IDLE·정지 증거를 대신하지 않는다.

### 로봇 터미널 3 — 관제 브리지

```bash
source ~/.bashrc
zen
```

### 로봇 터미널 4 — 더미 브리지

```bash
source ~/.bashrc
dzen
```

관제 `http://192.168.0.20:8000/real#control`에서 최신 상태와 Action 연결을 확인한다. 웹 표시만으로 더미 준비·위치 정합·안전 이격이 확인된 것은 아니다.

### 웹 작업과 인계 순서

1. 미니 관제에서 더미 준비 확인, 필요 수량 설정. 같은 웹 작업 재시험이면 보내기 직전에 마지막 수확 1회 반복 허용: 300초·같은 요청 내용·1회, 실행 중 중복 차단 유지. 더미 재시작하면 허용권은 사라진다. 다른 ID의 새 작업과 혼동하지 않는다.
2. 관제의 미확정 인계/대기열 일시정지는 사용자가 기존 관제에서 정리한다. 수확 로컬 복구로 관제 차단까지 자동 해제된다고 간주하지 않는다.
3. 사용자가 웹에서 window 수확 작업 전송. 요청 수락 → 이동 → 도착 기준 저장 → 더미 수확 → 최종 SUCCESS를 구분해 확인한다. #59/#60은 시험 작업이며 운영 좌표를 코드에 고정하지 않는다.
4. 사용자가 `dock_transfer` 전송하면 수확 차체의 인계 진입·벽 정렬이 시작될 수 있다. 단순 운송 호출 버튼으로 간주하지 않는다. DOCK_READY 확인 전 다음 이벤트를 보내지 않는다.
5. 실제 운송 또는 명시적인 시험 대역에서 DOCK_STABLE → 배출 → TRANSFER_COMPLETE → TRANSPORT_CLEAR → 복귀 → DockTransfer SUCCESS를 확인한다. 수동 버튼으로 이벤트를 보낸 시험은 실제 운송의 물리 검증과 구분한다.
6. 다음 window 작업을 사용자가 전송하고 새 도착 기준·수확 완료까지 확인한다. 서비스 accepted나 IDLE만으로 전체 성공을 판정하지 않는다.

## 6. 취소·재배치·복구

기동·종료는 사용자가 수행한다. 재배치 재시험은 laun → zen → dzen 터미널 Ctrl+C 및 잔존 프로세스 확인, 실제 스테이션 재배치 확인, 원본 저널/취소 결과 백업, 미니 관제의 수동 복구 기록, 위 재기동 순서로 진행한다. 실행 중 저널을 직접 덮어쓰거나 실패를 SUCCESS로 변경하지 않는다. PC 더미는 복구 필요 상태일 때만 복구하고 준비를 다시 확인한다.

- 로봇 저널 `/home/vic/.local/state/manyfarm/harvest_01/transfer.json`.
- PC 더미 저널 `/home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/fsm_live_20261024/journal.json`.
- 재시작 후 이전 window 도착 기준을 유효하다고 가정하지 않는다. 새 성공 도착을 확보한다.
- 원복 시 소스·설정·설치본을 검증된 백업에서 선택 복원한다. 저널은 증거용이며 과거 저널을 자동 복원하지 않는다.

## 7. 작업 이력과 증거 찾기

| 작업 묶음 | 내용·현재 해석 | 확인할 기록 |
| --- | --- | --- |
| 통신·팔 계약 | 관제 Action/이벤트와 팔 준비·수확·배출 계약, 이후 PC 더미로 실제 FSM 연결 | Confluence 10/14 통신 기록, `HARVEST_ARM_COMMON_STAGE2_20261018.md`, `HARVEST_DISCHARGE_ACTION_STAGE5_20261018.md` |
| 공통 동작·조합 | 독립 원호/벽 정렬/복귀를 컴포넌트와 로봇 조합으로 연결 | `HARVEST_ARC_SUCCESS_20261019.md`, `HARVEST_WALL_CONTINUOUS_RESTORE_20261020.md`, `HARVEST_HANDOFF_COMPONENT_INTEGRATION_20261022.md` |
| 내부 지연·출력 | baseline/fixed 구분, 입력 갱신에 따른 출력 거절·TF 문맥·취소 보호 검토 | `HANDOFF_DELAY_AUDIT_20261023.md` 및 Git 밖 현장 증거. 짧은 lock 측정만으로 전체 지연 원인을 확정하지 않음 |
| Zenoh·더미·반복 시험 | 브리지 재등록 콜백 해제, Action 완료/취소, 더미 반복 허용·수량·복구 콘솔 | `ROBOT_PC_SYNC_20261027.md`, trial_console README, 성공 백업 pc_dummy |
| 카메라·태그 | 설정 조회 지연, TBB 종료 처리, 태그 보정 연결과 별도 실기 기록 | `HARVEST_TAG_HANDOFF_20261010.md`, `ROBOT_PC_SYNC_20261027.md`, Git 밖 카메라 시험 로그 |
| 센서 대기·복귀 | 벽/align·watchdog/FSM 대기, 실제 시각과 대기 제외 시간 분리, TRANSPORT_CLEAR 후 재검사·재시도 | 현 운영 소스 및 `ROBOT_PC_SYNC_20261027.md`; 임시 후보와 실적용본 구분 |
| 운영 경로 정리 | 로봇 프로젝트 설치본으로 laun 통일, PC 동기화, 로그/시험자료 Git 밖 보존 | `PROJECT_RUNTIME_MIGRATION_20261027.md`, `ROBOT_PC_SYNC_20261027.md` |
| 최신 완료 판정·연속 성공 | 5cm·6도 완료 판정, 기존 실행 중 보호 유지, 다음 window 성공 | `HARVEST_SUCCESS_FREEZE_20261027.md`, PROJECT_STATE의 10/27 상세 이력 |

이 표는 작업 범위 인덱스다. 각 역사적 시험 결과를 현재 코드의 재검증 결과로 재사용하지 않는다. 게시용 상세 수치·날짜·원인은 각 로그/배포 영수증에 연결해서 확정한다.

## 8. 백업과 검증 범위

Git 밖 성공 보존: `/home/eunbi/vmany_artifacts/success_freeze_20261027_152308/`. 실행 소스·설정·설치본·로그 아카이브, SHA256, runtime 파라미터, 관제 결과, PC 더미, PC/로봇 비교, source/install 비교가 있다. 로그는 수집 시점 스냅샷이다.

적용 전 원복 백업: 로봇 `/home/vic/vmany-runtime-backups/return_completion_20261027_145454/`, PC `/home/eunbi/vmany_artifacts/return_completion_20261027_144650/operating_deploy/`. 신규 5+기존 20개 오프라인 테스트 및 운영 모듈 로드 통과 기록이 있다. 현재 문서 변경에는 코드 재시험을 수행하지 않았다.

## 9. 남은 문제와 다음 작업

- 같은 날 앞선 벽 정렬 `Failed to make progress` 및 일반 주행 collision 106 실패는 남은 이력이다. 최신 성공 1회로 반복 안정성이 검증되거나 원인이 모두 해결된 것은 아니다.
- 벽 진행도 제한에서 TF/센서 정지 대기 공제가 실제 모든 분기를 포함하는지, 부족한 관측·출력·이동량을 동시 로그로 재현할 필요가 있다. 성공본을 먼저 변경하지 않는다.
- 수동 재배치 후 AMCL/costmap 정합과 잔존 장애물 셀 문제는 매 재시험에서 구분한다. 충전/배터리와 관측 지연의 인과관계는 확정하지 않았다.
- 다음 window에서 태그 보정 재활성화 코드 경로와 실제 TAG_CORRECTION_APPLIED/AMCL 반영은 별도 증거다. 최신 성공 주행에 태그 보정이 반드시 적용됐다고 주장하지 않는다.
- 실제 팔 및 운송 로봇 전체 연동, 여러 목표·여러 회차·취소/재연결 후 안정성은 추가 검증 범위다.
- 외부 PC 더미·브리지·별칭/설정 의존성의 배포 정리는 후속 과제다. 이번에는 경로를 바꾸지 않는다.

## 10. Confluence 게시 완료 — 2026-10-27

사용자의 후속 게시 요청에 따라 **로봇3기 최종프로젝트 → ROS2** 아래 새 페이지를 게시했다.

[수확로봇 인계 통합 — 실기 성공 기준·운영·트러블슈팅 (2026-10-27)](https://robot3final.atlassian.net/wiki/spaces/3/pages/50593793/2026-10-27)

pageId `50593793`, parentId `819301`, version 1, status current를 재조회 확인했다. 성공 범위/남은 문제/장비별 실행/복구/작업 이력에 더해 통신·컴포넌트 구조, TF·lock, Zenoh·더미, costmap·라이다, 카메라 TBB, 센서 대기·Clock reversed, 복귀 판정, 배포 정리를 작업별 문제·조치·검증·한계로 정리했다. 기존 10/14 통신 검증 및 팀 인계 통신구조 문서는 수정하지 않고 참조 연결했다. 이번 게시 중 코드·설정·실행 상태 변경과 commit/push는 없다.
