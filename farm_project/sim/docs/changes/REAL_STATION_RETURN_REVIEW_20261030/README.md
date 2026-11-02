# 실물 스테이션 복귀·도킹 호환성 검토

2026-10-30. 사용자 요청: 시뮬103 해결을 위해 복귀 전후진을 변경하더라도 실물 구조물 도킹 방식과 모순되지 않아야 함. git fetch origin 성공, checkout/merge/운영 코드 수정 없음. 기존 미커밋 변경과 진행 시험 유지.

## 확인 기준

- origin/feature_dongmin:366e0c37164c22afdd2f640624b61eef8f0fa6f7
- origin/feat/harvest-handoff-real-20261018:e135cdef9462276cc25d9fa336f084e2dcac72e4
- local main:399379087374f9982b177e70d68e11721d5fdaaf + 기존 미커밋 변경
- 파일별 SHA/로컬 동일 여부: source_comparison.json. 원격의 두 브랜치 farm_common/station_return.py는 로컬과 바이트 동일.

## 실물 운송의 구현

별도 transport_robot FSM이 담당. 예찰·수확용 StationReturn과 다르다.

1. transport_real.yaml에서 STATION_TRANSPORT_01 진입A=node3, 관측B=node20, profile=station_transport_01 선택.
2. NavigationMoveState는 일반 주행으로A에 접근한다. 마지막 경로 접선 방향으로 도착/정지하며 도킹용 방향 회전은 정밀 제어기에 맡긴다.
3. waffle_profiles의 entry.mode=align_then_marker. A에서 정렬하고 정지 상태로 마커32(50mm)의 일관된8표본을 취득한다. 티칭 목표를 odom에 고정한 뒤 기존 전진 제어로 진입한다(entry.direction/pose_controller.direction=forward).
4. 프로파일 parking.enabled=true. 진입 완료 뒤20→3 방향으로 제자리 회전해 다음 출발 방향을 맞추고 정지한다. run_parking에서 이동량5cm 한도/방향3도/정지0.5초를 검사한다. 이 값은 이번에 변경하지 않았다.
5. DockingState는 Precision DOCK의 최종 성공 이후에만 ReturnToStation SUCCESS,docked=true를 반환한다. 운송 도착점만 밟고 도킹 성공으로 대체하면 실물 계약과 충돌한다.

주요 파일: robot/config/destinations/transport_real.yaml, robot/config/docking/waffle_profiles.yaml, transport_robot/configuration.py·transport_communication.py·states/navigation_move_state.py·states/docking_state.py, farm_docking/precision_server.py(begin_parking/run_parking).

이는 현재 브랜치 구현 확인이며 이번에 실기를 실행한 결과는 아니다. 프로파일에도 bounded_trial=true, 일부 기구/통로/extrinsics 검증 플래그false 및 Runtime test pending 설명이 남아 있으므로 실물 모든 조건의 안전/성공을 확정하지 않는다.

## 실물 예찰·수확의 구현 공백

- 두 최신 브랜치의 공통 StationReturn은 가상의 스테이션→현재 경로를 계산해 역순·StationReverse로 후진한다. 주행 완료만 SUCCESS, real은 docked=false, sim만 docked=true. 정밀 도킹 호출이 없다.
- feature_dongmin의 burger_profiles.yaml/vicpinky_profiles.yaml은 profiles:{}.
- transport_real.yaml의 STATION_SCOUT_01/STATION_HARVEST_01은 configured:false. 이는 운송 쪽 목적지 레지스트리의 미설정이며 예찰/수확 자체 운행 가능 여부 전체를 뜻하지 않는다.
- scout_new/states/docking_state.py는 DOCKING_UNAVAILABLE를 발생시키는 미연결 상태다. 실제 ScoutNode도 공통 StationReturn을 연결한다.
- 따라서 실물에 예찰/수확 구조물이 존재한다는 사용자 설명과 별개로, 확인한 원격 코드만으로 그 최종 도킹 방식/완성 상태를 확인할 수 없다. 별도 실물 실행 코드/다른 미공유 브랜치 존재 여부는 미확인.

## 수정 방향과 경계

일반 복귀는 스테이션 구조물 안이 아니라 도킹 시작점까지의 경로 및 허용된 회전 구간을 다룬다. 도킹 시작점의 위치/허용 자세에서 실제 도킹 프로파일로 제어를 넘기고, 마지막 전후진·마커취득·티칭목표·주차회전·완료판정을 그대로 유지해야 한다. 일반 도착 뒤 임의180도 회전/최종후진진입을 일괄 추가하는 방안은 채택하지 않는다. 실물 운송은 기존 전진 진입 및 지정 주차회전을 유지한다.

예찰103은 경로와 후진 계약을 일치시키는 해결이 필요하지만, 예찰/수확 실물 최종 도킹 연결이 미확인이라 운송 프로파일을 그대로 복제하거나 구조물 내부로 일반주행을 보내지 않는다. 알려진 시뮬 스테이션 마커생략 예외는 유지할 수 있으나 실물 최종도킹 동등성 검증으로 확대하지 않는다.

이번 작업은 코드/설정 비교만 수행. 공통 복귀 변경과 실제주행/도킹 시험은 미실행. 미커밋·미푸시.
