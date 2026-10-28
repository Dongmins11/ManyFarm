# 실물 수확 인계 코드 1단계 통합 — 2026-10-28

## 범위와 결과

사용자 “1번부터 진행해” 승인에 따라 실물 수확 인계 코드를 기존 시뮬 수정사항과 함께 통합했다. 코드·의존성 빌드 및 회귀 검증 단계다. 시뮬 인계 활성화, 관제 자동 사이클, 실제 로봇/Isaac 실행은 이번 결과에 포함하지 않는다. Frontend와 기존 실물·시뮬 설정은 수정하지 않았다. 미커밋·미푸시 상태다.

- 로컬 기준: `ea25693650a9a61d8bbcfcf6e02f6ac6889a97a1`.
- 실물 원본: `origin/feat/harvest-handoff-real-20261018`, `e135cdef9462276cc25d9fa336f084e2dcac72e4`. 이번 작업에서 fetch 후 확인.
- 공통 조상: `2a397da842300823cec077210ac7857024a6f66a`.
- 파일별 원본/현재 SHA256 및 반영·보존·제외 목록: [source_inventory.json](../test_results/20261028_harvest_handoff_integration/source_inventory.json).

## 추가한 동작과 의존성

| 영역 | 반영 내용 |
|---|---|
| harvest_robot | 차체 인계 준비, 벽 정렬, 원호 이동, 인계 후 후퇴·복귀, 마지막 완료 윈도우 기억/무효화, 입력 대기/취소/복구 모듈 |
| farm_navigation | 명시 경로 실행, 원호·벽 관측, 속도·정지 검증, 인계 실행 시계 선택 API |
| farm_common | ActionHandoff 외부 확인 콜백을 소유권 잠금 밖에서 호출하는 원본 수정 |
| farm_bringup | 명시적 handoff_config 선택과 출력 remap, 필요한 위치 조회 연결 |
| 새 패키지 | farm_arc_controller, farm_wall_controller, jetson_harvest_interfaces |
| 선택 기능 | Jetson 상태 연결 및 준비 확인. 기존 설정에 없으면 비활성 |
| 원본 참고 설정·도구 | vicpinky/transfer JSON 6개와 wall_reference_capture.py. 기존 환경 설정에 자동 연결하지 않음 |

선별한 원본 목록 118개 중 98개는 원본과 바이트 동일, 11개는 로컬 계약을 보존해 병합, 7개는 기존 로컬 유지, 2개는 미선택 실물 지도 전용 시험/fixture라 제외했다. 기존 시험 보완 및 신규 시뮬 회귀 시험은 manifest의 additional_local_edits에 별도로 기록했다. 전체 브랜치 병합이 아니다.

## 충돌 해결과 보존 사항

- 일반 주행의 경로 길이별 제한시간, 교통 허가·정지·완료 통지, 교통 사용 중 Spin 거절을 유지했다. 명시적 인계 실행 시계가 주어진 경우에는 원본 인계 예산을 사용한다. 기존 collision_recovery와 traffic 구현을 교체하지 않았다.
- D-059의 짧은 윈도우 진입 조건을 유지했다. 몸체 각도·횡오차·전방 여부를 각각 검사하며, 원본의 추가 목표선 각도 제한은 work_path_heading_limit_rad가 명시된 경우에만 적용한다. 원본의 기본 각도 제한으로 되돌리면 가까운 전방 윈도우를 거부할 수 있다.
- 기존 navigation 재시도 설정을 보존하고 새 harvest 설정과 중복 지정하면 거절한다. 원본 인계 재시도 설정은 출력 정지 소유자 연결을 요구한다.
- components 인계 출력과 교통 출력 소유권을 동시에 연결하는 조합은 아직 검증되지 않아 시작 시 거절한다. 기존 교통 프로필은 인계를 활성화하지 않으므로 이번 변경으로 그 조합을 선택하지 않는다.
- 관제 허가 이벤트 대기는 장치 동작 제한시간과 분리하는 원본 구현을 반영했다. 허가가 오지 않으면 계속 기다리지만 취소는 가능하다. 장치 실패·정지 및 미시작 작업의 제한적 재시도도 원본대로 유지한다. 이에 따라 기존 ‘장치 시간만큼 기다리면 허가 대기도 실패’ 시험은 취소/장치 실제 실패 검사로 보완했다.
- 보호 대상 기존 파일 463개가 HEAD와 동일하다: sim/ros_ws/src, robot/config, scout_robot, farm_tag_localization, farm_vision, nav2_controller, farm_interfaces, transport_robot, farm_docking. 신규 참고 JSON은 기존 파일 불변 집계와 별개다. [해시 기록](../test_results/20261028_harvest_handoff_integration/preserved_files.json).

## 검증 결과와 한계

