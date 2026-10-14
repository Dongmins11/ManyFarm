

<!-- HARVEST_RECEIVER_COMPAT_20261010 -->
## 기존 관제에 수확 수신부를 맞춤 — 2026-10-10

사용자 승인: 관제를 수정하지 말고 수확 쪽을 맞출 것. 앞선 ready 패키지 PC 적용·로봇 빌드 완료 보고 후 후속 수정이다.
앞선 HARVEST_CONTROL_LINK / HARVEST_CONTROL_READY의 frontend.patch 전달·관제 재빌드 지시는 철회한다. 이 패키지에는 관제 패치가 없다.
기준 관제: Frontend main 5909f0d 원본. 수확: feat/apriltag-localization 25cdf88 + 앞선 ready 적용본.
수확 farm_interfaces/HarvestTask.action에서 추가 section_id를 제거해 원래 Frontend Action과 바이트 동일하게 맞춘다. HarvestTask.msg/ScoutArea/예찰 소스는 변경하지 않는다.
수확 실물 설정의 default_section_id=SEC_01을 명시하고 단일 구역 설정에서만 Section 없는 Goal을 처리한다. 여러 구역/설정 누락은 추측하지 않고 거절한다. Window ID 파싱 없음.
관제의 farm_map_v1을 기존 내부 many_farm_v1에 연결하는 명시적 별칭과 Status 1Hz는 유지한다.
실제 받은 좌표/yaw/task_id/window_id/expected_count 보존. 기존 태그/지도/제어기/footprint 불변.
시험용 harvest_graph_goal.py도 section_id 없는 형식으로 맞춘다. 좌표 생성 기준은 기존 그래프이며 이번 관제 실행에서는 이 시험 Goal을 사용하지 않는다.
현재 실물 단일 구역 연결만 지원한다. 다중 구역 시뮬 등 기존 확장 Section 의존 클라이언트는 이번 Action 변경 영향이 있으므로 그 환경에 바로 배포하지 않는다. 후속 다중 구역 설계 없이 ID를 파싱하지 않는다.
실물에서 현재 팔 정책은 ARRIVAL_ONLY_NO_HARVEST. 도착 SUCCESS와 실제 수확/운송 인계를 구분한다.
검증: 원본 Frontend ControlQueue에서 생성한 Section 없는 Goal2개 → 수확 계약/미션/실제 RouteGraph → 원본 관제 Result 처리 PASS. 실제 DDS/ROS 빌드/이동은 이번 환경에서 미실행.
관제는 재빌드/수정하지 않는다. 로봇은 farm_interfaces와 의존 패키지를 재빌드하고 재시작한다. 이미 ready를 빌드한 상태도 적용기가 허용한다.
백업은 PC /home/eunbi/vmany_backups만 사용한다. 코드 원복은 이번 백업과 비교하고 관련 인터페이스를 다시 빌드해야 한다. commit/push 자동 수행 없음.
