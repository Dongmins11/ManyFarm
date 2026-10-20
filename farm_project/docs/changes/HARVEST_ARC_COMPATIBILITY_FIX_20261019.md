# 곡선 시험의 기존 주행 호환성 보완 (2026-10-19)

## 배경과 범위
곡선 시험에 진행 판정기를 추가하면서 기존 NavigateToPose / NavigateThroughPoses BT의 생략된 progress_checker_id가 더 이상 유일한 기본값을 선택하지 못하는 문제가 발견됐다. 또한 기존 prepare 완료 후 환경 파일을 바꿔 manifest와 최종 실행 입력이 달랐다.
이번 수확 주행 실패의 error_code=106은 NO_VALID_CONTROL이다. 위 호환성 문제를 이번 실패의 직접 원인으로 확정하지 않는다. 수확 route_then_follow는 명시적 제어기·진행 판정기를 사용하는 별도 경로다.

## 수정
- 공통 farm_navigation.arc_profile에서 시험 프로파일을 생성한다.
- 기존 BT를 수정하지 않고 실행 폴더에 사본을 만든다. FollowPath의 생략된 goal/progress checker만 기존의 유일한 판정기로 명시한다. 이미 명시된 선택 및 blackboard 연결은 유지한다.
- 기존 기본값을 유일하게 결정할 수 없거나 BT가 명시되지 않으면 실행 준비를 중단한다. 이름을 추측하지 않는다.
- 새 플러그인 및 시험 BT 경로를 제외한 기존 Nav2 설정 전체가 동일한지 생성 단계에서 검사한다.
- 최종 environment.yaml / arc_nav2.yaml / BT 사본 2개를 arc_final_inputs에 보존하고 manifest.arc_execution_inputs에 SHA256을 기록한다. 기존 environment 스냅샷·해시도 최종 내용으로 맞춘다.
- 기존 Nav2 YAML, 공통 운영 BT, 지도, 태그, 드라이버, 미션 로직은 변경하지 않는다.

## 검증
- Python 회귀 검사 26개 통과(기존 곡선 18개 + 호환성 8개).
- 보관된 현장 설정과 두 BT를 실제 설정 로더로 읽고 생성→YAML 저장→launch용 재해석 경로 검증 통과.
- 두 BT의 트리 구조·기존 속성·동작 순서는 동일하며 생략된 판정기 선택만 명시됨을 확인.
- 최종 실행 입력 4개 사본·해시 일치 및 원본 파일 불변 확인.
- PC용 verify_arc_compat.py는 사용자 현재 저장소의 실제 설정으로 같은 검사를 수행한다. 노드/Goal을 실행하지 않는다.
- C++ 제어기는 이번 수정에서 변경하지 않았다. 앞선 PC/로봇 빌드 및 단독 configure 성공과, 이번 Python/설정 검증은 별개다.
- ROS에서 기존 제어기들과 함께 동작하는 시험, 실물 곡선 및 이번 106 원인 확인은 아직 미완료. ROS가 없는 작성 환경에서 완료로 표시하지 않는다.

## 공통 구조로 이식 시
현재는 선택형 시험 진입점이다. 운영 인계 흐름에 연결할 때도 복수 판정기를 쓰는 모든 FollowPath 호출(직접 Action과 BT 양쪽)의 선택을 확인해야 한다. 실물 곡선 검증 전 기존 인계 동작을 교체하지 않는다.