| 검사 | 결과 |
|---|---|
| 관련 7패키지 colcon build | 성공. harvest 의존성 선언 추가 후 재빌드도 성공 |
| 공통 주행 단위 검사 | 194 통과 |
| 수확·인계 단위 검사 | 196 통과 / Jetson ROS 5개 건너뜀 |
| 관련 시뮬 회귀 검사 | 45 통과 |
| 원호/벽 C++ CTest | 3 통과 |
| 직접 import·문법·diff 검사 | 47 수확 모듈 import 및 compileall, git diff --check 통과 |
| 합계 | 438 통과, 5 건너뜀. 아래 조건부 교통 21개는 별도 |

Jetson ROS 5개는 원본 시험의 Domain231/LOCALHOST 별도 조건을 요구한다. 이번 작업에서 사용자 지정 Domain13/SUBNET을 바꿔 실행하지 않았다.

실물 원본의 실제 설정 파일들을 입력으로 build_server_config를 실행해 생성한 최종 인계 서버 설정은 원본/병합본이 바이트 동일하다. 두 [parameters JSON](../test_results/20261028_harvest_handoff_integration/parameters_integrated.json)을 보존했다. 이는 해당 생성 함수 결과 비교이며, 실행 중 ROS 파라미터 서버·센서·모터 동등성 검증을 뜻하지 않는다.

### 별도 발견: 교통 등록 그래프 불일치

현재 교통 검사 21개는 준비 단계에서 ‘교통 등록 그래프와 실행 그래프의 파일 해시가 다릅니다’로 실패한다. 변경 전 ea25693 소스/설정을 임시 경로에 내보내 검사해도 동일한 21개 오류다. 이전 선별장 경로 변경 뒤 등록용 그래프 복사본과 실행 그래프가 일치하지 않는 상태이며 이번 인계 코드 병합에서 생긴 문제가 아니다.

운영 설정은 변경하지 않고 임시 시험 경로에서 등록용 그래프를 실행 그래프와 맞춘 경우 교통 검사 21개가 통과했다. 이것으로 운영 교통 설정이 고쳐졌다고 보지 않는다. 전체 관제 연동 전에 생성 절차에 따라 그래프/등록 자료 정합을 별도로 처리해야 한다. baseline 실패와 조건부 성공 로그를 모두 남겼다.

초기 실패 로그도 보존했다. navigation.log의 초기 오류에는 미반영 설정·시험 도구와 속도 파라미터 mock 누락, 기존 교통 불일치가 포함된다. follow.log에는 신규 os 참조를 기존 AST 시험 mock에 제공하지 않은 오류가 있다. final 로그는 관련 수정 후 결과다. harvest.log는 원본의 무기한 허가 대기 변경 때문에 기존 timeout 시험이 대기한 초기 기록이다.

## 다음 작업

1. 원본 HandoffRuntime의 실물 전용 조건, use_sim_time=False 및 TF 복구 조건을 시뮬 시계·센서·단일 출력 소유권과 연결할 경계를 확인한다. 현재는 실물 전용 제약을 그대로 보존했다.
2. sim 전용 인계 프로필과 가상 장치 어댑터로 원본 수확 기구 계약을 충족시킨다. 현 sim transfer.enabled=false를 이번에 바꾸지 않았다. 무조건 성공하는 대체 동작은 추가하지 않았다.
3. 교통 등록 그래프 정합과 출력 소유권 연결을 마친 뒤 Domain13/SUBNET에서 관제 API의 개별 단계를 검증한다. 그 후 SEC01 자동 연쇄 실행을 연결한다.

스테이션 마커 생략, 바구니 72% 겹침 평가, 원본 USD 유지 등 기존 시뮬 승인 사항은 변경하지 않았다. 수확 인계 코드 통합을 전체 사이클 완료로 보고하지 않는다.

## 자료와 복원

공유 로그: [20261028_harvest_handoff_integration](../test_results/20261028_harvest_handoff_integration/). 전체 원시 작업 자료는 sim/runs/harvest_handoff_integration_20261028 및 /tmp에 있다. 영구 공유가 필요한 검사 로그와 설정 비교는 위 docs/test_results로 복사했다.

수정 파일 패치: sim/runs/harvest_handoff_integration_20261028_patch.zip. 프로젝트 루트(farm_project) 기준 상대 경로다.

```bash
unzip -o /home/ysy/main/farm_project/sim/runs/harvest_handoff_integration_20261028_patch.zip -d /home/ysy/main/farm_project
```

현재 작업공간에는 이미 적용되어 있으므로 다시 풀 필요 없다. 복원 시 manifest에 기록된 이번 수정 파일만 ea25693 내용으로 되돌리고 이번 신규 파일만 제거한 뒤 관련 패키지를 재빌드한다. Frontend와 다른 작업자의 파일을 일괄 reset/clean하지 않는다.
