# 운송 지도 계약·그래프 복원 — 2026-10-27

사용자 요청: 기존 운송 운영 지도 기준 복원. PGM/YAML은 기존 로봇과 SHA256 동일했으나 map_id와 그래프는 달랐다. 기존 로봇 /home/wmany/transport_docking_20261013에서 그래프를 직접 확보했다.

- map_id: many_farm_v1 → farm_map_v1 (운송 환경·목적지·장치 설정).
- 운송 map_yaml/route_graph 및 정밀주행 graph_file 4개를 maps/transport_real로 연결. 기존 지도 이미지/YAML과 기존 운영 그래프 보관.
- 노드5/12 x=2.181, 15=(2.181,-1.333), 17=(2.981,-1.333), 20=(1.446,-1.12) 및 연결 edge 복원.
- 공통 maps/many_farm 및 수확/예찰/시뮬 파일 불변. 마커 상대 티칭·속도·회전 정책·5↔12 차단 유지.
- 목적지 노드 기반 계산과 정밀 이탈/정렬이 같은 복원 그래프를 사용한다. initB 등 이전 운송 좌표와 다시 일치한다. 기존 별칭 변경 없음.
- 근거 로그: python3_8557_1793088813231.log에 Goal 거절: robot_id/map_id 불일치 10회. PGM 동일성만으로 지도 계약 전체 동일이라고 설명한 이전 답변 정정.
- 적용 후 실행 중 프로세스는 자동 재시작하지 않는다. 재브링업 필요. 실물 이동 검증 아님.
- 복원 전 설정 백업 reports/before_transport_map_restore.tar.gz. 공통 그래프는 보존되어 경로 설정 복원 가능.

## 티칭·초기위치 영향 검증
기존 로봇의 waffle_marker_targets.yaml, legacy_waffle_sites.yaml, sorter_departure_heading.json은 통합본과 바이트 단위 동일. 마커 상대 티칭은 수정 불필요. profile 차이는 의도된 초기 마커 복구 정책과 후진 yaw=0 유지 및 이번 graph_file 경로뿐임. initB/C/D/CC 실제 스크립트 좌표·방향은 복원 그래프와 일치. 99개 PC 회귀시험 통과.
